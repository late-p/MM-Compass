"""사이트 안에서 투입계획 직접 입력
- 최근 계산 결과(work/<주차>/use_*.pkl)에서 담당 범위 인원의 가동대상·현재 투입을 불러와 화면에 펼침
- 저장하면 표준 '인력롤링' 양식 엑셀을 만들어 일반 업로드와 똑같이 등록 → 미리보기 · 제출 · 반영 확정 · 재계산 흐름 그대로
"""
import os, re, glob, json, datetime as dt, collections
import pandas as pd, openpyxl

from .files import latest_work_root

M = list(range(1, 13))

def latest_work(storage):
    ws = sorted(l for l in os.listdir(latest_work_root(storage))
                if re.fullmatch(r"\d{4}-\d{2}-W\d", l) and os.path.exists(os.path.join(latest_work_root(storage), l, "use_clo_plan.pkl")))
    return ws[-1] if ws else None

def _gid(x):
    try: return int(float(str(x).strip()))
    except Exception: return None

def _cleanname(n): return re.sub(r"-\d+$", "", str(n or "").strip())

def _tag(T, cur):
    """당월~12월 가동대상 모양 → 달 중간에 빠지거나 들어오는 사람 표시 (없으면 빈 문자열)"""
    pos = [m for m in range(cur, 13) if T[m - 1] > 0.005]
    if not pos: return ""
    if pos[-1] < 12: return f"{pos[-1]}월까지 (이후 가동대상 아님 · 퇴사·이동 등)"
    if pos[0] > cur: return f"{pos[0]}월부터 가동대상"
    return ""

def load(storage, units, keys=None):
    """화면에 펼칠 데이터. units: 범위 문자열(들) — 본부·사업부·팀 어느 단계든. keys: 그 중 이 팀들만
    {label, cur, teams:[{key,label,dv,n}], people:[{gid,corp,name,team,tk,tl,dv,T,tag,lines}], projects}"""
    from . import org as ORG
    label = latest_work(storage)
    if not label: return None, "아직 재계산한 주차가 없습니다. 관리자가 한 번 재계산한 뒤 쓸 수 있습니다."
    if isinstance(units, str): units = [units]
    tk = ORG.expand(storage, units)
    if keys is not None: tk = [k for k in tk if k in set(keys)]
    if not tk: return None, "이 범위에서 가동대상 인원이 있는 팀을 찾지 못했습니다. (하반기 총괄 등 전체 범위는 화면 입력 대신 파일로 올려 주세요)"
    W = os.path.join(latest_work_root(storage), label)
    from engine import roles as RL
    lb2, cur, roster = ORG.roster(storage)
    tkset = set(tk); roster = [x for x in roster if x["key"] in tkset]
    PL = {}
    for corp, key in ((RL.CLO, "clo"), (RL.ET, "et")):
        if any(x["corp"] == corp for x in roster):
            pl = pd.read_pickle(os.path.join(W, f"use_{key}_plan.pkl"))
            MC = [f"2026년_{m}월" for m in M]
            pl[MC] = pl[MC].apply(pd.to_numeric, errors="coerce").fillna(0.0)
            pl["_g"] = pl["그룹사번"].apply(_gid); PL[corp] = pl
    KIND = {"이행": "이행", "제안": "제안", "R&D·내부과제": "R&D"}
    order = {k: i for i, k in enumerate(tk)}
    people = collections.OrderedDict()
    for x in sorted(roster, key=lambda x: (order.get(x["key"], 9999), x["name"])):
        g = (x["corp"], x["gid"])
        people[g] = dict(id=f"{x['corp']}|{x['gid']}", gid=x["gid"], corp=x["corp"], name=x["name"], dv=x["dv"],
                         team=(x["tm"] if x["tm"] != "(직속)" else (x["dv"] if x["dv"] != "(직속)" else x["hq"])),
                         tk=x["key"], tl=ORG.label(x["key"]), T=list(x["T"]), lines=collections.OrderedDict())
    if not people: return None, "이 범위에 입력할 인원이 없습니다."
    KEY = {}
    for g, p in people.items(): p["tag"] = _tag(p["T"], cur); KEY.setdefault(p["corp"], set()).add(g[1])
    for corp, pl in PL.items():
        for _, r in pl[pl["_g"].isin(KEY.get(corp, set()))].iterrows():
            mm = [float(r[f"2026년_{m}월"]) for m in M]
            if sum(mm) <= 0.0001: continue
            p = people[(corp, r["_g"])]; code = str(r.get("코드") or "").strip(); pj = str(r.get("PJT 명") or "").strip()
            k = (code or pj)
            sold = str(r.get("출처") or "") == "SOLD"
            ln = p["lines"].setdefault(k, dict(pj=pj, code=code, kind=KIND.get(r.get("구분"), "이행"), mm=[0.0] * 12, _s=sold))
            if ln.get("_s") and not sold: ln["pj"] = pj; ln["_s"] = False   # 투입계획 파일에 적힌 이름을 우선 (SOLD 표기와 다를 수 있음)
            ln["mm"] = [round(a + b, 4) for a, b in zip(ln["mm"], mm)]
    for p in people.values():
        for ln in p["lines"].values(): ln.pop("_s", None)
    projs = {}
    for pl in PL.values():
        for _, r in pl.iterrows():
            code = str(r.get("코드") or "").strip(); pj = str(r.get("PJT 명") or "").strip()
            if pj and pj not in projs: projs[pj] = dict(pj=pj, code=code, kind=KIND.get(r.get("구분"), "이행"))
    for x in cp_projects(storage, W):   # CP 프로젝트 목록 (관리자가 올린 최신본) — 이름이 같으면 투입계획 쪽 이름 그대로
        if x["pj"] not in projs: projs[x["pj"]] = x
        else: projs[x["pj"]].setdefault("cust", x.get("cust", ""))
    out = [dict(p, lines=list(p["lines"].values()), T=[round(v, 2) for v in p["T"]]) for p in people.values()]
    tinfo = {x["key"]: x for x in ORG.teams(storage)}
    cnt = collections.Counter(p["tk"] for p in out)
    teams = [dict(key=k, label=ORG.label(k), dv=tinfo[k]["grp"] if k in tinfo else "", n=cnt[k]) for k in tk if cnt.get(k)]
    return dict(label=label, cur=cur, people=out, teams=teams, projects=sorted(projs.values(), key=lambda x: x["pj"])), None

