# 통계 파일(10.08) 팀 단위 파싱
import openpyxl, re
F = __import__('cfg').inp("stats")
NM = {"플랫폼 Eng팀": "플랫폼엔지니어링팀", "MSP Eng팀": "MSP엔지니어링팀", "AX Eng팀": "AX엔지니어링팀", "Alliance/마케팅팀": "Alliance-Marketing팀",
      "DS Service팀": "DS-Service팀", "DS TS사업부": "DS-TS사업부", "DS 전략사업팀": "DS-전략사업팀", "ENT컨설팅팀": "Ent컨설팅팀"}
KEYS = {"가동MM": "T", "제안": "pr", "R&D/과제": "rd", "Sold": "sold", "New": "new", "대기": "idle"}
def parse(sheet, corp):
    wb = openpyxl.load_workbook(F, data_only=True, read_only=True); ws = wb[sheet]
    out = {}; hq = dv = tm = None
    for r in ws.iter_rows(values_only=True):
        b, c, d, e = r[1:5]
        if e == "가동MM":
            if b and "소계" not in str(b) and b != "계": hq = b
            if c and "소계" in str(c) or (b and ("소계" in str(b) or b == "계")): tm = None; continue
            if c: dv = c
            if b is None and hq is None: hq = dv
            tm = re.sub(r"\s*\n.*", "", str(d).strip()) if d else dv
            tm = NM.get(tm, tm)
            out[(corp, tm)] = dict(hq=hq, dv=dv, note=r[19] if len(r) > 19 else None)
        if tm and e in KEYS:
            out[(corp, tm)][KEYS[e]] = [float(x or 0) for x in r[5:17]]
    return out
def load():
    o = parse("2-1. 통계(조직별_월별현황)", "아이티센클로잇"); o.update(parse("2-2. 통계(엔텍 엔터사업본부)", "아이티센엔텍")); return o
if __name__ == "__main__":
    for k, v in load().items(): print(k, v["hq"], v["dv"], [round(x, 2) for x in v["T"][8:]], [round(x,2) for x in v["idle"][8:]])

NOT_IDLE = {("아이티센엔텍", __import__("cfg").A("김영관"))}   # 10.08 파일 5-2 명단 오기: SOLD 모비스_인도네시아 AMOS 10~12월 1.00 투입, 팀 통계(Sold 22)에도 투입으로 잡힘
COVER = {}   # 법인별 대기 명단 월 범위 (m0, 개수)
def idle_list():
    """5-1 CLO(9~12월), 5-2 ET(1~12월) 대기 명단 → [{corp,name,본부,사업부,팀,직급,직책,직무,idle[12],note,months}]"""
    wb = openpyxl.load_workbook(F, data_only=True, read_only=True); out = []
    for pre, corp, m0 in (("5-1.", "아이티센클로잇", 8), ("5-2.", "아이티센엔텍", 0)):
        ws = next((w for w in wb.worksheets if w.title.startswith(pre) and "대기" in w.title), None)
        if ws is None: continue
        n = 12 - m0
        for r in ws.iter_rows(max_row=6, values_only=True):   # 머리글의 월 열로 범위 판별 (예: 9~12월 / 1~12월)
            ms = [int(str(x).strip()[:-1]) for x in r[10:] if isinstance(x, str) and re.fullmatch(r"\d{1,2}월", x.strip())]
            if ms: m0, n = ms[0] - 1, len(ms); break
        for r in ws.iter_rows(min_row=4, values_only=True):
            if not isinstance(r[1], (int, float)) or not r[6]: continue
            if (corp, r[6]) in NOT_IDLE: continue   # 대기 명단 오기 보정
            vals = r[10:10 + n]
            idle = [None] * 12
            for j, v in enumerate(vals):
                idle[m0 + j] = float(v) if isinstance(v, (int, float)) else None
            tm = NM.get(r[5], r[5])
            out.append(dict(corp=corp, sabun=str(r[2]), hq=r[3] if r[3] else "스포츠Tech사업부", dv=r[4], tm=tm, name=r[6], 직급=r[7], 직책=r[8], 직무=r[9],
                            idle=idle, note=r[10 + n] if len(r) > 10 + n else None, m0=m0, n=n))
        COVER[corp] = (m0, n)
    for e in EXTRA_IDLE:   # 명단 누락 보정 — 새 통계 파일에 이미 있으면 다시 넣지 않음
        if not any(o["corp"] == e["corp"] and o["name"] == e["name"] for o in out): out.append(dict(e, idle=list(e["idle"])))
    return out

