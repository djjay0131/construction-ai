#!/bin/bash
# Master launcher for Construction AI
# Starts both backend and frontend in separate terminal windows

echo "=========================================="
echo "Construction AI - Master Launcher"
echo "=========================================="
echo ""

# Check if we're in the project root
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Must run from project root directory"
    exit 1
fi

# Function to detect terminal emulator
get_terminal() {
    if command -v gnome-terminal &> /dev/null; then
        echo "gnome-terminal --"
    elif command -v xterm &> /dev/null; then
        echo "xterm -e"
    elif command -v konsole &> /dev/null; then
        echo "konsole -e"
    else
        echo ""
    fi
}

TERMINAL=$(get_terminal)

if [ -z "$TERMINAL" ]; then
    echo "⚠️  No terminal emulator found."
    echo "Please start backend and frontend manually:"
    echo ""
    echo "Terminal 1:"
    echo "  cd backend && ./start_server.sh"
    echo ""
    echo "Terminal 2:"
    echo "  cd frontend && ./start_dev.sh"
    exit 1
fi

echo "Starting backend in new terminal..."
$TERMINAL bash -c "cd backend && ./start_server.sh; exec bash"

sleep 2

echo "Starting frontend in new terminal..."
$TERMINAL bash -c "cd frontend && ./start_dev.sh; exec bash"

echo ""
echo "=========================================="
echo "✓ Backend and frontend started!"
echo "=========================================="
echo ""
echo "Access the application:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/api/docs"
echo ""
echo "Close the terminal windows to stop the servers"

