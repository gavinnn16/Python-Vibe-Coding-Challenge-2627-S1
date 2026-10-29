#!/usr/bin/env bash
# Mac / Linux launcher:  bash run.sh
cd "$(dirname "$0")"
python3 -m venv .venv || exit 1
source .venv/bin/activate
python -m pip install --quiet -r requirements.txt || exit 1
python main.py
