"""
ShopSphere ETL — Glue PySpark Job: Customer 360 + Feature Engineering
=====================================================================
MENAT Industry AI Accelerator | Retail Personalization Engine

Reads raw CSVs from S3, performs sessionization + feature engineering,
writes Iceberg tables to the Glue Catalog (lakehouse serving layer).

UAE-region note: Uses Iceberg on Glue Catalog (S3 Tables alternative) —
avoids Databricks (Azure-only in me-central-1) and gives open-format
interoperability. No DataZone/SMUS dependency (not yet in UAE).

Glue version: 4.0 (Spark 3.3, Iceberg 1.0+)
Job parameters:
  --raw_bucket      s3 bucket with raw CSVs (prefix: raw/)
  --warehouse       s3 path for Iceberg warehouse (prefix: lakehouse/)
  --database        Glue database name (default: shopsphere)
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ["JOB_NAME", "raw_bucket", "warehouse", "database"])
RAW = f"s3://{args['raw_bucket']}/raw"
WH = args["warehouse"]
DB = args["database"]

# ---- Iceberg-enabled Spark session ----
spark = (SparkContext().getOrCreate() and None) or None
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", WH)
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl",
               "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.io-impl",
               "org.apache.iceberg.aws.s3.S3FileIO")
spark.conf.set("spark.sql.extensions",
               "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

spark.sql(f"CREATE DATABASE IF NOT EXISTS glue_catalog.{DB}")

# ---- Load raw ----
customers = spark.read.option("header", True).csv(f"{RAW}/customers.csv")
catalog = spark.read.option("header", True).csv(f"{RAW}/catalog.csv")
clicks = spark.read.option("header", True).csv(f"{RAW}/clickstream.csv")
oh = spark.read.option("header", True).csv(f"{RAW}/order_headers.csv")
ol = spark.read.option("header", True).csv(f"{RAW}/order_lines.csv")

clicks = clicks.withColumn("event_timestamp", F.to_timestamp("event_timestamp"))
oh = (oh.withColumn("order_timestamp", F.to_timestamp("order_timestamp"))
        .withColumn("order_total", F.col("order_total").cast("double"))
        .withColumn("num_items", F.col("num_items").cast("int")))
ol = (ol.withColumn("quantity", F.col("quantity").cast("int"))
        .withColumn("line_total", F.col("line_total").cast("double")))

# ---- Behavioral features from clickstream ----
behav = (clicks.groupBy("customer_id").agg(
    F.countDistinct("session_id").alias("total_sessions"),
    F.count("*").alias("total_events"),
    F.sum(F.when(F.col("event_type") == "add_to_cart", 1).otherwise(0)).alias("add_to_cart_events"),
    F.sum(F.when(F.col("event_type") == "view", 1).otherwise(0)).alias("view_events"),
    F.sum(F.when(F.col("event_type") == "search", 1).otherwise(0)).alias("search_events"),
    F.max("event_timestamp").alias("last_active_ts"),
))

# top category per customer (affinity)
cat_counts = clicks.groupBy("customer_id", "category").count()
w = Window.partitionBy("customer_id").orderBy(F.desc("count"))
top_cat = (cat_counts.withColumn("rn", F.row_number().over(w))
           .filter(F.col("rn") == 1)
           .select("customer_id", F.col("category").alias("top_affinity_category")))

# ---- Monetary features from orders ----
mon = (oh.filter(F.col("status") == "completed").groupBy("customer_id").agg(
    F.count("*").alias("total_orders"),
    F.sum("order_total").alias("lifetime_spend"),
    F.avg("order_total").alias("avg_order_value"),
    F.max("order_timestamp").alias("last_order_ts"),
))

# ---- Assemble Customer 360 ----
c360 = (customers
        .join(behav, "customer_id", "left")
        .join(top_cat, "customer_id", "left")
        .join(mon, "customer_id", "left")
        .fillna({"total_orders": 0, "lifetime_spend": 0.0, "avg_order_value": 0.0,
                 "total_sessions": 0, "total_events": 0, "add_to_cart_events": 0}))

# conversion rate + RFM-style recency
ref_date = F.lit("2026-10-01").cast("timestamp")
c360 = (c360
    .withColumn("cart_conversion_rate",
                F.when(F.col("add_to_cart_events") > 0,
                       F.col("total_orders") / F.col("add_to_cart_events")).otherwise(0.0))
    .withColumn("recency_days",
                F.datediff(ref_date, F.col("last_order_ts")))
    .withColumn("is_active_90d",
                F.when(F.col("recency_days") <= 90, 1).otherwise(0)))

(c360.writeTo(f"glue_catalog.{DB}.customer_360")
     .using("iceberg").tableProperty("format-version", "2")
     .createOrReplace())

# ---- Product performance (for catalog + merchandising) ----
prod_perf = (ol.join(oh.filter(F.col("status") == "completed").select("order_id"), "order_id")
             .groupBy("product_id").agg(
                 F.sum("quantity").alias("units_sold"),
                 F.sum("line_total").alias("revenue"),
                 F.countDistinct("order_id").alias("orders_count")))
catalog_enriched = (catalog
    .withColumn("price", F.col("price").cast("double"))
    .withColumn("rating", F.col("rating").cast("double"))
    .join(prod_perf, "product_id", "left")
    .fillna({"units_sold": 0, "revenue": 0.0, "orders_count": 0}))
(catalog_enriched.writeTo(f"glue_catalog.{DB}.product_performance")
    .using("iceberg").tableProperty("format-version", "2").createOrReplace())

# ---- Interaction matrix for Redshift ML (customer x product affinity score) ----
# weight: view=1, add_to_cart=3, order=5
click_w = (clicks.withColumn("w",
            F.when(F.col("event_type") == "view", 1)
             .when(F.col("event_type") == "add_to_cart", 3)
             .when(F.col("event_type") == "wishlist", 2).otherwise(0))
           .groupBy("customer_id", "product_id").agg(F.sum("w").alias("click_score")))
order_w = (ol.join(oh.select("order_id", "customer_id"), "order_id")
           .groupBy("customer_id", "product_id").agg((F.sum("quantity") * 5).alias("order_score")))
interactions = (click_w.join(order_w, ["customer_id", "product_id"], "outer")
                .fillna(0)
                .withColumn("affinity_score", F.col("click_score") + F.col("order_score"))
                .join(catalog.select("product_id", "category"), "product_id", "left"))
(interactions.writeTo(f"glue_catalog.{DB}.customer_product_interactions")
    .using("iceberg").tableProperty("format-version", "2").createOrReplace())

print("ShopSphere Customer 360 ETL complete.")
print("Tables written: customer_360, product_performance, customer_product_interactions")
job.commit()
