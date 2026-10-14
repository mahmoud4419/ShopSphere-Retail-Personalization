-- =====================================================================
-- ShopSphere — Redshift Serving Layer: COPY loads from S3
-- MENAT Industry AI Accelerator | Retail Personalization Engine
-- =====================================================================
-- Loads the Glue/Iceberg ETL outputs into Redshift Serverless as the
-- serving layer. QuickSight uses DIRECT QUERY on Redshift (NOT SPICE)
-- so the dashboard reflects new data immediately after each Glue run —
-- avoids SPICE refresh limits (32 full refreshes / 24h, etc.).
--
-- Pattern: Glue writes CSV/Parquet to S3 -> Redshift COPY from S3
-- (simpler than the Spark-Redshift connector for time-boxed demos).
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS shopsphere;

-- ---- Customer 360 -----------------------------------------------------
DROP TABLE IF EXISTS customer_360;
CREATE TABLE customer_360 (
    customer_id            VARCHAR(20),
    signup_date            VARCHAR(12),
    loyalty_tier           VARCHAR(12),
    age_band               VARCHAR(10),
    gender                 VARCHAR(2),
    city_zone              VARCHAR(32),
    preferred_language     VARCHAR(4),
    email_opt_in           INT,
    total_sessions         BIGINT,
    total_events           BIGINT,
    add_to_cart_events     BIGINT,
    view_events            BIGINT,
    search_events          BIGINT,
    top_affinity_category  VARCHAR(32),
    total_orders           BIGINT,
    lifetime_spend         DOUBLE PRECISION,
    avg_order_value        DOUBLE PRECISION,
    cart_conversion_rate   DOUBLE PRECISION,
    recency_days           INT,
    is_active_90d          INT
);
COPY customer_360 FROM 's3://<YOUR_WAREHOUSE_BUCKET>/serving/customer_360/'
IAM_ROLE 'arn:aws:iam::<ACCOUNT_ID>:role/<RedshiftCopyRole>'
FORMAT AS PARQUET;

-- ---- Product performance ---------------------------------------------
DROP TABLE IF EXISTS product_performance;
CREATE TABLE product_performance (
    product_id      VARCHAR(20),
    product_name    VARCHAR(128),
    category        VARCHAR(32),
    subcategory     VARCHAR(48),
    brand           VARCHAR(32),
    price           DOUBLE PRECISION,
    rating          DOUBLE PRECISION,
    num_reviews     INT,
    in_stock        INT,
    color           VARCHAR(16),
    is_new_arrival  INT,
    units_sold      BIGINT,
    revenue         DOUBLE PRECISION,
    orders_count    BIGINT
);
COPY product_performance FROM 's3://<YOUR_WAREHOUSE_BUCKET>/serving/product_performance/'
IAM_ROLE 'arn:aws:iam::<ACCOUNT_ID>:role/<RedshiftCopyRole>'
FORMAT AS PARQUET;

-- ---- Interactions -----------------------------------------------------
DROP TABLE IF EXISTS customer_product_interactions;
CREATE TABLE customer_product_interactions (
    customer_id     VARCHAR(20),
    product_id      VARCHAR(20),
    click_score     BIGINT,
    order_score     BIGINT,
    affinity_score  BIGINT,
    category        VARCHAR(32)
);
COPY customer_product_interactions FROM 's3://<YOUR_WAREHOUSE_BUCKET>/serving/interactions/'
IAM_ROLE 'arn:aws:iam::<ACCOUNT_ID>:role/<RedshiftCopyRole>'
FORMAT AS PARQUET;

-- Verify row counts
-- SELECT 'customer_360' t, COUNT(*) FROM customer_360
-- UNION ALL SELECT 'product_performance', COUNT(*) FROM product_performance
-- UNION ALL SELECT 'interactions', COUNT(*) FROM customer_product_interactions;
