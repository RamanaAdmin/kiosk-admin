import os, time, json
from flask import Flask, request, jsonify, render_template, session, redirect

APP = Flask(__name__, template_folder='templates')
APP.secret_key = "test-secret"
APP.config['SESSION_COOKIE_SAMESITE'] = "Lax"

STATE_PATH = "state.json"
URGENT_PATH = "urgent.json"
ADMIN_PIN = "1234"
STALE_MINUTES = 20

def now(): return int(time.time())
DEFAULT_STATE = {"status":"In Office","location":"Principal's Office","note":"","since":now()}

def load_state():
    try:
        with open(STATE_PATH, "r") as f: return json.load(f)
    except Exception:
        return DEFAULT_STATE.copy()

def save_state(s):
    with open(STATE_PATH, "w") as f: json.dump(s, f)

def set_state(status, location="", note=""):
    s = load_state()
    s["status"] = status
    s["location"] = location if location else s.get("location","")
    s["note"] = note
    s["since"] = now()
    save_state(s)
    return s

def load_urgent():
    try:
        with open(URGENT_PATH, "r") as f: return json.load(f)
    except Exception:
        return []

def save_urgent(lst):
    with open(URGENT_PATH, "w") as f: json.dump(lst, f)

def next_id(lst):
    return (max([m["id"] for m in lst], default=0) + 1)

@APP.route("/")
def index():
    return render_template("index.html")

@APP.get("/status")
def status():
    s = load_state()
    urgent = [m for m in load_urgent() if now() - m["time"] <= 20*60]
    last_urgent = urgent[-1] if urgent else None
    return jsonify({
        "status": s["status"],
        "location": s["location"],
        "note": s.get("note",""),
        "since": s["since"],
        "server_time": now(),
        "stale_after_min": STALE_MINUTES,
        "urgent": last_urgent
    })

@APP.post("/urgent")
def urgent():
    reason  = (request.form.get("reason") or "Other").strip()
    message = (request.form.get("message") or "").strip()
    name = (request.form.get("name") or "").strip()
    designation = (request.form.get("designation") or "").strip()
    if not message:
        return jsonify({"ok": False, "msg": "Message required"}), 400
    urgent = load_urgent()
    msg = {
        "id": next_id(urgent),
        "reason": reason,
        "text": message,
        "name": name,
        "designation": designation,
        "time": now(),
        "reply": None
    }
    urgent.append(msg)
    save_urgent(urgent)
    return jsonify({"ok": True, "id": msg["id"]})

@APP.get("/urgent")
def urgent_list():
    urgent = [m for m in load_urgent() if now() - m["time"] <= 20*60]
    return jsonify({"urgent": urgent})

@APP.post("/reply")
def reply():
    data = request.get_json(force=True)
    msg_id = int(data.get("id"))
    text = (data.get("text") or "").strip()
    urgent = load_urgent()
    for m in urgent:
        if m["id"] == msg_id:
            m["reply"] = {"text": text, "time": now()}
            save_urgent(urgent)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "msg": "Message not found"}), 404

@APP.post("/api/set")
def api_set():
    if not session.get("admin"): return jsonify({"ok": False, "msg": "Not authorized"}), 403
    data = request.get_json(force=True)
    set_state(data.get("status","In Office"), data.get("location",""), data.get("note",""))
    return jsonify({"ok": True})

@APP.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        pin = (request.form.get("pin") or "").strip()
        if pin == ADMIN_PIN:
            session["admin"] = True
            session.permanent = True
            return redirect("/admin")
        else:
            error = "Wrong PIN"
    return render_template("login.html", error=error)

@APP.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@APP.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/login")
    return render_template("admin.html")

if __name__ == "__main__":
    if not os.path.exists(STATE_PATH): save_state(DEFAULT_STATE.copy())
    if not os.path.exists(URGENT_PATH): save_urgent([])
    print("Kiosk: http://127.0.0.1:5000  Admin: http://127.0.0.1:5000/admin")
    APP.run(host="0.0.0.0", port=5000, debug=True)
