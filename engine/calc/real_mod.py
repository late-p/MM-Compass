# 실데이터 반영: 연간 대시보드(01~04) + 주간 리포트 '9월 실적 확정' — v4_extra 네임스페이스에 exec
import sys as _sys, json as _json, math as _math
_sys.path.insert(0, __import__('cfg').CALC)
import importlib as _il, real_data as _rd
_il.reload(_rd)
RT = _rd.tree()
_cf = __import__('cfg')
CUR = _cf.CI          # 당월 index
CM, PM = _cf.CUR, _cf.CUR - 1   # 당월 · 전월 (1~12)
ASOF = _cf.WEEK.get("asof") or ""
CONF = _cf.ACTM       # 실적 확정 월 수 (그 다음 달부터 예상 음영)
RQ = _cf.R(CM)        # 당월~12월 표기
RA = _cf.R(1, CONF)   # 실적 구간 표기
RP = _cf.R(CONF + 1) if CONF < 12 else ""   # 예상 구간 표기
_ST_D = f"({_cf.WEEK.get('stats_date')})" if _cf.WEEK.get('stats_date') else ""
PROV_TXT = (f" · {', '.join(f'{m}월' for m in _cf.PROV)}은 SOLD 마감 전이라 투입계획 기준 잠정" if _cf.PROV else "")

def _rng(series_list, floor_to=10, cap=100):
    vals = [v for s in series_list for v in s if v is not None]
    lo = max(0, _math.floor(min(vals) / floor_to) * floor_to - (floor_to if min(vals) % floor_to < 2 else 0))
    hi = max(cap, _math.ceil(max(vals) / floor_to) * floor_to)
    step = 10 if hi - lo <= 50 else 20
    ticks = tuple(range(int(lo), int(hi) + 1, step))
    if ticks[-1] != hi: ticks = ticks + (int(hi),)
    return lo, hi, ticks

def _mini(title, d, extra="", attrs="", sub=None, rng=None):
    u, g = d["u"], d["g"]; dd = (u[CUR] or 0) - (u[CUR-1] or 0)
    lo, hi, tk = rng or (30, 100, (40, 70, 100))
    sub = sub or f'가동대상 {d["T"][CUR]:.2f}MM · 연간 가동 {d["yu"]:.2f}% · 가득 {d["yg"]:.2f}%'
    arrow = "▲" if dd > 0.004 else ("▼" if dd < -0.004 else "–")
    cls = "rise" if dd > 0.004 else ("fall" if dd < -0.004 else "")
    return f'''<div class="mini" {attrs}><div class="mh"><b>{title}</b><span class="cur num"><em>{CM}월</em><strong>{u[CUR]:.2f}%</strong><i class="{cls}">{arrow}{abs(dd):.2f}</i></span></div>
      {line_chart([("가득률", C2, g), ("가동률", C1, u)], MON, W=300, H=176, ymin=lo, ymax=hi, ticks=tk, est_from=CONF, mini=True, label_every=3, aria=title+" 월별 가득률·가동률", cur=CUR)}
      <div class="mf num">{sub}</div>{extra}</div>'''

def _teams_flat(h):
    out = []
    for di, dv in enumerate(h["divs"]):
        for ti, t in enumerate(dv["teams"]):
            out.append((dv["name"], t, di, ti))
    return out

# ---- ORG (04 표 상세) ----
ORG = {}
_HKEYS = []
for ci, c in enumerate(RT["corps"]):
    for hi_, h in enumerate(c["hqs"]):
        hk = f"c{ci}h{hi_}"; _HKEYS.append((hk, h))
        path_h = c["name"]
        ORG[hk] = dict(name=h["name"], path=path_h, **{k: h["d"][k] for k in ("T", "ex", "pr", "rd", "idle", "u", "g", "yu", "yg")})
        for di, dv in enumerate(h["divs"]):
            if dv["name"] != "(직속)":
                ORG[f"{hk}d{di}"] = dict(name=dv["name"], path=f'{c["name"]} › {h["name"]}', **{k: dv["d"][k] for k in ("T", "ex", "pr", "rd", "idle", "u", "g", "yu", "yg")})
            for ti, t in enumerate(dv["teams"]):
                p = f'{c["name"]} › {h["name"]}' + ("" if dv["name"] == "(직속)" else f' › {dv["name"]}')
                ORG[f"{hk}d{di}t{ti}"] = dict(name=t["name"], path=p, **{k: t["d"][k] for k in ("T", "ex", "pr", "rd", "idle", "u", "g", "yu", "yg")})
ORG_JSON = _json.dumps(ORG, ensure_ascii=False)
ORG_JS = ORG_JS.replace("function f1(v){return v.toFixed(2)}", "function f1(v){return v==null?'—':v.toFixed(2)}").replace(
    "${line('가동률',o.u,true,'rate')}${line('가득률',o.g,true,'rate')}",
    "${line('가득률',o.g,true,'rate',o.yg)}${line('가동률',o.u,true,'rate',o.yu)}").replace(
    "const line=(lab,arr,rate,cls)=>`<tr class=\"${cls||''}\"><td class=\"l\">${lab}</td>${arr.map((v,i)=>`<td${est(i)}>${rate?f1(v)+'%':f1(v)}</td>`).join('')}<td class=\"strong\">${rate?f1(arr.reduce((a,b)=>a+b,0)/12)+'%':f1(arr.reduce((a,b)=>a+b,0))}</td></tr>`;",
    "const line=(lab,arr,rate,cls,yr)=>`<tr class=\"${cls||''}\"><td class=\"l\">${lab}</td>${arr.map((v,i)=>`<td${est(i)}>${rate?f1(v)+'%':f1(v)}</td>`).join('')}<td class=\"strong\">${rate?f1(yr)+'%':f1(arr.reduce((a,b)=>a+b,0))}</td></tr>`;").replace(
    "월별 실적 (MM) · 회색 음영 = 예상 · 파란 테두리 = 당월", "월별 실적 (MM) · 회색 음영 = 예상 · 파란 테두리 = 당월 · 연간 율 = 1~12월 MM 누계 기준")
ORG_JS = ORG_JS.replace("rate?f1(v)+'%':f1(v)", "rate?(v==null?'—':f1(v)+'%'):f1(v)")
assert "o.yu" in ORG_JS and "yr)=>" in ORG_JS

def annual_table_rows(mcells):
    rows = ""; hidx = 0
    for ci, c in enumerate(RT["corps"]):
        rows += f'<tr class="sub"><td class="l">{c["name"]}</td>{mcells(c["d"]["u"])}<td class="strong">{c["d"]["yu"]:.2f}</td></tr>'
        for hi_, h in enumerate(c["hqs"]):
            hk = f"c{ci}h{hi_}"; hid = f"{ci}_{hi_}"
            rows += f'<tr class="org hq" data-key="{hk}" data-hq="{hid}" tabindex="0"><td class="l"><span class="tw"></span>{h["name"]}</td>{mcells(h["d"]["u"])}<td class="strong">{h["d"]["yu"]:.2f}</td></tr>'
            for di, dv in enumerate(h["divs"]):
                if dv["name"] != "(직속)":
                    rows += f'<tr class="org dv" data-key="{hk}d{di}" data-parent="{hid}" tabindex="0" hidden><td class="l">{dv["name"]}</td>{mcells(dv["d"]["u"])}<td class="strong">{dv["d"]["yu"]:.2f}</td></tr>'
                for ti, t in enumerate(dv["teams"]):
                    cls = "dv" if dv["name"] == "(직속)" else "tm"
                    rows += f'<tr class="org {cls}" data-key="{hk}d{di}t{ti}" data-parent="{hid}" tabindex="0" hidden><td class="l">{t["name"]}</td>{mcells(t["d"]["u"])}<td>{t["d"]["yu"]:.2f}</td></tr>'
    return rows

def annual_view(ic):
    D = RT["d"]
    LG = legend([("가득률", C2), ("가동률", C1)])
    lo, hi, tk = _rng([D["u"], D["g"]])
    main_chart = line_chart([("가득률", C2, D["g"]), ("가동률", C1, D["u"])], MON, ymin=lo, ymax=hi, ticks=tk, est_from=CONF, cur=CUR, aria="2026년 전사 월별 가득률·가동률 추이")
    crng = _rng([c["d"][k] for c in RT["corps"] for k in ("u", "g")])
    corp_cards = ""
    for c in RT["corps"]:
        d = c["d"]
        corp_cards += f'''<div class="chart-card corp-card"><div class="ch"><b>{c["name"]}</b><span class="num muted">{CM}월 가동대상 {d["T"][CUR]:.2f}MM · 연간 가동 {d["yu"]:.2f}% · 가득 {d["yg"]:.2f}%</span></div>
          {line_chart([("가득률", C2, d["g"]), ("가동률", C1, d["u"])], MON, W=640, H=280, ymin=crng[0], ymax=crng[1], ticks=crng[2], est_from=CONF, cur=CUR, aria=c["name"]+" 월별 가득률·가동률")}</div>'''
    hrng = _rng([h["d"][k] for c in RT["corps"] for h in c["hqs"] for k in ("u", "g")])
    corp_blocks, panels = "", ""
    for ci, c in enumerate(RT["corps"]):
        minis = ""
        for hi_, h in enumerate(c["hqs"]):
            key = f"hq{ci}_{hi_}"; d = h["d"]; tl = _teams_flat(h)
            minis += _mini(h["name"], d, extra='<div class="more">팀별 현황 보기 ›</div>',
                           attrs=f'data-hq="{key}" tabindex="0" role="button" aria-expanded="false"',
                           sub=f'{c["name"]} · 가동대상 {d["T"][CUR]:.2f}MM · 연간 가동 {d["yu"]:.2f}% · 가득 {d["yg"]:.2f}%', rng=hrng)
            trng = _rng([t["d"][k] for _, t, _, _ in tl for k in ("u", "g")])
            tminis, trows = "", ""
            for dvn, t, di_, ti_ in tl:
                td = t["d"]
                tminis += _mini(t["name"], td, rng=trng, attrs=f'data-org="c{ci}h{hi_}d{di_}t{ti_}" tabindex="0" role="button" aria-pressed="false"', extra='<div class="more">월별 실적 보기 ›</div>', sub=(f'{dvn} · ' if dvn != "(직속)" and not t["name"].startswith(dvn) else "") + f'가동대상 {td["T"][CUR]:.2f}MM · 연간 가동 {td["yu"]:.2f}%')
                dvl = "" if dvn == "(직속)" or t["name"].startswith(dvn) else f'<span class="muted">{dvn} › </span>'
                P = lambda v: "—" if v is None else f"{v:.2f}%"
                cc = lambda _i: ("es" if _i > CUR else ("cm" if _i == CUR else ""))
                trows += (f'<tr class="tp-u"><td class="l" rowspan="2">{dvl}{t["name"]}</td><td rowspan="2">{td["T"][CUR]:.2f} MM</td><td class="k">가동</td>'
                          + "".join(f'<td class="{cc(i)}">{P(v)}</td>' for i, v in enumerate(td["u"])) + f'<td class="strong">{td["yu"]:.2f}%</td></tr>'
                          + f'<tr class="tp-g"><td class="k">가득</td>' + "".join(f'<td class="{cc(i)}">{P(v)}</td>' for i, v in enumerate(td["g"])) + f'<td class="strong">{td["yg"]:.2f}%</td></tr>')
            panels += f'''<div class="team-panel" id="{key}" hidden>
          <div class="tp-head"><b>{h["name"]}</b> 팀별 현황 <span class="muted">· {c["name"]} · 팀 {len(tl)}개</span><button class="tbtn tp-close" data-close>닫기 ✕</button></div>
          <div class="minis tm-minis">{tminis}</div>
          <div class="tp-detail"><p class="tp-empty">팀 카드를 누르면 그 팀의 1~12월 실적(가동대상 · 이행 · 제안 · R&amp;D · 대기 · 가득률 · 가동률)이 여기에 표시됩니다.</p></div>
          <details class="tp-all"><summary>전체 팀 비교표 보기 (가득률 · 가동률 1~12월)</summary>
          <div class="scroll"><table class="tp-tab"><thead><tr><th class="l">사업부 › 팀</th><th>가동대상<br><small>{CM}월</small></th><th>구분</th>{"".join(f'<th class="{("es" if i > CUR else ("cm" if i == CUR else ""))}">{m}{"<small>당월</small>" if i == CUR else ("<small>예상</small>" if i > CUR else "")}</th>' for i, m in enumerate(MON))}<th>연간</th></tr></thead><tbody>{trows}</tbody></table></div></details>
        </div>'''
        corp_blocks += f'''<div class="corp-block"><h4 class="corp-h">{c["name"]}<span class="num">본부 {len(c["hqs"])}개 · 연간 가동 {c["d"]["yu"]:.2f}% · {CM}월 {c["d"]["u"][CUR]:.2f}%</span></h4>
          <div class="minis hq-minis">{minis}</div></div>'''
    def mcells(vals, tag="td"):
        return "".join(f'<{tag} class="{("est" + (" cm" if i == CUR else "")) if i >= CONF else ""}">{"—" if v is None else f"{v:.2f}"}</{tag}>' for i, v in enumerate(vals))
    head2 = "".join(f'<th class="{("est" + (" cm" if i == CUR else "")) if i >= CONF else ""}">{m}{"<small>당월</small>" if i == CUR else ""}</th>' for i, m in enumerate(MON))
    rows = annual_table_rows(mcells)
    foot = f'<tr><td class="l">전체</td>{mcells(D["u"])}<td>{D["yu"]:.2f}</td></tr>'
    return f'''
<div class="view" id="v-annual">
  <div class="titlebar"><h1>연간 대시보드</h1><span class="chip solid">2026년</span><span class="chip">{RA} 실적 · {RP} 예상</span>
    <div class="meta2">{RA} = SOLD 실적 · {RP} = 부서별 투입계획(인력롤링){PROV_TXT} · 최종 반영 <b>{ASOF}</b></div></div>
  <section class="card-sec" id="a1">
    <div class="sec-head"><span class="sec-no">01</span><h2>전사 총괄</h2><span class="sub">아이티센클로잇 + 아이티센엔텍(ENT사업본부) · 연간 = 1~12월 MM 누계 기준(실적+예상)</span></div>
    <div class="kpis num k4">
      <div class="kpi"><div class="label">연간 가득률</div><div class="value">{D["yg"]:.2f}<small>%</small></div><div class="ytd">{RA} 실적 {D["cg"]:.2f}%</div>{_curl(D, "g")}</div>
      <div class="kpi alt"><div class="label">가득률<i>비매출 모수 제외</i></div><div class="value">{D["yn"]:.2f}<small>%</small></div><div class="ytd">{RA} 실적 {D["cn"]:.2f}% · 임원 MM 모수 제외</div>{_curl(D, "gn")}</div>
      <div class="kpi"><div class="label">연간 가동률</div><div class="value">{D["yu"]:.2f}<small>%</small></div><div class="ytd">{RA} 실적 {D["cu"]:.2f}%</div>{_curl(D, "u")}</div>
      <div class="kpi"><div class="label">실적 확정</div><div class="value">{CONF}<small>/ 12개월</small></div><div class="ytd">{f'다음 확정: {CONF + 1}월 실적 (SOLD 마감 후)' if CONF < 12 else '연간 확정'}</div></div>
    </div>
    <div class="chart-card"><div class="ch"><b>월별 가득률 · 가동률</b>{LG}</div>{main_chart}</div>
  </section>
  <section class="card-sec" id="a2">
    <div class="sec-head"><span class="sec-no">02</span><h2>법인별 연간 흐름</h2><span class="sub">아이티센엔텍은 ENT사업본부만 집계</span>{LG}</div>
    <div class="corp-grid">{corp_cards}</div>
  </section>
  <section class="card-sec" id="a3">
    <div class="sec-head"><span class="sec-no">03</span><h2>본부별 연간 추이</h2><span class="sub">본부 카드 동일 눈금({hrng[0]}~{hrng[1]}%) · ▲▼ = {PM}월 대비 {CM}월 가동률 · 본부를 누르면 팀별 현황</span>{LG}</div>
    {corp_blocks}
    <div class="tp-hint muted">본부 카드를 누르면 그 본부 바로 아래에 팀별 현황이 펼쳐집니다.</div>
    {panels}
  </section>
  <section class="card-sec" id="a4">
    <div class="sec-head"><span class="sec-no">04</span><h2>2026년 본부별 가동률</h2><span class="sub">단위 % · 회색 음영 = 예상 · 파란 테두리 = 당월({CM}월) · 본부를 누르면 사업부·팀, 조직을 누르면 월별 실적(MM)</span></div>
    <div class="scroll"><table class="mtab">
      <thead><tr><th class="l" rowspan="2">법인 / 본부</th><th colspan="{CONF}" class="grp-c">실적</th><th colspan="{12-CONF}" class="grp-e">예상</th><th rowspan="2">연간</th></tr>
      <tr>{head2}</tr></thead>
      <tbody>{rows}</tbody><tfoot>{foot}</tfoot></table></div>
  </section>
</div>
'''

