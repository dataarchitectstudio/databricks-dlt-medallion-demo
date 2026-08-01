# Orders Medallion Demo (Lakeflow Declarative Pipelines / DLT)

A minimal Databricks pipeline demonstrating the medallion architecture
(Bronze → Silver → Gold) using the `dlt` Python API, with 10 rows of inline
dummy `orders` data — no external source needed.

## Layout

```
notebooks/
  orders_medallion_pipeline.py     # single notebook, all 3 layers
src/orders_medallion/              # Python package, packaged as a wheel
  main.py                          # summarize_revenue() / main() entry point
pyproject.toml                     # package metadata for the wheel build
databricks.yml                     # Databricks Asset Bundle root config (incl. artifacts:)
resources/
  orders_medallion_pipeline.yml    # DLT pipeline resource
  orders_medallion_job.yml         # scheduled job: runs the pipeline, then the wheel task
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
- **orders_medallion (wheel package)** — `src/orders_medallion/main.py` reads
  the two gold tables and prints a revenue summary. Packaged as a wheel via
  `pyproject.toml` and run as a `python_wheel_task` in the job, right after
  the DLT pipeline finishes. See "Packaging Python logic as a wheel" below.

## Deploying to Databricks

Deployment is managed by a [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/bundles/index.html)
(`databricks.yml` + `resources/`), which defines the DLT pipeline, the
`orders_medallion` wheel, and the job that runs both on a daily schedule, as
code.

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
   This uploads the notebook, builds and uploads the `orders_medallion`
   wheel, and creates/updates the pipeline and job.
3. Trigger a run from the Databricks UI (Workflows → Pipelines), or:
   ```
   databricks bundle run orders_medallion_demo_every_day --target prod
   ```

### Packaging Python logic as a wheel

`src/orders_medallion/` is a regular Python package (`pyproject.toml` at the
repo root, sources under `src/`). It's not deployed as loose files — the
bundle packages it as a wheel and runs it as a job task:

- **`databricks.yml`** declares an `artifacts:` entry (`orders_medallion`,
  `type: whl`) with a `build:` command
  (`python3 -m pip wheel . -w dist --no-deps`). On `bundle deploy`, the CLI
  runs that command locally/in CI, then uploads the resulting
  `dist/orders_medallion-0.1.0-py3-none-any.whl` to the workspace — the
  wheel itself is never committed to git (`dist/`, `build/`, `*.egg-info/`
  are gitignored).
- **`resources/orders_medallion_job.yml`** adds a `summarize_revenue` task
  (`depends_on` the pipeline task) with a `python_wheel_task` pointing at
  `package_name: orders_medallion`, `entry_point: main`. Since this job runs
  on serverless compute, the wheel is attached via a job-level
  `environments:` block (`environment_key: default`,
  `dependencies: [../dist/*.whl]`) rather than a cluster-level `libraries:`
  list.
- The task calls `orders_medallion.main:main()`, which reads
  `gold_revenue_by_product` / `gold_revenue_by_customer` and prints a
  summary — demonstrating shared/reusable logic that lives outside the DLT
  notebook and can be unit tested independently.

To add more reusable logic, drop new modules under
`src/orders_medallion/`, add an entry point if needed, and reference it from
a task's `python_wheel_task` — no changes to the `artifacts:` build command
are required.

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
