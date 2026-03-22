#!/bin/bash
set -e

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi
pip3 install -r requirements.txt -q
python3 backend/app.py