def confirm_section():
    D = RT["d"]; m = CUR - 1
    inp = lambda d: d["ex"][m] + d["pr"][m] + d["rd"][m]
    rows = []
    for c in RT["corps"]:
        d = c["d"]
        rows.append(f'<tr class="sub"><td class="l">{c["name"]} 소계</td><td>{d["T"][m]:.2f} MM</td><td>{inp(d):.2f} MM</td><td>{d["ex"][m]:.2f} MM</td><td>{d["pr"][m]:.2f} MM</td><td>{d["rd"][m]:.2f} MM</td><td>{d["idle"][m]:.2f} MM</td><td>{d["g"][m]:.2f}%</td><td>{d["u"][m]:.2f}%</td></tr>')
        for h in c["hqs"]:
            d = h["d"]
            rows.append(f'<tr class="child"><td class="l">{h["name"]}</td><td>{d["T"][m]:.2f} MM</td><td>{inp(d):.2f} MM</td><td>{d["ex"][m]:.2f} MM</td><td>{d["pr"][m]:.2f} MM</td><td>{d["rd"][m]:.2f} MM</td><td>{d["idle"][m]:.2f} MM</td><td>{d["g"][m]:.2f}%</td><td>{d["u"][m]:.2f}%</td></tr>')
    return f'''
  <!-- 0 -->
  <section id="s0" class="card-sec confirm">
   <details class="conf-all" open>
    <summary class="sec-head"><span class="sec-no lock">전월</span><h2>{PM}월 실적 {'확정' if PM <= CONF else '(잠정)'}</h2><i class=\"ca-chev\" aria-hidden=\"true\"></i></summary>
    <div class="kpis num">
      <div class="kpi fix"><div class="label">가득률</div><div class="value">{D["g"][m]:.2f}<small>%</small></div><div class="kg">{_ag(D["g"][m], None, _GC, 150, True)}</div></div>
      <div class="kpi fix alt"><div class="label">가득률<i>비매출 모수 제외</i></div><div class="value">{D["gn"][m]:.2f}<small>%</small></div><div class="kg">{_ag(D["gn"][m], None, _GC, 150, True)}</div></div>
      <div class="kpi fix"><div class="label">가동률</div><div class="value">{D["u"][m]:.2f}<small>%</small></div><div class="kg">{_ag(D["u"][m], None, _UC, 150, True)}</div></div>
      <div class="kpi fix"><div class="label">투입 MM</div><div class="value">{inp(D):.2f}<small>/ {D["T"][m]:.2f}</small></div></div>
      <div class="kpi fix"><div class="label">대기 MM</div><div class="value">{D["idle"][m]:.2f}<small>MM · {sum(1 for p in PP.values() if p["idle"][m] > 0.005)}명</small></div><div class="ytd"><span class="kgo">대기 인력 상세 보기 ›</span></div></div>
    </div>
    <details class="conf-more">
      <summary>본부별 {PM}월 실적 보기</summary>
      <style>.conf-more table{{table-layout:fixed;width:100%}}.conf-more th.l,.conf-more td.l{{width:170px}}.conf-more th,.conf-more td{{white-space:nowrap}}</style>
      <div class="scroll"><table>
        <thead><tr><th class="l">법인 / 본부</th><th>가동대상</th><th>투입</th><th>이행</th><th>제안</th><th>R&amp;D·내부과제</th><th>대기</th><th>가득률</th><th>가동률</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
        <tfoot><tr><td class="l">전체</td><td>{D["T"][m]:.2f} MM</td><td>{inp(D):.2f} MM</td><td>{D["ex"][m]:.2f} MM</td><td>{D["pr"][m]:.2f} MM</td><td>{D["rd"][m]:.2f} MM</td><td>{D["idle"][m]:.2f} MM</td><td>{D["g"][m]:.2f}%</td><td>{D["u"][m]:.2f}%</td></tr></tfoot>
      </table></div>
    </details>
   </details>
  </section>
'''

# =====================================================================
# v17: 04 가득률 표 · 비매출 모수 명단 · 주간 리포트 실데이터 · 업로드 화면 실조직
# =====================================================================
import real_people as _rp
_il.reload(_rp)
PP = _rp.people()
import stats1008 as _st1008
IDLE_CHECK = _st1008.apply_people(PP) if __import__('cfg').IN.get('stats') else []   # 대기 = 통계 파일 대기 명단 (통계 실적 마지막 달 ~ 12월)
EV = _rp.events()
CORP_KEY = {"아이티센클로잇": "cloit", "아이티센엔텍": "entec"}
P9, P10 = CUR - 1, CUR   # 전월 · 당월 index
def _curl(D, k):
    """연간 카드: 현 시점(당월) 값과 전월 대비"""
    c, p = D[k][CUR], D[k][CUR - 1]; d = c - p
    ar = "▲" if d > 0.004 else ("▼" if d < -0.004 else "–")
    return f'<div class="ytd cur-now">{CM}월 현재 <b>{c:.2f}%</b> <span>(전월 {ar} {abs(d):.2f}%p)</span></div>'
def _inp(d, m): return d["ex"][m] + d["pr"][m] + d["rd"][m]
def _dlt(a, b, unit="%p", good_up=True, nd=2):
    d = (b or 0) - (a or 0)
    if abs(d) < 0.005: return "flat", f"±0.00{unit}"
    up = d > 0
    cls = "rise" if up else "fall"
    return cls, f'{"+" if up else "−"}{abs(d):.{nd}f}{unit}'
def _pc(v): return "—" if v is None else f"{v:.2f}%"

# ---- 비매출 모수(임원) 명단 ----
_ex = {}
for _p in PP.values():
    if not _p["exec"]: continue
    k_ = (_p["corp"], _p["name"])
    if k_ in _ex:
        q_ = _ex[k_]; q_["T"] = [a_ + b_ for a_, b_ in zip(q_["T"], _p["T"])]
    else:
        _ex[k_] = dict(_p); _ex[k_]["T"] = list(_p["T"])
EXECS = sorted(_ex.values(), key=lambda p: (p["corp"] != "아이티센클로잇", p["hq"], p["org"], p["name"]))
RDP = sorted([p for p in PP.values() if not p["exec"] and sum(p["rd"]) > 0.005], key=lambda p: (p["corp"] != "아이티센클로잇", p["hq"], p["org"], p["name"]))
def _rd_names(p):
    import re as _r3
    best = {}   # 공백·기호만 다른 같은 과제는 하나로 (코드가 더 긴 쪽 이름을 씀 — 05 현황과 같은 기준)
    for (c_, n, k), mm in p["projs"].items():
        if k != "R&D·내부과제" or sum(mm) <= 0.005: continue
        key = _r3.sub(r"[\s_\-\(\)\[\]]", "", str(n)).lower()
        if key not in best or len(str(c_)) > len(str(best[key][0])): best[key] = (c_, n.strip())
    return " · ".join(v[1] for v in best.values())
_NP_TG = '''<div class="np-tg" role="group" aria-label="법인 선택"><button type="button" data-c="" aria-pressed="true">전체</button><button type="button" data-c="아이티센클로잇" aria-pressed="false">아이티센클로잇</button><button type="button" data-c="아이티센엔텍" aria-pressed="false">아이티센엔텍</button></div>
      <script>(function(){var d=document.currentScript.closest('details');d.querySelectorAll('.np-tg button').forEach(function(b){b.onclick=function(e){e.preventDefault();var c=b.dataset.c;d.querySelectorAll('.np-tg button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false')});d.querySelectorAll('tbody tr[data-c]').forEach(function(r){r.hidden=!!c&&r.dataset.c!==c});var f=d.querySelector('tfoot');if(f)f.hidden=!!c;window.dispatchEvent(new Event('resize'))}})})()</script>'''

def np_list_html(open_=False):  # NPCORP_V1
    head = "".join(f'<th class="{("est" + (" cm" if i == CUR else "")) if i >= CONF else ""}">{m}</th>' for i, m in enumerate(MON))
    cc = lambda i: ("est" + (" cm" if i == CUR else "")) if i >= CONF else ""
    trs = ""; tot = [0.0] * 12; sums = []
    for cn in ("아이티센클로잇", "아이티센엔텍"):
        ex = [p for p in EXECS if p["corp"] == cn]; rd = [p for p in RDP if p["corp"] == cn]
        if not ex and not rd: continue
        te = [sum(p["T"][i] for p in ex) for i in range(12)]; tr_ = [sum(p["rd"][i] for p in rd) for i in range(12)]
        tc = [a_ + b_ for a_, b_ in zip(te, tr_)]; tot = [a_ + b_ for a_, b_ in zip(tot, tc)]
        sums.append(f'<b>{cn}</b> 사업부장 {len(ex)}명 + R&amp;D·내부과제 {len(rd)}명 · {CM}월 {tc[CUR]:.2f}MM')
        trs += f'<tr class="np-grp" data-c="{cn}"><td class="l" colspan="16">■ {cn} · 사업부장 {len(ex)}명 + R&amp;D·내부과제 {len(rd)}명</td></tr>'
        for p in ex:
            cells = "".join(f'<td class="{cc(i)}">{v:.2f}</td>' for i, v in enumerate(p["T"]))
            trs += f'<tr data-c="{cn}"><td class="l">{p["name"]}</td><td class="l np-so">{p["hq"]}{"" if p["org"] == p["hq"] else "<br>" + p["org"]}</td><td class="l">{p["직급"] or "사업부장"}</td>{cells}<td class="strong">{sum(p["T"]):.2f}</td></tr>'
        for p in rd:
            cells = "".join(f'<td class="{cc(i)}{" zero" if v <= 0.005 else ""}">{v:.2f}</td>' for i, v in enumerate(p["rd"]))
            trs += f'<tr data-c="{cn}"><td class="l">{p["name"]}</td><td class="l np-so">{p["hq"]}{"" if p["org"] == p["hq"] else "<br>" + p["org"]}</td><td class="l np-pj" title="{_rd_names(p)}">{('<span class="np-rk">' + p["직급"] + '</span><br>') if p.get("직급") else ""}<span class="np-pn">{_rd_names(p)}</span></td>{cells}<td class="strong">{sum(p["rd"]):.2f}</td></tr>'
        trs += f'<tr class="np-sub" data-c="{cn}"><td class="l" colspan="3">{cn} 소계 (사업부장 + R&amp;D·내부과제)</td>' + "".join(f'<td class="{cc(i)}">{v:.2f}</td>' for i, v in enumerate(tc)) + f'<td>{sum(tc):.2f}</td></tr>'
    foot = "".join(f'<td class="{cc(i)}">{v:.2f}</td>' for i, v in enumerate(tot))
    return f'''<details class="np-list"{" open" if open_ else ""}><summary>비매출 모수 명단 · {" · ".join(sums)}</summary>
      {_NP_TG}
      <div class="scroll"><table class="np-tab"><thead><tr><th class="l">성명</th><th class="l">소속</th><th class="l">직급 / 과제</th>{head}<th>합계</th></tr></thead>
      <tbody>{trs}</tbody><tfoot><tr><td class="l" colspan="3">비매출 모수 합계 (MM) · 두 법인</td>{foot}<td>{sum(tot):.2f}</td></tr></tfoot></table></div>
      <div class="note">비매출 모수 = 사업부장(아이티센클로잇 3자리 · 아이티센엔텍 ENT 2명) 가동대상MM + R&amp;D·내부과제 투입MM(사업유형 비매출 포함) · 비매출 모수 제외 가득률 = (이행 − 사업부장 이행) ÷ (가동대상 − 비매출 모수) · 26년 가동가득 통계 1번 시트와 같은 방식 · 사업부장 명단은 기준정보에서 관리</div></details>'''

# ---- 04 표: 가득률 · % 표기 ----
def annual_table_rows(mcells):
    rows = ""
    for ci, c in enumerate(RT["corps"]):
        rows += f'<tr class="sub"><td class="l">{c["name"]}</td>{mcells(c["d"]["g"])}<td class="strong">{c["d"]["yg"]:.2f}%</td></tr>'
        for hi_, h in enumerate(c["hqs"]):
            hk = f"c{ci}h{hi_}"; hid = f"{ci}_{hi_}"
            rows += f'<tr class="org hq" data-key="{hk}" data-hq="{hid}" tabindex="0"><td class="l"><span class="tw"></span>{h["name"]}</td>{mcells(h["d"]["g"])}<td class="strong">{h["d"]["yg"]:.2f}%</td></tr>'
            for di, dv in enumerate(h["divs"]):
                if dv["name"] != "(직속)":
                    rows += f'<tr class="org dv" data-key="{hk}d{di}" data-parent="{hid}" tabindex="0" hidden><td class="l">{dv["name"]}</td>{mcells(dv["d"]["g"])}<td class="strong">{dv["d"]["yg"]:.2f}%</td></tr>'
                for ti, t in enumerate(dv["teams"]):
                    cls = "dv" if dv["name"] == "(직속)" else "tm"
                    rows += f'<tr class="org {cls}" data-key="{hk}d{di}t{ti}" data-parent="{hid}" tabindex="0" hidden><td class="l">{t["name"]}</td>{mcells(t["d"]["g"])}<td>{t["d"]["yg"]:.2f}%</td></tr>'
    return rows

_annual_v16 = annual_view
def annual_view(ic):
    html_ = _annual_v16(ic)
    D = RT["d"]
    # 04: 가득률 + % 단위
    def _mc(i): return ("est" + (" cm" if i == CUR else "")) if i >= CONF else ("old" if i < CUR - 1 else "")   # old = 접기 대상(1~전전월)
    def pcell(vals):
        return "".join(f'<td class="{_mc(i)}">{_pc(v)}</td>' for i, v in enumerate(vals))
    a = html_.index('<section class="card-sec" id="a4">'); b = html_.index("</section>", a) + len("</section>")
    head2 = "".join(f'<th class="{_mc(i)}">{m}{"<small>당월</small>" if i == CUR else ""}</th>' for i, m in enumerate(MON))
    _fold = (f'<span class="tools" style="margin-left:auto"><button data-afold="{CONF}" data-old="{CUR - 1}" aria-pressed="false">1~{CUR - 1}월 접기</button></span>' if CUR > 1 else '')
    _fcss = ('<style>#a4.fold-old th.old,#a4.fold-old td.old{display:none}#a4.fold-old table.mtab{width:100%!important;min-width:0!important;table-layout:auto!important}#a4.fold-old table.mtab col{width:auto!important}#a4 .tools button[aria-pressed=true]{background:#EEF4FF;border-color:#1F5FD0;color:#1F5FD0}</style>'
             '<script>document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("button[data-afold]");if(!b)return;var s=document.getElementById("a4");'
             'var f=s.classList.toggle("fold-old");b.setAttribute("aria-pressed",f?"true":"false");var n=+b.dataset.old;'
             'b.textContent=f?"1~"+n+"월 펼치기":"1~"+n+"월 접기";var g=s.querySelector("th.grp-c");if(g)g.colSpan=+b.dataset.afold-(f?n:0);window.dispatchEvent(new Event("resize"))});'
             'window.__ca_after=function(){document.querySelectorAll("#s4 details.grp[open] .scroll>table").forEach(function(t){var cg=t.querySelector(":scope>colgroup[data-auto]");if(!cg||!t.offsetParent)return;var cols=cg.children,k=cols.length-2,sc=t.parentNode,cs=getComputedStyle(sc),avail=sc.clientWidth-(parseFloat(cs.paddingLeft)||0)-(parseFloat(cs.paddingRight)||0),sum=0;for(var i=0;i<cols.length;i++){if(getComputedStyle(cols[i]).display==="none")continue;sum+=parseFloat(cols[i].style.width)||0}if(sum<avail-4){cols[k].style.width=((parseFloat(cols[k].style.width)||0)+avail-sum)+"px";t.style.width=avail+"px";t.style.minWidth=avail+"px"}})};</script>')
    a4 = f'''<section class="card-sec" id="a4">{_fcss}
    <div class="sec-head"><span class="sec-no">04</span><h2>2026년 본부별 가득률</h2><span class="sub">가득률(%) = 이행 ÷ 가동대상 · 회색 음영 = 예상 · 파란 테두리 = 당월({CM}월) · 본부를 누르면 사업부·팀, 조직을 누르면 월별 실적(MM)</span>{_fold}</div>
    <div class="scroll"><table class="mtab">
      <thead><tr><th class="l" rowspan="2">법인 / 본부</th><th colspan="{CONF}" class="grp-c">실적 · 가득률(%)</th><th colspan="{12-CONF}" class="grp-e">예상 · 가득률(%)</th><th rowspan="2">연간<br><small>가득률</small></th></tr>
      <tr>{head2}</tr></thead>
      <tbody>{annual_table_rows(pcell)}</tbody><tfoot><tr><td class="l">전체</td>{pcell(D["g"])}<td>{D["yg"]:.2f}%</td></tr></tfoot></table></div>
  </section>'''
    html_ = html_[:a] + a4 + html_[b:]
    # 01: 비매출 모수 명단
    k = html_.index('<div class="chart-card"><div class="ch"><b>월별 가득률')
    html_ = html_[:k] + np_list_html() + "\n    " + html_[k:]
    html_ = html_.replace(f"{RA} 실적 " + f'{D["cn"]:.2f}% · 임원 MM 모수 제외', f"{RA} 실적 " + f'{D["cn"]:.2f}% · 아래 명단 참고')
    return html_

