#!/bin/bash
# SoruPilot Deployment Script

set -e

echo "🚀 SoruPilot Deployment"
echo "======================"

# Check environment
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Error: BOT_TOKEN not set"
    echo "   Add to .env: BOT_TOKEN=<your_bot_token>"
    exit 1
fi

if [ -z "$LLM_API_KEY" ]; then
    echo "❌ Error: LLM_API_KEY not set"
    echo "   Add to .env: LLM_API_KEY=<your_anthropic_api_key>"
    exit 1
fi

echo "✓ Environment variables loaded"

# Option 1: Local Docker
if [ "$1" = "docker" ]; then
    echo "🐳 Starting with Docker Compose..."
    docker compose up -d --build
    echo "✓ Running on http://localhost:8000"
    echo "✓ Panel: http://localhost:8000/app"
    exit 0
fi

# Option 2: Cloud Run
if [ "$1" = "cloudrun" ]; then
    PROJECT_ID="${2:-sorupilot-prod}"
    REGION="${3:-us-central1}"

    echo "☁️  Deploying to Cloud Run ($PROJECT_ID/$REGION)..."

    # Set GCP project
    gcloud config set project $PROJECT_ID

    # Build with Cloud Build
    echo "📦 Building image with Cloud Build..."
    gcloud builds submit --config=cloudbuild.yaml

    # Deploy to Cloud Run
    echo "🚀 Deploying to Cloud Run..."
    gcloud run deploy sorupilot \
        --region=$REGION \
        --image=gcr.io/$PROJECT_ID/sorupilot:latest \
        --platform=managed \
        --allow-unauthenticated \
        --set-env-vars="BOT_TOKEN=$BOT_TOKEN,LLM_API_KEY=$LLM_API_KEY,WEBHOOK_SECRET=$WEBHOOK_SECRET,WEBAPP_URL=$WEBAPP_URL,LLM_PROVIDER=anthropic"

    echo "✓ Deployed to Cloud Run"
    exit 0
fi

# Option 3: Railway
if [ "$1" = "railway" ]; then
    echo "🚂 Deploying to Railway..."
    railway up
    echo "✓ Deployed to Railway"
    exit 0
fi

# Option 4: Replit
if [ "$1" = "replit" ]; then
    echo "▶️  Running on Replit..."
    pip install -r requirements.txt
    python -m app.cli setup
    python -m uvicorn app.main:app --factory --host 0.0.0.0 --port 8000
    exit 0
fi

# Default: Local development
echo "📝 Local Development Mode"
echo ""
echo "Setup steps:"
echo "1. cp .env.example .env (edit with your tokens)"
echo "2. pip install -r requirements.txt"
echo "3. python -m app.cli setup"
echo "4. python -m app.cli poll"
echo ""
echo "Or use: ./deploy.sh docker"
echo "Or use: ./deploy.sh cloudrun [PROJECT_ID] [REGION]"
echo "Or use: ./deploy.sh railway"
echo "Or use: ./deploy.sh replit"
