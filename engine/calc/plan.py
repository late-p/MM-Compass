# 투입계획(인력롤링) → 실적 확정 다음 달 ~ 12월 투입 반영
import pandas as pd, re, openpyxl, warnings, collections, json
warnings.filterwarnings("ignore")
from plan_parse import parse_mm, D
SP = __import__('cfg').WORK
_cfg = __import__("cfg")
Q = list(range(_cfg.ACTM, 12))   # 투입계획으로 채우는 월 index (SOLD 실적 확정 다음 달 ~ 12월)
QM = [m + 1 for m in Q]          # 같은 월 (1~12)
MISSCOL = []   # 투입계획 파일에 없는 월 열 [(파일, 월)]
def _mcol(H, m, f, after=-1, test=None):
    """머리글에서 m월 열 찾기 — 없으면 None (그 달은 0으로 읽고 점검 목록에 남김)"""
    test = test or (lambda h: h == f"{m}월")
    i = next((i for i, h in enumerate(H) if i > after and test(h)), None)
    if i is None: MISSCOL.append((f, m))
    return i
def _qv(r, cols):
    q = []
    for c in cols:
        v = r[c] if c is not None and c < len(r) else None
        try: q.append(float(v) if v not in (None, "", "-") else 0.0)
        except Exception: q.append(0.0)
    return q
F_HB, F_EC, F_ES, F_AX = _cfg.IN.get("plan_hb", SP + "_absent_plan_hb.xlsx"), _cfg.IN.get("plan_ec", SP + "_absent_plan_ec.xlsx"), _cfg.IN.get("plan_es", SP + "_absent_plan_es.xlsx"), _cfg.IN.get("plan_ax", SP + "_absent_plan_ax.xlsx")
F_EES, F_EEM, F_MSP, F_DXP = _cfg.IN.get("plan_ees", SP + "_absent_plan_ees.xlsx"), _cfg.IN.get("plan_eem", SP + "_absent_plan_eem.xlsx"), _cfg.IN.get("plan_msp", SP + "_absent_plan_msp.xlsx"), _cfg.IN.get("plan_dxp", SP + "_absent_plan_dxp.xlsx")
F_HB2 = _cfg.IN.get("plan_hb2", SP + "_absent_plan_hb2.xlsx")   # 하반기 최신본 (MSP·플랫폼·DS)
_SR = _cfg.SHORT
SHORT = {F_HB: _SR.get("plan_hb", "하반기"), F_EC: _SR.get("plan_ec", "EC1·2사업부"), F_ES: _SR.get("plan_es", "ES사업부"), F_AX: _SR.get("plan_ax", "AX"),
         F_EES: _SR.get("plan_ees", "엔텍 ES"), F_EEM: _SR.get("plan_eem", "엔텍 EM"), F_MSP: _SR.get("plan_msp", "MSP 독자양식"),
         F_DXP: _SR.get("plan_dxp", "플랫폼 독자양식"), F_HB2: _SR.get("plan_hb2", "하반기(최신)")}
DEPT = _cfg.DEPT_FILES   # 부서가 올린 투입계획 (고정 자리 없는 부서) — 하반기보다 우선
FMT = {F_AX: "ax", F_MSP: "msp", F_DXP: "platform"}
for _d in DEPT: SHORT[_d["path"]] = _d["label"]; FMT[_d["path"]] = _d["fmt"]
PRESENT = collections.defaultdict(set)
PRESENT_X = collections.defaultdict(set)   # 동명이인 구분용: (이름, 그룹사번, 팀)
SOLD_KEEP = {("아이티센클로잇", "김충만"), ("아이티센클로잇", "이가은"), ("아이티센클로잇", "박상민"),
             ("아이티센엔텍", "전민서")}   # 엔텍 동행복권 인원 중 SOLD에 10~12월 배정이 있는 사람은 SOLD 기준
