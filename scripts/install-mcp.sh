#!/bin/bash
# MCP Installation Helper Script for claude-worker

set -e

echo "🚀 Claude Worker MCP Installation Helper"
echo "========================================"
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if fastmcp is installed
if ! command -v fastmcp &> /dev/null; then
    echo -e "${YELLOW}FastMCP CLI not found. Installing...${NC}"
    pip install fastmcp
fi

# Check if uv is installed (required for Claude Desktop)
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠️  UV not found. It's required for Claude Desktop integration.${NC}"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Or on macOS: brew install uv"
    echo
fi

# Function to show menu
show_menu() {
    echo "Select MCP installation target:"
    echo "1) Claude Desktop"
    echo "2) Claude Code"
    echo "3) Cursor"
    echo "4) Generic MCP JSON config"
    echo "5) Run MCP server locally (test)"
    echo "6) Install from PyPI"
    echo "7) Exit"
    echo
    read -p "Enter choice [1-7]: " choice
}

# Function to select mode
select_mode() {
    echo
    echo "Select MCP server mode:"
    echo "1) Auto (detect REST API availability)"
    echo "2) Standalone (embedded database)"
    echo "3) Proxy (connect to REST API)"
    read -p "Enter mode [1-3]: " mode_choice
    
    case $mode_choice in
        1) MODE="auto" ;;
        2) MODE="standalone" ;;
        3) MODE="proxy" ;;
        *) MODE="auto" ;;
    esac
}

# Main installation logic
while true; do
    show_menu
    
    case $choice in
        1) # Claude Desktop
            echo -e "\n${GREEN}Installing for Claude Desktop...${NC}"
            select_mode
            
            if [ "$MODE" = "proxy" ]; then
                read -p "Enter REST API URL (default: http://localhost:8000): " API_URL
                API_URL=${API_URL:-http://localhost:8000}
                
                fastmcp install claude-desktop \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE=proxy \
                    --env CLAUDE_WORKER_API_URL="$API_URL"
            else
                fastmcp install claude-desktop \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE="$MODE"
            fi
            
            echo -e "${GREEN}✅ Installed for Claude Desktop${NC}"
            echo "Restart Claude Desktop to see the new MCP server"
            ;;
            
        2) # Claude Code
            echo -e "\n${GREEN}Installing for Claude Code...${NC}"
            select_mode
            
            if [ "$MODE" = "proxy" ]; then
                read -p "Enter REST API URL (default: http://localhost:8000): " API_URL
                API_URL=${API_URL:-http://localhost:8000}
                
                fastmcp install claude-code \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE=proxy \
                    --env CLAUDE_WORKER_API_URL="$API_URL"
            else
                fastmcp install claude-code \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE="$MODE"
            fi
            
            echo -e "${GREEN}✅ Installed for Claude Code${NC}"
            ;;
            
        3) # Cursor
            echo -e "\n${GREEN}Installing for Cursor...${NC}"
            select_mode
            
            if [ "$MODE" = "proxy" ]; then
                read -p "Enter REST API URL (default: http://localhost:8000): " API_URL
                API_URL=${API_URL:-http://localhost:8000}
                
                fastmcp install cursor \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE=proxy \
                    --env CLAUDE_WORKER_API_URL="$API_URL"
            else
                fastmcp install cursor \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE="$MODE"
            fi
            
            echo -e "${GREEN}✅ Installed for Cursor${NC}"
            ;;
            
        4) # Generic MCP JSON
            echo -e "\n${GREEN}Generating MCP JSON configuration...${NC}"
            select_mode
            
            OUTPUT_FILE="claude-worker-mcp-config.json"
            
            if [ "$MODE" = "proxy" ]; then
                read -p "Enter REST API URL (default: http://localhost:8000): " API_URL
                API_URL=${API_URL:-http://localhost:8000}
                
                fastmcp install mcp-json \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE=proxy \
                    --env CLAUDE_WORKER_API_URL="$API_URL" \
                    > "$OUTPUT_FILE"
            else
                fastmcp install mcp-json \
                    -m src.mcp.factory \
                    --name "Claude Worker MCP" \
                    --env CLAUDE_WORKER_MODE="$MODE" \
                    > "$OUTPUT_FILE"
            fi
            
            echo -e "${GREEN}✅ Configuration saved to $OUTPUT_FILE${NC}"
            echo "Add this to your MCP client's configuration"
            ;;
            
        5) # Run locally
            echo -e "\n${GREEN}Running MCP server locally...${NC}"
            select_mode
            
            echo -e "${YELLOW}Starting MCP server in $MODE mode...${NC}"
            echo "Press Ctrl+C to stop"
            echo
            
            if [ "$MODE" = "proxy" ]; then
                read -p "Enter REST API URL (default: http://localhost:8000): " API_URL
                API_URL=${API_URL:-http://localhost:8000}
                export CLAUDE_WORKER_MODE=proxy
                export CLAUDE_WORKER_API_URL="$API_URL"
            else
                export CLAUDE_WORKER_MODE="$MODE"
            fi
            
            # Run with fastmcp dev for testing
            fastmcp dev src/mcp/factory.py
            ;;
            
        6) # Install from PyPI
            echo -e "\n${GREEN}Installing from PyPI...${NC}"
            echo
            echo "Choose installation type:"
            echo "1) MCP only (lightweight): pip install 'claude-worker[mcp]'"
            echo "2) Server + CLI only: pip install 'claude-worker[server]'"
            echo "3) Full installation: pip install 'claude-worker[full]'"
            read -p "Enter choice [1-3]: " install_choice
            
            case $install_choice in
                1) pip install 'claude-worker[mcp]' ;;
                2) pip install 'claude-worker[server]' ;;
                3) pip install 'claude-worker[full]' ;;
                *) echo "Invalid choice" ;;
            esac
            
            echo -e "${GREEN}✅ Installation complete${NC}"
            ;;
            
        7) # Exit
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
            
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
    
    echo
    read -p "Press Enter to continue..."
    echo
done