# org hierarchy, drilldowns, HR section states — appended into v4_extra namespace via exec
import json as _json

DIVS = {"SI사업본부": [("공공사업부", ["공공1팀", "공공2팀"]), ("금융사업부", ["금융1팀", "기술지원팀"])],
        "SM사업본부": [("SM사업부", ["SM1팀", "SM2팀", "SM3팀"])],
        "솔루션사업본부": [("솔루션사업부", ["솔루션개발팀", "솔루션기획팀"])],
        "기술연구소": [("플랫폼연구부", ["연구1팀", "연구2팀"])],
        "ENT사업본부": [("ENT사업부", ["ENT개발팀", "ENT운영팀", "ENT기획팀"])]}
# center team offsets so weighted team average == 본부
for _hq, _lst in list(TEAMS.items()):
    _T = sum(t[1] for t in _lst); _wm = sum(t[1]*t[2] for t in _lst)/_T
    TEAMS[_hq] = [(n, tt, round(off-_wm, 2)) for n, tt, off in _lst]
TEAM_INFO = {n: (hq, tt, off) for hq, lst in TEAMS.items() for n, tt, off in lst}
TU = {n: [round(v+off, 1) for v in HQU[hq]] for n, (hq, tt, off) in TEAM_INFO.items()}
TG = {n: [round(v+off*0.8, 1) for v in HQG[hq]] for n, (hq, tt, off) in TEAM_INFO.items()}
def _wv(names, src, wt):
    T = sum(wt[n] for n in names)
    return [round(sum(wt[n]*src[n][i] for n in names)/T, 1) for i in range(12)]
TT = {n: v[1] for n, v in TEAM_INFO.items()}
DU, DG, DT = {}, {}, {}
for hq, dl in DIVS.items():
    for dn, tl in dl:
        DU[dn] = _wv(tl, TU, TT); DG[dn] = _wv(tl, TG, TT); DT[dn] = sum(TT[t] for t in tl)
RDF = {"기술연구소": 0.7}
def _bd(T, u, g, rdf):
    ex = [T*x/100 for x in g]; inp = [T*x/100 for x in u]
    non = [a-b for a, b in zip(inp, ex)]
    rd = [x*rdf for x in non]; pr = [a-b for a, b in zip(non, rd)]
    idle = [T-x for x in inp]
    r2 = lambda L: [round(x, 1) for x in L]
    return dict(T=[T]*12, ex=r2(ex), pr=r2(pr), rd=r2(rd), idle=r2(idle), u=u, g=g)
ORG = {}
for hi, (hq, u) in enumerate(HQS):
    ORG[f"h{hi}"] = dict(name=hq, path=HQ_CORP[hq], **_bd(HQ_T[hq], u, HQG[hq], RDF.get(hq, 0.35)))
    for di, (dn, tl) in enumerate(DIVS[hq]):
        ORG[f"h{hi}d{di}"] = dict(name=dn, path=f"{HQ_CORP[hq]} › {hq}", **_bd(DT[dn], DU[dn], DG[dn], RDF.get(hq, 0.35)))
        for ti, tn in enumerate(tl):
            ORG[f"h{hi}d{di}t{ti}"] = dict(name=tn, path=f"{HQ_CORP[hq]} › {hq} › {dn}", **_bd(TT[tn], TU[tn], TG[tn], RDF.get(hq, 0.35)))
ORG_JSON = _json.dumps(ORG, ensure_ascii=False)

def annual_table_rows(mcells):
    rows = ""
    for cname, names in CORPS:
        cu = wavg(names, HQU)
        rows += f'<tr class="sub"><td class="l">{cname}</td>{mcells(cu)}<td class="strong">{avg(cu):.1f}</td></tr>'
        for n in names:
            hi = ALLN.index(n)
            rows += f'<tr class="org hq" data-key="h{hi}" data-hq="{hi}" tabindex="0"><td class="l"><span class="tw"></span>{n}</td>{mcells(HQU[n])}<td class="strong">{avg(HQU[n]):.1f}</td></tr>'
            for di, (dn, tl) in enumerate(DIVS[n]):
                rows += f'<tr class="org dv" data-key="h{hi}d{di}" data-parent="{hi}" tabindex="0" hidden><td class="l">{dn}</td>{mcells(DU[dn])}<td class="strong">{avg(DU[dn]):.1f}</td></tr>'
                for ti, tn in enumerate(tl):
                    rows += f'<tr class="org tm" data-key="h{hi}d{di}t{ti}" data-parent="{hi}" tabindex="0" hidden><td class="l">{tn}</td>{mcells(TU[tn])}<td>{avg(TU[tn]):.1f}</td></tr>'
    return rows

