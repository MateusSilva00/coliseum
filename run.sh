#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Limpa os containers ao pressionar CTRL+C
trap 'echo -e "\n${RED}--- Encerrando cluster ---${NC}"; docker compose down' INT

echo -e "${GREEN}--- Limpando ambiente Docker ---${NC}"
docker compose down --volumes --remove-orphans

echo -e "${GREEN}--- Subindo containers (Clean Build) ---${NC}"
docker compose up --build -d

echo -e "${GREEN}--- Exibindo Logs (CTRL+C para sair) ---${NC}"
docker compose logs -f
