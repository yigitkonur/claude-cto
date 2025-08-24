# Version Management System

This document explains the automated version management system for claude-cto.

## Current Version Status

You can check the current version in multiple ways:

### CLI Version
```bash
# Check installed version
claude-cto --version
# or
claude-cto -v

# Check from Python
python -c "import claude_cto; print(claude_cto.__version__)"
```

### API Server Version
```bash
# Health endpoint includes version
curl http://localhost:8000/health
# Returns: {"status": "healthy", "service": "claude-cto", "version": "0.7.4"}
```

### MCP Server Version
Both proxy and standalone MCP servers have version tools:

```python
# In MCP client
await mcp.get_version()
# Returns version info with mode and configuration details

await mcp.check_api_health()  # For proxy mode
# Returns both MCP and API server versions
```

## Version Sources

The version is maintained in these files (must stay synchronized):
- `claude_cto/__init__.py`: `__version__ = "0.7.4"`
- `pyproject.toml`: `version = "0.7.4"` (appears twice for project and poetry)

## Automated Version Bumping

### Manual Bumping (Development)

Use the provided script for local version bumps:

```bash
# Bump patch version (0.7.4 → 0.7.5)
python scripts/bump_version.py patch

# Bump minor version (0.7.4 → 0.8.0) 
python scripts/bump_version.py minor

# Bump major version (0.7.4 → 1.0.0)
python scripts/bump_version.py major

# Set specific version
python scripts/bump_version.py 1.2.3

# Version bump without git tag (for testing)
python scripts/bump_version.py patch --no-tag
```

The script will:
1. ✅ Update `__init__.py` and `pyproject.toml` 
2. ✅ Create git commit with message `chore: bump version to v{version}`
3. ✅ Create git tag `v{version}`
4. ✅ Prompt to push changes

### Automated Bumping (CI/CD)

Use GitHub Actions workflow for team version management:

1. **Go to GitHub Actions** → `Auto Version Management`
2. **Click "Run workflow"**
3. **Choose options**:
   - **Bump type**: `patch`, `minor`, or `major`
   - **Custom version**: Override with specific version (e.g., `1.2.3`)
   - **Skip release**: Only bump version, don't trigger release pipeline

The workflow will:
1. ✅ Bump version in both files
2. ✅ Create commit and push to main
3. ✅ Create git tag (unless skipped)
4. ✅ Trigger full release pipeline (PyPI, Docker, Homebrew)

## Release Pipeline Integration

Version bumping integrates with the existing release system:

### Automatic Release Trigger
- **Git tag `v*.*.*`** → Triggers complete release pipeline
- **Pipeline stages**:
  1. Build Python packages
  2. Publish to PyPI
  3. Build and push Docker images
  4. Update Homebrew formula
  5. Deploy to Smithery registry
  6. Create GitHub release with assets

### Manual Release Control
- **Version bump only**: Skip release by using `--skip-release` flag
- **Test releases**: Use TestPyPI option in release workflow
- **Rollback**: Git operations are reversible before pushing

## Version Display Integration

### CLI Integration
```bash
claude-cto --version
# Output: Claude CTO v0.7.4
```

### Server Integration
All API endpoints include version in health checks:
```json
{
  "status": "healthy",
  "service": "claude-cto", 
  "version": "0.7.4"
}
```

### MCP Integration
MCP servers expose version through tools:
- **Proxy mode**: Shows MCP version + connected API version
- **Standalone mode**: Shows MCP version + database/log paths
- **Tool name**: `get_version()` - available in all MCP servers

## Best Practices

### Development Workflow
1. **Feature development**: Work on feature branches
2. **Ready for release**: Use `python scripts/bump_version.py patch`
3. **Push changes**: `git push origin main && git push origin --tags`
4. **Monitor release**: Check GitHub Actions for pipeline status

### Production Releases
1. **Use GitHub Actions**: Provides audit trail and consistency
2. **Semantic versioning**: 
   - `patch`: Bug fixes, documentation
   - `minor`: New features, backward compatible
   - `major`: Breaking changes
3. **Test first**: Use `--skip-release` for version bumps without deployment

### Troubleshooting

#### Version Sync Issues
If `__init__.py` and `pyproject.toml` get out of sync:
```bash
# Fix manually or use the bump script
python scripts/bump_version.py $(python -c "import claude_cto; print(claude_cto.__version__)")
```

#### Failed Release Pipeline
- Check GitHub Actions logs
- Re-run failed jobs if transient
- For tag issues: Delete tag locally and remotely, then re-create

#### Local Installation Issues
```bash
# Force reinstall to get latest version
pip install --upgrade --force-reinstall claude-cto[full]
```

## File Structure

```
claude-cto/
├── claude_cto/__init__.py              # Source of truth for version
├── pyproject.toml                      # Package metadata (sync with __init__.py)
├── scripts/bump_version.py             # Automated version management
├── .github/workflows/
│   ├── auto-version.yml               # Version bump workflow
│   └── release.yml                    # Full release pipeline
└── VERSION_MANAGEMENT.md              # This documentation
```

## Security Considerations

- **Token permissions**: GitHub Actions uses appropriate minimal permissions
- **Branch protection**: Version bumps require proper git workflow
- **Release signatures**: PyPI publishes use trusted publishing (OIDC)
- **Audit trail**: All version changes tracked in git history

## Migration Notes

This system replaces manual version management. The key improvements:

1. **Consistency**: Single script ensures all files stay in sync
2. **Automation**: GitHub Actions removes human error
3. **Integration**: Version appears everywhere (CLI, API, MCP)
4. **Flexibility**: Supports both development and production workflows

For teams upgrading from manual versioning, use the automated workflows to ensure consistency across all deployment channels.