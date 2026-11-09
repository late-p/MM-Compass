import os, sqlite3, datetime as dt
from contextlib import contextmanager
from pathlib import Path
from flask import current_app, g, has_app_context

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display TEXT NOT NULL,
  pw_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','uploader','viewer')),
  dept TEXT DEFAULT '', active INTEGER DEFAULT 1,
  fail_count INTEGER DEFAULT 0, locked_until TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS uploads(
  id INTEGER PRIMARY KEY, user_id INTEGER, dept TEXT, kind TEXT, week TEXT,
  orig_name TEXT, stored_name TEXT, size INTEGER, status TEXT, note TEXT, uploaded_at TEXT);
CREATE TABLE IF NOT EXISTS weeks(
  label TEXT PRIMARY KEY, title TEXT, published INTEGER DEFAULT 0, published_at TEXT, comment TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY, at TEXT, user TEXT, action TEXT, detail TEXT);
"""

def now(): return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class Record(dict):
    """기존 SQLite 화면 코드의 행['이름']과 행[0] 접근을 모두 지원한다."""
    def __getitem__(self, key):
        if isinstance(key, int): return tuple(self.values())[key]
        return super().__getitem__(key)

def _record_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Record(zip(names, values))

class PostgresConnection:
    """앱의 기존 ? 매개변수를 PostgreSQL의 바인딩 매개변수로 전달한다."""
    def __init__(self, url):
        import psycopg
        self.raw = psycopg.connect(url, connect_timeout=15, sslmode="require",
                                  prepare_threshold=None, row_factory=_record_factory)

    def execute(self, sql, parameters=()):
        return self.raw.execute(sql.replace("?", "%s"), parameters or None)

    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()
    def __enter__(self): return self
    def __exit__(self, kind, value, traceback):
        try:
            if kind is None: self.commit()
            else: self.rollback()
        finally: self.close()

def connect(app=None, storage=None):
    config = app.config if app is not None else (current_app.config if has_app_context() else {})
    url = config.get("DATABASE_URL") if "DATABASE_URL" in config else os.environ.get("DATABASE_URL")
    if url: return PostgresConnection(url)
    path = os.path.join(storage, "gadong.db") if storage else config["DB_PATH"]
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection

@contextmanager
def transaction(app=None):
    connection = connect(app)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally: connection.close()

def initialize_postgres(url):
    """Supabase SQL Editor에서도 실행 가능한 초기 스키마. 명시적으로 한 번 적용한다."""
    with PostgresConnection(url) as connection:
        connection.raw.execute((Path(__file__).parent / "schema_postgres.sql").read_text(encoding="utf-8"))

def get():
    if "db" not in g:
        g.db = connect()
    return g.db

def close(_e=None):
    d = g.pop("db", None)
    if d is not None: d.close()

def init_app(app):
    if not app.config.get("DATABASE_URL"):
        with transaction(app) as c: c.executescript(SCHEMA)
    app.teardown_appcontext(close)

def audit(user, action, detail=""):
    d = get(); d.execute('INSERT INTO audit(at,"user",action,detail) VALUES(?,?,?,?)', (now(), user, action, detail)); d.commit()

def migrate(app):
    """업로드 상태 체계 변경: 접수 → 제출 (관리자 반영 확정 전까지 계산에서 제외)"""
    if app.config.get("DATABASE_URL"): return
    with transaction(app) as c:
        c.execute("UPDATE uploads SET status='제출' WHERE status='접수'")
        # 회원가입 신청: users.active = -1 (승인 대기) · 신청 내용은 req_note
        cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
        if "req_note" not in cols: c.execute("ALTER TABLE users ADD COLUMN req_note TEXT DEFAULT ''")
        if "depts" not in cols: c.execute("ALTER TABLE users ADD COLUMN depts TEXT DEFAULT ''")   # 담당 부서 여러 개 (JSON)
        if "ticket_id" not in {r[1] for r in c.execute("PRAGMA table_info(uploads)")}:
            c.execute("ALTER TABLE uploads ADD COLUMN ticket_id TEXT")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uploads_ticket_id ON uploads(ticket_id)")

def sync_published(app):
    """published 폴더와 주차 목록 맞추기 (켤 때마다)
    - 새로 들어온 주차 폴더(Claude가 만들어 넣은 것 등)는 자동 등록·게시
    - 폴더 안에 RETIRED.txt 가 있으면 목록에서 뺌 (잘못 붙은 주차 정리용)"""
    import os, re
    pub = os.path.join(app.config["STORAGE"], "published")
    with transaction(app) as c:
        for label in sorted(os.listdir(pub)):
            d = os.path.join(pub, label)
            if not os.path.isdir(d) or not re.fullmatch(r"\d{4}-\d{2}-W\d", label): continue
            if os.path.exists(os.path.join(d, "RETIRED.txt")):
                if app.config.get("DATABASE_URL"):
                    c.execute("UPDATE weeks SET published=0 WHERE label=?", (label,))
                else: c.execute("DELETE FROM weeks WHERE label=?", (label,))
                continue
            if os.path.exists(os.path.join(d, "meeting.html")):
                y, m, w = label[:4], int(label[5:7]), label.split("W")[-1]
                c.execute("INSERT INTO weeks(label,title,published,published_at) VALUES(?,?,1,?) ON CONFLICT(label) DO NOTHING", (label, f"{y}년 {m}월 {w}주차", now()))
