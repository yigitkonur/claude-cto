#!/bin/bash
# Docker entrypoint script for claude-cto
# Handles both CLI commands and server mode

# If no arguments provided, show help
if [ $# -eq 0 ]; then
    echo "Claude CTO - Fire-and-forget task execution system"
    echo ""
    echo "Usage:"
    echo "  docker run yigitkonur35/claude-cto <command> [options]"
    echo ""
    echo "Commands:"
    echo "  server        Start REST API server (default)"
    echo "  mcp           Start MCP server for Smithery"
    echo "  cli           Run CLI commands"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Start REST API server"
    echo "  docker run -p 8000:8000 -e ANTHROPIC_API_KEY=\$KEY yigitkonur35/claude-cto server"
    echo ""
    echo "  # Run CLI command"
    echo "  docker run -e ANTHROPIC_API_KEY=\$KEY yigitkonur35/claude-cto cli create 'Build a TODO app'"
    echo ""
    echo "  # Start MCP server"
    echo "  docker run -e ANTHROPIC_API_KEY=\$KEY yigitkonur35/claude-cto mcp"
    exit 0
fi

# Parse first argument as command
COMMAND=$1
shift

case "$COMMAND" in
    server|serve)
        echo "Starting Claude CTO REST API server..."
        exec python -m uvicorn claude_cto.server.main:app --host 0.0.0.0 --port ${PORT:-8000} "$@"
        ;;
    mcp)
        echo "Starting Claude CTO MCP server..."
        exec python -m claude_cto.mcp.factory "$@"
        ;;
    cli)
        # Run CLI with remaining arguments
        exec python -m claude_cto.cli.main "$@"
        ;;
    help|--help|-h)
        # Show help by calling this script with no args
        exec "$0"
        ;;
    # Direct CLI commands
    run|status|list|cancel|logs|orchestrate|orchestration-status|list-orchestrations)
        # Direct CLI command passthrough
        exec python -m claude_cto.cli.main "$COMMAND" "$@"
        ;;
    *)
        # Default to server mode if command not recognized
        echo "Unknown command: $COMMAND"
        echo "Starting server by default..."
        exec python -m uvicorn claude_cto.server.main:app --host 0.0.0.0 --port ${PORT:-8000} "$COMMAND" "$@"
        ;;
esac