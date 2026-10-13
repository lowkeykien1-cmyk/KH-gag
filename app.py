from flask import Flask, jsonify, render_template, request
import requests
import time
from threading import Lock

app = Flask(__name__)
PLACE_ID = 113290951185459  # Anime Dice place ID supplied in the conversation
ROBLOX_SERVERS_URL = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public"
ROBLOX_USERNAME_LOOKUP_URL = "https://users.roblox.com/v1/usernames/users"

_session = requests.Session()
_session.headers.update({
    "User-Agent": "KYOSH-Luck-Server-Finder/1.0 (public server browser)",
    "Accept": "application/json",
})
_cache = {}
_cache_lock = Lock()
CACHE_SECONDS = 20


def cached_get(key):
    with _cache_lock:
        item = _cache.get(key)
        if item and time.time() - item["time"] < CACHE_SECONDS:
            return item["data"]
    return None


def cache_set(key, data):
    with _cache_lock:
        _cache[key] = {"time": time.time(), "data": data}


@app.get("/")
def index():
    return render_template("index.html", place_id=PLACE_ID)


@app.get("/api/servers")
def servers():
    """Return public server instances and filter out full ones (9/9)."""
    try:
        limit = min(max(int(request.args.get("limit", "100")), 10), 100)
    except ValueError:
        limit = 100
    cursor = request.args.get("cursor", "")
    cache_key = f"servers:{limit}:{cursor}"
    cached = cached_get(cache_key)
    if cached is not None:
        return jsonify(cached)

    params = {"sortOrder": "Asc", "limit": limit}
    if cursor:
        params["cursor"] = cursor
    try:
        response = _session.get(ROBLOX_SERVERS_URL, params=params, timeout=12)
        response.raise_for_status()
        payload = response.json()
        result = []
        for server in payload.get("data", []):
            playing = int(server.get("playing", 0))
            max_players = int(server.get("maxPlayers", 9))
            # Anime Dice servers are expected to cap at 9. Keep only servers
            # that have space and normalize the displayed cap to 9.
            if playing >= 9:
                continue
            result.append({
                "id": server.get("id"),
                "playing": playing,
                "maxPlayers": max_players,
                "slotsLeft": max(0, 9 - playing),
                "ping": server.get("ping"),
                "fps": server.get("fps"),
                "luckStatus": "Unknown",
                "joinUrl": (
                    "https://www.roblox.com/games/start?placeId="
                    f"{PLACE_ID}&gameInstanceId={server.get('id')}"
                ),
            })
        data = {
            "placeId": PLACE_ID,
            "servers": result,
            "nextPageCursor": payload.get("nextPageCursor"),
            "previousPageCursor": payload.get("previousPageCursor"),
            "checkedAt": int(time.time()),
            "note": "Public server data only. Luck weather and player-to-server mapping are not exposed by this endpoint.",
        }
        cache_set(cache_key, data)
        return jsonify(data)
    except requests.RequestException as exc:
        return jsonify({
            "error": "Could not load Roblox public servers right now.",
            "details": str(exc),
            "servers": [],
        }), 502


@app.post("/api/lookup-user")
def lookup_user():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    if not username or len(username) > 20:
        return jsonify({"error": "Enter a valid Roblox username."}), 400
    try:
        response = _session.post(
            ROBLOX_USERNAME_LOOKUP_URL,
            json={"usernames": [username], "excludeBannedUsers": False},
            timeout=12,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            return jsonify({"found": False, "username": username})
        user = data[0]
        user_id = user.get("id")
        actual_name = user.get("name", username)
        return jsonify({
            "found": True,
            "id": user_id,
            "name": actual_name,
            "displayName": user.get("displayName", actual_name),
            "profileUrl": f"https://www.roblox.com/users/{user_id}/profile",
            "searchUrl": f"https://www.roblox.com/search/users?keyword={actual_name}",
            "message": "A profile match was found. Roblox does not provide this website the player's current server instance.",
        })
    except requests.RequestException as exc:
        return jsonify({"error": "Roblox username lookup failed.", "details": str(exc)}), 502




@app.post("/api/find-and-join")
def find_and_join():
    """Attempt a public presence lookup, then return a join URL only if Roblox exposes the instance."""
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    if not username or len(username) > 20:
        return jsonify({"found": False, "error": "Enter a valid Roblox username."}), 400

    try:
        lookup = _session.post(
            ROBLOX_USERNAME_LOOKUP_URL,
            json={"usernames": [username], "excludeBannedUsers": False},
            timeout=12,
        )
        lookup.raise_for_status()
        matches = lookup.json().get("data", [])
        if not matches:
            return jsonify({"found": False, "message": "No Roblox account matched that username."}), 404

        user = matches[0]
        user_id = user.get("id")
        actual_name = user.get("name", username)

        # Roblox presence endpoints may require authenticated access. Do not ask users
        # to provide cookies; if public access is denied, report that honestly.
        presence_response = _session.post(
            "https://presence.roblox.com/v1/presence/users",
            json={"userIds": [user_id]},
            timeout=12,
        )
        if presence_response.status_code in (401, 403):
            return jsonify({
                "found": True,
                "name": actual_name,
                "userId": user_id,
                "profileUrl": f"https://www.roblox.com/users/{user_id}/profile",
                "joinable": False,
                "status": "presence_unavailable",
                "message": "Roblox did not allow this website to read current presence. The public profile is available, but the current server cannot be confirmed."
            })

        presence_response.raise_for_status()
        presence_data = presence_response.json().get("userPresences", [])
        presence = presence_data[0] if presence_data else {}
        presence_type = presence.get("userPresenceType")
        current_place = presence.get("placeId")
        game_id = presence.get("gameId")

        if presence_type != 2 or not current_place or not game_id:
            return jsonify({
                "found": True,
                "name": actual_name,
                "userId": user_id,
                "profileUrl": f"https://www.roblox.com/users/{user_id}/profile",
                "joinable": False,
                "status": "instance_unavailable",
                "message": "The player is not reported in a joinable game, or Roblox did not provide the server instance ID."
            })

        if int(current_place) != PLACE_ID:
            return jsonify({
                "found": True,
                "name": actual_name,
                "userId": user_id,
                "profileUrl": f"https://www.roblox.com/users/{user_id}/profile",
                "joinable": False,
                "status": "different_game",
                "placeId": current_place,
                "message": "The player is playing a different experience, not the configured Anime Dice place."
            })

        join_url = (
            "https://www.roblox.com/games/start?placeId="
            f"{current_place}&gameInstanceId={game_id}"
        )
        return jsonify({
            "found": True,
            "name": actual_name,
            "userId": user_id,
            "joinable": True,
            "status": "instance_found",
            "placeId": current_place,
            "gameId": game_id,
            "joinUrl": join_url,
            "message": "Server instance found. Opening Roblox join link."
        })
    except requests.RequestException as exc:
        return jsonify({
            "found": True,
            "joinable": False,
            "status": "lookup_failed",
            "message": "Could not read the player's current server from Roblox. Their profile may still be public.",
            "details": str(exc)
        }), 502


@app.get("/health")
def health():
    return jsonify({"ok": True, "placeId": PLACE_ID})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