def cp_projects(storage, W):
    """CP 프로젝트 목록 → [{pj, code, kind, cust, cp:1}] (실주 제외). 파일: 계산 때 쓴 것 → 기준 폴더"""
    import json
    cands = []
    try: cands.append(json.load(open(os.path.join(W, "cfg.json"), encoding="utf-8"))["inputs"].get("cp"))
    except Exception: pass
    cands.append(os.path.join(storage, "inputs", "base", "cp.xlsx"))
    path = next((c for c in cands if c and os.path.exists(c)), None)
    if not path: return []
    try: c = pd.read_excel(path, header=1)
    except Exception: return []
    if "사업명" not in c.columns: return []
    out = []
    for _, r in c.iterrows():
        nm = str(r.get("사업명") or "").strip(); st = str(r.get("사업단계") or "")
        if not nm or st == "실주": continue
        kind = "R&D" if str(r.get("사업유형") or "") == "비매출" else ("이행" if st in ("이행", "무상유지보수") else "제안")
        cust = str(r.get("수요처(최종고객)") or r.get("매출처") or "").strip()
        out.append(dict(pj=nm, code=str(r.get("사업코드") or "").strip(), kind=kind, cust="" if cust == "nan" else cust, cp=1))
    return out

RH = ["사번", "No", "성명", "직위", "부서", "팀", "역할", "투입/미투입", "종료", "프로젝트명", "프로젝트코드", "win/Loss", "제안/이행", "상주", "계약시작일", "계약만료일",
      "오류", "MM"] + [f"{m}월" for m in M] + ["합계"]

