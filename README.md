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
