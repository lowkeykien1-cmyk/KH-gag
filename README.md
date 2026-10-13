# KYOSH Luck Server Finder

A Flask starter website for Anime Dice that:
- Lists public Roblox server instances when Roblox's public server endpoint is accessible.
- Filters out servers with 9 or more players and shows open slots based on a 9-player cap.
- Looks up a Roblox username through Roblox's public username lookup endpoint.
- Lets you save local notes for usernames and unit rolls spotted in Global chat.
- Provides a Join link for each public server instance.

## Important limitation

Roblox's public server list does **not** tell this website which instance has luck weather, nor does the username lookup endpoint reveal which server a player is currently in. Therefore, the website deliberately labels weather as **Unverified**. A rare-roll chat message is a clue, not proof that a server has luck weather.

The site does not read Anime Dice chat automatically. Paste usernames manually. It does not use executors, scrape private game data, or bypass Roblox access controls.

## Run on Windows

1. Install Python 3.10 or newer.
2. Extract the ZIP.
3. Open Command Prompt in the `KYOSH_Luck_Server_Finder` folder.
4. Run:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   py app.py
   ```

5. Open `http://127.0.0.1:5000` in your browser.

## Notes

- Place ID is set to `113290951185459`, based on the Anime Dice place file name supplied in the conversation. Change `PLACE_ID` in `app.py` if needed.
- Server counts change frequently; a displayed server may fill before you join.
- Roblox may change API behavior, rate limits, or joining URLs. The code has not been verified against a live Roblox session.
- This starter project has no account passwords, cookies, or authentication storage. Do not add your Roblox password or `.ROBLOSECURITY` cookie to it.