def write_xlsx(path, dept, people, user):
    """화면 입력 → 표준 인력롤링 양식 (사이트가 읽는 시트·머리글 그대로)"""
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "인력_투입현황MM"
    ws.append([None, f"■ 2026년 인력별 프로젝트 투입현황 · {dept} · MM-Compass 화면 입력 ({user}, {dt.datetime.now():%Y-%m-%d %H:%M})"])
    ws.append([]); ws.append([]); ws.append([None, None, "투입인력", None, None, None, None, "투입여부", None, "프로젝트"]); ws.append(RH)
    no = 0
    for p in people:
        lines = [l for l in p.get("lines", []) if (l.get("pj") or "").strip() and sum(float(v or 0) for v in l["mm"]) > 0]
        if not lines:
            no += 1
            ws.append([None, no, p["name"], None, p.get("dv"), p.get("team"), None, "미투입", None, "대기", None, None, None, None, None, None, None, 1] + [None] * 12 + [0])
        for l in lines:
            no += 1; mm = [round(float(v or 0), 4) for v in l["mm"]]
            ws.append([None, no, p["name"], None, p.get("dv"), p.get("team"), None, "투입", None, l["pj"].strip(), (l.get("code") or "").strip() or None,
                       "수주" if l.get("kind") != "제안" else "진행", {"R&D": "R&D", "제안": "제안"}.get(l.get("kind"), "이행"), None, None, None, None, 1]
                      + [v if v else None for v in mm] + [round(sum(mm), 4)])
    wb.save(path)

def _hr_info(storage, label):
    """그룹사번 → {사번, 직위, 직무} (계산 때 쓴 통합인사정보). 못 읽으면 빈 dict"""
    p = os.path.join(latest_work_root(storage), label, "hr.xlsx")
    if not os.path.exists(p): return {}
    try:
        raw = pd.read_excel(p, header=None, nrows=8)
        hi = next(i for i in range(len(raw)) if "성명" in [str(x).strip() for x in raw.iloc[i]] and "그룹사번" in [str(x).strip() for x in raw.iloc[i]])
        h = pd.read_excel(p, header=hi)
    except Exception: return {}
    h.columns = [str(c).strip() for c in h.columns]
    pick = lambda r, *cs: next((str(r[c]).strip() for c in cs if c in h.columns and str(r[c]).strip() not in ("", "nan", "None")), "")
    out = {}
    for _, r in h.iterrows():
        g = _gid(r.get("그룹사번"))
        if g is None: continue
        out[g] = dict(sabun=pick(r, "사번", "그룹사번"), pos=pick(r, "호칭", "직급", "직책", "직위"), job=pick(r, "직무", "직군"))
    return out

