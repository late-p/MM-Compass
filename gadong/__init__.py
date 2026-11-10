"""MM-Compass — 인력 가동 현황 사이트 (뼈대)

역할
  admin    : 관리자. 전체 대시보드, 업로드 현황, 사용자·주차 관리, 재계산
  uploader : 업로드 담당자. 담당 부서 투입계획 업로드, 본인 업로드 이력
  viewer   : 회의 참가자. 게시된 회의용 대시보드 보기
"""
import os, secrets, tempfile
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, g, request, render_template

def create_app():
    # 실행 위치에 관계없이 프로젝트 루트의 .env를 읽는다.
    # Vercel 등 실행 환경에서 이미 지정한 값은 덮어쓰지 않는다.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    # DB·파일 저장소 연결 전 Vercel에서는 읽기 전용 호스팅 확인 화면만 제공한다.
    # 이 분기는 storage 생성 및 SQLite 초기화보다 먼저 실행되어야 한다.
    cloud = os.environ.get("VERCEL") == "1"
    if cloud:
        # 주차·마감·감사 기록은 한국 시간. Vercel의 TZ 환경변수는 예약되어
        # 대시보드에 등록할 수 없으므로 프로세스 시간대를 초기화한다.
        import time
        os.environ["TZ"] = "KST-9"
        if hasattr(time, "tzset"): time.tzset()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if os.environ.get("GADONG_HOSTING_PREVIEW") == "1" or (cloud and not database_url):
        from .hosting import create_hosting_app
        return create_hosting_app()

    from . import db, auth, views
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__)
    storage = os.path.join(tempfile.gettempdir() if cloud else base, "mm-compass" if cloud else "storage")
    for directory in ("uploads", "published", "work", "drafts", "previews"):
        os.makedirs(os.path.join(storage, directory), exist_ok=True)
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if cloud and not secret_key: raise RuntimeError("Vercel에 SECRET_KEY를 설정해 주세요.")
    if not secret_key:
        key_file = os.path.join(storage, "secret.key")
        if not os.path.exists(key_file):
            with open(key_file, "w") as f: f.write(secrets.token_hex(32))
        with open(key_file) as f: secret_key = f.read().strip()
    app.config.update(
        SECRET_KEY=secret_key,
        DATABASE_URL=database_url,
        CLOUD_RUNTIME=cloud,
        SUPABASE_URL=os.environ.get("SUPABASE_URL", ""),
        SUPABASE_SECRET_KEY=os.environ.get("SUPABASE_SECRET_KEY", ""),
        SUPABASE_STORAGE_BUCKET=os.environ.get("SUPABASE_STORAGE_BUCKET", "mm-compass"),
        REMOTE_FILES=bool(database_url and os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SECRET_KEY")),
        BASE_DIR=base, STORAGE=storage,
        DB_PATH=os.path.join(storage, "gadong.db"),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,          # 업로드 최대 20MB
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=cloud,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=8 * 3600,           # 8시간 후 다시 로그인
        TEMPLATES_AUTO_RELOAD=True,                    # 화면(html) 파일을 바꾸면 사이트를 다시 켜지 않아도 바로 반영
    )
    db.init_app(app)
    db.migrate(app)
    if not cloud and not app.config["REMOTE_FILES"]: db.sync_published(app)
    # 계산 도중 사이트가 꺼졌거나 PC가 재시작됐다면 '계산 중'이 영원히 남아 재계산 버튼이 잠김 → 켤 때 '중단됨'으로 정리
    try:
        import datetime as _dt
        from engine import run as _er
        _wk = os.path.join(storage, "work")
        for _L in (os.listdir(_wk) if not app.config["REMOTE_FILES"] and not cloud and os.path.isdir(_wk) else []):
            _s = _er.read_status(storage, _L)
            if _s and _s.get("state") == "running":
                _er._set(storage, _L, state="error", finished=_dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         msg="계산 도중 사이트가 꺼지거나 다시 켜져서 중단되었습니다.", cause="계산 중단 (사이트 재시작)",
                         hint="'재계산'을 다시 눌러 주세요. 이전 계산본과 게시본은 그대로입니다.", files=[])
    except Exception:
        pass
    auth.init_app(app)
    views.init_app(app)
    from . import submit
    submit.init_app(app)
    from . import online
    online.register(app)
    from . import backup
    if not database_url and not os.environ.get("GADONG_NO_BACKUP"): backup.start_scheduler(app)   # SQLite 로컬 운영의 하루 1번 자동 백업

    @app.before_request
    def cloud_file_operations():
        # 계정·인사변동은 PostgreSQL에 저장된다. 파일 저장소 전환 전에는
        # Vercel 임시 디스크에 저장 성공으로 잘못 안내하지 않는다.
        file_endpoints = {"upload", "upload_delete", "plan_edit", "my_nochange", "weeks", "targets", "remind"}
        if app.config["REMOTE_FILES"]: file_endpoints = {"remind"}
        if cloud and request.method not in {"GET", "HEAD", "OPTIONS"} and request.endpoint in file_endpoints:
            return render_template("empty.html", msg="파일 업로드·재계산 기능은 준비 중입니다. 로그인과 계정 관리, 인사 변동 제출은 이용할 수 있습니다."), 503

    @app.get("/healthz")
    def health():
        try:
            db.get().execute("SELECT 1").fetchone()
            return {"status": "ok", "mode": "postgres" if database_url else "sqlite", "database_connected": True}
        except Exception:
            return {"status": "error", "database_connected": False}, 503

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp
    return app
