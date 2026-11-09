"""비공개 Supabase 객체와 로컬 계산 파일 사이의 저장 계층.

객체는 불변 이름으로 저장하고 DB가 현재 버전을 가리킨다. 캐시는 없어져도
복구 가능하며 파일을 읽을 때 크기와 SHA-256을 확인한다.
"""
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

from flask import current_app, g, has_request_context
from . import db

MAX_UPLOAD = 20 * 1024 * 1024


class StorageError(RuntimeError):
    pass


def enabled():
    return bool(current_app.config.get("REMOTE_FILES"))


def request(method, path, data=None, headers=None, limit=64 * 1024 * 1024):
    config = current_app.config
    key = config["SUPABASE_SECRET_KEY"]
    url = config["SUPABASE_URL"].rstrip("/") + "/storage/v1/" + path
    req = Request(url, method=method, data=data, headers={
        "apikey": key, "Authorization": "Bearer " + key, **(headers or {}),
    })
    try:
        with urlopen(req, timeout=45) as response:
            data = response.read(limit + 1)
            if len(data) > limit: raise StorageError("파일 크기 제한을 넘었습니다.")
            return data
    except HTTPError as error:
        # 서명 URL·비밀키를 오류 화면이나 로그에 포함하지 않는다.
        raise StorageError(f"파일 저장소 요청에 실패했습니다 (HTTP {error.code}).") from None
    except OSError:
        raise StorageError("파일 저장소에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.") from None


def object_path(key):
    return quote(current_app.config["SUPABASE_STORAGE_BUCKET"], safe="") + "/" + quote(key, safe="/")


def put_blob(data, name="file"):
    digest = hashlib.sha256(data).hexdigest()
    if len(data) > MAX_UPLOAD:
        if len(data) > 256 * 1024 * 1024: raise StorageError("중간 계산 파일이 너무 큽니다. 입력 자료의 불필요한 행·시트를 줄여 주세요.")
        parts = []
        try:
            for offset in range(0, len(data), MAX_UPLOAD):
                parts.append(put_blob(data[offset:offset+MAX_UPLOAD], name + ".part"))
            index = put_blob(json.dumps(parts).encode(), name + ".chunks.json")
            return dict(object_key=index["object_key"], parts=parts, sha256=digest, size=len(data))
        except Exception:
            try: remove_blobs([key for meta in parts for key in blob_keys(meta)])
            except StorageError: pass
            raise
    key = "objects/" + uuid.uuid4().hex + "/" + Path(name).name
    request("POST", "object/" + object_path(key), data,
            {"Content-Type": mimetypes.guess_type(name)[0] or "application/octet-stream"})
    return dict(object_key=key, sha256=digest, size=len(data))