IGNORE = {"백재현"}   # 퇴사자
FIXED = []   # 성명 오기 보정 내역   # 10/1 MSP 전배자: SOLD 10~12월 그대로
CAP_T = {("아이티센클로잇", "이대근")}   # 휴직(~11/16): 월 투입을 가동대상MM 이하로   # 파일에 이름이 있는 사람 (대기 포함)
NONPJ = ("대기", "휴직", "퇴사", "육아", "전배", "전적", "교육", "N/A")
def clean_name(n): return re.sub(r"-\d+$", "", str(n).strip()) if n else None
def gid(x):
    try: return int(float(str(x).strip()))
    except Exception: return None

def rolling_rows(f):
    df, _ = parse_mm(f)
    out = []
    for _, r in df.iterrows():
        nm = clean_name(r["성명"]);
        if not nm or nm == "None": continue
        PRESENT[f].add(nm); PRESENT_X[f].add((nm, None, str(r["팀"] or "")))
        pj = str(r["PJT"] or "").strip(); code = str(r["코드"] or "").strip(); st = str(r["상태"] or "").strip(); kd = str(r["구분"] or "").strip()
        q = [r["mm"][m] for m in Q]
        if sum(q) <= 0: continue
        if st == "미투입" or kd == "지원" or code in ("N/A", "#N/A", "") and (not pj or pj.startswith(NONPJ)) or pj.startswith(NONPJ):
            continue
        out.append(dict(src=f, name=nm, gid=None, dept=r["부서"], team=r["팀"], pjt=pj, code=code, kind_raw=kd or ("이행" if st == "투입예정" else ""), q=q))
    return out

def ax_rows(f=None):
    f = f or F_AX
    wb = openpyxl.load_workbook(D + f, read_only=True, data_only=True); ws = wb["AX사업본부"]
    rows = [list(r) + [None] * 5 for r in ws.iter_rows(values_only=True)]
    hi = next(i for i, r in enumerate(rows[:10]) if "성명" in [str(x).strip() if x else "" for x in r] and "프로젝트명" in [str(x).strip() if x else "" for x in r])
    H = [re.sub(r"\s+", "", str(x)) if x is not None else "" for x in rows[hi]]
    cN, cG, cO, cP = H.index("성명"), H.index("그룹사번"), H.index("조직명"), H.index("프로젝트명")
    cS = next((i for i, h in enumerate(H) if h.startswith("Sold")), cP + 1); cK = next((i for i, h in enumerate(H) if h.startswith("제안")), cP + 2)
    mc = [_mcol(H, m, f, after=cP, test=lambda h, m=m: h.startswith(f"{m}월")) for m in QM]
    out = []; cur = None
    for r in rows[hi + 1:]:
        if r[cK] == "가동MM": break
        if r[cN]: cur = (clean_name(r[cN]), gid(r[cG]), r[cO]); PRESENT[f].add(cur[0]); PRESENT_X[f].add((cur[0], cur[1], str(cur[2] or "")))
        if cur is None or not r[cP]: continue
        q = _qv(r, mc)
        if sum(q) <= 0: continue
        out.append(dict(src=f, name=cur[0], gid=cur[1], dept="AX", team=cur[2], pjt=str(r[cP]).strip(), code="", kind_raw=str(r[cK] or "").strip(), q=q, sn=r[cS]))
    return out

def msp_rows(f=None):
    f = f or F_MSP
    wb = openpyxl.load_workbook(D + f, read_only=True, data_only=True); ws = wb.worksheets[0]
    out = []; cur = None; cur_g = None; mc = [12 + m for m in QM]   # 1월 = 13열 (0부터)
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i == 2:
            H = [re.sub(r"\s+", "", str(x)) if x is not None else "" for x in r]
            if "1월" in H: mc = [_mcol(H, m, f, after=H.index("1월") - 1) for m in QM]
        if i < 3: continue
        if r[7] == "소계": break
        if r[3]:
            # 번호(NO) 없이 같은 그룹사번으로 적힌 행 = 앞 사람의 추가 프로젝트 (성명 오기 보정, 예: 김우중 R&D 행이 '백재현'으로 기재)
            if r[0] is None and cur is not None and gid(r[1]) is not None and gid(r[1]) == cur_g:
                FIXED.append((clean_name(r[3]), cur, str(r[7] or "")))
            else:
                cur = clean_name(r[3]); cur_g = gid(r[1]); PRESENT[f].add(cur); PRESENT_X[f].add((cur, cur_g, "MSP엔지니어링팀"))
        if cur is None or not r[7]: continue
        pj = str(r[7]).strip()
        if pj.startswith(NONPJ) or "휴직" in pj: continue
        q = _qv(r, mc)
        if sum(q) <= 0: continue
        out.append(dict(src=f, name=cur, gid=gid(r[1]) if r[3] else None, dept="DX-Eng사업부", team="MSP엔지니어링팀", pjt=pj,
                        code=str(r[8] or "").strip(), kind_raw=str(r[10] or "").strip(), q=q))
    return out

