"""재계산 엔진 — 업로드된 파일(없으면 기본 파일)로 관리자·회의용 화면을 다시 만든다

흐름
 1) 자리(role)별 입력 파일 정하기: 그 주차까지 올라온 업로드 중 최신(반려·보류 제외) → 없으면 storage/inputs/base
 2) storage/work/<주차>/ 에 계산 설정(cfg.json)을 쓰고 calc 스크립트를 차례로 실행
 3) 결과를 storage/drafts/<주차>/ 에 저장 (admin.html · meeting.html · checks.json · inputs.json · log.txt)
 4) 관리자가 미리보기 후 '게시'하면 published/<주차>/ 로 복사 (views.py)
"""
import os, sys, json, shutil, sqlite3, subprocess, threading, datetime as dt, traceback, re
from . import roles as RL

HERE = os.path.dirname(os.path.abspath(__file__))
CALC = os.path.join(HERE, "calc")
STEPS = [
    ("가동대상 정리", ["make_target.py"]),
    ("클로잇 SOLD 실적", ["make_perf2.py"]),
    ("엔텍 SOLD 실적", ["make_perf_et.py"]),
    ("투입계획 반영", ["plan.py"]),
    ("관리자 화면 계산", ["build_v4.py"]),
    ("관리자 화면 완성", ["gen_admin.py"]),
    ("숫자 표기 정리", ["post.py", "{work}admin.html"]),
    ("회의용 화면", ["meeting_build.py", "{work}meeting.html"]),
]
_lock = threading.Lock()
BASE_STATS_AT = "2026-10-08 12:00:00"   # 기본 통계 파일(10.08) 기준 시각

def week_meta(label):
    """2026-10-W2 → 제목·회의일 (그 주 목요일 기준 주차, 다음 주 월요일 회의)"""
    y, m, w = int(label[:4]), int(label[5:7]), int(label.split("W")[-1])
    d = dt.date(y, m, 1); first_thu = d + dt.timedelta(days=(3 - d.weekday()) % 7)
    thu = first_thu + dt.timedelta(days=7 * (w - 1)); mon = thu + dt.timedelta(days=4)
    wd = "월화수목금토일"[mon.weekday()]
    return dict(label=label, title=f"{y}년 {m}월 {w}주차", short=f"{m}월 {w}주차", meet=f"{mon:%m.%d}({wd}) 회의", thu=thu.isoformat())

def _db(storage):
    from gadong import db
    return db.connect(storage=storage)

