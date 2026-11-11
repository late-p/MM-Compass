# 회의용 대시보드(발표 모드) 생성 — 관리자 데이터와 같은 계산 결과 사용
import sys, os, html as H
sys.path.insert(0, __import__('cfg').CALC)
import v4_extra as X
import gauge as GA

E = lambda s: H.escape(str(s if s is not None else ""))
RT, PP, CUR = X.RT, X.PP, X.CUR
P9, P10 = CUR - 1, CUR
D = RT["d"]
WEEK_LABEL = __import__('cfg').WEEK["title"]
ASOF = __import__('cfg').WEEK["asof"]
MEET = __import__('cfg').WEEK["meet"]

def inp(d, m): return d["ex"][m] + d["pr"][m] + d["rd"][m]
def pc(v): return "—" if v is None else f"{v:.2f}%"
def dl(a, b, unit="%p"):
    if a is None or b is None: return ""
    d = b - a
    if abs(d) < 0.005: return f'<span class="pl pl-0">±0.00{unit}</span>'
    return f'<span class="pl {"pl-up" if d > 0 else "pl-dn"}">{"+" if d > 0 else "−"}{abs(d):.2f}{unit}</span>'

# ---------- 비교 기준: 월 첫 보고는 전월 확정, 같은 달 다음 보고부터는 전주 게시본 ----------
import json as _j
try:
    import cfg as _cfg; _WK = _cfg.WEEK
except Exception:
    _WK = {}
PREV = None
if _WK.get("prev_summary"):
    try: PREV = _j.load(open(_WK["prev_summary"], encoding="utf-8"))
    except Exception: PREV = None
# 전월이 SOLD 마감 전(잠정)이면 월 첫 보고는 전월 마지막 게시 주차 숫자와 비교
PMB = None
if not PREV and _WK.get("pm_summary"):
    try: PMB = _j.load(open(_WK["pm_summary"], encoding="utf-8"))
    except Exception: PMB = None
MODE = "week" if PREV else "month"
PM_OK = (P9 + 1) <= X.CONF                                 # 전월 SOLD 실적 확정 여부
ML = f"{P9 + 1}월 확정" if PM_OK else (f"{P9 + 1}월 잠정")   # 전월 (확정/잠정)
if PMB: ML = f"{P9 + 1}월 실적"   # 전월 마지막 주차 숫자지만 회의에서는 '전월 실적'으로 부름
ML_T = ML if "실적" in ML else ML + " 실적"
BL = (PREV.get("short") or "전주") if PREV else ML        # 이번 비교 기준 이름
BLs = "전주" if PREV else ML
def K(*a): return "|".join(a)
def val(d, f, m): return inp(d, m) if f == "inp" else d[f][m]
def base(key, d, f):
    if PREV: return (PREV["nodes"].get(key) or {}).get(f)
    if PMB:
        v = (PMB["nodes"].get(key) or {}).get(f)
        return v if v is not None else val(d, f, P9)
    return val(d, f, P9)
def f2(v): return "—" if v is None else f"{v:.2f}"
def cmp(key, d, f, unit="%p", pre=""):
    """비교 줄: 기준(전주 또는 전월 확정) + 증감, 전주 기준일 때는 전월 확정 줄을 접어 둠"""
    cur = val(d, f, P10); b = base(key, d, f)
    if PREV and b is None:   # 전주 값이 없는 조직(사업부·팀)은 전월 확정과 비교
        return f'<div class="cmp">{ML} {f2(val(d, f, P9))}{pre} {dl(val(d, f, P9), cur, unit)}</div>'
    out = f'<div class="cmp">{BLs} {f2(b)}{pre} {dl(b, cur, unit)}</div>'
    if PREV: out += f'<div class="cmp m-only">{ML} {f2(val(d, f, P9))}{pre} {dl(val(d, f, P9), cur, unit)}</div>'
    return out
SUMMARY = {"label": _WK.get("label", ""), "short": _WK.get("short", ""), "nodes": {}, "people": {}}
def _snap(key, d):
    SUMMARY["nodes"][key] = {f: (round(val(d, f, P10), 4) if val(d, f, P10) is not None else None) for f in ("T", "u", "g", "gn", "idle", "inp", "ex", "pr", "rd")}

# ---------- slide 1: 요약 ----------
idle_people = [p for p in PP.values() if p["idle"][P10] > 0.005]
_snap("ALL", D)
kpis = [("가득률 (비매출 모수 제외)", "gn", "%", "%p"), ("투입 MM", "inp", f' / {D["T"][P10]:.2f}', ""), ("대기 MM", "idle", " MM", "")]
kpi_html = "".join(f'<div class="kpi"><div class="kl">{E(l)}</div><div class="kv">{val(D, f, P10):.2f}<small>{E(sfx)}</small></div><div class="kc">{cmp("ALL", D, f, unit)}</div></div>'
                   for l, f, sfx, unit in kpis)
def _pmv(d, f):
    try: return d[f][P9]
    except Exception: return None
def _pmd(d, f):
    return dl(d[f][P9 - 1], d[f][P9], "%p") if P9 > 0 else ""
def _pmc(c):
    d = c["d"]; return f'<div class="pmc"><em>{E(c["name"])}</em> <span class="y3i">가득 <b class="vg">{_pmv(d, "g"):.2f}%</b></span><span class="y3i">가동 <b class="vu">{_pmv(d, "u"):.2f}%</b></span></div>'
PM_GAUGE = (not PREV)   # 월 첫 주(전주 보고 없음)에는 전월 실적도 나침반으로 보여줌
_pmg = ('<div class="pmg">' + GA.sized(GA.pair(min(_pmv(D, "u"), 100), min(_pmv(D, "g"), 100), None, None, "pmg", True), 300) + '</div>') if PM_GAUGE else ""
_pmcls = " pm" if PM_GAUGE else ""
year_html = (f'<div class="yr{_pmcls}">{_pmg}<div class="yl"><span>{ML_T} · 전사</span><br><span class="y3i">가득률 <b>{_pmv(D, "g"):.2f}%</b> {_pmd(D, "g")}</span> <span class="y3i">비매출 모수 제외 <b>{_pmv(D, "gn"):.2f}%</b></span> <span class="y3i">가동률 <b>{_pmv(D, "u"):.2f}%</b> {_pmd(D, "u")}</span></div>'
             f'<div class="yrr"><span>{ML_T} · 법인별</span>' + "".join(_pmc(c) for c in RT["corps"]) + '</div></div>')
def _y3(label, items):
    def one(k, v):
        c = "vg" if "가득" in k else "vu"
        return f'<span class="y3i">{k} <b class="{c}">{v:.2f}%</b></span>'
    return f'<div class="y3g"><span class="y3t">{label}</span>' + "".join(one(k, v) for k, v in items) + '</div>'
year3_html = ('<div class="yr3">' + _y3("연간(실적+예상)", [("가득률", D["yg"]), ("가동률", D["yu"]), ("비매출 모수 제외 가득률", D["yn"])])
              + _y3(f"{X.RA} 실적", [("가득률", D["cg"]), ("가동률", D["cu"])]) + '</div>')
# 본부 목록 (요약·막대·표에서 같이 씀)
HQS = [(c, h, K("h", c["name"], h["name"])) for c in RT["corps"] for h in c["hqs"]]
def hq_label(c, h): return h["name"] if c["name"] == "아이티센클로잇" else f'엔텍 {h["name"]}'
# 이번 주 요약 (자동)
def _dd(key, d, f):
    b = base(key, d, f); cur = val(d, f, P10)
    return None if b is None or cur is None else cur - b
lines = []
def _pv(key, d, f):
    """비교 기준값: 전주(게시본) → 없으면 전월 확정(첫 주) """
    b = base(key, d, f)
    if PREV and b is None: b = val(d, f, P9)
    return b
def _sl(label, f, unit="%", du="%p"):
    cur = D[f][P10]; b = _pv("ALL", D, f)
    return f'{label} <b>{cur:.2f}{unit if unit != " MM" else "MM"}</b> <span class="muted">{BLs} {f2(b)}{"" if unit == " MM" else "%"}</span> {dl(b, cur, du)}'
lines.append(_sl("전체 가득률", "g")); lines.append(_sl("전체 가득률 (비매출 모수 제외)", "gn")); lines.append(_sl("전체 가동률", "u"))
lines.append(_sl("대기", "idle", " MM", "MM"))
from collections import Counter as _C
_hc = _C(h["kind"] for h in X.HRE)
if _hc: lines.append(f'{P10 + 1}월 인사 변동 <b>{sum(_hc.values())}건</b> <span class="muted">(' + " · ".join(f"{k} {v}" for k, v in _hc.most_common()) + ")</span>")
summary_html = "".join(f"<li>{x}</li>" for x in lines)
def _rank_items(c):
    """클로잇 = 본부, 엔텍(본부 1개) = 사업부 단위"""
    if len(c["hqs"]) == 1:
        h = c["hqs"][0]
        return [(dv["name"], K("d", c["name"], h["name"], dv["name"]), dv["d"]) for dv in h["divs"] if dv["name"] != "(직속)" and (dv["d"]["T"][P10] or 0) > 0.005]
    return [(h["name"], K("h", c["name"], h["name"]), h["d"]) for h in c["hqs"] if (h["d"]["T"][P10] or 0) > 0.005]
_NOTE = set()
def _bd(key, d, f):
    b0 = base(key, d, f); tag = ""
    if PREV and b0 is None: b0 = d[f][P9]; tag = '<small class="bt">*</small>'; _NOTE.add(1)
    return dl(b0, d[f][P10]) + tag
def _gsvg(key, d, uid, w):
    return GA.sized(GA.pair(min(d["u"][P10], 100), min(d["g"][P10], 100), None, None, uid), w)
def _tgt(g):
    t = GA.TARGET; x = g - t
    return f'목표 {t:g}% 달성 <b>+{x:.2f}%p</b>' if x >= 0 else f'목표 {t:g}%까지 <b>−{abs(x):.2f}%p</b>'
def _gst(key, d, nr=False):
    _gn = val(d, "gn", P10) if nr else None
    if _gn is not None:
        return (f'<div class="gst"><div class="gs go two"><div class="gsi"><span>가득률</span><b>{d["g"][P10]:.2f}%</b>{cmp(key, d, "g", pre="%")}</div>'
                f'<div class="gsi"><span>가득률 (비매출 모수 제외)</span><b>{_gn:.2f}%</b>{cmp(key, d, "gn", pre="%")}</div></div>'
                f'<div class="gs gb"><span>가동률</span><b>{d["u"][P10]:.2f}%</b>{cmp(key, d, "u", pre="%")}</div></div>')
    return (f'<div class="gst"><div class="gs go"><span>가득률</span><b>{d["g"][P10]:.2f}%</b>{cmp(key, d, "g", pre="%")}</div>'
            f'<div class="gs gb"><span>가동률</span><b>{d["u"][P10]:.2f}%</b>{cmp(key, d, "u", pre="%")}</div></div>')
corp_cards = ""; rank_html = ""
for ci, c in enumerate(RT["corps"]):
    d = c["d"]; ck = K("c", c["name"])
    lis = ""
    for nm, key, dd in _rank_items(c):      # 조직 순서 그대로 (순위 아님)
        lis += (f'<li data-cn="{E(c["name"])}" data-nm="{E(nm)}" title="누르면 상세"><span class="rn">{E(nm)}</span><span class="pr"><span class="ru">{f2(dd["g"][P10])}%</span><span class="rd">{_bd(key, dd, "g")}</span></span>'
                f'<span class="pr"><span class="rv">{f2(dd["u"][P10])}%</span><span class="rd">{_bd(key, dd, "u")}</span></span></li>')
    unit_nm = "사업부별" if len(c["hqs"]) == 1 else "본부별"
    corp_cards += (f'<div class="cc2"><div class="cc2d">{_gsvg(ck, d, "cc%d" % ci, 480)}</div>'
                   f'<div class="cc2r"><div class="cch"><b>{E(c["name"])}</b><span>가동대상 {d["T"][P10]:.2f}MM · 대기 {d["idle"][P10]:.2f}MM</span></div>'
                   f'{_gst(ck, d, True)}<div class="rkt">{unit_nm}</div>'
                   f'<div class="rkh"><span></span><span class="hc">가득률</span><span class="hc">가동률</span></div><ol class="rkl">{lis}</ol></div></div>')
gcard = (f'<div class="card gcard"><h3>전사 MM 나침반</h3><div class="gdial">{_gsvg("ALL", D, "all", 480)}</div>{_gst("ALL", D)}'
         f'</div>')

# ---------- slide 2: 본부별 ----------
def mcell(key, d, f, unit="%p", pct=True):
    v = val(d, f, P10)
    bar = ""
    return f'<td class="mc"><div class="v">{f2(v)}{"%" if pct else ""}</div>{bar}{cmp(key, d, f, unit)}</td>'
def row_html(cls, name, key, d, attrs=""):
    _snap(key, d)
    return (f'<tr class="{cls}" {attrs}><td class="l">{name}</td><td class="tc">{d["T"][P10]:.2f}</td>'
            f'{mcell(key, d, "g")}{mcell(key, d, "u")}{mcell(key, d, "idle", "MM", False)}</tr>')
rows = ""
GD = []; SUBN = {}; CARDS = []; DVSID = {}
def gentry(id, name, c, key, d, par=None):
    e = dict(id=id, name=name, cn=c["name"], corp=(c["name"] if not par else None), T=round(d["T"][P10], 2), u=round(d["u"][P10], 2), g=round(d["g"][P10], 2),
             idle=round(d["idle"][P10], 2), pu=round(_pv(key, d, "u"), 2), pg=round(_pv(key, d, "g"), 2), pidle=round(_pv(key, d, "idle"), 2),
             mu=[round(min(float(v or 0), 100), 2) for v in d["u"][:12]], mg=[round(min(float(v or 0), 100), 2) for v in d["g"][:12]],
             fu=(round(min(d["u"][11], 100), 2) if P10 < 11 and d["u"][11] else None), fg=(round(min(d["g"][11], 100), 2) if P10 < 11 and d["g"][11] else None))
    if par: e["par"] = par
    GD.append(e); return e