# ---- 주간: 본부별 가동률·가득률 (전월 확정 → 당월 현재) ----
PCONF = "확정" if PM <= CONF else "잠정"
# 비교 기준: 같은 달 직전 게시 주차(전주) > 전월 잠정이면 전월 마지막 게시 주차 > 전월 실적 (회의용과 같은 규칙)
def _ldj(p):
    try: return _json.load(open(p, encoding="utf-8"))
    except Exception: return None
PREVS = _ldj(_cf.WEEK["prev_summary"]) if _cf.WEEK.get("prev_summary") else None
PMBS = None if PREVS else (_ldj(_cf.WEEK["pm_summary"]) if _cf.WEEK.get("pm_summary") else None)
BSRC = PREVS or PMBS
PML = f"{PM}월 {PCONF}"                                   # 전월 (확정/잠정)
BLA = (PREVS.get("short") or "전주") if PREVS else ((PMBS.get("short") or f"{PM}월 마지막 보고") if PMBS else PML)
def _K(*a): return "|".join(a)
def _bv(key, d, f):
    """비교 기준 값 — 전주(또는 전월 마지막 주차) 게시본에 없으면 None"""
    if BSRC: return (BSRC["nodes"].get(key) or {}).get(f)
    return _inp(d, P9) if f == "inp" else d[f][P9]
def _dlt2(a, b, unit="%p", good_up=True):
    return ("", "—") if a is None or b is None else _dlt(a, b, unit, good_up)

import gauge as _GA
def _ag(cur, base, col, size, big=False):
    """관리자용 계기판 — 진한 바늘 = 현재, 흰 원 = 비교 기준, 옅은 부채꼴 = 변화량"""
    import math as _m
    P = lambda cx, cy, a, r: (cx + r * _m.sin(_m.radians(a)), cy - r * _m.cos(_m.radians(a)))
    cx = cy = 60
    def ring(a0, a1, ro, ri, c, op=1):
        x0, y0 = P(cx, cy, a0, ro); x1, y1 = P(cx, cy, a1, ro); x2, y2 = P(cx, cy, a1, ri); x3, y3 = P(cx, cy, a0, ri)
        return f'<path d="M{x0:.1f},{y0:.1f} A{ro},{ro} 0 0 1 {x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f} A{ri},{ri} 0 0 0 {x3:.1f},{y3:.1f}Z" fill="{c}" fill-opacity="{op}"/>'
    a = lambda v: (min(max(v, 60), 100) - 60) / 40 * 180 - 90
    if cur is not None and cur > 100.005: cur = 100
    o = ""
    for lo, hi, c in ((60, _GA.LOW, "#EFA9A2"), (_GA.LOW, _GA.TARGET, "#F5DC8A"), (_GA.TARGET, 100, "#8FD8AE")):
        o += ring(a(lo) + (1.2 if lo > 60 else 0), a(hi) - (1.2 if hi < 100 else 0), 54, 44, c)
    if base is not None and cur is not None:
        a0, a1 = sorted((a(base), a(cur)))
        if a1 - a0 > 0.3: o += ring(a0, a1, 44, 14, "#B42335" if cur > base else "#2E8B60", .22)
        mx, my = P(cx, cy, a(base), 50)
        o += f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{4.5 if big else 5.5}" fill="#fff" stroke="#6b7684" stroke-width="2.2"/>'
    if cur is not None:
        t = P(cx, cy, a(cur), 48); l = P(cx, cy, a(cur) - 90, 4.5); r = P(cx, cy, a(cur) + 90, 4.5); b = P(cx, cy, a(cur) + 180, 6)
        o += f'<polygon points="{t[0]:.1f},{t[1]:.1f} {l[0]:.1f},{l[1]:.1f} {b[0]:.1f},{b[1]:.1f} {r[0]:.1f},{r[1]:.1f}" fill="{col}"/><circle cx="{cx}" cy="{cy}" r="4" fill="#0F2942"/>'
    if big:
        for sv, rr, dy in ((60, 54, 9), (_GA.LOW, 63, 3), (_GA.TARGET, 63, 3), (100, 54, 9)):
            lx, ly = P(cx, cy, a(sv), rr)
            if sv in (60, 100): ly = cy + 9
            else: ly += dy
            o += f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="7" font-weight="600" fill="#7B8AA0" text-anchor="middle">{sv:g}</text>'
        return f'<svg viewBox="-2 -6 124 82" width="{size}" aria-hidden="true">{o}</svg>'
    return f'<svg viewBox="2 4 116 66" width="{size}" aria-hidden="true">{o}</svg>'
def _two(a, b): return f'<span class="two"><span class="bw">{a}</span><span class="bm">{b}</span></span>'
def _gg(cur, b1, b2, col, size, big=False):
    if cur is None: return ""
    return _two(_ag(cur, b1, col, size, big), _ag(cur, b2, col, size, big))
_UC, _GC = "#2A5A9B", "#C77B2B"
WEEKLY_HEAD = (f'<thead><tr><th class="l" rowspan="2">법인 / 본부</th><th rowspan="2">가동대상<br><small>{CM}월</small></th><th colspan="4" class="gh gh-g">가득률 <small>(이행)</small></th>'
               '<th rowspan="2" class="gsep"></th><th colspan="4" class="gh">가동률 <small>(이행 · 제안 · R&amp;D·내부과제)</small></th></tr>'
               f'<tr><th class="gc">{_two(BLA, PML)}</th><th class="gc">{CM}월 현재</th><th class="gc">증감</th><th class="mg gc"></th><th>{_two(BLA, PML)}</th><th>{CM}월 현재</th><th>증감</th><th class="mg"></th></tr></thead>')
def weekly_rows():
    def row(cls, name, d, key, attrs=""):
        bu, bg = _bv(key, d, "u"), _bv(key, d, "g")
        mu, mg = d["u"][P9], d["g"][P9]                      # 전월 기준 (전월 토글)
        c1, s1 = _dlt2(bu, d["u"][P10]); c2, s2 = _dlt2(bg, d["g"][P10])
        k1, t1 = _dlt2(mu, d["u"][P10]); k2, t2 = _dlt2(mg, d["g"][P10])
        dU = _two('<span class="%s">%s</span>' % (c1, s1), '<span class="%s">%s</span>' % (k1, t1))
        dG = _two('<span class="%s">%s</span>' % (c2, s2), '<span class="%s">%s</span>' % (k2, t2))
        mini = "tm" not in cls.split()                      # 팀 줄은 숫자만 (사업부까지 계기판)
        gu = _gg(d["u"][P10], bu, mu, _UC, 42) if mini else ""
        gg_ = _gg(d["g"][P10], bg, mg, _GC, 42) if mini else ""
        return (f'<tr class="{cls}" {attrs}><td class="l">{name}</td><td>{d["T"][P10]:.2f} MM</td><td class="gc">{_two(_pc(bg), _pc(mg))}</td><td class="gc">{_pc(d["g"][P10])}</td><td>{dG}</td><td class="mg gc">{gg_}</td>'
                f'<td class="gsep"></td><td>{_two(_pc(bu), _pc(mu))}</td><td>{_pc(d["u"][P10])}</td><td>{dU}</td><td class="mg">{gu}</td></tr>')
    out = []
    for ci, c in enumerate(RT["corps"]):
        cn = c["name"]
        out.append(row("sub", f'{cn} 소계', c["d"], _K("c", cn)))
        for hi_, h in enumerate(c["hqs"]):
            hid = f"w{ci}_{hi_}"
            out.append(row("org hq child", f'<span class="tw"></span>{h["name"]}', h["d"], _K("h", cn, h["name"]), f'data-hq="{hid}" tabindex="0"'))
            for dv in h["divs"]:
                if dv["name"] != "(직속)":
                    out.append(row("org dv", dv["name"], dv["d"], _K("d", cn, h["name"], dv["name"]), f'data-parent="{hid}" hidden'))
                for t in dv["teams"]:
                    if dv["name"] != "(직속)" and len(dv["teams"]) == 1 and t["name"] == dv["name"]: continue   # 사업부와 이름이 같은 단일 팀은 중복 줄이므로 생략
                    out.append(row("org dv" if dv["name"] == "(직속)" else "org tm", t["name"], t["d"], _K("t", cn, h["name"], dv["name"], t["raw"]), f'data-parent="{hid}" hidden'))
    return "\n".join(out), row("", "전체", RT["d"], "ALL")

SCR = "<script>(function(){var s=document.getElementById('s1');if(!s)return;var bs=s.querySelectorAll('.bt button');bs.forEach(function(b){b.addEventListener('click',function(){bs.forEach(function(x){x.classList.toggle('on',x===b)});s.classList.toggle('vm',b.dataset.b==='m')})})})();</script>"

def _s1():
    D = RT["d"]
    idle_people = [p for p in PP.values() if p["idle"][P10] > 0.005]
    streak = [p for p in PP.values() if all(p["idle"][m] > 0.005 for m in range(CUR, 12))]
    np10 = D["np"][P10]
    def line(lab, base, cur, unit, good_up):
        if base is None: return f'<div class="cmp"><span>{lab} —</span></div>'
        c, s = _dlt(base, cur, unit, good_up)
        arrow = "▲" if cur > base + 0.004 else ("▼" if cur < base - 0.004 else "–")
        return f'<div class="cmp"><span>{lab} {base:.2f}{"%" if unit == "%p" else ""}</span><span class="{c}">{arrow} {s.lstrip("+−")}</span></div>'
    def kpi(label, val, small, ytd, f, unit="%p", good_up=True, alt=False):
        cur = _inp(D, P10) if f == "inp" else D[f][P10]
        pm = _inp(D, P9) if f == "inp" else D[f][P9]
        sub = line(BLA, _bv("ALL", D, f), cur, unit, good_up)
        if BSRC: sub += line(PML, pm, cur, unit, good_up).replace('class="cmp"', 'class="cmp cmp2"', 1)   # 전주 기준일 때 전월 대비도 작게
        gz = ""
        if f in ("u", "g", "gn"):
            gz = f'<div class="kg">{_gg(cur, _bv("ALL", D, f), pm, _UC if f == "u" else _GC, 150, True)}</div>'
        return (f'<div class="kpi{" alt" if alt else ""}"><div class="label">{label}</div><div class="value">{val}<small>{small}</small></div>{gz}'
                f'<div class="ytd">{ytd}</div>{sub}</div>')
    k = "".join([
        kpi("가득률", f'{D["g"][P10]:.2f}', "%", f'연간 누적 {D["yg"]:.2f}% (실적+예상)', "g"),
        kpi("가득률<i>비매출 모수 제외</i>", f'{D["gn"][P10]:.2f}', "%", f'비매출 모수 {np10:.2f}MM 제외<br>사업부장 + R&amp;D·내부과제', "gn", alt=True),
        kpi("가동률", f'{D["u"][P10]:.2f}', "%", f'연간 누적 {D["yu"]:.2f}% (실적+예상)', "u"),
        kpi("투입 MM", f'{_inp(D, P10):.2f}', f'/ {D["T"][P10]:.2f}', f'가동대상 {D["T"][P10]:.2f}MM ({PM}월 {D["T"][P9]:.2f})', "inp", unit=""),
        kpi("대기 MM", f'{D["idle"][P10]:.2f}', f'MM · {len(idle_people)}명', f'12월까지 연속 대기 예정 {len(streak)}명', "idle", unit="", good_up=False),
    ])
    comp = ""
    for lab, key in (("이행 (가득)", "ex"), ("제안", "pr"), ("R&amp;D·내부과제", "rd"), ("대기", "idle")):
        a_, b_ = _bv("ALL", D, key), D[key][P10]
        c, s = _dlt2(a_, b_, "", key != "idle")
        m_ = D[key][P9]; c3, s3 = _dlt2(m_, b_, "", key != "idle")
        dd = _two('<span class="%s">%s</span>' % (c, s), '<span class="%s">%s</span>' % (c3, s3))
        b1_ = "—" if a_ is None else "%.2f MM" % a_
        comp += (f'<tr><td class="l">{lab}</td><td>{_two(b1_, "%.2f MM" % m_)}</td><td>{b_:.2f} MM</td>'
                 f'<td>{dd}</td><td>{b_/D["T"][P10]*100:.2f}%</td></tr>')
    bT = _bv("ALL", D, "T")
    rows, total = weekly_rows()
    tf1 = _two("—" if bT is None else "%.2f MM" % bT, "%.2f MM" % D["T"][P9])
    tf2 = _two(_dlt2(bT, D["T"][P10], "")[1], _dlt2(D["T"][P9], D["T"][P10], "")[1])
    TOG = (f'<span class="bt" role="group"><button type="button" data-b="w" class="on">{"전주" if PREVS else "직전 보고"} 대비</button><button type="button" data-b="m">전월 대비</button></span>'
           if BSRC else "")
    return f'''<section id="s1" class="card-sec">
    <div class="sec-head"><span class="sec-no">01</span><h2>{_cf.WEEK.get("short", "")} 실적 · {BLA} 대비</h2>{TOG}<span class="sub">당월({CM}월) = 부서별 투입계획(인력롤링) 기준 · 그 달 첫 보고는 전월과 비교, 다음 보고부터 전주(직전 게시 주차) 대비{f" · KPI 아래 작은 글씨 = {PML} 대비" if BSRC else ""}</span></div>
    <div class="kpis num">{k}</div>
    <div class="row2 wide">
      <div class="panel">
        <h3>본부별 가득률 · 가동률 증감 <span>본부를 누르면 사업부·팀</span></h3>
        <div class="scroll"><table>{WEEKLY_HEAD}<tbody>
{rows}
        </tbody><tfoot>{total}</tfoot></table></div>
      </div>
      <div class="panel">
        <h3>투입 구성 비교 <span>{CM}월 가동대상 {D["T"][P10]:.2f}MM 기준</span></h3>
        <div class="scroll"><table>
          <thead><tr><th class="l">구분</th><th>{_two(BLA, PML)}</th><th>{CM}월 현재</th><th>증감</th><th>{CM}월 비중</th></tr></thead>
          <tbody>{comp}</tbody>
          <tfoot><tr><td class="l">가동대상</td><td>{tf1}</td><td>{D["T"][P10]:.2f} MM</td><td>{tf2}</td><td>100.00%</td></tr></tfoot>
        </table></div>
        <div class="note">비중 = {CM}월 가동대상MM 대비 · 증감 색: 상승 = 빨강, 하락 = 초록{" · 전주 게시본에 없던 항목은 —" if BSRC else ""}</div>
      </div>
    </div>
  {SCR}
  </section>'''

