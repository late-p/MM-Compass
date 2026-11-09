# 실데이터 집계: 가동대상(use_target) + 투입(use_clo, use_et) → 조직 트리 (12개월)
import pandas as pd, warnings
warnings.filterwarnings("ignore")
SP = __import__('cfg').WORK
M = 12
# 비매출 모수 사업부장 (26년 가동가득 통계 기준: 클로잇 사업부장 3자리 + 엔텍 ENT 사업부장 2명) — 기준정보에서 관리
NP_HEADS = {("아이티센클로잇", __import__("cfg").A("최지석")), ("아이티센클로잇", __import__("cfg").A("윤상훈")), ("아이티센클로잇", __import__("cfg").A("정승모")), ("아이티센클로잇", __import__("cfg").A("강기식")),
            ("아이티센엔텍", __import__("cfg").A("정윤채")), ("아이티센엔텍", __import__("cfg").A("이준규"))}
KIND = {"이행": "ex", "제안": "pr", "R&D·내부과제": "rd"}
CORP_ORDER = ["아이티센클로잇", "아이티센엔텍"]
HQ_ORDER = {"아이티센클로잇": ["ENT사업본부", "DX사업본부", "AX사업본부", "DS사업본부", "스포츠Tech사업부"], "아이티센엔텍": ["ENT사업본부"]}

def _load():
    t = pd.read_pickle(SP + "use_target.pkl").copy()
    t.loc[t["사업부"] == "AX-Eng사업부", "사업부"] = "AX Consulting & Eng 사업부"   # 구 조직명
    c = pd.read_pickle(SP + "use_clo_plan.pkl").copy(); c["법인"] = "아이티센클로잇"
    e = pd.read_pickle(SP + "use_et_plan.pkl").copy(); e["법인"] = "아이티센엔텍"
    i = pd.concat([c, e], ignore_index=True)
    MC = [f"2026년_{m}월" for m in range(1, 13)]
    i[MC] = i[MC].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return t, i, MC

def build():
    t, i, MC = _load()
    K = ["법인", "본부", "사업부", "팀"]
    leaf = {}
    def z(): return dict(T=[0.0]*M, ex=[0.0]*M, pr=[0.0]*M, rd=[0.0]*M, np=[0.0]*M, exh=[0.0]*M)
    for _, r in t.iterrows():
        k = tuple(r[K]); d = leaf.setdefault(k, z())
        for m in range(M):
            v = float(r[f"{m+1}월"]); d["T"][m] += v
            if (r["법인"], r["성명"]) in NP_HEADS: d["np"][m] += v
    def _g(x):
        try: return int(float(str(x).strip()))
        except Exception: return None
    execs = {(r["법인"], r["성명"]) for _, r in t.iterrows() if (r["법인"], r["성명"]) in NP_HEADS}
    for _, r in i.iterrows():
        k = tuple(r[K]); d = leaf.setdefault(k, z()); f = KIND.get(r["구분"])
        if not f: continue
        for m in range(M):
            v = float(r[MC[m]]); d[f][m] += v
            # 비매출 모수 = 임원(가동대상 전체) + R&D·내부과제 투입MM (임원은 중복 제외)
            hd_ = (r["법인"], r["성명"]) in execs
            if f == "rd" and not hd_: d["np"][m] += v          # 비매출 과제 (사업부장 중복 제외)
            if f == "ex" and hd_: d["exh"][m] += v             # 사업부장 이행 MM은 가득에서도 제외
    return leaf