def _sub(hid, h, c, name, key, d, dvname=None, tm=False):
    if name == h["name"]: return ""
    k = SUBN.get(hid, 0); SUBN[hid] = k + 1; sid = f"{hid}#{k}"
    e = gentry(sid, name, c, key, d, hid); e["corp"] = f'{c["name"]} · {h["name"]}'
    if dvname and not tm: DVSID[(hid, dvname)] = sid
    if tm:
        e["tm"] = 1; e["corp"] = f'{c["name"]} · {h["name"]} · {dvname}'
        if (hid, dvname) in DVSID: e["dv"] = DVSID[(hid, dvname)]
    return f' data-sid="{sid}"'
for c in RT["corps"]:
    rows += row_html("corp", E(c["name"]), K("c", c["name"]), c["d"])
    for hi, h in enumerate(c["hqs"]):
        hid = f'h{RT["corps"].index(c)}_{hi}'; hk = K("h", c["name"], h["name"])
        gentry(hid, h["name"], c, hk, h["d"])
        rows += row_html("hq", f'<span class="car">▸</span>{E(h["name"])}', hk, h["d"], f'data-hq="{hid}" tabindex="0" role="button" aria-expanded="false"')
        for dv in h["divs"]:
            if dv["name"] != "(직속)":
                if (dv["d"]["T"][P10] or 0) > 0.005:
                    dk = K("d", c["name"], h["name"], dv["name"])
                    rows += row_html("sub dv", E(dv["name"]), dk, dv["d"], f'data-p="{hid}" hidden' + _sub(hid, h, c, dv["name"], dk, dv["d"], dv["name"]))
            for t in dv["teams"]:
                nm = f'{t["name"]} (사업부 소속)' if dv["name"] != "(직속)" and t["name"] == dv["name"] else t["name"]
                if dv["name"] == "(직속)" and t["name"] == h["name"]: nm = f'{t["name"]} (본부 직속)'
                if (t["d"]["T"][P10] or 0) > 0.005:
                    tk = K("t", c["name"], h["name"], dv["name"], t["raw"])
                    extra = _sub(hid, h, c, nm, tk, t["d"]) if dv["name"] == "(직속)" else _sub(hid, h, c, nm, tk, t["d"], dv["name"], True)
                    rows += row_html("sub " + ("tm" if dv["name"] != "(직속)" else "dv"), E(nm), tk, t["d"], f'data-p="{hid}" hidden' + extra)
    # 카드: 본부가 1개뿐인 법인(엔텍)은 사업부 단위, 여러 개면 본부 단위
    if len(c["hqs"]) == 1: CARDS += [e["id"] for e in GD if e.get("par") == f'h{RT["corps"].index(c)}_0' and not e.get("tm")]
    else: CARDS += [f'h{RT["corps"].index(c)}_{hi}' for hi in range(len(c["hqs"]))]
GA_BY = {e["id"]: e for e in GD}
def _ge_svgs(e):
    kw = (e["pu"], e["pg"]); u = min(e["u"], 100); g = min(e["g"], 100); uid = "x" + e["id"].replace("#", "_")
    return dict(mini=("" if e.get("tm") else GA.sized(GA.pair(u, g, None, None, "m" + uid, True), 300)), big=GA.sized(GA.pair(u, g, None, None, "b" + uid), 480), sm="")
GDATA = dict(all=GD, cards=CARDS, subs={}, svg={e["id"]: _ge_svgs(e) for e in GD}, target=GA.TARGET, cm=P10)
for e in GD:
    if e.get("par") and not e.get("tm"): GDATA["subs"].setdefault(e["par"], []).append(e["id"])
GDATA_JSON = _j.dumps(GDATA, ensure_ascii=False).replace("</", "<\\/")
tot = row_html("tot", "전체", "ALL", D)
def _hq_bar():
    o = ""; cur = None
    for _id in CARDS:
        e = GA_BY[_id]; cn = e["cn"]
        if cn != cur:
            if cur is not None: o += "</div>"
            o += f'<div class="cgrp"><span class="cgl">{E(cn)}</span>'; cur = cn
        cls = "ok" if e["g"] >= 80 else ("mid" if e["g"] >= 70 else "lo")
        o += f'<button type="button" class="hqc {cls}" data-id="{_id}"><span class="hqn">{E(e["name"])}</span><b>{e["g"]:.1f}%</b></button>'
    return '<div id="hqbar"><span class="hql">전사 현황</span><div class="hqrow">' + o + '</div></div></div>'
HQ_BAR = _hq_bar()

# ---------- slide 3: 추이 ----------
lo, hi, tk = X._rng([D["u"], D["g"]])
chart = X.line_chart([("가득률", X.C2, D["g"]), ("가동률", X.C1, D["u"])], X.MON, W=1200, ymin=lo, ymax=hi, ticks=tk, est_from=X.CONF, cur=CUR, aria="월별 가득률·가동률", pad=(153.5, 45.5), end_labels=False)   # 월 위치 = 아래 표의 월 칸 가운데 (첫 칸 9% + 12등분)
# 마우스 올림 영역 (월별 세로 띠) — line_chart 기본 크기와 같은 좌표
_W, _pL, _pR, _pT, _pB, _H = 1200, 153.5, 45.5, 38, 30, 290
_n = len(X.MON); _st = (_W - _pL - _pR) / (_n - 1)
_Y = lambda v: _pT + (hi - v) / (hi - lo) * (_H - _pT - _pB)
hz = "".join(f'<rect class="hz" data-i="{i}" x="{_pL + i*_st - _st/2:.1f}" y="{_pT-4}" width="{_st:.1f}" height="{_H-_pT-_pB+4}" fill="transparent"/>' for i in range(_n))
hz += f'<line id="hzl" x1="0" x2="0" y1="{_pT-4}" y2="{_H-_pB}" stroke="#0F2942" stroke-opacity=".25" stroke-dasharray="3 3" visibility="hidden"/>'
hz += f'<circle id="hzu" r="5" fill="#fff" stroke="{X.C1}" stroke-width="2.5" visibility="hidden"/><circle id="hzg" r="5" fill="#fff" stroke="{X.C2}" stroke-width="2.5" visibility="hidden"/>'
chart = chart.replace("</svg>", hz + "</svg>", 1)
def _r(v): return None if v is None else round(v, 2)
TIP = [dict(m=X.MON[i], k=("실적" if i < X.CONF else ("당월" if i == CUR else "예상")),
            u=_r(D["u"][i]), g=_r(D["g"][i]), t=_r(D["T"][i]), idle=_r(D["idle"][i]),
            x=round(_pL + i*_st, 1), yu=round(_Y(D["u"][i]), 1) if D["u"][i] is not None else None, yg=round(_Y(D["g"][i]), 1) if D["g"][i] is not None else None)
       for i in range(_n)]
def _dcell(a, b):
    if a is None or b is None: return '<td class="z">—</td>'
    return f'<td>{dl(a, b)}</td>'
mtab = ('<table class="mt"><thead><tr><th class="l">월</th>' + "".join(f'<th class="{"cm" if i == CUR else ""}">{E(X.MON[i])}<small>{TIP[i]["k"]}</small></th>' for i in range(_n)) + '</tr></thead><tbody>'
        + "".join(f'<tr><td class="l"><b>{lb}</b></td>' + "".join(f'<td class="{"cm" if i == CUR else ""}">{"—" if D[k][i] is None else f"{D[k][i]:.2f}"}</td>' for i in range(_n)) + '</tr>'
                  f'<tr class="dr"><td class="l">전월 대비</td><td class="z">—</td>' + "".join(_dcell(D[k][i-1], D[k][i]) for i in range(1, _n)) + '</tr>' for lb, k in (("가득률 %", "g"), ("가동률 %", "u")))
        + '</tbody></table>')
import json as _json
TIP_JSON = _json.dumps(TIP, ensure_ascii=False).replace("</", "<\\/")
corp_line = '<div class="ycg-t" style="text-align:center;margin-bottom:2px">법인별 연간 추정</div><div class="cyg">' + "".join(
    f'<div class="cyi"><b>{E(c["name"])}</b><div class="cyd">{GA.sized(GA.pair(min(c["d"]["yu"], 100), min(c["d"]["yg"], 100), None, None, "cy%d" % _ci), 400)}</div></div>'
    for _ci, c in enumerate(RT["corps"])) + '</div>'

# ---------- slide 4: 대기 인력 (9·10월) ----------
def status(p):
    lv = X.leave_of(p)
    if lv: return (lv[0], "st-leave")
    if X.quit_txt(p): return ("퇴사", "st-leave")   # 당월 일부 근무 후 퇴사
    if p["exec"]: return ("비매출 모수", "st-mid")
    ms = p["idle"][P10:12]; i0, iL = ms[0], ms[-1]
    if sum(ms) <= 0.005: return (f"{P10 + 1}월 투입", "st-ok")
    if all(v > 0.005 for v in ms):
        if i0 >= 0.995: return ("미투입", "st-warn")
        return ("부분 투입", "st-mid")
    if i0 > 0.005 and iL <= 0.005: return ("투입 예정", "st-ok")
    if i0 <= 0.005: return ("종료 후 대기", "st-mid")
    return ("부분 투입", "st-mid")
idle_blocks = ""; n_show = 0; need = 0
IM = [P9] + list(range(P10, 12))   # 대기 표 월 열: 전월 · 당월 ~ 12월
OLD = list(range(0, P9))            # 그 이전 달(1~N월): 기본은 접어 둠 (관리자 화면과 같게)
K_OLD = len(OLD)
THEAD = ('<thead><tr><th class="l">성명</th><th class="l">소속</th><th class="l">직무</th><th class="l">직급</th>'
         + "".join(f'<th class="old">{m + 1}월</th>' for m in OLD)
         + f'<th>{P9 + 1}월<small>{"확정" if PM_OK else "잠정"}</small></th><th class="cm">{P10 + 1}월<small>당월</small></th>'
         + "".join(f'<th>{m + 1}월</th>' for m in range(P10 + 1, 12)) + '<th class="l">비고 · 현재·예정 투입</th><th>상태</th></tr></thead>')
def _idle(p): return p["idle"][P9] > 0.005 or p["idle"][P10] > 0.005
def _prow(p):
    global n_show, need
    st = status(p); n_show += 1; need += st[0] == "미투입"
    SUMMARY["people"][K(p["corp"], p["name"])] = round(p["idle"][P10], 4)
    plan = X._next_plan(p)
    ps = (plan[0][1] + (f" 외 {len(plan)-1}건" if len(plan) > 1 else "")) if plan else (X.quit_txt(p) or "미정")
    if p.get("idle_note"): ps = str(p["idle_note"]).strip()
    return (f'<tr data-a="{p["idle"][P9]:.4f}" data-b="{p["idle"][P10]:.4f}" data-mon="{sum(1 for v in p["idle"][:P10 + 1] if v >= 0.5)}" data-job="{X.job_key(p["직무"])}"{" data-exec=1" if p["exec"] else ""}><td class="l">{E(p["name"])}</td><td class="l">{X._org_br(E(p["org"]))}</td><td class="l">{E(p["직무"] or "—")}</td><td class="l">{E(p["직급"] or "—")}</td>'
            + "".join(f'<td class="old {"na" if p["T"][m] <= 0.005 else ("z" if p["idle"][m] <= 0.005 else "")}">{"" if p["T"][m] <= 0.005 else "%.2f" % p["idle"][m]}</td>' for m in OLD)
            + "".join(f'<td class="{"na" if p["T"][m] <= 0.005 else ("z" if p["idle"][m] <= 0.005 else "")}{" cm" if m == P10 else ""}">{"" if p["T"][m] <= 0.005 else "%.2f" % p["idle"][m]}</td>' for m in IM)
            + f'<td class="l pj" title="{E(ps)}">{E(ps)}{X.trn_html(p)}</td><td><span class="st {st[1]}">{E(st[0])}</span></td></tr>')
def _mm(d): return f'{P9 + 1}월 <span class="m9">{d["idle"][P9]:.2f}</span> · <b>{P10 + 1}월 <span class="m10">{d["idle"][P10]:.2f}</span></b>MM'
def dv_block(c, h, dv):
    """사업부 묶음: 팀별 소제목 + 사람"""
    trs = ""; n = 0
    for t in dv["teams"]:
        ppl = sorted([p for p in PP.values() if p["corp"] == c["name"] and p["hq"] == h["name"] and p["dv"] == dv["name"] and p["tm"] == t["raw"] and _idle(p)], key=lambda p: p["name"])
        if not ppl: continue
        tn = t["name"] if dv["name"] == "(직속)" or t["name"] != dv["name"] else f'{dv["name"]} (사업부 소속)'
        trs += f'<tr class="tmh"><td colspan="{6 + K_OLD + len(IM)}">{E(tn)} <span><span class="mn">{len(ppl)}</span>명 · 대기 {_mm(t["d"])}</span></td></tr>' + "".join(_prow(p) for p in ppl)
        n += len(ppl)
    if not n: return "", 0
    dn = f'{h["name"]} 소속' if dv["name"] == "(직속)" else dv["name"]
    return (f'<details class="dvb"><summary><span class="car">▸</span><b>{E(dn)}</b><span class="dmm">대기 {_mm(dv["d"])}</span><span class="muted"><span class="mn">{n}</span>명</span></summary>'
            f'<table class="it fold-old">{THEAD}<tbody>{trs}</tbody></table></details>'), n
