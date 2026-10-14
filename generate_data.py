#!/usr/bin/env python3
"""
ShopSphere Retail Personalization Engine - Synthetic Data Generator
====================================================================
MENAT Industry AI Accelerator | Retail Demo Package

Generates fully fictional retail data for the ShopSphere demo:
  - customers.csv     : customer profiles + loyalty tier
  - catalog.csv       : product catalog with categories, price, attributes
  - clickstream.csv   : web/app session events (view, add_to_cart, search)
  - orders.csv        : completed transactions (header + line items)

ALL DATA IS SYNTHETIC. No real customers, no real PII. Brand = "ShopSphere"
(fictional). Safe for public GitHub publication.

Usage:
    python generate_data.py --out ./output --customers 5000 --days 90
"""
import argparse
import csv
import os
import random
import uuid
from datetime import datetime, timedelta

RNG = random.Random(42)  # deterministic for reproducible demos

# ----------------------------------------------------------------------------
# Reference data (fictional)
# ----------------------------------------------------------------------------
CATEGORIES = {
    "Electronics":      ["Smartphone", "Laptop", "Headphones", "Smartwatch", "Tablet", "Camera"],
    "Fashion":          ["T-Shirt", "Jeans", "Sneakers", "Jacket", "Dress", "Handbag"],
    "Home & Kitchen":   ["Coffee Maker", "Cookware Set", "Vacuum", "Bedding", "Air Fryer", "Blender"],
    "Beauty":           ["Perfume", "Skincare Set", "Makeup Kit", "Hair Dryer", "Fragrance"],
    "Sports":           ["Running Shoes", "Yoga Mat", "Dumbbells", "Bicycle", "Backpack"],
    "Grocery":          ["Coffee Beans", "Olive Oil", "Dates Gift Box", "Honey", "Tea Selection"],
}
BRANDS = ["Aurora", "NovaPeak", "Lumio", "Verda", "Kyro", "Solace", "Mistral", "Zephyr", "Onyx", "Pavo"]
LOYALTY_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
LOYALTY_WEIGHTS = [0.50, 0.30, 0.15, 0.05]
CHANNELS = ["web", "mobile_app", "mobile_web"]
CITIES = ["Metro North", "Metro South", "Coastal", "Central", "Highland", "Riverside"]  # generic, non-country-specific
GENDERS = ["F", "M", "U"]
EVENT_TYPES = ["view", "search", "add_to_cart", "remove_from_cart", "wishlist"]
EVENT_WEIGHTS = [0.60, 0.18, 0.12, 0.05, 0.05]


def gen_customers(n):
    rows = []
    start = datetime(2023, 1, 1)
    for i in range(n):
        signup = start + timedelta(days=RNG.randint(0, 900))
        tier = RNG.choices(LOYALTY_TIERS, weights=LOYALTY_WEIGHTS)[0]
        rows.append({
            "customer_id": f"CUST{100000 + i}",
            "signup_date": signup.strftime("%Y-%m-%d"),
            "loyalty_tier": tier,
            "age_band": RNG.choice(["18-24", "25-34", "35-44", "45-54", "55+"]),
            "gender": RNG.choices(GENDERS, weights=[0.47, 0.47, 0.06])[0],
            "city_zone": RNG.choice(CITIES),
            "preferred_language": RNG.choices(["en", "ar"], weights=[0.55, 0.45])[0],
            "email_opt_in": RNG.choices([1, 0], weights=[0.7, 0.3])[0],
            "lifetime_value_band": tier,  # correlates with tier for demo realism
        })
    return rows


def gen_catalog(n_per_cat=40):
    rows = []
    pid = 0
    for cat, subs in CATEGORIES.items():
        for _ in range(n_per_cat):
            sub = RNG.choice(subs)
            brand = RNG.choice(BRANDS)
            base = {
                "Electronics": (120, 2500), "Fashion": (25, 300),
                "Home & Kitchen": (30, 600), "Beauty": (15, 250),
                "Sports": (20, 900), "Grocery": (8, 120),
            }[cat]
            price = round(RNG.uniform(*base), 2)
            rows.append({
                "product_id": f"PROD{10000 + pid}",
                "product_name": f"{brand} {sub}",
                "category": cat,
                "subcategory": sub,
                "brand": brand,
                "price": price,
                "rating": round(RNG.uniform(3.2, 5.0), 1),
                "num_reviews": RNG.randint(0, 5000),
                "in_stock": RNG.choices([1, 0], weights=[0.9, 0.1])[0],
                "color": RNG.choice(["Black", "White", "Blue", "Red", "Green", "Beige", "Silver"]),
                "is_new_arrival": RNG.choices([1, 0], weights=[0.2, 0.8])[0],
            })
            pid += 1
    return rows