def resolve_inputs(storage, label, exclude_id=None):
    """자리별 입력 파일 → (inputs, short, dept_files, files목록, used목록, 경고)"""
    base_dir = os.path.join(storage, "inputs", "base")
    bp = os.path.join(base_dir, "base.json")
    base = json.load(open(bp, encoding="utf-8")) if os.path.exists(bp) else {}
    pick = {r: dict(path=os.path.join(base_dir, v["file"]), orig=v["orig"], date=v["date"], short=v.get("short"), src="기본", at=v.get("at", "")) for r, v in base.items() if not r.startswith("_")}
    dept_files = {}; warns = []
    for d in base.get("_dept", []):   # 기본 자료에 포함된 부서 투입계획 (팀원 전달용 등 — 업로드가 없는 새 설치에서도 같은 계산이 되게)
        key = (d["corp"], d["hq"], d["dv"], d["tm"]); nm = " · ".join(x for x in key[1:] if x) or key[0]
        dept_files[key] = dict(path=os.path.join(base_dir, d["file"]), fmt=d["fmt"], corp=d["corp"], hq=d["hq"], dv=d["dv"], tm=d["tm"], label=f"{nm}({d['date']})",
                               orig=d["orig"], date=d["date"], src="기본", upload_id=None, at=d.get("at", ""))
    with _db(storage) as c:
        # 관리자가 '반영' 확정한 업로드만 계산에 씀 (확인 대기·제출·보류·반려는 제외)
        ups = c.execute("SELECT * FROM uploads WHERE status='반영' AND week<=? AND id<>? ORDER BY id", (label, exclude_id or -1)).fetchall()
    for u in ups:
        path = os.path.join(storage, "uploads", u["stored_name"])
        if not os.path.exists(path):
            from flask import has_app_context
            if has_app_context():
                from gadong import files as _files
                if _files.enabled(): _files.ensure("uploads/" + u["stored_name"], storage)
        if not os.path.exists(path): warns.append(f"업로드 원본 없음: {u['orig_name']}"); continue
        fmt = RL.detect_format(path) if u["kind"] == "plan" else None
        dept = u["dept"] or (RL.infer_dept(u["orig_name"], fmt) if u["kind"] == "plan" else "") or ""
        role, scope, err = RL.role_for_upload(u["kind"], dept, fmt)
        if err: warns.append(f"{u['orig_name']}: {err}"); continue
        date = u["uploaded_at"][5:10].replace("-", ".")
        info = dict(path=path, orig=u["orig_name"], date=date, src=f"업로드 #{u['id']}", upload_id=u["id"], at=u["uploaded_at"])
        if role:
            info["short"] = f"{RL.SHORT_NAME.get(role, '')}({date})" if role.startswith("plan_") else None
            pick[role] = info
            if role.startswith("plan_") and role != "plan_hb":   # 사업부·본부 전체 파일을 새로 올렸으면, 그보다 먼저 올린 팀·부서 단위 파일은 낡은 것 → 우선순위에서 뺌
                _c, _h, _d, _t = RL.split_dept(dept)
                for k in [k for k, d in dept_files.items() if _h and k[0] == _c and k[1] == _h and (not _d or k[2] == _d) and d.get("at", "") < info["at"]]:
                    dept_files.pop(k)
            if role == "plan_hb": pick["plan_hb2"] = dict(info)       # 하반기 총괄은 최신본 하나로
            if role == "stats": pick["stats_base"] = dict(info)       # 통계 파일은 조직 구조에도 최신본 사용
        else:
            key = (scope["corp"], scope["hq"], scope["dv"], scope["tm"])
            nm = " · ".join(x for x in key[1:] if x) or key[0]
            dept_files[key] = dict(path=path, fmt=fmt, corp=scope["corp"], hq=scope["hq"], dv=scope["dv"], tm=scope["tm"], label=f"{nm}({date})",
                                   orig=u["orig_name"], date=date, src=f"업로드 #{u['id']}", upload_id=u["id"], at=u["uploaded_at"])
    # 통계 파일보다 나중에 올라온 투입계획 → 당월 이후는 통계 대신 그 계획 기준
    stats_at = pick.get("stats", {}).get("at", BASE_STATS_AT)
    fresh = [v["path"] for r, v in pick.items() if r.startswith("plan_") and v.get("at", "") > stats_at]
    fresh += [d["path"] for d in dept_files.values() if d.get("at", "") > stats_at]
    inputs = {r: v["path"] for r, v in pick.items()}
    short = {r: v["short"] for r, v in pick.items() if v.get("short")}
    used = [dict(role=r, name=RL.ROLES[r][0], orig=v["orig"], date=v["date"], src=v["src"], upload_id=v.get("upload_id")) for r, v in pick.items()]
    used += [dict(role="plan_dept", name=f"투입계획 · {d['label']}", orig=d["orig"], date=d["date"], src=d["src"], upload_id=d.get("upload_id")) for d in dept_files.values()]
    files = [(v["date"], v["orig"], RL.ROLES[r][1]) for r, v in pick.items() if r not in ("plan_msp", "plan_dxp", "stats_base", "cp")]
    files += [(d["date"], d["orig"], f"10~12월 투입계획 · {d['label'].rsplit('(', 1)[0]} (부서 파일 우선)") for d in dept_files.values()]
    files.sort(key=lambda x: x[0], reverse=True)
    missing_plans = [RL.ROLES[r][0] for r in RL.ROLES if r.startswith("plan_") and r not in inputs]
    warns += ["투입계획 없음 (총괄·부서 파일로 대체하거나 0으로 계산): " + name for name in missing_plans]
    return inputs, short, list(dept_files.values()), files, used, warns, fresh