def template_xlsx(path, storage, units, user, keys=None):
    """업로드용 템플릿: 담당 부서 인원 기본정보 + 지금 계산에 쓰인 투입이 채워진 표준 인력롤링 양식"""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter as L
    data, err = load(storage, units, keys)
    if err: return err
    cur = data["cur"]; hr = _hr_info(storage, data["label"])
    from . import org as ORG
    tkeys = [t["key"] for t in data["teams"]]
    dept = ORG.summary(tkeys)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "인력_투입현황MM"
    ws.append([None, f"■ 2026년 인력별 프로젝트 투입현황 · {dept} · MM-Compass 업로드 템플릿 ({dt.datetime.now():%Y-%m-%d} · 기준 계산본 {data['label']})"])
    ws.append([None, f"※ 노란 칸({cur}월~12월 MM)만 고치세요. 회색 칸(지난달까지)은 고쳐도 반영되지 않습니다 · 열 순서·머리글·시트 이름은 바꾸지 마세요 · "
                     "새 프로젝트는 그 사람 행 아래에 행을 넣고 성명을 똑같이 쓰면 됩니다 · 여러 팀이 한 시트에 섞여 있어도 올리면 사이트가 팀별로 나눠 등록합니다"])
    ws.append([]); ws.append([None, None, "투입인력", None, None, None, None, "투입여부", None, "프로젝트"]); ws.append(RH)
    MC = {m: RH.index(f"{m}월") + 1 for m in M}; cTot = RH.index("합계") + 1
    no = 0; r0 = 6
    for p in data["people"]:
        info = hr.get(p["gid"], {}); base = [info.get("sabun") or p["gid"], None, p["name"], info.get("pos"), p.get("dv"), p.get("team"), info.get("job")]
        lines = [l for l in p["lines"] if sum(l["mm"]) > 0] or [None]
        for l in lines:
            no += 1; row = list(base); row[1] = no
            if l is None: row += ["미투입", None, "대기", None, None, None, None, None, None, None, 1] + [None] * 12
            else:
                row += ["투입", None, l["pj"], l["code"] or None, "수주" if l["kind"] != "제안" else "진행", l["kind"], None, None, None, None, 1] + [round(v, 4) or None for v in l["mm"]]
            row[RH.index("오류")] = p["tag"] or None
            ws.append(row + [None])
            rr = ws.max_row; ws.cell(rr, cTot).value = f"=SUM({L(MC[1])}{rr}:{L(MC[12])}{rr})"
    last = max(ws.max_row, r0) + 30   # 새 행 넣을 여유 (검사 범위)
    thin = Side(style="thin", color="C9D1DC"); hdr = PatternFill("solid", fgColor="DCE6F1"); past = PatternFill("solid", fgColor="EEEEEE"); edit = PatternFill("solid", fgColor="FFF7D6")
    for c in ws[5]: c.font = Font(bold=True); c.fill = hdr; c.alignment = Alignment(horizontal="center", vertical="center"); c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    ws["B1"].font = Font(bold=True, size=13); ws["B2"].font = Font(color="B42335", size=10)
    for rr in range(r0, ws.max_row + 1):
        for m in M:
            c = ws.cell(rr, MC[m]); c.fill = past if m < cur else edit; c.number_format = "0.00"
        ws.cell(rr, cTot).number_format = "0.00"
        if ws.cell(rr, RH.index("오류") + 1).value: ws.cell(rr, RH.index("오류") + 1).font = Font(color="B42335", size=9)
    dv = DataValidation(type="decimal", operator="between", formula1="0", formula2="1", allow_blank=True, showErrorMessage=True,
                        errorTitle="MM 값", error="0 ~ 1 사이 숫자만 넣을 수 있습니다 (예: 0.5)")
    dv.add(f"{L(MC[1])}{r0}:{L(MC[12])}{last}"); ws.add_data_validation(dv)
    dk = DataValidation(type="list", formula1='"이행,제안,R&D"', allow_blank=True); dk.add(f"{L(RH.index('제안/이행') + 1)}{r0}:{L(RH.index('제안/이행') + 1)}{last}"); ws.add_data_validation(dk)
    ds = DataValidation(type="list", formula1='"투입,미투입"', allow_blank=True); ds.add(f"{L(RH.index('투입/미투입') + 1)}{r0}:{L(RH.index('투입/미투입') + 1)}{last}"); ws.add_data_validation(ds)
    for i, w in enumerate([10, 5, 9, 8, 14, 14, 12, 9, 6, 38, 13, 8, 8, 5, 10, 10, 22, 5] + [7] * 12 + [7], start=1): ws.column_dimensions[L(i)].width = w
    ws.freeze_panes = "D6"
    g = wb.create_sheet("작성안내")
    for t in ["MM-Compass 업로드 템플릿 작성 안내", "",
              f"1. '인력_투입현황MM' 시트의 노란 칸({cur}월~12월)에 월별 투입 MM을 넣습니다 (0~1, 예: 반만 투입 0.5).",
              "2. 한 사람이 프로젝트 여러 개면 행을 여러 개 씁니다 (성명을 똑같이). 한 달 합계는 1.00을 넘지 않게.",
              "3. 대기(투입 없음)는 '미투입' 행 그대로 두거나 MM을 비워 두면 됩니다.",
              "4. 새 프로젝트: 그 사람 행 아래에 행을 넣고 성명·프로젝트명·제안/이행·MM을 씁니다. 코드를 알면 프로젝트코드도.",
              "5. 열 순서·머리글·시트 이름을 바꾸거나 시트를 지우면 사이트가 읽지 못하고 돌려보냅니다.",
              "6. 다 쓰면 MM-Compass → 투입계획 → 파일 업로드로 올리고, 반영 미리보기를 확인한 뒤 [제출]을 누릅니다.",
              "7. 여러 팀을 한 시트에 받았으면 '팀' 열이 팀을 가릅니다. 그대로 올리면 사이트가 팀별로 나눠 등록하고, 팀별로 미리보기·제출됩니다.",
              "8. '오류' 열에 적힌 표시(예: 11월까지)는 그 달부터 가동대상이 아니라는 뜻입니다. 퇴사·전출·휴직으로 가동대상이 없는 사람은 아예 빠져 있습니다.",
              "", "※ 엑셀보다 사이트의 '화면에서 입력'이 더 빠르고 실수가 적습니다 (기간·비율로 한 번에 채우기, 프로젝트 검색)."]:
        g.append([t])
    g["A1"].font = Font(bold=True, size=13); g.column_dimensions["A"].width = 110
    meta = wb.create_sheet("_gadong"); meta.append(["dept", dept]); meta.append(["mode", "teams"]); meta.append(["teams", json.dumps(tkeys, ensure_ascii=False)]); meta.append(["label", data["label"]]); meta.append(["made", dt.datetime.now().isoformat(timespec="seconds")]); meta.append(["by", user])
    meta.sheet_state = "hidden"
    wb.active = 0; wb.save(path)
    return None