# ---- 02 인사 변동 (당월) ----
# ---- 직무 드롭다운: 같은 직무인데 표기가 갈린 것은 하나로 묶음 (표시 이름 기준) ----
JOB_MAP = {"개발": "개발 · Programming", "programming": "개발 · Programming", "pm": "PM"}
def job_canon(j):
    j = (j or "").strip()
    return JOB_MAP.get(j.lower(), j)
def job_key(j):
    import html as _h
    return _h.escape(re.sub(r"\s+", "", job_canon(j)).lower(), quote=True)
def job_select(el_id, persons, style="width:170px"):
    import html as _h
    seen = {}
    for p in persons:
        c = job_canon(p.get("직무"))
        if c: seen.setdefault(job_key(p.get("직무")), c)
    opts = "".join(f'<option value="{_h.escape(v)}"></option>' for k, v in sorted(seen.items(), key=lambda kv: kv[1].lower()))
    return (f'<input id="{el_id}" type="search" list="{el_id}L" placeholder="직무 검색 · 선택" autocomplete="off" style="{style}" title="입력해서 검색하거나 화살표로 목록에서 고르세요 · 지우면 전체">'
            f'<datalist id="{el_id}L"><option value="전체 직무"></option>{opts}</datalist>')


def _org_cell(h, esc=lambda x: x):
    """인사 변동 소속 칸: 전배처럼 '이전 → 이후'가 길면 화살표까지만 윗줄, 이후 소속은 아랫줄 전체"""
    full = f'{h["corp"]} · {h["org"]}'
    def nw(t):   # 법인·사업부·팀 이름은 중간에 끊기지 않게 한 덩어리로 (줄은 ' · ' 자리에서만 바뀜)
        return " · ".join(f'<span class="nw">{esc(x)}</span>' for x in t.split(" · "))
    if " → " in full and len(full) > 60:
        a, b = full.split(" → ", 1)
        return nw(a) + " →<br>" + nw(b)
    if " → " in full:
        return " → ".join(nw(x) for x in full.split(" → "))
    return nw(full)
def _org_br(s):
    """사업부 이름 'AX Consulting & Eng 사업부'는 Eng 앞에서 줄바꿈"""
    return s.replace("&amp; Eng 사업부", "&amp;<br>Eng 사업부").replace("& Eng 사업부", "&<br>Eng 사업부")
def _merge_events():
    out = []; used = set()
    for i, e in enumerate(EV):
        if i in used: continue
        if e["kind"] in ("전입", "전출"):
            j = next((j for j, f in enumerate(EV) if j != i and j not in used and f["name"] == e["name"] and f["date"] == e["date"] and {f["kind"], e["kind"]} == {"전입", "전출"}), None)
            if j is not None:
                used.update({i, j}); src = e if e["kind"] == "전출" else EV[j]; dst = EV[j] if e["kind"] == "전출" else e
                same_hq = src["org"].split(" · ")[0] == dst["org"].split(" · ")[0]
                if src["corp"] != dst["corp"]:
                    out.append(dict(kind="전적", corp=dst["corp"], name=e["name"], org=f'{src["corp"]} · {src["org"]} → {dst["corp"]} · {dst["org"]}', date=e["date"],
                                    imp="법인 간 이동 (전체 합계 변동 없음)", delta=0.0, note="법인 이동"))
                    continue
                out.append(dict(kind="전배", corp=e["corp"], name=e["name"], org=f'{src["org"]} → {dst["org"]}', date=e["date"],
                                imp="본부 내 이동 (합계 변동 없음)" if same_hq else "본부 간 이동 (법인 합계 변동 없음)", delta=0.0, note="부서 이동"))
                continue
        used.add(i)
        if e["kind"] == "입사": imp, dlt, note = f'+{e["m10"]:.2f} MM ({CM}월)', e["m10"], ""
        elif e["kind"] == "퇴사": imp, dlt, note = f'−{max(e["m9"] - e["m10"], 0):.2f} MM ({CM}월)', -max(e["m9"] - e["m10"], 0), ""
        elif e["kind"] == "휴직": imp, dlt, note = f'−{max(e["m9"] - e["m10"], 0):.2f} MM ({CM}월)', -max(e["m9"] - e["m10"], 0), "휴직 " + e["note"]
        elif e["kind"] == "복직": imp, dlt, note = f'+{max(e["m10"] - e["m9"], 0):.2f} MM ({CM}월)', max(e["m10"] - e["m9"], 0), e["note"]
        elif e["kind"] == "전입": imp, dlt, note = "타 조직에서 전입", 0.0, "이전 소속: 집계 대상 밖"
        else: imp, dlt, note = "타 조직으로 전출", 0.0, ""
        out.append(dict(kind=e["kind"], corp=e["corp"], name=e["name"], org=e["org"], date=e["date"], imp=imp, delta=dlt, note=note))
    return out
_RANK = {}
for _p in PP.values():
    if _p.get("직급"): _RANK.setdefault((_p["corp"], _p["name"]), _p["직급"])
def _rank(corp, name): return _RANK.get((corp, name), "—")
_JOB = {}
for _p in PP.values():
    if _p.get("직무"): _JOB.setdefault((_p["corp"], _p["name"]), _p["직무"])
def _job(corp, name): return _JOB.get((corp, name), "—")
HRE = _merge_events()
PILL = {"입사": "p-ok", "복직": "p-ok", "퇴사": "p-warn", "휴직": "p-mid", "전배": "p-mid", "전입": "p-mid", "전출": "p-mid", "전적": "p-mid"}
def hr_section():
    from collections import Counter
    c = Counter(h["kind"] for h in HRE)
    keys = ["입사", "퇴사", "휴직", "복직", "전적", "전배", "전입"]
    chips = "".join(f'<span class="hrc hrc-f" role="button" tabindex="0" data-k="{k}" title="누르면 {k} 인원만 표시 (다시 누르면 전체)"><b>{c.get(k, 0)}</b>{k}</span>' for k in keys)
    plus = sum(h["delta"] for h in HRE if h["delta"] > 0); minus = -sum(h["delta"] for h in HRE if h["delta"] < 0)
    trs = "".join(f'<tr data-k="{h["kind"]}"><td class="c"><span class="pill {PILL.get(h["kind"], "p-mid")}">{h["kind"]}</span></td><td class="l">{h["name"]}<span class="newtag">신규</span></td>'
                  f'<td class="l">{_org_cell(h)}</td><td class="l">{_job(h["corp"], h["name"])}</td><td class="l">{_rank(h["corp"], h["name"])}</td><td class="c">{h["date"]:%m.%d}</td><td class="l">{"" if "변동 없음" in h["imp"] else h["imp"]}</td><td class="l muted">{h["note"]}</td></tr>' for h in HRE)
    if not trs: trs = f'<tr><td class="c muted" colspan="8">{CM}월 등록된 인사 변동 없음</td></tr>'
    return f'''
  <!-- HR -->
  <section id="s2" class="card-sec hr-sec" data-state="month">
    <div class="sec-head"><span class="sec-no">02</span><h2>인사 변동</h2>
      <span class="hr-badge b-month">월초 · {CM}월 전체 표시</span><span class="hr-badge b-none">전주 대비 변동 없음</span><span class="hr-badge b-new">전주 대비 신규 0건</span>
      <span class="sub">기준: {CM}월(당월) 발령 · 가동인력목록 · 통합인사정보(AX) · 계약직(일반) 제외</span></div>
    <div class="demo-switch"><em>디자인 확인용</em><button data-s="month" aria-pressed="true">월초</button><button data-s="none" aria-pressed="false">변동 없음</button><button data-s="new" aria-pressed="false">변동 있음</button></div>
    <div class="hr-sum num">{chips}<span class="hr-net">{CM}월 가동대상 영향 합계 <b>{plus - minus:+.2f} MM</b> <em>(입사·복직 +{plus:.2f} / 퇴사·휴직 −{minus:.2f})</em></span></div>
    <details class="hr-list" open><summary><span class="t-open">명단 접기</span><span class="t-closed">{CM}월 명단 보기 ({len(HRE)}건)</span></summary>
    <div class="panel scroll" data-search><table>
      <thead><tr><th class="c">유형</th><th class="l">성명</th><th class="l">소속 (변동)</th><th class="l">직무</th><th class="l">직급</th><th class="c">적용일</th><th class="l">가동대상MM 영향</th><th class="l">비고</th></tr></thead>
      <tbody>{trs}</tbody>
    </table></div></details>
  </section>
'''

# ---- 03 조직별 특이사항 (본부 · 전월 대비 ±3%p) ----
def _s3():
    cols = ""
    for c in RT["corps"]:
        items = []
        for h in c["hqs"]:
            d = h["d"]; bu = _bv(_K("h", c["name"], h["name"]), d, "u")
            if bu is None: bu = d["u"][P9]
            dd = (d["u"][P10] or 0) - (bu or 0)
            if abs(dd) < 3: continue
            cls, s = _dlt(bu, d["u"][P10])
            # 하락 원인: 9월 대비 투입이 줄어든 팀 상위 2개
            def _ti(dv, t):
                v = _bv(_K("t", c["name"], h["name"], dv["name"], t["raw"]), t["d"], "idle")
                return t["d"]["idle"][P9] if v is None else v
            chg = sorted(((t["name"], t["d"]["idle"][P10] - _ti(dv, t)) for dv in h["divs"] for t in dv["teams"]), key=lambda x: -x[1] if dd < 0 else x[1])
            why = " · ".join(f'{n} {v:+.2f}MM' for n, v in chg[:3] if abs(v) > 0.005)
            items.append(f'''<div class="issue {"b-rise" if dd > 0 else "b-fall"}">
            <div class="top-line"><span class="path">{h["name"]}</span><span class="auto">자동 감지 · {"상승" if dd > 0 else "하락"}</span></div>
            <div class="fig num"><div>{CM}월 가동률<b>{d["u"][P10]:.2f}%</b></div><div>{BLA} 대비<b class="{cls}">{s}</b></div><div>{CM}월 대기<b>{d["idle"][P10]:.2f} MM</b></div></div>
            <p class="auto-why"><em>{"대기 증가" if dd < 0 else "대기 감소"}</em>{why or "—"}</p>
            <p class="nocm"><em>코멘트</em>입력된 코멘트 없음</p></div>''')
        cols += f'<div class="corp-col"><h4>{c["name"]} <span>{len(items)}건</span></h4><div class="stack">{"".join(items) or "<p class=muted>해당 없음</p>"}</div></div>'
    return f'''<section id="s3" class="card-sec">
    <div class="sec-head"><span class="sec-no">03</span><h2>조직별 특이사항</h2><span class="sub">본부 가동률이 {BLA} 대비 ±3.00%p 이상 변한 경우 자동 표시 · {CM}월 이후는 미등록 투입계획이 있으면 낮게 보일 수 있음</span></div>
    <div class="corp-cols">{cols}</div>
  </section>'''

# ---- 04 대기 인력 (인원별) ----
def _next_plan(p, months=tuple(range(CUR, 12)), kinds=None, exclude_rd=False):
    out = []
    for (code, name, kind), mm in p["projs"].items():
        if exclude_rd and kind == "R&D·내부과제": continue
        ms = [m for m in months if mm[m] > 0.005]
        if ms: out.append((ms[0], name, kind))
    out.sort()
    return out
def _leave_map():
    import pandas as _pd
    t, i, MC, attr, cl, et, hd = _rp.load()
    d8 = lambda x: (None if _pd.isna(x) or x in ("", None) else _pd.to_datetime(x).date())
    L = {}
    def put(corp, g, kind, a, b):
        cur = L.get((corp, g))
        if cur is None or (a and (cur[1] is None or a > cur[1])): L[(corp, g)] = (kind, a, b)
    for df, corp in ((cl, "아이티센클로잇"), (et, "아이티센엔텍")):
        for _, r in df.iterrows():
            g = _rp.gid(r["그룹사번"])
            if str(r.get("재직여부")) == "퇴사" and d8(r.get("퇴사일")): put(corp, g, "퇴사", d8(r.get("퇴사일")), None)
            elif d8(r.get("휴직시작일")): put(corp, g, "휴직", d8(r.get("휴직시작일")), d8(r.get("휴직종료일")))
    for _, r in hd.iterrows():
        g = _rp.gid(r["그룹사번"])
        if str(r.get("재직여부")) == "퇴사" and d8(r.get("퇴사일")): put("아이티센클로잇", g, "퇴사", d8(r.get("퇴사일")), None)
        elif d8(r.get("휴직시작일")): put("아이티센클로잇", g, "휴직", d8(r.get("휴직시작일")), d8(r.get("휴직종료일")))
    return L
LEAVE = _leave_map()
def _leave_rows():
    """휴직 인원 전체 (당월 이후 휴직 중) — 통계 파일 재직현황(휴직) + 가동인력목록·인사정보, 복직일은 더 늦은 쪽(연장 반영)"""
    import datetime as _dt
    cur1 = _dt.date(2026, CUR + 1, 1)
    byname = {}
    for p in PP.values(): byname.setdefault(p["name"], []).append(p)
    def find(nm, tm=None):
        c = byname.get(nm, [])
        return next((p for p in c if tm and (p["tm"] == tm or p["org"] == tm)), c[0] if c else None)
    src = []
    try:
        if __import__("cfg").IN.get("stats"): src = _st1008.leave_sheet()
    except ImportError:
        src = _st1008.leave_sheet()
    except Exception:
        src = []
    ET_T = {"EM사업부", "MIS1팀", "MIS2팀", "MES팀", "복권사업팀"}
    rows = {}
    for r in src:
        p = find(r["name"], r["tm"]); key = (p["corp"], p["gid"]) if p else ("?", r["name"])
        end = r["end"]; lv = LEAVE.get(key) if p else None
        if lv and lv[0] == "휴직" and lv[2] and (end is None or lv[2] > end): end = lv[2]
        corp = p["corp"] if p else ("아이티센엔텍" if r["tm"] in ET_T or r["dv"] in ET_T else "아이티센클로잇")
        rows[key] = dict(corp=corp, name=r["name"], org=(p["org"] if p else r["tm"]), 직무=(p["직무"] if p and p.get("직무") else r["직무"]),
                         직급=(p["직급"] if p and p.get("직급") else r["직급"]), start=r["start"], end=end, note=r.get("note") or "",
                         T=(p["T"][CUR:12] if p else [0.0] * (12 - CUR)))
    for key, (k, a, b) in LEAVE.items():
        if k != "휴직" or key in rows: continue
        p = next((q for q in PP.values() if (q["corp"], q["gid"]) == key), None)
        if not p or (b and b < cur1): continue
        rows[key] = dict(corp=p["corp"], name=p["name"], org=p["org"], 직무=p.get("직무") or "", 직급=p.get("직급") or "", start=a, end=b, note="",
                         T=p["T"][CUR:12])
    out = [r for r in rows.values() if r["end"] is None or r["end"] >= cur1]
    order = {"아이티센클로잇": 0, "아이티센엔텍": 1}
    return sorted(out, key=lambda r: (order.get(r["corp"], 2), str(r["org"]), r["name"]))
LEAVE_ROWS = _leave_rows()
def leave_of(p):
    """현재(당월) 가동대상이 0이고 휴직·퇴사 기록이 있으면 (구분, 표시문구)"""
    if p["T"][CUR] > 0.005: return None
    x = LEAVE.get((p["corp"], p["gid"]))
    if not x: return None
    k, a, b = x
    if k == "퇴사": return ("퇴사", f"{a:%y.%m.%d} 퇴사")
    return ("휴직", f"휴직 {a:%y.%m.%d}~" + (f"{b:%y.%m.%d}" if b else ""))

def quit_txt(p):
    """퇴사 기록이 있으면 '퇴사(yy.mm.dd)' (당월 일부 근무한 사람도 포함) — 대기 비고의 '미정' 대신 표시"""
    x = LEAVE.get((p["corp"], p["gid"]))
    if x and x[0] == "퇴사": return f"퇴사({x[1]:%y.%m.%d})"
    return None

def quit_tag(p):
    """당월 일부 근무 후 퇴사한 사람의 이름 옆 표시문구 'yy.mm.dd 퇴사'"""
    x = LEAVE.get((p["corp"], p["gid"]))
    if x and x[0] == "퇴사": return f"{x[1]:%y.%m.%d} 퇴사"
    return None

def trans_note(p):  # TRN_V1
    """중간에 팀을 옮긴 사람: '9월 전배 · 이전팀 → 현재팀' (대기 인력 비고에 표시)"""
    tm = p.get("tmT") or {}
    if len(tm) <= 1: return ""
    seq = []
    for (h, d, t), T in tm.items():
        f0 = next((m for m in range(12) if T[m] > 0.005), None)
        if f0 is not None: seq.append((f0, _rp.org_label(h, d, t)))
    seq.sort()
    if len(seq) < 2: return ""
    return f"{seq[-1][0] + 1}월 전배 · " + " → ".join(n for _, n in seq)

def trn_html(p, style=""):
    n = trans_note(p)
    if not n: return ""
    n = n.replace("&", "&amp;").replace("<", "&lt;")
    return f'<div class="trn"{style} title="{n}">{n}</div>'

def split_people():
    """중간에 팀을 옮긴 사람(전배·전적 등)은 팀별로 나눠서 — 그 팀에 있던 달의 대기만 그 팀에 잡힘. 안 옮긴 사람은 그대로"""
    out = []
    for p in PP.values():
        tm = p.get("tmT") or {}
        if len(tm) <= 1: out.append(p); continue
        for (h, d, t), T in tm.items():
            q = dict(p); q["hq"], q["dv"], q["tm"] = h, d, t; q["org"] = _rp.org_label(h, d, t)
            q["idle"] = [round(p["idle"][m] * T[m] / p["T"][m], 4) if p["T"][m] > 0.005 else 0.0 for m in range(12)]
            q["T"] = list(T)
            if sum(q["idle"]) > 0.005: out.append(q)
    return out
MONTH_START = True   # 월 첫 주차: 전월(확정) 대기도 표시 대상
def _quiet(p):
    """기본 숨김 대상: 당월 대기 0 (월초에는 전월 대기도 0)"""
    if p["idle"][CUR] > 0.005: return False
    if MONTH_START and p["idle"][CUR - 1] > 0.005: return False
    return True

def _rq_txt(mem):
    return f" · {RQ} {sum(sum(p['idle'][CUR:12]) for p in mem):.2f}MM" if CM < 12 else ""
def _msum(L):
    """팀·본부 줄: 월별 대기 MM 합계를 아래 인원 표의 월 칸과 같은 자리에 (연간 합 포함)"""
    out = ""
    for i in range(12):
        v = sum(p["idle"][i] for p in L)
        out += f'<td class="msum {"old " if i < CUR - 1 else ""}{"conf" if i < CUR else ("cm" if i == CUR else "fut")}">{v:.2f}</td>'
    return out + f'<td class="msum strong">{sum(sum(p["idle"]) for p in L):.2f}</td>'
def _s4():
    groups = []
    for c in RT["corps"]:
        for h in c["hqs"]:
            ppl = [p for p in split_people() if p["corp"] == c["name"] and p["hq"] == h["name"] and sum(p["idle"]) > 0.005]
            if not ppl: continue
            groups.append((c["name"], h["name"], ppl))
    total_n = sum(len(g[2]) for g in groups)
    by_c = {cn: [p for g in groups if g[0] == cn for p in g[2]] for cn in ("아이티센클로잇", "아이티센엔텍")}
    def status(p):
        ms = p["idle"][CUR:12]; i0, iL = ms[0], ms[-1]   # 당월 · 12월 대기
        if p["exec"]: return ("비매출 모수", "p-mid")
        if sum(ms) <= 0.005: return (f"{CM}월 투입", "p-ok")
        if all(v > 0.005 for v in ms):
            if i0 >= 0.995: return ("미투입", "p-warn")
            return ("부분 투입", "p-mid")
        if i0 > 0.005 and iL <= 0.005: return ("투입 예정", "p-ok")
        if i0 <= 0.005: return ("종료 후 대기", "p-mid")
        return ("부분 투입", "p-mid")
    need = sum(1 for g in groups for p in g[2] if status(p)[0] == "미투입" and not leave_of(p))
    need_mm = sum(p["idle"][CUR] for g in groups for p in g[2] if status(p)[0] == "미투입" and not leave_of(p))
    html_g = ""
    for cn, hq, ppl in groups:
        n_need = sum(1 for p in ppl if status(p)[0] == "미투입")
        mm_need = sum(p["idle"][CUR] for p in ppl if status(p)[0] == "미투입" and not leave_of(p))
        def _row(p):
            st = status(p); ms = p["idle"][CUR:12]
            badge = '<span class="streak s3">연말까지</span>' if all(v > 0.005 for v in ms) and not p["exec"] else ""
            tag = '<span class="exec-tag">사업부장</span>' if p["exec"] else ""
            lv = leave_of(p)
            if not lv and quit_txt(p):   # 당월 일부 근무 후 퇴사: 상태도 '퇴사', 이름 옆에 퇴사일 표시 (합계·미투입 집계는 그대로)
                st = ("퇴사", "p-quit"); tag += f'<span class="leave-tag lt-quit">{quit_tag(p)}</span>'
            if lv: st = (lv[0], "p-quit" if lv[0] == "퇴사" else "p-leave"); tag += f'<span class="leave-tag {"lt-quit" if lv[0] == "퇴사" else "lt-leave"}">{lv[1]}</span>'
            cells = "".join(f'<td class="{"na " if p["T"][i] <= 0.005 else ("zero " if v <= 0.005 else "")}{"old " if i < CUR - 1 else ""}{"conf" if i < CUR else ("cm" if i == CUR else "fut")}">{"" if p["T"][i] <= 0.005 else "%.2f" % v}</td>' for i, v in enumerate(p["idle"]))
            plan = _next_plan(p)
            plan_s = (f'{plan[0][1]} ({MON[plan[0][0]]}~)' if plan[0][0] > CUR else plan[0][1]) + (f' 외 {len(plan)-1}건' if len(plan) > 1 else "") if plan else (quit_txt(p) or "미정")
            plan_t = " / ".join(n for _, n, _ in plan)
            return f'<tr{" data-leave=1" if lv else ""}{" data-cur0=1" if _quiet(p) else ""} data-name="{p["name"]}" data-job="{job_key(p["직무"])}"{" data-exec=1" if p["exec"] else ""} data-mon="{sum(1 for v in p["idle"][:CUR + 1] if v >= 0.5)}" data-h1="{sum(p["idle"][:CUR]):.4f}" data-hp="{p["idle"][CUR - 1]:.4f}" data-hc="{p["idle"][CUR]:.4f}" data-need="{(p["idle"][CUR] if st[0] == "미투입" and not lv else 0):.4f}" data-idle="{sum(p["idle"][CUR:12]):.4f}" data-year="{sum(p["idle"]):.4f}"><td class="l">{p["name"]} {tag}{badge}</td><td class="l">{p["org"]}</td><td class="l">{p["직무"] or "—"}</td><td class="l">{p["직급"] or "—"}</td>{cells}<td class="strong">{sum(p["idle"]):.2f}</td><td class="l plan" title="{plan_t}">{plan_s}{trn_html(p)}</td><td class="c"><span class="pill {st[1]}">{st[0]}</span></td></tr>'

        hnode = next(h for c in RT["corps"] if c["name"] == cn for h in c["hqs"] if h["name"] == hq)
        order = [(dv["name"], t["raw"], t["name"], dv["name"]) for dv in hnode["divs"] for t in dv["teams"]]
        trs = ""
        for dvn, tmr, tlabel, _ in order:
            mem = sorted([p for p in ppl if p["dv"] == dvn and p["tm"] == tmr], key=lambda p: p["name"])
            if not mem: continue
            path = tlabel if (dvn == "(직속)" or tlabel == dvn) else f'{dvn} › {tlabel}'
            trs += (f'<tbody class="tgrp"><tr class="tg-h" tabindex="0" role="button" aria-expanded="true"><td class="l" colspan="4"><i class="tg-chev" aria-hidden="true"></i><b>{path}</b><span>표시 <em class="tg-vis">{len(mem)}</em> / {len(mem)}명{f" (휴직·퇴사 {sum(1 for p in mem if leave_of(p))}명 포함)" if any(leave_of(p) for p in mem) else ""}</span></td>{_msum(mem)}<td class="l" colspan="2"></td></tr>'
                    + "".join(_row(p) for p in mem) + '</tbody>')
        left = [p for p in ppl if (p["dv"], p["tm"]) not in {(o[0], o[1]) for o in order}]
        if left:
            trs += '<tbody class="tgrp"><tr class="tg-h" tabindex="0" role="button" aria-expanded="true"><td class="l" colspan="4"><i class="tg-chev" aria-hidden="true"></i><b>기타</b></td>' + _msum(left) + '<td class="l" colspan="2"></td></tr>' + "".join(_row(p) for p in sorted(left, key=lambda p: p["name"])) + '</tbody>'
        html_g += f'''
<details class="grp" data-corp="{CORP_KEY[cn]}">
  <summary>
    <span class="g-name"><span class="corp-chip {CORP_KEY[cn]}">{cn}</span>{hq}</span>
    <span class="g-m"><em>{PM}·{CM}월 인원</em><b class="g-vis">{sum(1 for p in ppl if not _quiet(p))}명</b></span>
    <span class="g-m"><em>연간 이력</em><span class="gv gm-n">{len(ppl)}명</span></span>
    <span class="g-m"><em>1~{PM}월</em><span class="gv gm-h1">{sum(sum(p["idle"][:CUR]) for p in ppl):.2f} MM</span></span>
    <span class="g-m"><em>{PM}월</em><span class="gv gm-hp">{sum(p["idle"][CUR - 1] for p in ppl):.2f} MM</span></span>
    <span class="g-m g-cur"><em>{CM}월 · 당월 대기</em><span class="gv gm-hc">{sum(p["idle"][CUR] for p in ppl):.2f} MM</span></span>
    <span class="g-m" title="{CM}월~12월 내내 투입이 0인 인원의 {CM}월 대기 MM"><em>└ 연말까지 투입 없음</em><b class="gv gm-need {"warn-t" if mm_need else ""}">{mm_need:.2f} MM</b></span>
    <span class="chev" aria-hidden="true"></span>
  </summary>
  <div class="scroll"><table>
    <thead><tr><th class="l">성명</th><th class="l">소속</th><th class="l">직무</th><th class="l">직급</th>{"".join(f'<th class="{"old " if i < CUR - 1 else ""}{"conf" if i < CUR else ("cm" if i == CUR else "fut")}">{m}{"<br><small>당월</small>" if i == CUR else ""}</th>' for i, m in enumerate(MON))}<th>연간 합</th><th class="l">현재·예정 투입 프로젝트</th><th class="c">상태</th></tr></thead>
    <tbody class="hq-tot"><tr><td class="l" colspan="4"><b>{hq} 합계</b> <span>{len(ppl)}명</span></td>{_msum(ppl)}<td class="l" colspan="2"></td></tr></tbody>
    {trs}
  </table></div>
</details>'''
    sm = lambda L: sum(p["idle"][CUR] for p in L)
    s9 = lambda L: sum(p["idle"][CUR - 1] for p in L)
    n9 = lambda L: sum(1 for p in L if p["idle"][CUR - 1] > 0.005)
    return f'''<section id="s4" class="card-sec sec-3 detail fold-old">{_FOLD_CSS}{_SUM_CSS}
    <div class="sec-head"><span class="sec-no">04</span><h2>대기 인력 현황</h2><span class="sub">인원별 대기 = 가동대상MM − 투입MM · {RA} = 확정 실적{PROV_TXT} · {CM}월 = 당월{f' · {_cf.R(CM + 1)} = 투입계획 기준 대기 예정' if CM < 12 else ''} · 연간 대기가 있었던 인원 전체 · 본부 클릭 시 인원 표시 · 단위 MM</span></div>
    <div class="corp-sum num">
      <span class="cur-sum">{CM}월 당월 대기 합계 <b id="sc-all">{sm([p for g in groups for p in g[2]]):.2f}MM · {total_n}명</b></span>
      <span>아이티센클로잇 <b id="sc-cl">{sm(by_c["아이티센클로잇"]):.2f}MM · {len(by_c["아이티센클로잇"])}명</b></span>
      <span>아이티센엔텍 <b id="sc-et">{sm(by_c["아이티센엔텍"]):.2f}MM · {len(by_c["아이티센엔텍"])}명</b></span>
      <span title="{CM}월~12월 내내 투입이 0인 인원의 {CM}월 대기 MM">미투입 <b class="warn-t" id="sc-need">{need_mm:.2f} MM · {need}명</b></span>
      <span class="conf-sum">{PM}월(전월 확정) 대기 <b id="sc-conf">{s9([p for g in groups for p in g[2]]):.2f}MM · {n9([p for g in groups for p in g[2]])}명</b></span>
    </div>
    <div class="tabs" role="tablist" data-scope="idle">
      <button role="tab" aria-selected="true" data-f="all">전체</button>
      <button role="tab" aria-selected="false" data-f="cloit">아이티센클로잇</button>
      <button role="tab" aria-selected="false" data-f="entec">아이티센엔텍</button>
      <span class="tools">{f'<button data-fold="1" aria-pressed="false">1~{CUR - 1}월 펼치기</button>' if CUR > 1 else ''}<button data-act="csv">엑셀 다운로드</button><button data-act="open">모두 펼치기</button><button data-act="close">모두 접기</button></span>
    </div>
    <div class="sort-bar"><em>정렬</em><button data-sort="name" aria-pressed="true">이름순</button><button data-sort="idle" aria-pressed="false">{RQ} 대기 많은순</button><button data-sort="year" aria-pressed="false">연간 대기 많은순</button><label class="lv-toggle"><input type="checkbox" id="cur0Show"> {PM}월(전월)·{CM}월(당월) 대기 없는 인원도 표시</label><label class="lv-toggle"><input type="checkbox" id="lvShow" checked> 휴직·퇴사자 포함</label><label class="lv-toggle"><input type="checkbox" id="exShow" checked> 사업부장 포함</label><label class="lv-toggle">직무 {job_select("jobQ", [p for g in groups for p in g[2]])}</label><label class="lv-toggle">대기 기간 <select id="ldSel"><option value="0">전체</option><option value="1">누적 1개월 이상</option><option value="2">누적 2개월 이상</option><option value="3">누적 3개월 이상</option><option value="4">누적 4개월 이상</option><option value="5">누적 5개월 이상</option><option value="6">누적 6개월 이상</option></select></label><span class="grp-toggle"><em>팀 묶음</em><button data-g="open">모두 펼치기</button><button data-g="close">모두 접기</button></span></div>
    <div class="note st-legend">상태: <b>미투입</b> {RQ} 계속 대기 (투입 0) · 헤더의 「연말까지 투입 없음」 = 이 상태 인원의 {CM}월 대기 MM · <b>부분 투입</b> 투입은 있으나 1.00 미만{f' · <b>투입 예정</b> {CM}월 대기 후 12월엔 투입 · <b>종료 후 대기</b> {CM}월 투입, 이후 대기 예정' if CM < 12 else ''} · <b>{CM}월 투입</b> {PM}월 대기 후 {CM}월부터 투입 · <b>비매출 모수</b> 사업부장</div>
    <div class="note st-legend st-legend2"><span class="leave-tag lt-quit">퇴사</span> <span class="leave-tag lt-leave">휴직</span> {CM}월 가동대상 0 (휴직·퇴사 전 달의 대기는 실적이므로 합계에 포함)</div>
    <div id="idle" class="hide-cur0" data-search>{html_g}
    </div>
    {_leave_block()}
  </section>'''

