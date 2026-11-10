"""주간 제출 흐름 + 인사 변동 제출
- /my            업로드 담당자 첫 화면: 이번 주 제출 상태 · 제출 방법 3가지(화면 입력 / 템플릿 업로드 / 변동없음) · 지난 주차 이력 · 인사 변동 제출
- /my/nochange   변동없음: 우리 부서가 마지막으로 '반영'된 파일을 그대로 이번 주 제출로 복사
- /my/hr         인사 변동 제출 (월 중간 입사·퇴사·휴직·복직·조직이동). 회사 인사자료가 기준, 제출은 참고용
- /admin/board   관리자: 주차별 부서 제출 현황(미제출 포함) · 반영 확정 · 변동 제출 확인
"""
import os, json, shutil, uuid, datetime as dt
from flask import render_template, request, redirect, url_for, abort, flash, g, current_app
from werkzeug.utils import secure_filename
from . import db, files
from .auth import login_required, check_csrf
from .scope import user_depts, pick_dept, allowed, units_of, ALL
from . import org as ORG

HR_KINDS = ["입사", "퇴사", "휴직", "복직", "조직이동", "기타"]
HR_ST = ["접수", "확인", "반영", "인사자료와 다름"]
HR_HELP = {"접수": "관리자가 아직 보지 않았습니다", "확인": "관리자가 확인했습니다 (반영으로 바꾸면 계산에 들어갑니다)",
           "반영": "다음 재계산부터 가동대상MM에 반영됩니다", "인사자료와 다름": "회사 인사자료와 달라 확인이 필요합니다"}
# 제출 상태 (이번 주 · 부서 기준) → (화면 이름, css)
ST_VIEW = {"미제출": ("미제출", "rej"), "확인 대기": ("작성 중", "wait"), "제출": ("제출", "sub"), "변동없음": ("변동없음 제출", "sub"),
           "반영": ("반영", "ok"), "보류": ("보류", "hold"), "반려": ("반려 · 다시 제출", "rej"), "일부": ("일부 제출", "wait")}
NOCHANGE = "변동없음"

def _now(): return db.now()

def ensure_schema(app):
    if app.config.get("DATABASE_URL"): return
    with db.transaction(app) as c:
        c.executescript("""
CREATE TABLE IF NOT EXISTS hr_notes(
  id INTEGER PRIMARY KEY, dept TEXT, user_id INTEGER, name TEXT, sabun TEXT DEFAULT '', kind TEXT, date TEXT,
  to_org TEXT DEFAULT '', memo TEXT DEFAULT '', status TEXT DEFAULT '접수', admin_note TEXT DEFAULT '',
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
""")

def get_setting(key, default=None):
    r = db.get().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if not r: return default
    try: return json.loads(r["value"])
    except Exception: return default

def set_setting(key, val):
    d = db.get(); d.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(val, ensure_ascii=False))); d.commit()

WD = "월화수목금토일"
def deadline_default():
    v = get_setting("deadline_default") or {}
    return int(v.get("wd", 3)), v.get("time", "15:00")

def deadline(week):
    """그 주 업로드 마감 → (datetime, 이 주만 따로 정했는지). 기본: 매주 목요일 15:00 (관리자가 한 번 정하면 계속 적용)"""
    v = get_setting("deadline:" + week)
    if v:
        try: return dt.datetime.fromisoformat(v), True
        except ValueError: pass
    wd, tm = deadline_default()
    mon = dt.date.fromisoformat(week_dates(week)[0]); d = mon + dt.timedelta(days=wd)
    hh, mm = map(int, tm.split(":"))
    return dt.datetime(d.year, d.month, d.day, hh, mm), False

def dl_text(d):
    ap = "오전" if d.hour < 12 else "오후"; h = d.hour if d.hour <= 12 else d.hour - 12
    return f"{d.month}/{d.day}({WD[d.weekday()]}) {ap} {h}시" + (f" {d.minute}분" if d.minute else "")