def split_by_team(storage, path, keys, out_dir):
    """인력롤링 파일 하나 → 팀별 파일 여러 개 (사람 이름 → 팀은 가동인력목록 기준, 담당 팀(keys) 안에서만)
    반환: ({팀키: {path, people, rows}}, 담당 범위 밖·못 찾은 이름 목록, 시트 머리글 행 수)"""
    import openpyxl
    from . import org as ORG
    ks = set(keys); who = collections.defaultdict(list)
    for x in ORG.roster(storage)[2]:
        if x["key"] in ks and x["key"] not in who[x["name"]]: who[x["name"]].append(x["key"])
    wv = openpyxl.load_workbook(path, data_only=True, read_only=True)   # 저장된 값만 읽음 (큰 파일도 빠르게)
    sn = next(s for s in wv.sheetnames if s.strip().endswith("인력_투입현황MM"))
    rows, empty = [], 0
    for r in wv[sn].iter_rows(values_only=True):   # 서식만 남은 빈 줄이 수십만 줄인 파일도 있어서 빈 줄이 이어지면 거기서 끝냄
        r = list(r)
        while r and r[-1] is None: r.pop()   # 열이 1만 칸 넘게 잡힌 파일이 있어 뒤의 빈 칸은 자름
        rows.append(r); empty = empty + 1 if not r else 0
        if empty > 300: break
    hi = next(i for i, r in enumerate(rows[:15]) if r and "성명" in [str(x).strip() if x else "" for x in r] and any(str(x).strip() == "1월" for x in r if x))
    H = [str(x).strip() if x is not None else "" for x in rows[hi]]
    W_ = len(H)
    ci = lambda n: H.index(n) if n in H else None
    cn, ct, cd = ci("성명"), ci("팀"), ci("부서"); mc = [ci(f"{m}월") for m in M]; ctot = ci("합계")
    norm = lambda x: re.sub(r"[\s_\-&]", "", str(x or "")).lower().replace("팀", "").replace("사업부", "")
    mine, unknown = collections.defaultdict(list), collections.OrderedDict()
    for i in range(hi + 1, len(rows)):
        r = rows[i]
        if not r or cn is None or cn >= len(r) or not r[cn]: continue
        nm = _cleanname(r[cn])
        c = who.get(nm, [])
        if not c: unknown[nm] = 1; continue
        k = c[0]
        if len(c) > 1:   # 같은 이름이 담당 팀 여러 곳에 있으면 팀·부서 칸으로 고름
            tn = norm(r[ct]) if ct is not None and ct < len(r) else ""; dn = norm(r[cd]) if cd is not None and cd < len(r) else ""
            k = next((x for x in c if tn and norm(x.split(" · ")[3] if x.split(" · ")[3] != ORG.DIRECT else x.split(" · ")[2]) == tn), None) or \
                next((x for x in c if dn and norm(x.split(" · ")[2]) == dn), None) or c[0]
        mine[k].append(i)
    os.makedirs(out_dir, exist_ok=True); parts = collections.OrderedDict()
    for k in [x for x in keys if x in mine]:
        nb = openpyxl.Workbook(); ns = nb.active; ns.title = sn
        for i in range(hi + 1): ns.append(list(rows[i]))
        names = set()
        for i in mine[k]:
            vals = list(rows[i]) + [None] * (W_ - len(rows[i]))
            ns.append(vals); rr = ns.max_row
            if ctot is not None: ns.cell(rr, ctot + 1).value = round(sum(float(ns.cell(rr, q + 1).value or 0) for q in mc if isinstance(ns.cell(rr, q + 1).value, (int, float))), 4)
            names.add(vals[cn])
        pth = os.path.join(out_dir, f"{abs(hash(k)) % 10**8}_{len(parts)}.xlsx"); nb.save(pth)
        parts[k] = dict(path=pth, people=len(names), rows=len(mine[k]))
    return parts, list(unknown), hi + 1