# 10.08 파일 5-1 명단 누락 보정: 팀 통계 대기에는 포함, 명단에만 없음 (투입계획 기준 9~12월 0.30 대기)
EXTRA_IDLE = [dict(corp="아이티센클로잇", sabun=__import__("cfg").A("50149"), hq="AX사업본부", dv="AX Consulting & Eng 사업부", tm="AX엔지니어링팀", name=__import__("cfg").A("정재희"),
                   직급="G4", 직책="팀원", 직무="QM", idle=[None]*8 + [0.3, 0.3, 0.3, 0.3], note="명단 누락 보정 (팀 대기 포함분)", m0=8)]

# ---------------- 대시보드 반영 ----------------
MERGE_INTO = {("아이티센클로잇", "EC2사업부"): "EC3팀", ("아이티센클로잇", "ES사업부"): "ES1팀"}   # 통계표는 사업부장 행을 팀에 합쳐 둠
LOG = []
AUTO_T = []   # 가동대상을 최신 목록으로 덮은 조직 (corp, 팀)
def _team_of(corp, hq, dv, tm):
    return tm if tm != "(직속)" else (dv if dv != "(직속)" else hq)

def leave_sheet():
    """통계 파일 '3. 재직현황' 시트의 ◎ 휴직 명단 → [{name, hq, dv, tm, 직급, 직무, start, end, note}]"""
    import datetime as _dt
    wb = openpyxl.load_workbook(F, data_only=True, read_only=True)
    ws = next((w for w in wb.worksheets if w.title.startswith("3.") and "재직" in w.title), None)
    if ws is None: return []
    out = []; on = False
    for r in ws.iter_rows(values_only=True):
        v = [c for c in r if c is not None]
        if v and isinstance(v[0], str) and v[0].startswith("◎"): on = "휴직" in v[0]; continue
        if not on or not v or not isinstance(v[0], (int, float)) or len(v) < 8: continue
        dts = [c for c in v if isinstance(c, _dt.datetime)]
        strs = [c for c in v[1:] if isinstance(c, str)]
        # 순서: (그룹사번) (사원번호) 본부 사업부 팀 성명 직급 직책 직무 시작 종료 [비고]
        import re as _re
        j = next((i for i, c in enumerate(strs) if _re.fullmatch(r"[GSME]\d", c.strip())), None)   # 직급 위치
        k = next((i for i, c in enumerate(strs) if c.endswith(("사업본부", "사업부"))), None)
        if j is None or k is None or j - 1 <= k: continue
        nm, rank = strs[j - 1], strs[j]
        org = strs[k:j - 1]; hq, tm = org[0], org[-1]; dv = org[1] if len(org) > 2 else hq
        job = strs[j + 2] if len(strs) > j + 2 else ""
        note = strs[j + 3] if len(strs) > j + 3 else ""
        out.append(dict(name=nm, hq=hq, dv=dv, tm=tm, 직급=rank, 직무=job, start=dts[0].date() if dts else None,
                        end=dts[1].date() if len(dts) > 1 else None, note=note))
    return out

# 가동대상MM: 통계 파일보다 가동인력목록이 최신인 조직 (당월부터 목록 값 사용)
T_FROM_LIST = {("아이티센클로잇", "스포츠Tech사업부", "(직속)", "스포츠엔지니어링팀"): "이대근 휴직 연장 (10월 휴직 · 11/17 복직) — 통계 파일은 10/16 복직 기준",
               ("아이티센클로잇", "DX사업본부", "DX-Eng사업부", "플랫폼엔지니어링팀"): "박성진 퇴사 (10/16) — 가동인력목록 10.20 기준, 통계 파일(10.08)에는 없음"}

