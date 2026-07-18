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

5. Copy `.env.example` to `.env` and fill in the bot configuration:

   ```env
   discord_token=your_discord_bot_token
   dev_guild_id=0
   prefix=%
   log_level=INFO
   lead_dev_user_id=0
   toes_url=
   yoshimaru_url=
   mongo_connection_string=mongodb://localhost:27017
   mongo_database_name=BeanBotPythonDB
   mongo_role_menu_collection=roleMenus
   ```

Only `discord_token` is required; the other values fall back to defaults or may be left empty where applicable.

The Python bot stores self-role menus in `BeanBotPythonDB` by default, leaving the C# bot's legacy
`BeanBotDB` untouched. An administrator can run `%rolesetting` and choose up to 20 self-assignable
roles at once with Discord's role picker. The bot needs the Manage Roles and Embed Links
permissions, and its highest role must be above every role it assigns. Published role menus are
persistent across bot restarts.

### Migrate legacy reaction roles

The C# bot stores reaction roles in `BeanBotDB.roleSettings`. The migration command copies those
documents into `BeanBotPythonDB.roleMenus` and never writes to or deletes from the legacy database.
Migrated reaction messages keep working while newly created menus use Discord's multi-role picker.

Preview and validate the migration first:

```powershell
python -m beanbot.migrations.migrate_role_settings
```

If the MongoDB URI still lives in the deprecated bot's dotenv file, pass it without copying or
printing the credential:

```powershell
python -m beanbot.migrations.migrate_role_settings --env-file ../BeanBot-DEPRACATED/.env
```

Apply the copy only after the dry run reports no invalid documents or conflicts:

```powershell
python -m beanbot.migrations.migrate_role_settings --apply
```

The migration is idempotent: rerunning it skips documents already copied from the same legacy ID.
See [docs/role-menus.md](docs/role-menus.md) for the schema, architecture, verification, and
rollback procedure.

## Run

Start the bot from the project root after activating the virtual environment:

```powershell
python -m beanbot
```

The package entry point calls `src/beanbot/app.py`, loads settings from `.env`, configures logging, creates the Discord bot, and starts it with your configured token.
