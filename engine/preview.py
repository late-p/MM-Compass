"""업로드 반영 미리보기 — 재계산 전에, 올린 파일에서 무엇을 읽었는지와 이상한 점을 보여 준다

사용: python -m engine.preview <storage> <upload_id>   (사이트 폴더에서 실행)
결과: storage/previews/<upload_id>.json
 - read   : 읽은 범위 (팀별 인원·10~12월 MM, 지금 쓰는 파일과 비교)
 - red    : 꼭 확인할 것 (가동대상 아닌 사람에게 계획, 1인 월 1.00 초과, 팀 가동률 100% 초과)
 - yellow : 참고 (지금 파일엔 있는데 새 파일에서 빠진 사람, 크게 바뀐 사람)
 - changes: 사람별 10~12월 변화
"""
import re, os, sys, json, glob, sqlite3, datetime as dt, collections, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
CALC = os.path.join(HERE, "calc")
MON = ["10월", "11월", "12월"]   # plan 모듈을 읽은 뒤 이번 주차 기준(실적 확정 다음 달 ~ 12월)으로 바뀜

def _rows(plan, path, fmt):
    if fmt == "ax": return plan.ax_rows(path)
    if fmt == "msp": return plan.msp_rows(path)
    if fmt == "platform": return plan.platform_rows(path)
    if fmt == "dx": return plan.platform_rows(path) + plan.dxmsp_rows(path)
    return plan.rolling_rows(path)

def _kind(x):
    """구분: 제안 / R&D·내부과제 / 이행 (파일의 구분 칸 기준)"""
    kr = str(x.get("kind_raw") or ""); pj = str(x.get("pjt") or "")
    if "동행복권" in pj and "Next" in pj: return "R&D·내부과제"
    if "제안" in kr: return "제안"
    if "R&D" in kr.upper() or "RND" in kr.upper() or "과제" in kr: return "R&D·내부과제"
    return "이행"

PKEY = lambda x: x["name"]   # 같은 이름이 여러 명이면 main()에서 "이름 (팀)" 형태로 바꿔 끼움
_LAB = {}
def _bn(k): return _LAB.get(k, k)
def _norm_t(s): return re.sub(r"[\s_\-&]", "", str(s or "")).lower().replace("팀", "").replace("사업부", "")

def _by_person(rows):
    out = collections.OrderedDict()
    for x in rows:
        p = out.setdefault(PKEY(x), dict(q=[0.0] * len(MON), team=x.get("team") or "", pj=[], items=collections.OrderedDict()))
        for i in range(len(MON)): p["q"][i] += x["q"][i]
        p["pj"].append(x["pjt"])
        idk = re.sub(r"[\s\[\]()_\-·.,]", "", str(x["pjt"])).lower() or str(x["pjt"])   # 띄어쓰기·괄호 표기만 다른 같은 이름은 같은 프로젝트로
        k_ = (_kind(x), idk); p.setdefault("nm", {}).setdefault(k_, x["pjt"])
        it = p["items"].setdefault(k_, [0.0] * len(MON))
        for i in range(len(MON)): it[i] += x["q"][i]
    return out

def _old_cached(plan, path, fmt, work):
    """지금 쓰는 큰 파일은 팀마다 똑같이 읽으므로 한 번 읽은 결과를 저장해 두고 재사용 (파일이 바뀌면 자동으로 다시 읽음)"""
    import pickle, hashlib
    st = os.stat(path); key = hashlib.md5(f"{path}|{st.st_mtime_ns}|{st.st_size}|{fmt}".encode("utf-8")).hexdigest()[:16]
    cp = os.path.join(work, f"oldcache_{key}.pkl")
    try:
        with open(cp, "rb") as fh: return pickle.load(fh)
    except Exception: pass
    out = _by_person(_rows(plan, path, fmt))
    try:
        for f_ in os.listdir(work):
            if f_.startswith("oldcache_") and f_ != os.path.basename(cp): os.remove(os.path.join(work, f_))
        tmp = cp + f".{os.getpid()}.tmp"
        with open(tmp, "wb") as fh: pickle.dump(out, fh)
        os.replace(tmp, cp)
    except Exception: pass
    return out