def _plan_rows(week):
    """그 주차 투입계획 업로드 전부 (최신순) — 한 요청 안에서는 한 번만 읽음"""
    c = getattr(g, "_plan_rows", None)
    if c is None: c = g._plan_rows = {}
    if week not in c:
        c[week] = db.get().execute("SELECT up.*, us.display FROM uploads up LEFT JOIN users us ON us.id=up.user_id "
                                   "WHERE up.kind='plan' AND up.dept<>'' AND up.week=? ORDER BY up.id DESC", (week,)).fetchall()
    return c[week]

def _covers(updept, unit):
    """올린 부서(updept)가 그 범위(unit: 팀 또는 사업부)를 덮는지 — 법인만 적은 하반기 총괄은 제외"""
    if updept == unit: return True
    u = ORG.split_dept(updept)
    if not u[1]: return False
    if ORG.covers(updept, unit): return True
    if not u[3]:   # 팀 없이 올린 파일은 계산에서 이렇게 쓰이므로 제출도 같은 범위로 봄: EC1·EC2 한 파일, AX는 본부 전체
        t = ORG.split_dept(unit)
        if u[2] in ("EC1사업부", "EC2사업부") and t[:2] == u[:2] and t[2] in ("EC1사업부", "EC2사업부"): return True
        if u[1] == "AX사업본부" and t[:2] == u[:2]: return True
    return False

def week_state(dept, week):
    """그 범위(팀·사업부)·주차의 최신 투입계획 업로드 → (상태키, 업로드 행). 사업부 단위로 올린 파일도 그 아래 팀의 제출로 봄"""
    for r in _plan_rows(week):
        if _covers(r["dept"], dept):
            st = r["status"]
            if st == "제출" and (r["note"] or "").startswith(NOCHANGE): st = "변동없음"
            return st, r
    return "미제출", None

def last_applied(dept):
    for r in db.get().execute("SELECT * FROM uploads WHERE kind='plan' AND dept<>'' AND status='반영' ORDER BY id DESC LIMIT 400"):
        if _covers(r["dept"], dept): return r
    return None

def unit_teams(storage, dept, user=None):
    """화면에서 고른 범위 → 팀 목록 [{key,label,dv,n}]"""
    u = user
    units = units_of(u, dept) if u is not None else [dept]
    ks = set(ORG.expand(storage, units))
    return [t for t in ORG.teams(storage) if t["key"] in ks]

def agg_state(states):
    """팀별 상태 목록 → 한 줄 요약 상태"""
    s = set(states)
    if len(s) == 1: return states[0]
    done = [x for x in states if x != "미제출"]
    return "일부" if done and len(done) < len(states) else ("반려" if "반려" in s else "확인 대기" if "확인 대기" in s else "제출" if "제출" in s or "변동없음" in s else "반영")

def weeks_back(n):
    from .views import week_of
    base = dt.date.fromisoformat(week_dates(week_of()[0])[0])
    out, seen = [], set()
    for i in range(n + 3):
        lb, tt = week_of(base - dt.timedelta(days=7 * i))
        if lb not in seen: seen.add(lb); out.append((lb, tt))
    return out[:n]

def week_dates(label):
    """주차 라벨 → (월요일, 목요일) ISO 문자열. 그 달 n번째 목요일이 있는 주"""
    y, m, w = int(label[:4]), int(label[5:7]), int(label.split("W")[-1])
    d = dt.date(y, m, 1); first_thu = d + dt.timedelta(days=(3 - d.weekday()) % 7)
    thu = first_thu + dt.timedelta(days=7 * (w - 1)); mon = thu - dt.timedelta(days=3)
    return mon.isoformat(), thu.isoformat()

