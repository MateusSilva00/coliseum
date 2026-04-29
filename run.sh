#!/bin/bash

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}--- Limpando ambiente Docker ---${NC}"

docker compose down --volumes --remove-orphans

echo -e "${GREEN}--- Subindo containers (Clean Build) ---${NC}"
docker compose up --build -d

echo -e "${GREEN}--- Exibindo Logs (CTRL+C para sair) ---${NC}"
docker compose logs -f