def main(storage, uid):
    sys.path.insert(0, os.path.dirname(HERE))
    from engine import roles as RL, run as RUN
    from gadong import db
    c = db.connect(storage=storage)
    try: u = c.execute("SELECT * FROM uploads WHERE id=?", (uid,)).fetchone()
    finally: c.close()
    path = os.path.join(storage, "uploads", u["stored_name"])
    res = dict(id=uid, name=u["orig_name"], kind=u["kind"], at=dt.datetime.now().strftime("%Y-%m-%d %H:%M"), read=[], red=[], yellow=[], changes=[], note="")
    if u["kind"] != "plan":
        res["note"] = "투입계획이 아닌 파일은 미리보기를 지원하지 않습니다. 재계산할 때 전체를 읽어 반영합니다."
        return res
    fmt = RL.detect_format(path)
    dept = u["dept"] or RL.infer_dept(u["orig_name"], fmt) or ""
    role, scope, err = RL.role_for_upload("plan", dept, fmt)
    FMTN = {"rolling": "인력롤링 양식", "ax": "AX 가득가동현황", "dx": "DX 인력운용 현황 (MSP 시트 + Platform 시트)", "platform": "DX 인력운용 현황 (Platform 시트)", "msp": "MSP 투입계획"}
    res.update(fmt=FMTN.get(fmt, "알 수 없음"), dept=dept, place=(RL.ROLES[role][0] if role else (f"투입계획 · {' · '.join(x for x in (scope or {}).values() if x)}" if scope else "")))
    if err: res["red"].append(err); return res
    corp = RL.ET if dept.startswith(RL.ET) else RL.CLO
    # 계산 설정 (plan.py 가 읽을 수 있게) — 지금 반영된 파일 기준
    inputs, short, dept_files, files, used, warns, fresh = RUN.resolve_inputs(storage, u["week"], exclude_id=uid)
    work = os.path.join(storage, "work", "_preview") + os.sep; os.makedirs(work, exist_ok=True)
    json.dump(dict(work=work, inputs=inputs, short=short, dept_files=dept_files, week=RUN.week_meta(u["week"])), open(work + "cfg.json", "w", encoding="utf-8"), ensure_ascii=False)
    os.environ["GADONG_CFG"] = work + "cfg.json"; sys.path.insert(0, CALC)
    import plan
    global MON; MON = [f"{m}월" for m in plan.QM]
    # 가동대상 (가장 최근 재계산 결과) — 같은 이름이 여러 명이면 사번·팀으로 구분해 "이름 (팀)"으로 따로 다룸
    global PKEY
    tgt = None; _dup = {}
    cands = sorted(glob.glob(os.path.join(storage, "work", "*", "use_target.pkl")), key=os.path.getmtime)
    if cands:
        import pandas as pd
        t = pd.read_pickle(cands[-1]); t = t[t["법인"] == corp]
        def _g(v):
            try: return int(float(str(v).strip()))
            except Exception: return None
        per = collections.OrderedDict()
        for _, r in t.iterrows():
            tm_ = r["팀"] if r["팀"] != "(직속)" else (r["사업부"] if r["사업부"] != "(직속)" else r["본부"])
            e = per.setdefault((r["성명"], _g(r["그룹사번"])), dict(T=[0.0] * len(MON), rows=[]))
            tv = [float(r[m] or 0) for m in MON]
            for i, v in enumerate(tv): e["T"][i] += v
            e["rows"].append((sum(tv), tm_, r["본부"], r["사업부"]))
        cnt = collections.Counter(n for n, _ in per)
        tgt = {}
        for (n, g_), e in per.items():
            best = max(e["rows"], key=lambda z: z[0])
            ent = dict(T=e["T"], team=best[1], hq=best[2], dv=best[3])
            if cnt[n] > 1:
                lab = f"{n} ({best[1]})"
                if lab in tgt: lab = f"{n} ({best[1]} #{g_})"
                _dup.setdefault(n, []).append((g_, best[1], lab)); _LAB[lab] = n; tgt[lab] = ent
            else: tgt[n] = ent
        def _pk(x):
            n = x["name"]; c = _dup.get(n)
            if not c: return n
            g = x.get("gid")
            if g is not None:
                for g2, tm, lab in c:
                    if g2 == g: return lab
            tn = _norm_t(x.get("team") or x.get("dept"))
            if tn:
                for g2, tm, lab in c:
                    if _norm_t(tm) == tn: return lab
            return f"{n} ({x.get('team') or '팀 모름'})"
        PKEY = _pk
    new = _by_person(_rows(plan, path, fmt))
    # 지금 쓰는 같은 자리 파일
    prev_path, prev_fmt = None, None
    if role: prev_path, prev_fmt = inputs.get(role), RL.PLAN_FMT.get(role, "rolling")
    else:
        # 지금 이 범위(팀·사업부)를 계산에 쓰는 파일: 이 범위를 덮는 부서 파일 중 가장 좁은 것 → 고정 자리 파일 → 하반기 총괄 (plan.py가 고르는 순서와 같게)
        cov = [d for d in dept_files if d["corp"] == scope["corp"] and (not d["hq"] or d["hq"] == scope["hq"]) and (not d["dv"] or d["dv"] == scope["dv"]) and (not d["tm"] or d["tm"] == scope["tm"])]
        d = max(cov, key=lambda d: sum(1 for k in ("hq", "dv", "tm") if d.get(k))) if cov else None
        if d: prev_path, prev_fmt = d["path"], d["fmt"]
        else:
            c_, h_, v_, t_ = scope["corp"], scope["hq"], scope["dv"], scope["tm"]
            r_ = (("plan_ees" if v_ == "ES사업부" else "plan_eem") if c_ == "아이티센엔텍" else "plan_ax" if h_ == "AX사업본부" else "plan_ec" if v_ in ("EC1사업부", "EC2사업부")
                  else "plan_hb2" if (t_ in ("MSP엔지니어링팀", "플랫폼엔지니어링팀") or h_ == "DS사업본부") else "plan_es" if v_ == "ES사업부" else "plan_hb2")
            prev_path, prev_fmt = inputs.get(r_) or inputs.get("plan_hb2"), RL.PLAN_FMT.get(r_, "rolling")
            res["prev_role"] = r_
    old = {}
    if prev_path and os.path.exists(prev_path):
        try: old = _old_cached(plan, prev_path, prev_fmt, work)
        except Exception: res["note"] = "지금 쓰는 파일을 읽지 못해 비교는 생략했습니다."
    def team_of(nm, p): return (tgt[nm]["team"] if tgt and nm in tgt else (p.get("team") or "(팀 모름)"))
    # 읽은 범위 (팀별)
    teams = collections.OrderedDict()
    for nm, p in new.items():
        tm = team_of(nm, p); a = teams.setdefault(tm, dict(team=tm, n=0, mm=[0.0] * len(MON), prev=[0.0] * len(MON), T=[0.0] * len(MON)))
        a["n"] += 1
        for i in range(len(MON)): a["mm"][i] += p["q"][i]
    for nm, p in old.items():
        tm = team_of(nm, p)
        if tm in teams:
            for i in range(len(MON)): teams[tm]["prev"][i] += p["q"][i]
    if tgt:
        for nm, x in tgt.items():
            if x["team"] in teams:
                for i in range(len(MON)): teams[x["team"]]["T"][i] += x["T"][i]
    for a in teams.values():
        a["mm"] = [round(v, 2) for v in a["mm"]]; a["prev"] = [round(v, 2) for v in a["prev"]]; a["T"] = [round(v, 2) for v in a["T"]]
        a["rate"] = [round(m / T * 100, 1) if T > 0.005 else None for m, T in zip(a["mm"], a["T"])]
    res["read"] = list(teams.values())
    res["months"] = MON
    # 빨강: 꼭 확인
    for nm, p in new.items():
        if tgt is not None:
            x = tgt.get(nm)
            if not x: res["red"].append(f"{nm} — 가동대상 명단에 없는 사람인데 {MON[0][:-1]}~12월 계획 {sum(p['q']):.2f}MM (퇴사·전출·이름 오타 확인)")
            else:
                over = [f"{MON[i]} 계획 {p['q'][i]:.2f} > 가동대상 {x['T'][i]:.2f}" for i in range(len(MON)) if p["q"][i] > x["T"][i] + 0.005]
                if over: res["red"].append(f"{nm} ({x['team']}) — " + " · ".join(over) + " (퇴사·휴직·전출 후 계획이 남아 있음 → 가동대상만큼만 반영됨)")
        big = [f"{MON[i]} {p['q'][i]:.2f}" for i in range(len(MON)) if p["q"][i] > 1.0001]
        if big: res["red"].append(f"{nm} — 1인 월 1.00 초과: " + " · ".join(big) + " (1.00으로 맞춰 반영됨)")
    for a in res["read"]:
        hi = [f"{MON[i]} {r:.1f}%" for i, r in enumerate(a["rate"]) if r is not None and r > 100.05]
        if hi: res["red"].append(f"{a['team']} — 팀 가동률 100% 초과: " + " · ".join(hi))
    # 비교는 이 파일이 읽은 팀 안에서만 (하반기 총괄과 비교할 때 다른 부서까지 섞이지 않게)
    old = collections.OrderedDict((nm, p) for nm, p in old.items() if team_of(nm, p) in teams)
    keep = {n for c_, n in getattr(plan, "SOLD_KEEP", set()) if c_ == corp}
    # 노랑: 참고
    gone = [nm for nm in old if nm not in new and _bn(nm) not in keep and sum(old[nm]["q"]) > 0.005]
    if gone: res["yellow"].append("지금 파일엔 계획이 있는데 새 파일에 없는 사람: " + ", ".join(gone[:30]) + (f" 외 {len(gone)-30}명" if len(gone) > 30 else ""))
    if tgt is not None:
        listed0 = getattr(plan, "PRESENT", {}).get(path, set())   # 파일에 이름은 있음 (대기·미투입 행)
        _px = getattr(plan, "PRESENT_X", {}).get(path, set())
        def _is_listed(nm):
            b_ = _bn(nm)
            if b_ not in listed0: return False
            c_ = _dup.get(b_)
            if not c_ or not _px: return True
            for g2, tm, lab in c_:          # 동명이인: 사번 또는 팀이 같은 사람만 "파일에 있음"
                if lab == nm:
                    return any(n_ == b_ and ((g_ is not None and g_ == g2) or (_norm_t(t_) and _norm_t(t_) == _norm_t(tm))) for n_, g_, t_ in _px)
            return True
        class _L:
            def __contains__(self, k): return _is_listed(k)
        listed = _L()
        miss = [nm for nm, x in tgt.items() if x["team"] in teams and sum(x["T"]) > 0.005 and nm not in new and _bn(nm) not in keep and nm not in listed]
        if miss: res["yellow"].append("읽은 팀의 가동대상인데 새 파일에 없는 사람 (대기로 계산될 수 있음): " + ", ".join(miss[:30]))
        idle = [nm for nm, x in tgt.items() if x["team"] in teams and sum(x["T"]) > 0.005 and nm not in new and nm in listed]
        if idle: res["yellow"].append("파일에 대기(미투입)로 적힌 사람: " + ", ".join(idle[:30]))
    else:
        res["yellow"].append("아직 재계산한 적이 없어 가동대상과의 대조는 생략했습니다.")
    for nm in list(new) + [g for g in old if g not in new]:
        a = [round(v, 2) for v in new.get(nm, {"q": [0] * len(MON)})["q"]]; b = [round(v, 2) for v in old.get(nm, {"q": [0] * len(MON)})["q"]]
        ni = (new.get(nm) or {}).get("items", {}); oi = (old.get(nm) or {}).get("items", {})
        items = []
        for k in list(oi) + [k for k in ni if k not in oi]:
            o_ = [round(v, 2) for v in oi.get(k, [0.0] * len(MON))]; n_ = [round(v, 2) for v in ni.get(k, [0.0] * len(MON))]
            if any(abs(x - y) > 0.005 for x, y in zip(o_, n_)): items.append(dict(kind=k[0], pj=((new.get(nm) or {}).get("nm", {}).get(k) or (old.get(nm) or {}).get("nm", {}).get(k) or k[1]), old=o_, new=n_))
        if not items: continue   # 합계도 항목도 그대로
        T = [round(v, 2) for v in tgt[nm]["T"]] if tgt and nm in tgt else None
        idle_o = [round(max(0.0, t - x), 2) for t, x in zip(T, b)] if T else None
        idle_n = [round(max(0.0, t - x), 2) for t, x in zip(T, a)] if T else None
        # 한 줄 요약: 월별로 무엇이 바뀌었는지 (대기 → 이행 등)
        summ = []
        for i, m in enumerate(MON):
            parts = []
            if idle_o and abs(idle_o[i] - idle_n[i]) > 0.005: parts.append(f"대기 {idle_o[i]:.2f}→{idle_n[i]:.2f}")
            for it in items:
                if abs(it["old"][i] - it["new"][i]) > 0.005: parts.append(f"{it['kind']} {it['pj'][:24]} {it['old'][i]:.2f}→{it['new'][i]:.2f}")
            if parts: summ.append(f"{m}: " + " · ".join(parts))
        res["changes"].append(dict(name=nm, team=team_of(nm, new.get(nm) or old.get(nm)), new=a, old=b, items=items, T=T, idle_old=idle_o, idle_new=idle_n, summary=summ))
    if role: res["prev_name"] = next((f"{x['orig']} ({x['src']})" for x in used if x["role"] == role), "")
    else: res["prev_name"] = next((f"{d['orig']} ({d['src']})" for d in dept_files if d["path"] == prev_path), next((f"{x['orig']} ({x['src']})" + (" · 하반기 총괄" if x["role"] == "plan_hb2" else "") for x in used if x["role"] == res.get("prev_role", "plan_hb2")), ""))
    return res

if __name__ == "__main__":
    storage, uid = sys.argv[1], int(sys.argv[2])
    out = os.path.join(storage, "previews"); os.makedirs(out, exist_ok=True)
    try: res = main(storage, uid)
    except Exception as e:
        res = dict(id=uid, error=f"파일을 읽지 못했습니다 — 양식(시트·열 이름)이 바뀌었는지 확인해 주세요 ({type(e).__name__}: {e})", trace=traceback.format_exc()[-2000:], read=[], red=[], yellow=[], changes=[])
    json.dump(res, open(os.path.join(out, f"{uid}.json"), "w", encoding="utf-8"), ensure_ascii=False)