def _month_text(t, cur, act):
    """반영 파일 설명의 월 표기를 이번 주차 기준으로"""
    return (t.replace("1~9월 실적", f"1~{act}월 실적").replace("10~12월 투입계획", (f"{act + 1}~12월" if act < 11 else "12월") + " 투입계획"))

def sold_act(path, cur):
    """SOLD투입MM목록에서 실적이 확정된 마지막 월 — 'Activity 실적(누적)' 합이 1~m월 합과 맞는 가장 큰 m (당월 전까지)"""
    import pandas as pd
    try:
        h = pd.read_excel(path, header=None)
        cols = [f"{str(a)[:5]}_{b}" if str(a).startswith(("2026년", "2027년")) else a for a, b in zip(h.iloc[0], h.iloc[1])]
        d = h.iloc[2:].copy(); d.columns = cols
        act = pd.to_numeric(d["Activity 실적(누적, MM)"], errors="coerce").fillna(0)
        mm = [pd.to_numeric(d[f"2026년_{m}월"], errors="coerce").fillna(0) for m in range(1, 13)]
        best = 0
        for m in range(1, cur):
            s = sum(mm[:m])
            if abs(float(s.sum()) - float(act.sum())) < 0.5 and float(((act - s).abs() < 0.011).mean()) > 0.98: best = m
        return best
    except Exception:
        return cur - 1

# ---- 재계산 실패 원인 안내 ----
STEP_FILES = {   # 단계 → 그 단계가 읽는 자리
    "make_target.py": ["target_clo", "target_et", "hr", "stats_base"],
    "make_perf2.py": ["sold_clo", "stats_base"], "make_perf_et.py": ["sold_et", "stats_base"],
    "plan.py": ["plan_hb", "plan_hb2", "plan_ec", "plan_es", "plan_ax", "plan_ees", "plan_eem", "plan_msp", "plan_dxp", "plan_dept"],
    "build_v4.py": ["stats", "target_clo", "target_et"], "gen_admin.py": [], "post.py": [], "meeting_build.py": ["stats"],
}
def _explain(err):
    """오류 마지막 줄 → (원인, 해결 방법) — 담당자가 읽을 수 있는 말로"""
    import re as _re
    e = err.strip()
    if "투입계획 파일을 읽지 못했습니다" in e:
        return e.split("RuntimeError: ")[-1], "그 파일을 열어 시트 이름·머리글(성명, 1월~12월 등)이 바뀌었는지 확인하고, 고친 파일을 다시 올리거나 그 업로드를 보류/삭제한 뒤 재계산하세요."
    if "PermissionError" in e:
        return "파일을 열 수 없습니다 (다른 프로그램이 사용 중)", "엑셀에서 storage 안의 파일을 열어 두었다면 닫고 다시 재계산하세요."
    m = _re.search(r"Worksheet named '(.+?)' not found|Worksheet (.+?) does not exist|sheet '?(.+?)'? (?:not found|does not exist)", e)
    if m:
        return f"'{next(x for x in m.groups() if x)}' 시트를 찾지 못했습니다", "그 단계에서 쓰는 파일의 시트 이름이 바뀌었는지 확인하세요. 원래 이름으로 고쳐 다시 올리면 됩니다."
    m = _re.search(r"KeyError: '?(.+?)'?$", e)
    if m:
        return f"'{m.group(1)}' 열(또는 항목)을 찾지 못했습니다", "그 단계에서 쓰는 파일의 머리글(열 이름)이 바뀌었거나 빠졌는지 확인하세요."
    if "FileNotFoundError" in e or "No such file" in e:
        return "필요한 파일이 없습니다", "업로드 원본이 지워졌을 수 있습니다. 해당 파일을 다시 올리세요."
    if "BadZipFile" in e or "not a zip file" in e or "InvalidFileException" in e:
        return "엑셀 파일이 손상되었거나 엑셀 형식이 아닙니다", "엑셀에서 열어 '다른 이름으로 저장 → Excel 통합 문서(.xlsx)'로 저장한 뒤 다시 올리세요."
    if "MemoryError" in e:
        return "메모리가 부족합니다", "다른 프로그램을 닫고 다시 재계산하세요."
    if "StopIteration" in e or "ValueError" in e or "IndexError" in e:
        return "파일에서 기대한 위치에 내용이 없습니다", "그 단계에서 쓰는 파일의 양식(머리글 줄, 시트 구성)이 평소와 다른지 확인하세요."
    return "예상하지 못한 오류", "아래 기술 로그를 캡처해서 Claude에게 보내 주세요."

