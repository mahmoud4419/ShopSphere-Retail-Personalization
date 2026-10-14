#!/usr/bin/env bash
#
# push_to_github.sh — publish the ShopSphere demo to GitHub under mahmoud4419
# ----------------------------------------------------------------------------
# Run this from inside the extracted repo folder
# (shopsphere-retail-personalization/).
#
# Prereqs: git installed, and EITHER the GitHub CLI (`gh`) authenticated,
# OR you create the empty repo manually in the GitHub UI first.
#
# Usage:
#   chmod +x push_to_github.sh
#   ./push_to_github.sh
# ----------------------------------------------------------------------------
set -euo pipefail

REPO_NAME="shopsphere-retail-personalization"
GH_USER="mahmoud4419"
DESCRIPTION="ShopSphere — Retail Personalization Engine demo (Data & AI on AWS) for the MENAT Industry AI Accelerator. Fictional retailer, synthetic data."

# 1. Initialize the local repo
git init
git add .
git commit -m "Initial commit: ShopSphere Retail Personalization Engine demo"
git branch -M main

# 2a. Option A — create + push with the GitHub CLI (recommended)
if command -v gh >/dev/null 2>&1; then
  gh repo create "${GH_USER}/${REPO_NAME}" --public \
     --description "${DESCRIPTION}" --source=. --remote=origin --push
  echo "Done. https://github.com/${GH_USER}/${REPO_NAME}"
  exit 0
fi

# 2b. Option B — gh not installed: create the empty repo in the GitHub UI first
#     (https://github.com/new, name = ${REPO_NAME}, do NOT add README/License),
#     then this will push to it:
echo "GitHub CLI (gh) not found."
echo "Create an empty repo at https://github.com/new named '${REPO_NAME}',"
echo "then run:"
echo "  git remote add origin https://github.com/${GH_USER}/${REPO_NAME}.git"
echo "  git push -u origin main"
