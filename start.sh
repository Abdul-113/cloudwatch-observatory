#!/bin/bash

# CloudWatch Observatory - Quick Start Script
# Automates setup and launches the monitoring platform

echo "╔════════════════════════════════════════════════════════╗"
echo "║   CloudWatch Observatory - Quick Start                 ║"
echo "║   Module C: App Health & Metrics Anomaly Radar         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python installation
echo -e "${BLUE}[1/5]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.8 or higher.${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Install dependencies
echo -e "\n${BLUE}[2/5]${NC} Installing Python dependencies..."
cd backend
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

echo "  Activating virtual environment..."
source venv/bin/activate

echo "  Installing packages..."
pip install -q -r requirements.txt
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}✗ Failed to install dependencies${NC}"
    exit 1
fi

# Generate demo data
echo -e "\n${BLUE}[3/5]${NC} Generating demo data..."
python demo_data.py historical 24
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Demo data generated${NC}"
else
    echo -e "${YELLOW}⚠ Demo data generation skipped${NC}"
fi

# Start backend
echo -e "\n${BLUE}[4/5]${NC} Starting Flask backend server..."
echo -e "${YELLOW}Backend will run on http://localhost:5000${NC}"
python app.py &
BACKEND_PID=$!
sleep 3

# Check if backend started
if ps -p $BACKEND_PID > /dev/null; then
    echo -e "${GREEN}✓ Backend server started (PID: ${BACKEND_PID})${NC}"
else
    echo -e "${RED}✗ Failed to start backend server${NC}"
    exit 1
fi

# Open frontend
echo -e "\n${BLUE}[5/5]${NC} Opening dashboard..."
cd ../frontend

# Detect OS and open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open dashboard.html
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open dashboard.html 2>/dev/null || echo -e "${YELLOW}Please open frontend/dashboard.html in your browser${NC}"
else
    echo -e "${YELLOW}Please open frontend/dashboard.html in your browser${NC}"
fi

echo -e "\n${GREEN}✓ Dashboard opened at frontend/dashboard.html${NC}"

# Instructions
echo -e "\n╔════════════════════════════════════════════════════════╗"
echo -e "║                    ${GREEN}PLATFORM READY${NC}                      ║"
echo -e "╚════════════════════════════════════════════════════════╝"
echo ""
echo -e "${BLUE}Access Points:${NC}"
echo -e "  📊 Dashboard:  file://$(pwd)/dashboard.html"
echo -e "  🔌 Backend:    http://localhost:5000"
echo ""
echo -e "${BLUE}API Endpoints:${NC}"
echo -e "  GET  /api/health/summary"
echo -e "  GET  /api/health/anomalies?hours=24"
echo -e "  GET  /api/metrics/history?service=api-gateway&hours=24"
echo -e "  POST /api/collect/<service_name>"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo -e "  Generate more data:  cd backend && python demo_data.py live 30"
echo -e "  Stop backend:        kill ${BACKEND_PID}"
echo -e "  View logs:           cd backend && tail -f app.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the platform${NC}"
echo ""

# Wait for user interrupt
trap "echo -e '\n${YELLOW}Shutting down...${NC}'; kill $BACKEND_PID 2>/dev/null; deactivate; exit 0" INT

# Keep script running
wait $BACKEND_PID
