# beanbot

Code for a bot written for the Midwest Illinois Livers and Friends server, re-written in Python and planning to host on a Raspberry Pi 5. May move to an arch linux box in the future. Will run Docker. I have goals of writing this in a very enterprise Python app way. I also plan on somehow microservicing a Discord bot, I'm sure it's possible. Or I might not. Is the speed of a quick command like %help worth sacrificing to make it reusable across every bot? Or maybe I make simple commands like that, a library instead. Who knows!

## Setup

This project requires Python 3.11 or newer.

1. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

2. Activate it in PowerShell:

   ```powershell
   & .venv\Scripts\Activate.ps1
   ```

3. Install the project in editable mode:

   ```powershell
   pip install -e .
   ```

4. If you want linting, typing, and test tools as well, install the dev extras:

   ```powershell
   pip install -e .[dev]
   ```

5. Create a `.env` file in the project root with the bot configuration:

   ```env
   discord_token=your_discord_bot_token
   dev_guild_id=0
   prefix=%
   log_level=INFO
   lead_dev_user_id=0
   toes_url=
   yoshimaru_url=
   ```

Only `discord_token` is required; the other values fall back to defaults or may be left empty where applicable.

## Run

Start the bot from the project root after activating the virtual environment:

```powershell
python -m beanbot
```

The package entry point calls `src/beanbot/app.py`, loads settings from `.env`, configures logging, creates the Discord bot, and starts it with your configured token.
