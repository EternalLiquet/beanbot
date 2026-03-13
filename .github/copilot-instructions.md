# Copilot Instructions for beanbot

## Project Overview

- **beanbot** is a Discord bot for the Midwest Illinois Livers and Friends server, written in Python.
- Designed for enterprise-level structure, with potential for microservice architecture and Docker deployment.
- Main bot logic is under `src/beanbot/`, with submodules for cogs, services, Discord integration, and resources.

## Key Components

- `src/beanbot/app.py`: Entry point for bot application logic.
- `src/beanbot/discord/bot.py`: Discord bot setup and event handling.
- `src/beanbot/cogs/`: Contains bot commands and features, organized as cogs (e.g., `help.py`, `meme_cog.py`).
- `src/beanbot/services/`: Service modules for external APIs and business logic (e.g., `meme_api.py`, `puns.py`).
- `src/beanbot/resources/`: Static resources (e.g., `puns.csv`).
- `src/beanbot/config.py` & `logging_config.py`: Configuration and logging setup.

## Developer Workflows

- **Environment**: Use a Python virtual environment (`.venv`). Activate with `& .venv\Scripts\Activate.ps1` (Windows PowerShell).
- **Build/Install**: Use `pyproject.toml` for dependencies and build config. Install with `pip install -e .` from project root.
- **Run Bot**: Launch via `python -m beanbot` or `python src/beanbot/__main__.py`.
- **Testing**: No explicit test directory found; add tests under `src/beanbot/tests/` if needed.
- **Debugging**: Use logging configuration in `logging_config.py`. Adjust log levels as needed.

## Project Conventions

- **Cogs**: Each cog implements a bot feature. Register cogs in the main bot setup.
- **Services**: Business logic and API integrations are separated from cogs for modularity.
- **Resources**: Use CSVs and other static files for data-driven features.
- **Configuration**: Centralized in `config.py`.
- **Egg-info**: Ignore `beanbot.egg-info/` for code changes; it's for packaging metadata.

## Integration Points

- **Discord.py**: Core library for bot functionality.
- **External APIs**: Accessed via service modules (e.g., meme API).
- **Docker**: Planned for deployment; Dockerfile not found, but structure supports containerization.

## Patterns & Examples

- Register cogs in bot setup:
  ```python
  from beanbot.cogs.help import HelpCog
  bot.add_cog(HelpCog(bot))
  ```
- Use services for API calls:
  ```python
  from beanbot.services.meme_api import get_meme
  meme = get_meme()
  ```
- Logging setup:
  ```python
  import beanbot.logging_config
  ```

## References

- See `src/beanbot/cogs/` for command patterns.
- See `src/beanbot/services/` for integration logic.
- See `README.md` for project background.

---

**Update this file as the project evolves.**