def _leave_block():
    L = LEAVE_ROWS
    fd = lambda d: d.strftime("%y.%m.%d") if d else "—"
    trs = "".join(f'<tr><td class="l">{r["name"]} <span class="leave-tag lt-leave">휴직</span></td><td class="l">{r["corp"]}</td><td class="l">{r["org"]}</td>'
                  f'<td class="l">{r["직무"] or "—"}</td><td class="l">{r["직급"] or "—"}</td><td class="c">{fd(r["start"])}</td><td class="c">{fd(r["end"])}</td>'
                  + "".join(f'<td class="{"zero" if v <= 0.005 else ""}">{v:.2f}</td>' for v in r["T"]) + f'<td class="l muted">{r["note"]}</td></tr>' for r in L)
    return f'''<div class="lv-sec"><div class="lv-head"><h3>휴직 인원 <b>{len(L)}명</b></h3><span class="sub">당월 이후 휴직 중인 인원 전체 · 통계 파일 재직현황 + 가동인력목록 · 복직일은 더 늦은 쪽(연장) 기준 · 가동대상MM은 휴직 반영 값</span></div>
    <div class="scroll"><table class="lv-t"><thead><tr><th class="l">성명</th><th class="l">법인</th><th class="l">소속</th><th class="l">직무</th><th class="l">직급</th><th class="c">휴직 시작</th><th class="c">복직 예정</th>
    <th>{MON[CUR]}<br><small>가동대상</small></th>{''.join(f'<th>{MON[i]}</th>' for i in range(CUR + 1, 12))}<th class="l">비고</th></tr></thead><tbody>{trs or f'<tr><td colspan="{9 + 12 - CUR}">휴직 인원 없음</td></tr>'}</tbody></table></div></div>'''

# 본부·과제 요약 줄: 어느 줄이든 같은 칸 위치 (글자 길이와 상관없이 숫자 열이 세로로 맞게)
_SUM_CSS = ('<style>#s4 details.grp>summary{display:grid;grid-template-columns:minmax(210px,1.5fr) repeat(6,minmax(0,1fr)) 18px;gap:0 10px;flex-wrap:nowrap;align-items:center}'
            '#s5 details.grp>summary{display:grid;grid-template-columns:minmax(260px,2.4fr) minmax(0,1.2fr) repeat(3,minmax(0,.6fr)) 18px;gap:0 10px;flex-wrap:nowrap;align-items:center}'
            '#s4 details.grp>summary .g-m,#s5 details.grp>summary .g-m{min-width:0;white-space:nowrap;text-align:right;font-size:13px;display:flex;flex-direction:column;align-items:flex-end;gap:1px}'
            '#s4 details.grp>summary .g-m em,#s5 details.grp>summary .g-m em{margin-right:0;font-size:10.5px}'
            '#s4 details.grp>summary .g-name{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#s5 details.grp>summary .g-name .kind{white-space:nowrap}#s5 details.grp>summary .g-name{min-width:0;white-space:normal;word-break:keep-all;overflow-wrap:anywhere;line-height:1.35}'
            '#s5 details.grp>summary .g-org{min-width:0;overflow:hidden}#s5 details.grp>summary .g-org .g-hq{display:block;white-space:normal;overflow-wrap:anywhere}'
            '#s4 details.grp>summary .g-cur .gv{font-weight:800;color:var(--navy)}#s4 details.grp>summary .g-cur em{color:var(--navy);font-weight:700}#s4 details.grp>summary .gm-need{font-size:12.5px}details.grp>summary .chev{justify-self:end}</style>')
# 1~(전전월) 접기: 기본 접힘 · 버튼으로 펼침 (대기 인력·R&D 표)
_FOLD_CSS = ('<style>section.fold-old td.old,section.fold-old th.old{display:none}section.fold-old col.old{display:none}'
             '#s5.fold-old table.rdt{min-width:0}.tools button[data-fold][aria-pressed=true]{background:#EEF4FF;border-color:#1F5FD0;color:#1F5FD0}</style>'
             '<script>document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("button[data-fold]");if(!b)return;'
             'var s=b.closest("section");var f=s.classList.toggle("fold-old");b.setAttribute("aria-pressed",f?"false":"true");'
             'b.textContent=b.textContent.replace(f?"접기":"펼치기",f?"펼치기":"접기");window.dispatchEvent(new Event("resize"))});'
             'window.__ca_after=function(){document.querySelectorAll("#s4 details.grp[open] .scroll>table").forEach(function(t){var cg=t.querySelector(":scope>colgroup[data-auto]");if(!cg||!t.offsetParent)return;var cols=cg.children,k=cols.length-2,sc=t.parentNode,cs=getComputedStyle(sc),avail=sc.clientWidth-(parseFloat(cs.paddingLeft)||0)-(parseFloat(cs.paddingRight)||0),sum=0;for(var i=0;i<cols.length;i++){if(getComputedStyle(cols[i]).display==="none")continue;sum+=parseFloat(cols[i].style.width)||0}if(sum<avail-4){cols[k].style.width=((parseFloat(cols[k].style.width)||0)+avail-sum)+"px";t.style.width=avail+"px";t.style.minWidth=avail+"px"}})};</script>')

# ---- 05 R&D · 내부과제 (실과제) ----
def _s5():
    import re as _r2
    def _pk(code, name):
        return _r2.sub(r"[\s_\-\(\)\[\]]", "", str(name)).lower()
    projs, meta = {}, {}
    for p in PP.values():
        per = {}
        for (code, name, kind), mm in p["projs"].items():
            if kind != "R&D·내부과제" or sum(mm) <= 0.005: continue
            k = (p["corp"], _pk(code, name))
            cur = per.setdefault(k, [0.0]*12)
            for i in range(12): cur[i] += mm[i]
            m0 = meta.get(k)
            if m0 is None or (len(str(code)) > len(str(m0[0]))): meta[k] = (code, name)
        for k, mm in per.items():
            projs.setdefault(k, []).append((p, mm))
    projs = {(k[0], meta[k][0], meta[k][1]): v for k, v in projs.items()}
    blocks = ""; tot = {"아이티센클로잇": 0.0, "아이티센엔텍": 0.0}; npp = 0
    for (corp, code, name), lst in sorted(projs.items(), key=lambda kv: (-sum(mm[CUR] for _, mm in kv[1]), -sum(sum(mm) for _, mm in kv[1]))):
        kind = "내부과제" if code.endswith("I") or "내부과제" in name else "R&D"
        m10 = sum(mm[CUR] for _, mm in lst); tot[corp] += m10; npp += len(lst)
        orgs = list(dict.fromkeys(p["org"] for p, _ in lst))
        hq = lst[0][0]["hq"]
        trs = ""
        for p, mm in sorted(lst, key=lambda x: (-x[1][CUR], -sum(x[1]))):
            trs += (f'<tr><td class="l">{p["name"]}</td><td class="l">{p["org"]}</td>' + "".join(f'<td class="{"zero " if v <= 0.005 else ""}{"conf" if i < CUR else ("cm" if i == CUR else "fut")}">{v:.2f}</td>' for i, v in enumerate(mm)) + f'<td class="strong">{sum(mm):.2f}</td></tr>')
        blocks += f'''
<details class="grp" data-corp="{CORP_KEY[corp]}">
  <summary>
    <span class="g-name"><span class="kind {"k-rd" if kind == "R&D" else "k-in"}">{kind.replace("&", "&amp;")}</span>{name.strip()}</span>
    <span class="g-org"><b class="g-code">{code}</b><br><span class="g-hq">{corp} · {hq} · {", ".join(orgs[:2])}{" 외" if len(orgs) > 2 else ""}</span></span>
    <span class="g-m"><em>인원</em>{len(lst)}명</span>
    <span class="g-m"><em>연간</em>{sum(sum(mm) for _, mm in lst):.2f} MM</span>
    <span class="g-m"><em>{CM}월</em>{m10:.2f} MM</span>
    <span class="chev" aria-hidden="true"></span>
  </summary>
  <div class="scroll"><table class="rdt">
    <colgroup><col class="c-nm"><col class="c-org">{"".join(f'<col class="c-mo">' for i, _ in enumerate(MON))}<col class="c-yr"></colgroup>
    <thead><tr><th class="l">성명</th><th class="l">소속</th>{"".join(f'<th class="{"conf" if i < CUR else ("cm" if i == CUR else "fut")}">{m}{"<br><small>당월</small>" if i == CUR else ""}</th>' for i, m in enumerate(MON))}<th>연간</th></tr></thead>
    <tbody>{trs}</tbody>
  </table></div>
</details>'''
    if not blocks: blocks = f'<p class="muted">{RQ} R&amp;D·내부과제 투입 없음</p>'
    return f'''<section id="s5" class="card-sec detail">{_SUM_CSS}
    <style>#s5 table.rdt{{table-layout:fixed;width:100%;min-width:980px}}#s5 table.rdt col.c-nm{{width:90px}}#s5 table.rdt col.c-org{{width:170px}}#s5 table.rdt col.c-mo{{width:58px}}#s5 table.rdt col.c-yr{{width:70px}}#s5 table.rdt td.l,#s5 table.rdt th.l{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}</style>
    <div class="sec-head"><span class="sec-no">05</span><h2>R&amp;D · 내부과제 현황</h2><span class="sub">2026년 R&amp;D·내부과제 투입 과제 전체({RA} 실적 · {RP} 계획) · 과제를 클릭하면 투입 인원 · 1~12월 전체 표시</span></div>
    <div class="corp-sum num">
      <span>전체 <b>{len(projs)}개 과제 · {npp}명 · 연간 {sum(sum(mm) for lst in projs.values() for _, mm in lst):.2f}MM · {CM}월 {sum(tot.values()):.2f}MM</b></span>
      <span>아이티센클로잇 <b>{tot["아이티센클로잇"]:.2f}MM</b></span>
      <span>아이티센엔텍 <b>{tot["아이티센엔텍"]:.2f}MM</b></span>
    </div>
    <div class="tabs" role="tablist" data-scope="proj">
      <button role="tab" aria-selected="true" data-f="all">전체</button>
      <button role="tab" aria-selected="false" data-f="cloit">아이티센클로잇</button>
      <button role="tab" aria-selected="false" data-f="entec">아이티센엔텍</button>
      <span class="tools"><button data-act="csv">엑셀 다운로드</button><button data-act="open">모두 펼치기</button><button data-act="close">모두 접기</button></span>
    </div>
    <div id="proj" data-search>{blocks}
    </div>
  </section>'''

import re as _re
_tr_v16 = transform_report
def transform_report(body):
    body = _tr_v16(body)
    def sub_sec(sid, new):
        nonlocal body
        m = _re.search(r'<section id="%s"[^>]*>.*?</section>' % sid, body, _re.S)
        assert m, sid
        body = body[:m.start()] + new + body[m.end():]
    sub_sec("s1", _s1()); sub_sec("s3", _s3()); sub_sec("s4", _s4()); sub_sec("s5", _s5())
    m = _re.search(r'(<section id="s6"[^>]*>.*?<div class="comment-box">).*?(</div>\s*</section>)', body, _re.S)
    body = body[:m.start()] + m.group(1) + '\n    <p class="nocm"><em>코멘트</em>입력된 코멘트 없음 · 관리자가 회의 후 입력</p>\n    ' + m.group(2) + body[m.end():]
    body = body.replace("※ 본 리포트의 수치와 인명은 디자인 확인용 샘플입니다. ",
                        f"※ 데이터: 조직별 숫자 = 26년 가동가득 통계{_ST_D} 기준 (클로잇·엔텍 ENT 1~12월) · 대기 명단 = 같은 파일 대기인력 시트 · 사람별 프로젝트·직무 = SOLD투입MM목록·부서별 인력롤링·가동인력목록 ")
    return body

import plan as _plan
_il.reload(_plan)
_ANOM, _PP, _CMP = _plan.anomalies()
__import__('json').dump(dict(plan=[list(map(str, a)) for a in _ANOM], idle=[list(map(str, a)) for a in IDLE_CHECK]), open(__import__('cfg').w('checks.json'), 'w', encoding='utf-8'), ensure_ascii=False)
def upload_view(ic):
    li = ""
    for c in RT["corps"]:
        for h in c["hqs"]:
            nt = sum(len(dv["teams"]) for dv in h["divs"])
            li += f'<li><span>{h["name"]}{" <em>엔텍</em>" if c["name"] == "아이티센엔텍" else ""}</span><b class="num">0/{nt}</b><span class="pill p-mid">대기</span></li>'
    nt_all = sum(len(dv["teams"]) for c in RT["corps"] for h in c["hqs"] for dv in h["divs"])
    files = __import__("cfg").FILES or [("10.08", "26년 가동가득 통계 (261008).xlsx", "<b>최종 기준</b> · 클로잇·엔텍 ENT 조직별 가동MM·이행·제안·R&amp;D·대기 1~12월 + 9~12월 대기 명단"),
             ("10.09", "(261009)26년 인력롤링_EC1 2사업부.xlsx", "10~12월 투입계획 · EC1·EC2사업부 (우선)"),
             ("10.02", "(261002)26년 인력롤링_ES사업부.xlsx", "10~12월 투입계획 · ES사업부 (우선)"),
             ("10.02", "AX 사업본부 가득가동현황_261002.xlsx", "10~12월 투입계획 · AX사업본부 (우선)"),
             ("10.07", "(261006) 26년 인력롤링_하반기.xlsx (10.07 업로드본)", "10~12월 투입계획 · MSP·플랫폼엔지니어링팀 · DS사업본부 (최신)"),
             ("09.02 · 9월 2주", "MSP·플랫폼 독자양식", "비교용 (10.07 하반기 업로드본으로 대체)"),
             ("10.06", "(261006) 26년 인력롤링_하반기.xlsx", "10~12월 투입계획 · 그 외 아이티센클로잇 부서 (총괄)"),
             ("09.15", "(260915)26년 인력롤링_엔텍엔터사업본부_EM사업부.xlsx", "10~12월 투입계획 · 엔텍 EM사업부 (9월 회신)"),
             ("09월", "(2609)26년 인력운영_ET사업본부_ES사업부_검토완료.xlsx", "10~12월 투입계획 · 엔텍 ES사업부 (9월 회신)"),
             ("10.06", "SOLD투입MM목록_20261006.xlsx", "1~9월 실적 · 아이티센엔텍 (ENT사업본부)"), ("10.06", "01. 가동인력목록_20261006_ET.xlsx", "아이티센엔텍 가동대상"),
             ("10.06", "01. 가동인력목록_20261006.xlsx", "아이티센클로잇 가동대상 (AX 외)"), ("10.06", "통합인사정보조회_20261006.xls", "AX사업본부 가동대상"),
             ("10.02", "SOLD투입MM목록_20261002.xlsx", "1~9월 실적 · 아이티센클로잇")]
    trs = "".join(f'<tr><td class="l">{d}</td><td class="l">{f}</td><td class="l">{u}</td><td class="c"><span class="pill p-ok">반영 완료</span></td></tr>' for d, f, u in files)
    return f'''
<div class="view" id="v-upload"><style>#v-upload a.tbtn{{text-decoration:none;display:inline-flex;align-items:center;justify-content:center}}</style>
  <div class="titlebar"><h1>투입계획 업로드</h1><span class="crumb">담당 부서의 투입계획 파일을 올리면 자동으로 취합됩니다</span></div>
  <span class="mock-note">아래는 이번 계산에 실제 반영된 원본 파일</span>
  <div class="up-grid">
    <div>
      <div class="steps">
        <div><b>1. 양식 확인</b>투입계획 표준양식 사용</div>
        <div><b>2. 파일 업로드</b>여러 팀이 섞여 있어도 OK</div>
        <div><b>3. 자동 인식</b>시트·헤더·팀 자동 매칭</div>
        <div><b>4. 확인 후 반영</b>변경 내역 확인 → 저장</div>
      </div>
      <section class="card-sec" id="u1">
        <div class="drop">{ic('upload', 34)}<b>업로드는 사이트 메뉴에서 합니다</b>이 화면은 이번 계산에 들어간 파일을 보여 주는 기록입니다 · 담당자 화면과 같은 업로드·템플릿 화면으로 이동
          <div class="row"><a class="tbtn" href="/upload" target="_top">파일 업로드 ›</a><a class="tbtn" href="/upload#tpl" target="_top">작성 양식(템플릿) 받기</a><a class="tbtn" href="/plan/edit" target="_top">화면에서 입력</a></div></div>
      </section>
      <section class="card-sec" id="u2">
        <div class="sec-head"><h2>반영된 원본 파일</h2><span class="sub">현재 대시보드 수치의 근거</span></div>
        <table><thead><tr><th class="l">기준일</th><th class="l">파일명</th><th class="l">용도</th><th class="c">결과</th></tr></thead>
        <tbody>{trs}</tbody></table>
        <div class="note">우선순위: {RA} 실적 = SOLD(센터) · {CONF + 1}월 이후 = 부서별·독자양식 투입계획 &gt; 하반기 총괄 · 1인 월 1.00 초과분은 1.00으로 맞춤</div>
      </section>
      <section class="card-sec" id="u4">
        <div class="sec-head"><h2>확인 필요</h2><span class="sub">반영은 완료 · 담당자 확인용 ({len(_ANOM)}건)</span></div>
        <table><thead><tr><th class="l">구분</th><th class="l">대상</th><th class="l">내용</th></tr></thead>
        <tbody>{"".join(f'<tr><td class="l"><span class="pill p-mid">{a}</span></td><td class="l">{b}</td><td class="l">{c}</td></tr>' for a, b, c in _ANOM)}</tbody></table>
      </section>
    </div>
    <aside class="card-sec side" id="u3">
      <div class="sec-head"><h2>이번 주 제출 현황</h2><span class="sub">부서별 제출·반영 상태</span></div>
      <div class="role"><span class="chip solid">관리자</span> 부서별 제출 여부·반영 확정·인사 변동 제출은 사이트 「관리 ▾ 제출 현황」에서 실시간으로 봅니다</div>
      <a class="tbtn wide" href="/admin/board" target="_top" style="display:block;text-align:center;margin-top:10px">제출 현황 열기 ›</a>
    </aside>
  </div>
</div>
'''