for c in RT["corps"]:
    body = ""; c_n = 0
    for h in c["hqs"]:
        inner = ""; hn = 0
        for dv in h["divs"]:
            blk, n = dv_block(c, h, dv); inner += blk; hn += n
        if not hn: continue
        c_n += hn
        if len(c["hqs"]) == 1: body += f'<div class="ibb">{inner}</div>'   # 본부가 하나뿐인 법인(엔텍)은 바로 사업부 (들여쓰기는 같게 → 표 열 위치 통일)
        else:
            body += (f'<details class="ib" open><summary class="ibh"><span class="car">▸</span><b>{E(h["name"])}</b><span><span class="mn">{hn}</span>명 · 대기 {_mm(h["d"])}</span></summary>'
                     f'<div class="ibb">{inner}</div></details>')
    d = c["d"]
    idle_blocks += (f'<details class="cb" open><summary class="cbh"><span class="car">▸</span><b>{E(c["name"])}</b>'
                    f'<span class="cbm">{P10 + 1}월 대기 <em class="m10">{d["idle"][P10]:.2f}</em>MM <span class="muted"><span class="cbbase">· {BLs} {f2(base(K("c", c["name"]), d, "idle"))}MM {dl(base(K("c", c["name"]), d, "idle"), d["idle"][P10], "MM")} </span>· <span class="mn">{c_n}</span>명</span></span></summary>'
                    f'<div class="cbb">{body or "<p class=muted>대기 인원 없음</p>"}</div></details>')

# ---------- slide 5: 인사 변동 ----------
hr_rows = "".join(f'<tr><td><span class="st {"st-ok" if h["kind"] in ("입사", "복직") else ("st-warn" if h["kind"] == "퇴사" else "st-mid")}">{E(h["kind"])}</span></td>'
                  f'<td class="l">{E(h["name"])}</td><td class="l">{X._org_cell(h, E)}</td><td class="l">{E(X._job(h["corp"], h["name"]))}</td><td class="l">{E(X._rank(h["corp"], h["name"]))}</td><td>{h["date"]:%m.%d}</td><td class="l">{E(h["imp"])}</td></tr>' for h in X.HRE) \
          or f'<tr><td colspan="7">{P10 + 1}월 인사 변동 없음</td></tr>'

# ---------- 휴직 인원 (인사 변동 아래) ----------
_fd = lambda d: d.strftime("%y.%m.%d") if d else "—"
lv_rows = "".join(f'<tr><td class="l"><b>{E(r["name"])}</b></td><td class="l">{E(r["corp"])}</td><td class="l">{E(r["org"])}</td><td class="l">{E(r["직무"] or "—")}</td><td class="l">{E(r["직급"] or "—")}</td>'
                  f'<td>{_fd(r["start"])} ~ {_fd(r["end"])}</td>' + "".join(f'<td class="{"z" if v <= 0.005 else ""}">{v:.2f}</td>' for v in r["T"]) + f'<td class="l">{E(r["note"])}</td></tr>' for r in X.LEAVE_ROWS) \
          or f'<tr><td colspan="{7 + 12 - P10}">휴직 인원 없음</td></tr>'

# ---------- slide 6: 대기 변화 (자동) ----------
def _pbase(p):
    if PREV: return PREV["people"].get(K(p["corp"], p["name"]), 0.0)
    if PMB: return PMB["people"].get(K(p["corp"], p["name"]), 0.0)
    return p["idle"][P9]
new_idle, cleared = [], []
for p in PP.values():
    if X.leave_of(p) or p["exec"]: continue
    b0, c0 = _pbase(p), p["idle"][P10]
    if c0 > 0.005 and b0 <= 0.005: new_idle.append(p)
    elif b0 > 0.005 and c0 <= 0.005: cleared.append(p)
def _plan_s(p):
    plan = X._next_plan(p)
    return (plan[0][1] + (f" 외 {len(plan)-1}건" if len(plan) > 1 else "")) if plan else "—"
def _ptable(ps, kind):
    if not ps: return '<p class="empty">해당 인원 없음</p>'
    head = ('<thead><tr><th class="l">성명</th><th class="l">소속</th><th class="l">직무</th><th class="l">직급</th>'
            + ('<th>대기<small>' + f"{P10 + 1}월" + '</small></th><th>상태</th>' if kind == "new" else '<th>대기<small>' + E(BLs) + '</small></th><th class="l">투입 프로젝트</th>') + '</tr></thead>')
    trs = ""
    for p in sorted(ps, key=lambda p: (p["corp"], p["org"], p["name"])):
        lead = f'<td class="l"><b>{E(p["name"])}</b></td><td class="l">{X._org_br(E(p["org"]))}</td><td class="l">{E(p["직무"] or "—")}</td><td class="l">{E(p["직급"] or "—")}</td>'
        if kind == "new":
            st = status(p); trs += f'<tr>{lead}<td>{p["idle"][P10]:.2f}</td><td><span class="st {st[1]}">{E(st[0])}</span></td></tr>'
        else:
            ps_ = _plan_s(p); trs += f'<tr>{lead}<td>{_pbase(p):.2f}</td><td class="l pj" title="{E(ps_)}">{E(ps_)}</td></tr>'
    return f'<table class="at at-{kind}">{head}<tbody>{trs}</tbody></table>'
pchg = (f'<div class="pcg"><div class="pc pc-new"><h3>신규 대기 인력 <b>{len(new_idle)}명</b><small>{E(BLs)}엔 대기 없음 → 지금 대기</small></h3>{_ptable(new_idle, "new")}</div>'
        f'<div class="pc pc-clr"><h3>대기 해소 (투입) <b>{len(cleared)}명</b><small>{E(BLs)}엔 대기 → 지금 투입</small></h3>{_ptable(cleared, "clr")}</div></div>')

