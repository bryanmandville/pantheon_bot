#!/bin/bash
# Install PANTHEON / APEX as a background service

set -e

BLUE='\03[0;36m'
GREEN='\03[0;32m'
NC='\03[0m'

clear
echo -e "${BLUE}██████╗  █████╗ ███╗   ██╗████████╗██╗  ██╗███████╗██████╗ ███╗   ██╗${NC}"
echo -e "${BLUE}██╔══██╗██╔══██╗████╗  ██║╚══██╔══╝██║  ██║██╔════╝██╔══██╗████╗  ██║${NC}"
echo -e "${BLUE}██████╔╝███████║██╔██╗ ██║   ██║   ███████║█████╗  ██║  ██║██╔██╗ ██║${NC}"
echo -e "${BLUE}██╔═══╝ ██╔══██║██║╚██╗██║   ██║   ██╔══██║██╔══╝  ██║  ██║██║╚██╗██║${NC}"
echo -e "${BLUE}██║     ██║  ██║██║ ╚████║   ██║   ██║  ██║███████╗██████╔╝██║ ╚████║${NC}"
echo -e "${BLUE}╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═══╝${NC}"
echo -e "${GREEN}                                  A I   A G E N T   M E S H${NC}"
echo ""

# Configuration
DEFAULT_INSTALL_DIR="/opt/apex"
DEFAULT_USER=$(whoami)

# Helper function to run commands with sudo if available and necessary
run_as_root() {
    if [ "$EUID" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo -e "${RED}[!] Error: Root privileges required but 'sudo' is not installed.${NC}"
        echo -e "${RED}[!] Please run this script as root.${NC}"
        exit 1
    fi
}

echo -e "${GREEN}Welcome to the Pantheon APEX Installer.${NC}"
read -p "Enter installation directory [$DEFAULT_INSTALL_DIR]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}

read -p "Enter service user [$DEFAULT_USER]: " SERVICE_USER
SERVICE_USER=${SERVICE_USER:-$DEFAULT_USER}

echo ""
echo -e "${BLUE}[*] Preparing installation at $INSTALL_DIR for user $SERVICE_USER...${NC}"

# Ensure we run this with root capabilities if writing to /opt
if [ ! -w "$(dirname "$INSTALL_DIR")" ] && [ "$EUID" -ne 0 ]; then
    echo -e "${BLUE}[*] We need root privileges to create the installation directory...${NC}"
    run_as_root mkdir -p "$INSTALL_DIR"
    run_as_root chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
else
    mkdir -p "$INSTALL_DIR"
fi

# Copy files and setup git
echo -e "${BLUE}[*] Copying files and setting up git repository...${NC}"
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"

# Copy everything including hidden files (like .git if it exists in the source)
if [ "$EUID" -ne 0 ] && [ "$SERVICE_USER" != "$(whoami)" ]; then
    run_as_root cp -r "$SCRIPT_DIR"/. "$INSTALL_DIR"/
    run_as_root chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
else
    cp -r "$SCRIPT_DIR"/. "$INSTALL_DIR"/
fi

# Ensure it's a valid git repository so `pantheon update` works
cd "$INSTALL_DIR"
if [ ! -d .git ]; then
    echo -e "${YELLOW}[!] Source was not a git clone. Initializing git tracking for future updates...${NC}"
    if [ "$EUID" -ne 0 ] && [ "$SERVICE_USER" != "$(whoami)" ]; then
        su - "$SERVICE_USER" -c "cd $INSTALL_DIR && git init && git branch -M main && git remote add origin https://github.com/bryanmandville/pantheon_bot.git && git fetch --all && git reset --hard origin/main"
    else
        git init
        git branch -M main
        git remote add origin https://github.com/bryanmandville/pantheon_bot.git
        git fetch --all
        git reset --hard origin/main
    fi
fi

# Switch to context of service user to run python tasks
cd "$INSTALL_DIR"

echo -e "${BLUE}[*] Checking Python environment dependencies...${NC}"
if ! python3 -m venv --help >/dev/null 2>&1; then
    echo -e "${YELLOW}[!] python3-venv is missing. Attempting to install it...${NC}"
    if command -v apt >/dev/null 2>&1; then
        run_as_root apt update
        # Try to install the version-specific venv package or fallback to the generic one
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        run_as_root apt install -y python${PYTHON_VERSION}-venv || run_as_root apt install -y python3-venv
    elif command -v yum >/dev/null 2>&1; then
        run_as_root yum install -y python3-venv
    elif command -v pacman >/dev/null 2>&1; then
        run_as_root pacman -S --noconfirm python-virtualenv
    else
        echo -e "${RED}[!] Could not automatically install python3-venv. Please install it manually for your OS and try again.${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}[*] Setting up Python virtual environment...${NC}"
if [ "$EUID" -eq 0 ] && [ "$SERVICE_USER" != "root" ]; then
    su - "$SERVICE_USER" -c "cd $INSTALL_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
fi

echo -e "${BLUE}[*] Launching Interactive Configurator...${NC}"
if [ "$EUID" -eq 0 ] && [ "$SERVICE_USER" != "root" ]; then
    su - "$SERVICE_USER" -c "cd $INSTALL_DIR && .venv/bin/pantheon config"
else
    "$INSTALL_DIR"/.venv/bin/pantheon config
fi

echo -e "${BLUE}[*] Starting Qdrant vector database via Docker...${NC}"
if command -v docker >/dev/null 2>&1; then
    # Start only the qdrant service from docker-compose.yml
    run_as_root docker compose -f "$INSTALL_DIR/docker-compose.yml" up -d qdrant || echo -e "${YELLOW}[!] Failed to start Qdrant. Please check your docker installation.${NC}"
else
    echo -e "${YELLOW}[!] Docker not found! Skipping Qdrant spin-up.${NC}"
    echo -e "${YELLOW}[!] APEX requires Qdrant. Please install Docker manually and run:${NC}"
    echo -e "${YELLOW}[!] cd $INSTALL_DIR && sudo docker compose up -d qdrant${NC}"
fi

echo -e "${BLUE}[*] Configuring systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/apex.service"
# Create the service file using the template
cat "$INSTALL_DIR/deploy/apex.service" | sed "s|{INSTALL_DIR}|$INSTALL_DIR|g" | sed "s|{SERVICE_USER}|$SERVICE_USER|g" > /tmp/apex.service
run_as_root mv /tmp/apex.service "$SERVICE_FILE"
run_as_root chmod 644 "$SERVICE_FILE"

echo -e "${BLUE}[*] Creating global symlink...${NC}"
run_as_root ln -sf "$INSTALL_DIR/.venv/bin/pantheon" /usr/local/bin/pantheon

echo -e "${BLUE}[*] Starting background service...${NC}"
run_as_root systemctl daemon-reload
run_as_root systemctl enable apex.service
run_as_root systemctl restart apex.service

echo ""
echo -e "${GREEN}Installation successful!${NC}"
echo -e "You can now run ${BLUE}pantheon chat${NC} anywhere to interact with APEX."
echo -e "To view background logs, run: ${BLUE}journalctl -u apex -f${NC}"
