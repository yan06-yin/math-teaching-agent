#!/bin/bash
cd backend
pip install -r requirements.txt --quiet
uvicorn main:app --host 0.0.0.0 --port $PORT