def stats_actual():
    """통계 파일 2-1 시트 머리글의 '실적' 구간 끝 월 (그 다음 열부터 '추정') — 못 찾으면 통계 파일 날짜의 전월"""
    try:
        wb = openpyxl.load_workbook(F, data_only=True, read_only=True); ws = wb["2-1. 통계(조직별_월별현황)"]
        rows = list(ws.iter_rows(max_row=6, values_only=True))
        for i, r in enumerate(rows):
            if "추정" in [str(x).strip() for x in r if x is not None] and i + 1 < len(rows):
                j = [str(x).strip() for x in r].index("추정")
                m = rows[i + 1][j]
                if isinstance(m, str) and m.strip().endswith("월"): return int(m.strip()[:-1]) - 1
    except Exception:
        pass
    return __import__('cfg').CI
SA = stats_actual()   # 통계 파일의 실적 월 수 (10.08 파일 = 9 → 1~9월 실적, 10월부터 추정)
CUR_M = SA            # (이전 이름) 이 달 index부터는 통계보다 새 자료가 있으면 그 자료를 씀
def keep_months(corp, fresh):
    """통계 대신 계산값을 쓰는 월 index: 통계 '추정' 구간 중 ① SOLD 실적이 확정된 달 ② 통계보다 최근 투입계획이 있는 조직"""
    a = __import__('cfg').act_of(corp)
    return [m for m in range(SA, 12) if m < a or fresh]
def _fresh():
    """통계 파일보다 나중에 올라온 투입계획이 적용되는 조직 (엔진이 plan 단계에서 fresh.json 으로 남김)"""
    try:
        import cfg, json as _j
        return {tuple(k) for k in _j.load(open(cfg.w("fresh.json"), encoding="utf-8"))["teams"]}
    except Exception:
        return set()
def _fresh_tn(FR):
    out = set()
    for k in FR:
        tn = _team_of(*k); out.add((k[0], MERGE_INTO.get((k[0], tn), tn)))
    return out

def apply_leaf(leaf, M=12):
    """조직 단위 숫자를 통계 파일(10.08)로 맞춤: 가동MM·이행(Sold+New)·제안·R&D (1~12월). 대기 = 가동MM − 투입"""
    ST = load(); LOG.clear(); AUTO_T.clear()
    FR = _fresh(); keep = {k: {f: list(leaf[k][f]) for f in ("ex", "pr", "rd", "np")} for k in leaf if keep_months(k[0], k in FR)}
    keepT = {k: list(leaf[k]["T"]) for k in leaf if k in T_FROM_LIST}
    keyed = {}
    for k in leaf:
        tn = _team_of(*k); keyed.setdefault((k[0], tn), []).append(k)
    # 가동대상MM 자동 판별: 통계 파일(10.08)과 최신 가동인력목록·통합인사정보의 당월 이후 가동대상이 다른 조직은
    # 사람이 없어도 최신 자료를 따름 (퇴사·전배·입사 등). 같으면 통계 값 그대로.
    for (corp, tn), s in ST.items():
        ks = keyed.get((corp, tn), []) + [k for (c2, t2), kk in keyed.items() for k in kk if c2 == corp and MERGE_INTO.get((c2, t2)) == tn]
        if not ks: continue
        if any(abs(sum(leaf[k]["T"][m] for k in ks) - s["T"][m]) > 0.01 for m in range(CUR_M, M)):
            for k in ks:
                if k not in keepT:
                    keepT[k] = list(leaf[k]["T"])
            AUTO_T.append((corp, tn))
    for (corp, tn), s in ST.items():
        file = dict(T=s["T"], ex=[a + b for a, b in zip(s["sold"], s["new"])], pr=s["pr"], rd=s["rd"])
        main = keyed.get((corp, tn), [])
        extra = [k for (c2, t2), ks in keyed.items() for k in ks if c2 == corp and MERGE_INTO.get((c2, t2)) == tn]
        if not main: LOG.append(("조직 없음", corp, tn)); continue
        tgt = main[0]
        for f in file:
            base = [sum(leaf[k][f][m] for k in extra) + sum(leaf[k][f][m] for k in main[1:]) for m in range(M)]
            old = list(leaf[tgt][f])
            leaf[tgt][f] = [file[f][m] - base[m] for m in range(M)]
            if f == "rd": leaf[tgt]["np"] = [leaf[tgt]["np"][m] + leaf[tgt]["rd"][m] - old[m] for m in range(M)]
    for k, v in keepT.items():   # 가동대상MM: 목록이 더 최신인 조직은 당월 이후 목록 값
        for m in range(CUR_M, M): leaf[k]["T"][m] = v[m]
    for k, v in keep.items():   # SOLD 확정 달 · 최근 투입계획이 있는 조직: 계산 값 유지
        for f, vals in v.items():
            for m in keep_months(k[0], k in FR): leaf[k][f][m] = vals[m]
    return leaf

