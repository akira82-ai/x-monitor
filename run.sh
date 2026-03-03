#!/usr/bin/env bash
# Startup script for x-monitor

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "x-monitor - X (Twitter) User Monitoring Dashboard"
echo "=================================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if dependencies are installed
if ! python -c "import prompt_toolkit" 2>/dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Installing...${NC}"
    pip install -q prompt_toolkit feedparser httpx toml wcwidth pyperclip
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# Check if config exists
if [ ! -f "config.toml" ]; then
    echo -e "${YELLOW}Config file not found. Creating sample config...${NC}"
    python main.py --create-config
    echo -e "${GREEN}✓ Created config.toml${NC}"
    echo ""
    echo -e "${YELLOW}Please edit config.toml with your Twitter handles, then run this script again.${NC}"
    exit 0
fi

# Run the application
echo ""
echo "Starting x-monitor..."
echo ""

# Clear SOCKS proxy to avoid socksio dependency, keep HTTP/HTTPS proxy
unset all_proxy ALL_PROXY

python main.py config.toml
