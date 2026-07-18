#!/bin/bash
# Start the full IntelliClaim development environment
# Usage: bash scripts/start_dev.sh

set -e

echo "====================================="
echo "🚀 IntelliClaim Development Setup"
echo "====================================="
echo ""

# Step 1: Start infrastructure
echo "📦 Starting infrastructure (Postgres, Redis, MinIO, Neo4j)..."
docker-compose up -d
echo "   Waiting for services to be ready..."
sleep 5

# Step 2: Run migrations
echo ""
echo "🗄️  Running database migrations..."
cd backend
python3 -m alembic upgrade head 2>/dev/null || echo "   ⚠️  Migrations failed — generate them first with: cd backend && alembic revision --autogenerate -m 'initial'"
cd ..

# Step 3: Start ML service (background)
echo ""
echo "🧠 Starting ML inference service (port 8001)..."
python3 ml/serve.py &
ML_PID=$!
echo "   ML service PID: $ML_PID"
sleep 3

# Step 4: Start Celery worker (background)
echo ""
echo "⚙️  Starting Celery worker..."
cd backend
celery -A app.worker.celery_app worker --loglevel=info --pool=solo &
CELERY_PID=$!
cd ..
echo "   Celery PID: $CELERY_PID"

# Step 5: Start backend API
echo ""
echo "🌐 Starting backend API (port 8000)..."
cd backend
uvicorn app.main:app --reload --port 8000 &
API_PID=$!
cd ..
echo "   API PID: $API_PID"

# Step 6: Start frontend
echo ""
echo "🎨 Starting frontend (port 5173)..."
cd frontend
npm run dev &
FE_PID=$!
cd ..

echo ""
echo "====================================="
echo "✅ All services started!"
echo ""
echo "   Frontend:    http://localhost:5173"
echo "   Backend:     http://localhost:8000/docs"
echo "   ML Service:  http://localhost:8001/docs"
echo "   MinIO:       http://localhost:9001"
echo "   Neo4j:       http://localhost:7474"
echo ""
echo "   Press Ctrl+C to stop all services"
echo "====================================="

# Wait and cleanup on exit
trap "kill $ML_PID $CELERY_PID $API_PID $FE_PID 2>/dev/null; docker-compose stop" EXIT
wait
