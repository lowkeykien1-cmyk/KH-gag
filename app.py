import os, hmac, secrets, hashlib, json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD_HASH = os.environ.get("DASHBOARD_PASSWORD_HASH", "")
ROBLOX_API_KEY = os.environ.get("ROBLOX_API_KEY", "")
HEARTBEAT_TIMEOUT = int(os.environ.get("HEARTBEAT_TIMEOUT_SECONDS", "90"))
DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() == "true"

if not app.secret_key:
    raise RuntimeError("Set FLASK_SECRET_KEY in Render environment variables.")
if not DATABASE_URL:
    raise RuntimeError("Set DATABASE_URL to your PostgreSQL connection string.")
if not DASHBOARD_PASSWORD_HASH:
    raise RuntimeError("Set DASHBOARD_PASSWORD_HASH. Generate with: python -c \"from werkzeug.security import generate_password_hash; print(generate_password_hash('YOUR_PASSWORD'))\"")
if not ROBLOX_API_KEY:
    raise RuntimeError("Set ROBLOX_API_KEY to a long random secret.")

limiter = Limiter(get_remote_address, app=app, default_limits=["300 per hour"])
VALID_CATEGORIES = {
    "Pets", "Sprinklers", "WateringCans", "Mushrooms", "Gnomes", "Raccoons",
    "Crates", "SeedPacks", "Trowels", "Props", "Seeds", "HarvestedFruits", "EmptyPots"
}

