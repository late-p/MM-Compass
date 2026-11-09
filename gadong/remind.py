"""제출 안내 메일 (관리자). 제출 현황에서 아직 제출하지 않은 부서의 담당자에게 안내 메일을 보낸다.
- 받는 주소: 사용자 화면에서 담당자별로 입력한 메일 칸 (users.email)
- 보내는 설정: storage/mail.json  {"host","port","user","password","from","ssl"}  — 없으면 '미리보기 모드'(실제 발송 없이 기록만)
- 사람 한 명당 한 통: 그 사람이 맡은 미제출 부서를 한 메일에 모아서 보낸다"""
import os, json, smtplib, ssl, sqlite3
from email.message import EmailMessage
from email.utils import formataddr
from flask import render_template, request, redirect, url_for, flash, g, current_app
from . import db, org as ORG
from .auth import login_required, check_csrf
from .scope import user_depts

NEED = ("미제출", "반려", "보류", "확인 대기")
DEFAULT_SUBJECT = "[MM-Compass] {주차} 투입계획 제출 요청"
DEFAULT_BODY = """{이름}님, 안녕하세요.
인력관리팀입니다.

{주차} 투입계획이 아직 제출되지 않아 안내드립니다.

■ 제출이 필요한 부서
{부서목록}

■ 제출 마감: {마감}

■ 제출 방법
MM-Compass에 로그인하신 뒤 「이번 주 제출」에서 화면 입력, 템플릿 파일 올리기, 변동없음 제출 중 편한 방법으로 제출해 주세요.
변동이 없으면 「변동없음」 한 번으로 끝납니다.

이미 제출하셨다면 이 메일은 무시해 주세요.
감사합니다.

{발신자} 드림"""

def _mail_path(): return os.path.join(current_app.config["STORAGE"], "mail.json")
def mail_conf():
    try: return json.load(open(_mail_path(), encoding="utf-8"))
    except Exception: return {}

def ensure_schema(app):
    if app.config.get("DATABASE_URL"): return
    with db.transaction(app) as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
        if "email" not in cols: c.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
        c.executescript("""CREATE TABLE IF NOT EXISTS mail_log(
  id INTEGER PRIMARY KEY, at TEXT, week TEXT, user_id INTEGER, email TEXT, subject TEXT, mode TEXT, ok INTEGER, err TEXT DEFAULT '');""")
        if os.path.exists(os.path.join(app.config["BASE_DIR"], "_demo_meta.json")):   # 데모: 가상 주소를 채워 둠 (실제 발송 없음)
            c.execute("UPDATE users SET email=username||'@hanbit-demo.example' WHERE role='uploader' AND (email IS NULL OR email='')")

def targets(wl):
    """사람별로 모은 안내 대상: [{u, teams:[(label, 상태)]}]"""
    from . import submit as SB
    S = current_app.config["STORAGE"]; per = {}
    mine = {}
    for r in db.get().execute("SELECT * FROM users WHERE role='uploader' AND active=1 ORDER BY display"):
        mine[r["id"]] = (r, set(ORG.expand(S, user_depts(r))))
    orphan = []
    for k in ORG.expand(S, SB.target_depts()):
        st, _ = SB.week_state(k, wl)
        if st not in NEED: continue
        hit = False
        for uid, (r, ks) in mine.items():
            if k in ks: per.setdefault(uid, []).append((ORG.label(k), st)); hit = True
        if not hit: orphan.append(ORG.label(k))
    out = [dict(u=mine[uid][0], teams=ts) for uid, ts in per.items()]
    return out, orphan

def compose(tpl_subject, tpl_body, name, teams, wtitle, dl, sender):
    lst = "\n".join(f"- {l} · {SBV.get(s, s)}" for l, s in teams)
    rep = {"{이름}": name, "{주차}": wtitle, "{부서목록}": lst, "{마감}": dl, "{발신자}": sender}
    sub, body = tpl_subject, tpl_body
    for a, b in rep.items(): sub, body = sub.replace(a, b), body.replace(a, b)
    return sub, body
SBV = {"미제출": "미제출", "반려": "반려 · 다시 제출 필요", "보류": "보류", "확인 대기": "작성 중 · 제출 필요"}