ICON_URI = "%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 512 512%22 width=%22512%22 height=%22512%22%3E%3Crect width=%22512%22 height=%22512%22 rx=%22112%22 fill=%22%230F2942%22/%3E%3Cpath d=%22M108.9,403.1 A208,208 0 0 1 103.8,114.2 L146.3,153.7 A150,150 0 0 0 149.9,362.1 Z%22 fill=%22%23E8847A%22/%3E%3Cpath d=%22M115.2,102.9 A208,208 0 0 1 396.8,102.9 L357.6,145.6 A150,150 0 0 0 154.4,145.6 Z%22 fill=%22%23F2CB5C%22/%3E%3Cpath d=%22M408.2,114.2 A208,208 0 0 1 403.1,403.1 L362.1,362.1 A150,150 0 0 0 365.7,153.7 Z%22 fill=%22%235FCB8A%22/%3E%3Cpolygon points=%22434.6,278.6 289.9,253.7 288.3,266.6%22 fill=%22%238DB6EC%22/%3E%3Cpolygon points=%22433.3,172.5 282.0,234.1 289.5,250.0%22 fill=%22%23F0A04B%22/%3E%3Ccircle cx=%22256%22 cy=%22256%22 r=%2230%22 fill=%22%23fff%22/%3E%3C/svg%3E"
CSS = r"""
:root{--navy:#0F2942;--steel:#2A5A9B;--line:#E3E8EF;--muted:#6B7280;--bg:#F4F6F9;--rise:#B42335;--fall:#2E8B60;--cm:#2A5A9B}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:#1F2937;font-family:"Pretendard","Malgun Gothic","Apple SD Gothic Neo",sans-serif;font-variant-numeric:tabular-nums}
.top{position:fixed;top:0;left:0;right:0;height:52px;background:var(--navy);color:#fff;display:flex;align-items:center;gap:16px;padding:0 24px;z-index:5}
.top b{font-size:17px}.top b.tbn{display:inline-flex;align-items:center}.tbi{width:28px;height:28px;border-radius:7px;margin-right:9px}.top .wk{opacity:.8;font-size:13px}.top .sp{flex:1}.top button{background:transparent;border:1px solid rgba(255,255,255,.4);color:#fff;padding:6px 12px;font:inherit;font-size:13px;cursor:pointer}
.top button:hover{background:rgba(255,255,255,.12)}.top .pg{font-size:13px;min-width:60px;text-align:center}
.deck{position:absolute;top:52px;left:0;right:0;bottom:0}
.slide{position:absolute;inset:0;padding:28px 40px 24px;overflow:auto;display:none}
.slide.on{display:block}
.slide h2{margin:0 0 4px;font-size:26px;color:var(--navy)}.slide .sub{color:var(--muted);font-size:14px;margin-bottom:18px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:10px}
.kpi{background:#fff;border-top:4px solid var(--navy);padding:18px 18px 14px}.kl{font-size:14px;color:#374151;font-weight:700}
.kv{font-size:40px;font-weight:800;color:var(--navy);margin:6px 0}.kv small{font-size:15px;font-weight:700;color:#4B5563}
.kc{display:flex;justify-content:space-between;font-size:13.5px;font-weight:700;color:#4B5563;border-top:1px solid var(--line);padding-top:8px}
.yr{margin-top:18px;background:#fff;padding:14px 18px;font-size:15px}.yr span{color:var(--muted);margin-right:6px}.yr .sep{margin:0 12px}
.rise{color:var(--rise);font-weight:700}.fall{color:var(--fall);font-weight:700}.flat{color:var(--muted)}
table{border-collapse:collapse;width:100%;background:#fff}th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:center;font-size:15px}
th{background:#EEF2F7;color:var(--navy);font-weight:700;font-size:14px}th small{display:block;font-weight:500;color:var(--muted);font-size:11px}
td.l,th.l{text-align:left}td.ind{padding-left:28px}tr.corp td{background:#F7F9FC;font-weight:700}tr.tot td{background:#3D5D84;color:#fff;font-weight:700}
tr.tot .rise,tr.tot .fall{color:#fff}td.cm,th.cm{background:#EAF1FA;font-weight:700}
.chart-card{background:#fff;padding:16px}.corp-line{margin-top:12px;font-size:15px;background:#fff;padding:12px 16px}
.lg{display:flex;gap:18px;font-size:13px;color:var(--muted);margin-bottom:6px}.lg i{display:inline-block;width:14px;height:3px;margin-right:5px;vertical-align:middle}
.ib{margin-bottom:18px}.ibh{display:flex;gap:12px;align-items:baseline;margin-bottom:6px}.ibh b{font-size:18px;color:var(--navy)}.ibh span{color:var(--muted);font-size:13.5px}
.it td{font-size:14px;padding:7px 8px}
table.it{table-layout:fixed;width:100%}
table.it th:nth-child(1){width:7%}table.it th:nth-child(2){width:12%}table.it th:nth-child(3){width:9%}table.it th:nth-child(4){width:6.5%}
{IT_W}
table.it td{overflow:hidden;text-overflow:clip;white-space:nowrap}.it td.z{color:#C0C4CC}.it td.pj{max-width:320px;white-space:nowrap;overflow:hidden;text-overflow:clip}
.st{display:inline-block;padding:2px 9px;font-size:12.5px;font-weight:700}.st-ok{background:#E3F1EB;color:#1F6F54}.st-warn{background:#F8ECE2;color:#A2551B}.st-mid{background:#EEF2F7;color:#3B597A}.st-leave{background:#F1EEF8;color:#5B4B8A}
.isgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.iss{background:#fff;padding:16px 18px;border-left:5px solid var(--fall)}.iss.up{border-left-color:var(--rise)}
.iss b{font-size:18px;color:var(--navy);margin-right:8px}.iss span{color:var(--muted);font-size:13px}.ifig{margin-top:8px;font-size:15px}
.cmt{margin-top:18px;background:#fff;padding:16px 18px;min-height:120px;color:var(--muted)}
.muted{color:var(--muted)}
.ccs{display:grid;grid-template-columns:1fr;gap:14px;margin-top:14px}.cc{background:#fff;padding:14px 18px;border-left:5px solid var(--steel)}
.cch{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}.cch b{font-size:18px;color:var(--navy)}.cch span{font-size:13.5px;color:var(--muted)}
.ccb{display:grid;grid-template-columns:1fr 1fr;gap:6px 22px}.cv{font-size:30px;font-weight:800;color:var(--navy);margin:2px 0 4px}.cv small{font-size:14px;color:var(--muted)}
.cy{grid-column:1/-1;font-size:13.5px;color:var(--muted);margin-top:4px}.cy b{color:#1F2937}
tr.sub[data-sid]{cursor:pointer}tr.sub[data-sid]:hover td{background:#F2F6FB}tr.sub[data-sid] td.l::before{content:'▸';display:inline-block;width:14px;color:#7FA0C8;font-size:.8em}tr.hq{cursor:pointer}tr.hq:hover td{background:#F2F6FB}tr.hq:focus-visible{outline:2px solid var(--steel);outline-offset:-2px}
.car{display:inline-block;width:16px;color:var(--steel);transition:transform .15s}tr.hq[aria-expanded=true] .car,details[open]>summary .car{transform:rotate(90deg)}
tr.sub td{font-size:14px;background:#FBFCFE;color:#374151}tr.sub td.cm{background:#EEF4FB}tr.sub td.l{padding-left:48px}tr.sub.tm td.l{padding-left:66px;color:var(--muted)}
.tg{margin-left:8px;border:1px solid var(--line);background:#fff;color:var(--navy);font:inherit;font-size:12.5px;padding:3px 10px;cursor:pointer}.tg:hover{background:#EEF2F7}
.cyg{display:flex;gap:24px;justify-content:center;flex-wrap:wrap}.cyi{flex:1 1 440px;max-width:560px;text-align:center}.cyi>b{display:block;font-size:15px;color:var(--navy);margin:2px 0 0}.cyd{display:flex;justify-content:center}.cyd svg{max-width:100%;height:auto}.chart-card{position:relative}.hz{cursor:crosshair}.s3g{display:grid;grid-template-columns:460px minmax(0,1fr);gap:10px;align-items:stretch}.s3m{min-width:0}.ycg{text-align:center;background:#fff;display:flex;flex-direction:column;justify-content:center;padding:8px}.ycg svg{width:100%;height:auto;display:block;margin:0 auto}.ycg-t{font-size:13px;font-weight:700;color:var(--muted);margin-bottom:2px}td.na{background:#E9ECF1!important}@media (max-width:1250px){.s3g{grid-template-columns:minmax(0,1fr)}.ycg{display:none}}#cc svg.chart{display:block;margin:0 auto;width:min(100%,calc(30vh * 4.138))}#cc.chart-card{padding:16px 0}#cc .lg{padding-left:16px;font-size:14px}#cc .lg span:nth-child(1){color:#2A5A9B;font-weight:700}#cc .lg span:nth-child(2){color:#B8691A;font-weight:700}body #gdet.on{justify-content:center;gap:clamp(30px,4.5vw,160px)}body #gdet .gtr svg{max-width:clamp(560px,38vw,1600px)}#cc .lg span:nth-child(1){color:#B8691A}#cc .lg span:nth-child(2){color:#2A5A9B}table.mt{max-width:calc(30vh * 4.138);margin-left:auto;margin-right:auto}
.tip{position:absolute;pointer-events:none;background:#0F2942;color:#fff;padding:10px 12px;font-size:13px;line-height:1.6;min-width:190px;box-shadow:0 4px 14px rgba(15,41,66,.25);z-index:3}
.tip b{font-size:14px}.tip .k{opacity:.7;margin-left:6px;font-size:12px}.tip .rise{color:#F0B48A}.tip .fall{color:#8EE0B6}.tip .flat{color:#C9D3DF}.tip i{display:inline-block;width:10px;height:3px;margin-right:6px;vertical-align:middle}
.mt{margin-top:12px}.mt th,.mt td{font-size:13px;padding:6px 4px}.mt tr.dr td{font-size:12px;border-bottom:2px solid var(--line)}.mt td.z{color:#C0C4CC}
details.cb{margin-bottom:16px;background:#fff;border-top:4px solid var(--navy)}summary{list-style:none;cursor:pointer}summary::-webkit-details-marker{display:none}
.cbh{display:flex;align-items:baseline;gap:12px;padding:12px 16px}.cbh b{font-size:21px;color:var(--navy)}.cbm{font-size:15px}.cbm em{font-style:normal;font-size:22px;font-weight:800;color:var(--navy);margin:0 2px}
.cbb{padding:0 16px 8px}.ibb{padding-left:22px}details.dvb{margin:0 0 4px;border-bottom:1px solid var(--line)}details.dvb>summary{display:flex;align-items:baseline;gap:14px;padding:8px 4px}details.dvb>summary:hover{background:#F5F8FC}details.dvb>summary b{font-size:16px;color:#1F3A5F;flex:0 0 270px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dmm{font-size:14.5px;flex:0 0 250px}.dmm b{color:var(--navy)}details.dvb[open]>table{margin:4px 0 12px}tr.tmh td{background:#F1F5FA;font-weight:700;color:var(--navy);text-align:left;font-size:13.5px}tr.tmh td span{font-weight:500;color:var(--muted);margin-left:10px}tr.tmh td span b{color:var(--navy)}details.ib{margin:0 0 14px}details.ib>summary{padding:6px 0;border-bottom:1px solid var(--line)}details.ib>summary:hover b{text-decoration:underline}
.st{white-space:nowrap}table td:nth-child(2),table td:nth-child(1){white-space:nowrap}th{white-space:nowrap}
.note{font-size:12px;color:var(--muted);margin-top:10px}
.pl{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:700;line-height:1.6;white-space:nowrap;vertical-align:middle}
.pl-up{background:#FBE4E6;color:#B42335}.pl-dn{background:#E1F2EA;color:#22744F}.pl-0{background:#EEF1F4;color:#6B7280}
tr.tot .pl-up,tr.tot .pl-dn,tr.tot .pl-0{background:rgba(255,255,255,.18);color:#fff}
.rkg{display:grid;grid-template-columns:1fr 1fr;gap:18px}.rkn{font-size:11.5px;color:var(--muted);margin-top:8px}.bt{font-size:12px;color:var(--muted);margin-left:2px}.rkc h4{margin:0 0 6px;font-size:13px;color:var(--muted);font-weight:700}
ol.rkl{list-style:none;margin:0;padding:0}ol.rkl li,.rkh{display:grid;grid-template-columns:minmax(90px,1fr) 78px 62px 74px 82px 64px 82px;align-items:center;padding:7px 4px;border-bottom:1px solid var(--line)}
.rk{width:20px;height:20px;border-radius:50%;background:#EEF2F7;color:var(--navy);font-size:11.5px;font-weight:800;display:flex;align-items:center;justify-content:center}
ol.rkl li:first-child .rk{background:var(--navy);color:#fff}.cc2 ol.rkl li{cursor:pointer}.cc2 ol.rkl li:hover{background:#F2F6FB}.rn{font-size:14.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:clip}
.rv{font-size:16px;font-weight:800;color:var(--navy);text-align:right;padding-right:8px}.ru{font-size:13.5px;color:#374151;text-align:right;padding-right:8px}
.rkh{font-size:11px;color:var(--muted);padding:0 4px 2px;border-bottom:1px solid var(--line)}.rkh .hcx{text-align:right;padding-right:8px;font-weight:700;color:var(--navy)}.rd{text-align:left}.bt{font-size:10.5px;color:var(--muted);margin-left:4px}
table.ht{table-layout:fixed}
table.hrt{table-layout:fixed}table.hrt th:nth-child(1){width:7%}table.hrt th:nth-child(2){width:8%}table.hrt th:nth-child(3){width:41%}table.hrt th:nth-child(4){width:10%}table.hrt th:nth-child(5){width:8%}table.hrt th:nth-child(6){width:7%}table.hrt th:nth-child(7){width:19%}
table.hrt td{white-space:nowrap;overflow:hidden;text-overflow:clip}
table.mt{table-layout:fixed}table.mt th:first-child{width:9%!important}table.mt th:not(:first-child){width:calc(91% / 12)}table.mt{width:100%}.mt th,.mt td{font-size:clamp(13px,.8vw,24px);padding:clamp(6px,.45vw,12px) 4px}.mt th small{font-size:clamp(10px,.6vw,16px)}.mt tr.dr td{font-size:clamp(12px,.74vw,22px)}.mt .pl{font-size:clamp(11px,.7vw,20px);padding:.15em .6em}.corp-line{font-size:clamp(15px,.9vw,26px)}
.pcg{grid-template-columns:1fr 1fr;align-items:start}.pc{border-top:4px solid var(--steel);padding:14px 16px}.pc-new{border-top-color:#B4541E}.pc-clr{border-top-color:#1F5FA8}
.pc h3{display:flex;align-items:baseline;gap:8px;margin-bottom:10px}.pc h3 b{font-size:20px;color:var(--navy)}.pc h3 small{margin-left:auto}
table.at{table-layout:fixed;width:100%}table.at td,table.at th{font-size:13.5px;padding:7px 8px;white-space:nowrap;overflow:hidden;text-overflow:clip}
table.at th:nth-child(1){width:15%}table.at th:nth-child(2){width:22%}table.at th:nth-child(3){width:14%}table.at th:nth-child(4){width:11%}table.at th:nth-child(5){width:12%}table.at th:nth-child(6){width:26%}
h3.sh{margin:22px 0 8px;font-size:17px;color:var(--navy);display:flex;align-items:baseline;gap:8px}h3.sh b{color:#5B4B8A}h3.sh small{font-weight:500;color:var(--muted);font-size:12.5px}
table.lvt{table-layout:fixed}table.lvt th:nth-child(1){width:7%}table.lvt th:nth-child(2){width:11%}table.lvt th:nth-child(3){width:20%}table.lvt th:nth-child(4){width:11%}table.lvt th:nth-child(5){width:6%}table.lvt th:nth-child(6){width:14%}
{LV_W}table.lvt td{white-space:nowrap;overflow:hidden;font-size:14px}table.lvt td.z{color:#C0C4CC}
.empty{color:var(--muted);padding:18px 4px;margin:0}
.cmp{font-size:12.5px;color:var(--muted);margin-top:2px;white-space:nowrap}.cmp .rise,.cmp .fall,.cmp .flat{font-size:12.5px}
.m-only{display:none}body.show-m .m-only{display:block}.gst .m-only{display:block}.kc{display:block}.kc .cmp{font-size:13.5px;font-weight:700}
.row2{display:grid;grid-template-columns:1fr 1.1fr;gap:14px;margin-top:14px}.card{background:#fff;padding:14px 18px}.card h3{margin:0 0 10px;font-size:16px;color:var(--navy)}
ul.sum{margin:0;padding-left:18px;font-size:15.5px;line-height:1.9}ul.sum b{color:var(--navy)}
.lgd{font-size:12px;color:var(--muted);font-weight:500;margin-left:10px}.lgd i{display:inline-block;width:12px;height:8px;margin:0 4px 0 8px;vertical-align:middle}
i.bu,.bl i.bu{background:#2A5A9B}i.bg,.bl i.bg{background:#C17A2B}
.br{display:grid;grid-template-columns:150px 1fr;align-items:center;gap:10px;margin:5px 0}.bn{font-size:14px;font-weight:600;color:#1F2937;white-space:nowrap;overflow:hidden;text-overflow:clip}
.bl{display:flex;align-items:center;gap:8px;height:13px;margin:2px 0}.bl i{display:block;height:9px;border-radius:2px}.bl em{font-style:normal;font-size:12px;color:#374151;min-width:52px}
table.ht td{vertical-align:middle}table.ht td.mc{text-align:left;padding:8px 14px}table.ht th:nth-child(1){width:26%}table.ht th:nth-child(2){width:10%}table.ht th:nth-child(3),table.ht th:nth-child(4){width:24%}table.ht th:nth-child(5){width:16%}
td.mc .v{font-size:19px;font-weight:800;color:var(--navy)}tr.sub td.mc .v{font-size:15px}td.tc{font-size:15px}
i.mb{display:block;height:5px;background:#EEF2F7;margin:3px 0 2px;max-width:180px}i.mb b{display:block;height:100%;background:#2A5A9B}
tr.tot td.mc .v{color:#fff}tr.tot .cmp{color:#DCE6F2}tr.tot i.mb{background:rgba(255,255,255,.25)}tr.tot i.mb b{background:#fff}
tr.hq td.l{padding-left:28px}
.pcg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:16px}.pc{background:#fff;padding:14px 18px}.pc h3{margin:0 0 8px;font-size:16px;color:var(--navy)}.pc h3 small{font-weight:500;color:var(--muted);font-size:12px;margin-left:6px}
ul.pl{margin:0;padding-left:18px;columns:2;font-size:14px;line-height:1.8}
.s1g{display:grid;grid-template-columns:560px minmax(0,1fr);gap:14px;margin-top:10px;align-items:stretch}.s1r{display:flex;flex-direction:column;gap:14px;min-width:0}
.s1r .kpis{grid-template-columns:repeat(3,1fr);margin-top:0}.s1r .yr{margin-top:0;display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:14px 16px 14px 0}.yr .yl{padding-left:18px}.yr .yrr{padding-left:10px}.s1r .yr{font-size:15px;line-height:1.7;background:#fff}.yr .yl>span,.yr .yrr>span{font-weight:700;color:var(--navy);font-size:14px}.yr.pm{grid-template-columns:300px 1fr 1fr;align-items:center}.pmg{padding-left:8px}.yr3{display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;background:#fff;padding:12px 18px;font-size:15px;margin-top:10px}.yr3 span{color:var(--muted);margin-right:6px}.pmc em{font-style:normal;font-weight:700;color:var(--navy);display:inline-block;min-width:110px}.s1r .sumc{flex:1}
ul.sum{font-size:17px!important;line-height:2.25!important}.gc svg{width:100%;max-width:100%;height:auto}.cc2d svg,.gdial svg{width:480px;max-width:100%;height:auto}.gcard{text-align:center}.gcard h3{text-align:left}.gdial{display:flex;justify-content:center}
.gst{display:grid;grid-template-columns:1fr 1fr;gap:10px;text-align:left;margin-top:6px}.gs{padding:6px 10px;border-top:3px solid #C77B2B}.gs.gb{border-top-color:#7FA8DA}.gs span{font-size:12.5px;color:var(--muted)}.gs b{display:block;font-size:22px}.gs.go b{color:#B8691A}.gs.gb b{color:#2A5A9B}
.gtg{font-size:13.5px;color:#374151;margin-top:8px}.gtg b{color:var(--navy)}.gleg{font-size:12px;color:var(--muted);margin-top:6px}.gleg i{display:inline-block;width:14px;height:4px;margin:0 4px 0 8px;vertical-align:middle;background:#C77B2B}.gleg i.gb{background:#7FA8DA}.gleg i.gg{background:#BFC9D8}
.cc2{background:#fff;display:grid;grid-template-columns:var(--ccw,518px) minmax(0,1fr);gap:10px 35px;padding:14px 16px;min-width:0;overflow:hidden;align-items:center;border-left:5px solid var(--steel)}.cc2d{text-align:center;display:flex;justify-content:center;align-items:center}.cc2r{min-width:0}.cc2 .rkt{font-size:12.5px;font-weight:700;color:var(--muted);margin:10px 0 2px}.cc2 .cch{margin-bottom:4px}
.cc2 .gs b{font-size:18px}.cc2 .rkl .pl{font-size:11.5px;padding:1px 7px}.cc2 .rn{font-size:14px}.cc2 .rm{text-align:right;padding-right:10px;font-size:13.5px;color:#4A5A70;font-variant-numeric:tabular-nums}.cc2 .rkh .rm{font-size:11.5px;font-weight:700;color:#4B5563}.cc2 .rv{font-size:15px;padding-right:6px}.cc2 .ru{font-size:15px;font-weight:800;color:var(--navy);padding-right:6px}.cc2 .gst{gap:8px}.cc2 .gs span{font-size:15px;font-weight:600;color:#4B5563}.gs.go.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr);gap:0 12px;align-items:start}.gs.go.two .gsi{flex:0 0 auto}.gs.go.two .gsi:last-child b{color:#8A5A1F}.lgd{display:flex;gap:18px;font-size:15px;font-weight:700;margin:2px 0 8px}.lgd .lu{color:#2A5A9B}.lgd .lo{color:#C77B2B}.fbar{display:flex;gap:18px;align-items:center;margin:2px 0 10px;font-size:14px}.fbar label{display:inline-flex;align-items:center;gap:6px;cursor:pointer}.fbar select{font:inherit;padding:3px 6px;border:1px solid #C9D2DF;background:#fff}tr.flt{display:none!important}.cc2 ol.rkl li,.cc2 .rkh{grid-template-columns:minmax(120px,1.3fr) minmax(0,.8fr) minmax(0,.7fr) minmax(0,.8fr) minmax(0,.7fr)}.cc2 .rkh .hc{grid-column:span 2;text-align:center;font-weight:700;color:var(--navy)}.cc2 .rd{padding-left:4px}.cc2 .rm{padding-right:18px}.cc2 .rkl .pl{font-size:11px;padding:1px 5px}.gcard{display:flex;flex-direction:column}.gcard .gdial{margin:auto 0}.gcard{padding-bottom:0}.gcard .gst{flex:none;margin-top:auto;box-sizing:border-box;align-items:stretch}.gcard .gst .gs{padding:0 18px;display:flex;flex-direction:column;justify-content:center}.gcard .gst .gs>span{font-size:15px;font-weight:700;color:#4B5563}.gcard .gst .gs>b{font-size:40px;line-height:1.1;margin:4px 0 8px}.gcard .gst .gs .cmp{font-size:14px;color:#6B7280}.gcard .gst .gs .cmp .pl{font-size:13px}.gcard .gst .m-only{display:none}body.show-m .gcard .gst .m-only{display:block}.gcard .gst .gs{display:flex;flex-direction:column;justify-content:center}.cc2 ol.rkl li,.cc2 .rkh{grid-template-columns:calc(50% + 5px) minmax(0,1fr) minmax(0,1fr);column-gap:0}.cc2 .pr{display:flex;align-items:center;justify-content:flex-start;gap:6px;min-width:0;padding-left:10px}.cc2 .rkh .hc{grid-column:auto;text-align:left;padding-left:10px}.cc2 .rv,.cc2 .ru{padding-right:0}.cc2 .rd{padding-left:0}
#gcards{display:flex;flex-wrap:wrap;gap:8px 26px;margin:6px 0 12px;align-items:center}.cgrp{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:12px;flex:var(--n) 1 calc(var(--n)*215px);min-width:calc(var(--n)*170px)}
.gc{background:#fff;padding:12px 10px 10px;text-align:center;min-width:0;cursor:pointer;border:2px solid transparent;transition:transform .18s,box-shadow .18s,border-color .18s}.gc:hover{border-color:#B9C7DA}
.gc.sel{border-color:#1F3A5F;transform:scale(1.05);box-shadow:0 8px 22px rgba(15,41,66,.18);z-index:2;position:relative}
.gc .gcn{font-size:15px;font-weight:700;color:#4A5A70;margin-bottom:1px}.gc .ghn{font-size:15px;font-weight:800;color:var(--navy);margin-bottom:2px}.gc .gs1{font-size:12px;color:var(--muted);margin-top:2px}.gc .gs2{font-size:12.5px;color:#2A5A9B;margin-top:3px}.gc .gw{font-size:12px;color:var(--rise);font-weight:700;margin-top:3px}
.cgrp{display:flex;flex-wrap:wrap;gap:8px;align-items:center;flex:none;min-width:0}.cgl{font-size:13px;font-weight:700;color:#4A5A70;margin-right:2px}
.hqc{background:#fff;border:2px solid #D5DEEA;padding:7px 15px;display:inline-flex;gap:10px;align-items:baseline;cursor:pointer;border-radius:999px;font-size:15px;font-weight:700;color:var(--navy);font-family:inherit}.hqc b{font-size:16px;color:#2E7D4F}.hqc.mid b{color:#B8791A}.hqc.lo b{color:#C0392B}.hqc:hover{border-color:#7FA0C8}
.gc.hqc.sel,.hqc.sel{transform:none;box-shadow:none;background:#1F3A5F;border-color:#1F3A5F;color:#fff}.hqc.sel b{color:#fff}
#hqbar .cgrp{flex:0 1 auto}#hqbar .hqrow{flex:1 1 100%}#hqbar{background:#fff;padding:10px 16px;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center}.hql{font-size:15px;color:var(--navy);font-weight:700;border:2px solid var(--navy);border-radius:999px;padding:6px 16px;background:#fff}.hqrow{display:flex;flex-wrap:wrap;gap:8px 26px;align-items:center}
.hqbk{border:1px solid #1F3A5F;background:#fff;color:#1F3A5F;font:inherit;font-weight:700;font-size:14px;padding:6px 14px;border-radius:999px;cursor:pointer;margin-right:6px}.hqbk:hover{background:#1F3A5F;color:#fff}
#gsub{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px;padding-left:4px}#gsub:empty{display:none}.hqc.sub{padding:5px 13px;font-size:14px}
.gtip{position:absolute;pointer-events:none;background:#0F2942;color:#fff;padding:8px 12px;font-size:13px;line-height:1.6;box-shadow:0 4px 14px rgba(15,41,66,.25);z-index:5;white-space:nowrap}
#gdet{display:none;background:#fff;border:2px solid #1F3A5F;margin:0 0 14px;padding:14px 20px;position:relative;font-size:14px;line-height:1.5}#gdet.on{display:flex;gap:30px;align-items:center}
#gdet .gx{position:absolute;right:12px;top:10px;border:1px solid #C9D2DF;background:#fff;padding:3px 10px;cursor:pointer;font-size:12.5px}
.gtr{margin-top:12px}.gtr svg{width:100%;max-width:560px;height:auto;display:block}#gdet h3{font-size:19px;color:var(--navy);margin:0 0 2px}#gdet .gsb{font-size:13px;color:var(--muted);margin-bottom:12px}
#gdet .gk{display:flex;gap:26px;flex-wrap:wrap}#gdet .gk>div{min-width:150px;padding-top:6px;font-size:14px;line-height:1.6}#gdet .gk b{font-size:14px}#gdet .gk b.n{font-size:24px;display:block;line-height:1.2}#gdet .gh{margin-top:12px;font-size:13px;color:var(--muted)}
#gdet .sg{margin-left:auto;border-left:1px solid #E1E7F0;padding:4px 40px 0 26px}#gdet .sgt{font-size:13px;font-weight:700;color:var(--navy);margin-bottom:6px}#gdet .sgl{display:flex;gap:10px;flex-wrap:wrap;max-width:560px}
#gdet .sgi{width:124px;text-align:center;padding:6px 3px;border:2px solid transparent;cursor:pointer;font-size:12.5px;line-height:1.35}#gdet .sgi:hover{border-color:#B9C7DA}#gdet .sgi.on{border-color:#1F3A5F;background:#F5F8FC}
#gdet .sgn{font-weight:700;color:var(--navy);font-size:12.5px;min-height:34px;display:flex;align-items:center;justify-content:center}#gdet .sgh{font-size:11.5px;color:var(--muted);margin-top:6px}
.glg2{font-size:12.5px;color:var(--muted);margin:-4px 0 12px}
table.ht tr.hq.hsel td,table.ht tr.sub.hsel2 td{background:#E8EFF8!important}
.up{color:var(--rise);font-weight:700}.dn{color:var(--fall);font-weight:700}.fl{color:var(--muted)}
#gdet>div:nth-child(2){flex:0 0 clamp(480px,24vw,1100px)!important}#gdet>div:nth-child(2) svg{width:100%;max-width:100%;height:auto}.gtr svg{max-width:clamp(560px,28vw,1200px)}#gdet .sgl{max-width:clamp(560px,28vw,1200px)}
body #gdet.on{justify-content:stretch;gap:0}body #gdet.on>div:nth-child(2){flex:1 1 0!important;min-width:0;display:flex;align-items:center;justify-content:center}body #gdet.on>div:nth-child(2) svg{width:100%;max-width:clamp(560px,30vw,1300px)}body #gdet.on>div:nth-child(3){flex:1 1 0;min-width:0}body #gdet.on>div:nth-child(3)>*{width:min(100%,clamp(600px,34vw,1500px));margin-left:auto;margin-right:auto;box-sizing:border-box}
@media print{#gdet{display:none!important}}

@media print{.top,.tg,.tip{display:none!important}tr.sub{display:table-row!important}.deck{position:static}.slide{display:block!important;position:static;page-break-after:always;overflow:visible;padding:14mm}
 @page{size:A4 landscape;margin:0} body{background:#fff}}
"""
JS = r"""
const S=[...document.querySelectorAll('.slide')];let i=0;
function go(n){i=Math.max(0,Math.min(S.length-1,n));S.forEach((s,k)=>s.classList.toggle('on',k===i));document.getElementById('pg').textContent=(i+1)+' / '+S.length;location.hash='s'+(i+1)}
document.addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();go(i+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();go(i-1)}if(e.key==='Home')go(0);if(e.key==='End')go(S.length-1)});
/* 화면 비례 확대: 큰 화면·전체 화면에서 옆이 휑하지 않게, 슬라이드 전체를 같은 비율로 키움 (1500px 기준 · 1~2배) */
(function(){const yr=document.querySelector('.s1r .yr'),gs=document.querySelector('.gcard .gst');if(!yr||!gs)return;function sync(){const t=yr.getBoundingClientRect().height;if(!t)return;gs.style.height='100px';const k=gs.getBoundingClientRect().height/100;if(!k)return;gs.style.height=(t/k)+'px'}
 sync();if(window.ResizeObserver){const ro=new ResizeObserver(sync);ro.observe(yr);ro.observe(document.querySelector('.gcard'))}addEventListener('resize',()=>setTimeout(sync,80));addEventListener('load',sync);document.addEventListener('fullscreenchange',()=>setTimeout(sync,120));document.addEventListener('click',()=>setTimeout(sync,60));setTimeout(sync,300);setTimeout(sync,1200)})();
(function(){const DW=1500,DH=830,TOP=52,d=document.querySelector('.deck'),tp=document.querySelector('.top');
 function fit(){if(!matchMedia('screen').matches)return;const w=innerWidth,h=innerHeight;let z=Math.max(Math.min(w/DW,(h-TOP)/DH),w/1900);z=Math.max(1,Math.min(2,z));z=Math.round(z*100)/100;
  document.documentElement.style.setProperty('--u',z>1?'0px':'');tp.style.zoom=z>1?z:'';d.style.top=(TOP*(z>1?z:1))+'px';S.forEach(s=>s.style.zoom=z>1?z:'')}
 fit();addEventListener('resize',fit);document.addEventListener('fullscreenchange',()=>setTimeout(fit,60))})();
document.getElementById('prev').onclick=()=>go(i-1);document.getElementById('next').onclick=()=>go(i+1);
const mt=document.getElementById('mtog');if(mt)mt.onclick=()=>{const o=document.body.classList.toggle('show-m');mt.textContent=o?'전월 확정 비교 숨기기':'{ML_JS} 대비 보기'};
document.getElementById('full').onclick=()=>{document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen()};
document.querySelectorAll('tr.hq').forEach(r=>{const t=()=>{const o=r.getAttribute('aria-expanded')!=='true';r.setAttribute('aria-expanded',o);document.querySelectorAll('tr.sub[data-p="'+r.dataset.hq+'"]').forEach(x=>x.hidden=!o)};r.onclick=t;r.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();t()}}});
(function(){const b=document.getElementById('idold');if(!b)return;const t0=b.textContent;b.onclick=()=>{const fold=document.querySelector('table.it').classList.contains('fold-old');document.querySelectorAll('table.it').forEach(t=>t.classList.toggle('fold-old',!fold));b.textContent=fold?t0.replace('펼치기','접기'):t0;requestAnimationFrame(()=>fit())}})();
document.getElementById('idopen').onclick=()=>document.querySelectorAll('details.cb,details.ib,details.dvb').forEach(d=>d.open=true);
document.getElementById('idclose').onclick=()=>{document.querySelectorAll('details.cb,details.ib').forEach(d=>d.open=true);document.querySelectorAll('details.dvb').forEach(d=>d.open=false)};
window.addEventListener('beforeprint',()=>document.querySelectorAll('details').forEach(d=>d.open=true));
(function(){const cc=document.getElementById('cc'),tip=document.getElementById('tip'),svg=cc.querySelector('svg'),L=document.getElementById('hzl'),cu=document.getElementById('hzu'),cg=document.getElementById('hzg');
 const f=v=>v==null?'—':v.toFixed(2);
 const d=(a,b,u)=>{if(a==null||b==null)return '<span class="flat">전월 없음</span>';const x=b-a;if(Math.abs(x)<0.005)return '<span class="flat">±0.00'+u+'</span>';return '<span class="'+(x>0?'rise':'fall')+'">'+(x>0?'▲ ':'▼ ')+Math.abs(x).toFixed(2)+u+'</span>'};
 function show(i){const t=TIP[i],p=i>0?TIP[i-1]:null;
  L.setAttribute('x1',t.x);L.setAttribute('x2',t.x);L.setAttribute('visibility','visible');
  [[cu,t.yu],[cg,t.yg]].forEach(([c,y])=>{if(y==null){c.setAttribute('visibility','hidden')}else{c.setAttribute('cx',t.x);c.setAttribute('cy',y);c.setAttribute('visibility','visible')}});
  tip.innerHTML='<b>'+t.m+'</b><span class="k">'+t.k+'</span><br><i style="background:#E0A060"></i>가득률 <b>'+f(t.g)+'%</b> '+d(p&&p.g,t.g,'%p')+'<br><i style="background:#6FA0E0"></i>가동률 <b>'+f(t.u)+'%</b> '+d(p&&p.u,t.u,'%p')+'<br><span class="k" style="margin:0">가동대상 '+f(t.t)+'MM · 대기 '+f(t.idle)+'MM</span>';
  tip.hidden=false;const r=svg.getBoundingClientRect(),cr=cc.getBoundingClientRect(),sc=r.width/1200;let x=r.left-cr.left+t.x*sc+14;
  if(x+tip.offsetWidth>cc.clientWidth-6)x=r.left-cr.left+t.x*sc-tip.offsetWidth-14;tip.style.left=x+'px';tip.style.top=(r.top-cr.top+40*sc)+'px'}
 function hide(){tip.hidden=true;[L,cu,cg].forEach(e=>e.setAttribute('visibility','hidden'))}
 svg.querySelectorAll('.hz').forEach(z=>{z.addEventListener('mouseenter',()=>show(+z.dataset.i))});svg.addEventListener('mouseleave',hide)})();
function fit(root){(root||document).querySelectorAll('table.it td,table.hrt td,table.lvt td,table.ht td.l,table.mt td,.rn,.cch b').forEach(el=>{if(!el.offsetParent)return;el.style.fontSize='';el.style.whiteSpace='';let fs=parseFloat(getComputedStyle(el).fontSize),n=0;while(el.scrollWidth>el.clientWidth+1&&fs>11.5&&n<20){fs-=0.5;el.style.fontSize=fs+'px';n++}if(el.scrollWidth>el.clientWidth+1){el.style.whiteSpace='normal';el.style.lineHeight='1.3'}})}
const _go=go;go=function(n){_go(n);requestAnimationFrame(()=>fit(S[i]))};
document.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>fit(d)));
document.querySelectorAll('tr.hq').forEach(r=>r.addEventListener('click',()=>requestAnimationFrame(()=>fit())));
window.addEventListener('resize',()=>fit(S[i]));
window.addEventListener('beforeprint',()=>{document.querySelectorAll('.slide').forEach(x=>fit(x))});
const h=parseInt((location.hash||'').replace('#s',''));go(isNaN(h)?0:h-1);
"""
JSF = r"""
(function(){const ex=document.getElementById('mex'),ld=document.getElementById('mld'),jb=document.getElementById('mjob'),sl=document.querySelectorAll('.slide')[3];if(!ex||!sl)return;
const hdrs=[...sl.querySelectorAll('tr.tmh td, details>summary')];const orig=new Map();hdrs.forEach(h=>orig.set(h,h.innerHTML));
const f2=v=>v.toFixed(2);
function setH(h,rows){const sum=k=>rows.reduce((a,r)=>a+(+r.dataset[k]),0);const q=c=>h.querySelector(c);
 const a=q('.m9'),b=q('.m10'),n=q('.mn');if(a)a.textContent=f2(sum('a'));if(b)b.textContent=f2(sum('b'));if(n)n.textContent=rows.length;const cb=q('.cbbase');if(cb)cb.style.display='none'}
function run(){const hideEx=!ex.checked,minM=+ld.value,q=jb?(jb.value||'').replace(/\s+/g,'').toLowerCase().replace(/^전체직무$/,''):'',act=hideEx||minM>0||!!q;
 const all=[...sl.querySelectorAll('tr[data-b]')];all.forEach(r=>r.classList.toggle('flt',act&&((hideEx&&!!r.dataset.exec)||(minM&&+r.dataset.mon<minM)||(q&&(r.dataset.job||'').indexOf(q)<0))));
 hdrs.forEach(h=>h.innerHTML=orig.get(h));
 sl.querySelectorAll('tr.tmh').forEach(t=>t.classList.remove('flt'));sl.querySelectorAll('details').forEach(d=>d.style.display='');
 if(!act)return;
 sl.querySelectorAll('tbody').forEach(tb=>{let cur=null,rs=[];const fin=()=>{if(cur){const vis=rs.filter(r=>!r.classList.contains('flt'));setH(cur.querySelector('td'),vis);cur.classList.toggle('flt',!vis.length)}};
  [...tb.children].forEach(tr=>{if(tr.classList.contains('tmh')){fin();cur=tr;rs=[]}else if(tr.dataset.b!==undefined)rs.push(tr)});fin()});
 [...sl.querySelectorAll('details')].reverse().forEach(d=>{const vis=[...d.querySelectorAll('tr[data-b]')].filter(r=>!r.classList.contains('flt'));setH(d.querySelector(':scope>summary'),vis);if(!vis.length)d.style.display='none';else if(q)d.open=true})}
[ex,ld].forEach(e=>e.addEventListener('change',run));if(jb)['input','change'].forEach(ev=>jb.addEventListener(ev,run))})();
"""
JS2 = r"""
(function(){const S2=document.querySelectorAll('.slide')[1],tb=S2.querySelector('table.ht'),box=document.getElementById('gcards'),det=document.getElementById('gdet');
const A={};GD.all.forEach(x=>A[x.id]=x);const CID=new Set(GD.cards);const f=v=>v.toFixed(2),T=GD.target;
const dl=(a,b,u)=>{const x=b-a;if(Math.abs(x)<0.005)return '<span class="fl">±0.00'+u+'</span>';return '<span class="'+(x>0?'up':'dn')+'">'+(x>0?'+':'−')+Math.abs(x).toFixed(2)+u+'</span>'};
const over=r=>r.g>100.005||r.u>100.005;
const gcHtml=id=>{const r=A[id];return '<div class="gc hqc '+(r.g>=80?'ok':(r.g>=70?'mid':'lo'))+'" data-id="'+id+'" role="button" tabindex="0"><span class="hqn">'+r.name+'</span><b>'+r.g.toFixed(1)+'%</b></div>'};
const grp=[];GD.cards.forEach(id=>{const c=A[id].cn;let g=grp[grp.length-1];if(!g||g.c!==c){g={c:c,ids:[]};grp.push(g)}g.ids.push(id)});
const sub=document.getElementById('gsub');
box.innerHTML='<button type="button" class="hqbk" id="hqback">◀ 전사 현황</button>'+grp.map(g=>'<div class="cgrp"><span class="cgl">'+g.c+'</span>'+g.ids.map(gcHtml).join('')+'</div>').join('');
document.getElementById('hqback').onclick=()=>go(0);
const cards=[...box.querySelectorAll('.gc')];let cur=null;
const hrows=()=>[...tb.querySelectorAll('tr.hq')];
const setRow=(r,o)=>{r.setAttribute('aria-expanded',o);tb.querySelectorAll('tr.sub[data-p="'+r.dataset.hq+'"]').forEach(x=>x.hidden=!o)};
function trend(r){const W=540,H=184,pl=40,pr=14,pt=30,pb=26,cm=GD.cm;const all=r.mu.concat(r.mg);const lo=0,hi=100;
 const X=i=>pl+(W-pl-pr)*i/11,Y=v=>pt+(H-pt-pb)*(1-(v-lo)/(hi-lo));let o='';
 [lo,(lo+hi)/2,hi].forEach(v=>{o+='<line x1="'+pl+'" x2="'+(W-pr)+'" y1="'+Y(v)+'" y2="'+Y(v)+'" stroke="#E3E8EF"/><text x="'+(pl-6)+'" y="'+(Y(v)+4)+'" font-size="11" fill="#7B8AA0" text-anchor="end">'+v+'%</text>'});
 for(let i=0;i<12;i++)o+='<text x="'+X(i)+'" y="'+(H-6)+'" font-size="11" fill="'+(i===cm?'#0F2942':'#7B8AA0')+'" font-weight="'+(i===cm?800:500)+'" text-anchor="middle">'+(i+1)+'월</text>';
 o+='<rect x="'+(X(cm)-14)+'" y="'+pt+'" width="28" height="'+(H-pt-pb)+'" fill="#2A5A9B" opacity=".08"/>';
 const line=(a,c)=>{let act='',fc='';a.forEach((v,i)=>{const p=X(i).toFixed(1)+','+Y(v).toFixed(1);if(i<=cm)act+=(act?'L':'M')+p;if(i>=cm)fc+=(fc?'L':'M')+p});
  return '<path d="'+act+'" fill="none" stroke="'+c+'" stroke-width="2.5"/>'+(fc&&cm<11?'<path d="'+fc+'" fill="none" stroke="'+c+'" stroke-width="2.5" stroke-dasharray="2 5" stroke-linecap="round"/>':'')+a.map((v,i)=>'<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(v).toFixed(1)+'" r="'+(i===cm?5:3)+'" fill="'+(i>cm?'#fff':c)+'" stroke="'+c+'" stroke-width="2"/>').join('')};
 o+=line(r.mu,'#2A5A9B')+line(r.mg,'#C77B2B');
 const up=r.mu[cm]>=r.mg[cm];const ly=(v,dy)=>{let y=Y(v)+dy;if(y>H-pb-2)y=Y(v)-10;return y};
 o+='<text x="'+X(cm)+'" y="'+ly(r.mu[cm],up?-10:20)+'" font-size="12" font-weight="800" fill="#2A5A9B" text-anchor="middle">'+r.mu[cm].toFixed(2)+'</text><text x="'+X(cm)+'" y="'+ly(r.mg[cm],up?20:-10)+'" font-size="12" font-weight="800" fill="#C77B2B" text-anchor="middle">'+r.mg[cm].toFixed(2)+'</text>';
 return '<svg viewBox="0 0 '+W+' '+H+'" width="'+W+'" height="'+H+'">'+o+'</svg>'}
function filt(par){tb.querySelectorAll('tbody tr').forEach(tr=>{if(tr.classList.contains('corp')){tr.hidden=true;return}if(tr.dataset.hq)tr.hidden=(tr.dataset.hq!==par)});tb.querySelectorAll('tfoot tr').forEach(t=>t.hidden=true)}
const chip=(q,cls)=>'<div class="hqc sub '+(q.g>=80?'ok':(q.g>=70?'mid':'lo'))+(cls||'')+'" data-id="'+q.id+'" role="button" tabindex="0"><span class="hqn">'+q.nm+'</span><b>'+q.g.toFixed(1)+'%</b></div>';
function renderSub(id,par){const sl=GD.subs[par]||[];if(!CID.has(par)||!sl.length){sub.innerHTML='';return}
 const h=A[par];sub.innerHTML='<span class="cgl">사업부별</span>'+chip({id:par,nm:'본부 전체',g:h.g},id===par?' sel':'')+sl.map(sid=>chip({id:sid,nm:A[sid].name,g:A[sid].g},(sid===id||A[id].dv===sid)?' sel':'')).join('');
 sub.querySelectorAll('.hqc').forEach(e=>{const a=()=>show(e.dataset.id,{noScroll:true});e.onclick=a;e.onkeydown=ev=>{if(ev.key==='Enter'){ev.preventDefault();a()}}})}
function hov(r){const g=det.querySelector('.gtr');if(!g)return;const sv=g.querySelector('svg');if(!sv)return;g.style.position='relative';
 const tip=document.createElement('div');tip.className='gtip';tip.hidden=true;g.appendChild(tip);
 const W=540,pl=40,pr=14,cm=GD.cm,ns='http://www.w3.org/2000/svg';const vl=document.createElementNS(ns,'line');vl.setAttribute('y1',30);vl.setAttribute('y2',158);vl.setAttribute('stroke','#7B8AA0');vl.setAttribute('stroke-dasharray','3 3');vl.style.display='none';sv.appendChild(vl);
 sv.addEventListener('mousemove',e=>{const b=sv.getBoundingClientRect();const x=(e.clientX-b.left)*W/b.width;let i=Math.round((x-pl)/((W-pl-pr)/11));i=Math.max(0,Math.min(11,i));
  const X=pl+(W-pl-pr)*i/11;vl.setAttribute('x1',X);vl.setAttribute('x2',X);vl.style.display='';
  tip.innerHTML='<b>'+(i+1)+'월'+(i>cm?' (예상)':'')+'</b><br><span style="color:#F0B48A">● 가득률 '+r.mg[i].toFixed(2)+'%</span><br><span style="color:#9CC0EE">● 가동률 '+r.mu[i].toFixed(2)+'%</span>';tip.hidden=false;
  const gb=g.getBoundingClientRect();let lx=e.clientX-gb.left+14;if(lx>gb.width-150)lx=e.clientX-gb.left-150;tip.style.left=lx+'px';tip.style.top=(e.clientY-gb.top-10)+'px'});
 sv.addEventListener('mouseleave',()=>{tip.hidden=true;vl.style.display='none'})}
function clear(){sub.innerHTML='';tb.querySelectorAll('tbody tr.corp,tbody tr.hq').forEach(t=>t.hidden=false);tb.querySelectorAll('tfoot tr').forEach(t=>t.hidden=false);hrows().forEach(h=>setRow(h,false));cur=null;cards.forEach(c=>c.classList.remove('sel'));hrows().forEach(r=>r.classList.remove('hsel'));tb.querySelectorAll('tr.hsel2').forEach(x=>x.classList.remove('hsel2'));det.classList.remove('on');det.innerHTML=''}
function show(id,o){o=o||{};const r=A[id];if(!r)return;cur=id;const par=r.par||id;
 cards.forEach(c=>c.classList.toggle('sel',c.dataset.id===id||c.dataset.id===par));
 hrows().forEach(h=>{const me=h.dataset.hq===par;h.classList.toggle('hsel',me&&!r.par);setRow(h,me)});
 tb.querySelectorAll('tr.hsel2').forEach(x=>x.classList.remove('hsel2'));
 if(r.par){const t=tb.querySelector('tr[data-sid="'+id+'"]');if(t)t.classList.add('hsel2')}
 filt(par);
 const sl=GD.subs[par]||[];
 const subH=sl.length?'<div class="sg"><div class="sgt">사업부별</div><div class="sgl">'+sl.map(sid=>{const q=A[sid];return '<div class="sgi'+((sid===id||r.dv===sid)?' on':'')+'" data-id="'+sid+'">'+GD.svg[sid].sm+'<div class="sgn">'+q.name+'</div><div><b style="color:#B8691A">'+f(q.g)+'%</b> <span style="color:#2A5A9B">'+f(q.u)+'%</span></div></div>'}).join('')+'</div></div>':'';
 const gap=T-r.g;
 det.innerHTML='<button class="gx" type="button">닫기 ✕</button><div style="flex:0 0 480px">'+GD.svg[id].big+'</div><div><h3>'+r.name+'</h3><div class="gsb">'+(r.corp||r.cn)+' · 가동대상 '+f(r.T)+'MM · 대기 '+f(r.idle)+'MM '+dl(r.pidle,r.idle,'MM')+'</div>'+(over(r)?'<div class="gw" style="margin-bottom:6px">⚠ 100% 초과 · 데이터 확인 필요</div>':'')+'<div class="gk"><div style="border-top:3px solid #C77B2B"><span style="color:#6B7280">가득률</span><b class="n" style="color:#B8691A">'+f(r.g)+'%</b>전주 '+f(r.pg)+' '+dl(r.pg,r.g,'%p')+'</div><div style="border-top:3px solid #7FA8DA"><span style="color:#6B7280">가동률</span><b class="n" style="color:#2A5A9B">'+f(r.u)+'%</b>전주 '+f(r.pu)+' '+dl(r.pu,r.u,'%p')+'</div></div><div class="gtr">'+trend(r)+'</div></div>';
 det.classList.add('on');det.querySelector('.gx').onclick=()=>{clear();hrows().forEach(h=>setRow(h,false))};
 det.querySelectorAll('.sgi').forEach(e=>e.onclick=()=>{show(e.dataset.id,{noScroll:true});const t=tb.querySelector('tr[data-sid="'+e.dataset.id+'"]');if(t)t.scrollIntoView({behavior:'smooth',block:'center'})});
 /*ALIGN_V1*/{const th=tb.querySelector('thead th:nth-child(2)'),inf=det.children[2];if(th&&inf){inf.style.marginLeft='0px';const rg=document.createRange();rg.selectNodeContents(th.firstChild||th);const tx=rg.getBoundingClientRect().left,ix=inf.getBoundingClientRect().left;if(tx>ix)inf.style.marginLeft=Math.round(tx-ix)+'px'}}
 /*HQNAV_V3*/renderSub(id,par);hov(r);
 if(!o.noScroll)det.scrollIntoView({behavior:'smooth',block:'start'})}
cards.forEach(c=>{const act=()=>{c.dataset.id===cur?clear():show(c.dataset.id,{noScroll:true})};c.onclick=act;c.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();act()}}});
/*HQNAV_V1*/window.__showHq=id=>show(id,{noScroll:true});
document.querySelectorAll('#hqbar .hqc').forEach(b=>{const a=()=>{go(1);window.__showHq(b.dataset.id)};b.onclick=a;b.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();a()}}});
/*HQNAV_V2*/hrows().forEach(r=>{r.addEventListener('click',()=>setTimeout(()=>{const open=r.getAttribute('aria-expanded')==='true';if(open)show(r.dataset.hq,{noScroll:true});else if(cur===r.dataset.hq||(A[cur]&&A[cur].par===r.dataset.hq))clear()},0))});
/*HQNAV_V4*/tb.querySelectorAll('tr.sub[data-sid]').forEach(r=>{const a=()=>show(r.dataset.sid,{noScroll:true});r.onclick=a;r.tabIndex=0;r.setAttribute('role','button');r.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();a()}}});
document.querySelectorAll('.cc2 ol.rkl li').forEach(li=>{const id=GD.cards.find(x=>A[x].cn===li.dataset.cn&&A[x].name===li.dataset.nm);if(!id)return;li.onclick=()=>{go(1);window.__showHq(id)}});
})();
"""
LG = f'<div class="lg"><span><i style="background:{X.C2}"></i>가득률</span><span><i style="background:{X.C1}"></i>가동률</span><span>실선 = 실적 · 점선 = 예상</span></div>'
_n_im = len(IM); _k_lv = 12 - P10   # 월 열 개수 (달이 지날수록 줄어듦 → 비고 열이 나머지 너비)
IT_W = ("".join(f"table.it th:nth-child({5 + i}){{width:4.6%}}" for i in range(K_OLD))
        + "".join(f"table.it th:nth-child({5 + K_OLD + i}){{width:4.4%}}" for i in range(_n_im))
        + f"table.it th:nth-child({5 + K_OLD + _n_im}){{width:{100 - 7 - 12 - 9 - 6.5 - 9 - 4.4 * _n_im:.1f}%}}table.it th:nth-child({6 + K_OLD + _n_im}){{width:9%}}"
        + "".join(f"table.it:not(.fold-old) th:nth-child({k}){{width:{w}%}}" for k, w in [(1, 6), (2, 10), (3, 8), (4, 6)])   # 1~N월을 펼친 상태: 월 열이 늘어도 표가 화면 안에 들어오게
        + "".join(f"table.it:not(.fold-old) th:nth-child({5 + i}){{width:3.6%}}" for i in range(K_OLD + _n_im))
        + f"table.it:not(.fold-old) th:nth-child({5 + K_OLD + _n_im}){{width:{100 - 30 - 8 - 3.6 * (K_OLD + _n_im):.1f}%}}table.it:not(.fold-old) th:nth-child({6 + K_OLD + _n_im}){{width:8%}}"
        + "table.it.fold-old .old{display:none}table.it tr[data-b] td:nth-child(2){font-size:.84em;letter-spacing:-.2px;color:#4B5563}table.it .trn{font-size:.82em;color:#6B7280;margin-top:2px}")