ORG_CSS = ORG_CSS + r"""
  .cur-now{margin-top:3px;color:var(--navy)}.cur-now b{font-size:14px}.cur-now span{color:var(--muted);font-size:12px}

  .hrc-f{cursor:pointer;user-select:none}.hrc-f:hover{border-color:var(--navy)}.hrc-f.on{background:var(--navy);color:#fff;border-color:var(--navy)}.hrc-f.on b{color:#fff}

  .np-list{margin:12px 0 4px;border:1px solid var(--line);background:#fff}
  .np-list>summary{cursor:pointer;padding:10px 14px;font-size:13px;color:var(--navy);font-weight:600;list-style:none}
  .np-list>summary::before{content:'▸ ';color:var(--steel)}
  .np-list[open]>summary::before{content:'▾ '}
  .np-list>summary b{margin:0 4px;color:var(--navy)}
  .np-list .scroll{padding:0 14px 6px}
  .np-list .note{padding:0 14px 12px;font-size:12px;color:var(--muted)}
  .np-tab td,.np-tab th{text-align:center}
  .np-tab td.l,.np-tab th.l{text-align:left}
  .exec-tag{display:inline-block;font-size:10.5px;font-weight:700;color:#fff;background:#7F9BB8;padding:1px 6px;margin-left:4px;vertical-align:1px}
  .auto-why{font-size:12.5px;color:#374151}
  .auto-why em{font-style:normal;font-weight:700;color:var(--steel);margin-right:6px}
  .st-legend{margin:6px 0 10px;font-size:12px;color:var(--muted)}
  .st-legend b{color:#374151}
  :root{--rise:#B42335;--fall:#2E8B60}
  .rise{color:var(--rise)!important;font-weight:600}.fall{color:var(--fall)!important;font-weight:600}
  .mh .cur i.rise{color:var(--rise)}.mh .cur i.fall{color:var(--fall)}
  tfoot td.rise{color:#F6C9A2!important}tfoot td.fall{color:#A9E3C4!important}
  .issue.b-rise{border-left-color:var(--rise)}.issue.b-fall{border-left-color:var(--fall)}
  .warn-t{color:var(--warn)}
  th.conf,td.conf{background:#F3F5F8;color:#4B5563}
  .corp-sum .conf-sum{padding-left:14px;border-left:1px solid var(--line)}.corp-sum .cur-sum{background:#FFF4E6;border-left:4px solid #C77B2B;padding:5px 14px;font-weight:700}.corp-sum .cur-sum b{font-size:1.2em;color:#B8691A}
  .np-tab tr.np-grp td{background:#EEF2F7;color:var(--navy);font-weight:700;font-size:12.5px}
  .np-tab tr.np-sub td{font-weight:700;background:#F8FAFC}
  .np-tab td.np-so,table.ca-fix td.l.np-so{white-space:normal!important;word-break:keep-all!important;overflow-wrap:normal!important;font-size:12px;line-height:1.35}
  .np-tg{display:flex;gap:6px;padding:8px 14px 4px}.np-tg button{font:inherit;font-size:12.5px;padding:4px 12px;border:1px solid var(--line);background:#fff;color:#374151;cursor:pointer;border-radius:999px}.np-tg button[aria-pressed=true]{background:#1F3A5F;border-color:#1F3A5F;color:#fff}
  .np-tab tr[hidden]{display:none}
  .np-tab td:first-child,.np-tab th:first-child,table.ca-fix.np-tab td:first-child{white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;padding-left:6px!important;padding-right:2px!important}   /* 성명이 두 줄로 꺾이지 않게 */
  .np-tab td.np-pj{white-space:normal!important;overflow:visible;text-overflow:clip;line-height:1.35;word-break:keep-all;overflow-wrap:anywhere}.np-tab td.np-pj .np-rk{font-size:13px;color:#1F2937}.np-tab td.np-pj .np-pn{font-size:11.5px;color:#6B7280}
  #idle td.plan,#proj td.l:nth-last-child(2){max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #idle td.plan .trn{font-size:.82em;color:#6B7280;margin-top:2px;overflow:hidden;text-overflow:ellipsis}
  #idle td.zero,#proj td.zero{color:#C0C4CC}
  #idle td,#proj td{padding-left:6px;padding-right:6px}
  .tp-tab td.k{font-size:12px;color:var(--muted)}
  .tp-tab tr.tp-g td{border-top:none}
  .tp-tab tr.tp-u td{border-bottom:1px dashed #E5E9EF}
"""

ORG_JS = ORG_JS + r"""
// ---- annual 03: 팀 카드 클릭 → 그 팀 1~12월 실적 ----
document.querySelectorAll('.team-panel .mini[data-org]').forEach(card=>{
  const pick=()=>{
    const panel=card.closest('.team-panel'); const box=panel.querySelector('.tp-detail');
    const on=card.getAttribute('aria-pressed')!=='true';
    panel.querySelectorAll('.mini[data-org]').forEach(c=>{c.setAttribute('aria-pressed','false');c.classList.remove('sel')});
    if(!on){ box.innerHTML='<p class="tp-empty">팀 카드를 누르면 그 팀의 1~12월 실적이 여기에 표시됩니다.</p>'; return }
    card.setAttribute('aria-pressed','true'); card.classList.add('sel');
    box.innerHTML=orgDetail(card.dataset.org);
    box.querySelector('.od-x').addEventListener('click',e=>{e.stopPropagation();card.click()});
    box.scrollIntoView({behavior:'smooth',block:'nearest'});
  };
  card.addEventListener('click',e=>{e.stopPropagation();pick()});
  card.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}});
});
"""
ORG_CSS = ORG_CSS + r"""
  .team-panel .mini[data-org]{cursor:pointer;transition:border-color .15s}
  .team-panel .mini[data-org]:hover{border-color:var(--steel)}
  .team-panel .mini[data-org].sel{border:2px solid var(--navy);background:#FAFBFD}
  .tp-detail{margin-top:12px}
  .tp-detail .od{border:1px solid var(--line);background:#fff;padding:12px}
  .tp-detail .od .scroll>table{table-layout:fixed;width:100%}.tp-detail .od table th:first-child{width:118px}.tp-detail .od table td,.tp-detail .od table th{padding:5px 3px;font-size:12px}.tp-detail .od table th:last-child{width:62px}
  .tp-empty{margin:4px 0;padding:14px;border:1px dashed #CBD3DD;color:var(--muted);font-size:13px;text-align:center;background:#fff}
  .tp-all{margin-top:12px}
  .tp-all>summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--steel);padding:6px 0}
"""

# ---- 팀별 대기 인원 (annual 03 팀 상세용) ----
_TK = {}
for ci, c in enumerate(RT["corps"]):
    for hi_, h in enumerate(c["hqs"]):
        for di, dv in enumerate(h["divs"]):
            for ti, t in enumerate(dv["teams"]):
                _TK[(c["name"], h["name"], dv["name"], t["raw"])] = f"c{ci}h{hi_}d{di}t{ti}"
IDLE = {}
for p in split_people():
    k = _TK.get((p["corp"], p["hq"], p["dv"], p["tm"]))
    if not k or sum(p["idle"]) <= 0.005: continue
    IDLE.setdefault(k, []).append(dict(n=p["name"], j=p["직무"] or "", e=bool(p["exec"]), l=(leave_of(p) or (None, quit_tag(p) or ""))[1], g=p["직급"] or "", v=[round(x, 4) for x in p["idle"]], a=[1 if x > 0.005 else 0 for x in p["T"]]))
for k in IDLE: IDLE[k].sort(key=lambda x: x["n"])
ORG_JS = ORG_JS.replace("const ORG=__ORG__;", "const ORG=__ORG__; const IDLE=" + _json.dumps(IDLE, ensure_ascii=False) + ";")
ORG_JS = ORG_JS.replace("box.innerHTML=orgDetail(card.dataset.org);", "box.innerHTML=orgDetail(card.dataset.org)+idleList(card.dataset.org);")
ORG_JS = ORG_JS + r"""
function idleList(key){
  const L=IDLE[key]||[]; const est=i=>i>=9?' class="est'+(i===9?' cm':'')+'"':'';
  if(!L.length) return '<div class="od-idle"><div class="oi-h"><b>대기 인원</b><span>연간 대기 없음</span></div></div>';
  const tot=MONS.map((_,i)=>L.reduce((a,p)=>a+p.v[i],0));
  const row=p=>`<tr><td class="l">${p.n}${p.e?' <span class="exec-tag">사업부장</span>':''}${p.l?' <span class="leave-tag '+(p.l.indexOf('퇴사')>=0?'lt-quit':'lt-leave')+'">'+p.l+'</span>':''}</td><td class="l">${p.g||'—'}</td><td class="l muted">${p.j}</td>${p.v.map((v,i)=>{const na=p.a&&!p.a[i],e=est(i),tc=na?(e?e.replace('class="','class="na '):' class="na"'):e;return `<td${tc}>${na?'':'<span class="'+(v<=0.005?'z':'')+'">'+f1(v)+'</span>'}</td>`}).join('')}<td class="strong">${f1(p.v.reduce((a,b)=>a+b,0))}</td></tr>`;
  return `<div class="od-idle"><div class="oi-h"><b>대기 인원</b><span>${L.length}명 · 인원별 대기MM (가동대상 − 투입) · 이름순 · 현재 소속 기준이라 월중 이동·1인 초과투입이 있으면 위 팀 대기와 합계가 다를 수 있음</span></div>
   <div class="scroll"><table><thead><tr><th class="l">성명</th><th class="l">직급</th><th class="l">직무</th>${MONS.map((m,i)=>`<th${est(i)}>${m}</th>`).join('')}<th>연간</th></tr></thead>
   <tbody>${L.map(row).join('')}</tbody><tfoot><tr><td class="l" colspan="3">합계</td>${tot.map((v,i)=>`<td${est(i)}>${f1(v)}</td>`).join('')}<td>${f1(tot.reduce((a,b)=>a+b,0))}</td></tr></tfoot></table></div></div>`;
}
// ---- 주간 04 대기: 팀 안 정렬 ----
document.querySelectorAll('#s4 .sort-bar button').forEach(b=>b.addEventListener('click',()=>{
  const k=b.dataset.sort;
  document.querySelectorAll('#s4 .sort-bar button').forEach(x=>x.setAttribute('aria-pressed',x===b));
  document.querySelectorAll('#idle tbody.tgrp').forEach(tb=>{
    const rows=[...tb.querySelectorAll('tr[data-name]')];
    rows.sort((a,c)=>k==='name'?a.dataset.name.localeCompare(c.dataset.name,'ko'):(+c.dataset[k]-+a.dataset[k])||a.dataset.name.localeCompare(c.dataset.name,'ko'));
    rows.forEach(r=>tb.appendChild(r));
  });
}));
"""
ORG_CSS = ORG_CSS + r"""
  #idle tr.tg-h td{background:#EEF2F7;border-top:2px solid #D5DEEA;padding:8px 10px}
  #idle tr.tg-h b{color:var(--navy);font-size:13.5px;margin-right:10px}
  #idle tr.tg-h span{font-size:12px;color:var(--muted)}
  #idle td.msum{text-align:center;font-weight:700;font-size:13px;color:var(--navy);font-variant-numeric:tabular-nums}
  #idle td.msum.cm{background:#E1E9F7}
  #idle tbody.hq-tot td{background:#DCE6F5;border-top:2px solid #B9C9E2;padding:8px 10px;font-size:13.5px}
  #idle tbody.hq-tot b{color:var(--navy)}#idle tbody.hq-tot span{font-size:12px;color:var(--muted);font-weight:400}
  #idle tbody.tgrp tr[data-name] td:first-child{padding-left:18px}
  .sort-bar{display:flex;align-items:center;gap:6px;margin:8px 0 2px;font-size:12.5px;flex-wrap:wrap}
  .sort-bar em{font-style:normal;font-weight:700;color:#374151;margin-right:2px}
  .sort-bar button{border:1px solid #D1D5DB;background:#fff;padding:3px 10px;font:inherit;font-size:12.5px;cursor:pointer;color:#374151}
  .sort-bar button[aria-pressed="true"]{background:var(--navy);border-color:var(--navy);color:#fff}
  .sort-bar .grp-toggle{margin-left:auto;display:inline-flex;gap:6px;align-items:center}
  .od-idle{margin-top:10px;border:1px solid var(--line);background:#fff;padding:12px}
  .tp-detail .od table th:first-child{width:274px}
  .od-idle .scroll>table{table-layout:fixed;width:100%}.od-idle table td,.od-idle table th{padding:5px 3px;font-size:12px}
  .od-idle table th:nth-child(1){width:100px}.od-idle table th:nth-child(2){width:50px}.od-idle table th:nth-child(3){width:60px}.od-idle table th:last-child{width:62px}
  .od-idle table td.l{white-space:normal}
  .tp-detail .od tr.rate td{font-size:12px;letter-spacing:-.2px;padding-left:1px;padding-right:1px}
  .od-idle .oi-h{display:flex;gap:10px;align-items:baseline;margin-bottom:6px}
  .od-idle .oi-h b{color:var(--navy)} .od-idle .oi-h span{font-size:12px;color:var(--muted)}
  .od-idle td .z{color:#C0C4CC}
  #idle td.na,.od-idle td.na{background:#E9ECF1!important;border-color:#E9ECF1}
"""

ORG_JS = ORG_JS + r"""
// ---- 02 인사 변동: 유형 칩을 누르면 해당 인원만 ----
(function(){const s=document.getElementById('s2');if(!s)return;const chips=[...s.querySelectorAll('.hrc-f')];let cur='';
 const apply=()=>{chips.forEach(c=>c.classList.toggle('on',c.dataset.k===cur));s.querySelectorAll('tbody tr[data-k]').forEach(r=>{r.hidden=!!cur&&r.dataset.k!==cur});
  const d=s.querySelector('details.hr-list');if(d&&cur)d.open=true};
 chips.forEach(c=>{const t=()=>{cur=cur===c.dataset.k?'':c.dataset.k;apply()};c.addEventListener('click',t);c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();t()}})})})();
// ---- 주간 04 대기: 본부를 열면 그 안의 사업부·팀도 모두 펼침 ----
document.querySelectorAll('#idle details.grp').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)d.querySelectorAll('tbody.tgrp').forEach(tb=>{tb.classList.remove('closed');const h=tb.querySelector('tr.tg-h');if(h)h.setAttribute('aria-expanded',true)})}));
// ---- 주간 04 대기: 사업부·팀 묶음 접기/펼치기 ----
function tgSet(tb,open){tb.classList.toggle('closed',!open);const h=tb.querySelector('tr.tg-h');if(h)h.setAttribute('aria-expanded',open)}
document.querySelectorAll('#idle tr.tg-h').forEach(h=>{
  const t=()=>{const tb=h.parentElement;tgSet(tb,tb.classList.contains('closed'))};
  h.addEventListener('click',t); h.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();t()}});
});
document.querySelectorAll('#s4 .tabs [data-act="open"],#s4 .tabs [data-act="close"]').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#idle tbody.tgrp').forEach(tb=>tgSet(tb,b.dataset.act==='open'));
}));
document.querySelectorAll('#s4 .grp-toggle button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#idle tbody.tgrp').forEach(tb=>tgSet(tb,b.dataset.g==='open'));
}));
"""
ORG_CSS = ORG_CSS + r"""
  #idle tr.tg-h{cursor:pointer}
  #idle tr.tg-h:hover td{background:#E4EAF2}
  #idle tr.tg-h .tg-chev{display:inline-block;width:8px;height:8px;border-right:2px solid var(--steel);border-bottom:2px solid var(--steel);transform:rotate(45deg);margin:0 10px 2px 2px;transition:transform .15s}
  #idle tbody.closed tr.tg-h .tg-chev{transform:rotate(-45deg)}
  #idle tbody.closed tr[data-name]{display:none}
  @media print{ #idle tbody.closed tr[data-name]{display:table-row} }
"""

