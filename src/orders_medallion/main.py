from pyspark.sql import SparkSession


def summarize_revenue(catalog: str = "workspace", schema: str = "dlt_demo") -> None:
    spark = SparkSession.getActiveSession()
    if spark is None:
        raise RuntimeError(
            "summarize_revenue must run on a Databricks cluster with an active Spark session."
        )

    print("Top products by revenue:")
    spark.table(f"{catalog}.{schema}.gold_revenue_by_product").limit(5).show(truncate=False)

    print("Top customers by spend:")
    spark.table(f"{catalog}.{schema}.gold_revenue_by_customer").limit(5).show(truncate=False)


def main() -> None:
    summarize_revenue()


if __name__ == "__main__":
    main()