LV_W = ("".join(f"table.lvt th:nth-child({7 + i}){{width:6%}}" for i in range(_k_lv))
        + f"table.lvt th:nth-child({7 + _k_lv}){{width:{13 + 6 * (3 - _k_lv)}%}}")

# ---------- 목표 대비 M/M 갭 위젯(월별 추이 슬라이드) + 전주 대비 변동 원인 슬라이드 ----------
import re as _re
_TG = getattr(__import__('cfg'), "TARGETS", None) or {}
_sT = sum(D["T"]); _sE = sum(D["ex"])
_sEn = sum(a - b for a, b in zip(D["ex"], D["exh"])); _sN = sum(D["np"])
_k_rem = 12 - P10
_idle_rem = sum(D["idle"][P10:])
def _gwb(title, num, den, tg, small=False):
    tv = "" if tg in (None, "") else f"{float(tg):g}"
    cur = num / den * 100 if den else 0
    return (f'<div class="gwb{" sm" if small else ""}" data-num="{num:.4f}" data-den="{den:.4f}" data-idle="{_idle_rem:.4f}" data-k="{_k_rem}">'
            f'<div class="gwr"><span class="gwl">{E(title)} <b>{cur:.2f}%</b> → 목표</span><span class="gwi"><input class="bgt" type="number" step="0.1" min="0" max="100" value="{tv}" aria-label="목표 가득률">%</span></div>'
            f'<div class="bgg"></div><div class="bgs"></div></div>')
