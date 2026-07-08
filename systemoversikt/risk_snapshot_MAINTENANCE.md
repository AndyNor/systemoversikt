# Risk snapshot maintenance

This document explains how to keep the **risk snapshot** feature working when the risk domain model or the live risk UI changes.

Snapshots are **read-only archives** of two live views:

| Live page | Snapshot list | Snapshot detail |
|-----------|---------------|-----------------|
| Collection rapport (`/sikkerhet/risiko/collection/<pk>/rapport/`) | `/sikkerhet/risiko/collection/<pk>/snapshot/` | `.../snapshot/<uuid>/rapport/` |
| Sammenstilling detail (`/sikkerhet/risiko/rammeverk/sammenstilling/<pk>/`) | `/sikkerhet/risiko/rammeverk/sammenstilling/<pk>/snapshot/` | `.../snapshot/<uuid>/` |

Each snapshot stores **compact JSON** plus metadata in `RiskSnapshot`. HTML is rendered later from **versioned templates** under `templates/risk_snapshots/v<N>/`. Omfang figures are **not** copied into snapshots; the snapshot template still loads the image from the **live** `RiskScope` file URL when present.

Daily capture: `python manage.py risk_snapshot_capture` (optionally `--dry-run`).

---

## How the pieces fit together

```
Live DB  →  serializer (risk_snapshot.py)  →  JSON payload  →  RiskSnapshot row
                                                              ↓
Live permission check  →  render_context  →  templates/risk_snapshots/v<N>/…  →  HTML
```

Two independent version numbers are stored on every snapshot row:

| Field | Constant (current) | Purpose |
|-------|-------------------|---------|
| `template_version` | `RISK_SNAPSHOT_TEMPLATE_VERSION` in `models.py` | Selects HTML template directory `risk_snapshots/v<N>/` |
| `json_schema_version` | `RISK_SNAPSHOT_JSON_SCHEMA_VERSION` in `models.py` | Documents the JSON payload shape produced by the serializer |

**Old snapshots never change version.** When captured, they record the versions active at capture time. The detail view uses `snapshot.template_version` to pick the template; the payload inside the row is fixed.

---

## Decision guide: what to change

Use this when you modify risk collections, sammenstillinger, rapport layout, or related helpers.

### 1. Live-only change (no impact on archived snapshots)

Examples: edit buttons, kartlegging links, API routes, access-control logic on the **editable** detail page.

**Do:** Change live views/templates only (`risiko_scope_rapport.html`, `risiko_sammenstilling_detail.html`, `views_risiko.py`, etc.).

**Do not** bump snapshot versions. Existing snapshots correctly show the old layout.

### 2. Display tweak that should apply to **new** snapshots only

Examples: CSS spacing, wording, reorder sections without new data fields.

**Do:**

1. Update the **live** template.
2. Update the **current** snapshot template copy: `templates/risk_snapshots/v1/…` (or whatever `RISK_SNAPSHOT_TEMPLATE_VERSION` is).
3. Leave older `v0`, `v1`, … directories untouched if you have already bumped the version before.

**Do not** bump `template_version` unless you intentionally want to fork HTML history (see §4).

### 3. New or changed **data** shown on the rapport / sammenstilling

Examples: new scenario field, new tiltak column, new rollup tree section, renamed status labels.

**Do:**

1. Extend the serializer in `risk_snapshot.py`:
   - Collection: `build_collection_snapshot_payload()` and helpers (`_serialize_scenario`, `_serialize_action`, …).
   - Sammenstilling: `build_sammenstilling_snapshot_payload()` and `_serialize_rollup_tree` / `_serialize_sammenstilling_matrix`.
2. Precompute **display strings and CSS classes in JSON**. Snapshot templates must not call `get_*_display()` or filters that need live `User` / model instances.
3. Update `collection_render_context()` / `sammenstilling_render_context()` if templates need new top-level context keys.
4. Update the **current** snapshot template under `risk_snapshots/v<N>/`.
5. Update the live template to match (if the live page should show the same field).

**Bump `json_schema_version`** when the payload shape changes in a way that old render code cannot ignore safely (new required keys, renamed keys, changed types). Increment `RISK_SNAPSHOT_JSON_SCHEMA_VERSION` in `models.py` and include the new version in newly captured payloads.

**Backward compatibility:** If old snapshots must keep rendering after a schema change, either:

- keep supporting the old keys in `*_render_context()` and templates (branch on `snapshot.json_schema_version`), or
- accept that only snapshots captured **after** the change show the new field (old rows simply lack the data).

### 4. Layout or markup redesign (historical HTML must be preserved)

Examples: new report sections, different matrix markup, switch from tables to cards.

**Do:**

1. **Increment** `RISK_SNAPSHOT_TEMPLATE_VERSION` in `models.py`.
2. **Copy** the previous template directory to the new version, e.g. `v1/` → `v2/`, then edit **only** `v2/`.
3. Update serializers / `*_render_context()` for anything the new templates need.
4. New captures automatically store the new `template_version`; old rows still render with `v1/`.