# ---- weekly report: 본부별 가동률 증감 with drilldown ----
HQW = {"SI사업본부": (160.0, 137.6, 141.4), "SM사업본부": (120.0, 109.8, 110.5), "솔루션사업본부": (90.0, 64.6, 68.1),
       "기술연구소": (40.0, 30.2, 28.2), "ENT사업본부": (40.0, 31.4, 33.0)}
NOISE = [0.9, -0.6, 0.4, -1.2, 0.7, -0.3, 1.1, -0.8, 0.5, -0.9, 0.6, 0.2, -0.4]
def _dl(d): return ("up" if d > 0.04 else ("down" if d < -0.04 else "flat")), ("+" if d > 0.04 else ("−" if d < -0.04 else "±")) + f"{abs(d):.1f}"
def weekly_rows():
    """본부별 가동률·가득률 증감 (전주 vs 금주) + 사업부/팀 드릴다운"""
    out = []; k = 0
    tw = {}
    for hq, lst in TEAMS.items():
        T, P, C = HQW[hq]; pp, cc = P/T*100, C/T*100
        nz = [NOISE[(k+i) % len(NOISE)] for i in range(len(lst))]; k += len(lst)
        wm = sum(t[1]*z for t, z in zip(lst, nz))/sum(t[1] for t in lst)
        for (n, tt, off), z in zip(lst, nz):
            pu, cu = pp+off+(z-wm), cc+off
            tw[n] = (tt, pu, cu, pu-GAP[hq]+0.5, cu-GAP[hq])
    def hqv(h):
        T, P, C = HQW[h]; pu, cu = P/T*100, C/T*100
        return (T, pu, cu, pu-GAP[h]+0.5, cu-GAP[h])
    def agg(items):
        T = sum(x[0] for x in items)
        return (T,) + tuple(sum(x[0]*x[j] for x in items)/T for j in range(1, 5))
    def cell3(p, c):
        dc, ds = _dl(round(c, 2)-round(p, 2))
        return f'<td>{p:.2f}%</td><td>{c:.2f}%</td><td class="{dc}">{ds}%p</td>'
    def row(cls, name, v, attrs=""):
        T, pu, cu, pg, cg = v
        g3 = cell3(pg, cg).replace("<td>", '<td class="gc">', 2)
        return f'<tr class="{cls}" {attrs}><td class="l">{name}</td><td>{T:.2f} MM</td>{cell3(pu, cu)}<td class="gsep"></td>{g3}</tr>'
    for corp in ("아이티센클로잇", "아이티센엔텍"):
        hs = [h for h in HQW if HQ_CORP[h] == corp]
        out.append(row("sub", f"{corp} 소계", agg([hqv(h) for h in hs])))
        for h in hs:
            hi = ALLN.index(h)
            out.append(row("org hq child", f'<span class="tw"></span>{h}', hqv(h), f'data-hq="{hi}" tabindex="0"'))
            for dn, tl in DIVS[h]:
                out.append(row("org dv", dn, agg([tw[t] for t in tl]), f'data-parent="{hi}" hidden'))
                for t in tl:
                    out.append(row("org tm", t, tw[t], f'data-parent="{hi}" hidden'))
    total = row("", "전체", agg([hqv(h) for h in HQW]))
    return "\n".join(out), total

WEEKLY_HEAD = ('<thead><tr><th class="l" rowspan="2">법인 / 본부</th><th rowspan="2">가동대상</th><th colspan="3" class="gh">가동률 <small>(이행 · 제안 · R&amp;D·내부과제)</small></th>'
               '<th rowspan="2" class="gsep"></th><th colspan="3" class="gh gh-g">가득률 <small>(이행)</small></th></tr>'
               '<tr><th>전주</th><th>금주</th><th>증감</th><th class="gc">전주</th><th class="gc">금주</th><th class="gc">증감</th></tr></thead>')

