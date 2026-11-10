import threading, os, json, uuid, zipfile, datetime as dt
from flask import (render_template, request, redirect, url_for, abort, send_file, flash, g, current_app)
from werkzeug.utils import secure_filename
from . import db, files, jobs
from .auth import login_required, check_csrf, hash_pw
from .scope import user_depts, pick_dept, allowed, units_of, ALL, upload_options
from . import org as ORG

ROLES = {"admin": "관리자", "uploader": "업로드 담당자", "viewer": "회의 참석자"}
KINDS_UPLOADER = {"plan": "투입계획 (인력롤링·부서 양식)"}
KINDS_ADMIN = {"plan": "투입계획 (인력롤링·부서 양식)", "sold": "SOLD투입MM목록 (법인 선택)", "target": "가동인력목록 (법인 선택)",
               "hr": "통합인사정보조회", "stats": "가동가득 통계 (최종 기준)", "cp": "프로젝트 코드 목록 (CP)"}
ALLOWED_EXT = {".xlsx", ".xls", ".xlsm"}   # .xlsm은 저장할 때 매크로를 떼고 .xlsx로 보관

def csrf_token_value():
    from flask import session
    return session.get("csrf", "")

def engine_week_title(label):
    from engine import run as _r
    return _r.week_meta(label)["title"]

