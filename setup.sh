#!/bin/bash
set -e
echo "======================================"
echo "  EKO Reconciliation App - Setup"
echo "======================================"

# Backend
echo ""
echo "📦 Installing Python dependencies..."
cd backend
pip install -r requirements.txt --break-system-packages --quiet
cd ..

# Frontend
echo ""
echo "📦 Installing Node dependencies..."
cd frontend
npm install --silent
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Run ./start.sh to launch the app"