GAP_W = ('<div class="gw"><div class="gwt">목표 대비 필요 투입</div>'
         + _gwb("전체 기준", _sE, _sT, _TG.get("all"))
         + _gwb("비매출 제외", _sEn, _sT - _sN, _TG.get("net"), True)
         + '<script>(function(){document.querySelectorAll(".gwb").forEach(function(c){var num=+c.dataset.num,den=+c.dataset.den,idle=+c.dataset.idle,k=+c.dataset.k,inp=c.querySelector(".bgt"),g=c.querySelector(".bgg"),s=c.querySelector(".bgs");'
         'function f1(v){return v.toFixed(1)}'
         'function r(){var t=parseFloat(inp.value);if(isNaN(t)){g.className="bgg";g.textContent="목표를 입력하세요";s.textContent="";return}'
         'var need=t/100*den-num,cur=num/den*100;'
         'if(need<=0.05){g.className="bgg ok";g.innerHTML="<b>목표 달성권</b> · 여유 "+f1(-need)+" M/M";s.textContent=""}'
         'else{g.className="bgg lack";g.innerHTML="<b>"+f1(need)+" M/M 부족</b> <small>("+(cur-t).toFixed(2)+"%p)</small>";'
         'if(need<=idle)s.innerHTML="";'
         'else s.innerHTML="대기 전원("+f1(idle)+" M/M)을 투입해도 <b>"+f1(need-idle)+" M/M</b> 부족 · 신규 수주 필요"}}'
         'inp.addEventListener("input",r);r()})})();</script></div>')