def depts():
    p = os.path.join(current_app.config["BASE_DIR"], "gadong", "depts.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []

def week_of(d=None):
    """주차 규칙: 그 주(월~일)의 목요일이 속한 달·순번 (예: 10/1(목)이 있는 주 = 10월 1주차)
    그 주 목~금에 통계를 보내고, 다음 주 월요일에 회의"""
    d = d or dt.date.today()
    thu = d + dt.timedelta(days=3 - d.weekday())
    wk = (thu.day - 1) // 7 + 1
    return f"{thu:%Y-%m}-W{wk}", f"{thu.year}년 {thu.month}월 {wk}주차"

def latest_published():
    r = db.get().execute("SELECT * FROM weeks WHERE published=1 ORDER BY label DESC LIMIT 1").fetchone()
    return r

def published_path(label, name):
    if files.enabled(): return jobs.report_path(label, name, published=True)
    d = os.path.join(current_app.config["STORAGE"], "published", secure_filename(label))
    if os.path.exists(os.path.join(d, "RETIRED.txt")): return None
    p = os.path.join(d, name)
    return p if os.path.exists(p) else None

def validate_excel(fs):
    """확장자·형식·매크로 검사. 문제 없으면 None, 있으면 사유 문자열"""
    name = fs.filename or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXT: return "엑셀 파일(.xlsx, .xlsm, .xls)만 올릴 수 있습니다."
    head = fs.stream.read(8); fs.stream.seek(0)
    if ext in (".xlsx", ".xlsm"):
        if head[:4] != b"PK\x03\x04": return f"{ext[1:]} 형식이 아닙니다."
        try:
            with zipfile.ZipFile(fs.stream) as z:
                names = z.namelist()
                if len(names) > 10000 or sum(item.file_size for item in z.infolist()) > 256 * 1024 * 1024:
                    return "엑셀 내부 데이터가 너무 큽니다. 불필요한 시트·서식을 줄인 뒤 다시 올려 주세요."
                if ext == ".xlsx" and any(n.lower().endswith("vbaproject.bin") for n in names): return "매크로가 포함된 파일은 받지 않습니다."
                if "[Content_Types].xml" not in names: return "엑셀 파일 구조가 올바르지 않습니다."
        except zipfile.BadZipFile:
            return "파일이 손상되었거나 엑셀 형식이 아닙니다."
        finally:
            fs.stream.seek(0)
    if ext == ".xls" and head[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": return "xls 형식이 아닙니다."
    return None

def strip_macros(src, dst):
    """.xlsm → 매크로(vbaProject 등)를 뺀 .xlsx (값·서식·계산된 값은 그대로, 매크로는 실행하지 않음)"""
    import re as _re
    drop = lambda n: _re.search(r"(vbaProject|vbaData|vbaProjectSignature)[^/]*\.(bin|xml)$", n, _re.I) or _re.search(r"(^|/)_rels/vbaProject\.bin\.rels$", n, _re.I)
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            if drop(it.filename): continue
            b = zi.read(it.filename)
            if it.filename == "[Content_Types].xml":
                t = b.decode("utf-8")
                t = t.replace("application/vnd.ms-excel.sheet.macroEnabled.main+xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
                t = _re.sub(r'<(Default|Override)[^>]*(vbaProject|vbaData)[^>]*/>', "", t)
                b = t.encode("utf-8")
            elif it.filename.endswith(".rels"):
                t = b.decode("utf-8"); t2 = _re.sub(r'<Relationship [^>]*Target="[^"]*(vbaProject|vbaData)[^"]*"[^>]*/>', "", t)
                if t2 != t: b = t2.encode("utf-8")
            zo.writestr(it, b)

def place_of(kind, dept, path):
    """업로드 파일이 계산에서 들어갈 자리 → (설명, 오류)"""
    from engine import roles as RL
    fmt = RL.detect_format(path) if kind == "plan" else None
    role, scope, err = RL.role_for_upload(kind, dept, fmt)
    if err: return None, err
    if role: return RL.ROLES[role][0], None
    nm = " · ".join(x for x in (scope["hq"], scope["dv"], scope["tm"]) if x)
    return f"투입계획 · {nm} (부서 파일, 하반기보다 우선)", None

STATUS_CSS = {"확인 대기": "wait", "제출": "sub", "반영": "ok", "보류": "hold", "반려": "rej", "접수": "sub"}
STATUS_HELP = {"확인 대기": "미리보기를 확인한 뒤 '제출'해 주세요", "제출": "관리자 반영 확정을 기다립니다",
               "반영": "다음 통계 집계부터 계산에 들어갑니다", "보류": "계산에서 빠집니다", "반려": "계산에서 빠집니다"}

def make_preview(uid):
    """업로드 미리보기 생성 (별도 프로세스, 보통 수 초)"""
    import subprocess, sys
    base = current_app.config["BASE_DIR"]
    try:
        subprocess.run([sys.executable, "-m", "engine.preview", current_app.config["STORAGE"], str(uid)], cwd=base, timeout=240,
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    except Exception:
        pass

def load_preview(uid):
    if files.enabled():
        row = db.get().execute("SELECT preview_json FROM uploads WHERE id=?", (uid,)).fetchone()
        return json.loads(row["preview_json"]) if row and row["preview_json"] else None
    p = os.path.join(current_app.config["STORAGE"], "previews", f"{int(uid)}.json")
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None

def draft_path(label, name):
    if files.enabled(): return jobs.report_path(label, name)
    d = os.path.join(current_app.config["STORAGE"], "drafts", secure_filename(label), name)
    return d if os.path.exists(d) else None

def is_hq_rolling(path, dept):
    """본부 단위로 고른 인력롤링 파일 → 어느 사업부 파일인지 알 수 없으므로 팀별로 나눠 등록 (고른 본부 안의 팀만, 파일에 없는 팀은 건드리지 않음)"""
    from engine import roles as RL
    corp, hq, dv, tm = RL.split_dept(dept or "")
    if not (corp and hq) or dv or tm: return False
    try: return RL.detect_format(path) == "rolling"
    except Exception: return False

def should_split(path, dept):
    """인력롤링 양식 + 클로잇 본부·사업부 단위(팀 하나를 고른 게 아님)면 체크 없이 자동으로 팀별 분리.
    AX 가득가동현황·DX·MSP 같은 독자 양식, 하반기 총괄, 엔텍 파일은 나누지 않고 부서 파일 그대로 등록."""
    from engine import roles as RL
    if not dept or dept == RL.HB_DEPT: return False
    if dept == ALL: return True
    corp, hq, dv, tm = RL.split_dept(dept)
    if corp != RL.CLO or not hq or tm: return False
    try: return RL.detect_format(path) == "rolling"
    except Exception: return False

def is_team_template(path):
    """우리 사이트에서 받은 '여러 팀 한 시트' 템플릿인지 (숨은 _gadong 시트의 mode=teams)"""
    import openpyxl
    wb = None
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if "_gadong" not in wb.sheetnames: return False
        return any(r and r[0] == "mode" and r[1] == "teams" for r in wb["_gadong"].iter_rows(values_only=True))
    except Exception:
        return False
    finally:
        try:
            if wb is not None: wb.close()
        except Exception: pass

def safe_remove(path):
    """파일 삭제 (Windows에서 잠겨 있어도 오류 화면이 뜨지 않게)"""
    import time
    for _ in range(5):
        try:
            if os.path.exists(path): os.remove(path)
            return
        except PermissionError: time.sleep(0.3)
        except OSError: return

def start_previews(ids):
    """여러 건의 미리보기를 뒤에서 차례로 만듦 (화면은 기다리지 않음)"""
    if files.enabled(): return  # 미리보기 화면의 POST 요청이 실행한다.
    app_ = current_app._get_current_object()
    for i in ids:   # 지웠던 번호가 다시 쓰이면 옛 미리보기가 남아 있어 새 파일인 것처럼 보임 → 새로 만들기 전에 치움
        try: os.remove(os.path.join(current_app.config["STORAGE"], "previews", f"{int(i)}.json"))
        except OSError: pass
    def bg():
        from concurrent.futures import ThreadPoolExecutor
        def one(i):
            with app_.app_context(): make_preview(i)
        if not ids: return
        one(ids[0])   # 첫 건이 큰 파일을 읽어 저장해 두면 나머지는 그걸 재사용 → 나머지는 동시에 만듦
        if len(ids) > 1:
            with ThreadPoolExecutor(max_workers=3) as ex: list(ex.map(one, ids[1:]))
    threading.Thread(target=bg, daemon=True).start()

def register_team_file(u, S, team, tmp_path, orig, wlabel, wtitle, note, status="확인 대기"):
    """팀 하나의 투입계획 파일을 업로드로 등록 → 업로드 id"""
    stored = f"{dt.datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}.xlsx"
    import shutil
    path = os.path.join(S, "uploads", stored); shutil.move(tmp_path, path)
    place, perr = place_of("plan", team, path)
    if perr: safe_remove(path); return None, perr
    ticket = getattr(g, "upload_ticket", None)
    if ticket: ticket += ":" + __import__("hashlib").sha256(team.encode()).hexdigest()
    uid = store_upload(u, team, "plan", wlabel, orig[:200], path, status, f"{note} · 자리: {place}", ticket)
    d = db.get()
    d.execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (wlabel, wtitle)); d.commit()
    return uid, None

def store_upload(user, dept, kind, week, name, path, status, note, ticket=None):
    d = db.get()
    if ticket:
        existing = d.execute("SELECT id FROM uploads WHERE ticket_id=?", (ticket,)).fetchone()
        if existing: safe_remove(path); return existing["id"]
    files.persist(path)
    row = d.execute("INSERT INTO uploads(user_id,dept,kind,week,orig_name,stored_name,size,status,note,uploaded_at,ticket_id) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(ticket_id) DO UPDATE SET ticket_id=excluded.ticket_id RETURNING id,stored_name",
        (user["id"], dept, kind, week, name, os.path.basename(path), os.path.getsize(path), status, note, db.now(), ticket)).fetchone()
    if row["stored_name"] != os.path.basename(path): files.delete("uploads/" + os.path.basename(path))
    return row["id"]

def split_register(u, S, path, fname, dept, wlabel, wtitle):
    """여러 팀이 섞인 인력롤링 파일 → 팀별로 나눠 각각 업로드로 등록 (담당 범위 안의 팀만)"""
    from . import webplan as WP
    import shutil
    from engine import roles as RL
    if RL.detect_format(path) != "rolling": return None, "팀별로 나누기는 인력롤링 양식(템플릿 포함)만 됩니다. 이 파일은 부서 단위로 올려 주세요."
    units = units_of(u, dept or ALL) if dept != RL.HB_DEPT else []
    keys = ORG.expand(S, units)
    if not keys: return None, "담당 범위에 가동대상이 있는 팀이 없습니다. 부서를 고르거나 관리자에게 담당 팀 지정을 요청해 주세요."
    tmpd = os.path.join(S, "work", "_split_" + uuid.uuid4().hex[:8])
    try: parts, unknown, _ = WP.split_by_team(S, path, keys, tmpd)
    except Exception as e: shutil.rmtree(tmpd, ignore_errors=True); return None, f"파일을 읽지 못했습니다 ({type(e).__name__}). 시트 이름·머리글(성명, 1월~12월)을 확인해 주세요."
    if not parts: shutil.rmtree(tmpd, ignore_errors=True); return None, "파일에서 담당 팀 인원을 한 명도 찾지 못했습니다. 성명이 가동인력목록과 같은지 확인해 주세요."
    ids = []
    for k, p in parts.items():
        i, err = register_team_file(u, S, k, p["path"], f"{fname} [{ORG.label(k)}]", wlabel, wtitle, f"팀별 분리 · 원본 {fname} · {p['people']}명", )
        if i: ids.append(i)
    shutil.rmtree(tmpd, ignore_errors=True)
    db.audit(u["username"], "upload_split", f"{fname} → {len(ids)}팀")
    miss = [ORG.label(k) for k in keys if k not in parts]
    msg = f"{fname} → {len(ids)}팀으로 나눠 등록했습니다."
    if miss and not (u["role"] == "admin" and (not dept or dept == ALL)): msg += f" 파일에 없는 팀 {len(miss)}곳({', '.join(miss[:3])}{' …' if len(miss) > 3 else ''})은 이번에 등록되지 않았습니다."
    if unknown: msg += f" 담당 팀 밖이거나 가동인력목록에 없는 이름 {len(unknown)}명은 제외했습니다({', '.join(unknown[:4])}{' …' if len(unknown) > 4 else ''})."
    start_previews(ids)
    return ids, msg

def receive_upload(u, fs, form):
    is_admin = u["role"] == "admin"
    kinds = KINDS_ADMIN if is_admin else KINDS_UPLOADER
    wlabel, wtitle = week_of()
    prev = week_of(dt.date.today() - dt.timedelta(days=7))
    kind = form.get("kind", "plan")
    if is_admin and form.get("week") == prev[0]: wlabel, wtitle = prev
    dept = form.get("dept", "") if is_admin else form.get("dept", "")
    if not is_admin:
        if not allowed(u, dept): abort(403)
        pick_dept(u, dept)
    if kind not in kinds: abort(400)
    if not fs or not fs.filename: flash("파일을 선택해 주세요."); return redirect(url_for("upload"))
    err = validate_excel(fs)
    if err: flash(err); db.audit(u["username"], "upload_reject", f"{fs.filename}: {err}"); return redirect(url_for("upload"))
    ext = os.path.splitext(fs.filename)[1].lower()
    stored = f"{dt.datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}{'.xlsx' if ext == '.xlsm' else ext}"
    path = os.path.join(current_app.config["STORAGE"], "uploads", stored)
    if ext == ".xlsm":   # 매크로를 떼고 .xlsx로 보관
        tmp = path + ".part"; fs.save(tmp)
        try: strip_macros(tmp, path)
        except Exception: flash("파일을 읽을 수 없습니다. 엑셀에서 '다른 이름으로 저장 → .xlsx'로 저장해 올려 주세요."); return redirect(url_for("upload"))
        finally:
            if os.path.exists(tmp): os.remove(tmp)
    else: fs.save(path)
    size = os.path.getsize(path)
    split = kind == "plan" and (form.get("split") == "1" or should_split(path, dept) or is_team_template(path) or is_hq_rolling(path, dept))
    if split and is_admin and dept and dept != ALL and not ORG.roster(current_app.config["STORAGE"])[2]:
        split = False
        flash("첫 계산 전에는 선택한 부서 파일로 접수합니다. 기준 인원이 계산된 다음부터 팀별 자동 분리를 사용할 수 있습니다.")
    if split:
        ids, info = split_register(u, current_app.config["STORAGE"], path, os.path.basename(fs.filename), dept, wlabel, wtitle)
        safe_remove(path)
        if not ids: flash(f"팀별로 나눌 수 없습니다: {info}"); return redirect(url_for("upload"))
        flash(info)
        return redirect(url_for("upload_batch", ids=",".join(map(str, ids))))
    guessed = ""
    if kind == "plan" and not dept:
        from engine import roles as RL
        dept = RL.infer_dept(fs.filename, RL.detect_format(path)) or ""
        guessed = f" (부서 자동 인식: {dept})" if dept else ""
    place, perr = place_of(kind, dept, path)
    if perr:
        safe_remove(path); flash(f"반영할 수 없는 파일입니다: {perr}"); db.audit(u["username"], "upload_reject", f"{fs.filename}: {perr}")
        return redirect(url_for("upload"))
    new_id = store_upload(u, dept, kind, wlabel, os.path.basename(fs.filename)[:200], path, "확인 대기", f"자리: {place}", getattr(g, "upload_ticket", None))
    d = db.get()
    d.execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (wlabel, wtitle)); d.commit()
    db.audit(u["username"], "upload", f"{kind} · {dept} · {fs.filename}")
    start_previews([new_id])   # 미리보기는 뒤에서 만들고 화면은 바로 넘어감 (큰 파일도 멈추지 않음)
    flash(f"업로드했습니다: {fs.filename} → {place}{guessed} · {wtitle}. 미리보기를 만들고 있습니다 (잠시 뒤 자동으로 나타납니다).")
    return redirect(url_for("upload_preview", uid=new_id))


def init_app(app):
    @app.route("/")
    @login_required()
    def home():
        r = g.user["role"]
        return redirect(url_for({"admin": "admin_home", "uploader": "my_home", "viewer": "meeting"}[r]))

    # ---------------- 회의용 (모든 역할) ----------------
    @app.route("/meeting")
    @login_required("admin", "uploader", "viewer")
    def meeting():
        w = latest_published()
        if not w: return render_template("empty.html", msg="아직 게시된 주차가 없습니다. 관리자가 주차를 게시하면 여기에 나타납니다.")
        p = published_path(w["label"], "meeting.html")
        if not p: abort(404)
        db.audit(g.user["username"], "view_meeting", w["label"])
        return send_file(p, mimetype="text/html")

    # ---------------- 관리자 대시보드 ----------------
    @app.route("/admin")
    @login_required("admin")
    def admin_home():
        weeks = [w for w in db.get().execute("SELECT * FROM weeks ORDER BY label DESC").fetchall() if published_path(w["label"], "admin.html")]
        sel = request.args.get("week") or (weeks[0]["label"] if weeks else "")
        built = ""
        p = published_path(sel, "admin.html") if sel else None
        if p: built = dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y.%m.%d %H:%M")
        return render_template("admin_dashboard.html", weeks=weeks, sel=sel, built=built)

    @app.route("/admin/raw/<label>/<page>")
    @login_required("admin")
    def admin_raw(label, page):
        if page not in ("admin.html", "meeting.html"): abort(404)
        p = published_path(label, page)
        if not p: abort(404)
        if page == "admin.html": return _with_week_select(p, label)
        return send_file(p, mimetype="text/html")

    def _with_week_select(p, label):
        """리포트 상단 주차 선택: 게시된 모든 주차로 이동 (같은 달의 1·2주차 등)"""
        import re as _re
        from flask import Response
        html = open(p, encoding="utf-8").read()
        ws = [w for w in db.get().execute("SELECT * FROM weeks ORDER BY label DESC").fetchall() if published_path(w["label"], "admin.html")]
        if len(ws) > 1:
            opts = "".join(f'<option value="{w["label"]}"{" selected" if w["label"] == label else ""}>{w["title"]}</option>' for w in ws)
            sel = f'<select aria-label="기준 주차" onchange="location.href=\'../\'+this.value+\'/admin.html\'">{opts}</select>'
            html = _re.sub(r'<select aria-label="기준 주차">.*?</select>', lambda m: sel, html, count=1, flags=_re.S)
        return Response(html, mimetype="text/html")

    # ---------------- 업로드 ----------------
    @app.route("/upload", methods=["GET", "POST"])
    @login_required("admin", "uploader")
    def upload():
        u = g.user; is_admin = u["role"] == "admin"
        kinds = KINDS_ADMIN if is_admin else KINDS_UPLOADER
        wlabel, wtitle = week_of()
        prev = week_of(dt.date.today() - dt.timedelta(days=7))
        week_opts = [(wlabel, wtitle + " (이번 주)"), (prev[0], prev[1] + " (지난주 · 월요일 회의 자료 수정용)")]
        if request.method == "POST":
            check_csrf()
            return receive_upload(u, request.files.get("file"), request.form)
        d = db.get()
        q = ("SELECT up.*, us.display FROM uploads up LEFT JOIN users us ON us.id=up.user_id " +
             ("" if is_admin else "WHERE up.user_id=? ") + "ORDER BY up.id DESC LIMIT 200")
        rows = d.execute(q, () if is_admin else (u["id"],)).fetchall()
        from engine.roles import HB_DEPT, CLO, ET
        nass = len(user_depts(u)); mydepts = upload_options(u) if not is_admin else user_depts(u); cur = pick_dept(u, request.args.get("dept"))
        S = current_app.config["STORAGE"]; units = ([ALL] if (nass > 1 and not is_admin) else []) + (mydepts if not is_admin else list(depts()))
        tj = {}
        for un in units:
            ks = set(ORG.expand(S, units_of(u, un)))
            tj[un] = [dict(k=t["key"], l=t["label"], dv=t["grp"], n=t["n"]) for t in ORG.teams(S) if t["key"] in ks]
        return render_template("upload.html", mydepts=mydepts, nass=nass, cur=cur, tj=tj, ALL=ALL, css=STATUS_CSS, help=STATUS_HELP, kinds=kinds, rows=rows, depts=[HB_DEPT, CLO, ET] + depts(), week=wtitle, all_kinds=KINDS_ADMIN, week_opts=week_opts)

    @app.route("/admin/uploads/<int:uid>/download")
    @login_required("admin")
    def download(uid):
        r = db.get().execute("SELECT * FROM uploads WHERE id=?", (uid,)).fetchone()
        if not r: abort(404)
        p = files.ensure("uploads/" + secure_filename(r["stored_name"]))
        if not p: abort(404)
        db.audit(g.user["username"], "download", r["orig_name"])
        if files.enabled(): return redirect(files.signed_download("uploads/" + r["stored_name"], r["orig_name"]))
        return send_file(p, as_attachment=True, download_name=r["orig_name"])

    @app.route("/upload/<int:uid>/preview")
    @login_required("admin", "uploader")
    def upload_preview(uid):
        r = db.get().execute("SELECT up.*, us.display FROM uploads up LEFT JOIN users us ON us.id=up.user_id WHERE up.id=?", (uid,)).fetchone()
        if not r: abort(404)
        if g.user["role"] != "admin" and r["user_id"] != g.user["id"] and not allowed(g.user, r["dept"]): abort(403)
        pv = load_preview(uid)
        if pv and pv.get("changes") and "items" not in pv["changes"][0]: pv = None   # 예전 형식(프로젝트별 변화 없음) → 다시 만들기
        if pv is None and request.args.get("make") and not files.enabled(): make_preview(uid); pv = load_preview(uid)
        try: young = (dt.datetime.now() - dt.datetime.strptime(r["uploaded_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() < 600
        except Exception: young = False
        return render_template("upload_preview.html", r=r, pv=pv, css=STATUS_CSS, help=STATUS_HELP, wait=(pv is None and young))

    @app.route("/upload/<int:uid>/act", methods=["POST"])
    @login_required("admin", "uploader")
    def upload_act(uid):
        check_csrf()
        d = db.get(); r = d.execute("SELECT * FROM uploads WHERE id=?", (uid,)).fetchone()
        if not r: abort(404)
        act = request.form.get("act"); admin = g.user["role"] == "admin"; mine = r["user_id"] == g.user["id"]
        new = None
        if act == "submit" and (mine or admin) and r["status"] == "확인 대기": new = "반영" if admin else "제출"
        elif act == "confirm" and admin: new = "반영"
        elif act == "hold" and admin: new = "보류"
        elif act == "reject" and admin: new = "반려"
        if not new: abort(403)
        d.execute("UPDATE uploads SET status=? WHERE id=?", (new, uid))
        if new in ("반려", "보류") and request.form.get("note", "").strip(): d.execute("UPDATE uploads SET note=? WHERE id=?", (request.form["note"].strip()[:300], uid))
        d.commit()
        db.audit(g.user["username"], "upload_" + act, f'{uid} · {r["orig_name"]} → {new}')
        flash({"반영": "반영 확정했습니다. 다음 통계 집계부터 이 파일이 쓰입니다.", "제출": "제출했습니다. 관리자가 확인 후 반영합니다.",
               "보류": "보류했습니다. 계산에서 빠집니다.", "반려": "반려했습니다. 계산에서 빠지고 지금까지 쓰던 파일이 그대로 쓰입니다."}[new])
        nx = request.form.get("next", "")
        if nx.startswith("/") and not nx.startswith("//"): return redirect(nx)
        return redirect(url_for("upload_preview", uid=uid) if new != "반려" else url_for("upload"))

    @app.route("/upload/<int:uid>/delete", methods=["POST"])
    @login_required("admin", "uploader")
    def upload_delete(uid):
        check_csrf()
        d = db.get(); r = d.execute("SELECT * FROM uploads WHERE id=?", (uid,)).fetchone()
        if not r: abort(404)
        if g.user["role"] != "admin" and (r["user_id"] != g.user["id"] or r["status"] == "반영"): abort(403)
        p = os.path.join(current_app.config["STORAGE"], "uploads", secure_filename(r["stored_name"]))
        files.delete("uploads/" + secure_filename(r["stored_name"]))
        d.execute("DELETE FROM uploads WHERE id=?", (uid,)); d.commit()
        try: os.remove(os.path.join(current_app.config["STORAGE"], "previews", f"{int(uid)}.json"))
        except OSError: pass
        db.audit(g.user["username"], "upload_delete", f'{uid} · {r["orig_name"]}')
        flash(f'삭제했습니다: {r["orig_name"]} (다음 통계 집계부터 빠집니다)')
        nx = request.form.get("next", "")
        return redirect(nx if nx.startswith("/") and not nx.startswith("//") else url_for("upload"))

    @app.route("/admin/uploads/<int:uid>/status", methods=["POST"])
    @login_required("admin")
    def upload_status(uid):
        check_csrf()
        st = request.form.get("status")
        if st not in ("확인 대기", "제출", "반영", "보류", "반려"): abort(400)
        db.get().execute("UPDATE uploads SET status=?, note=? WHERE id=?", (st, request.form.get("note", "")[:300], uid))
        wk = request.form.get("week", "")
        import re as _re
        if wk:
            if not _re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])-W[1-5]", wk): abort(400)
            from engine.run import week_meta
            meta = week_meta(wk)
            if meta["thu"][5:7] != wk[5:7]: abort(400)
            db.get().execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (wk, meta["title"]))
            db.get().execute("UPDATE uploads SET week=? WHERE id=?", (wk, uid))
        db.get().commit()
        db.audit(g.user["username"], "upload_status", f"{uid} → {st}")
        return redirect(url_for("upload"))

    # ---------------- 주차 · 통계 집계 · 게시 ----------------
    @app.route("/admin/weeks", methods=["GET", "POST"])
    @login_required("admin")
    def weeks():
        from engine import run as engine_run
        d = db.get(); st = current_app.config["STORAGE"]
        if request.method == "POST":
            check_csrf()
            label = request.form.get("label", ""); act = request.form.get("act")
            if act == "new": label = week_of()[0]
            if act in ("rebuild", "new"):
                ok, msg = jobs.start(label, g.user["username"]) if files.enabled() else engine_run.rebuild(st, label, g.user["username"])
                if ok: d.execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (label, engine_run.week_meta(label)["title"]))
                flash(msg)
            elif act == "cancel" and files.enabled():
                jobs.cancel(label); flash("계산을 취소했습니다. 다시 통계 집계할 수 있습니다.")
            elif act == "publish_draft" and files.enabled():
                try: jobs.publish(label); flash(f"{label} 집계본을 게시했습니다.")
                except ValueError as error: flash(str(error))
            elif act == "publish_draft":
                src = os.path.join(st, "drafts", secure_filename(label)); dst = os.path.join(st, "published", secure_filename(label))
                if not draft_path(label, "meeting.html"): flash("게시할 집계본이 없습니다.")
                else:
                    import shutil
                    os.makedirs(dst, exist_ok=True)
                    for f in ("admin.html", "meeting.html", "checks.json", "inputs.json", "summary.json"):
                        if os.path.exists(os.path.join(src, f)): shutil.copy(os.path.join(src, f), os.path.join(dst, f))
                    if os.path.exists(os.path.join(dst, "RETIRED.txt")): os.remove(os.path.join(dst, "RETIRED.txt"))
                    d.execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (label, engine_run.week_meta(label)["title"]))
                    d.execute("UPDATE weeks SET published=1, published_at=? WHERE label=?", (db.now(), label))
                    try:
                        used = json.load(open(os.path.join(dst, "inputs.json"), encoding="utf-8"))["used"]
                        for x in used:
                            if x.get("upload_id"): d.execute("UPDATE uploads SET status='반영' WHERE id=? AND status='접수'", (x["upload_id"],))
                    except Exception: pass
                    flash(f"{label} 새 집계본을 게시했습니다. 회의용 화면에 바로 보입니다.")
                    from . import backup as _bk
                    threading.Thread(target=_bk.make_backup, args=(current_app._get_current_object(), "게시"), daemon=True).start()
            elif act == "publish":
                if not published_path(label, "meeting.html"): flash("이 주차의 게시본이 없습니다. 먼저 통계 집계 후 집계본을 게시하세요.")
                else: d.execute("UPDATE weeks SET published=1, published_at=? WHERE label=?", (db.now(), label)); flash(f"{label} 게시했습니다.")
            elif act == "backup_now":
                from . import backup as _bk
                ok, msg = _bk.make_backup(current_app._get_current_object(), "수동")
                flash(f"백업했습니다: {msg}" if ok else f"백업하지 못했습니다 — {msg}")
            elif act == "backup_dir":
                from . import backup as _bk
                try: flash(f"백업 폴더를 바꿨습니다: {_bk.set_backup_dir(current_app._get_current_object(), request.form.get('path', ''))}")
                except Exception as e: flash(f"그 폴더에 쓸 수 없습니다 — {e}")
            elif act == "unpublish":
                d.execute("UPDATE weeks SET published=0 WHERE label=?", (label,)); flash(f"{label} 게시를 내렸습니다.")
            d.commit(); db.audit(g.user["username"], f"week_{act}", label)
            return redirect(url_for("weeks"))
        rows = d.execute("SELECT * FROM weeks ORDER BY label DESC").fetchall()
        info = {}
        for r in rows:
            L = r["label"]
            s_ = jobs.status(L) if files.enabled() else (engine_run.read_status(st, L) or {})
            ck = {}
            try: ck = json.load(open(draft_path(L, "checks.json"), encoding="utf-8"))
            except Exception: pass
            info[L] = dict(pub=bool(published_path(L, "meeting.html")), draft=bool(draft_path(L, "meeting.html")), st=s_,
                           nchk=len(ck.get("plan", [])) + len(ck.get("idle", [])) + len(ck.get("warn", [])))
        running = any(i["st"].get("state") == "running" for i in info.values())
        cur = week_of()
        pending = d.execute("SELECT count(*) FROM uploads WHERE status IN ('제출','확인 대기')").fetchone()[0]
        from . import backup as _bk
        bk = dict(dir=_bk.backup_dir(current_app), files=_bk.list_backups(current_app)[:8])
        return render_template("weeks.html", rows=rows, info=info, running=running, cur=cur, has_cur=any(r["label"] == cur[0] for r in rows), pending=pending, bk=bk)

    @app.route("/admin/weeks/<label>")
    @login_required("admin")
    def week_detail(label):
        from engine import run as engine_run
        st = current_app.config["STORAGE"]; L = secure_filename(label)
        s_ = jobs.status(L) if files.enabled() else (engine_run.read_status(st, L) or {})
        ck, inp = {}, {}
        try: ck = json.load(open(draft_path(L, "checks.json"), encoding="utf-8"))
        except Exception: pass
        try: inp = json.load(open(draft_path(L, "inputs.json"), encoding="utf-8"))
        except Exception: pass
        log = s_.get("log", "") if files.enabled() else ""
        lp = os.path.join(st, "work", L, "log.txt")
        if s_.get("state") == "error" and os.path.exists(lp): log = open(lp, encoding="utf-8").read()[-6000:]
        return render_template("week_detail.html", label=L, st=s_, ck=ck, inp=inp, log=log, draft=bool(draft_path(L, "meeting.html")), meta=engine_run.week_meta(L))

    @app.route("/admin/draft/<label>/<page>")
    @login_required("admin")
    def admin_draft(label, page):
        if page not in ("admin.html", "meeting.html"): abort(404)
        p = draft_path(label, page)
        if not p: abort(404)
        return send_file(p, mimetype="text/html")

    # ---------------- 사용자 관리 ----------------
    @app.route("/admin/users", methods=["GET", "POST"])
    @login_required("admin")
    def users():
        d = db.get()
        if request.method == "POST":
            check_csrf(); act = request.form.get("act")
            if act == "create":
                un = request.form.get("username", "").strip(); pw = request.form.get("password", "")
                role = request.form.get("role"); dept = request.form.get("dept", "")
                if role not in ROLES or not un or len(pw) < 8: flash("아이디, 역할, 8자 이상 비밀번호를 확인해 주세요.")
                elif role == "uploader" and not dept: flash("업로드 담당자는 담당 부서를 지정해야 합니다.")
                else:
                    try:
                        d.execute("INSERT INTO users(username,display,pw_hash,role,dept,created_at) VALUES(?,?,?,?,?,?)",
                                  (un, request.form.get("display", un).strip() or un, hash_pw(pw), role, dept if role == "uploader" else "", db.now()))
                        d.execute("UPDATE users SET email=? WHERE username=?", (request.form.get("email", "").strip(), un)); d.commit(); flash(f"{un} 계정을 만들었습니다."); db.audit(g.user["username"], "user_create", f"{un} ({role})")
                    except Exception: d.rollback(); flash("이미 있는 아이디입니다.")
            elif act == "setemail":
                em = request.form.get("email", "").strip()
                if em and ("@" not in em or " " in em): flash("메일 주소 형식을 확인해 주세요.")
                else:
                    d.execute("UPDATE users SET email=? WHERE id=?", (em, int(request.form.get("id")))); d.commit(); flash("메일 주소를 저장했습니다.")
            elif act == "setrole":
                uid = int(request.form.get("id")); role = request.form.get("role"); dept = request.form.get("dept", "")
                u_ = d.execute("SELECT * FROM users WHERE id=? AND active<>-1", (uid,)).fetchone()
                if not u_: flash("계정을 찾지 못했습니다.")
                elif uid == g.user["id"]: flash("본인 역할은 바꿀 수 없습니다. (스스로 관리자 권한을 잃는 것을 막기 위해)")
                elif role not in ROLES: flash("역할을 골라 주세요.")
                elif role == u_["role"]: flash("이미 그 역할입니다.")
                elif u_["role"] == "admin" and d.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND id<>?", (uid,)).fetchone()[0] == 0:
                    flash("마지막 관리자입니다. 다른 관리자가 있어야 역할을 바꿀 수 있습니다.")
                elif role == "uploader" and not (dept or u_["dept"]): flash("업로드 담당자로 바꾸려면 담당 부서를 함께 골라 주세요.")
                else:
                    nd = (dept or u_["dept"]) if role == "uploader" else ""
                    d.execute("UPDATE users SET role=?, dept=?, depts=? WHERE id=?", (role, nd, json.dumps([nd], ensure_ascii=False) if nd else "", uid)); d.commit()
                    flash(f"{u_['username']} 역할을 {ROLES[u_['role']]} → {ROLES[role]}(으)로 바꿨습니다."); db.audit(g.user["username"], "user_role", f"{u_['username']} {u_['role']}→{role}")
            elif act == "delete":
                uid = int(request.form.get("id"))
                u_ = d.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                if not u_: flash("계정을 찾지 못했습니다.")
                elif uid == g.user["id"]: flash("본인 계정은 삭제할 수 없습니다.")
                elif u_["role"] == "admin" and u_["active"] == 1 and d.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND id<>?", (uid,)).fetchone()[0] == 0:
                    flash("마지막 관리자는 삭제할 수 없습니다.")
                else:
                    d.execute("DELETE FROM users WHERE id=?", (uid,)); d.commit()
                    flash(f"{u_['username']} 계정을 삭제했습니다. (이 계정이 올린 파일·기록은 그대로 남습니다)"); db.audit(g.user["username"], "user_delete", f"{u_['username']} ({u_['role']})")
            elif act in ("deactivate", "activate"):
                uid = int(request.form.get("id"))
                if uid == g.user["id"]: flash("본인 계정은 끌 수 없습니다.")
                else: d.execute("UPDATE users SET active=? WHERE id=?", (1 if act == "activate" else 0, uid)); d.commit()
            elif act == "approve":
                uid = int(request.form.get("id")); role = request.form.get("role"); dept = request.form.get("dept", "")
                u_ = d.execute("SELECT * FROM users WHERE id=? AND active=-1", (uid,)).fetchone()
                if not u_: flash("이미 처리된 신청입니다.")
                elif role not in ROLES: flash("역할을 골라 주세요.")
                elif role == "uploader" and not dept: flash("업로드 담당자는 담당 부서를 지정해야 합니다.")
                else:
                    d.execute("UPDATE users SET active=1, role=?, dept=? WHERE id=?", (role, dept if role == "uploader" else "", uid)); d.commit()
                    flash(f"{u_['username']} ({u_['display']}) 가입을 승인했습니다."); db.audit(g.user["username"], "signup_approve", f"{u_['username']} ({role})")
            elif act == "reject":
                uid = int(request.form.get("id"))
                u_ = d.execute("SELECT * FROM users WHERE id=? AND active=-1", (uid,)).fetchone()
                if u_:
                    d.execute("DELETE FROM users WHERE id=?", (uid,)); d.commit()
                    flash(f"{u_['username']} ({u_['display']}) 가입 신청을 반려했습니다."); db.audit(g.user["username"], "signup_reject", u_["username"])
            elif act == "setdepts":
                uid = int(request.form.get("id")); okset = set(depts()) | {t["key"] for t in ORG.teams(current_app.config["STORAGE"])}; sel = [x for x in request.form.getlist("depts") if x in okset]
                if not sel: flash("담당 부서를 하나 이상 골라 주세요.")
                else:
                    d.execute("UPDATE users SET dept=?, depts=? WHERE id=?", (sel[0], json.dumps(sel, ensure_ascii=False), uid)); d.commit()
                    flash(f"담당 부서를 {len(sel)}개로 저장했습니다."); db.audit(g.user["username"], "user_depts", f"{uid} · {', '.join(sel)}")
            elif act == "reset":
                uid = int(request.form.get("id")); pw = request.form.get("password", "")
                if len(pw) < 8: flash("비밀번호는 8자 이상이어야 합니다.")
                else: d.execute("UPDATE users SET pw_hash=?, fail_count=0, locked_until='' WHERE id=?", (hash_pw(pw), uid)); d.commit(); flash("비밀번호를 바꿨습니다.")
            return redirect(url_for("users"))
        rows = d.execute("SELECT * FROM users WHERE active<>-1 ORDER BY role, username").fetchall()
        pend = d.execute("SELECT * FROM users WHERE active=-1 ORDER BY id").fetchall()
        return render_template("users.html", rows=rows, pend=pend, roles=ROLES, depts=depts(), teamkeys=[t["key"] for t in ORG.teams(current_app.config["STORAGE"]) if t["key"] not in depts()], user_depts=user_depts)

    # ---------------- 화면에서 투입계획 직접 입력 ----------------
    @app.route("/plan/edit", methods=["GET", "POST"])
    @login_required("admin", "uploader")
    def plan_edit():
        from . import webplan as WP, submit as SB
        u = g.user; is_admin = u["role"] == "admin"; st = current_app.config["STORAGE"]
        if request.method == "POST":
            if request.headers.get("X-CSRF", "") != csrf_token_value(): abort(400)
            body = request.get_json(force=True, silent=True) or {}
            dept = body.get("dept", "")
            if not dept or not allowed(u, dept): return {"ok": False, "msg": "담당 부서가 아닙니다."}, 403
            keys = [k for k in (body.get("keys") or []) if isinstance(k, str)] or None
            data, err = WP.load(st, units_of(u, dept), keys)
            if err: return {"ok": False, "msg": err}, 400
            base = {p["id"]: p for p in data["people"]}
            cur = data["cur"]
            def norm(lines):
                return sorted((l["pj"].strip(), l["kind"], tuple(round(float(x or 0), 3) for x in l["mm"][cur - 1:])) for l in lines if (l["pj"] or "").strip() and sum(float(x or 0) for x in l["mm"][cur - 1:]) > 0.0001)
            edited, changed = {}, set()
            for p in body.get("people", []):
                b = base.get(p.get("id"))
                if not b: continue
                lines = []
                for l in p.get("lines", [])[:30]:
                    mm = [min(1.0, max(0.0, float(x or 0))) for x in (l.get("mm") or [0] * 12)][:12]
                    lines.append(dict(pj=str(l.get("pj", ""))[:200], code=str(l.get("code", ""))[:30], kind=l.get("kind") if l.get("kind") in ("이행", "제안", "R&D") else "이행", mm=mm + [0.0] * (12 - len(mm))))
                edited[b["id"]] = lines
                if norm(lines) != norm(b["lines"]): changed.add(b["tk"])
            wl = max(week_of()[0], data["label"]); wt = engine_week_title(wl)
            rest = bool(body.get("rest"))   # 체크했을 때만: 고치지 않은 팀도 지금 값 그대로 함께 저장 (기본은 고친 팀만)
            todo = [t["key"] for t in data["teams"] if t["key"] in changed or (rest and SB.week_state(t["key"], wl)[0] in ("미제출", "반려", "보류"))]
            if not todo: return {"ok": False, "msg": "고친 곳이 없습니다." if not rest else "고친 곳이 없고, 이미 모두 이번 주에 제출된 팀입니다."}, 400
            import tempfile
            tmpd = tempfile.mkdtemp(); ids = []
            for k in todo:
                ppl = []
                for b in data["people"]:
                    if b["tk"] != k: continue
                    ppl.append(dict(gid=b["gid"], name=b["name"], dv=b["dv"], team=b["team"], lines=edited.get(b["id"], b["lines"])))
                tmp = os.path.join(tmpd, f"{len(ids)}.xlsx")
                WP.write_xlsx(tmp, k, ppl, u["display"])
                orig = f"화면입력_{ORG.label(k)}_{dt.datetime.now():%m%d_%H%M}.xlsx"
                i, perr = register_team_file(u, st, k, tmp, orig, wl, wt, "화면 입력" + ("" if k in changed else " · 고친 곳 없음(그대로)"))
                if perr: return {"ok": False, "msg": f"{ORG.label(k)}: {perr}"}, 400
                ids.append(i)
            import shutil; shutil.rmtree(tmpd, ignore_errors=True)
            db.audit(u["username"], "plan_web_edit", f"{dept} · {len(ids)}팀 (고친 팀 {len(changed)})")
            if len(ids) == 1:
                start_previews(ids)   # 미리보기는 뒤에서 만들고, 저장은 바로 끝냄 (미리보기 화면이 알아서 새로고침)
                flash(f"화면에서 입력한 투입계획을 저장했습니다 → {ORG.label(todo[0])} · {wt}. 미리보기를 확인하고 '제출'해 주세요.")
                return {"ok": True, "url": url_for("upload_preview", uid=ids[0])}
            start_previews(ids)
            flash(f"{len(ids)}팀을 저장했습니다 (고친 팀 {len(changed)}곳 · 나머지는 지금 값 그대로) · {wt}. 팀별 미리보기를 확인하고 한 번에 제출하세요.")
            return {"ok": True, "url": url_for("upload_batch", ids=",".join(map(str, ids)))}
        if not is_admin and request.args.get("dept") and not allowed(u, request.args.get("dept")): abort(403)
        dept = (request.args.get("dept", "") if is_admin else pick_dept(u, request.args.get("dept"))) or ""
        if dept and not allowed(u, dept): abort(403)
        keys = request.args.getlist("team") or None
        data, err = (WP.load(st, units_of(u, dept), keys) if dept else (None, None))
        if is_admin: opts = [x for x in depts() if " · " in x]
        else: opts = ([ALL] if len(user_depts(u)) > 1 else []) + (user_depts(u) if len(user_depts(u)) > 1 else [])
        return render_template("plan_edit.html", dept=dept, data=data, err=err, opts=opts, ALL=ALL)

    @app.route("/plan/template")
    @login_required("admin", "uploader")
    def plan_template():
        """담당 범위 업로드 템플릿: 한 시트 + 팀 열 (고른 팀만, 안 고르면 범위 전체)"""
        from . import webplan as WP
        import tempfile
        u = g.user
        if u["role"] != "admin" and request.args.get("dept") and not allowed(u, request.args.get("dept")): abort(403)
        dept = request.args.get("dept", "") if u["role"] == "admin" else pick_dept(u, request.args.get("dept"))
        if not dept or not allowed(u, dept): abort(403)
        keys = request.args.getlist("team") or None
        fd, tmp = tempfile.mkstemp(suffix=".xlsx"); os.close(fd)
        err = WP.template_xlsx(tmp, current_app.config["STORAGE"], units_of(u, dept), u["display"], keys)
        if err: os.remove(tmp); flash(f"템플릿을 만들지 못했습니다: {err}"); return redirect(url_for("upload"))
        db.audit(u["username"], "template_download", f"{dept} · {len(keys) if keys else '전체'}팀")
        S = current_app.config["STORAGE"]
        tk = [k for k in ORG.expand(S, units_of(u, dept)) if not keys or k in keys]
        short = ORG.label(tk[0]) if len(tk) == 1 else (ORG.summary(tk) if tk else dept.split(" · ")[-1])
        short = short.replace(" › ", "_").replace("/", "_")
        import io
        buf = io.BytesIO(open(tmp, "rb").read()); os.remove(tmp)   # 인사 정보가 든 임시 파일은 바로 지움
        return send_file(buf, as_attachment=True, download_name=f"({dt.date.today():%y%m%d}) 투입계획_업로드템플릿_{short}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ---------------- 팀별로 나뉘어 등록된 업로드 묶음 ----------------
    def _batch_rows(ids):
        d = db.get(); out = []
        for i in ids[:100]:
            r = d.execute("SELECT up.*, us.display FROM uploads up LEFT JOIN users us ON us.id=up.user_id WHERE up.id=?", (i,)).fetchone()
            if not r: continue
            if g.user["role"] != "admin" and r["user_id"] != g.user["id"] and not allowed(g.user, r["dept"]): abort(403)
            out.append(r)
        return out

    @app.route("/upload/batch")
    @login_required("admin", "uploader")
    def upload_batch():
        try: ids = [int(x) for x in request.args.get("ids", "").split(",") if x.strip()]
        except ValueError: abort(400)
        rows = _batch_rows(ids)
        if not rows: abort(404)
        pvs = {r["id"]: load_preview(r["id"]) for r in rows}
        return render_template("upload_batch.html", rows=rows, pvs=pvs, ids=",".join(map(str, ids)), css=STATUS_CSS, help=STATUS_HELP, org=ORG)

    @app.route("/upload/batch/act", methods=["POST"])
    @login_required("admin", "uploader")
    def upload_batch_act():
        check_csrf()
        ids = [int(x) for x in request.form.get("ids", "").split(",") if x.strip().isdigit()]
        rows = _batch_rows(ids); admin = g.user["role"] == "admin"; d = db.get(); n = 0
        for r in rows:   # 관리자는 '제출'된 건도 한 번에 반영 확정 (담당자는 '확인 대기' → 제출)
            if (r["status"] == "확인 대기" or (admin and r["status"] == "제출")) and (admin or r["user_id"] == g.user["id"]):
                d.execute("UPDATE uploads SET status=? WHERE id=?", ("반영" if admin else "제출", r["id"])); n += 1
        d.commit(); db.audit(g.user["username"], "upload_batch_submit", f"{n}건")
        flash(f"{n}팀을 {'반영 확정' if admin else '제출'}했습니다." + ("" if admin else " 관리자가 확인 후 반영합니다."))
        nx = request.form.get("next", "")
        if nx.startswith("/") and not nx.startswith("//"): return redirect(nx)
        return redirect(url_for("upload_batch", ids=",".join(map(str, ids))))

    @app.route("/guide")
    @login_required("admin", "uploader")
    def guide(): return render_template("guide.html")

    from . import targets as _tg; _tg.register(app)
    from . import remind as _rm; _rm.register(app)

    @app.route("/admin/audit")
    @login_required("admin")
    def audit_log():
        rows = db.get().execute("SELECT * FROM audit ORDER BY id DESC LIMIT 300").fetchall()
        return render_template("audit.html", rows=rows)

    @app.errorhandler(403)
    def forbidden(e): return render_template("empty.html", msg="이 화면을 볼 권한이 없습니다."), 403
    @app.errorhandler(413)
    def too_big(e): return render_template("empty.html", msg="파일이 너무 큽니다 (최대 20MB)."), 413

    app.jinja_env.globals["ROLES"] = ROLES
    app.jinja_env.globals["user_depts"] = user_depts
    def pending_count():
        try: return db.get().execute("SELECT COUNT(*) FROM users WHERE active=-1").fetchone()[0]
        except Exception: return 0
    app.jinja_env.globals["pending_count"] = pending_count
    app.jinja_env.globals["KIND_NAMES"] = KINDS_ADMIN