def send_one(conf, to, subject, body, sender_name):
    m = EmailMessage(); m["Subject"] = subject; m["To"] = to
    m["From"] = formataddr((sender_name, conf.get("from") or conf.get("user")))
    m.set_content(body)
    port = int(conf.get("port") or (465 if conf.get("ssl") else 587))
    if conf.get("ssl"):
        s = smtplib.SMTP_SSL(conf["host"], port, timeout=20, context=ssl.create_default_context())
    else:
        s = smtplib.SMTP(conf["host"], port, timeout=20); s.ehlo()
        if s.has_extn("starttls"): s.starttls(context=ssl.create_default_context()); s.ehlo()
        elif conf.get("user"): s.quit(); raise RuntimeError("메일 서버가 암호화(STARTTLS)를 지원하지 않아 로그인 정보를 보낼 수 없습니다")
    try:
        if conf.get("user"): s.login(conf["user"], conf.get("password", ""))
        s.send_message(m)
    finally:
        try: s.quit()
        except Exception: pass

def register(app):
    ensure_schema(app)

    @app.route("/admin/remind", methods=["GET", "POST"])
    @login_required("admin")
    def remind():
        from . import submit as SB
        d = db.get(); wks = SB.weeks_back(8)
        wl = request.values.get("week") or wks[0][0]; wt = dict(wks).get(wl, wl)
        dl, _ = SB.deadline(wl); dl_txt = SB.dl_text(dl)
        conf = mail_conf(); live = bool(conf.get("host"))
        T, orphan = targets(wl)
        subj = request.form.get("subject") or DEFAULT_SUBJECT
        body = request.form.get("body") or DEFAULT_BODY
        if request.method == "POST":
            check_csrf(); act = request.form.get("act")
            if act == "conf":
                new = {k: request.form.get(k, "").strip() for k in ("host", "port", "user", "from")}
                new["ssl"] = request.form.get("ssl") == "1"
                pw = request.form.get("password", "")
                new["password"] = pw if pw else conf.get("password", "")
                if not new["host"]: new = {}
                json.dump(new, open(_mail_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                db.audit(g.user["username"], "mail_conf", new.get("host", "(해제)")); flash("메일 보내기 설정을 저장했습니다." if new else "메일 보내기 설정을 해제했습니다. (미리보기 모드)")
                return redirect(url_for("remind", week=wl))
            if act == "send":
                ids = {int(x) for x in request.form.getlist("to")}
                sent = fail = 0; mode = "발송" if live else "미리보기"
                for t in T:
                    u = t["u"]
                    if u["id"] not in ids: continue
                    em = (u["email"] or "").strip()
                    if not em: fail += 1; continue
                    sj, bd = compose(subj, body, u["display"], t["teams"], wt, dl_txt, g.user["display"])
                    ok, err = 1, ""
                    if live:
                        try: send_one(conf, em, sj, bd, g.user["display"])
                        except Exception as e: ok, err = 0, str(e)[:200]
                    d.execute("INSERT INTO mail_log(at,week,user_id,email,subject,mode,ok,err) VALUES(?,?,?,?,?,?,?,?)", (db.now(), wl, u["id"], em, sj, mode, ok, err)); d.commit()
                    if ok: sent += 1
                    else: fail += 1
                db.audit(g.user["username"], "remind", f"{wl} · {mode} {sent}명 · 실패 {fail}")
                flash((f"{sent}명에게 제출 안내 메일을 보냈습니다." if live else f"미리보기 모드라 실제로는 보내지 않았습니다. {sent}명 발송 기록만 남겼습니다.") + (f" (실패·주소 없음 {fail}명)" if fail else ""))
                return redirect(url_for("remind", week=wl))
        last = {}
        for r in d.execute("SELECT user_id, MAX(at) at FROM mail_log WHERE week=? AND ok=1 GROUP BY user_id", (wl,)): last[r["user_id"]] = r["at"]
        prev = []
        if T:
            t0 = T[0]; sj, bd = compose(subj, body, t0["u"]["display"], t0["teams"], wt, dl_txt, g.user["display"]); prev = (t0["u"]["display"], sj, bd)
        return render_template("remind.html", T=T, wks=wks, wl=wl, wt=wt, dl_txt=dl_txt, live=live, conf=conf, last=last, subj=subj, body=body, prev=prev, SBV=SBV, orphan=orphan)
