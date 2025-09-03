#!/bin/bash
#
# Install git hooks for version management
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GIT_HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📦 Installing git hooks for version management..."

# Create hooks directory if it doesn't exist
if [ ! -d "$GIT_HOOKS_DIR" ]; then
    echo -e "${RED}❌ Not a git repository${NC}"
    exit 1
fi

# Create pre-push hook
cat > "$GIT_HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
#
# Pre-push hook to check version consistency
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get the project root
PROJECT_ROOT="$(git rev-parse --show-toplevel)"

# Check if sync script exists
if [ ! -f "$PROJECT_ROOT/scripts/sync_versions.py" ]; then
    echo -e "${YELLOW}⚠️  Version sync script not found, skipping checks${NC}"
    exit 0
fi

echo "🔍 Checking version consistency before push..."

# Check version consistency
if python "$PROJECT_ROOT/scripts/sync_versions.py" --check >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Version files are in sync${NC}"
else
    echo -e "${RED}❌ Version conflicts detected!${NC}"
    echo ""
    python "$PROJECT_ROOT/scripts/sync_versions.py" --check
    echo ""
    echo -e "${YELLOW}Fix with one of these commands:${NC}"
    echo "  python scripts/sync_versions.py --sync     # Sync with remote"
    echo "  python scripts/sync_versions.py --update <version> --force"
    echo ""
    echo "Or bypass with: git push --no-verify"
    exit 1
fi

# Check if current version has a tag
CURRENT_VERSION=$(python -c "import re; content=open('$PROJECT_ROOT/claude_cto/__init__.py').read(); print(re.search(r'__version__ = [\"']([^\"']+)[\"']', content).group(1))" 2>/dev/null)

if [ -n "$CURRENT_VERSION" ]; then
    if ! git tag -l "v$CURRENT_VERSION" | grep -q "v$CURRENT_VERSION"; then
        echo -e "${YELLOW}⚠️  Version $CURRENT_VERSION is not tagged${NC}"
        echo "   Consider creating a tag: git tag v$CURRENT_VERSION"
    fi
fi

# Check for uncommitted version changes
VERSION_FILES="claude_cto/__init__.py pyproject.toml smithery.yaml"
CHANGED_VERSION_FILES=""

for file in $VERSION_FILES; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        if git diff --cached --name-only | grep -q "^$file$"; then
            CHANGED_VERSION_FILES="$CHANGED_VERSION_FILES $file"
        fi
    fi
done

if [ -n "$CHANGED_VERSION_FILES" ]; then
    echo -e "${YELLOW}📝 Version files being pushed:${NC}$CHANGED_VERSION_FILES"
    
    # Ensure all version files are updated together
    ALL_STAGED=true
    for file in $VERSION_FILES; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            if ! git diff --cached --name-only | grep -q "^$file$"; then
                ALL_STAGED=false
                break
            fi
        fi
    done
    
    if [ "$ALL_STAGED" = false ]; then
        echo -e "${RED}❌ Not all version files are staged!${NC}"
        echo "   All version files should be updated together."
        echo "   Stage all version files or use: python scripts/sync_versions.py --update <version>"
        exit 1
    fi
fi

exit 0
EOF

# Create pre-commit hook
cat > "$GIT_HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
#
# Pre-commit hook to validate version changes
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get the project root
PROJECT_ROOT="$(git rev-parse --show-toplevel)"

# Check if any version files are being committed
VERSION_FILES="claude_cto/__init__.py pyproject.toml smithery.yaml"
VERSION_CHANGED=false

for file in $VERSION_FILES; do
    if git diff --cached --name-only | grep -q "^$file$"; then
        VERSION_CHANGED=true
        break
    fi
done

if [ "$VERSION_CHANGED" = true ]; then
    echo "🔍 Validating version changes..."
    
    # Create temporary directory for staged files
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT
    
    # Export staged version files to temp directory
    for file in $VERSION_FILES; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            mkdir -p "$TEMP_DIR/$(dirname $file)"
            git show ":$file" > "$TEMP_DIR/$file" 2>/dev/null || cp "$PROJECT_ROOT/$file" "$TEMP_DIR/$file"
        fi
    done
    
    # Check version format in staged files
    if [ -f "$TEMP_DIR/claude_cto/__init__.py" ]; then
        VERSION=$(python -c "import re; content=open('$TEMP_DIR/claude_cto/__init__.py').read(); match=re.search(r'__version__ = [\"']([^\"']+)[\"']', content); print(match.group(1) if match else '')" 2>/dev/null)
        
        if [ -z "$VERSION" ]; then
            echo -e "${RED}❌ Invalid version format in __init__.py${NC}"
            exit 1
        fi
        
        # Validate semantic versioning
        if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
            echo -e "${RED}❌ Version $VERSION does not follow semantic versioning (X.Y.Z)${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}✅ Version $VERSION is valid${NC}"
    fi
fi

exit 0
EOF

# Make hooks executable
chmod +x "$GIT_HOOKS_DIR/pre-push"
chmod +x "$GIT_HOOKS_DIR/pre-commit"

echo -e "${GREEN}✅ Git hooks installed successfully!${NC}"
echo ""
echo "Installed hooks:"
echo "  • pre-push: Checks version consistency before pushing"
echo "  • pre-commit: Validates version format in commits"
echo ""
echo "To bypass hooks (not recommended):"
echo "  • git push --no-verify"
echo "  • git commit --no-verify"
echo ""
echo "To uninstall hooks:"
echo "  • rm .git/hooks/pre-push .git/hooks/pre-commit"