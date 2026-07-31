# Orders Medallion Demo (Lakeflow Declarative Pipelines / DLT)

A minimal Databricks pipeline demonstrating the medallion architecture
(Bronze → Silver → Gold) using the `dlt` Python API, with 10 rows of inline
dummy `orders` data — no external source needed.

## Layout

```
notebooks/
  orders_medallion_pipeline.py     # single notebook, all 3 layers
databricks.yml                     # Databricks Asset Bundle root config
resources/
  orders_medallion_pipeline.yml    # DLT pipeline resource
  orders_medallion_job.yml         # scheduled job resource (every 5 min)
.github/workflows/
  databricks-ci.yml                # validates the bundle on every PR
  databricks-cd.yml                # deploys the bundle on merge to main
```

## What it does

- **bronze_orders** — raw 10-row orders dataset as-is (includes 2 intentionally
  bad rows: one with a null `customer_id`, one with a negative `quantity`).
- **silver_orders** — cleans the data using DLT expectations
  (`expect_or_drop` for customer/quantity validity, `expect` to just flag bad
  prices without dropping them), casts `order_date`, and derives
  `total_amount`.
- **gold_revenue_by_product** / **gold_revenue_by_customer** — business
  aggregates (revenue, units, order counts) over completed orders only.

## Deploying to Databricks

Deployment is managed by a [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/bundles/index.html)
(`databricks.yml` + `resources/`), which defines the DLT pipeline and its
5-minute schedule as code.

### Manual / local deploy

The bundle doesn't hardcode a workspace host — it's picked up from your
active auth (OAuth profile or `DATABRICKS_HOST`/`DATABRICKS_TOKEN` env vars),
so the same `databricks.yml` works locally and in CI without editing.

1. Authenticate with OAuth (no tokens needed):
   ```
   databricks auth login --host <your-workspace-url>
   ```
2. Validate and deploy:
   ```
   databricks bundle validate --target prod
   databricks bundle deploy --target prod
   ```
   This uploads the notebook and creates/updates the pipeline and job.
3. Trigger a run from the Databricks UI (Workflows → Pipelines), or:
   ```
   databricks bundle run orders_medallion_demo_every_5min --target prod
   ```

### CI/CD (GitHub Actions)

- **`.github/workflows/databricks-ci.yml`** — on every pull request into
  `main`, runs `databricks bundle validate` to catch config errors before
  merge.
- **`.github/workflows/databricks-cd.yml`** — on every push to `main` (i.e.
  right after a PR is merged), runs `databricks bundle deploy --target prod`
  to roll the change out to the workspace.

Both workflows authenticate to Databricks with a personal access token (PAT)
generated **for a service principal** (not a human user), read from GitHub
Actions repository secrets — never committed or pasted anywhere:

| Secret | Value |
|---|---|
| `DATABRICKS_HOST` | Your workspace URL, e.g. `https://<workspace>.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | PAT generated for the service principal |

To set this up:

1. In the Databricks workspace UI: **Settings → Identity and access →
   Service principals → Add service principal**, e.g.
   `github-actions-dlt-medallion`.
2. Grant it permission to manage the target catalog/schema and to
   create/manage DLT pipelines and jobs.
3. Open the service principal → generate a PAT for it (workspace admin →
   service principal → **Tokens** → **Generate new token**). Copy it
   immediately — it's shown once.
4. Add the two values above as secrets on the GitHub repo (Settings →
   Secrets and variables → Actions), or via the `gh` CLI:
   ```
   gh secret set DATABRICKS_HOST
   gh secret set DATABRICKS_TOKEN
   ```
   (`gh secret set` prompts for the value locally and uploads it encrypted —
   it's never printed or stored in shell history.)
5. (Recommended) In GitHub repo Settings → Environments, create a
   `production` environment and add required reviewers, so every deploy
   needs manual approval.
6. Set an expiry/rotation reminder for the PAT — unlike OAuth M2M tokens,
   it doesn't auto-refresh and will silently start failing deploys once it
   expires.

With this in place: open a PR → CI validates the bundle → merge the PR into
`main` → CD deploys automatically to Databricks.
