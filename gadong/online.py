"""직접 업로드, 요청으로 실행하는 미리보기·계산 단계 API."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from flask import abort, current_app, g, redirect, request, url_for
from werkzeug.datastructures import FileStorage
from . import db, files, jobs
from .auth import check_csrf, login_required
from .scope import allowed


def run_preview(uid):
    token = uuid.uuid4().hex
    with db.transaction(current_app) as connection:
        row = connection.execute("UPDATE uploads SET preview_token=?,preview_lease=? WHERE id=? AND preview_lease<=? RETURNING *",
                                 (token, int(time.time()) + 360, uid, int(time.time()))).fetchone()
    if not row: return False
    result = None
    try:
        with tempfile.TemporaryDirectory(prefix="mm-preview-") as root:
            jobs._hydrate_inputs(root, row["week"])
            source = files.ensure("uploads/" + row["stored_name"], root)
            if not source: raise ValueError("업로드 원본이 없습니다. 파일을 다시 올려 주세요.")
            with db.transaction(current_app) as connection:
                latest = connection.execute("SELECT j.artifacts FROM weeks w JOIN calc_jobs j ON j.id=w.draft_job WHERE j.state='done' ORDER BY w.label DESC LIMIT 1").fetchone()
            if latest:
                saved = {name: meta for name, meta in json.loads(latest["artifacts"]).items() if name.startswith("work/") and name.endswith("use_target.pkl")}
                files.restore(saved, root)
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
            command = [sys.executable, "-m", "engine.preview", root, str(uid)]
            process = subprocess.run(command, cwd=current_app.config["BASE_DIR"], env=env, capture_output=True, timeout=220)
            path = Path(root) / "previews" / f"{uid}.json"
            if process.returncode or not path.is_file(): raise ValueError("미리보기 계산을 완료하지 못했습니다. 양식을 확인해 주세요.")
            result = json.loads(path.read_text(encoding="utf-8"))
            result.pop("trace", None)
    except (ValueError, files.StorageError) as error:
        result = dict(error=str(error), read=[], red=[], yellow=[], changes=[])
    except Exception as error:
        result = dict(error=f"미리보기를 만들지 못했습니다 ({type(error).__name__}). 다시 시도해 주세요.", read=[], red=[], yellow=[], changes=[])
    finally:
        with db.transaction(current_app) as connection:
            connection.execute("UPDATE uploads SET preview_json=?,preview_lease=0,preview_token='' WHERE id=? AND preview_token=?",
                               (json.dumps(result, ensure_ascii=False), uid, token))
    return True


def register(app):
    @app.errorhandler(files.StorageError)
    def storage_error(error):
        from flask import render_template
        if request.path.endswith(("/sign", "/finish", "/advance", "/run")):
            return {"error": str(error)}, 503
        return render_template("empty.html", msg=str(error)), 503

    @app.post("/upload/sign")
    @login_required("admin", "uploader")
    def upload_sign():
        check_csrf()
        if not files.enabled(): abort(404)
        # 서명 만료 후 남은 전송용 파일만 정리한다. 등록된 원본은 건드리지 않는다.
        with db.transaction(current_app) as connection:
            expired = connection.execute("SELECT id,object_key FROM upload_tickets WHERE expires_at<? AND lease_until<? LIMIT 20", (int(time.time())-120, int(time.time()))).fetchall()
        if expired:
            files.remove_blobs([row["object_key"] for row in expired])
            with db.transaction(current_app) as connection:
                for row in expired: connection.execute("DELETE FROM upload_tickets WHERE id=?", (row["id"],))
        from .views import ALLOWED_EXT, KINDS_ADMIN, KINDS_UPLOADER, week_of
        import datetime as dt
        form = request.form
        name = os.path.basename(form.get("name", ""))[:200]
        kind = form.get("kind", "plan"); dept = form.get("dept", "")
        try: size = int(form.get("size", "0"))
        except ValueError: abort(400)
        if not 0 < size <= files.MAX_UPLOAD: return {"error": "파일은 20MB 이하만 올릴 수 있습니다."}, 400
        if Path(name).suffix.lower() not in ALLOWED_EXT: return {"error": "엑셀(.xlsx/.xlsm/.xls)만 올릴 수 있습니다."}, 400
        admin = g.user["role"] == "admin"
        if kind not in (KINDS_ADMIN if admin else KINDS_UPLOADER): abort(403)
        if not admin and not allowed(g.user, dept): abort(403)
        week = week_of()[0]
        previous = week_of(dt.date.today() - dt.timedelta(days=7))[0]
        if admin and form.get("week") == previous: week = previous
        identifier = uuid.uuid4().hex
        key = f"incoming/{g.user['id']}/{identifier}{Path(name).suffix.lower()}"
        response = json.loads(files.request("POST", "object/upload/sign/" + files.object_path(key), b"{}", {"Content-Type": "application/json"}))
        signed = response["url"]
        origin = current_app.config["SUPABASE_URL"].rstrip("/") + "/storage/v1"
        signed = signed if signed.startswith("https://") else origin + signed
        with db.transaction(current_app) as connection:
            from engine.run import week_meta
            connection.execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (week, week_meta(week)["title"]))
            connection.execute("INSERT INTO upload_tickets(id,user_id,object_key,name,kind,dept,week,size,split,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (identifier, g.user["id"], key, name, kind, dept, week, size, int(form.get("split") == "1"), int(time.time()) + 7200))
        return {"ticket": identifier, "url": signed}

    @app.post("/upload/finish")
    @login_required("admin", "uploader")
    def upload_finish():
        check_csrf()
        if not files.enabled(): abort(404)
        identifier = request.form.get("ticket", "")
        now = int(time.time()); token = uuid.uuid4().hex
        with db.transaction(current_app) as connection:
            ticket = connection.execute("SELECT * FROM upload_tickets WHERE id=? AND user_id=?", (identifier, g.user["id"])).fetchone()
            if not ticket: abort(404)
            if ticket["state"] == "done": return json.loads(ticket["result"])
            if ticket["expires_at"] < now: return {"error": "업로드 시간이 만료되었습니다. 파일을 다시 선택해 주세요."}, 400
            if g.user["role"] != "admin" and (ticket["kind"] != "plan" or not allowed(g.user, ticket["dept"])): abort(403)
            claimed = connection.execute("UPDATE upload_tickets SET state='processing',lease_token=?,lease_until=? WHERE id=? AND lease_until<=? RETURNING id",
                                         (token, now+420, identifier, now)).fetchone()
            if not claimed: return {"error": "파일을 확인하고 있습니다. 잠시 후 다시 확인해 주세요."}, 409
        try:
            data = files.request("GET", "object/authenticated/" + files.object_path(ticket["object_key"]), limit=files.MAX_UPLOAD)
            if len(data) != ticket["size"]: raise ValueError("올린 파일 크기가 다릅니다. 파일을 다시 선택해 주세요.")
            g.upload_ticket = identifier
            from .views import receive_upload
            response = receive_upload(g.user, FileStorage(stream=io.BytesIO(data), filename=ticket["name"]),
                dict(kind=ticket["kind"], dept=ticket["dept"], week=ticket["week"], split=str(ticket["split"])))
            result = {"url": response.location}
            with db.transaction(current_app) as connection:
                connection.execute("UPDATE upload_tickets SET state='done',result=?,lease_token='',lease_until=0 WHERE id=? AND lease_token=?",
                                   (json.dumps(result), identifier, token))
            try: files.remove_blob(ticket["object_key"])
            except files.StorageError: pass
            return result
        except (ValueError, files.StorageError) as error:
            with db.transaction(current_app) as connection:
                connection.execute("UPDATE upload_tickets SET state='issued',lease_until=0,lease_token='' WHERE id=? AND lease_token=?", (identifier, token))
            return {"error": str(error)}, 400

    @app.post("/upload/<int:uid>/preview/run")
    @login_required("admin", "uploader")
    def preview_run(uid):
        check_csrf()
        if not files.enabled(): abort(404)
        row = db.get().execute("SELECT * FROM uploads WHERE id=?", (uid,)).fetchone()
        if not row: abort(404)
        if g.user["role"] != "admin" and row["user_id"] != g.user["id"] and not allowed(g.user, row["dept"]): abort(403)
        db.get().commit()
        return {"finished": run_preview(uid)}

    @app.post("/admin/weeks/<label>/advance")
    @login_required("admin")
    def advance_job(label):
        check_csrf()
        if not files.enabled(): abort(404)
        db.get().commit()
        return jobs.advance(label)
