# Orders Medallion Demo (Lakeflow Declarative Pipelines / DLT)

A minimal Databricks pipeline demonstrating the medallion architecture
(Bronze → Silver → Gold) using the `dlt` Python API, with 10 rows of inline
dummy `orders` data — no external source needed.

## Layout

```
notebooks/
  orders_medallion_pipeline.py   # single notebook, all 3 layers
pipeline_settings.json           # example DLT pipeline config
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

1. Authenticate with OAuth (no tokens needed):
   ```
   databricks auth login --host <your-workspace-url>
   ```
2. Import the notebook into your workspace, e.g.:
   ```
   databricks workspace import ./notebooks/orders_medallion_pipeline.py \
     /Workspace/Users/<your-databricks-username>/databricks-dlt-medallion-demo/notebooks/orders_medallion_pipeline \
     --language PYTHON --format SOURCE
   ```
3. Update the `notebook.path` in `pipeline_settings.json` to match your
   workspace path, then create the pipeline:
   ```
   databricks pipelines create --json @pipeline_settings.json
   ```
4. Trigger a run from the Databricks UI (Workflows → Pipelines) or via
   `databricks pipelines start-update --pipeline-id <id>`.

Alternatively, just paste the notebook contents directly into a new notebook
in the Databricks workspace UI and attach it to a new DLT pipeline — no CLI
needed.
