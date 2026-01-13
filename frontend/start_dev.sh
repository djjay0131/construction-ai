#!/bin/bash
# Quick start script for Construction AI frontend

echo "========================================"
echo "Construction AI - Frontend Startup"
echo "========================================"
echo ""

# Check if we're in the frontend directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Not in frontend directory"
    echo "Please run this script from the frontend/ directory"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo ""
    echo "Install Node.js using nvm:"
    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash"
    echo "  source ~/.bashrc"
    echo "  nvm install 18"
    echo "  nvm use 18"
    exit 1
fi

NODE_VERSION=$(node -v)
echo "✓ Node.js version: $NODE_VERSION"

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo "✓ Dependencies installed"
else
    echo "✓ Dependencies already installed"
fi

# Check if backend is running
echo ""
echo "Checking backend connection..."
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✓ Backend is running at http://localhost:8000"
else
    echo "⚠️  Warning: Backend not detected at http://localhost:8000"
    echo "   Make sure to start the backend server first:"
    echo "   cd ../backend && ./start_server.sh"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "========================================"
echo "Starting development server..."
echo "========================================"
echo ""
echo "Frontend: http://localhost:5173"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/api/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the development server
npm run dev

