# Beanbot

A Discord bot for the Midwest Illinois Livers and Friends server, migrated from the original .NET
application to Python. It is organized as a feature-oriented modular monolith: clear domain
boundaries and testable services, without unnecessary distributed-system overhead.

See [the architecture guide](docs/architecture.md) for package ownership and dependency rules, and
[the migration status](docs/migration-status.md) for the remaining .NET parity work.

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
   general_channel_id=0
   toes_url=
   yoshimaru_url=
   mongo_connection_string=mongodb://localhost:27017
   mongo_database_name=BeanBotPythonDB
   mongo_role_menu_collection=roleMenus
   ```

Only `discord_token` is required; the other values fall back to defaults or may be left empty where applicable.
Set `general_channel_id` to enable the daily 4:20 PM America/Chicago pun post in that channel.
The scheduler sends the same legacy sequence: intro line, 420 emote, then one random pun from
`resources/puns.csv`.

The Python settings also accept the legacy C# deployment names:

| Python setting | Legacy environment name |
| --- | --- |
| `discord_token` | `BEANBOT_BOT_TOKEN` |
| `general_channel_id` | `BEANBOT_GENERAL_CHANNEL_ID` |
| `toes_url` | `BEANBOT_HATOETE_URL` |
| `yoshimaru_url` | `BEANBOT_YOSHIMARU_URL` |
| `mongo_connection_string` | `BEANBOT_MONGO_CONNECTION_STRING` |

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

Apply requires a transaction-capable MongoDB replica set or mongos. A standalone deployment is
reported as unsupported and receives no inserts. Eligible documents are committed in one
transaction, so a late duplicate or write failure cannot leave that run partially inserted.

The migration is idempotent: rerunning it skips documents already copied from the same source
database, source collection, and legacy ID.
See [docs/role-menus.md](docs/role-menus.md) for the schema, architecture, verification, and
rollback procedure.

## Run

Start the bot from the project root after activating the virtual environment:

```powershell
python -m beanbot
```

The package entry point calls `src/beanbot/app.py`, loads settings from `.env`, configures logging, creates the Discord bot, and starts it with your configured token.
