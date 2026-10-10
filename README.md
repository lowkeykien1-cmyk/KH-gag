# KYOSH Control Dashboard

A Render + Flask + PostgreSQL dashboard with:
- Authenticated dark dashboard and session login
- Account heartbeat monitor for Roblox experiences you own/are authorized to modify
- Gift-request builder that stores requests but **does not send third-party game gifts**
- Event log and protected API endpoints
- Optional Roblox server-side heartbeat Script

## Important third-party boundary

If you only have client-side access to someone else's Roblox experience, there is no authorized way for this app to invoke its server-side mailbox remote. Do not put executor scripts into a third-party game. The gift UI here is a request tracker/demo only. Live gifting requires the game's owner to implement a server-side endpoint and verify the actual inventory and recipient server-side.

## Deploy to Render

1. Create a PostgreSQL database in Render.
2. Create a Web Service from this project or upload the files to your GitHub repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables:
   - `DATABASE_URL`: Render PostgreSQL **internal** connection string
   - `FLASK_SECRET_KEY`: long random secret (Render can generate this)
   - `DASHBOARD_USERNAME`: your login name
   - `DASHBOARD_PASSWORD_HASH`: hash generated below
   - `ROBLOX_API_KEY`: a different long random secret for the server Lua script
   - `HEARTBEAT_TIMEOUT_SECONDS`: `90`
   - `DEMO_MODE`: `true`
6. Generate password hash locally:
   `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('CHANGE_THIS_TO_A_LONG_PASSWORD'))"`
   Copy the output to `DASHBOARD_PASSWORD_HASH`. Do not store your plain password in code.
7. Set a strong unique `FLASK_SECRET_KEY`. Never reuse `ROBLOX_API_KEY` as the Flask session secret.
8. Visit `/login`.

## Authorized Roblox heartbeat

Only for a Roblox experience you own or are authorized to edit:
1. In Roblox Studio, enable **Allow HTTP Requests**.
2. Add `roblox/KYOSH_ServerHeartbeat.server.lua` as a normal server Script in ServerScriptService.
3. Replace `API_URL` with your Render service URL.
4. Replace `API_KEY` with the same `ROBLOX_API_KEY` environment variable value.
5. Publish the game and test with a private test server first.

The key must remain in a server Script and must never be copied into a LocalScript, UI, or public repository. If the repository is public, keep the live key out of the file until you deploy privately, or inject it through a secure deployment workflow.

## Endpoints

- `GET /health` health check
- `POST /api/monitor/heartbeat` API-key protected heartbeat
- `GET /api/monitor/status` dashboard-session protected account status
- `POST /api/gifts` dashboard-session protected gift-request record (not an actual in-game send)
- `GET /api/gifts` dashboard-session protected request list
- `POST /api/roblox/events` API-key protected event record

## Notes

- Heartbeat records are presence observations, not proof of ownership or authorization.
- Do not use this system to collect Roblox passwords, cookies, authentication tokens, or private account credentials.
- For production, use HTTPS, rotate secrets if exposed, keep dependencies updated, and use a private repository for deployment-specific configuration.
