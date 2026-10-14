# ShopSphere — Setup Guide

Step-by-step deployment of the Retail Personalization Engine demo in
**AWS me-central-1 (UAE)**. Target build time: ~2 hours.

## Prerequisites

- AWS account with access to: S3, Glue, Athena, Redshift Serverless,
  QuickSight, Amazon Bedrock, S3 Vectors.
- **Bedrock model access** enabled for:
  - `amazon.titan-embed-text-v2:0` (embeddings)
  - `amazon.nova-pro-v1:0` (or an in-region Claude model) for the agent
- Python 3.10+ with `boto3` and `pandas`.
- An IAM role for Redshift with:
  - `s3:GetObject` on your buckets (for COPY)
  - `sagemaker:*` (wildcard) — **required** by Redshift ML
  - Glue Catalog read (if querying Iceberg from Redshift Spectrum)

---

## Step 1 — Generate synthetic data

```bash
cd data_generators
python generate_data.py --out ./output --customers 5000 --days 90
```

Produces: `customers.csv`, `catalog.csv`, `clickstream.csv`,
`order_headers.csv`, `order_lines.csv`.

## Step 2 — Upload raw data to S3

```bash
export RAW_BUCKET=shopsphere-raw-<acct>
export WH_BUCKET=shopsphere-lakehouse-<acct>
aws s3 mb s3://$RAW_BUCKET --region me-central-1
aws s3 mb s3://$WH_BUCKET --region me-central-1
aws s3 cp data_generators/output/ s3://$RAW_BUCKET/raw/ --recursive
```

## Step 3 — Run the Glue ETL (Customer 360 → Iceberg)

Create a Glue 4.0 PySpark job from `etl/glue_etl_customer360.py` with job
parameters:

| Key | Value |
|-----|-------|
| `--raw_bucket` | `shopsphere-raw-<acct>` |
| `--warehouse` | `s3://shopsphere-lakehouse-<acct>/lakehouse/` |
| `--database` | `shopsphere` |

Enable the Iceberg job parameter: `--datalake-formats iceberg`.

Outputs three Iceberg tables in the `shopsphere` Glue database:
`customer_360`, `product_performance`, `customer_product_interactions`.

> Inspect them in Athena using `etl/iceberg_ddl_athena.sql` as reference
> (Athena/Trino DDL — note the syntax differs from Spark SQL).

## Step 4 — Load the Redshift serving layer

1. Create a Redshift Serverless workgroup (`shopsphere-wg`) in me-central-1.
2. Export the Iceberg tables to Parquet under `s3://$WH_BUCKET/serving/...`
   (a small Glue/Athena `UNLOAD` or `CTAS` step), **or** point COPY at the
   Iceberg data files directly.
3. Edit `ml/redshift_load.sql` — replace `<YOUR_WAREHOUSE_BUCKET>`,
   `<ACCOUNT_ID>`, `<RedshiftCopyRole>` — and run it.

## Step 5 — Train the Redshift ML recommendation model

Edit `ml/redshift_ml_recommendations.sql`:
- replace `<ACCOUNT_ID>`, `<RedshiftMLRole>`, `<YOUR_REDSHIFTML_BUCKET>`.

Run sections in order:
1. Build `ml_training_set` (confirm ≥ 500 rows).
2. `CREATE MODEL ss_reco` (async — poll with `SHOW MODEL ss_reco`).
3. Smoke-test `fn_predict_category_propensity` with `LIMIT 1`.
4. Build `customer_category_scores` → `customer_recommendations`.

**Gotchas honored** (do not change): no `S3_OUTPUT_PATH`, short model name,
`sagemaker:*` wildcard IAM, ≥500 training rows.

## Step 6 — Build product embeddings (S3 Vectors)

```bash
# create an S3 Vectors bucket + index (1024-dim, cosine) named shopsphere-products
python ml/build_product_embeddings.py \
    --catalog data_generators/output/catalog.csv \
    --vector-bucket shopsphere-vectors-<acct> \
    --index shopsphere-products \
    --region me-central-1
# add --dry-run to test embedding without writing vectors
```

## Step 7 — QuickSight dashboard (optional live version)

- Add Redshift Serverless as a QuickSight data source.
- Create datasets on `customer_360`, `product_performance`,
  `customer_recommendations` using **Direct Query** (not SPICE).
- Build visuals for GMV trend, conversion funnel, category revenue, tier
  GMV/AOV. The included `dashboard/shopsphere_dashboard.html` mirrors this
  layout for an offline demo.

## Step 8 — Run the agent

```bash
# edit agent/shopping_agent.py __main__ with your vector bucket + workgroup
python agent/shopping_agent.py
```

The agent detects AR/EN, calls `search_products` (S3 Vectors),
`get_recommendations` and `get_customer_profile` (Redshift Data API), and
responds in the shopper's language.

---

## Teardown

```bash
aws s3 rb s3://$RAW_BUCKET --force
aws s3 rb s3://$WH_BUCKET --force
# delete Redshift workgroup, Glue job, QuickSight datasets, S3 Vectors index
```
