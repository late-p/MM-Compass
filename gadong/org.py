"""조직 · 팀 목록 (투입계획 제출 단위 = 팀)
- 팀 키: "법인 · 본부 · 사업부 · 팀" (본부·사업부 바로 아래 인원은 팀 자리에 '(직속)')
- 목록은 가장 최근 통계 집계 결과(work/<주차>/use_target.pkl)의 가동대상 인원 기준 — 당월~12월 가동대상이 있는 팀만
- 담당 범위(users.depts)·제출 대상에는 사업부(또는 본부)도 넣을 수 있고, 그러면 그 아래 팀 전부를 뜻함
"""
import os, re, json
from engine.roles import split_dept

DIRECT = "(직속)"
_cache = {}

def key(corp, hq, dv, tm): return " · ".join([corp or "", hq or "", dv or "", tm or ""])

def _latest(storage):
    from .files import latest_work_root
    w = latest_work_root(storage)
    if not os.path.isdir(w): return None
    ls = sorted(l for l in os.listdir(w) if re.fullmatch(r"\d{4}-\d{2}-W\d", l) and os.path.exists(os.path.join(w, l, "use_target.pkl")))
    return ls[-1] if ls else None

def label(k, full=False):
    """화면에 보일 이름: 사업부 › 팀 (직속이면 사업부(직속))"""
    corp, hq, dv, tm = split_dept(k)
    if not tm and not dv: return " · ".join(x for x in (corp, hq) if x) if full else (hq or corp)
    if not tm: return f"{hq} › {dv}" if full else dv + (" · 엔텍" if corp == "아이티센엔텍" else "")
    up = dv if dv and dv != DIRECT else hq
    nm = f"{up} (직속)" if tm == DIRECT else (tm if tm == up else f"{up} › {tm}")
    if full: return f"{corp.replace('아이티센', '')} · " + nm
    return nm + (" · 엔텍" if corp == "아이티센엔텍" else "")

def _gid(x):
    try: return int(float(str(x).strip()))
    except Exception: return None

_rcache = {}
def roster(storage):
    """(주차 라벨, 당월, [사람]) — 사람마다 지금 소속 팀 하나로 정리 (가동인력목록에 소속이 여러 줄이면 당월 가동대상이 큰 쪽, plan.py와 같은 기준)
    사람: {corp,gid,name,hq,dv,tm,key,T[12]} · 당월~12월 가동대상이 하나도 없는 사람(퇴사·전출·휴직)은 빠짐"""
    lb = _latest(storage)
    if not lb: return None, 0, []
    from .files import latest_work_root
    p = os.path.join(latest_work_root(storage), lb, "use_target.pkl"); mt = os.path.getmtime(p)
    if _rcache.get("k") == (p, mt): return lb, _rcache["cur"], _rcache["v"]
    import pandas as pd
    t = pd.read_pickle(p)
    if "제외" in t.columns: t = t[t["제외"].fillna("") == ""]
    cur = int(lb[5:7]); out = {}
    for r in t.to_dict("records"):
        T = [float(pd.to_numeric(r.get(f"{m}월"), errors="coerce") or 0) for m in range(1, 13)]
        g = (r["법인"], _gid(r["그룹사번"]) if _gid(r["그룹사번"]) is not None else "n:" + str(r["성명"]))
        x = out.get(g)
        if x is None: x = out[g] = dict(corp=r["법인"], gid=g[1], name=r["성명"], T=[0.0] * 12, best=None)
        for i in range(12): x["T"][i] += T[i]
        score = (T[cur - 1], sum(T[cur - 1:]))
        if x["best"] is None or score >= x["best"][0]: x["best"] = (score, r)
    people = []
    for x in out.values():
        if sum(x["T"][cur - 1:]) <= 0.005: continue
        r = x["best"][1]
        people.append(dict(corp=x["corp"], gid=x["gid"], name=x["name"], hq=r["본부"], dv=r["사업부"], tm=r["팀"], key=key(r["법인"], r["본부"], r["사업부"], r["팀"]), T=[round(v, 4) for v in x["T"]]))
    _rcache.update(k=(p, mt), cur=cur, v=people)
    return lb, cur, people

def teams(storage):
    """[{key, corp, hq, dv, tm, label, grp, n}] — 가동대상이 있는 팀만, 조직 순서"""
    lb, cur, people = roster(storage)
    seen = {}
    for x in people:
        k = x["key"]
        if k not in seen:
            seen[k] = dict(key=k, corp=x["corp"], hq=x["hq"], dv=x["dv"], tm=x["tm"], label=label(k), n=0,
                           grp=(x["dv"] if x["dv"] != DIRECT else x["hq"]) + (" · 엔텍" if x["corp"] == "아이티센엔텍" else ""))
        seen[k]["n"] += 1
    CORP = {"아이티센클로잇": 0, "아이티센엔텍": 1}
    return sorted(seen.values(), key=lambda x: (CORP.get(x["corp"], 9), x["hq"], x["dv"] != DIRECT, x["dv"], x["tm"] != DIRECT, x["tm"]))

def covers(unit, team_key):
    """unit(법인/본부/사업부/팀 중 어디까지 적힌 부서)이 그 팀을 포함하는지"""
    u = split_dept(unit); t = split_dept(team_key)
    if not u[0]: return False
    return all((not a) or a == b for a, b in zip(u, t))

def expand(storage, units):
    """부서·팀 목록 → 그 아래 팀 키 목록 (조직 순서, 중복 없음)"""
    units = [x for x in (units or []) if x]
    return [t["key"] for t in teams(storage) if any(covers(u, t["key"]) for u in units)]

def groups(storage, keys=None):
    """사업부별로 묶은 팀: [(사업부 키, 사업부 이름, [팀...])]"""
    ks = set(keys) if keys is not None else None
    out = []
    for t in teams(storage):
        if ks is not None and t["key"] not in ks: continue
        g = key(t["corp"], t["hq"], t["dv"] if t["dv"] != DIRECT else "", "")
        g = g.rstrip(" ·").replace(" ·  · ", " · ")
        gk = " · ".join(x for x in (t["corp"], t["hq"], t["dv"] if t["dv"] != DIRECT else "") if x)
        if not out or out[-1][0] != gk:
            out.append((gk, label(gk, full=True), []))
        out[-1][2].append(t)
    return out

def summary(keys):
    """팀 목록을 짧게: 1개면 그 이름, 여러 개면 '사업부 외 n팀'"""
    keys = list(keys or [])
    if not keys: return ""
    if len(keys) == 1: return label(keys[0])
    dvs = sorted({split_dept(k)[2] for k in keys})
    return f"{label(keys[0])} 외 {len(keys) - 1}팀" if len(dvs) > 1 else f"{dvs[0]} {len(keys)}팀"

def common_unit(keys):
    """여러 팀을 대표하는 부서 문자열 (업로드 기록의 dept 칸용): 공통 앞부분"""
    ps = [split_dept(k) for k in keys]
    if not ps: return ""
    out = []
    for i in range(4):
        v = {p[i] for p in ps}
        if len(v) == 1 and list(v)[0]: out.append(list(v)[0])
        else: break
    return " · ".join(out)
