"""DB 연결에 앞서 배포 주소·화면을 확인하는 Vercel 전용 앱.

운영 앱과 같은 템플릿을 쓰되 SQLite, 로컬 storage, 백그라운드 작업은
시작하지 않는다. 외부 DB·파일 저장소 전환 후 운영 앱으로 통합할 예정.
"""
import os
import secrets

from flask import Flask, redirect, render_template, request, url_for


def create_hosting_app():
    app = Flask("gadong")
    app.config.update(
        HOSTING_PREVIEW=True,
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.environ.get("VERCEL") == "1",
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,
    )
    app.jinja_env.globals["me"] = lambda: None

    @app.before_request
    def require_persistent_storage():
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            return render_template(
                "empty.html",
                msg="서비스 오픈 준비 중입니다. 로그인·회원가입·자료 제출은 준비가 끝난 후 이용할 수 있습니다.",
            ), 503

    @app.get("/")
    def home():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        return redirect(url_for("login"))

    @app.get("/healthz")
    def health():
        # 웹 배포 확인용. DB 연결 완료를 의미하는 readiness 응답은 아니다.
        return {"status": "ok", "mode": "hosting-preview", "database_connected": False}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    return app