def platform_rows(f=None):
    f = f or F_DXP
    wb = openpyxl.load_workbook(D + f, read_only=True, data_only=True); ws = wb["Platform"]
    rows = [list(r) + [None] * 5 for r in ws.iter_rows(values_only=True)]
    hi = next(i for i, r in enumerate(rows[:10]) if any(str(x).strip() == "12월" for x in r if x is not None))
    H = [re.sub(r"\s+", "", str(x)) if x is not None else "" for x in rows[hi]]
    cN = next(i for i, h in enumerate(H) if h in ("이름", "성명")); cP = H.index("프로젝트"); cG = H.index("등급") if "등급" in H else None
    cC = H.index("프로젝트코드") if "프로젝트코드" in H else None
    mc = [_mcol(H, m, f) for m in QM]
    SUMMARY = ("가득률", "가득율", "총원", "투입(가득)", "미투입")
    out = []; cur = None
    for r in rows[hi + 1:]:
        if all(x is None for x in (r[cN], r[cP])) and cur is not None and all(r[c] is None for c in mc if c is not None): break
        if r[cN] is None and str(r[cP] or "").strip() in SUMMARY: continue
        if r[cN]:
            cur = None if cG is not None and str(r[cG]).strip() in ("퇴직", "전적") else clean_name(r[cN])
            PRESENT[f].add(clean_name(r[cN]))
        if cur is None or not r[cP]: continue
        q = _qv(r, mc)
        if sum(q) <= 0: continue
        out.append(dict(src=f, name=cur, gid=None, dept="DX-Eng사업부", team="플랫폼엔지니어링팀", pjt=str(r[cP]).strip(),
                        code=str(r[cC] or "").strip() if cC is not None else "", kind_raw="", q=q))
    return out

def dxmsp_rows(f):
    """DX사업본부 인력운용 현황의 'MSP' 시트 (이름 · 투입과제 · 등급 · 이행구분 · 26년 1~12월)"""
    wb = openpyxl.load_workbook(D + f, read_only=True, data_only=True); ws = wb["MSP"]
    out = []; cur = None; hdr = False
    KR = {"이행프로젝트": "이행", "RnD과제": "R&D", "제안": "제안"}
    for r in ws.iter_rows(values_only=True):
        r = list(r) + [None] * 20
        if r[1] == "이름":
            hdr = True; H = [re.sub(r"\s+", "", str(x)) if x is not None else "" for x in r]
            mc = [_mcol(H, m, f, test=lambda h, m=m: h.endswith(f"{m}월") and not h.endswith(f"1{m}월")) for m in QM]
            continue
        if not hdr: continue
        nm = str(r[1]).strip() if r[1] else None
        if nm and (nm.startswith(("가득", "미투입", "총원", "가득율", "가득률", "합계", "Total", "소계")) or nm == "계" or re.match(r"^\d\.", nm)): cur = None; continue
        if nm:
            cur = clean_name(re.sub(r"\(.*?\)", "", nm)); PRESENT[f].add(cur)
        if cur is None or not r[2]: continue
        pj = str(r[2]).strip()
        if pj.startswith(NONPJ) or "휴직" in pj: continue
        q = _qv(r, mc)
        if sum(q) <= 0: continue
        m = re.search(r"\[(C[A-Z]\d{7}[A-Z]?)\]", pj)
        out.append(dict(src=f, name=cur, gid=None, dept="DX-Eng사업부", team="MSP엔지니어링팀", pjt=pj, code=m.group(1) if m else "",
                        kind_raw=KR.get(str(r[4] or "").strip(), str(r[4] or "").strip()), q=q))
    return out

