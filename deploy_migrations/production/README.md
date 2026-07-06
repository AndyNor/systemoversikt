# Production migration transfer (archived)

**As of 2026-07-06:** Test and production have been squashed to `systemoversikt/migrations/0001_initial.py`. New schema changes are normal Django migrations in `systemoversikt/migrations/` — deploy with `manage.py migrate` (see `oslokommune/build.sh`). Do **not** copy files from this folder for new features.

## Current migrations (post-squash)

| File | Purpose |
|------|---------|
| `0001_initial.py` | Squashed baseline (all models through risk virksomhet groups, etc.) |
| `0002_risk_framework_layer.py` | Risk framework aggregation layer (`RiskFramework`, nodes, links, assessments) |

After deploy, on server:

```bash
python manage.py migrate systemoversikt
python manage.py seed_risk_framework_it_plattform   # first time only
python manage.py makemigrations systemoversikt --dry-run   # should report no changes
```

## Archived files below (pre-squash transfer only)

The `0458`–`0461` files were a one-off transfer when production migration history diverged from dev. They are kept for reference only if an environment still lists those numbers in `django_migrations`. Environments that have run the squash should **not** apply these.

| File | Purpose (historical) |
|------|----------------------|
| `0458_risk_participant_groups.py` | `virksomhet_read_only`, `participant_groups` |
| `0459_rename_risk_virksomhet_group.py` | Rename read-group models |
| `0460_alter_risk_virksomhet_group_related_names.py` | `related_name` on FK fields |
| `0461_risk_virksomhet_group_historical_meta.py` | Historical model verbose names |
