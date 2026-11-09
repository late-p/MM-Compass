"""자동 백업 — 계정 DB · 업로드 원본 · 게시본 · 기본 입력 파일을 zip 하나로

- 언제: 사이트를 켤 때(마지막 백업이 20시간 넘었으면) · 켜져 있는 동안 1시간마다 확인해 하루 1번 · 계산본 게시 직후 · 관리자가 '지금 백업'
- 어디로: storage/backup_dir.txt 에 적힌 폴더 (관리자 화면에서 바꿈) · 없으면 storage/backups
- 몇 개: 최근 30개만 남기고 오래된 것부터 지움
- 다시 만들 수 있는 것(work · drafts · previews)은 넣지 않음
※ 백업 파일에도 인사정보가 들어 있으니 storage 와 똑같이 외부 공유 금지
"""
import os, sqlite3, zipfile, threading, time, datetime as dt, tempfile, glob

KEEP = 30
INCLUDE = ("uploads", "published", "inputs")
PREFIX = "가동ON_백업_"
_lock = threading.Lock()

def backup_dir(app):
    st = app.config["STORAGE"]
    p = os.path.join(st, "backup_dir.txt")
    if os.path.exists(p):
        d = open(p, encoding="utf-8").read().strip()
        if d: return d
    return os.path.join(app.config["STORAGE"], "backups")   # 기본: storage 안 (storage 와 함께 외부 공유 금지)

def set_backup_dir(app, path):
    path = (path or "").strip().strip('"')
    p = os.path.join(app.config["STORAGE"], "backup_dir.txt")
    if not path:
        if os.path.exists(p): os.remove(p)
        return backup_dir(app)
    os.makedirs(path, exist_ok=True)
    test = os.path.join(path, ".write_test")
    open(test, "w").write("ok"); os.remove(test)          # 쓸 수 있는 폴더인지 확인
    open(p, "w", encoding="utf-8").write(path)
    return path

def list_backups(app):
    d = backup_dir(app)
    out = []
    for f in sorted(glob.glob(os.path.join(d, PREFIX + "*.zip")), reverse=True):
        s = os.stat(f)
        out.append(dict(name=os.path.basename(f), size=s.st_size, at=dt.datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M")))
    return out

def last_backup_time(app):
    b = list_backups(app)
    return dt.datetime.strptime(b[0]["at"], "%Y-%m-%d %H:%M") if b else None

def make_backup(app, reason="자동"):
    """백업 1개 만들기 → (성공 여부, 파일 이름 또는 오류)"""
    if app.config.get("DATABASE_URL"): return False, "PostgreSQL 백업은 DB의 백업·내보내기 기능을 사용해 주세요."
    if not _lock.acquire(blocking=False): return False, "다른 백업이 진행 중입니다."
    try:
        st = app.config["STORAGE"]; d = backup_dir(app); os.makedirs(d, exist_ok=True)
        name = f"{PREFIX}{dt.datetime.now():%Y%m%d_%H%M%S}_{reason}.zip"
        tmp_db = os.path.join(tempfile.gettempdir(), f"gadong_backup_{os.getpid()}.db")
        src = sqlite3.connect(app.config["DB_PATH"]); dst = sqlite3.connect(tmp_db)
        with dst: src.backup(dst)                              # 사용 중에도 안전하게 DB 복사
        src.close(); dst.close()
        part = os.path.join(d, name + ".part")
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(tmp_db, "storage/gadong.db")
            for sub in INCLUDE:
                for root, _, files in os.walk(os.path.join(st, sub)):
                    for f in files:
                        fp = os.path.join(root, f)
                        z.write(fp, os.path.join("storage", os.path.relpath(fp, st)))
            for f in ("secret.key", "backup_dir.txt"):
                if os.path.exists(os.path.join(st, f)): z.write(os.path.join(st, f), f"storage/{f}")
            z.writestr("복원방법.txt", "1) 사이트(검은 창)를 끕니다.\r\n2) 이 zip 안의 storage 폴더 내용을 가동ON_site\\storage 에 덮어씁니다.\r\n"
                       "3) 시작.bat 으로 다시 켭니다. (work·drafts는 재계산하면 다시 만들어집니다)\r\n")
        os.replace(part, os.path.join(d, name))
        os.remove(tmp_db)
        for old in sorted(glob.glob(os.path.join(d, PREFIX + "*.zip")), reverse=True)[KEEP:]:
            try: os.remove(old)
            except OSError: pass
        return True, name
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        _lock.release()

def start_scheduler(app):
    """켤 때 1번 + 1시간마다 확인해서 마지막 백업이 20시간 넘었으면 백업"""
    def loop():
        while True:
            try:
                last = last_backup_time(app)
                if last is None or dt.datetime.now() - last > dt.timedelta(hours=20):
                    ok, msg = make_backup(app, "자동")
                    with app.app_context():
                        from . import db
                        try: db.audit("system", "backup" if ok else "backup_fail", msg)
                        except Exception: pass
            except Exception:
                pass
            time.sleep(3600)
    threading.Thread(target=loop, daemon=True, name="gadong-backup").start()