# ---- 인사 변동 (당월 기준 · 상태별 표시) ----
HR_NEW = {0, 3, 5}  # 전주 이후 신규 등록 (데모)
def hr_section():
    from collections import Counter
    c = Counter(h[0] for h in HR_CHG)
    chips = "".join(f'<span class="hrc"><b>{c.get(k,0)}</b>{k}</span>' for k in ["입사","퇴사","휴직","복직","전적","전배"])
    trs = "".join(f'<tr class="{"new" if i in HR_NEW else ""}"><td class="c"><span class="pill {p}">{t}</span></td><td class="l">{n}<span class="newtag">신규</span></td><td class="l">{org}</td><td class="c">{d}</td><td class="l">{imp}</td><td class="l muted">{note}</td></tr>' for i, (t,p,n,org,d,imp,note) in enumerate(HR_CHG))
    return f'''
  <!-- HR -->
  <section id="s2" class="card-sec hr-sec" data-state="month">
    <div class="sec-head"><span class="sec-no">02</span><h2>인사 변동</h2>
      <span class="hr-badge b-month">월초 · 10월 전체 표시</span><span class="hr-badge b-none">전주 대비 변동 없음</span><span class="hr-badge b-new">전주 대비 신규 {len(HR_NEW)}건</span>
      <span class="sub">기준: 10월(당월) 누계 · 인사정보 기준 자동 집계</span></div>
    <div class="demo-switch"><em>디자인 확인용</em><button data-s="month" aria-pressed="true">월초</button><button data-s="none" aria-pressed="false">변동 없음</button><button data-s="new" aria-pressed="false">변동 있음</button></div>
    <div class="hr-sum num">{chips}<span class="hr-net">10월 가동대상 영향 합계 <b>+1.80 MM</b> <em>(입사·복직 +3.05 / 퇴사·휴직 −1.25)</em></span></div>
    <details class="hr-list" open><summary><span class="t-open">명단 접기</span><span class="t-closed">10월 명단 보기 ({len(HR_CHG)}건)</span></summary>
    <div class="panel scroll" data-search><table>
      <thead><tr><th class="c">유형</th><th class="l">성명</th><th class="l">소속 (변동)</th><th class="c">적용일</th><th class="l">가동대상MM 영향</th><th class="l">비고</th></tr></thead>
      <tbody>{trs}</tbody>
    </table></div></details>
  </section>
'''

