"""목표 가득률 설정 (관리자). storage/targets.json 에 저장 — 회의용 '목표 대비 M/M 갭'이 읽는다.
빼려면: 이 파일 삭제 + views.py 의 'targets' 등록 줄 + base.html 의 '목표 가득률' 메뉴 줄 삭제.
구조: {"all": 90, "net": 94, "by": {"<본부>": {"all":..,"net":..}}}  (by 는 본부별 목표용 자리 — 비어 있으면 전사 값 사용)"""
import os, json
from flask import render_template, request, redirect, url_for, flash, g, current_app
from . import db, files
from .auth import login_required, check_csrf

def _path(): return os.path.join(current_app.config["STORAGE"], "targets.json")

def load():
    if files.enabled(): files.ensure("targets.json")
    try: return json.load(open(_path(), encoding="utf-8"))
    except Exception: return {}

def _num(s):
    s = (s or "").strip().replace("%", "")
    if not s: return None
    v = float(s)
    if not 30 <= v <= 100: raise ValueError
    return round(v, 1)

def register(app):
    @app.route("/admin/targets", methods=["GET", "POST"])
    @login_required("admin")
    def targets():
        t = load()
        if request.method == "POST":
            check_csrf()
            try:
                a, n = _num(request.form.get("all")), _num(request.form.get("net"))
            except ValueError:
                flash("목표는 30~100 사이 숫자로 입력해 주세요."); return redirect(url_for("targets"))
            new = {k: v for k, v in (("all", a), ("net", n)) if v is not None}
            if t.get("by"): new["by"] = t["by"]
            json.dump(new, open(_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            files.persist(_path())
            db.audit(g.user["username"], "targets", f"전체 {a} · 비매출 제외 {n}")
            flash("목표 가득률을 저장했습니다. 다음 통계 집계부터 회의용 화면에 반영됩니다.")
            return redirect(url_for("targets"))
        return render_template("targets.html", t=t)
