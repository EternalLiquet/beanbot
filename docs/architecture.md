# Architecture

Beanbot is a feature-oriented modular monolith. That gives a small Discord bot clear ownership
boundaries without adding deployment or network complexity that the project does not need.

## Package map

```text
src/beanbot/
+-- app.py                 # process composition root
+-- core/                  # settings and cross-cutting infrastructure
+-- discord/               # bot lifecycle and Discord client adapter
+-- features/
|   +-- registry.py        # enabled extension inventory
|   +-- help/              # one vertical slice per bot capability
|   +-- info/
|   +-- memes/
|   +-- ping/
|   +-- role_menus/
+-- migrations/            # explicit, operator-run data migrations
+-- resources/             # packaged static assets
```

Tests mirror these boundaries under `tests/unit/`. A future integration suite can live under
`tests/integration/` without mixing MongoDB or Discord lifecycle tests into fast unit tests.

## Dependency rules

- `app.py` is the composition root. It creates the process and should contain no bot behavior.
- `core` must not import Discord features.
- `discord` owns connection lifecycle and loads the extensions listed in `features.registry`.
- A feature owns its commands, models, services, persistence adapter, and UI components. Features
  should not reach into another feature's internals.
- MongoDB access stays behind feature repositories. Commands and views do not issue raw queries.
- Document schema changes are implemented as separate migrations. Runtime startup never silently
  rewrites production documents.
- `resources` contains immutable packaged data only.

## Design guidance

Prefer adding behavior to an existing feature slice. Create a new feature when it represents a
separate capability with its own Discord events, commands, or persistence. Split a feature further
when a module gains a second reason to change. For example, the role-menu slice separates Discord
views, persistence, document models, and role-assignment behavior.

This structure intentionally avoids a generic `services/` or `cogs/` dumping ground. It also avoids
microservices: process boundaries can be introduced later if independent scaling or reliability
requirements make them useful.