Never edit `risk_snapshots/v1/` for a redesign intended to apply only going forward—fork to `v2/` instead.

### 5. Risk **model** or database schema change

Examples: new `RiskScenario` field, changed choices on `RiskAction.status`, new M2M, renamed relations.

**Do:**

1. Migrations as usual for live functionality.
2. Update live views and report builders (`views_risiko.py`, `risk_report.py`, `risk_framework.py`, …).
3. Update snapshot serializers to read the new model shape and **serialize display values into JSON**.
4. Follow §3 or §4 depending on whether HTML layout changes.
5. Run `risk_snapshot_capture --dry-run` and fix any serializer errors before deploy.

Snapshots do **not** auto-migrate when models change. Rows already stored keep their JSON forever.

### 6. Criteria / matrix label changes

Matrix colours and axis labels come from `get_active_criteria()` at **capture** time and are stored in the payload (`konsekvens_labels`, per-cell `css_class`, scenario labels). Changing criteria later does not rewrite old snapshots—which is usually what you want for an archive.

If you change how criteria are computed, only **new** captures reflect it.

### 7. Permission changes

Snapshot views always check access against the **live** `RiskScope` / `RiskSammenstilling` (`_has_scope_read_access`, `user_can_view_sammenstilling`). Update `views_risk_snapshot.py` only if the rule for “who may see this object” changes.

---

## Files to know

| Area | Files |
|------|--------|
| Model + version constants | `systemoversikt/models.py` (`RiskSnapshot`, `RISK_SNAPSHOT_*`) |
| Capture + serialize + retention | `systemoversikt/risk_snapshot.py` |
| Nightly job | `systemoversikt/management/commands/risk_snapshot_capture.py` |
| Read-only views | `systemoversikt/views_risk_snapshot.py` |
| URLs | `systemoversikt/urls.py` |
| Snapshot list (unversioned) | `templates/risk_snapshots/risiko_snapshot_list.html` |
| Versioned detail templates | `templates/risk_snapshots/v1/risiko_scope_rapport.html`, `…/risiko_sammenstilling_detail.html`, `…/_risiko_rapport_styles.html` |
| Live pages (entry links) | `templates/risiko_scope_rapport.html`, `templates/risiko_sammenstilling_detail.html` |
| Live rapport logic to mirror | `views_risiko._build_rapport_context`, `risk_report.py`, `risk_framework.py` |

Template path helper: `snapshot_template_name(version, 'risiko_scope_rapport.html')` → `risk_snapshots/v1/risiko_scope_rapport.html`.

---

## Snapshot template rules

1. **Use payload dicts only** — fields like `scenario.status_display`, `owners_display`, `action.ansvarlig_display`.
2. **No edit affordances** — no kartlegging, mapping, or POST forms (snapshot views are GET-only).
3. **Omfang image** — uses live URL via `omfang_fil.scope_pk`; if the file is deleted later, the snapshot may show a broken image. That is intentional (no file copies in JSON).
4. **Shared partials** — e.g. `risiko_matrise_grid.html` may be included if the JSON provides the attributes the partial expects in `report_mode`.

---

## Retention and deduplication (usually no maintenance)

- **Dedup:** A new row is skipped if SHA-256 of normalized JSON matches the latest snapshot for the same `source_type` + `source_pk`.
- **Retention:** After each save, `prune_snapshots_for_source()` keeps one snapshot per time bin (daily ×7, weekly ×3 months, monthly ×1 year, yearly older). Constants: `_RETENTION_*_DAYS` in `risk_snapshot.py`.

Change retention only if product owners ask; it affects storage, not rendering.

---

## Checklist before merge/deploy

1. `python manage.py check`
2. `python manage.py risk_snapshot_capture --dry-run`
3. Open a **live** rapport and sammenstilling — confirm layout still correct.
4. Capture or pick an existing snapshot — open **Historikk / versjoner** and confirm detail pages render.
5. If you bumped `template_version`, confirm an **old** snapshot still opens (uses `v1/`, not `v2/`).
6. If you bumped `json_schema_version`, confirm an **old** snapshot still opens (or document that it requires a one-off fix).

---

## Quick reference: bumping versions

**New JSON fields (same HTML):**

```python
# models.py
RISK_SNAPSHOT_JSON_SCHEMA_VERSION = 2  # was 1
```

Update serializers; optionally branch in `*_render_context()` for schema 1 vs 2.

**New HTML layout (same or new JSON):**

```python
# models.py
RISK_SNAPSHOT_TEMPLATE_VERSION = 2  # was 1
```

Copy `templates/risk_snapshots/v1/` → `v2/`, edit `v2/` only. Serializers already set `template_version` from the constant.

Both bumps can be done together when a feature needs new data **and** new markup.
