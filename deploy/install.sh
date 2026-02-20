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

echo -e "${GREEN}Welcome to the Pantheon APEX Installer.${NC}"
read -p "Enter installation directory [$DEFAULT_INSTALL_DIR]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}

read -p "Enter service user [$DEFAULT_USER]: " SERVICE_USER
SERVICE_USER=${SERVICE_USER:-$DEFAULT_USER}

echo ""
echo -e "${BLUE}[*] Preparing installation at $INSTALL_DIR for user $SERVICE_USER...${NC}"

# Ensure we run this with sudo capabilities if writing to /opt
if [ ! -w "$(dirname "$INSTALL_DIR")" ] && [ "$EUID" -ne 0 ]; then
    echo -e "${BLUE}[*] We need sudo to create the installation directory...${NC}"
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
else
    mkdir -p "$INSTALL_DIR"
fi

# Copy files
echo -e "${BLUE}[*] Copying files...${NC}"
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"
if [ "$EUID" -ne 0 ] && [ "$SERVICE_USER" != "$(whoami)" ]; then
    sudo cp -ru "$SCRIPT_DIR"/* "$INSTALL_DIR"/
    sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
else
    cp -ru "$SCRIPT_DIR"/* "$INSTALL_DIR"/
fi

# Switch to context of service user to run python tasks
cd "$INSTALL_DIR"

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

echo -e "${BLUE}[*] Configuring systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/apex.service"
# Create the service file using the template
cat "$INSTALL_DIR/deploy/apex.service" | sed "s|{INSTALL_DIR}|$INSTALL_DIR|g" | sed "s|{SERVICE_USER}|$SERVICE_USER|g" > /tmp/apex.service
sudo mv /tmp/apex.service "$SERVICE_FILE"
sudo chmod 644 "$SERVICE_FILE"

echo -e "${BLUE}[*] Creating global symlink...${NC}"
sudo ln -sf "$INSTALL_DIR/.venv/bin/pantheon" /usr/local/bin/pantheon

echo -e "${BLUE}[*] Starting background service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable apex.service
sudo systemctl restart apex.service

echo ""
echo -e "${GREEN}Installation successful!${NC}"
echo -e "You can now run ${BLUE}pantheon chat${NC} anywhere to interact with APEX."
echo -e "To view background logs, run: ${BLUE}journalctl -u apex -f${NC}"
