#!/usr/bin/env bash
# Render build script for the SafeSight backend.
# Exit on error, treat unset vars as errors, fail on broken pipes.
set -o errexit
set -o nounset
set -o pipefail

pip install --upgrade pip

# Install CPU-only torch/torchvision FIRST so pip does not pull the multi-GB
# CUDA wheels (Render runs CPU instances). The +cpu builds satisfy the
# ==2.5.1 / ==0.20.1 pins in requirements.txt.
pip install torch==2.5.1 torchvision==0.20.1 \
  --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt

# Collect static assets for WhiteNoise to serve.
python manage.py collectstatic --no-input

# Apply database migrations against the Postgres instance.
python manage.py migrate