def gen_events_and_orders(customers, catalog, days):
    """Generate correlated clickstream + orders.
    Customers have affinity to 1-2 categories -> realistic personalization signal."""
    clickstream, order_headers, order_lines = [], [], []
    now = datetime(2026, 10, 1)
    start = now - timedelta(days=days)
    cat_list = list(CATEGORIES.keys())
    prod_by_cat = {}
    for p in catalog:
        prod_by_cat.setdefault(p["category"], []).append(p)

    for cust in customers:
        # each customer has affinity categories
        affinity = RNG.sample(cat_list, k=RNG.choice([1, 1, 2]))
        tier_mult = {"Bronze": 0.6, "Silver": 1.0, "Gold": 1.8, "Platinum": 3.2}[cust["loyalty_tier"]]
        n_sessions = max(1, int(RNG.gauss(6 * tier_mult, 3)))
        for _ in range(n_sessions):
            sess_time = start + timedelta(
                days=RNG.randint(0, days - 1),
                hours=RNG.randint(6, 23), minutes=RNG.randint(0, 59))
            session_id = str(uuid.uuid4())[:12]
            channel = RNG.choices(CHANNELS, weights=[0.35, 0.5, 0.15])[0]
            # pick products mostly from affinity category
            cat = RNG.choices(
                [RNG.choice(affinity), RNG.choice(cat_list)], weights=[0.75, 0.25])[0]
            n_events = RNG.randint(2, 9)
            cart = []
            for _ in range(n_events):
                prod = RNG.choice(prod_by_cat[cat])
                etype = RNG.choices(EVENT_TYPES, weights=EVENT_WEIGHTS)[0]
                evt_time = sess_time + timedelta(seconds=RNG.randint(5, 400))
                clickstream.append({
                    "event_id": str(uuid.uuid4())[:16],
                    "session_id": session_id,
                    "customer_id": cust["customer_id"],
                    "event_type": etype,
                    "product_id": prod["product_id"],
                    "category": prod["category"],
                    "channel": channel,
                    "event_timestamp": evt_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "search_term": RNG.choice(["", "", prod["subcategory"].lower(), prod["brand"].lower()]),
                })
                if etype == "add_to_cart":
                    cart.append(prod)
            # convert some carts to orders
            if cart and RNG.random() < 0.35 * min(tier_mult, 2.0):
                order_id = f"ORD{str(uuid.uuid4())[:10].upper()}"
                order_time = sess_time + timedelta(minutes=RNG.randint(2, 30))
                total = 0.0
                for prod in cart:
                    qty = RNG.choices([1, 2, 3], weights=[0.8, 0.15, 0.05])[0]
                    line_total = round(prod["price"] * qty, 2)
                    total += line_total
                    order_lines.append({
                        "order_id": order_id,
                        "product_id": prod["product_id"],
                        "quantity": qty,
                        "unit_price": prod["price"],
                        "line_total": line_total,
                    })
                order_headers.append({
                    "order_id": order_id,
                    "customer_id": cust["customer_id"],
                    "order_timestamp": order_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "channel": channel,
                    "num_items": len(cart),
                    "order_total": round(total, 2),
                    "payment_method": RNG.choice(["card", "wallet", "cod", "installments"]),
                    "status": RNG.choices(["completed", "returned", "cancelled"], weights=[0.88, 0.08, 0.04])[0],
                })
    return clickstream, order_headers, order_lines


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {len(rows):>8,} rows -> {os.path.basename(path)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./output")
    ap.add_argument("--customers", type=int, default=5000)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--products-per-category", type=int, default=40)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    print("ShopSphere synthetic data generation (all fictional)")
    print("=" * 55)
    customers = gen_customers(args.customers)
    catalog = gen_catalog(args.products_per_category)
    clickstream, oh, ol = gen_events_and_orders(customers, catalog, args.days)

    write_csv(os.path.join(args.out, "customers.csv"), customers)
    write_csv(os.path.join(args.out, "catalog.csv"), catalog)
    write_csv(os.path.join(args.out, "clickstream.csv"), clickstream)
    write_csv(os.path.join(args.out, "order_headers.csv"), oh)
    write_csv(os.path.join(args.out, "order_lines.csv"), ol)
    print("=" * 55)
    print(f"Done. Output in: {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