def apply_people(PP, months=None):
    """사람별 대기 (통계 실적 마지막 달 ~ 12월) = 대기 명단(5-1·5-2). 명단에 없는데 통계 팀 대기에 남는 MM이 있으면 기존 값 유지(명단 누락 표시)"""
    L = idle_list(); ST = load()
    def MS(corp):
        if months is not None: return list(months)
        m0, n = COVER.get(corp, (8, 4))
        return [m for m in range(max(SA - 1, m0), min(m0 + n, 12))]
    FR = _fresh(); FRT = _fresh_tn(FR)
    def mon(p):
        km = keep_months(p["corp"], (p["corp"], p["hq"], p["dv"], p["tm"]) in FR)
        return [m for m in MS(p["corp"]) if m not in km]
    byname = {}
    for k, p in PP.items(): byname.setdefault((p["corp"], p["name"]), []).append(p)
    listed = set(); MISSING = []
    lsum = {}
    for r in L:
        cands = byname.get((r["corp"], r["name"]), [])
        if not cands: MISSING.append(("명단 인원이 가동대상에 없음", r["corp"], r["name"])); continue
        p = next((c for c in cands if c["tm"] == r["tm"] or c["org"] == r["tm"]), None) or max(cands, key=lambda c: sum(c["T"]))
        if id(p) not in listed:
            for m in mon(p): p["idle"][m] = 0.0
            listed.add(id(p))
        for m in mon(p): p["idle"][m] += r["idle"][m] or 0.0
        if mon(p) == MS(p["corp"]): p["idle_note"] = r["note"]   # 최근 계획이 있는 사람은 통계 비고 대신 계획 프로젝트 표시
    # 명단에 없는 사람
    for p in PP.values():
        if id(p) in listed: continue
        if any(p["idle"][m] > 0.005 for m in mon(p)):
            p["_keep_check"] = True
    # 팀별 잔여 확인 (통계 팀 대기 − 명단 합)
    def tkey(p):
        tn = p["tm"] if p["tm"] != "(직속)" else (p["dv"] if p["dv"] != "(직속)" else p["hq"])
        return (p["corp"], MERGE_INTO.get((p["corp"], tn), tn))
    for r in L:   # 명단 합은 명단에 적힌 팀 기준 (전배자의 전월 대기는 전 소속 팀에 잡힘)
        if (r["corp"], r["name"]) in {(c, n) for _, c, n, *rest in MISSING if _ == "명단 인원이 가동대상에 없음"}: continue
        k = (r["corp"], MERGE_INTO.get((r["corp"], r["tm"]), r["tm"]))
        for m in MS(r["corp"]):
            if m in keep_months(k[0], k in FRT): continue
            lsum.setdefault(k, [0.0] * 12)[m] += r["idle"][m] or 0.0
    for p in PP.values():
        if not p.pop("_keep_check", False): continue
        k = tkey(p); s = ST.get(k)
        for m in mon(p):
            res = (s["idle"][m] if s else 0) - lsum.get(k, [0.0] * 12)[m]
            if p["idle"][m] > 0.005 and res >= p["idle"][m] - 0.011:
                lsum.setdefault(k, [0.0] * 12)[m] += p["idle"][m]
                MISSING.append(("명단 누락(통계 팀 대기에는 포함)", p["corp"], p["name"], m + 1, round(p["idle"][m], 2)))
            else:
                p["idle"][m] = 0.0
    # 명단 합 ≠ 통계 팀 대기
    for k, s in ST.items():
        for m in MS(k[0]):
            if m in keep_months(k[0], k in FRT): continue
            a = lsum.get(k, [0.0] * 12)[m]
            if abs(a - s["idle"][m]) > 0.011: MISSING.append(("명단 합 ≠ 통계 팀 대기", k[0], k[1], m + 1, round(a, 2), round(s["idle"][m], 2)))
    return MISSING