ORG_CSS = r"""
  /* 표 숫자 가운데 정렬 (공통) */
  table th:not(.l),table td:not(.l){text-align:center!important}
  /* 대기인력: 11~12월 음영 없음, 당월 강조 */
  #idle th.fut,#idle td.fut{background:none!important;color:inherit;font-weight:inherit}
  /* 합계 행: 조금 연한 네이비 (공통) */
  tfoot td{background:#3D5D84!important;color:#fff!important}
  .mtab tr.sub td{background:#EEF2F7!important}
  /* drilldown rows */
  tr.org.hq{cursor:pointer}
  tr.org.hq:hover td{background:#F3F6FA!important}
  tr.org .tw{display:inline-block;width:0;height:0;border-left:5px solid var(--steel);border-top:4px solid transparent;border-bottom:4px solid transparent;margin-right:7px;vertical-align:1px;transition:transform .15s}
  tr.org.hq.open .tw{transform:rotate(90deg)}
  tr.org.hq.open td{background:var(--blue-gray)!important;font-weight:700;color:var(--navy)}
  tr.org.dv td{background:#FAFBFD!important;font-weight:600}
  tr.org.dv td:first-child{padding-left:30px}
  tr.org.tm td{color:#374151}
  tr.org.tm td:first-child{padding-left:46px}
  tr.org.dv td:first-child::before,tr.org.tm td:first-child::before{content:"└ ";color:#A9B8C8}
  .mtab tr.org{cursor:pointer}
  .mtab tr.org.sel td{box-shadow:inset 0 -2px 0 var(--navy)}
  tr.detail-row>td{padding:0!important;background:#fff!important}
  .od{outline:2px solid var(--navy);outline-offset:-2px;border:0;margin:6px 0 10px;padding:12px 0;background:#FAFBFD}
  .od>.od-h{padding:0 14px}
  .tp-detail .od{outline:0}
  .od-h{display:flex;align-items:baseline;gap:10px;margin-bottom:8px;flex-wrap:wrap}
  .od-h b{font-size:14px;color:var(--navy)} .od-h span{font-size:12px;color:var(--muted)}
  .od-h button{margin-left:auto;height:28px}
  .od table td,.od table th{padding:5px 7px;font-size:12px}
  .od tr.rate td{font-weight:700;color:var(--navy);background:var(--blue-gray)}
  .od tr.rate td:first-child{color:var(--navy)}
  /* 04 예상 */
  /* 예상 = 음영 · 당월 = 진한 음영 + 네이비 굵게 (공통) */
  table.mtab td.est,.od td.est,.tp-tab td.es{background:#F1F4F8!important;color:var(--text)!important;font-weight:700;font-style:normal;border-left:none!important}
  table.mtab th.est,.od th.est,.tp-tab th.es{background:#E9EEF4!important;color:#374151!important;border-left:none!important}
  /* 당월 = 배경은 그대로, 글자만 빨강 (공통) */
  /* 당월 = 네이비 테두리로 열 강조 + 굵은 네이비 글씨 (공통) */
  table td.cm,table th.cm,table.mtab td.est.cm,table.mtab th.est.cm,.od td.est.cm,.od th.est.cm,table.mtab tr.sub td.est.cm{color:var(--navy)!important;font-weight:800!important;box-shadow:inset 2px 0 0 #2A5A9B,inset -2px 0 0 #2A5A9B}
  table th.cm,table.mtab th.est.cm,.od th.est.cm{box-shadow:inset 2px 0 0 #2A5A9B,inset -2px 0 0 #2A5A9B,inset 0 3px 0 #2A5A9B}
  table th.cm small{display:inline-block;margin-top:2px;background:#2A5A9B;color:#fff!important;font-size:9.5px;font-weight:700;padding:0 6px;border-radius:8px;opacity:1}
  table tbody tr:last-child td.cm{box-shadow:inset 2px 0 0 #2A5A9B,inset -2px 0 0 #2A5A9B,inset 0 -2px 0 #2A5A9B}
  table.mtab th.grp-c{background:#3D5D84!important}
  th small{display:block;font-size:10px;font-weight:500;color:#6B7280}
  table.mtab th.grp-e{background:#E9EEF4!important;color:#374151!important;border-bottom:none!important;text-align:center}
  table.mtab .e1,.od .e1{border-left:none!important}
  table.mtab tfoot td.est{background:#4A6A90!important;color:#fff!important}
  table.mtab tfoot td.cm,tfoot td.cm{color:#FFC4C4!important}
  table.mtab tr.sub td.est{background:#E6EBF1!important}
  /* mini header */
  .mini .mh{flex-wrap:wrap;row-gap:4px}
  .mini .mh>b{flex:1 1 100%}
  .mh .cur{display:flex;align-items:baseline;gap:6px}
  .mh .cur em{font-style:normal;font-size:11px;color:#fff;background:var(--navy);padding:1px 6px;border-radius:2px}
  .mh .cur strong{font-size:17px;color:var(--navy);letter-spacing:-.02em}
  .mh .cur i{font-style:normal;font-size:11.5px;font-weight:600}
  .mh .cur i.up{color:var(--good)} .mh .cur i.down{color:var(--warn)}
  /* HR states */
  .hr-badge{display:none;font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:10px}
  .hr-sec[data-state=month] .b-month{display:inline-block;background:var(--navy);color:#fff}
  .hr-sec[data-state=none] .b-none{display:inline-block;background:#EEF0F3;color:#4B5563}
  .hr-sec[data-state=new] .b-new{display:inline-block;background:var(--warn-bg);color:var(--warn)}
  .demo-switch{display:flex;gap:4px;align-items:center;margin:-6px 0 10px;font-size:11.5px}
  .demo-switch em{font-style:normal;color:var(--steel);background:var(--blue-gray);padding:2px 8px;margin-right:4px}
  .demo-switch button{font:inherit;font-size:11.5px;border:1px solid var(--line);background:#fff;padding:2px 9px;cursor:pointer}
  .demo-switch button[aria-pressed=true]{border-color:var(--navy);color:var(--navy);font-weight:700}
  details.hr-list>summary{font-size:12.5px;color:var(--steel);font-weight:600;padding:4px 0 8px;list-style:none;cursor:pointer}
  details.hr-list>summary::-webkit-details-marker{display:none}
  details.hr-list>summary::before{content:"▸ ";} details.hr-list[open]>summary::before{content:"▾ ";}
  details.hr-list .t-open{display:none} details.hr-list[open] .t-open{display:inline} details.hr-list[open] .t-closed{display:none}
  .newtag{display:none;font-size:10px;font-weight:700;color:var(--warn);background:var(--warn-bg);padding:0 5px;margin-left:5px}
  .hr-sec[data-state=new] tr.new .newtag{display:inline-block}
  .hr-sec[data-state=new] tr.new td{background:#FFFBF5!important}
  table.mtab tfoot td.est.cm,table tfoot td.cm{color:#fff!important;box-shadow:inset 2px 0 0 #9DB7DA,inset -2px 0 0 #9DB7DA,inset 0 -2px 0 #9DB7DA}
  @media print{ .demo-switch{display:none} tr.org[hidden]{display:none} }
"""

ORG_JS = r"""
// ---- weekly: 본부 클릭 → 사업부/팀 펼침 ----
document.querySelectorAll('#v-report tr.org.hq').forEach(r=>{
  const tb=r.parentElement;
  const tog=()=>{const on=!r.classList.contains('open');r.classList.toggle('open',on);
    tb.querySelectorAll(`tr[data-parent="${r.dataset.hq}"]`).forEach(x=>x.hidden=!on)};
  r.addEventListener('click',tog); r.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();tog()}});
});
// ---- annual 04: 본부 → 사업부/팀, 조직 클릭 → 월별 실적 ----
const ORG=__ORG__;
const MONS=['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];
function f1(v){return v.toFixed(2)}
function orgDetail(key){
  const o=ORG[key]; const est=i=>i>=9?' class="est'+(i===9?' cm':'')+'"':'';
  const line=(lab,arr,rate,cls)=>`<tr class="${cls||''}"><td class="l">${lab}</td>${arr.map((v,i)=>`<td${est(i)}>${rate?f1(v)+'%':f1(v)}</td>`).join('')}<td class="strong">${rate?f1(arr.reduce((a,b)=>a+b,0)/12)+'%':f1(arr.reduce((a,b)=>a+b,0))}</td></tr>`;
  return `<div class="od"><div class="od-h"><b>${o.name}</b><span>${o.path.endsWith(" › "+o.name)?o.path.slice(0,-(o.name.length+3)):o.path} · 월별 실적 (MM) · 회색 음영 = 예상 · 파란 테두리 = 당월</span><button class="tbtn od-x">닫기 ✕</button></div>
   <div class="scroll"><table><thead><tr><th class="l">구분</th>${MONS.map((m,i)=>`<th${est(i)}>${m}</th>`).join('')}<th>연간</th></tr></thead><tbody>
   ${line('가동대상',o.T)}${line('이행 (가득)',o.ex)}${line('제안',o.pr)}${line('R&D·내부과제',o.rd)}${line('대기',o.idle)}
   ${line('가동률',o.u,true,'rate')}${line('가득률',o.g,true,'rate')}</tbody></table></div></div>`;
}
function alignDet(d){ /* ALIGN_V4: 위 줄의 칸 폭을 '비율(%)'로 맞춤 — 화면 확대·표 선 두께와 무관하게 같은 위치 */
  const t=d.querySelector('.od .scroll>table'); const row=d.previousElementSibling; if(!row||!t) return;
  const rr=row.getBoundingClientRect();
  const ws=[...row.children].map(c=>c.getBoundingClientRect().width); const tot=ws.reduce((a,b)=>a+b,0); if(!tot||!rr.width) return;
  t.style.tableLayout='fixed'; t.style.maxWidth='none'; t.style.minWidth='0'; t.style.marginLeft='0px'; t.style.width='100%';
  const old=t.querySelector('colgroup'); if(old) old.remove();
  const cg=document.createElement('colgroup');
  ws.forEach(x=>{if(x<1) return; const c=document.createElement('col'); c.style.width=(x/tot*100).toFixed(4)+'%'; cg.appendChild(c)}); t.prepend(cg);
  [...t.rows].forEach(r=>[...r.cells].forEach((c,q)=>{c.style.display=(ws[q]!==undefined&&ws[q]<1)?'none':''}));
  /* 패널 안쪽 여백 등으로 위 줄과 폭·왼쪽 끝이 다르면 그만큼 보정 (표 자신의 화면 배율로 환산) */
  let tr=t.getBoundingClientRect(); const kk=t.offsetWidth?tr.width/t.offsetWidth:1;
  if(Math.abs(tr.width-rr.width)>0.5){ t.style.width=(t.offsetWidth*rr.width/tr.width)+'px'; tr=t.getBoundingClientRect(); }
  const dl=(rr.left-tr.left)/kk; if(Math.abs(dl)>0.3) t.style.marginLeft=dl.toFixed(2)+'px';
}
window.__ca_done=()=>{ if(typeof openDet!=='undefined'&&openDet) alignDet(openDet.det) };
window.addEventListener('resize',()=>{ if(openDet) alignDet(openDet.det) });
let openDet=null;
function closeDet(){ if(openDet){openDet.row.classList.remove('sel');openDet.det.remove();openDet=null} }
document.querySelectorAll('.mtab tr.org').forEach(r=>{
  const act=()=>{
    const same=openDet&&openDet.row===r; closeDet();
    if(r.classList.contains('hq')){
      const tb=r.parentElement; const on=!r.classList.contains('open')||!same;
      if(same){ r.classList.remove('open'); tb.querySelectorAll(`tr[data-parent="${r.dataset.hq}"]`).forEach(x=>x.hidden=true); return }
      r.classList.add('open'); tb.querySelectorAll(`tr[data-parent="${r.dataset.hq}"]`).forEach(x=>x.hidden=false);
    } else if(same) return;
    const d=document.createElement('tr'); d.className='detail-row'; d.innerHTML=`<td colspan="14">${orgDetail(r.dataset.key)}</td>`;
    r.after(d); r.classList.add('sel'); openDet={row:r,det:d}; alignDet(d); [200,800].forEach(ms=>setTimeout(()=>{if(openDet&&openDet.det===d)alignDet(d)},ms));
    d.querySelector('.od-x').addEventListener('click',e=>{e.stopPropagation();closeDet()});
  };
  r.addEventListener('click',act); r.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();act()}});
});
// ---- 인사 변동 상태 ----
const hrSec=document.querySelector('.hr-sec');
function hrState(s){ hrSec.dataset.state=s; hrSec.querySelector('details.hr-list').open=(s!=='none');
  hrSec.querySelectorAll('.demo-switch button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.s===s)); }
if(hrSec){ hrSec.querySelectorAll('.demo-switch button').forEach(b=>b.addEventListener('click',()=>hrState(b.dataset.s))); }
"""

WEEKLY_CSS = r"""
  .row2.wide{grid-template-columns:1.7fr 1fr}
  th.gh{text-align:center!important;background:#DCE4EE!important}
  th.gh-g{background:#C9D6E5!important;color:var(--navy)!important}
  th.gh small{font-weight:500;opacity:.8}
  td.gc{background:#F6F8FC}
  tr.org.hq.open td.gc,tr.sub td.gc{background:inherit}
  th.gsep,td.gsep{width:6px;padding:0!important;background:#fff!important;border-bottom:none!important}
  tfoot td.gsep{background:#fff!important}
  tfoot td.gc{background:#4A6A90!important;color:#fff!important}
  th.gh small{display:inline;font-size:11px;font-weight:500;color:#4B5563}
  @media (max-width:1300px){ .row2.wide{grid-template-columns:1fr} }
  @media print{ .row2.wide{grid-template-columns:1fr!important} }
"""

# ALIGN_V3