# 사람·프로젝트별 당월 이행 MM 스냅샷 → 다음 주 '전주 대비 변동 원인'에 씀 (프로젝트는 코드로 묶음)
_pp, _pt, _pjn = {}, {}, {}
try:
    for _p in PP.values():
        _pk = f'{_p["corp"]}|{_p["gid"]}'
        _pt[_pk] = [round(_p["T"][P10], 4), round(_p["ex"][P10], 4), round(_p["pr"][P10], 4), round(_p["rd"][P10], 4)]
        for (_cd, _nm, _gu), _mm in _p["projs"].items():
            if _gu != "이행" or _mm[P10] <= 0.0001: continue
            _kk = str(_cd).strip() or str(_nm)
            _d = _pp.setdefault(_pk, {}); _d[_kk] = round(_d.get(_kk, 0.0) + _mm[P10], 4)
            _pjn[_kk] = _re.sub(r"\s*\[CH\w+\]\s*$", "", str(_nm)).strip() or _kk
    SUMMARY["pp"], SUMMARY["pt"], SUMMARY["pjn"] = _pp, _pt, _pjn
    SUMMARY["yt"] = {"T": round(D["T"][P10], 3), "E": round(D["ex"][P10], 3), "m": P10}
except Exception as _e:
    print("변동 원인 집계 건너뜀:", _e)

def _why_build():
    if not PREV or "pp" not in PREV or "pt" not in PREV or PREV.get("yt", {}).get("m") != P10: return ""
    T0, E0 = PREV["yt"]["T"], PREV["yt"]["E"]; T1, E1 = D["T"][P10], D["ex"][P10]
    if not (T0 and T1): return ""
    g0, g1 = E0 / T0 * 100, E1 / T1 * 100; tot = g1 - g0
    names = dict(PREV.get("pjn", {})); names.update(_pjn)
    old_pj = {k for v in PREV["pp"].values() for k in v}
    rows = {}
    for pk in set(_pp) | set(PREV["pp"]):
        a_, b_ = PREV["pp"].get(pk, {}), _pp.get(pk, {})
        t0, t1 = PREV["pt"].get(pk, [0, 0, 0, 0]), _pt.get(pk, [0, 0, 0, 0])
        i0, i1 = t0[0] - t0[1] - t0[2] - t0[3], t1[0] - t1[1] - t1[2] - t1[3]
        moved = abs(t1[1] - t0[1]) < 0.005
        for pj in set(a_) | set(b_):
            d = b_.get(pj, 0.0) - a_.get(pj, 0.0)
            if abs(d) < 0.005 or moved: continue
            if d < 0:
                if pk not in _pt or t1[0] < t0[0] - 0.005: tag = "가동대상 변동 (휴직·퇴사 등)"
                elif i1 - i0 > 0.005: tag = "대기로 전환"
                elif t1[3] - t0[3] > 0.005: tag = "R&D·내부과제로 전환"
                elif t1[2] - t0[2] > 0.005: tag = "제안 업무로 전환"
                else: tag = "투입 축소"
            else:
                if pk not in PREV["pt"] or t1[0] > t0[0] + 0.005: tag = "가동대상 증가 (입사·복직 등)"
                elif i1 - i0 < -0.005: tag = "대기에서 투입"
                elif t1[3] - t0[3] < -0.005: tag = "R&D·내부과제에서 전환"
                elif t1[2] - t0[2] < -0.005: tag = "제안에서 이행으로 전환"
                elif pj not in old_pj: tag = "신규 투입"
                else: tag = "투입 확대"
            r = rows.setdefault((pj, tag, d > 0), [0.0, set()]); r[0] += d; r[1].add(pk)
    items = [(v[0] / T1 * 100, names.get(k[0], k[0]), k[1], len(v[1])) for k, v in rows.items() if abs(v[0] / T1 * 100) >= 0.005]
    den = E0 * (1 / T1 - 1 / T0) * 100
    dn_all = sorted([x for x in items if x[0] < 0]); up_all = sorted([x for x in items if x[0] > 0], reverse=True)
    dn_sum, up_sum = sum(x[0] for x in dn_all), sum(x[0] for x in up_all)
    rest = tot - dn_sum - up_sum - den
    def sg(d): return f'<span class="pl {"pl-up" if d > 0 else "pl-dn"}">{"+" if d > 0 else "−"}{abs(d):.2f}%p</span>'
    def li(x): return f'<li><div class="wn"><b>{E(x[1])}</b><em>{E(x[2])} · {x[3]}명</em></div>{sg(x[0])}</li>'
    def col(t, lst, empty): return f'<div class="why-col"><h4>{t}</h4><ul>{"".join(li(x) for x in lst[:5]) or f"<li class=wn0>{empty}</li>"}</ul></div>'
    lead = (dn_all[0] if tot < 0 and dn_all else up_all[0] if up_all else None)
    cls = "up" if tot > 0 else "dn"
    head = (f'<div class="whyb"><small>{E(BL)} 대비 {P10 + 1}월 가득률</small><em class="{cls}">{"+" if tot > 0 else "−"}{abs(tot):.2f}<i>%p</i></em><span>{g0:.2f}% → {g1:.2f}%</span></div>'
            + (f'<div class="whyl">가장 큰 요인 · <b>{E(lead[1])}</b> ({E(lead[2])}) {sg(lead[0])}</div>' if lead else ""))
    def eq(label, v, c=""): return f'<div class="{c}"><small>{label}</small><b class="{"up" if v > 0 else "dn"}">{"+" if v > 0 else "−"}{abs(v):.2f}%p</b></div>'
    parts = [eq("하락 요인 합", dn_sum) if dn_all else '<div><small>하락 요인 합</small><b>—</b></div>', eq("상승 요인 합", up_sum) if up_all else '<div><small>상승 요인 합</small><b>—</b></div>']
    if abs(den) >= 0.005: parts.append(eq("모수(가동대상) 변동", den))
    if abs(rest) >= 0.005: parts.append(eq("기타", rest))
    foot = '<div class="whyeq">' + '<i>+</i>'.join(parts) + f'<i>=</i>{eq("전체 변동", tot, "tot")}</div><div class="whyf">프로젝트별 상위 5건만 표시 · 사람 단위로 투입 이동이 상쇄된 건은 제외</div>'
    return (f'<section class="slide"><h2>전주 대비 변동 원인</h2><div class="why"><div class="whyh">{head}</div>'
            f'<div class="whyg">{col("하락 요인", dn_all, "없음")}{col("상승 요인", up_all, "없음")}</div>{foot}</div></section>')
try: WHY_SLIDE = _why_build()
except Exception as _e:
    print("변동 원인 슬라이드 건너뜀:", _e); WHY_SLIDE = ""

