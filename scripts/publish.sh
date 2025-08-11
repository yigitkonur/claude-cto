#!/bin/bash
# Publishing automation script for claude-worker

set -e  # Exit on error

echo "🚀 Claude Worker Publishing Assistant"
echo "====================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to prompt yes/no
confirm() {
    read -p "$1 (y/n): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command_exists poetry; then
    echo -e "${RED}❌ Poetry not found. Please install Poetry first.${NC}"
    exit 1
fi

if ! command_exists git; then
    echo -e "${RED}❌ Git not found. Please install Git first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"

# Check git status
echo -e "\n${YELLOW}Checking git status...${NC}"
if [[ -n $(git status -s) ]]; then
    echo -e "${RED}❌ Working directory not clean. Please commit or stash changes.${NC}"
    git status -s
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo -e "${YELLOW}⚠️  Not on main branch (current: $CURRENT_BRANCH)${NC}"
    if ! confirm "Continue anyway?"; then
        exit 1
    fi
fi

echo -e "${GREEN}✅ Git status clean${NC}"

# Get current version
CURRENT_VERSION=$(poetry version -s)
echo -e "\n${YELLOW}Current version: $CURRENT_VERSION${NC}"

# Ask for version bump
echo -e "\nHow would you like to bump the version?"
echo "1) Patch (x.y.Z) - Bug fixes"
echo "2) Minor (x.Y.z) - New features"
echo "3) Major (X.y.z) - Breaking changes"
echo "4) Custom version"
echo "5) Keep current version"

read -p "Select option (1-5): " VERSION_CHOICE

case $VERSION_CHOICE in
    1)
        poetry version patch
        ;;
    2)
        poetry version minor
        ;;
    3)
        poetry version major
        ;;
    4)
        read -p "Enter new version: " NEW_VERSION
        poetry version $NEW_VERSION
        ;;
    5)
        echo "Keeping version $CURRENT_VERSION"
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

NEW_VERSION=$(poetry version -s)
echo -e "${GREEN}Version set to: $NEW_VERSION${NC}"

# Update lock file
echo -e "\n${YELLOW}Updating dependencies...${NC}"
poetry lock --no-update
echo -e "${GREEN}✅ Dependencies locked${NC}"

# Clean build artifacts
echo -e "\n${YELLOW}Cleaning build artifacts...${NC}"
rm -rf dist/ build/ *.egg-info
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
echo -e "${GREEN}✅ Build artifacts cleaned${NC}"

# Build package
echo -e "\n${YELLOW}Building package...${NC}"
poetry build
echo -e "${GREEN}✅ Package built${NC}"

# Display build artifacts
echo -e "\n${YELLOW}Build artifacts:${NC}"
ls -lh dist/

# Test installation
if confirm "Test local installation?"; then
    echo -e "\n${YELLOW}Testing local installation...${NC}"
    
    # Create temporary venv
    TEMP_VENV=$(mktemp -d)
    python -m venv "$TEMP_VENV/venv"
    source "$TEMP_VENV/venv/bin/activate"
    
    # Install and test
    pip install dist/*.whl
    claude-worker --version
    
    # Cleanup
    deactivate
    rm -rf "$TEMP_VENV"
    
    echo -e "${GREEN}✅ Local installation test passed${NC}"
fi

# Publish to Test PyPI
if confirm "Publish to Test PyPI?"; then
    echo -e "\n${YELLOW}Publishing to Test PyPI...${NC}"
    
    # Check if test repo is configured
    if ! poetry config repositories.test-pypi 2>/dev/null; then
        echo "Configuring Test PyPI repository..."
        poetry config repositories.test-pypi https://test.pypi.org/legacy/
    fi
    
    poetry publish -r test-pypi
    echo -e "${GREEN}✅ Published to Test PyPI${NC}"
    echo -e "Test with: pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ claude-worker"
fi

# Final confirmation for PyPI
echo -e "\n${YELLOW}Ready to publish to PyPI${NC}"
echo "Version: $NEW_VERSION"
echo "Files:"
ls -1 dist/

if confirm "Publish to PyPI?"; then
    # Create git tag
    TAG="v$NEW_VERSION"
    echo -e "\n${YELLOW}Creating git tag $TAG...${NC}"
    
    # Commit version bump if changed
    if [[ "$CURRENT_VERSION" != "$NEW_VERSION" ]]; then
        git add pyproject.toml poetry.lock
        git commit -m "Bump version to $NEW_VERSION"
    fi
    
    git tag -a "$TAG" -m "Release $TAG"
    
    # Publish to PyPI
    echo -e "\n${YELLOW}Publishing to PyPI...${NC}"
    poetry publish
    
    echo -e "${GREEN}✅ Published to PyPI!${NC}"
    
    # Push to GitHub
    if confirm "Push tag to GitHub?"; then
        git push origin main
        git push origin "$TAG"
        echo -e "${GREEN}✅ Pushed to GitHub${NC}"
    fi
    
    echo -e "\n${GREEN}🎉 Publication complete!${NC}"
    echo "Package available at: https://pypi.org/project/claude-worker/"
    echo "Install with: pip install claude-worker"
else
    echo -e "${YELLOW}Publication cancelled. Build artifacts remain in dist/${NC}"
fi