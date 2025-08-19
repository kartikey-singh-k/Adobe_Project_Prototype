#!/bin/bash

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "📁 Creating directories..."
mkdir -p app/data/uploads
mkdir -p app/static/audio
mkdir -p app/static/assets
mkdir -p app/static/css
mkdir -p app/static/js

echo "🚀 Starting Document Intelligence Server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload