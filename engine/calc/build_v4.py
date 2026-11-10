import re
D = __import__('cfg').WORK
t = open(__import__('cfg').c("tpl.html"), encoding="utf-8").read()

css_old = t[t.index("<style>") + 7 : t.index("</style>")]
body = t[t.index("  <!-- 1 -->") : t.index("<script>")]
body = body[: body.rindex("</div>")]          # drop closing of .page
js_old = t[t.index("<script>") + 8 : t.index("</script>")].replace("const box=document.getElementById(tabs.dataset.scope);","const box=document.getElementById(tabs.dataset.scope); if(!box) return;")

# --- section tweaks ---
for i in range(1, 5):
    body = body.replace(f'<span class="sec-no">{i}</span>', f'<span class="sec-no">0{i}</span>')
body = body.replace("  <!-- 1 -->\n  <section>", '  <!-- 1 -->\n  <section id="s1" class="card-sec">', 1)
body = body.replace("  <!-- 2 -->\n  <section>", '  <!-- 2 -->\n  <section id="s2" class="card-sec">', 1)
body = body.replace('  <section class="sec-3">', '  <section id="s3" class="card-sec sec-3 detail">', 1)
body = body.replace("  <!-- 4 -->\n  <section>", '  <!-- 4 -->\n  <section id="s4" class="card-sec detail">', 1)
body = body.replace("  <footer>\n    <h3>금주 코멘트</h3>",
  '  <section id="s5" class="card-sec">\n    <div class="sec-head"><span class="sec-no">05</span><h2>금주 코멘트</h2><span class="sub">관리자 입력</span></div>\n    <div class="comment-box">')
body = body.replace("  </footer>", "    </div>\n  </section>")
# excel buttons into tabs tools
body = body.replace('<span class="tools"><button data-act="open">',
                    '<span class="tools"><button data-act="csv">엑셀 다운로드</button><button data-act="open">')
# search target attribute
body = body.replace('<div id="idle">', '<div id="idle" data-search>').replace('<div id="proj">', '<div id="proj" data-search>')
import sys; sys.path.insert(0, D); import v4_extra as X
_cf = __import__('cfg'); _PM = _cf.CUR - 1
import real_views as R
body = X.transform_report(body)

I = {  # inline icons (stroke)
 "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
 "alert": '<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17v.5"/>',
 "idle":  '<circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-6 7-6"/><circle cx="17" cy="17" r="4"/><path d="M17 15v2l1.5 1"/>',
 "lab":   '<path d="M9 3h6M10 3v6L4 20h16L14 9V3"/><path d="M7 15h10"/>',
 "note":  '<path d="M4 4h16v12H8l-4 4V4z"/><path d="M8 9h8M8 12h5"/>',
 "upload":'<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v4h16v-4"/>',
 "check": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1.5 1.5L7 5M3 12l1.5 1.5L7 11M3 18l1.5 1.5L7 17"/>',
 "gear":  '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>',
 "search":'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
 "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 "type":  '<path d="M4 7V4h12v3M10 4v16M7 20h6"/><path d="M15 13h6M18 13v7"/>',
 "print": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="1"/><path d="M6 14h12v7H6z"/>',
}
def ic(n, s=20): return f'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{I[n]}</svg>'

css_new = r"""
  /* ===== Site shell ===== */
  body{padding:0;background:var(--bg-sub)}
  :root{--hdr:60px;--rail:84px;--z:1;--lh:1.5}
  .topbar{position:sticky;top:0;z-index:30;height:var(--hdr);background:#fff;color:var(--text);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:20px;padding:0 20px}
  .brand{display:flex;align-items:baseline;gap:10px;white-space:nowrap}
  .brand .bic{width:26px;height:26px;border-radius:6px;align-self:center;margin-right:-2px}
  .brand b{font-size:20px;font-weight:800;color:var(--navy);letter-spacing:-.02em}
  .brand b span{color:var(--steel)}
  .brand small{font-size:12px;color:var(--muted)}
  .gnb{display:flex;gap:2px;height:100%}
  .gnb a{display:flex;align-items:center;padding:0 14px;font-size:14.5px;font-weight:600;color:#374151;text-decoration:none;border-bottom:3px solid transparent;white-space:nowrap}
  .gnb a:hover{color:var(--navy)}
  .gnb a.on{color:var(--navy);border-bottom-color:var(--navy)}
  .tools-top{margin-left:auto;display:flex;align-items:center;gap:8px}
  .search{position:relative;display:flex;align-items:center;border:1px solid #D1D5DB;height:36px;width:230px;padding:0 10px;gap:6px;color:var(--muted);background:#fff}
  .search:focus-within{border-color:var(--navy);box-shadow:0 0 0 2px var(--blue-gray)}
  .search input{border:none;outline:none;font:inherit;font-size:13px;flex:1;min-width:0;color:var(--text)}
  .search .cnt{font-size:12px;color:var(--navy);font-weight:700}
  .search .x{border:none;background:none;cursor:pointer;color:var(--muted);font-size:14px;display:none}
  .search.has .x{display:block}
  .tbtn{height:36px;display:inline-flex;align-items:center;gap:6px;padding:0 12px;border:1px solid #D1D5DB;background:#fff;font:inherit;font-size:13px;font-weight:600;color:#374151;cursor:pointer;white-space:nowrap}
  .tbtn:hover{border-color:var(--navy);color:var(--navy)}
  .tbtn[aria-pressed="true"]{background:var(--blue-gray);border-color:var(--navy);color:var(--navy)}
  .user{display:flex;align-items:center;gap:8px;padding-left:8px;border-left:1px solid var(--line);margin-left:4px}
  .avatar{width:32px;height:32px;border-radius:50%;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
  .user div{font-size:12.5px;line-height:1.3}
  .user div small{display:block;color:var(--muted);font-size:11px}

  .rail{position:fixed;top:var(--hdr);left:0;bottom:0;width:var(--rail);background:#fff;border-right:1px solid var(--line);padding:14px 0;overflow-y:auto;z-index:20}
  .rail .grp{display:none}
  .rail .grp.on{display:block}
  .rail a{display:flex;flex-direction:column;align-items:center;gap:4px;padding:10px 4px;font-size:11.5px;color:#4B5563;text-decoration:none;text-align:center;line-height:1.25;border-left:3px solid transparent}
  .rail a:hover{color:var(--navy);background:var(--bg-sub)}
  .rail a.on{color:var(--navy);font-weight:700;border-left-color:var(--navy);background:var(--blue-gray)}
  .rail hr{border:none;border-top:1px solid var(--line);margin:10px 12px}
  .rail .cap{font-size:10.5px;color:#9CA3AF;text-align:center;padding:4px}

  .main{margin-left:var(--rail);padding:20px 24px 40px;zoom:var(--z)}
  .main, .main p, .main li{line-height:var(--lh)}
  .titlebar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:4px 0 16px}
  .titlebar h1{font-size:20px;color:var(--navy);margin:0;padding-left:12px;border-left:4px solid var(--navy);line-height:1.2}
  .titlebar .crumb{font-size:13px;color:var(--muted)}
  .titlebar select{height:32px;border:1px solid #D1D5DB;font:inherit;font-size:13px;padding:0 8px;background:#fff;color:var(--navy);font-weight:600}
  .chip{font-size:12px;padding:3px 10px;border:1px solid #C3D0DE;color:var(--steel);background:#fff;white-space:nowrap}
  .chip.solid{background:var(--navy);border-color:var(--navy);color:#fff;font-weight:600}
  .titlebar .meta2{margin-left:auto;font-size:12px;color:var(--muted);text-align:right}
  .titlebar .meta2 b{color:var(--text);font-weight:600}

  .card-sec{background:#fff;border:1px solid var(--line);border-radius:6px;margin-bottom:16px;padding:22px 26px}
  section+section{border-top:1px solid var(--line)}
  .sec-no{background:var(--blue-gray)!important;color:var(--navy)!important;font-size:12.5px!important;padding:2px 7px!important}
  .comment-box ul{padding-left:18px;display:flex;flex-direction:column;gap:5px;font-size:13px}
  .foot-note{border:none!important;padding:4px 4px 0!important}

  .summary-banner{display:none;background:var(--blue-gray);border:1px solid #C3D0DE;color:var(--navy);font-size:13px;padding:10px 16px;margin-bottom:16px;border-radius:6px}
  body.sum .summary-banner{display:block}
  body.sum .detail{display:none}

  mark.hit{background:#FDE68A;color:inherit;padding:0 1px}
  tr.hitrow td{background:#FFFBEB!important}

  .pop{position:absolute;top:calc(var(--hdr) - 4px);right:120px;width:320px;background:#fff;border:1px solid var(--line);box-shadow:0 10px 30px rgba(15,41,66,.15);padding:16px;z-index:40;display:none}
  .pop.on{display:block}
  .pop h4{font-size:15px;color:var(--navy);margin-bottom:2px}
  .pop .d{font-size:12px;color:var(--muted);margin-bottom:12px}
  .pop .lb{font-size:12.5px;font-weight:600;margin:10px 0 6px}
  .seg{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:6px}
  .seg button{height:34px;border:1px solid var(--line);background:#fff;font:inherit;font-size:12.5px;cursor:pointer}
  .seg button[aria-pressed="true"]{border-color:var(--navy);background:var(--blue-gray);color:var(--navy);font-weight:700}
  .pop .acts{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:14px}
  .pop .acts button{height:36px;border:1px solid var(--line);background:#fff;font:inherit;font-size:13px;font-weight:600;cursor:pointer}
  .pop .acts button.pri{background:var(--navy);border-color:var(--navy);color:#fff}
  body.hc{--muted:#374151;--line:#9CA3AF;--text:#000}

  /* other pages (mock) */
  .view{display:none}.view.on{display:block}
  .drop{border:2px dashed #A9B8C8;background:#FAFBFD;padding:34px;text-align:center;color:var(--muted);border-radius:6px}
  .drop b{display:block;color:var(--navy);font-size:15px;margin:8px 0 4px}
  .drop .row{display:flex;gap:8px;justify-content:center;margin-top:14px;flex-wrap:wrap}
  .steps{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
  .steps div{border:1px solid var(--line);background:#fff;padding:12px 14px;font-size:12.5px;color:var(--muted)}
  .steps b{display:block;color:var(--navy);font-size:13.5px}
  .prog{height:8px;background:var(--bg-sub);margin-top:6px}.prog i{display:block;height:100%;background:var(--navy)}
  .mock-note{font-size:11.5px;color:var(--steel);background:var(--blue-gray);display:inline-block;padding:2px 8px;margin-bottom:12px}

  @media (max-width:1100px){ .gnb a{padding:0 9px;font-size:13.5px} .search{width:160px} .user div{display:none} }
  @media (max-width:860px){
    .gnb,.brand small,.tbtn span.t{display:none}
    .rail{display:none}.main{margin-left:0;padding:14px 12px}
    .card-sec{padding:16px}
    .search{width:auto;flex:1;min-width:0}
    .user,#btnRead{display:none}
    .brand b{font-size:17px}
    .topbar{gap:10px;padding:0 12px}
    .tbtn{padding:0 9px}
    .card-sec{overflow-x:auto}
    .titlebar .meta2{margin-left:0;text-align:left}
    .tools-top{flex:1}
    .steps{grid-template-columns:1fr 1fr}
  }
  @media print{
    .topbar,.rail,.titlebar select,.summary-banner,.tabs,.pop{display:none!important}
    .main{margin:0;padding:0;zoom:1}
    .card-sec{border:none;border-radius:0;padding:12px 0;margin:0;border-top:1px solid var(--line)}
    .view:not(#v-report){display:none!important}
    .kpis{grid-template-columns:repeat(5,1fr)!important}
    .row2{grid-template-columns:1fr 1fr!important}
    .corp-cols{grid-template-columns:1.4fr 1fr!important}
    .titlebar .meta2{margin-left:auto!important}
    .card-sec{overflow:visible!important}
    .scroll{overflow:visible!important}
    .row2 th,.row2 td{padding:4px 4px!important;font-size:7.5pt!important;white-space:normal!important}
    .row2 table{table-layout:fixed}
    .row2 td:first-child,.row2 th:first-child{width:28%}
    .share .bar{width:36px!important}
    .row2 .note{display:none}
  }
"""

ADMIN_ICON = "%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 512 512%22 width=%22512%22 height=%22512%22%3E%3Crect width=%22512%22 height=%22512%22 rx=%22112%22 fill=%22%230F2942%22/%3E%3Cpath d=%22M108.9,403.1 A208,208 0 0 1 103.8,114.2 L146.3,153.7 A150,150 0 0 0 149.9,362.1 Z%22 fill=%22%23E8847A%22/%3E%3Cpath d=%22M115.2,102.9 A208,208 0 0 1 396.8,102.9 L357.6,145.6 A150,150 0 0 0 154.4,145.6 Z%22 fill=%22%23F2CB5C%22/%3E%3Cpath d=%22M408.2,114.2 A208,208 0 0 1 403.1,403.1 L362.1,362.1 A150,150 0 0 0 365.7,153.7 Z%22 fill=%22%235FCB8A%22/%3E%3Cpolygon points=%22434.6,278.6 289.9,253.7 288.3,266.6%22 fill=%22%238DB6EC%22/%3E%3Cpolygon points=%22433.3,172.5 282.0,234.1 289.5,250.0%22 fill=%22%23F0A04B%22/%3E%3Ccircle cx=%22256%22 cy=%22256%22 r=%2230%22 fill=%22%23fff%22/%3E%3C/svg%3E"
shell_top = f"""
<header class="topbar">
  <div class="brand"><img class="bic" alt="" src="data:image/svg+xml,{ADMIN_ICON}"><b>MM-<span>Compass</span></b><small>인력 가동 현황</small></div>
  <nav class="gnb" aria-label="주 메뉴">
    <a href="#report" data-view="report" class="on">주간 리포트</a>
    <a href="#annual" data-view="annual">연간 대시보드</a>
    <a href="#upload" data-view="upload">투입계획 업로드</a>
    <a href="#hr" data-view="hr">인사정보</a>
    <a href="#proj" data-view="proj">프로젝트정보</a>
    <a href="#master" data-view="master">기준정보</a>
  </nav>
  <div class="tools-top">
    <label class="search" id="srch">{ic('search',16)}<input id="q" placeholder="성명 · 조직 · 과제 검색" aria-label="검색"><span class="cnt" id="qc"></span><button class="x" id="qx" aria-label="지우기">✕</button></label>
    <button class="tbtn" id="btnSum" aria-pressed="false">{ic('clock',16)}<span class="t">회의 요약</span></button>
    <button class="tbtn" id="btnRead" aria-pressed="false">{ic('type',16)}<span class="t">읽기 설정</span></button>
    <div class="user"><span class="avatar">인</span><div>인력관리팀<small>관리자</small></div></div>
  </div>
</header>

<div class="pop" id="pop" role="dialog" aria-label="읽기 설정">
  <h4>읽기 설정</h4>
  <div class="d">회의실 화면·모니터에 맞게 조정합니다.</div>
  <div class="lb">글자 크기</div>
  <div class="seg" data-k="z"><button data-v="0.9">작게</button><button data-v="1" aria-pressed="true">기본</button><button data-v="1.12">크게</button><button data-v="1.25">더 크게</button></div>
  <div class="lb">줄 간격</div>
  <div class="seg" data-k="lh"><button data-v="1.35">촘촘히</button><button data-v="1.5" aria-pressed="true">기본</button><button data-v="1.75">넓게</button></div>
  <div class="lb">대비</div>
  <div class="seg" data-k="hc"><button data-v="0" aria-pressed="true">기본</button><button data-v="1">고대비</button></div>
  <div class="acts"><button id="rReset">초기화</button></div>
</div>

<aside class="rail" aria-label="화면 내 메뉴">
  <div class="grp on" data-for="report">
    <a href="#s0">{ic('check')}{_PM}월<br>실적 {'확정' if _PM <= _cf.ACTM else '잠정'}</a>
    <a href="#s1" class="on">{ic('chart')}전주 대비<br>실적</a>
    <a href="#s2">{ic('idle')}인사<br>변동</a>
    <a href="#s3">{ic('alert')}조직별<br>특이사항</a>
    <a href="#s4" class="detail-link">{ic('idle')}대기인력</a>
    <a href="#s5" class="detail-link">{ic('lab')}R&amp;D·<br>내부과제</a>
    <a href="#s6">{ic('note')}금주<br>코멘트</a>
    <hr><div class="cap">{_cf.WEEK.get('short', '')}</div>
  </div>
  <div class="grp" data-for="annual">
    <a href="#a1" class="on">{ic('chart')}전사<br>총괄</a>
    <a href="#a2">{ic('chart')}법인별<br>흐름</a>
    <a href="#a3">{ic('chart')}본부별<br>추이</a>
    <a href="#a4">{ic('check')}본부별<br>가동률</a>
  </div>
  <div class="grp" data-for="upload">
    <a href="#u1" class="on">{ic('upload')}파일<br>업로드</a>
    <a href="#u2">{ic('check')}업로드<br>이력</a>
    <a href="#u3">{ic('check')}제출<br>현황</a>
  </div>
  <div class="grp" data-for="hr">
    <a href="#h1" class="on">{ic('upload')}업로드·<br>연동</a>
    <a href="#h2">{ic('gear')}계산<br>규칙</a>
    <a href="#h3">{ic('idle')}인원별<br>가동대상</a>
  </div>
  <div class="grp" data-for="proj">
    <a href="#p1" class="on">{ic('gear')}분류<br>규칙</a>
    <a href="#p2">{ic('lab')}프로젝트<br>목록</a>
  </div>
  <div class="grp" data-for="master">
    <a href="#m1" class="on">{ic('gear')}조직·<br>기준정보</a>
  </div>
</aside>

<main class="main">
<div class="view on" id="v-report">
  <div class="titlebar">
    <h1>2026년 {_cf.CUR}월 인력 가동 현황 리포트</h1>
    <select aria-label="기준 주차"><option>{_cf.WEEK.get('short', '')} ({_cf.WEEK.get('asof', '')})</option></select>
    <span class="chip solid">클로잇 + 아이티센엔텍</span>
    <span class="chip">실적 {_cf.R(1, _cf.ACTM)}{''.join(f' · {m}월 잠정' for m in _cf.PROV)} · {_cf.R(max(_cf.ACTM + 1, _cf.CUR))} 예상</span>
    <div class="meta2">데이터 기준 <b>{_cf.WEEK.get('asof', '')}</b> · 가동가득 통계{f"({_cf.WEEK.get('stats_date')})" if _cf.WEEK.get('stats_date') else ''} 기준</div>
  </div>
  <div class="summary-banner"><b>회의 요약 모드</b> · 실적 확정, 01 실적, 02 인사 변동, 03 특이사항, 06 코멘트만 표시합니다. 상단 「회의 요약」을 다시 누르면 전체로 돌아갑니다.</div>
"""

views_other = "\n</div>\n" + X.annual_view(ic) + X.upload_view(ic) + R.hr_view_real(ic) + R.proj_view_real(ic) + X.master_view() + "\n</main>\n"

js_new = r"""
// ---- page views (top menu) ----
const views=['report','annual','upload','hr','proj','master'];
function show(v){ if(!views.includes(v)) v='report';
  document.querySelectorAll('.view').forEach(x=>x.classList.toggle('on',x.id==='v-'+v));
  document.querySelectorAll('.gnb a').forEach(a=>a.classList.toggle('on',a.dataset.view===v));
  document.querySelectorAll('.rail .grp').forEach(g=>g.classList.toggle('on',g.dataset.for===v));
  window.scrollTo(0,0);
}
document.querySelectorAll('.gnb a').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();show(a.dataset.view)}));
// ---- left rail scroll + scrollspy ----
const railLinks=[...document.querySelectorAll('.rail .grp[data-for=report] a')];
railLinks.forEach(a=>a.addEventListener('click',e=>{e.preventDefault();const el=document.querySelector(a.getAttribute('href'));
  if(el&&el.offsetParent!==null) window.scrollTo({top:el.getBoundingClientRect().top+scrollY-76,behavior:'smooth'})}));
const io=new IntersectionObserver(es=>{es.forEach(en=>{if(en.isIntersecting){railLinks.forEach(a=>a.classList.toggle('on',a.getAttribute('href')==='#'+en.target.id))}})},{rootMargin:'-80px 0px -60% 0px'});
document.querySelectorAll('#v-report .card-sec[id]').forEach(s=>io.observe(s));
// ---- meeting summary mode ----
const btnSum=document.getElementById('btnSum');
function setSum(on){document.body.classList.toggle('sum',on);btnSum.setAttribute('aria-pressed',on);
  document.querySelectorAll('.detail-link').forEach(a=>a.style.display=on?'none':'')}
btnSum.addEventListener('click',()=>setSum(btnSum.getAttribute('aria-pressed')!=='true'));
// ---- reading settings ----
const pop=document.getElementById('pop'),btnRead=document.getElementById('btnRead');
btnRead.addEventListener('click',e=>{e.stopPropagation();const on=!pop.classList.contains('on');pop.classList.toggle('on',on);btnRead.setAttribute('aria-pressed',on)});
document.addEventListener('click',e=>{if(!pop.contains(e.target)&&e.target!==btnRead){pop.classList.remove('on');btnRead.setAttribute('aria-pressed',false)}});
let userZ=1;
function autoZ(){const w=window.innerWidth; if(w<=860)return 1; return Math.max(0.85,Math.min(1.3,(w-84)/1700))}
function updZ(){const z=userZ*autoZ();document.documentElement.style.setProperty('--z',z.toFixed(3));
  /* 아주 큰 화면(4K 등): 본문 폭에 상한을 두고 가운데로 */
  const m=document.querySelector('.main');if(m){const MAXW=1900,rail=84;m.style.maxWidth=MAXW+'px';
    const extra=window.innerWidth>860?Math.max(0,(window.innerWidth/z-rail-MAXW)/2):0;m.style.marginLeft=window.innerWidth>860?(rail+extra)+'px':''}}
window.addEventListener('resize',updZ); updZ();
function applySet(k,v){ if(k==='z'){userZ=parseFloat(v)||1;updZ()}
  if(k==='lh')document.documentElement.style.setProperty('--lh',v);
  if(k==='hc')document.body.classList.toggle('hc',v==='1');}
pop.querySelectorAll('.seg').forEach(seg=>seg.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  seg.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));applySet(seg.dataset.k,b.dataset.v)})));
document.getElementById('rReset').addEventListener('click',()=>pop.querySelectorAll('.seg').forEach(seg=>{
  const def=seg.querySelector('[data-v="1"],[data-v="1.5"],[data-v="0"]');def.click()}));
// ---- search (name / org / project) ----
const q=document.getElementById('q'),qc=document.getElementById('qc'),srch=document.getElementById('srch');
const marked=[];
function clearHits(){document.querySelectorAll('mark.hit').forEach(m=>m.replaceWith(document.createTextNode(m.textContent)));
  document.querySelectorAll('tr.hitrow').forEach(r=>r.classList.remove('hitrow'));document.querySelectorAll('[data-search]').forEach(b=>b.normalize())}
function runSearch(){ clearHits(); const s=q.value.trim(); srch.classList.toggle('has',!!s); if(!s){qc.textContent='';return}
  if(document.body.classList.contains('sum')) setSum(false);
  let n=0, first=null;
  document.querySelectorAll('.view.on [data-search] tbody tr, .view.on [data-search] summary').forEach(row=>{
    if(!row.textContent.includes(s)) return;
    const det=row.closest('details'); if(det){det.open=true; det.style.display='';}
    if(row.tagName==='TR'){row.classList.add('hitrow'); n++}
    const w=document.createTreeWalker(row,NodeFilter.SHOW_TEXT); const ns=[]; while(w.nextNode()) if(w.currentNode.nodeValue.includes(s)) ns.push(w.currentNode);
    ns.forEach(t=>{const i=t.nodeValue.indexOf(s);const m=document.createElement('mark');m.className='hit';const r=t.splitText(i);r.splitText(s.length);m.textContent=r.nodeValue;r.replaceWith(m)});
    if(!first) first=row;
  });
  document.querySelectorAll('.tabs [data-f=all]').forEach(b=>b.click());
  qc.textContent=n+'건'; if(first) window.scrollTo({top:first.getBoundingClientRect().top+scrollY-120,behavior:'smooth'});
}
let tm; q.addEventListener('input',()=>{clearTimeout(tm);tm=setTimeout(runSearch,250)});
document.getElementById('qx').addEventListener('click',e=>{e.preventDefault();q.value='';runSearch()});
// ---- excel (csv) download ----
document.querySelectorAll('[data-act=csv]').forEach(b=>b.addEventListener('click',()=>{
  const box=document.getElementById(b.closest('.tabs').dataset.scope); const rows=[];
  box.querySelectorAll('details').forEach(d=>{ if(d.style.display==='none') return;
    const grp=d.querySelector('.g-name').innerText.replace(/\s+/g,' ').trim();
    const head=[...d.querySelectorAll('thead th')].map(th=>th.innerText); if(!rows.length) rows.push(['구분',...head]);
    d.querySelectorAll('tbody tr').forEach(tr=>rows.push([grp,...[...tr.cells].map(td=>td.innerText.replace(/\s+/g,' ').trim())]))});
  const csv='﻿'+rows.map(r=>r.map(c=>'"'+c.replace(/"/g,'""')+'"').join(',')).join('\r\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download=(box.id==='idle'?'대기인력':'RnD_내부과제')+'.csv';a.click();
}));
"""

out = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<title>MM-Compass (MM 나침반) · 인력 가동 현황</title><link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 512 512%22 width=%22512%22 height=%22512%22 xmlns:c2pa=%22http://c2pa.org/manifest%22%3E%3Cmetadata%3E%3Cc2pa:manifest%3EAAAWgmp1bWIAAAAeanVtZGMycGEAEQAQgAAAqgA4m3EDYzJwYQAAABZcanVtYgAAAEdqdW1kYzJtYQARABCAAACqADibcQN1cm46YzJwYTpmYmI1NmZjNy1mZTU5LTQ4NmItOWI0Ni0zMjk0NDQ2ZGQyODAAAAADl2p1bWIAAAApanVtZGMyYXMAEQAQgAAAqgA4m3EDYzJwYS5hc3NlcnRpb25zAAAAALxqdW1iAAAARGp1bWRjYm9yABEAEIAAAKoAOJtxE2MycGEuaW5ncmVkaWVudC52MwAAAAAYYzJzaE7/tOzrw%2BHHVJmKdsX4fsMAAABwY2JvcqNpZGM6Zm9ybWF0bWltYWdlL3N2Zyt4bWxqaW5zdGFuY2VJRHgseG1wOmlpZDpmYWM4MmY1NS1mMTdhLTRhZjctYTA2Ni00OGMwZjIzYTYwMzBscmVsYXRpb25zaGlwaHBhcmVudE9mAAAB4mp1bWIAAABBanVtZGNib3IAEQAQgAAAqgA4m3ETYzJwYS5hY3Rpb25zLnYyAAAAABhjMnNoBlUhBtoA0FsjtJzBnG5QrQAAAZljYm9yomdhY3Rpb25zgqJmYWN0aW9ua2MycGEub3BlbmVkanBhcmFtZXRlcnOha2luZ3JlZGllbnRzgaJjdXJseC1zZWxmI2p1bWJmPWMycGEuYXNzZXJ0aW9ucy9jMnBhLmluZ3JlZGllbnQudjNkaGFzaFggej4a7ADtXZXhoCmUum45HDmMYys%2BiWekeruqSYe73gmkZmFjdGlvbngdY29tLmFudGhyb3BpYy5jbGF1ZGUucHJvdmlkZWRqcGFyYW1ldGVyc6F4H2NvbS5hbnRocm9waWMub3JpZ2luLWNvbmZpZGVuY2VndW5rbm93bmtkZXNjcmlwdGlvbnhmQ2xhdWRlIHByb3ZpZGVkIHRoaXMgZmlsZSBhdCB0aGUgcmVxdWVzdCBvZiBhIHVzZXIgYW5kIG1heSBoYXZlIGNyZWF0ZWQgb3IgbW9kaWZpZWQgdGhlIGZpbGUgY29udGVudHMubXNvZnR3YXJlQWdlbnShZG5hbWVmQ2xhdWRlcmFsbEFjdGlvbnNJbmNsdWRlZPUAAADIanVtYgAAAEBqdW1kY2JvcgARABCAAACqADibcRNjMnBhLmhhc2guZGF0YQAAAAAYYzJzaMM6XSQuduRcQP8rChVXRX8AAACAY2JvcqVjYWxnZnNoYTI1NmNwYWRNAAAAAAAAAAAAAAAAAGRoYXNoWCB6Kew%2BjPMlYZiCMJMjm8RXUCHUCOBrqYrFoxHtk2J%2BLmRuYW1lbmp1bWJmIG1hbmlmZXN0amV4Y2x1c2lvbnOBomVzdGFydBiWZmxlbmd0aBkeBAAAAj5qdW1iAAAAJ2p1bWRjMmNsABEAEIAAAKoAOJtxA2MycGEuY2xhaW0udjIAAAACD2Nib3KlY2FsZ2ZzaGEyNTZpc2lnbmF0dXJleE1zZWxmI2p1bWJmPS9jMnBhL3VybjpjMnBhOmZiYjU2ZmM3LWZlNTktNDg2Yi05YjQ2LTMyOTQ0NDZkZDI4MC9jMnBhLnNpZ25hdHVyZWppbnN0YW5jZUlEeCx4bXA6aWlkOmQ4YzIwYzQ4LWU2NDgtNDQzZC1hMWRhLTlkYzhiNmNjZWFiYXJjcmVhdGVkX2Fzc2VydGlvbnODomN1cmx4LXNlbGYjanVtYmY9YzJwYS5hc3NlcnRpb25zL2MycGEuaW5ncmVkaWVudC52M2RoYXNoWCB6PhrsAO1dleGgKZS6bjkcOYxjKz6JZ6R6u6pJh7veCaJjdXJseCpzZWxmI2p1bWJmPWMycGEuYXNzZXJ0aW9ucy9jMnBhLmFjdGlvbnMudjJkaGFzaFggkFjZuSunUYJ09D4bd7vzxwZEL/66XMVYLYtqkwcJoxGiY3VybHgpc2VsZiNqdW1iZj1jMnBhLmFzc2VydGlvbnMvYzJwYS5oYXNoLmRhdGFkaGFzaFggsH0m3EDTSA8TH7dDDVq38IxrALcgfWkcCxYKkSNkNTN0Y2xhaW1fZ2VuZXJhdG9yX2luZm%2BjZG5hbWVvQW50aHJvcGljIEZpbGVzZ3ZlcnNpb25lMS4wLjBrc3BlY1ZlcnNpb25lMi40LjAAABA4anVtYgAAAChqdW1kYzJjcwARABCAAACqADibcQNjMnBhLnNpZ25hdHVyZQAAABAIY2JvctKEWQISogEmGCFZAgowggIGMIIBjaADAgECAhRA5aAK7sI50L64g/oGQgU9Z1UTADAKBggqhkjOPQQDAzBJMRcwFQYDVQQKEw5BbnRocm9waWMsIFBCQzEuMCwGA1UEAxMlQW50aHJvcGljIENvbnRlbnQgQ3JlZGVudGlhbHMgUm9vdCBDQTAeFw0yNjA4MDcxODQzNTZaFw0yODA4MDYxOTQzNTZaMEQxFzAVBgNVBAoTDkFudGhyb3BpYywgUEJDMSkwJwYDVQQDEyBBbnRocm9waWMgQ2xhdWRlIENvbnRlbnQgU2lnbmluZzBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABJh6CmvLUBgFFNU0vUKlOVtE6djd17L5SuwX0LemFisBM3dkd/3cyjxFA3Qo5S46fX0/ihY0VZ7mfb9KF703t5OjWDBWMA4GA1UdDwEB/wQEAwIHgDAVBgNVHSUEDjAMBgorBgEEAYPoXgIBMAwGA1UdEwEB/wQCMAAwHwYDVR0jBBgwFoAUzlHiBIFOZFsj%2BOPEz5o%2BnMHXXMIwCgYIKoZIzj0EAwMDZwAwZAIwMXMdFJ4BetLLVY7ORuE9noqbbAZOZn/aArXyTwFAZfKrPzxF2vPoJNf1%2BUCdg1XGAjBwX1zd9WGqYkqmL5SFqw1QySjr1zJfpJM9%2B1rdDwSPLMOPOjKuiXjoU/pUUeG9RwmhY3BhZFkNngAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPZYQAFohDKvUOA8brfWmjTMXNHWMKJNdpVxlgiA%2BnDwgCumCUK8S2gkQBQGuusiO50zcCM1Xj8ZSf5JBx7EPqG6Ue0=%3C/c2pa:manifest%3E%3C/metadata%3E%3Crect width=%22512%22 height=%22512%22 rx=%22112%22 fill=%22%230F2942%22/%3E%3Cpath d=%22M108.9,403.1 A208,208 0 0 1 103.8,114.2 L146.3,153.7 A150,150 0 0 0 149.9,362.1 Z%22 fill=%22%23E8847A%22/%3E%3Cpath d=%22M115.2,102.9 A208,208 0 0 1 396.8,102.9 L357.6,145.6 A150,150 0 0 0 154.4,145.6 Z%22 fill=%22%23F2CB5C%22/%3E%3Cpath d=%22M408.2,114.2 A208,208 0 0 1 403.1,403.1 L362.1,362.1 A150,150 0 0 0 365.7,153.7 Z%22 fill=%22%235FCB8A%22/%3E%3Cpolygon points=%22434.6,278.6 289.9,253.7 288.3,266.6%22 fill=%22%238DB6EC%22/%3E%3Cpolygon points=%22433.3,172.5 282.0,234.1 289.5,250.0%22 fill=%22%23F0A04B%22/%3E%3Ccircle cx=%22256%22 cy=%22256%22 r=%2230%22 fill=%22%23fff%22/%3E%3C/svg%3E">\n'
       '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">\n'
       '<style>' + css_old + css_new + X.CSS + R.CSS + '</style>\n</head>\n<body>\n'
       + shell_top + body + views_other + '\n<script>' + js_old + js_new + X.JS + R.JS + '</script>\n</body>\n</html>\n')
# remove old .page max-width styling influence: content no longer wrapped in .page
out = out.replace("추정", "예상")
open(D + "tpl4.html", "w", encoding="utf-8").write(out)
print("ok", len(out))

# ADMIN_V1