def build():
    t = pd.read_pickle(SP + "use_target.pkl").copy()
    t.loc[t["사업부"] == "AX-Eng사업부", "사업부"] = "AX Consulting & Eng 사업부"
    c = pd.read_pickle(SP + "use_clo.pkl").copy(); c["법인"] = "아이티센클로잇"
    e = pd.read_pickle(SP + "use_et.pkl").copy(); e["법인"] = "아이티센엔텍"
    MC = [f"2026년_{m}월" for m in range(1, 13)]
    for x in (c, e): x[MC] = x[MC].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    # SOLD 코드 → 구분 (규칙 적용된 값)
    sold = pd.concat([c, e]); kmap = {}; kall = {}; kpers = {}   # kall: 9자리 코드의 구분 후보 (같은 코드에 P(제안)·C(이행)가 함께 있을 수 있음)
    for _, r in sold.iterrows():
        k = str(r["코드"])[:9]
        if k: kmap.setdefault(k, r["구분"]); kall.setdefault(k, set()).add(r["구분"]); kpers.setdefault((str(r["성명"]).strip(), k), set()).add(r["구분"])
    pjmap = {str(r["PJT 명"]).strip(): r["구분"] for _, r in sold.iterrows()}
    # 인원 현재 소속 (당월 기준)
    t["_g"] = t["그룹사번"].apply(gid)
    cur = t.sort_values(f"{_cfg.CUR}월").groupby(["법인", "_g"]).tail(1)
    q4T = t.groupby(["법인", "_g"])[[f"{m}월" for m in QM]].sum().sum(axis=1).to_dict()
    people = {(r["법인"], r["_g"]): dict(name=r["성명"], hq=r["본부"], dv=r["사업부"], tm=r["팀"], g=r["_g"], q4=q4T.get((r["법인"], r["_g"]), 0)) for _, r in cur.iterrows()}
    # 같은 이름이 여러 명(또는 사번 2개)인 경우: Q4 가동대상이 있는 사람 우선
    dup = collections.Counter((k[0], v["name"]) for k, v in people.items())
    def norm(x): return re.sub(r"[\s_\-&]", "", str(x or "")).lower().replace("팀", "").replace("사업부", "")
    def _in_file(f, corp, p, g):
        """이 파일에 그 사람이 적혀 있나 — 동명이인은 이름만 보지 않고 사번·팀까지 맞춰 봄"""
        nm = p["name"]
        if nm not in PRESENT[f]: return False
        if dup[(corp, nm)] <= 1: return True
        X = [x for x in PRESENT_X[f] if x[0] == nm]
        if not X: return True
        tn = {norm(p["tm"]), norm(p["dv"])} - {""}
        return any((x[1] is not None and x[1] == g) or (x[1] is None and norm(x[2]) in tn) or (x[1] is None and not norm(x[2])) for x in X) or \
               any(x[1] is not None and norm(x[2]) in tn for x in X)
    def src_for(corp, hq, dv, tm=""):
        for d in sorted(DEPT, key=lambda d: -sum(1 for k in ("hq", "dv", "tm") if d.get(k))):   # 부서 파일이 있으면 그 파일 (좁은 범위 먼저)
            if d["corp"] == corp and (not d.get("hq") or d["hq"] == hq) and (not d.get("dv") or d["dv"] == dv) and (not d.get("tm") or d["tm"] == tm):
                return d["path"]
        if corp == "아이티센엔텍": return F_EES if dv == "ES사업부" else F_EEM
        if hq == "AX사업본부": return F_AX
        if dv in ("EC1사업부", "EC2사업부"): return F_EC
        if tm in ("MSP엔지니어링팀", "플랫폼엔지니어링팀") or hq == "DS사업본부": return F_HB2
        if dv == "ES사업부": return F_ES
        return F_HB
    try:
        _teams = {(r["법인"], r["본부"], r["사업부"], r["팀"]) for _, r in t.iterrows()}
        _fr = [list(k) for k in _teams if src_for(*k) in _cfg.FRESH]
        __import__("json").dump({"teams": _fr}, open(SP + "fresh.json", "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as _e:
        print("fresh.json 기록 실패", _e)
    PRESENT.clear(); PRESENT_X.clear()
    def _parse(f):
        if not __import__("os").path.isfile(f): return []
        try:
            return ax_rows(f) if FMT.get(f) == "ax" else msp_rows(f) if FMT.get(f) == "msp" else platform_rows(f) if FMT.get(f) == "platform" else (platform_rows(f) + dxmsp_rows(f)) if FMT.get(f) == "dx" else rolling_rows(f)
        except Exception as ex:
            raise RuntimeError(f"투입계획 파일을 읽지 못했습니다: {SHORT[f]} — 양식(시트·열 이름)이 바뀌었는지 확인해 주세요 ({type(ex).__name__})") from ex
    R = {f: _parse(f) for f in SHORT}
    global _R_CACHE; _R_CACHE = R
    byname = {f: collections.defaultdict(list) for f in R}
    for f, rows in R.items():
        for x in rows: byname[f][x["name"]].append(x)
    new, used, notes = [], set(), collections.defaultdict(list)
    for (corp, g), p in people.items():
        if (corp, p["name"]) in SOLD_KEEP:
            base_ = c if corp == "아이티센클로잇" else e
            for _, r in base_[(base_["성명"] == p["name"]) & (base_[[MC[m] for m in Q]].sum(axis=1) > 0)].iterrows():
                row = {"법인": corp, "본부": p["hq"], "사업부": p["dv"], "팀": p["tm"], "성명": p["name"], "그룹사번": g, "구분": r["구분"],
                       "코드": r["코드"], "PJT 명": r["PJT 명"], "출처": "SOLD · 전배자" if corp == "아이티센클로잇" else "SOLD · SOLD 배정 우선"}
                for m in range(12): row[MC[m]] = float(r[MC[m]]) if m in Q else 0.0
                new.append(row)
            continue
        f = src_for(corp, p["hq"], p["dv"], p["tm"])
        rows = byname[f].get(p["name"], [])
        if f == F_AX:
            byg = [x for x in rows if x["gid"] == g]
            rows = byg or ([] if any(x["gid"] == people[k]["g"] for x in rows for k in people if k[0] == corp and people[k]["name"] == p["name"] and k != (corp, g)) else rows)
        if dup[(corp, p["name"])] > 1:
            same = [k for k, v in people.items() if k[0] == corp and v["name"] == p["name"]]
            if p["q4"] <= 0.005 and any(people[k]["q4"] > 0.005 for k in same if k != (corp, g)):
                continue           # 사번이 2개인 동일인: Q4 가동대상 있는 쪽에만 반영
            elif f != F_AX:
                tn = norm(p["tm"] if p["tm"] != "(직속)" else p["dv"])
                rows = [x for x in rows if norm(x["team"]) == tn or norm(x["dept"]) == tn]
                if len([k for k in same if people[k]["q4"] > 0.005]) > 1: notes["dupname"].append((p["name"], p["dv"], p["tm"], len(rows)))
        if not rows and not _in_file(f, corp, p, g) and f != F_HB and corp == "아이티센클로잇" and byname[F_HB].get(p["name"]):
            rows = byname[F_HB][p["name"]]; notes["fallback"].append((p["name"], p["dv"], p["tm"], SHORT[f]))
        for x in rows:
            used.add(id(x))
            code9 = x["code"][:9]
            kind = None
            if code9 and code9 not in ("N/A", "#N/A"):
                _kp = kpers.get((p["name"], code9)) or set()
                if len(_kp) == 1: kind = next(iter(_kp))                  # 같은 사람·같은 코드의 SOLD 구분
                elif len(kall.get(code9, ())) == 1: kind = next(iter(kall[code9]))
                elif len(kall.get(code9, ())) > 1:                        # P(제안)·C(이행) 둘 다 있는 코드 → 계획 파일의 '제안/이행' 칸을 따름
                    _kr = x["kind_raw"]
                    kind = "제안" if "제안" in _kr else ("R&D·내부과제" if "R&D" in _kr else ("이행" if "이행" in _kr else None))
            if kind is None and not (code9 and len(kall.get(code9, ())) > 1): kind = pjmap.get(x["pjt"])
            if kind is None:
                kr = x["kind_raw"]
                kind = "제안" if "제안" in kr else ("R&D·내부과제" if "R&D" in kr else "이행")
            if corp == "아이티센엔텍" and "동행복권" in x["pjt"] and "Next" in x["pjt"]: kind = "R&D·내부과제"
            row = {"법인": corp, "본부": p["hq"], "사업부": p["dv"], "팀": p["tm"], "성명": p["name"], "그룹사번": g, "구분": kind,
                   "코드": x["code"] if x["code"] not in ("N/A", "#N/A") else "", "PJT 명": x["pjt"], "출처": SHORT[x["src"]]}
            for m in range(12): row[MC[m]] = 0.0
            for i, m in enumerate(Q): row[MC[m]] = x["q"][i]
            new.append(row)
    # 계획 파일에 있으나 가동대상에 없는 행
    for f, rows in R.items():
        for x in rows:
            if id(x) in used: continue
            same_ = [(k, v) for k, v in people.items() if v["name"] == x["name"]]
            if len(same_) > 1 and len({k[0] for k, _ in same_}) < len(same_):   # 같은 법인에 동명이인: 사번 또는 팀이 맞는 사람이 있어야 '명단에 있음'
                tn_ = norm(x["team"]) if x.get("team") else ""
                ok_ = any((x.get("gid") is not None and x["gid"] == v["g"]) or (tn_ and tn_ in (norm(v["tm"]), norm(v["dv"]))) for _, v in same_)
                if not ok_ and x.get("gid") is None and not tn_: ok_ = True
                if not ok_: notes["unmatched"].append((SHORT[f], x["name"], x["team"], x["pjt"], round(sum(x["q"]), 2)))
                continue
            if x["name"] not in {v["name"] for v in people.values()}:
                notes["unmatched"].append((SHORT[f], x["name"], x["team"], x["pjt"], round(sum(x["q"]), 2)))
    P = pd.DataFrame(new)
    # ---- 규칙: SOLD에 해당 월 배정이 있으면 SOLD를 따른다 (사람·월 단위) ----
    sold_all = pd.concat([c, e], ignore_index=True); sold_all["_g"] = sold_all["그룹사번"].apply(gid)
    sold_over = []; add = []
    for (corp, g), p in people.items():
        sr = sold_all[(sold_all["법인"] == corp) & (sold_all["_g"] == g)]
        if sr.empty: continue
        for m in Q:
            sm = float(sr[MC[m]].sum())
            if sm <= 0.005: continue
            mask = (P["법인"] == corp) & (P["그룹사번"] == g)
            pm = float(P.loc[mask, MC[m]].sum()) if len(P) else 0.0
            Tm = float(t[(t["법인"] == corp) & (t["_g"] == g)][f"{m+1}월"].sum())
            if corp == "아이티센엔텍" and sm > pm + 0.005 and Tm > 0.005:   # 계획이 SOLD보다 적게 잡혀 대기가 생기는 경우 → SOLD 배정 우선
                if len(P): P.loc[mask, MC[m]] = 0.0
                for _, r in sr[sr[MC[m]] > 0].iterrows():
                    row = {"법인": corp, "본부": p["hq"], "사업부": p["dv"], "팀": p["tm"], "성명": p["name"], "그룹사번": g, "구분": r["구분"],
                           "코드": r["코드"], "PJT 명": r["PJT 명"], "출처": "SOLD 배정 우선"}
                    for mm in range(12): row[MC[mm]] = float(r[MC[mm]]) if mm == m else 0.0
                    add.append(row)
                sold_over.append((corp, p["name"], p["tm"], f"{m+1}월", round(pm, 2), round(sm, 2)))
    if add: P = pd.concat([P, pd.DataFrame(add)], ignore_index=True)
    P = P[P[[MC[m] for m in Q]].sum(axis=1) > 0].reset_index(drop=True)
    notes["sold_over"] = sold_over
    capped = []
    for (corp, g), idx in P.groupby(["법인", "그룹사번"]).groups.items():
        for m in Q:
            col = MC[m]; tot = P.loc[idx, col].sum()
            if tot > 1.0001:
                P.loc[idx, col] = P.loc[idx, col] / tot
                capped.append((corp, P.loc[idx[0], "성명"], P.loc[idx[0], "팀"], f"{m+1}월", round(tot, 2), P.loc[idx[0], "출처"]))
    notes["capped"] = capped
    for (corp, g), idx in P.groupby(["법인", "그룹사번"]).groups.items():
        nm = P.loc[idx[0], "성명"]
        for m in Q:
            col = MC[m]; tot = P.loc[idx, col].sum(); T = t[(t["법인"] == corp) & (t["_g"] == g)][f"{m+1}월"].sum()
            if tot > T + 0.0001:
                P.loc[idx, col] = P.loc[idx, col] * (T / tot if tot else 0)
                notes["capT"].append((nm, f"{m+1}월", round(tot, 2), round(T, 2)))
    new = P.to_dict("records")
    out = {}
    for corp, base, key in (("아이티센클로잇", c, "clo"), ("아이티센엔텍", e, "et")):
        b = base.copy()
        Qc = [m for m in Q if m >= _cfg.act_of(corp)]   # 이 법인 SOLD가 이미 확정한 달은 SOLD 그대로
        for m in Qc: b[MC[m]] = 0.0
        b["출처"] = "SOLD"
        pp = P[P["법인"] == corp].copy()
        for m in Q:
            if m not in Qc: pp[MC[m]] = 0.0
        allr = pd.concat([b, pp], ignore_index=True)
        allr.to_pickle(SP + f"use_{key}_plan.pkl"); out[key] = allr
    # 비교 자료: 우선 파일 vs 하반기
    cmp = []
    for f in (F_EC, F_ES, F_AX, F_MSP, F_DXP):
        for nm, rows in byname[f].items():
            a = [sum(x["q"][i] for x in rows) for i in range(len(Q))]
            b = [sum(x["q"][i] for x in byname[F_HB].get(nm, [])) for i in range(len(Q))]
            if any(abs(u - v) > 0.01 for u, v in zip(a, b)): cmp.append((SHORT[f], nm, [round(v, 2) for v in a], [round(v, 2) for v in b]))
    # 사람별 월 합 > 가동대상 체크
    over = []
    for (corp, g), grp in P.groupby(["법인", "그룹사번"]):
        for m in Q:
            s = grp[MC[m]].sum(); T = t[(t["법인"] == corp) & (t["_g"] == g)][f"{m+1}월"].sum()
            if s > T + 0.01: over.append((corp, grp["성명"].iloc[0], f"{m+1}월", round(s, 2), round(T, 2), grp["출처"].iloc[0]))
    return P, notes, cmp, over, people

if __name__ == "__main__":
    P, notes, cmp, over, people = build()
    print("plan rows", len(P)); print(P.groupby(["법인", "출처"])[[f"2026년_{m}월" for m in QM]].sum().round(2))
    print("fallback", notes["fallback"][:20], len(notes["fallback"]))
    print("unmatched", len(notes["unmatched"])); [print(" ", u) for u in notes["unmatched"][:60]]
    print("diff priority vs 하반기", len(cmp)); [print(" ", x) for x in cmp[:60]]
    print("over", len(over)); [print(" ", x) for x in over[:40]]

def anomalies():
    P, notes, cmp, over, people = build()
    MC = [f"2026년_{m}월" for m in QM]; RQ = _cfg.R(QM[0]) if QM else ""
    A = []
    for corp, nm, tm, mon, tot, src in notes["capped"]:
        A.append(("반영 완료 · 1.00으로 맞춤", f"{nm} ({tm})", f"{mon} 투입 합계 {tot:.2f} → 1.00 · {src}"))
    for corp, nm, mon, s, T, src in over:
        A.append(("가동대상보다 투입이 큼", nm, f"{mon} 투입 {s:.2f} / 가동대상 {T:.2f} · 휴직·복직 일정 확인 · {src}"))
    for src, nm, tm, pj, q in notes["unmatched"]:
        if nm in IGNORE: continue
        A.append(("계획엔 있으나 가동대상 명단에 없음", f"{nm} ({tm})", f"{pj} · {RQ} {q:.2f}MM · {src}"))
    try:
        for r_ in json.load(open(SP + "hr_applied.json", encoding="utf-8")):
            if r_.get("ok"): A.append(("반영 완료 · 인사 변동 입력", f'{r_["name"]} ({r_.get("team") or r_.get("dept")})', f'{r_["kind"]} {r_["date"]} → 가동대상MM {r_["msg"]}'))
            else: A.append(("확인 필요 · 인사 변동 입력을 적용하지 못함", f'{r_["name"]} ({r_.get("dept") or ""})', f'{r_["kind"]} {r_["date"]} · {r_["msg"]}'))
    except Exception: pass
    have = set(zip(P["법인"], P["그룹사번"]))
    t = pd.read_pickle(SP + "use_target.pkl"); t["_g"] = t["그룹사번"].apply(gid)
    for nm in ("김충만", "이가은", "박상민"):
        x = P[P["성명"] == nm]
        A.append(("반영 완료 · 전배자 SOLD 기준", f"{nm} (MSP엔지니어링팀)", f"10/1 플랫폼 → MSP 전배 · {RQ} = SOLD 내역 그대로 (월 " + "/".join(f"{x[c].sum():.2f}" for c in MC) + ")"))
    for nm, mon, tot, T in notes["capT"]:
        if any(nm == x[1] for x in CAP_T): A.append(("반영 완료 · 휴직(~11/16)", nm, f"{mon} 투입 {tot:.2f} → {T:.2f} (가동대상MM에 맞춤)"))
        else: A.append(("반영 완료 · 가동대상만큼만 반영", nm, f"{mon} 투입계획 {tot:.2f} > 가동대상 {T:.2f} → {T:.2f}로 맞춤 (퇴사·휴직·전출 후 계획이 남아 있음 · 부서 파일 확인)"))
    e = P[(P["법인"] == "아이티센엔텍") & P["PJT 명"].str.contains("동행복권") & P["PJT 명"].str.contains("Next")]
    if len(e): A.append(("반영 완료 · 9월 회신 파일 기준", "엔텍 동행복권 Next Gen", f'{", ".join(e["성명"])} {RQ} R&D (SOLD에 배정 없음)'))
    j = P[(P["법인"] == "아이티센엔텍") & (P["성명"] == "전민서")]
    if len(j): A.append(("반영 완료 · SOLD 배정 우선", "전민서 (복권사업팀)", "SOLD 현대모비스 nSMART 10월 1.00 · 11~12월 0 → 동행복권 계획 대신 SOLD 적용"))
    for corp, nm, tm, mon, pm, sm in notes["sold_over"]:
        A.append(("반영 완료 · SOLD 배정 우선", f"{nm} ({tm})", f"{mon} 투입계획 {pm:.2f} < SOLD {sm:.2f} → SOLD 적용"))
    for wrong, right, pj in dict.fromkeys(FIXED):
        A.append(("반영 완료 · 성명 오기 보정", f"{right} (MSP엔지니어링팀)", f"MSP 파일에 같은 그룹사번으로 '{wrong}' 이름이 적힌 '{pj}' 행 → {right} 투입으로 반영"))
    for f_, m_ in dict.fromkeys(MISSCOL): A.append(("투입계획 파일에 월 열 없음", SHORT.get(f_, str(f_)), f"{m_}월 열을 찾지 못해 0으로 읽음 — 파일 양식 확인"))
    A.append(("우선 파일과 하반기 파일이 다름", f"{len(cmp)}명", "우선 파일(부서별·독자양식) 값 반영 · 상세는 엑셀 '우선파일_vs_하반기'"))
    return A, P, cmp
