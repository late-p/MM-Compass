"""요청 하나에 계산 한 단계. DB 임대와 불변 체크포인트로 재개·게시를 보장한다."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from flask import current_app
from . import db, files

LEASE = 420


def start(label, user):
    from engine import run
    import re
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])-W[1-5]", label):
        return False, "주차 형식이 올바르지 않습니다."
    meta = run.week_meta(label)
    if meta["thu"][5:7] != label[5:7]: return False, "이 달에는 해당 주차가 없습니다."
    identifier = uuid.uuid4().hex
    with db.transaction(current_app) as connection:
        row = connection.execute("INSERT INTO calc_jobs(id,label,by_user,started,user_id) VALUES(?,?,?,?,(SELECT id FROM users WHERE username=?)) ON CONFLICT DO NOTHING RETURNING id",
                                 (identifier, label, user, db.now(), user)).fetchone()
        if not row: return False, "다른 재계산이 진행 중입니다. 계산 화면에서 이어서 진행하거나 취소해 주세요."
        connection.execute("INSERT INTO weeks(label,title) VALUES(?,?) ON CONFLICT(label) DO NOTHING", (label, meta["title"]))
    return True, "재계산을 시작했습니다. 이 화면을 열어 두면 단계별로 이어서 계산합니다."


def get(label):
    with db.transaction(current_app) as connection:
        return connection.execute("SELECT * FROM calc_jobs WHERE label=? ORDER BY sequence DESC LIMIT 1", (label,)).fetchone()


def status(label):
    row = get(label)
    if not row: return {}
    from engine import run
    names = ["입력 자료 준비"] + [name for name, _ in run.STEPS] + ["계산본 저장"]
    detail = json.loads(row["detail"])
    return dict(detail, id=row["id"], state=row["state"], started=row["started"], finished=row["finished"],
                step=detail.get("step") or (names[min(row["step"], len(names)-1)] if row["state"] == "running" else "완료"),
                cursor=row["step"], total=len(names), busy=row["lease_until"] > int(time.time()))


def cancel(label):
    # 실행 중인 워커는 최종 CAS에서 거절된다. 새 게시본에 영향을 주지 않는다.
    with db.transaction(current_app) as connection:
        connection.execute("UPDATE calc_jobs SET state='error',lease_token='',finished=?,detail=? WHERE label=? AND state='running'",
                           (db.now(), json.dumps({"cause": "관리자가 계산을 취소했습니다.", "hint": "재계산을 다시 시작할 수 있습니다."}, ensure_ascii=False), label))


def _rebase(value, old, new):
    if isinstance(value, str): return new + value[len(old):] if value.startswith(old + os.sep) else value
    if isinstance(value, list): return [_rebase(item, old, new) for item in value]
    if isinstance(value, dict): return {key: _rebase(item, old, new) for key, item in value.items()}
    return value


def _hydrate_inputs(root, label):
    files.hydrate("inputs/base", root)
    files.ensure("targets.json", root)
    with db.transaction(current_app) as connection:
        uploads = connection.execute("SELECT stored_name FROM uploads WHERE status='반영' AND week<=?", (label,)).fetchall()
        previous = connection.execute("SELECT label,published_job FROM weeks WHERE published_job IS NOT NULL AND label<? ORDER BY label DESC", (label,)).fetchall()
    for upload in uploads:
        if not files.ensure("uploads/" + upload["stored_name"], root):
            raise ValueError("반영 확정한 업로드 원본을 찾을 수 없습니다. 해당 파일을 다시 올려 주세요.")
    for week in previous:
        path = report_path(week["label"], "summary.json", published=True)
        if path:
            destination = Path(root) / "published" / week["label"] / "summary.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


def advance(label):
    from engine import run
    token = uuid.uuid4().hex
    now = int(time.time())
    with db.transaction(current_app) as connection:
        row = connection.execute("UPDATE calc_jobs SET lease_token=?,lease_until=? WHERE id=(SELECT id FROM calc_jobs WHERE label=? AND state='running' ORDER BY sequence DESC LIMIT 1) "
            "AND state='running' AND lease_until<=? RETURNING *", (token, now + LEASE, label, now)).fetchone()
    if not row: return status(label)
    saved = json.loads(row["artifacts"])
    with tempfile.TemporaryDirectory(prefix="mm-calc-") as root:
        try:
            files.restore(saved, root)
            work = Path(root) / "work" / label
            context_path = Path(root) / "context.json"
            if row["step"] == 0:
                _hydrate_inputs(root, label)
                cfg, warnings, used, log = run.prepare(root, label, row["by_user"])
                context = dict(root=root, cfg=cfg, warnings=warnings, used=used, log=log)
            else:
                context = json.loads(context_path.read_text(encoding="utf-8"))
                context = _rebase(context, context["root"], root)
                context["root"] = root
                cfg = context["cfg"]
                (work / "cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
                if row["step"] <= len(run.STEPS):
                    name, command = run.STEPS[row["step"] - 1]
                    args = [sys.executable, os.path.join(run.CALC, command[0])] + [a.format(work=str(work) + os.sep) for a in command[1:]]
                    env = dict(os.environ, GADONG_CFG=str(work / "cfg.json"), PYTHONPATH=run.CALC,
                               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
                    result = subprocess.run(args, cwd=run.CALC, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=220)
                    context["log"].append(f"## {name}\n{result.stdout[-3000:]}\n{result.stderr[-6000:]}")
                    if result.returncode: raise run.StepError(name, command[0], result.stderr, cfg["inputs"], context["used"])
                else:
                    run.finish(root, label, row["by_user"], cfg, context["warnings"], context["used"])
            context_path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
            (work / "log.txt").write_text("\n\n".join(context["log"]), encoding="utf-8")
            manifest = files.checkpoint(root, saved)
            complete = row["step"] == len(run.STEPS) + 1
            with db.transaction(current_app) as connection:
                accepted = connection.execute("UPDATE calc_jobs SET step=step+1,artifacts=?,state=?,finished=?,lease_token='',lease_until=0 WHERE id=? AND lease_token=? AND state='running' RETURNING id",
                    (json.dumps(manifest), "done" if complete else "running", db.now() if complete else "", row["id"], token)).fetchone()
                if accepted and complete: connection.execute("UPDATE weeks SET draft_job=? WHERE label=?", (row["id"], label))
            old_keys = {key for meta in saved.values() for key in files.blob_keys(meta)}
            new_keys = {key for meta in manifest.values() for key in files.blob_keys(meta)}
            try: files.remove_unreferenced(old_keys - new_keys if accepted else new_keys - old_keys)
            except files.StorageError: pass
        except Exception as error:
            if isinstance(error, run.StepError):
                detail = dict(msg=error.msg, cause=error.cause, hint=error.hint, files=error.files, step=error.step)
            elif isinstance(error, subprocess.TimeoutExpired):
                detail = dict(cause="현재 계산 단계가 제한 시간을 넘었습니다.", hint="입력 파일 크기와 양식을 확인한 뒤 다시 계산해 주세요.")
            elif isinstance(error, (ValueError, files.StorageError)):
                detail = dict(cause=str(error), hint="업로드·반영 확정 상태를 확인한 뒤 다시 계산해 주세요.")
            else:
                detail = dict(cause=f"계산 중 오류가 발생했습니다 ({type(error).__name__}).", hint="입력 양식과 자료를 확인해 주세요.")
            detail["log"] = "\n\n".join(context.get("log", []) if "context" in locals() else [])[-6000:]
            with db.transaction(current_app) as connection:
                connection.execute("UPDATE calc_jobs SET state='error',finished=?,detail=?,lease_token='',lease_until=0 WHERE id=? AND lease_token=? AND state='running'",
                                   (db.now(), json.dumps(detail, ensure_ascii=False), row["id"], token))
    return status(label)


def report_path(label, name, published=False):
    column = "published_job" if published else "draft_job"
    with db.transaction(current_app) as connection:
        row = connection.execute(f"SELECT j.artifacts FROM weeks w JOIN calc_jobs j ON j.id=w.{column} WHERE w.label=? AND j.state='done'", (label,)).fetchone()
    if not row: return None
    meta = json.loads(row["artifacts"]).get(f"drafts/{label}/{name}")
    return files.cached(meta) if meta else None


def publish(label):
    # 미리보기한 완성본의 모든 필수 결과가 있어야 포인터를 한 번에 전환한다.
    with db.transaction(current_app) as connection:
        selected = connection.execute("SELECT draft_job FROM weeks WHERE label=?", (label,)).fetchone()
    if not selected or not selected["draft_job"]: raise ValueError("게시할 계산본이 없습니다.")
    for name in ("admin.html", "meeting.html", "checks.json", "inputs.json", "summary.json"):
        if not report_path(label, name): raise ValueError("완성된 계산본이 없습니다. 재계산을 완료한 뒤 게시해 주세요.")
    with db.transaction(current_app) as connection:
        row = connection.execute("UPDATE weeks SET published_job=draft_job,published=1,published_at=? WHERE label=? AND draft_job=? AND draft_job IN (SELECT id FROM calc_jobs WHERE state='done') RETURNING published_job",
                                 (db.now(), label, selected["draft_job"])).fetchone()
        if not row: raise ValueError("게시할 계산본을 찾지 못했습니다.")
