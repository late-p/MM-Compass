"""계산 설정 — engine/run.py 가 만든 JSON(GADONG_CFG)을 읽음
inputs     : 자리(role) → 파일 경로
short      : 자리 → 화면에 쓰는 짧은 이름 (예: 하반기(10.06))
dept_files : 부서가 올린 투입계획 중 고정 자리가 없는 것 [{path, fmt, corp, hq, dv, tm, label}]
files      : 관리자 화면 '반영 파일' 목록 [[날짜, 파일명, 설명], ...]
week       : {label, title, short, asof, meet}
"""
import os, json
_C = json.load(open(os.environ["GADONG_CFG"], encoding="utf-8"))
CALC = os.path.dirname(os.path.abspath(__file__)) + os.sep
WORK = _C["work"].rstrip("/\\") + os.sep
IN = _C["inputs"]
SHORT = _C.get("short", {})
DEPT_FILES = _C.get("dept_files", [])
FILES = [tuple(x) for x in _C.get("files", [])] or None
WEEK = _C["week"]
TARGETS = _C.get("targets") or {}   # 관리자가 정한 목표 가득률 {"all": 전체 기준, "net": 비매출 모수 제외 기준}
HR_NOTES = _C.get("hr_notes", [])   # 사이트 '인사 변동 제출' 중 계산에 넣을 것 (반영 상태)
FRESH = set(_C.get("fresh", []))   # 통계 파일보다 나중에 올라온 투입계획 파일 경로
ALIAS = _C.get("alias") or {}   # 코드에 적힌 실제 이름 → 가명 (가명 자료 시연용). 비어 있으면 코드 그대로
def A(s):
    """코드에 적힌 이름·낱말을 ALIAS 대로 바꾼다 (ALIAS 가 비어 있으면 그대로)"""
    for k, v in ALIAS.items(): s = s.replace(k, v)
    return s
def inp(role):
    if role not in IN: raise KeyError(f"입력 파일 없음: {role}")
    return IN[role]
def w(name): return WORK + name
def c(name): return CALC + name

# ---- 월 기준 (주차가 속한 달 = 당월) ----
# CUR  : 당월 (1~12)          CI : 당월 index (0~11)
# ACT  : 법인별 SOLD 실적 확정 월 (run.py 가 SOLD 파일의 'Activity 실적(누적)'으로 판별) — 없으면 전월까지 확정으로 봄
# ACTM : 두 법인 중 늦은 쪽 기준 실적 확정 월 · PROV : 지난달인데 SOLD 마감 전이라 투입계획으로 채운 '잠정' 월
CUR = int(WEEK.get("label", "2026-10")[5:7])
CI = CUR - 1
ACT = {k: min(int(v), CUR - 1) for k, v in _C.get("act", {"clo": CUR - 1, "et": CUR - 1}).items()}
ACTM = min(ACT.values()) if ACT else CUR - 1
PROV = list(range(ACTM + 1, CUR))
def act_of(corp): return ACT.get("et" if "엔텍" in str(corp) else "clo", ACTM)
def M(m): return f"{m}월"
def R(a, b=12):
    """월 범위 표기: R(10) → '10~12월', R(12) → '12월', R(1, 9) → '1~9월'"""
    return f"{a}월" if a == b else f"{a}~{b}월"
