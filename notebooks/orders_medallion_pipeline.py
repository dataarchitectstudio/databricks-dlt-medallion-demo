# Databricks notebook source
# MAGIC %md
# MAGIC # Orders Medallion Pipeline (Bronze → Silver → Gold)
# MAGIC
# MAGIC Demo Lakeflow Declarative Pipelines (DLT) notebook. Uses inline dummy `orders`
# MAGIC data (10 records, including a couple of intentionally messy rows) so the whole
# MAGIC pipeline runs standalone with no external source configured.
# MAGIC
# MAGIC To run: create a Pipeline in Databricks Workflows (or use `databricks.yml` /
# MAGIC `pipeline_settings.json` in this repo) pointing at this notebook as the source.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, IntegerType, StringType, DoubleType
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze layer
# MAGIC Raw data, ingested as-is. Row 5 has a null `customer_id`, row 8 has a negative
# MAGIC `quantity` — both get caught by data quality expectations in the silver layer.

# COMMAND ----------

@dlt.table(
    name="bronze_orders",
    comment="Raw orders data ingested as-is (dummy demo data)."
)
def bronze_orders():
    data = [
        (1,  "C001", "Laptop",      1,  1200.00, "2026-07-01", "COMPLETED"),
        (2,  "C002", "Mouse",       2,    25.50, "2026-07-02", "COMPLETED"),
        (3,  "C003", "Keyboard",    1,    45.00, "2026-07-02", "PENDING"),
        (4,  "C001", "Monitor",     2,   300.00, "2026-07-03", "COMPLETED"),
        (5,  None,   "Laptop",      1,  1150.00, "2026-07-03", "CANCELLED"),
        (6,  "C004", "Headphones",  3,    60.00, "2026-07-04", "COMPLETED"),
        (7,  "C005", "Mouse",       1,    25.50, "2026-07-04", "COMPLETED"),
        (8,  "C002", "Keyboard",   -1,    45.00, "2026-07-05", "COMPLETED"),
        (9,  "C006", "Monitor",     1,   300.00, "2026-07-05", "PENDING"),
        (10, "C003", "Laptop",      1,  1200.00, "2026-07-06", "COMPLETED"),
    ]
    schema = StructType([
        StructField("order_id",    IntegerType(), True),
        StructField("customer_id", StringType(),  True),
        StructField("product",     StringType(),  True),
        StructField("quantity",    IntegerType(), True),
        StructField("unit_price",  DoubleType(),  True),
        StructField("order_date",  StringType(),  True),
        StructField("status",      StringType(),  True),
    ])
    return (
        spark.createDataFrame(data, schema)
        .withColumn("_ingested_at", F.current_timestamp())
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver layer
# MAGIC Cleaned and validated. Bad rows are dropped via `expect_or_drop`, price is
# MAGIC flagged (not dropped) via `expect`, and a `total_amount` column is derived.

# COMMAND ----------

@dlt.table(
    name="silver_orders",
    comment="Cleaned, validated orders with derived total_amount."
)
@dlt.expect_or_drop("valid_customer", "customer_id IS NOT NULL")
@dlt.expect_or_drop("valid_quantity", "quantity > 0")
@dlt.expect("valid_price", "unit_price > 0")
def silver_orders():
    return (
        dlt.read("bronze_orders")
        .withColumn("order_date", F.to_date("order_date"))
        .withColumn("total_amount", F.round(F.col("quantity") * F.col("unit_price"), 2))
        .dropDuplicates(["order_id"])
        .select(
            "order_id", "customer_id", "product", "quantity",
            "unit_price", "total_amount", "order_date", "status"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold layer
# MAGIC Business-level aggregates for completed orders: revenue by product and by
# MAGIC customer.

# COMMAND ----------

@dlt.table(
    name="gold_revenue_by_product",
    comment="Revenue, units sold, and distinct customers per product (completed orders only)."
)
def gold_revenue_by_product():
    return (
        dlt.read("silver_orders")
        .filter(F.col("status") == "COMPLETED")
        .groupBy("product")
        .agg(
            F.sum("total_amount").alias("total_revenue"),
            F.sum("quantity").alias("total_units_sold"),
            F.countDistinct("customer_id").alias("distinct_customers"),
        )
        .orderBy(F.desc("total_revenue"))
    )

# COMMAND ----------

@dlt.table(
    name="gold_revenue_by_customer",
    comment="Total spend and order count per customer (completed orders only)."
)
def gold_revenue_by_customer():
    return (
        dlt.read("silver_orders")
        .filter(F.col("status") == "COMPLETED")
        .groupBy("customer_id")
        .agg(
            F.sum("total_amount").alias("total_spent"),
            F.count("order_id").alias("num_orders"),
        )
        .orderBy(F.desc("total_spent"))
    )
