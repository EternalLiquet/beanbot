# Self-role menus

Beanbot's self-role feature is a vertical slice under
`src/beanbot/features/role_menus/`:

- `models.py` defines the versioned Mongo document model and emoji-key normalization.
- `repository.py` owns MongoDB queries and indexes.
- `service.py` contains Discord-independent role toggling plus legacy reaction handling.
- `views.py` defines the persistent Discord role picker and administrator setup UI.
- `cog.py` wires commands, views, storage, and Discord events together.

New menus use Discord components. An administrator runs `%rolesetting [label]`, selects up to 20
roles at once, and Beanbot publishes a persistent multi-select. A member can then toggle several
roles in one interaction.

## Storage

Runtime configuration defaults to the new `BeanBotPythonDB.roleMenus` namespace. The C# bot's
`BeanBotDB.roleSettings` collection is not opened by the runtime feature and is never mutated by
the migration.

Each target document has a `schema_version`, a `menu_type`, Discord location IDs, a label, and an
ordered `roles` array. New component menus use `menu_type: "select"`. Migrated messages use
`menu_type: "reaction"` and retain a canonical emoji key so their existing reactions continue to
work.

Canonical emoji keys are either `custom:<discord-id>` or `name:<emoji-name-or-unicode>`. The
migration accepts both legacy `emojiId` and `emojiKey` fields.

## Migration procedure

1. Back up `BeanBotDB` using the normal MongoDB backup process.
2. Stop the C# bot so role-setting documents do not change during the copy.
3. Run the default dry run:

   ```powershell
   python -m beanbot.migrations.migrate_role_settings
   ```

4. Confirm `invalid` and `conflicts` are both zero.
5. Apply the copy:

   ```powershell
   python -m beanbot.migrations.migrate_role_settings --apply
   ```

6. Run the dry run again. Every valid document should now appear as `already migrated`.
7. Start the Python bot and verify one migrated reaction message and one newly created select menu.

Apply mode performs a complete preflight before its first write. Invalid source documents or
target message conflicts abort all planned inserts. The legacy database remains the rollback
source; deleting the new `BeanBotPythonDB` database does not affect it.