CSS += r"""
.gw{margin-top:16px;padding:14px 26px 4px;border-top:1px solid var(--line);width:100%}.gwt{font-size:14px;font-weight:700;color:var(--navy);margin-bottom:8px}.gwt small{font-weight:500;color:var(--muted);font-size:12px}
.gwb{margin-bottom:12px}.gwr{display:flex;justify-content:space-between;align-items:center;font-size:14px;color:var(--muted)}.gwr b{color:var(--navy);font-size:16px}.gwl,.gwi{white-space:nowrap}.gwi{color:var(--muted);font-size:14px}
.bgt{width:78px;font:inherit;font-size:24px;font-weight:800;color:var(--steel);border:0;border-bottom:2px solid var(--steel);background:#F5F8FC;padding:0 6px;text-align:right;line-height:1.2}.bgt:focus{outline:0;background:#E9F0FA}
.bgg{margin-top:6px;font-size:14px;color:#374151}.bgg b{font-size:21px;font-weight:800}.bgg small{font-size:12.5px;color:var(--muted)}.bgg.lack b{color:var(--rise)}.bgg.ok b{color:var(--fall)}
.bgs{margin-top:3px;font-size:13px;line-height:1.5;color:#374151}.bgs b{color:var(--navy)}.gwb.sm .bgs{display:none}.gwb.sm .bgg b{font-size:17px}
.why{background:#fff;border-top:4px solid var(--steel);padding:20px 26px 18px}.whyh{margin-bottom:18px}.whyb{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap}.whyb small{font-size:16px;color:var(--muted)}
.whyb em{font-style:normal;font-size:24px;font-weight:700;line-height:1.2}.whyb em i{font-style:normal;font-size:15px;margin-left:1px}.whyb em.up{color:var(--rise)}.whyb em.dn{color:var(--fall)}.whyb span{font-size:16px;color:#374151}
.whyl{margin-top:6px;font-size:15px;color:#374151}.whyl b{color:var(--navy)}
.whyg{display:grid;grid-template-columns:1fr 1fr;gap:36px}.why-col h4{margin:0 0 8px;font-size:15px;color:var(--navy);font-weight:800}.why-col ul{list-style:none;margin:0;padding:0}
.why-col li{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)}.wn{min-width:0}.wn b{display:block;font-size:15px;color:#1F2937;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.wn em{display:block;font-style:normal;font-size:12.5px;color:var(--muted);margin-top:2px}.wn0{color:var(--muted)}
.whyeq{display:flex;align-items:center;gap:14px;margin-top:20px;padding:10px 20px;background:#F5F8FC;border-radius:6px}.whyeq>div{text-align:center;min-width:120px}.whyeq small{display:block;font-size:12.5px;color:var(--muted);margin-bottom:2px}
.whyeq b{font-size:20px;font-weight:700;color:var(--navy)}.whyeq b.up{color:var(--rise)}.whyeq b.dn{color:var(--fall)}.whyeq>i{font-style:normal;font-size:22px;color:#9AA5B5}.whyeq .tot{padding-left:14px;border-left:2px solid var(--line)}.whyeq .tot b{font-size:22px}
.whyf{margin-top:10px;font-size:12.5px;color:var(--muted)}
"""

CSS += r"""
/* 1110 디자인: 지표 묶음은 항목 단위로만 줄바꿈 */
.y3i{white-space:nowrap;display:inline-block;margin-right:12px}.y3i:last-child{margin-right:0}
.yr3{display:grid;grid-template-columns:150px repeat(3,max-content);justify-content:start;align-items:center;gap:8px 10px}.yr3 .y3g{display:contents}
.pmc{display:flex;align-items:center;white-space:nowrap;gap:8px;margin-top:4px}.pmc em{min-width:112px;flex:none}.pmc .y3i{margin:0}.pmc .y3i b.vg{color:#C26D1A}.pmc .y3i b.vu{color:#1D4ED8}.pmc .y3i b{font-weight:800}
.yr3 .y3t{font-weight:700;color:var(--navy);margin-right:2px;white-space:nowrap}
.yr3 .y3i{margin-right:0;display:inline-flex;align-items:center;gap:6px;background:#F1F5F9;border-radius:6px;padding:4px 10px;color:#64748B;font-size:14px}
.yr3 .y3i b{font-weight:700;font-size:15px}.yr3 .y3i b.vg{color:#C26D1A}.yr3 .y3i b.vu{color:#1D4ED8}
.nw{white-space:nowrap}
/* 본부 선택: 법인 줄·사업부별 줄의 시작 위치(라벨 칸)·높이·간격을 같게 */
#gcards{display:flex;flex-direction:column;align-items:flex-start;gap:8px;margin:6px 0 8px}
#gcards .hqbk{margin:0 0 2px 0}
#gcards .cgrp,#gsub{display:flex;flex-wrap:wrap;align-items:center;gap:8px;width:100%;box-sizing:border-box;min-height:0}
#gcards .cgl,#gsub .cgl{flex:0 0 112px;width:112px;margin:0;padding:0;line-height:1.2;align-self:center;font-size:13px;font-weight:700;color:#4A5A70}
#gsub{padding:0;margin:0 0 12px}
#gsub .hqc{margin:0}
/* 법인별 요약 카드: 지표 3등분 · 전월 확정 줄 */
.cc2 .gst{grid-template-columns:repeat(3,minmax(0,1fr));gap:0 16px}
.cc2 .gs.go.two{display:contents}
.cc2 .gst .gsi{border-top:3px solid #C77B2B;padding:6px 14px;min-width:0}
.cc2 .gst .gs.gb{padding:6px 14px;border-top-width:3px}
.cc2 .gst .gsi>span,.cc2 .gst .gs>span{font-size:15px;font-weight:700;color:#4B5563;white-space:nowrap}
.cc2 .gst .gsi>b,.cc2 .gst .gs>b{display:block;font-size:26px;line-height:1.15;margin:2px 0 6px}
.cc2 .gst .gsi>b{color:#B8691A}
.gst .cmp{display:flex;align-items:center;flex-wrap:wrap;gap:4px 6px;font-weight:600;color:#374151}
.cc2 .gst .cmp{font-size:14px}
.cc2 ol.rkl li,.cc2 .rkh{grid-template-columns:repeat(3,minmax(0,1fr));column-gap:16px}
.cc2 .rkl li .rn{padding-left:14px}.cc2 .rkt{padding-left:14px}
.cc2 .pr,.cc2 .rkh .hc{padding-left:14px}
"""
CSS = CSS.replace("{IT_W}", IT_W).replace("{LV_W}", LV_W)
import re as _re_fit
CSS = _re_fit.sub(r"(\d*\.?\d+)vw", lambda m: "calc(var(--u,1vw)*" + m.group(1) + ")", CSS)   # 화면 비례 확대(fit)를 켜면 --u=0 으로 두어 이중 확대 방지
page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MM-Compass (MM 나침반) · 회의용 · {E(WEEK_LABEL)}</title><link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{ICON_URI}"><style>{CSS}</style></head><body>
<div class="top"><b class="tbn"><img class="tbi" alt="" src="data:image/svg+xml,{ICON_URI}">MM-Compass <small style="font-weight:500;opacity:.8">(MM 나침반)</small></b><span class="wk">{E(WEEK_LABEL)} · 데이터 기준 {E(ASOF)} · {E(MEET)}</span><span class="sp"></span>
<button id="prev" aria-label="이전">◀</button><span class="pg" id="pg"></span><button id="next" aria-label="다음">▶</button>{'<button id="mtog">' + E(ML) + ' 대비 보기</button>' if PREV else ''}<button id="full">전체 화면</button></div>
<div class="deck">
<section class="slide"><h2>{E(WEEK_LABEL)} 인력 가동 현황</h2><div class="sub">{P10 + 1}월(당월) 현재 · <b>{E(BL)} 대비</b> · 아이티센클로잇 + 아이티센엔텍</div>
<div class="s1g">{gcard}<div class="s1r">{HQ_BAR}<div class="kpis">{kpi_html}</div><div class="card sumc"><h3>이번 주 요약</h3><ul class="sum">{summary_html}</ul></div>{year_html}</div></div>
<div class="ccs">{corp_cards}</div>{('<div class="rkn">* 전주 값이 없는 조직은 ' + ML + ' 대비 (다음 주부터 전주 대비)</div>') if _NOTE else ''}<div class="note">가득률 = 이행 ÷ 가동대상 · 가동률 = (이행+제안+R&amp;D·내부과제) ÷ 가동대상 · 비매출 모수 = 사업부장 + R&amp;D·내부과제 · {X.CONF + 1}월 이후는 투입계획 기준 예상{E(X.PROV_TXT)} · 수치 기준: 26년 가동가득 통계{X._ST_D}</div></section>
<section class="slide"><h2>본부별 가득률 · 가동률</h2><div class="lgd"><span class="lo">● 가득률</span><span class="lu">● 가동률</span></div><div class="sub">큰 숫자 = {P10 + 1}월 현재 · 아래 작은 글씨 = <b>{E(BL)}</b> 값과 증감 · 가동대상·대기는 MM · <b>위 본부 버튼을 누르면 해당 본부 상세가 나옵니다</b></div>
<div id="gcards"></div><div id="gsub"></div><div id="gdet"></div>
<table class="ht"><thead><tr><th class="l">법인 / 본부</th><th>가동대상<small>{P10 + 1}월 MM</small></th><th>가득률</th><th>가동률</th><th>대기<small>MM</small></th></tr></thead><tbody>{rows}</tbody><tfoot>{tot}</tfoot></table></section>
<section class="slide"><h2>월별 가득률 · 가동률 추이</h2><div class="sub">{X.RA} 실적 · {P10 + 1}월 당월{f' · {X._cf.R(P10 + 2)} 투입계획 기준 예상' if P10 < 11 else ''}{E(X.PROV_TXT)}</div>
<div class="s3g"><div class="ycg"><div class="ycg-t">연간 추정</div>{GA.sized(GA.pair(min(D["yu"], 100), min(D["yg"], 100), None, None, "yy"), 440)}{GAP_W}</div><div class="s3m"><div class="chart-card" id="cc">{LG}{chart}<div class="tip" id="tip" hidden></div></div><div class="note">그래프의 각 달에 마우스를 올리면 수치와 전월 대비 증감이 나옵니다.</div>{mtab}{year3_html}</div></div><div class="corp-line">{corp_line}</div></section>
<section class="slide"><h2>대기 인력</h2><div class="fbar"><label><input type="checkbox" id="mex" checked> 사업부장 포함</label><label>직무 {X.job_select("mjob", [p for p in PP.values() if _idle(p)])}</label><label>대기 기간 <select id="mld"><option value="0">전체</option>{"".join(f'<option value="{k}">누적 {k}개월 이상</option>' for k in range(1, 7))}</select></label></div><div class="sub">{P9 + 1}월({"확정" if PM_OK else "잠정"}) 또는 {P10 + 1}월(당월) 대기가 있는 인원 {n_show}명 · 단위 MM · 법인 › 본부 › 사업부 › 팀 · 사업부를 누르면 사람이 펼쳐집니다 {('<button class="tg" id="idold">' + (f'1~{P9}월 펼치기' if P9 > 1 else '1월 펼치기') + '</button>') if K_OLD else ''}<button class="tg" id="idopen">사람까지 모두 펼치기</button><button class="tg" id="idclose">사업부까지만 보기</button></div>{idle_blocks}</section>
<section class="slide"><h2>인사 변동</h2>
<h3 class="sh">변동 인원 <b>{len(X.HRE)}명</b><small>{P10 + 1}월 입사 · 퇴사 · 휴직 · 복직 · 전배 · 가동대상 영향</small></h3>
<table class="hrt"><thead><tr><th>유형</th><th class="l">성명</th><th class="l">소속 (변동)</th><th class="l">직무</th><th class="l">직급</th><th>적용일</th><th class="l">가동대상 영향</th></tr></thead><tbody>{hr_rows}</tbody></table>
<h3 class="sh">휴직 인원 <b>{len(X.LEAVE_ROWS)}명</b><small>당월 이후 휴직 중 · 복직 예정일은 연장 반영 · 가동대상MM</small></h3>
<table class="lvt"><thead><tr><th class="l">성명</th><th class="l">법인</th><th class="l">소속</th><th class="l">직무</th><th class="l">직급</th><th>휴직 기간</th>{"".join(f'<th>{m + 1}월</th>' for m in range(P10, 12))}<th class="l">비고</th></tr></thead><tbody>{lv_rows}</tbody></table></section>
</div><script>const TIP={TIP_JSON};const GD={GDATA_JSON};{JS.replace("{ML_JS}", ML)}
{JS2}{JSF}</script></body></html>"""

# ---------- 검증: 투입이 가동대상을 넘는 조직·인원 (가동률·가득률 100% 초과) ----------
_over = []
for _k, _n in SUMMARY["nodes"].items():
    if _n["T"] is None or _n["inp"] is None: continue
    if _n["inp"] > _n["T"] + 0.005 or (_n["u"] or 0) > 100.005 or (_n["g"] or 0) > 100.005: _over.append((_k, _n))
_paths = [tuple(k.split("|")[1:]) for k, _ in _over]
_ov_txt = []
for (_k, _n), _p in zip(_over, _paths):
    if any(len(q) > len(_p) and q[:len(_p)] == _p for q in _paths): continue
    _ov_txt.append(f'{" › ".join(x for x in _p if x != "(직속)")} — 투입 {_n["inp"]:.2f}MM > 가동대상 {_n["T"]:.2f}MM (가동률 {_n["u"]:.2f}%) · 입력 데이터 확인 필요')
for _p in PP.values():
    _i = inp(_p, P10)
    if _i > _p["T"][P10] + 0.005: _ov_txt.append(f'{_p["name"]} ({_p["org"]}) — {P10 + 1}월 투입 {_i:.2f} > 가동대상 {_p["T"][P10]:.2f} · 입력 데이터 확인 필요')
SUMMARY["over"] = _ov_txt
if _ov_txt: print("OVER100", *_ov_txt, sep="\n  ")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else __import__('cfg').w("meeting.html")
    import tidy as _tidy; page = _tidy.tidy_meeting(page)
    open(out, "w", encoding="utf-8").write(page)
    _j.dump(SUMMARY, open(os.path.join(os.path.dirname(out) or ".", "summary.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("ok", out, n_show, need)

# ORDER_V1

# MEET2_V1