class StepError(Exception):
    def __init__(self, step, script, stderr, inputs, used):
        last = (stderr.strip().splitlines() or ["(메시지 없음)"])[-1]
        self.step = step; self.cause, self.hint = _explain(last)
        roles = STEP_FILES.get(script, [])
        self.files = [f"{u['name']} — {u['orig']} ({u['src']})" for u in used if u["role"] in roles]
        if "투입계획 파일을 읽지 못했습니다" in last: self.files = []
        self.msg = f"'{step}' 단계에서 멈췄습니다. {self.cause}"
        super().__init__(self.msg)

def status_path(storage, label): return os.path.join(storage, "work", label, "status.json")

def read_status(storage, label):
    p = status_path(storage, label)
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None

def _set(storage, label, **kw):
    p = status_path(storage, label); os.makedirs(os.path.dirname(p), exist_ok=True)
    st = read_status(storage, label) or {}; st.update(kw)
    json.dump(st, open(p, "w", encoding="utf-8"), ensure_ascii=False)

def _clean_hr_header(out):
    """센터에서 정렬해서 내려받으면 머리글에 정렬 표시가 붙음 ('성명▲' 등) → 제거해서 원래 열 이름으로 (2026-11-03)"""
    import re, openpyxl
    wb = openpyxl.load_workbook(out); ws = wb.worksheets[0]; ch = 0
    for row in ws.iter_rows(min_row=1, max_row=1):
        for c in row:
            if isinstance(c.value, str):
                v = re.sub(r"[\s▲▼△▽↑↓⇧⇩⏶⏷]+$", "", c.value.strip())
                if v != c.value: c.value = v; ch += 1
    if ch: wb.save(out)

def _prep_hr(path, work):
    out = os.path.join(work, "hr.xlsx")
    if path.lower().endswith(".xlsx"): shutil.copy(path, out)
    else:
        import pandas as pd   # .xls → .xlsx (xlrd 필요)
        pd.read_excel(path, header=None).to_excel(out, header=False, index=False)
    try: _clean_hr_header(out)
    except Exception: pass   # 정리에 실패해도 원래 파일 그대로 진행

def _strip_comments(a):
    """관리자 화면에서 수기 코멘트 칸 제거 (자동 작성 안 하는 칸)"""
    a = re.sub(r'\s*<p class="nocm">.*?</p>', "", a)
    a = re.sub(r'\s*<section id="s6" class="card-sec">\s*<div class="sec-head"><span class="sec-no">06</span><h2>금주 코멘트</h2>.*?</section>', "", a, flags=re.S)
    a = re.sub(r'<a href="#s6">(?:(?!</a>).)*?금주<br>코멘트</a>', "", a, flags=re.S)
    return a.replace(", 06 코멘트만 표시합니다", "만 표시합니다")

def _idle_text(x):
    """대기 명단 대조 결과를 읽기 쉬운 [구분, 내용] 으로"""
    k = x[0]
    try:
        if k.startswith("명단 합"): return [k, f"{x[2]} · {x[3]}월 — 명단 합 {float(x[4]):.2f}MM / 통계 팀 대기 {float(x[5]):.2f}MM"]
        if k.startswith("명단 누락"): return [k, f"{x[2]} · {x[3]}월 {float(x[4]):.2f}MM"]
        return [k, " · ".join(x[1:])]
    except Exception:
        return [k, " · ".join(map(str, x[1:]))]