def target_depts():
    """제출 대상 범위(부서·사업부 문자열): 설정에 저장된 목록 → 없으면 업로드 담당자 담당 범위 + 최근 8주 투입계획 올린 부서"""
    from engine.roles import HB_DEPT
    s = get_setting("submit_depts")
    if s: return s
    d = db.get(); out = []
    for r in d.execute("SELECT * FROM users WHERE role='uploader' AND active=1"):
        for x in user_depts(r):
            if x not in out: out.append(x)
    wk = [w for w, _ in weeks_back(8)]
    q = "SELECT DISTINCT dept FROM uploads WHERE kind='plan' AND dept<>'' AND week IN (%s) ORDER BY dept" % ",".join("?" * len(wk))
    for r in d.execute(q, wk):
        if r["dept"] not in out and r["dept"] != HB_DEPT and ORG.split_dept(r["dept"])[1]: out.append(r["dept"])
    return sorted(out)

def init_app(app):
    ensure_schema(app)
    from .views import week_of, STATUS_CSS, STATUS_HELP, depts as all_depts

    # ---------------- 업로드 담당자 첫 화면 ----------------
    @app.route("/my")
    @login_required("admin", "uploader")
    def my_home():
        u = g.user; S = current_app.config["STORAGE"]
        if u["role"] == "admin" and not request.args.get("dept"): return redirect(url_for("submit_board"))
        dept = request.args.get("dept") if u["role"] == "admin" else pick_dept(u, request.args.get("dept"))
        if not dept: return render_template("empty.html", msg="담당 부서가 지정되지 않았습니다. 관리자에게 부서 지정을 요청해 주세요.")
        if not allowed(u, dept): abort(403)
        wl, wt = week_of(); mon, thu = week_dates(wl)
        tms = unit_teams(S, dept, u)
        trows = []
        for t in tms:
            s_, r_ = week_state(t["key"], wl); trows.append(dict(t=t, st=s_, r=r_))
        if trows:
            st = agg_state([x["st"] for x in trows]); row = trows[0]["r"] if len(trows) == 1 else None
        else: st, row = week_state(dept, wl)
        keys = [t["key"] for t in tms] or [dept]
        firsts = [r["w"] for r in db.get().execute("SELECT dept, min(week) w FROM uploads WHERE kind='plan' AND dept<>'' GROUP BY dept") if any(_covers(r["dept"], k) for k in keys)]
        first = min(firsts) if firsts else wl
        hist = []
        for lb, tt in weeks_back(9)[1:]:
            if lb < first: break   # 처음 낸 주차 이전은 보이지 않음
            if trows:
                ss = [week_state(k, lb) for k in keys]; s2 = agg_state([x[0] for x in ss]); r2 = ss[0][1] if len(ss) == 1 else None
                n_ok = sum(1 for x in ss if x[0] != "미제출")
            else: s2, r2 = week_state(dept, lb); n_ok = 0
            hist.append(dict(label=lb, title=tt, st=s2, r=r2, n=len(keys), n_ok=n_ok))
        last = last_applied(keys[0]) if len(keys) == 1 else next((x for x in (last_applied(k) for k in keys) if x), None)
        us = units_of(u, dept) + [dept] + keys
        notes = db.get().execute("SELECT * FROM hr_notes WHERE dept IN (%s) ORDER BY id DESC LIMIT 30" % ",".join("?" * len(us)), us).fetchall()
        dl, _ = deadline(wl); now = dt.datetime.now()
        from .db import now as _dbnow
        try: now = dt.datetime.fromisoformat(_dbnow())   # 데모 시각 고정과 맞춤
        except Exception: pass
        left = dl - now
        try: hr_ok = int(request.args.get("hr_ok", 0))
        except ValueError: hr_ok = 0
        chips = []
        if u["role"] != "admin":
            L = user_depts(u)
            for dp in ([ALL] if len(L) > 1 else []) + L:
                tt = unit_teams(S, dp, u); ag = agg_state([week_state(t["key"], wl)[0] for t in tt]) if tt else week_state(dp, wl)[0]
                chips.append(dict(dept=dp, st=ag, n=len(tt)))
        mine = chips
        cnt = {}
        for x in trows: cnt[x["st"]] = cnt.get(x["st"], 0) + 1
        return render_template("my_home.html", dl=dl_text(dl), late=left.total_seconds() < 0, left_h=int(left.total_seconds() // 3600), mine=mine, hr_ok=hr_ok, dept=dept, wl=wl, wt=wt, mon=mon, thu=thu, st=st, row=row, hist=hist, last=last,
                               trows=trows, cnt=cnt, ALL=ALL, dlabel=("내 담당 전체" if dept == ALL else dept), org=ORG, agg=agg_state,
                               notes=notes, V=ST_VIEW, HR_KINDS=HR_KINDS, HR_HELP=HR_HELP, help=STATUS_HELP, today=dt.date.fromisoformat(thu).isoformat())

    @app.route("/my/nochange", methods=["POST"])
    @login_required("admin", "uploader")
    def my_nochange():
        check_csrf()
        from . import webplan as WP
        u = g.user; dept = request.form.get("dept", ""); S = current_app.config["STORAGE"]
        if not allowed(u, dept): abort(403)
        wl, wt = week_of()
        tms = unit_teams(S, dept, u)
        keys = [t["key"] for t in tms] or [dept]
        need = [k for k in keys if week_state(k, wl)[0] in ("미제출", "반려", "보류", "확인 대기")]
        if not need:
            flash(f"이번 주({wt})는 모두 이미 제출한 상태입니다. 다시 내려면 아래 이력에서 먼저 삭제해 주세요.")
            return redirect(url_for("my_home", dept=dept))
        groups, none_ = {}, []
        for k in need:
            src = last_applied(k)
            if not src: none_.append(k); continue
            groups.setdefault(src["id"], (src, []))[1].append(k)
        if not groups:
            flash("지난번에 반영된 파일이 없어 '변동없음'으로 낼 수 없습니다. 화면에서 입력하거나 템플릿을 올려 주세요.")
            return redirect(url_for("my_home", dept=dept))
        new = "반영" if u["role"] == "admin" else "제출"
        d = db.get(); made = 0; ids = []
        from engine import roles as RL
        def put(updept, src, sp, ks):
            ext = ".xlsx" if sp.endswith(".xlsx") else os.path.splitext(sp)[1]
            stored = f"{dt.datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}{ext}"
            shutil.move(sp, os.path.join(S, "uploads", stored)) if sp.startswith(tmpd) else shutil.copy(sp, os.path.join(S, "uploads", stored))
            files.persist(os.path.join(S, "uploads", stored))
            new_id = d.execute("INSERT INTO uploads(user_id,dept,kind,week,orig_name,stored_name,size,status,note,uploaded_at) VALUES(?,?,?,?,?,?,?,?,?,?) RETURNING id",
                      (u["id"], updept, "plan", wl, src["orig_name"], stored, os.path.getsize(os.path.join(S, "uploads", stored)), new,
                       f"{NOCHANGE} · 지난 값 그대로 (#{src['id']} · {src['week']} 반영본)", _now())).fetchone()[0]
            ids.append(new_id)
        tmpd = os.path.join(S, "work", "_split_" + uuid.uuid4().hex[:8])
        for src, ks in groups.values():
            sp = files.ensure("uploads/" + secure_filename(src["stored_name"]))
            if not sp: continue
            if not os.path.exists(sp): continue
            if src["dept"] in ks and len(ks) == 1:   # 팀 단위로 낸 파일 → 그대로
                put(src["dept"], src, sp, ks); made += 1; continue
            parts = {}
            try:
                if RL.detect_format(sp) == "rolling": parts, _, _ = WP.split_by_team(S, sp, ks, tmpd)
            except Exception: parts = {}
            if parts:
                for k, p in parts.items(): put(k, src, p["path"], [k]); made += 1
            else: put(src["dept"], src, sp, ks); made += len(ks)   # 나눌 수 없는 양식 → 올렸던 범위 그대로
        shutil.rmtree(tmpd, ignore_errors=True)
        d.execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (wl, wt)); d.commit()
        db.audit(u["username"], "plan_nochange", f"{dept} · {wl} · {made}팀")
        msg = f"{wt} '변동없음'으로 {made}팀을 제출했습니다. 지난번 반영본이 그대로 쓰입니다."
        if none_: msg += f" (지난 반영본이 없는 {len(none_)}팀은 화면 입력이나 파일로 내 주세요: {', '.join(ORG.label(k) for k in none_[:4])}{' …' if len(none_) > 4 else ''})"
        flash(msg)
        return redirect(url_for("my_home", dept=dept))

    @app.route("/my/hr", methods=["POST"])
    @login_required("admin", "uploader")
    def my_hr():
        check_csrf()
        u = g.user; f = request.form
        dept = f.get("dept", "")
        if not allowed(u, dept): abort(403)
        name = f.get("name", "").strip()[:30]; kind = f.get("kind", ""); date = f.get("date", "")[:10]
        try: dt.date.fromisoformat(date)
        except ValueError: date = ""
        if not name or kind not in HR_KINDS or not date:
            flash("성명·변동 종류·날짜를 모두 넣어 주세요."); return redirect(url_for("my_home", dept=dept) + "#hr")
        d = db.get()
        nid = d.execute("INSERT INTO hr_notes(dept,user_id,name,sabun,kind,date,to_org,memo,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
                  (dept, u["id"], name, f.get("sabun", "").strip()[:20], kind, date, f.get("to_org", "").strip()[:100],
                   f.get("memo", "").strip()[:300], "반영" if u["role"] == "admin" else "접수", _now(), _now())).fetchone()[0]
        d.commit(); db.audit(u["username"], "hr_note", f"{dept} · {name} · {kind} · {date}")
        if u["role"] == "admin" and f.get("back") == "board":
            flash(f"{name} · {kind} · {date} 제출을 저장했습니다. 다음 재계산부터 가동대상MM에 반영됩니다."); return redirect(url_for("submit_board", week=f.get("week", "")) + "#hr")
        return redirect(url_for("my_home", dept=dept, hr_ok=nid) + "#hr")

    @app.route("/my/hr/<int:nid>/delete", methods=["POST"])
    @login_required("admin", "uploader")
    def my_hr_delete(nid):
        check_csrf()
        d = db.get(); r = d.execute("SELECT * FROM hr_notes WHERE id=?", (nid,)).fetchone()
        if not r: abort(404)
        if g.user["role"] != "admin" and (r["user_id"] != g.user["id"] or r["status"] != "접수"): abort(403)
        d.execute("DELETE FROM hr_notes WHERE id=?", (nid,)); d.commit(); db.audit(g.user["username"], "hr_note_delete", str(nid))
        flash("제출을 삭제했습니다."); return redirect(request.referrer or url_for("my_home"))

    # ---------------- 관리자: 제출 현황 ----------------
    @app.route("/admin/board", methods=["GET", "POST"])
    @login_required("admin")
    def submit_board():
        if request.method == "POST":
            check_csrf()
            if request.form.get("what") == "depts":
                sel = [x for x in request.form.getlist("dept") if x]
                set_setting("submit_depts", sel); db.audit(g.user["username"], "setting", f"submit_depts {len(sel)}개")
                flash(f"제출 대상 부서를 {len(sel)}개로 저장했습니다.")
            elif request.form.get("what") == "deadline":
                wd = int(request.form.get("wd", 3)); tm = request.form.get("time", "15:00")[:5]
                set_setting("deadline_default", dict(wd=max(0, min(6, wd)), time=tm)); db.audit(g.user["username"], "setting", f"deadline {wd} {tm}")
                flash(f"업로드 마감을 매주 {WD[wd]}요일 {tm}로 저장했습니다. 매주 따로 바꿀 필요 없습니다.")
            elif request.form.get("what") == "deadline_week":
                wk = request.form.get("week", ""); v = (request.form.get("day", "") + "T" + request.form.get("time", "15:00")) if request.form.get("day") else ""
                try: dt.datetime.fromisoformat(v)
                except ValueError: v = ""
                set_setting("deadline:" + wk, v or None); db.audit(g.user["username"], "setting", f"deadline {wk} {v}")
                flash("이 주만 마감을 바꿨습니다." if v else "이 주 마감을 기본값으로 돌렸습니다.")
            elif request.form.get("what") == "hr":
                nid = int(request.form.get("id", 0)); st = request.form.get("status")
                if st not in HR_ST: abort(400)
                d = db.get(); d.execute("UPDATE hr_notes SET status=?, admin_note=?, updated_at=? WHERE id=?",
                                        (st, request.form.get("admin_note", "")[:200], _now(), nid)); d.commit()
                db.audit(g.user["username"], "hr_note_status", f"{nid} → {st}")
            return redirect(url_for("submit_board", week=request.form.get("week", "")) + ("#hr" if request.form.get("what") == "hr" else ""))
        wks = weeks_back(8)
        wl = request.args.get("week") or wks[0][0]
        wt = dict(wks).get(wl, wl); mon, thu = week_dates(wl)
        users = {}
        for r in db.get().execute("SELECT * FROM users WHERE role='uploader' AND active=1"):
            for x in user_depts(r): users.setdefault(x, []).append(r["display"])
        S = current_app.config["STORAGE"]
        who = {}
        for r in db.get().execute("SELECT * FROM users WHERE role='uploader' AND active=1"):
            for k in ORG.expand(S, user_depts(r)): who.setdefault(k, []).append(r["display"])
        tmap = {t["key"]: t for t in ORG.teams(S)}
        rows, cnt = [], {}
        for i, k in enumerate(ORG.expand(S, target_depts())):
            st, r = week_state(k, wl)
            prev = [week_state(k, lb)[0] for lb, _ in wks if lb < wl][:4]
            t = tmap[k]
            rows.append(dict(dept=k, label=ORG.label(k), dv=t["grp"], corp=t["corp"], st=st, r=r, who=who.get(k, []), prev=prev, o=i))
            c_ = "done" if st in ("반영",) else "sub" if st in ("제출", "변동없음") else "miss"
            cnt[c_] = cnt.get(c_, 0) + 1
        order = {"미제출": 0, "반려": 1, "보류": 2, "확인 대기": 3, "제출": 4, "변동없음": 5, "반영": 6}
        rows.sort(key=lambda x: (order.get(x["st"], 9), x["o"]))
        hr_f = request.args.get("hr", "open")
        q = "SELECT h.*, u.display FROM hr_notes h LEFT JOIN users u ON u.id=h.user_id " + ("WHERE h.status IN ('접수','인사자료와 다름') " if hr_f == "open" else "") + "ORDER BY h.id DESC LIMIT 200"
        notes = db.get().execute(q).fetchall()
        n_open = db.get().execute("SELECT COUNT(*) FROM hr_notes WHERE status='접수'").fetchone()[0]
        dl, dl_set = deadline(wl); dwd, dtm = deadline_default()
        return render_template("submit_board.html", dl=dl, dl_txt=dl_text(dl), dl_set=dl_set, dwd=dwd, dtm=dtm, WD=WD, wks=wks, wl=wl, wt=wt, mon=mon, thu=thu, rows=rows, cnt=cnt, V=ST_VIEW,
                               notes=notes, HR_ST=HR_ST, HR_KINDS=HR_KINDS, hr_f=hr_f, n_open=n_open, all_depts=sorted(set(all_depts()) | set(target_depts())),
                               tdepts=target_depts(), custom=bool(get_setting("submit_depts")))

    def board_count():
        """관리 메뉴 배지: 반영 확정을 기다리는 제출 + 새 변동 제출"""
        try:
            d = db.get(); wl = week_of()[0]
            a = d.execute("SELECT COUNT(*) FROM uploads WHERE kind='plan' AND status='제출' AND week=?", (wl,)).fetchone()[0]
            b = d.execute("SELECT COUNT(*) FROM hr_notes WHERE status='접수'").fetchone()[0]
            return a + b
        except Exception: return 0
    app.jinja_env.globals["board_count"] = board_count
    def how_of(r):
        if not r: return ""
        n = r["note"] or ""
        return "변동없음" if n.startswith(NOCHANGE) else "화면 입력" if n.startswith("화면 입력") else "파일 업로드"
    app.jinja_env.globals["how_of"] = how_of