def cached(meta):
    root = Path(current_app.config["STORAGE"]) / "_cache"
    root.mkdir(parents=True, exist_ok=True)
    path = root / meta["sha256"]
    if not path.is_file() or path.stat().st_size != meta["size"] or hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
        data = b"".join(Path(cached(part)).read_bytes() for part in meta["parts"]) if meta.get("parts") else request("GET", "object/authenticated/" + object_path(meta["object_key"]))
        if len(data) != meta["size"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise StorageError("저장 파일 검증에 실패했습니다. 파일을 다시 올려 주세요.")
        descriptor, temporary = tempfile.mkstemp(dir=root)
        try:
            with os.fdopen(descriptor, "wb") as output: output.write(data)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.remove(temporary)
    return str(path)


def remove_blob(key):
    request("DELETE", "object/" + quote(current_app.config["SUPABASE_STORAGE_BUCKET"], safe=""),
            json.dumps({"prefixes": [key]}).encode(), {"Content-Type": "application/json"})


def remove_blobs(keys):
    keys = list(set(keys))
    for offset in range(0, len(keys), 100):
        request("DELETE", "object/" + quote(current_app.config["SUPABASE_STORAGE_BUCKET"], safe=""),
                json.dumps({"prefixes": keys[offset:offset+100]}).encode(), {"Content-Type": "application/json"})


def blob_keys(meta):
    return [meta["object_key"]] + [key for part in meta.get("parts", []) for key in blob_keys(part)]


def remove_unreferenced(keys):
    keys = set(keys)
    if not keys: return
    referenced = set()
    with db.transaction(current_app) as connection:
        for key in keys:
            if connection.execute("SELECT 1 FROM file_objects WHERE object_key=? LIMIT 1", (key,)).fetchone(): referenced.add(key)
            if connection.execute("SELECT 1 FROM calc_jobs WHERE artifacts LIKE ? LIMIT 1", ("%" + key + "%",)).fetchone(): referenced.add(key)
    remove_blobs(keys - referenced)


def relative(path):
    return Path(path).resolve().relative_to(Path(current_app.config["STORAGE"]).resolve()).as_posix()


def safe_path(root, key):
    part = PurePosixPath(key)
    if part.is_absolute() or ".." in part.parts or "\\" in key:
        raise StorageError("올바르지 않은 파일 경로입니다.")
    return Path(root).joinpath(*part.parts)


def persist(path):
    if not enabled(): return
    key = relative(path)
    if not (key.startswith(("uploads/", "inputs/", "previews/")) or key == "targets.json"):
        raise StorageError("저장할 수 없는 파일 경로입니다.")
    data = Path(path).read_bytes()
    if len(data) > MAX_UPLOAD: raise StorageError("입력 파일은 20MB 이하만 저장할 수 있습니다.")
    digest = hashlib.sha256(data).hexdigest()
    with db.transaction(current_app) as connection:
        old = connection.execute("SELECT * FROM file_objects WHERE path=?", (key,)).fetchone()
        if old and old["sha256"] == digest: return
    meta = put_blob(data, Path(path).name)
    try:
        with db.transaction(current_app) as connection:
            connection.execute("INSERT INTO file_objects(path,object_key,sha256,size,updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(path) DO UPDATE SET object_key=excluded.object_key,sha256=excluded.sha256,size=excluded.size,updated_at=excluded.updated_at",
                (key, meta["object_key"], meta["sha256"], meta["size"], db.now()))
    except Exception:
        remove_blob(meta["object_key"])
        raise
    if old:
        try: remove_unreferenced([old["object_key"]])
        except StorageError: pass  # 새 버전은 이미 반영됨. 이전 객체 정리는 재시도 가능.


def ensure(key, root=None):
    root = root or current_app.config["STORAGE"]
    path = safe_path(root, key)
    if not enabled(): return str(path) if path.is_file() else None
    with db.transaction(current_app) as connection:
        meta = connection.execute("SELECT * FROM file_objects WHERE path=?", (key,)).fetchone()
    if not meta: return None
    source = cached(meta)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
        descriptor, temporary = tempfile.mkstemp(dir=path.parent)
        os.close(descriptor)
        try:
            shutil.copyfile(source, temporary)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.remove(temporary)
    return str(path)


def hydrate(prefix, root):
    with db.transaction(current_app) as connection:
        rows = connection.execute("SELECT path FROM file_objects WHERE path LIKE ?", (prefix.rstrip("/") + "/%",)).fetchall()
    for row in rows: ensure(row["path"], root)


def delete(key):
    if enabled():
        with db.transaction(current_app) as connection:
            old = connection.execute("DELETE FROM file_objects WHERE path=? RETURNING object_key", (key,)).fetchone()
        if old: remove_unreferenced([old["object_key"]])
    path = safe_path(current_app.config["STORAGE"], key)
    path.unlink(missing_ok=True)


def signed_download(key, name):
    with db.transaction(current_app) as connection:
        row = connection.execute("SELECT object_key FROM file_objects WHERE path=?", (key,)).fetchone()
    if not row: raise StorageError("파일을 찾지 못했습니다.")
    response = json.loads(request("POST", "object/sign/" + object_path(row["object_key"]),
        json.dumps({"expiresIn": 60}).encode(), {"Content-Type": "application/json"}))
    path = response.get("signedURL") or response.get("signedUrl")
    url = path if path.startswith("https://") else current_app.config["SUPABASE_URL"].rstrip("/") + "/storage/v1" + path
    return url + "&download=" + quote(name, safe="")


def checkpoint(root, previous=None):
    saved = {}
    with db.transaction(current_app) as connection:
        latest = connection.execute("SELECT artifacts FROM calc_jobs WHERE state='done' ORDER BY sequence DESC LIMIT 1").fetchone()
    by_hash = {(meta["sha256"], meta["size"]): meta for meta in json.loads(latest["artifacts"]).values()} if latest else {}
    try:
        for path in sorted(Path(root).rglob("*")):
            if not path.is_file() or path.name == "status.json": continue
            name = path.relative_to(root).as_posix()
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            old = (previous or {}).get(name)
            saved[name] = old if old and old["sha256"] == digest else by_hash.get((digest, len(data))) or put_blob(data, path.name)
    except Exception:
        try: remove_unreferenced({key for meta in saved.values() for key in blob_keys(meta)} - {key for meta in (previous or {}).values() for key in blob_keys(meta)})
        except StorageError: pass
        raise
    return saved


def restore(saved, root):
    for name, meta in saved.items():
        path = safe_path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached(meta), path)


def latest_work_root(storage):
    if not enabled(): return os.path.join(storage, "work")
    cache = getattr(g, "_work_roots", {}) if has_request_context() else {}
    if storage in cache: return cache[storage]
    with db.transaction(current_app) as connection:
        row = connection.execute("SELECT j.* FROM calc_jobs j JOIN weeks w ON w.draft_job=j.id WHERE j.state='done' ORDER BY w.label DESC LIMIT 1").fetchone()
    if not row:
        result = os.path.join(storage, "work")
        if has_request_context(): cache[storage] = result; g._work_roots = cache
        return result
    root = Path(storage) / "_results" / row["id"]
    manifest = json.loads(row["artifacts"])
    for name, meta in manifest.items():
        if not name.startswith("work/") or name.endswith(("cfg.json", "status.json", "log.txt")): continue
        path = safe_path(root, name)
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached(meta), path)
    result = str(root / "work")
    if has_request_context(): cache[storage] = result; g._work_roots = cache
    return result
