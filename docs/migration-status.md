# .NET migration status

The Python migration is complete when every legacy behavior is either **Complete** or explicitly
**Retired**. **Partial** and **Remaining** rows are still migration work.

| Legacy capability | Status | Python location or remaining work |
| --- | --- | --- |
| Help command | Complete | `features/help` |
| Developer command | Complete | `features/info` |
| Ping command | Complete | `features/ping` |
| Meme API command | Complete | `features/memes` |
| Pun-on-demand command and CSV data | Complete | `features/memes/puns.py` and `resources/puns.csv` |
| Novelty command set | Complete | `features/memes/cog.py` |
| Reaction-role data and reaction handling | Complete | `features/role_menus`; legacy data has a safe copy migration |
| Multi-role self-service setup | Complete | Replaces one-role-at-a-time setup with persistent role selects |
| Legacy environment variable compatibility | Complete | `core/config.py` |
| 8-ball behavior | Partial | Basic question/response flow exists; richer validation, response overrides, queue responses, and PunMaster behavior remain |
| Command prefixes and legacy aliases | Partial | `%` and mention prefixes work; legacy `succ ` prefix and some aliases need a product decision or implementation |
| Automatic daily pun | Complete | `features/memes/cog.py` posts at 16:20 America/Chicago to `general_channel_id`; covered by `tests/unit/features/memes/test_cog.py` |
| New-member direct message | Remaining | Port the non-bot member welcome/instruction handler |
| Edited 8-ball request handling | Remaining | Track the response and replace it when the original request is edited |
| Connection health endpoint | Remaining | Port or replace authenticated `/healthz`, readiness state, and rate limiting |
| Empty time-based auto-post handler | Retired | Legacy handler has no posting behavior to preserve |
| Commented-out role/shine/delete/patch code | Retired | Dead legacy code is not part of supported behavior |

## Recommended completion order

1. Finish 8-ball parity and decide which legacy aliases are still supported.
2. Add member-join and message-edit event features.
3. Define the deployment health contract, then implement the smallest endpoint that satisfies it.
4. Run a Discord staging-server parity checklist and mark the remaining rows complete or retired.

The role-menu migration does not mutate `BeanBotDB.roleSettings`. It copies valid documents into
the separately configured Python database and collection. See [role-menus.md](role-menus.md) for
the operational procedure.

Runtime settings continue to accept the old C# environment names where parity features depend on
them, including `BEANBOT_GENERAL_CHANNEL_ID` for the daily pun destination.