def add(a, b): return {k: [x+y for x, y in zip(a[k], b[k])] for k in a}
def derive(d):
    o = {k: [round(v, 4) for v in d[k]] for k in d}
    T, ex, pr, rd, np_ = d["T"], d["ex"], d["pr"], d["rd"], d["np"]
    exn = [a - b for a, b in zip(ex, d["exh"])]
    inp = [a+b+c for a, b, c in zip(ex, pr, rd)]
    o["idle"] = [round(a-b, 4) for a, b in zip(T, inp)]
    o["u"] = [round(a/b*100, 4) if b > 0.005 else None for a, b in zip(inp, T)]
    o["g"] = [round(a/b*100, 4) if b > 0.005 else None for a, b in zip(ex, T)]
    o["gn"] = [round(a/(b-c)*100, 4) if (b-c) > 0.005 else None for a, b, c in zip(exn, T, np_)]
    sT, sI, sE, sN = sum(T), sum(inp), sum(ex), sum(np_)
    o["yu"] = sI/sT*100 if sT else 0; o["yg"] = sE/sT*100 if sT else 0; o["yn"] = sum(exn)/(sT-sN)*100 if sT-sN else 0
    c9 = __import__("cfg").ACTM   # 실적 확정 월까지 누계
    o["cu"] = sum(inp[:c9])/sum(T[:c9])*100 if sum(T[:c9]) else 0
    o["cg"] = sum(ex[:c9])/sum(T[:c9])*100 if sum(T[:c9]) else 0
    o["cn"] = sum(exn[:c9])/(sum(T[:c9])-sum(np_[:c9]))*100 if sum(T[:c9])-sum(np_[:c9]) else 0
    return o

def tree():
    leaf = build()
    if __import__('cfg').IN.get('stats'):
        import stats1008 as _st; _st.apply_leaf(leaf)   # 10.08 통계 파일 기준으로 조직 숫자 맞춤
    Z = lambda: dict(T=[0.0]*M, ex=[0.0]*M, pr=[0.0]*M, rd=[0.0]*M, np=[0.0]*M, exh=[0.0]*M)
    total = Z(); corps = []
    for corp in CORP_ORDER:
        cz = Z(); hqs = []
        hq_names = HQ_ORDER[corp] + sorted({k[1] for k in leaf if k[0] == corp} - set(HQ_ORDER[corp]))
        for hq in hq_names:
            hz = Z(); divs = []
            dnames = list(dict.fromkeys(k[2] for k in sorted(leaf) if k[0] == corp and k[1] == hq))
            # 직속 먼저
            dnames.sort(key=lambda x: (x != "(직속)", x))
            for dv in dnames:
                dz = Z(); teams = []
                tnames = sorted({k[3] for k in leaf if k[:3] == (corp, hq, dv)}, key=lambda x: (x != "(직속)", x))
                for tm in tnames:
                    lz = leaf[(corp, hq, dv, tm)]
                    if sum(lz["T"]) == 0 and sum(lz["ex"]) + sum(lz["pr"]) + sum(lz["rd"]) == 0: continue
                    if dv == "(직속)" and tm == "(직속)": label = hq
                    elif tm == "(직속)": label = dv
                    else: label = tm
                    teams.append(dict(name=label, raw=tm, d=derive(lz))); dz = add(dz, lz)
                divs.append(dict(name=dv, d=derive(dz), teams=teams)); hz = add(hz, dz)
            hqs.append(dict(name=hq, corp=corp, d=derive(hz), divs=divs)); cz = add(cz, hz)
        corps.append(dict(name=corp, d=derive(cz), hqs=hqs)); total = add(total, cz)
    return dict(d=derive(total), corps=corps)

if __name__ == "__main__":
    T = tree()
    def p(n, d, ind=""):
        print(f"{ind}{n:28s} T9={d['T'][8]:7.2f} ex9={d['ex'][8]:7.2f} u9={d['u'][8]:6.2f} g9={d['g'][8]:6.2f} | u10={d['u'][9]:6.2f} T10={d['T'][9]:7.2f} | yu={d['yu']:.2f} yg={d['yg']:.2f} yn={d['yn']:.2f}")
    p("전체", T["d"])
    for c in T["corps"]:
        p(c["name"], c["d"], " ")
        for h in c["hqs"]:
            p(h["name"], h["d"], "  ")
            for dv in h["divs"]:
                p(dv["name"], dv["d"], "    ")
                for tm in dv["teams"]: p(tm["name"], tm["d"], "      ")
    print([round(x, 2) for x in T["d"]["u"]]); print([round(x, 2) for x in T["d"]["g"]]); print([round(x, 2) for x in T["d"]["gn"]])