@contextmanager
def db():
    conn = psycopg2.connect(DATABASE_URL, sslmode="require", cursor_factory=RealDictCursor)
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS monitor_accounts (
      user_id TEXT PRIMARY KEY,
      username TEXT NOT NULL DEFAULT '',
      display_name TEXT NOT NULL DEFAULT '',
      online BOOLEAN NOT NULL DEFAULT FALSE,
      last_seen TIMESTAMPTZ,
      heartbeat_at TIMESTAMPTZ,
      place_id TEXT NOT NULL DEFAULT '',
      server_job_id TEXT NOT NULL DEFAULT '',
      public_status TEXT NOT NULL DEFAULT 'No heartbeat yet',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS monitor_events (
      id BIGSERIAL PRIMARY KEY,
      user_id TEXT NOT NULL,
      event_type TEXT NOT NULL,
      details JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS gift_requests (
      id BIGSERIAL PRIMARY KEY,
      requester_user_id TEXT NOT NULL,
      recipient_user_id TEXT NOT NULL,
      recipient_name TEXT NOT NULL DEFAULT '',
      category TEXT NOT NULL,
      item_key TEXT NOT NULL,
      quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 100),
      message TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'queued',
      mode TEXT NOT NULL DEFAULT 'demo',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS monitor_events_created_idx ON monitor_events(created_at DESC);
    CREATE INDEX IF NOT EXISTS gift_requests_created_idx ON gift_requests(created_at DESC);
    """
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

@app.before_request
def ensure_db():
    if not getattr(app, "_db_ready", False):
        init_db()
        app._db_ready = True

def dashboard_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("dashboard_logged_in"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def constant_time_secret(candidate):
    return bool(candidate and hmac.compare_digest(candidate, ROBLOX_API_KEY))

def api_key_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        candidate = auth[7:] if auth.startswith("Bearer ") else request.headers.get("X-Kyosh-Key", "")
        if not constant_time_secret(candidate):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper

def add_event(cur, user_id, event_type, details):
    cur.execute(
        "INSERT INTO monitor_events(user_id,event_type,details) VALUES(%s,%s,%s::jsonb)",
        (str(user_id), event_type, json.dumps(details or {}))
    )

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "KYOSH dashboard", "mode": "demo" if DEMO_MODE else "monitor-only"})

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if hmac.compare_digest(username, DASHBOARD_USERNAME) and check_password_hash(DASHBOARD_PASSWORD_HASH, password):
            session.clear()
            session["dashboard_logged_in"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.post("/logout")
@dashboard_login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/")
@dashboard_login_required
def dashboard():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE heartbeat_at > NOW() - (%s * INTERVAL '1 second')) AS active FROM monitor_accounts", (HEARTBEAT_TIMEOUT,))
            counts = cur.fetchone()
            cur.execute("""
                SELECT user_id, username, display_name, online, last_seen, heartbeat_at, place_id, public_status,
                (heartbeat_at > NOW() - (%s * INTERVAL '1 second')) AS heartbeat_fresh
                FROM monitor_accounts ORDER BY heartbeat_at DESC NULLS LAST LIMIT 100
            """, (HEARTBEAT_TIMEOUT,))
            accounts = cur.fetchall()
            cur.execute("SELECT id, requester_user_id, recipient_user_id, recipient_name, category, item_key, quantity, message, status, mode, created_at FROM gift_requests ORDER BY created_at DESC LIMIT 50")
            gifts = cur.fetchall()
            cur.execute("SELECT id, user_id, event_type, details, created_at FROM monitor_events ORDER BY created_at DESC LIMIT 30")
            events = cur.fetchall()
    return render_template("dashboard.html", counts=counts, accounts=accounts, gifts=gifts, events=events, demo_mode=DEMO_MODE)

@app.post("/api/monitor/heartbeat")
@limiter.limit("120 per minute")
@api_key_required
def heartbeat():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    username = str(data.get("username", "")).strip()[:40]
    display_name = str(data.get("display_name", "")).strip()[:60]
    place_id = str(data.get("place_id", "")).strip()[:32]
    server_job_id = str(data.get("server_job_id", "")).strip()[:80]
    if not user_id.isdigit() or len(user_id) > 20:
        return jsonify({"ok": False, "error": "user_id must be a numeric Roblox user ID"}), 400
    now = datetime.now(timezone.utc)
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
              INSERT INTO monitor_accounts(user_id,username,display_name,online,last_seen,heartbeat_at,place_id,server_job_id,public_status)
              VALUES(%s,%s,%s,TRUE,%s,%s,%s,%s,'Heartbeat received')
              ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username, display_name=EXCLUDED.display_name,
              online=TRUE,last_seen=EXCLUDED.last_seen,heartbeat_at=EXCLUDED.heartbeat_at,
              place_id=EXCLUDED.place_id,server_job_id=EXCLUDED.server_job_id,public_status='Heartbeat received'
            """, (user_id, username, display_name, now, now, place_id, server_job_id))
            add_event(cur, user_id, "heartbeat", {"username": username, "place_id": place_id})
    return jsonify({"ok": True, "server_time": now.isoformat()})

@app.get("/api/monitor/status")
@dashboard_login_required
def monitor_status():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
              UPDATE monitor_accounts SET online=FALSE, public_status='Heartbeat timed out'
              WHERE online=TRUE AND heartbeat_at < NOW() - (%s * INTERVAL '1 second')
            """, (HEARTBEAT_TIMEOUT,))
            cur.execute("SELECT user_id, username, display_name, online, last_seen, heartbeat_at, place_id, public_status FROM monitor_accounts ORDER BY heartbeat_at DESC NULLS LAST LIMIT 100")
            rows = cur.fetchall()
    return jsonify({"ok": True, "accounts": rows})

@app.post("/api/gifts")
@dashboard_login_required
@limiter.limit("20 per minute")
def create_gift_request():
    data = request.get_json(silent=True) or request.form
    requester = str(data.get("requester_user_id", "")).strip()
    recipient = str(data.get("recipient_user_id", "")).strip()
    recipient_name = str(data.get("recipient_name", "")).strip()[:60]
    category = str(data.get("category", "")).strip()
    item_key = str(data.get("item_key", "")).strip()[:100]
    message = str(data.get("message", "")).strip()[:200]
    try:
        quantity = int(data.get("quantity", 1))
    except (ValueError, TypeError):
        quantity = 0
    if not requester.isdigit() or not recipient.isdigit():
        return jsonify({"ok": False, "error": "Enter numeric Roblox user IDs."}), 400
    if requester == recipient:
        return jsonify({"ok": False, "error": "Sender and recipient must be different."}), 400
    if category not in VALID_CATEGORIES or not item_key:
        return jsonify({"ok": False, "error": "Choose a supported category and enter an item key."}), 400
    if quantity < 1 or quantity > 100:
        return jsonify({"ok": False, "error": "Quantity must be between 1 and 100."}), 400
    # Client-only access to a third-party game means this is a request record only.
    mode = "demo" if DEMO_MODE else "pending-owner-integration"
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
              INSERT INTO gift_requests(requester_user_id,recipient_user_id,recipient_name,category,item_key,quantity,message,status,mode)
              VALUES(%s,%s,%s,%s,%s,%s,%s,'queued',%s) RETURNING id
            """, (requester, recipient, recipient_name, category, item_key, quantity, message, mode))
            gift_id = cur.fetchone()["id"]
            add_event(cur, requester, "gift_request_created", {"gift_id": gift_id, "recipient_user_id": recipient, "mode": mode})
    return jsonify({"ok": True, "id": gift_id, "status": "queued", "mode": mode,
                    "note": "Saved as a request only. It does not send an in-game gift."}), 201

@app.get("/api/gifts")
@dashboard_login_required
def list_gifts():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, requester_user_id, recipient_user_id, recipient_name, category, item_key, quantity, message, status, mode, created_at FROM gift_requests ORDER BY created_at DESC LIMIT 100")
            rows = cur.fetchall()
    return jsonify({"ok": True, "requests": rows})

@app.post("/api/roblox/events")
@api_key_required
@limiter.limit("120 per minute")
def roblox_event():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    event_type = str(data.get("event_type", "event")).strip()[:40]
    details = data.get("details", {})
    if not user_id.isdigit():
        return jsonify({"ok": False, "error": "invalid user_id"}), 400
    if not isinstance(details, dict):
        details = {}
    # Never accept passwords, cookies, auth tokens, or arbitrary account secrets.
    with db() as conn:
        with conn.cursor() as cur:
            add_event(cur, user_id, event_type, details)
    return jsonify({"ok": True})

@app.errorhandler(429)
def rate_limited(_):
    return jsonify({"ok": False, "error": "rate limit exceeded"}), 429

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
