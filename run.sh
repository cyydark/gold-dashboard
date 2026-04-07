#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd):$PYTHONPATH"
echo "Starting Gold Dashboard on http://localhost:18000"
uvicorn backend.main:app --host 0.0.0.0 --port 18000 --reload
