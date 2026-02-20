#!/bin/bash
# Safe Push Script for Pantheon APEX
# This script ensures we never accidentally push the .env file or other sensitive data.

set -e

RED='\03[0;31m'
GREEN='\03[0;32m'
YELLOW='\03[0;33m'
NC='\03[0m'

echo -e "${YELLOW}[*] Preparing to push updates to GitHub...${NC}"

# Check if git is initialized
if [ ! -d .git ]; then
    echo -e "${RED}[!] Error: Not a git repository. Please initialize git first.${NC}"
    exit 1
fi

# Safeguard: Check if .env is somehow tracked
if git ls-files --error-unmatch .env > /dev/null 2>&1; then
    echo -e "${RED}[!] WARNING: .env file is currently tracked by git!${NC}"
    echo -e "${RED}[!] ABORTING PUSH to prevent secret leaks.${NC}"
    echo -e "Run 'git rm --cached .env' and ensure it is in .gitignore."
    exit 1
fi

# Stage all changes
git add .

# Safeguard: Double check the staged files just to be absolutely certain
if git diff --cached --name-only | grep -q '^\.env$'; then
    echo -e "${RED}[!] CRITICAL WARNING: .env is staged for commit!${NC}"
    echo -e "${RED}[!] ABORTING PUSH.${NC}"
    git reset HEAD .env
    exit 1
fi

# Get commit message
read -p "Enter commit message (default: 'Update APEX'): " COMMIT_MSG
COMMIT_MSG=${COMMIT_MSG:-"Update APEX"}

echo -e "${YELLOW}[*] Committing changes...${NC}"
git commit -m "$COMMIT_MSG" || echo -e "${YELLOW}[*] No changes to commit.${NC}"

echo -e "${YELLOW}[*] Pushing to origin main...${NC}"
git push origin HEAD:main

echo -e "${GREEN}[+] Successfully pushed to GitHub!${NC}"