def _hr_notes(storage):
    """사이트 '인사 변동 제출' 중 계산에 넣을 것: 반영 상태 + 관리자가 직접 입력한 것(인사자료와 다름 제외)"""
    try:
        import sqlite3
        c = _db(storage)
        rows = c.execute("SELECT h.id,h.dept,h.name,h.sabun,h.kind,h.date,h.to_org,h.memo,h.status,u.role FROM hr_notes h LEFT JOIN users u ON u.id=h.user_id "
                         "WHERE h.status='반영' OR (u.role='admin' AND h.status IN ('접수','확인')) ORDER BY h.date, h.id").fetchall()
        c.close()
        out = [dict(r) for r in rows]
    except Exception:
        out = []
    try:   # 기본 자료에 함께 둔 인사 변동 입력 (새 설치 DB에는 없으므로)
        bp = os.path.join(storage, "inputs", "base", "hr_notes.json")
        if os.path.exists(bp):
            have = {(n.get("name"), n.get("kind"), n.get("date")) for n in out}
            out += [n for n in json.load(open(bp, encoding="utf-8")) if (n.get("name"), n.get("kind"), n.get("date")) not in have]
    except Exception:
        pass
    return out

def prepare(storage, label, user):
    work = os.path.join(storage, "work", label) + os.sep
    os.makedirs(work, exist_ok=True)
    os.makedirs(os.path.join(storage, "published"), exist_ok=True)
    log = []
    meta = week_meta(label)
    inputs, short, dept_files, files, used, warns, fresh = resolve_inputs(storage, label)
    asof = dt.date.today().strftime("%m.%d")   # 계산한 날
    meta["asof"] = asof
    # 비교 기준: 같은 달의 직전 게시 주차가 있으면 전주, 없으면(월 첫 보고) 전월 확정
    pub = os.path.join(storage, "published")
    prevs = sorted(l for l in os.listdir(pub) if l < label and l[:7] == label[:7] and os.path.exists(os.path.join(pub, l, "summary.json"))
                   and not os.path.exists(os.path.join(pub, l, "RETIRED.txt")))
    if prevs:
        meta["prev_summary"] = os.path.join(pub, prevs[-1], "summary.json"); meta["prev_label"] = prevs[-1]
    else:   # 월 첫 보고: 전월이 SOLD 마감 전이면 전월 마지막 게시 주차와 비교 (확정이면 전월 실적과 비교)
        y, m = int(label[:4]), int(label[5:7]); pl = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
        pms = sorted(l for l in os.listdir(pub) if l[:7] == pl and os.path.exists(os.path.join(pub, l, "summary.json"))
                     and not os.path.exists(os.path.join(pub, l, "RETIRED.txt")))
        if pms: meta["pm_label"] = pms[-1]; meta["pm_summary_path"] = os.path.join(pub, pms[-1], "summary.json")
    for f in os.listdir(work):
        if f != "status.json":
            fp = os.path.join(work, f)
            if os.path.isfile(fp): os.remove(fp)
    required = ["hr", "sold_clo", "sold_et", "target_clo", "target_et", "stats", "stats_base", "cp"]
    missing = [RL.ROLES[r][0] for r in required if r not in inputs or not os.path.isfile(inputs[r])]
    if missing: raise ValueError("필수 입력 자료가 없습니다: " + ", ".join(missing) + ". 업로드 후 반영 확정해 주세요.")
    if not any(r.startswith("plan_") for r in inputs) and not dept_files:
        raise ValueError("반영 확정된 투입계획이 없습니다. 총괄 또는 부서 투입계획을 올려 주세요.")
    _prep_hr(inputs["hr"], work)
    baseline = os.path.join(storage, "inputs", "base", "_stats21.pkl")
    if os.path.isfile(baseline): shutil.copy(baseline, os.path.join(work, "stats21.pkl"))
    else:
        import pandas as pd
        raw = pd.read_excel(inputs["stats_base"], sheet_name="2-1. 통계(조직별_월별현황)", header=None)
        rows = []; division = ""
        for _, row in raw.iterrows():
            if len(row) < 17: continue
            if pd.notna(row[2]): division = str(row[2])
            if row[4] in ("Sold", "제안", "R&D/과제"):
                rows.append(dict(dv=division, k=row[4], **{f"m{m}": float(pd.to_numeric(row[4+m], errors="coerce") or 0) if pd.notna(row[4+m]) else 0.0 for m in range(1, 13)}))
        pd.DataFrame(rows, columns=["dv", "k"] + [f"m{m}" for m in range(1, 13)]).to_pickle(os.path.join(work, "stats21.pkl"))
    cur = int(label[5:7])
    act = {k: sold_act(inputs[f"sold_{k}"], cur) for k in ("clo", "et")}
    meta["act"] = act
    meta["stats_date"] = next((u["date"] for u in used if u["role"] == "stats"), "")
    if meta.get("pm_summary_path") and min(act.values()) < cur - 1: meta["pm_summary"] = meta["pm_summary_path"]   # 전월 잠정일 때만
    files = [(d_, o_, _month_text(u_, cur, min(act.values()))) for d_, o_, u_ in files]
    log.append(f"## 월 기준\n당월 {cur}월 · SOLD 실적 확정 아이티센클로잇 {act['clo']}월 · 아이티센엔텍 {act['et']}월")
    try: targets = json.load(open(os.path.join(storage, "targets.json"), encoding="utf-8"))
    except Exception: targets = {}
    hr_notes = _hr_notes(storage)
    cfg = dict(work=work, inputs=inputs, short=short, dept_files=dept_files, files=files, week=meta, fresh=fresh, act=act, targets=targets, hr_notes=hr_notes)
    json.dump(cfg, open(os.path.join(work, "cfg.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return cfg, warns, used, log


def finish(storage, label, user, cfg, warns, used):
    work = cfg["work"]
    draft = os.path.join(storage, "drafts", label)
    meta = cfg["week"]; asof = meta["asof"]
    dept_files = cfg["dept_files"]; inputs = cfg["inputs"]; fresh = cfg["fresh"]; act = cfg["act"]
    cur = int(label[5:7])
    # 결과 정리 → drafts
    os.makedirs(draft, exist_ok=True)
    a = open(work + "admin.html", encoding="utf-8").read()
    a = a.replace("10월 2주차 (10.08)", f"{meta['short']} ({asof})")   # (예전 고정 문구 대비 — 지금은 화면에서 직접 주차를 씀)
    a = _strip_comments(a)
    _ca = "<script>" + open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "colalign.js"), encoding="utf-8").read() + "</script>"   # 월 열 맞춤
    def _inj(h): return h.replace("</body>", _ca + "</body>", 1) if "</body>" in h else h + _ca
    open(os.path.join(draft, "admin.html"), "w", encoding="utf-8").write(_inj(a))
    open(os.path.join(draft, "meeting.html"), "w", encoding="utf-8").write(_inj(open(work + "meeting.html", encoding="utf-8").read()))
    if os.path.exists(work + "summary.json"): shutil.copy(work + "summary.json", os.path.join(draft, "summary.json"))
    checks = json.load(open(work + "checks.json", encoding="utf-8")) if os.path.exists(work + "checks.json") else {}
    try: _ov = json.load(open(work + "summary.json", encoding="utf-8")).get("over", [])
    except Exception: _ov = []
    checks["warn"] = list(warns) + [f"⚠ 100% 초과 — {x}" for x in _ov]
    fr_ids = {d.get("upload_id") for d in dept_files if d["path"] in fresh}
    fr_ids |= {u.get("upload_id") for u in used if u["role"] in inputs and inputs[u["role"]] in fresh}
    checks["info"] = sorted({f"{u['orig']} ({u['src']}) — 통계 파일보다 나중에 올라와 통계 추정 구간은 이 파일 기준" for u in used if u.get("upload_id") in fr_ids - {None}})
    if min(act.values()) < cur - 1:
        checks["info"].insert(0, f"{', '.join(f'{m}월' for m in range(min(act.values()) + 1, cur))} SOLD 실적이 아직 마감 전 → 투입계획 기준 잠정 (SOLD투입MM목록을 새로 올리면 실적으로 바뀝니다)")
    checks["idle"] = [_idle_text(x) for x in checks.get("idle", [])]
    checks["plan"] = [[str(v).replace(" ((직속))", "").replace("((직속))", "") for v in x] for x in checks.get("plan", [])]
    json.dump(checks, open(os.path.join(draft, "checks.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(dict(meta=meta, used=used, by=user, at=dt.datetime.now().strftime("%Y-%m-%d %H:%M")), open(os.path.join(draft, "inputs.json"), "w", encoding="utf-8"), ensure_ascii=False)


def _job(storage, label, user):
    work = os.path.join(storage, "work", label) + os.sep
    draft = os.path.join(storage, "drafts", label)
    log = []
    try:
        cfg, warns, used, log = prepare(storage, label, user)
        inputs = cfg["inputs"]
        env = dict(os.environ, GADONG_CFG=os.path.join(work, "cfg.json"), PYTHONPATH=CALC, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        for i, (name, cmd) in enumerate(STEPS, 1):
            _set(storage, label, step=f"{i}/{len(STEPS)} {name}")
            args = [sys.executable, os.path.join(CALC, cmd[0])] + [a.format(work=work) for a in cmd[1:]]
            r = subprocess.run(args, cwd=CALC, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
            log.append(f"## {i}. {name}\n{r.stdout[-3000:]}\n{r.stderr[-6000:]}")
            if r.returncode != 0:
                raise StepError(name, cmd[0], r.stderr, inputs, used)
        finish(storage, label, user, cfg, warns, used)
        _set(storage, label, state="done", step="완료", finished=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg="")
    except StepError as e:
        log.append(traceback.format_exc())
        _set(storage, label, state="error", finished=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg=e.msg, cause=e.cause, hint=e.hint, files=e.files, step=e.step)
    except subprocess.TimeoutExpired as e:
        log.append(traceback.format_exc())
        _set(storage, label, state="error", finished=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg="계산이 30분 넘게 끝나지 않아 멈췄습니다.",
             cause="시간 초과", hint="PC가 바쁘거나 파일이 아주 큰 경우입니다. 다른 프로그램을 닫고 다시 재계산해 보세요.", files=[])
    except Exception as e:
        log.append(traceback.format_exc())
        c, h = _explain(f"{type(e).__name__}: {e}")
        _set(storage, label, state="error", finished=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg=str(e), cause=c, hint=h, files=[])
    finally:
        os.makedirs(os.path.join(storage, "work", label), exist_ok=True)
        open(os.path.join(storage, "work", label, "log.txt"), "w", encoding="utf-8").write("\n\n".join(log))
        _lock.release()

def rebuild(storage, label, user="admin", wait=False):
    """재계산 시작. (시작됐는지, 메시지)"""
    if not re.fullmatch(r"\d{4}-\d{2}-W\d", label): return False, "주차 형식이 올바르지 않습니다."
    if not _lock.acquire(blocking=False): return False, "다른 재계산이 진행 중입니다. 끝난 뒤 다시 눌러 주세요."
    _set(storage, label, state="running", step="준비", started=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished="", msg="", cause="", hint="", files=[], by=user)
    t = threading.Thread(target=_job, args=(storage, label, user), daemon=True); t.start()
    if wait: t.join()
    return True, "재계산을 시작했습니다. 몇 분 걸립니다. 이 화면에서 진행 상황을 볼 수 있습니다."
