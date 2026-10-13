# KYOSH Luck Server Finder

## Deploy to Render

1. Upload this folder to a GitHub repository.
2. Sign in to https://render.com and choose **New + → Blueprint** if you want Render to read `render.yaml`, or choose **New + → Web Service** and connect the repository.
3. For a Web Service, use:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
4. Deploy and open the `onrender.com` URL Render gives you.

The `Procfile` and `render.yaml` are included for deployment support.

## Local Windows run

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py app.py
```

Then open http://127.0.0.1:5000.

## Important feature limitations

This app lists public Roblox server instances and looks up public Roblox usernames. It cannot detect Anime Dice luck weather or map a username to their current server using the public endpoints used here. Weather is intentionally labeled **Unverified**. The app does not read in-game Global chat automatically.


## Find-and-join attempt

The Find button now calls `/api/find-and-join`. It resolves the username, then attempts to read Roblox presence and opens a server-specific join URL only if Roblox returns the player's current Anime Dice place and game instance ID.

**Important:** Roblox may block unauthenticated presence requests or omit the instance ID. In that case the website will show that the server is unavailable; it cannot force a join from a public profile alone. Do not add Roblox passwords or `.ROBLOSECURITY` cookies to this app.
