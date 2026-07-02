# Production migration transfer

These files are **not** used by local `manage.py migrate`. Copy all four to the server:

`systemoversikt/migrations/`

## When

- `0457_riskvirksomhetreadgroup_and_more` is applied (create read-group tables only)
- Broken `0458_historical…` file is deleted
- Current application code (RiskVirksomhetGroup, participant_groups, etc.) is deployed

## Files (apply in order)

| File | Dev equivalent | Purpose |
|------|----------------|---------|
| `0458_risk_participant_groups.py` | 0220 | `virksomhet_read_only`, `participant_groups`, data migration |
| `0459_rename_risk_virksomhet_group.py` | 0221 | Rename all four models, constraints, M2M target |
| `0460_alter_risk_virksomhet_group_related_names.py` | 0222 | `related_name` on FK fields |
| `0461_risk_virksomhet_group_historical_meta.py` | 0223 | Historical model verbose names |

## Commands on server

```bash
python manage.py migrate --plan
python manage.py migrate systemoversikt
python manage.py makemigrations systemoversikt --dry-run
```

After migrate, `makemigrations --dry-run` should report **No changes detected**.

## Verify before migrate

```bash
python manage.py sqlmigrate systemoversikt 0458
python manage.py sqlmigrate systemoversikt 0459
```

0458 should add columns/M2M; 0459 should rename tables (no DROP of group tables).
