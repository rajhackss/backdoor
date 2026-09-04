#!/bin/bash
# Shadow C2 — Setup Script for Ubuntu
set -e

echo "====================================="
echo "  Shadow C2 — Installation Script"
echo "====================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[!] Running without root. ICMP channel will be disabled.${NC}"
fi

# System packages
echo -e "${GREEN}[*] Installing system packages...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv openssl

# Create virtual environment
echo -e "${GREEN}[*] Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "${GREEN}[*] Installing Python packages...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create directories
echo -e "${GREEN}[*] Creating directories...${NC}"
mkdir -p data/db
mkdir -p data/downloads
mkdir -p data/payloads
mkdir -p data/logs
mkdir -p data/ssl

# Generate SSL certificate
if [ ! -f data/ssl/server.crt ]; then
    echo -e "${GREEN}[*] Generating self-signed SSL certificate...${NC}"
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
        -keyout data/ssl/server.key -out data/ssl/server.crt \
        -days 365 -nodes -subj "/CN=shadowc2.local" 2>/dev/null
    echo -e "${GREEN}[+] SSL certificate generated${NC}"
fi

# Create .env file if not exists
if [ ! -f .env ]; then
    echo -e "${GREEN}[*] Creating default .env file...${NC}"
    SECRET=$(python3 -c "import os; print(os.urandom(32).hex())")
    MASTER=$(python3 -c "import os; print(os.urandom(32).hex())")
    cat > .env << EOF
# Shadow C2 Configuration
export SC2_HOST=0.0.0.0
export SC2_PORT=8443
export SC2_USERNAME=operator
export SC2_PASSWORD=shadowc2
export SC2_SECRET_KEY=${SECRET}
export SC2_MASTER_KEY=${MASTER}
export SC2_DEBUG=false
export SC2_DNS_ENABLED=true
export SC2_DNS_PORT=5353
export SC2_DNS_DOMAIN=c2.local
export SC2_ICMP_ENABLED=false
# export SC2_DISCORD_TOKEN=your_bot_token
# export SC2_DISCORD_CHANNEL=your_channel_id
# export SC2_TELEGRAM_TOKEN=your_bot_token
# export SC2_TELEGRAM_CHAT=your_chat_id
EOF
    echo -e "${GREEN}[+] .env created — edit it to configure${NC}"
fi

echo ""
echo -e "${GREEN}====================================="
echo "  Installation Complete!"
echo "=====================================${NC}"
echo ""
echo -e "  ${YELLOW}To start Shadow C2:${NC}"
echo "    source venv/bin/activate"
echo "    source .env"
echo "    python -m server.app"
echo ""
echo -e "  ${YELLOW}Dashboard:${NC} https://localhost:8443/dashboard/"
echo -e "  ${YELLOW}Default login:${NC} operator / shadowc2"
echo ""
echo -e "  ${RED}⚠️  Change the default password in .env!${NC}"
echo ""