ORG_JS = ORG_JS + r"""
const lvBox=document.getElementById('lvShow');
if(lvBox){lvBox.addEventListener('change',()=>document.getElementById('idle').classList.toggle('hide-leave',!lvBox.checked))}
"""
ORG_CSS = ORG_CSS + r"""
  #idle.hide-leave tr[data-leave]{display:none}
  .leave-tag{display:inline-block;font-size:10.5px;font-weight:600;padding:0 6px;margin-left:4px;vertical-align:1px;border:1px solid}
  .leave-tag.lt-quit{color:#fff;background:#6B7280;border-color:#6B7280}
  .st-legend2{margin-top:-6px}.st-legend .leave-tag{white-space:nowrap}
  .lv-sec{margin-top:22px;border-top:2px solid #E3E8EF;padding-top:14px}.lv-head{display:flex;align-items:baseline;gap:12px;margin-bottom:8px}.lv-head h3{margin:0;font-size:16px;color:#0F2942}.lv-head h3 b{color:#5B4B8A}
  table.lv-t{table-layout:fixed;width:100%}table.lv-t th:nth-child(1){width:10%}table.lv-t th:nth-child(2){width:10%}table.lv-t th:nth-child(3){width:15%}table.lv-t th:nth-child(4){width:10%}table.lv-t th:nth-child(5){width:7%}
  table.lv-t th:nth-child(6),table.lv-t th:nth-child(7){width:8%}table.lv-t th:nth-child(8),table.lv-t th:nth-child(9),table.lv-t th:nth-child(10){width:6%}table.lv-t th:nth-child(11){width:12%}table.lv-t td{white-space:nowrap;overflow:hidden}
  .g-org{line-height:1.35}.g-org .g-code{font-weight:700;color:#374151;font-family:inherit}.g-org .g-hq{font-size:12px;color:#6B7280}
  td.st-cell{white-space:nowrap;vertical-align:middle}.lv-line{display:block;margin-top:3px;font-size:11px;line-height:1.2;font-variant-numeric:tabular-nums}
  .lv-line.lt-quit{color:#4B5563}.lv-line.lt-leave{color:#5B4B8A}
  .leave-tag.lt-leave{color:#5B4B8A;background:#F1EEF8;border-color:#C9BFE3}
  .pill.p-quit{background:#6B7280;color:#fff}
  .pill.p-leave{background:#F1EEF8;color:#5B4B8A}
  #idle tr[data-leave] td{color:#6B7280}
  .lv-toggle{margin-left:12px;font-size:12.5px;display:inline-flex;align-items:center;gap:4px;cursor:pointer}
"""

ORG_JS = ORG_JS + r"""
// ---- 주간 04: 당월 대기 0 인원 숨김 (기본) ----
function idleFilter(){
  const box=document.getElementById('idle'); if(!box) return;
  box.classList.toggle('hide-cur0',!document.getElementById('cur0Show').checked);
  box.classList.toggle('hide-leave',!document.getElementById('lvShow').checked);
  box.querySelectorAll('tbody.tgrp').forEach(tb=>{
    const vis=[...tb.querySelectorAll('tr[data-name]')].filter(r=>!(box.classList.contains('hide-cur0')&&r.dataset.cur0)&&!(box.classList.contains('hide-leave')&&r.dataset.leave)&&!r.classList.contains('flt')).length;
    tb.classList.toggle('empty',vis===0);
    const c=tb.querySelector('.tg-vis'); if(c) c.textContent=vis;
  });
  box.querySelectorAll('details.grp').forEach(d=>{
    const vis=[...d.querySelectorAll('tr[data-name]')].filter(r=>!(box.classList.contains('hide-cur0')&&r.dataset.cur0)&&!(box.classList.contains('hide-leave')&&r.dataset.leave)&&!r.classList.contains('flt')).length;
    const em=d.querySelector('.g-vis'); if(em) em.textContent=vis+'명';
  });
}
['cur0Show','lvShow'].forEach(id=>{const e=document.getElementById(id); if(e) e.addEventListener('change',idleFilter)});
idleFilter();
"""
ORG_JS = ORG_JS + r"""
// ---- 대기 인력: 사업부장 제외 · 누적 대기 기간 필터 (합계 재계산) ----
(function(){
  const box=document.getElementById('idle'); if(!box) return;
  const JOBQ=v=>{v=(v||'').replace(/\s+/g,'').toLowerCase();return v==='전체직무'?'':v};
  const ex=document.getElementById('exShow'), ld=document.getElementById('ldSel'), jq=document.getElementById('jobQ');
  const ids=['sc-conf','sc-all','sc-cl','sc-et','sc-need'], cls=['gm-n','gm-h1','gm-hp','gm-hc','gm-need'];
  const orig=new Map();
  ids.forEach(i=>{const e=document.getElementById(i); if(e) orig.set(e,e.innerHTML)});
  box.querySelectorAll('details.grp .gv').forEach(e=>orig.set(e,e.innerHTML));
  const f2=v=>v.toFixed(2);
  function apply(){
    const hideEx=ex&&!ex.checked, minM=ld?+ld.value:0, q=jq?JOBQ(jq.value):'', active=hideEx||minM>0||!!q;
    const rows=[...box.querySelectorAll('tr[data-name]')];
    rows.forEach(r=>r.classList.toggle('flt',!!((hideEx&&r.dataset.exec)||(minM&&(+r.dataset.mon<minM))||(q&&(r.dataset.job||'').indexOf(q)<0))));
    if(q) box.querySelectorAll('details.grp').forEach(d=>{if([...d.querySelectorAll('tr[data-name]')].some(r=>!r.classList.contains('flt'))) d.open=true});
    if(!active){orig.forEach((h,e)=>e.innerHTML=h); return}
    const A={conf:[0,0],all:[0,0],cl:[0,0],et:[0,0],need:[0,0]};
    box.querySelectorAll('details.grp').forEach(d=>{
      const rs=[...d.querySelectorAll('tr[data-name]')].filter(r=>!r.classList.contains('flt'));
      const sum=k=>rs.reduce((a,r)=>a+(+r.dataset[k]),0);
      const set=(c,t)=>{const e=d.querySelector('.'+c); if(e) e.textContent=t};
      set('gm-n',rs.length+'명'); set('gm-h1',f2(sum('h1'))+' MM'); set('gm-hp',f2(sum('hp'))+' MM'); set('gm-hc',f2(sum('hc'))+' MM'); set('gm-need',f2(sum('need'))+' MM');
      const key=d.dataset.corp==="cloit"?'cl':'et';
      rs.forEach(r=>{
        if(+r.dataset.hp>0.005){A.conf[0]++;A.conf[1]+=+r.dataset.hp}
        A.all[0]++;A.all[1]+=+r.dataset.hc; A[key][0]++;A[key][1]+=+r.dataset.hc;
        if(+r.dataset.need>0){A.need[0]++;A.need[1]+=+r.dataset.need}
      });
    });
    const put=(id,t)=>{const e=document.getElementById(id); if(e) e.textContent=t};
    put('sc-conf',f2(A.conf[1])+'MM · '+A.conf[0]+'명'); put('sc-all',f2(A.all[1])+'MM · '+A.all[0]+'명');
    put('sc-cl',f2(A.cl[1])+'MM · '+A.cl[0]+'명'); put('sc-et',f2(A.et[1])+'MM · '+A.et[0]+'명'); put('sc-need',f2(A.need[1])+' MM · '+A.need[0]+'명');
    if(typeof idleFilter==='function') idleFilter();
  }
  [ex,ld].forEach(e=>e&&e.addEventListener('change',()=>{apply(); if(typeof idleFilter==='function') idleFilter()}));
  if(jq) ['input','change'].forEach(ev=>jq.addEventListener(ev,()=>{apply(); if(typeof idleFilter==='function') idleFilter()}));
}).call(this);
""".replace("__CM__", str(CM))
ORG_CSS = ORG_CSS + r"""
  #idle tr.flt{display:none}
"""
ORG_CSS = ORG_CSS + r"""
  #idle.hide-cur0 tr[data-cur0]{display:none}
  #idle tbody.tgrp.empty{display:none}
"""

# ---- 월 기준 반영 (JS 음영 · 휴직 표 열 너비) ----
ORG_JS = ORG_JS.replace("const est=i=>i>=9?' class=\"est'+(i===9?' cm':'')+'\"':'';", "const est=i=>i>=%d?' class=\"est'+(i===%d?' cm':'')+'\"':'';" % (CONF, CUR))
_klv = 12 - CUR
ORG_CSS = ORG_CSS.replace("table.lv-t th:nth-child(8),table.lv-t th:nth-child(9),table.lv-t th:nth-child(10){width:6%}table.lv-t th:nth-child(11){width:12%}",
                          "".join(f"table.lv-t th:nth-child({8 + i}){{width:6%}}" for i in range(_klv)) + f"table.lv-t th:nth-child({8 + _klv}){{width:{12 + 6 * (3 - _klv)}%}}")

ORG_CSS = ORG_CSS + r"""
  /* 인사 변동: 유형을 눌러도 열·쪽 너비가 변하지 않게 고정 */
  html{scrollbar-gutter:stable}
  #s2 .panel>table{table-layout:fixed;width:100%}
  .pop{position:fixed!important;top:calc(var(--hdr) - 4px)!important;max-height:calc(100vh - var(--hdr) - 20px);overflow:auto}#s4{scroll-margin-top:96px}.kpi.go-idle{cursor:pointer}.kpi.go-idle:hover{border-color:var(--steel)}.kpi .kgo{color:var(--steel);font-weight:700;font-size:13px}
  .kpis .kpi .label{font-size:17px!important;font-weight:800!important;color:var(--navy)!important;letter-spacing:-.01em}
  .kpis .kpi.alt .label{color:var(--steel)!important}
  .kpis .kpi .label i{font-size:12.5px!important;font-weight:700!important}
  .kpis .kpi .value{font-size:17pt!important}
  .kpis .kpi .value small{font-size:14px!important}
  .kpis .kpi .ytd,.kpis .kpi .cmp{font-size:13px!important}
  #s2 .panel{overflow-x:hidden}
  #s2 table th:nth-child(1){width:68px}#s2 table th:nth-child(2){width:78px}#s2 table th:nth-child(4){width:124px}#s2 table td:nth-child(4){overflow-wrap:normal}#s2 table th:nth-child(5){width:70px}#s2 table th:nth-child(6){width:62px}#s2 table th:nth-child(7){width:15%}#s2 table th:nth-child(8){width:11%}
  #s2 table td{white-space:normal;word-break:keep-all;overflow-wrap:anywhere}
  #s2 .hr-sum .hrc{box-sizing:border-box;min-width:76px}
  /* 연간 대기 인원: 휴직·퇴사 표시가 옆 칸을 덮지 않게 이름 칸 안에서 줄바꿈 */
  /*TEAMSM*/#idle tr[data-name] td:nth-child(2){font-size:.84em;letter-spacing:-.2px;color:#4B5563}
  .od-idle table th:nth-child(1){width:118px}.od-idle table th:nth-child(2){width:64px}.od-idle table th:nth-child(3){width:92px}
  .od-idle table td.l{padding-right:8px}
  .od-idle table td .leave-tag,.od-idle table td .exec-tag{display:block;width:fit-content;max-width:100%;margin:3px 0 0 0;white-space:normal;word-break:keep-all;line-height:1.3;padding:1px 6px}
"""
ORG_CSS = ORG_CSS + """
  .kpi .cmp.cmp2{margin-top:2px;padding-top:0;border-top:0;font-size:11.5px;opacity:.8}

  .two{display:inline-grid;justify-items:end}.two>.bw,.two>.bm{grid-area:1/1}.bm{visibility:hidden}#s1.vm .bw{visibility:hidden}#s1.vm .bm{visibility:visible}
  .bt{display:inline-flex;background:#e8edf3;border-radius:7px;padding:2px;margin-left:6px}.bt button{border:0;background:none;padding:4px 11px;font:inherit;font-size:12.5px;color:#667;border-radius:5px;cursor:pointer}.bt button.on{background:#fff;color:#0F2942;font-weight:700;box-shadow:0 1px 2px #0002}
  .kg{display:flex;justify-content:center;margin:2px 0 4px}.kg svg{display:block}
  td.mg,th.mg{width:46px;padding:2px 3px!important;text-align:center}td.mg svg{display:block;margin:0 auto}#s1 .row2 .panel:first-child th,#s1 .row2 .panel:first-child td{padding-left:7px!important;padding-right:7px!important}
  tfoot span.rise{color:#F6C9A2!important}tfoot span.fall{color:#A9E3C4!important}
  /* 1110 디자인: 이름·날짜 문구는 중간에서 끊기지 않게 */
  .nw{white-space:nowrap}
  .od-idle table td .leave-tag,.od-idle table td .exec-tag,.leave-tag,.exec-tag{white-space:nowrap!important;word-break:keep-all}
  #idle td .leave-tag,#idle td .exec-tag{white-space:nowrap!important}
  /* 비매출 모수 명단: 표를 박스 좌우 끝까지 채우고, 배너·탭·표 글자의 시작 축(14px)을 같게 */
  .np-list .scroll{padding:0 0 6px!important}
  .np-list table.np-tab{width:100%;table-layout:fixed}
  .np-tab th:first-child,.np-tab td:first-child,table.ca-fix.np-tab td:first-child{padding-left:14px!important}
  .np-tab th:last-child,.np-tab td:last-child{padding-right:14px!important}
  .np-tab tr.np-grp td:first-child{padding-left:14px!important}
  #a4 table.mtab td:first-child,#a4 table.mtab th:first-child{white-space:nowrap}
"""

ORG_JS = ORG_JS + r"""
// ---- 1110: 비매출 모수 명단 표가 칸 폭 계산 뒤에 오른쪽이 비면 컨테이너 폭까지 비례해서 채움 ----
(function(){
  function stretch(){
    document.querySelectorAll('table.np-tab,#a4 table.mtab').forEach(function(t){
      if(!t.offsetParent) return;
      var sc=t.parentNode, cs=getComputedStyle(sc), inner=sc.clientWidth-parseFloat(cs.paddingLeft||0)-parseFloat(cs.paddingRight||0);
      var cg=t.querySelector(':scope>colgroup'); if(!cg||inner<=0) return;
      var cols=[].slice.call(cg.children); var tot=0; cols.forEach(function(c){tot+=parseFloat(c.style.width)||0});
      if(!tot||inner-tot<4||t.dataset.npw==String(Math.round(inner))&&Math.abs(t.offsetWidth-inner)<3) return;
      var k=inner/tot, first=-1;
      if(t.closest('#a4')){ // 04 본부별 가득률: 첫 칸(법인/본부)은 좁게 고정, 남는 폭은 월·연간 칸에 나눔
        var w0=Math.min(parseFloat(cols[0].style.width)||0,170); first=0;
        k=(inner-w0)/(tot-(parseFloat(cols[0].style.width)||0)); cols[0].style.width=w0.toFixed(1)+'px';
      }
      cols.forEach(function(c,i){if(i===first)return;c.style.width=(parseFloat(c.style.width)*k).toFixed(1)+'px'});
      t.style.width=inner+'px'; t.style.minWidth=inner+'px'; t.dataset.npw=String(Math.round(inner));
    });
  }
  setInterval(stretch,700); window.addEventListener('resize',function(){setTimeout(stretch,400)});
})();
"""

# ORDER_V1

# ADMIN_V1
