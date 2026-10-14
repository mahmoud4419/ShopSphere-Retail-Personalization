#!/usr/bin/env python3
"""
ShopSphere — Semantic Product Search: Build Embeddings (S3 Vectors)
===================================================================
MENAT Industry AI Accelerator | Retail Personalization Engine

Generates product embeddings with Amazon Titan Text Embeddings (Bedrock)
and stores them in Amazon S3 Vectors — the UAE-region (me-central-1)
alternative to Bedrock Knowledge Bases (NOT available in UAE).

This powers:
  * Semantic product search ("comfy running shoes for flat feet")
  * The shopping agent's retrieval tool (grounded product grounding)
  * Multimodal story: swap Titan Text for Titan Multimodal to add image search

Prereqs:
    pip install boto3
    Bedrock model access: amazon.titan-embed-text-v2:0
    An S3 Vectors bucket + index (see Setup_Guide.md)
"""
import argparse
import csv
import json
import time
import boto3

REGION = "me-central-1"  # UAE
EMBED_MODEL = "amazon.titan-embed-text-v2:0"
EMBED_DIM = 1024


def product_to_text(row):
    """Compose a rich text document per product for embedding."""
    return (
        f"{row['product_name']}. Category: {row['category']} > {row['subcategory']}. "
        f"Brand: {row['brand']}. Color: {row['color']}. "
        f"Price: {row['price']}. Rating: {row['rating']} from {row['num_reviews']} reviews. "
        f"{'New arrival. ' if row.get('is_new_arrival') == '1' else ''}"
    )


def embed_text(bedrock, text):
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text, "dimensions": EMBED_DIM, "normalize": True}),
    )
    return json.loads(resp["body"].read())["embedding"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True, help="path to catalog.csv")
    ap.add_argument("--vector-bucket", required=True, help="S3 Vectors bucket name")
    ap.add_argument("--index", default="shopsphere-products", help="S3 Vectors index name")
    ap.add_argument("--region", default=REGION)
    ap.add_argument("--dry-run", action="store_true", help="embed only, skip S3 Vectors put")
    args = ap.parse_args()

    bedrock = boto3.client("bedrock-runtime", region_name=args.region)
    s3vectors = None if args.dry_run else boto3.client("s3vectors", region_name=args.region)

    with open(args.catalog, encoding="utf-8") as f:
        products = list(csv.DictReader(f))

    print(f"Embedding {len(products)} products with {EMBED_MODEL} ...")
    batch = []
    for i, row in enumerate(products, 1):
        text = product_to_text(row)
        vec = embed_text(bedrock, text)
        batch.append({
            "key": row["product_id"],
            "data": {"float32": vec},
            "metadata": {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "category": row["category"],
                "subcategory": row["subcategory"],
                "brand": row["brand"],
                "price": float(row["price"]),
                "rating": float(row["rating"]),
                "text": text,
            },
        })
        if len(batch) >= 100 and not args.dry_run:
            s3vectors.put_vectors(vectorBucketName=args.vector_bucket,
                                  indexName=args.index, vectors=batch)
            print(f"  upserted {i} products")
            batch = []
        if i % 50 == 0:
            print(f"  embedded {i}/{len(products)}")
    if batch and not args.dry_run:
        s3vectors.put_vectors(vectorBucketName=args.vector_bucket,
                              indexName=args.index, vectors=batch)
    print("Done. Embeddings stored in S3 Vectors index:", args.index if not args.dry_run else "(dry-run)")


if __name__ == "__main__":
    main()
