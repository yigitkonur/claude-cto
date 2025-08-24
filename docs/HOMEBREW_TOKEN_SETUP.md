# Setting up HOMEBREW_TAP_TOKEN

The release workflow requires a `HOMEBREW_TAP_TOKEN` secret to automatically update the Homebrew formula when a new version is released.

## Why This Token is Needed

The `peter-evans/repository-dispatch` action needs to trigger a workflow in the `homebrew-claude-cto` repository. GitHub Actions' default `GITHUB_TOKEN` doesn't have permissions for cross-repository operations, so a Personal Access Token (PAT) is required.

## Creating the Token

1. Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
   - Direct link: https://github.com/settings/tokens/new

2. Configure the token:
   - **Note**: `Homebrew tap updates for claude-cto`
   - **Expiration**: Choose 90 days or custom (will need renewal)
   - **Scopes**: Select only `repo` (full control of private repositories)
     - This gives: repo:status, repo_deployment, public_repo, repo:invite, security_events

3. Click "Generate token" and copy the token immediately (you won't see it again)

## Adding the Token to Repository Secrets

1. Go to the claude-cto repository settings:
   https://github.com/yigitkonur/claude-cto/settings/secrets/actions

2. Click "New repository secret"

3. Add the secret:
   - **Name**: `HOMEBREW_TAP_TOKEN`
   - **Secret**: Paste the token you copied

4. Click "Add secret"

## Token Permissions Explained

The token needs `repo` scope because it must:
- Trigger workflows in the homebrew-claude-cto repository
- Create dispatch events
- Access repository metadata

## Security Considerations

- The token has write access to all your repositories
- Consider creating a fine-grained PAT instead (if available) with access only to `homebrew-claude-cto`
- Rotate the token periodically
- Never commit the token to source control

## Testing the Token

You can test if the token works by manually triggering the release workflow:

```bash
gh workflow run release.yml -f version=0.5.2 -f test_pypi=false
```

Then check if the Homebrew repository received the dispatch event:
https://github.com/yigitkonur/homebrew-claude-cto/actions

## Troubleshooting

If you see "Repository not found, OR token has insufficient permissions":
1. Verify the token hasn't expired
2. Ensure the token has `repo` scope
3. Check that the secret name is exactly `HOMEBREW_TAP_TOKEN`
4. Verify the homebrew-claude-cto repository exists and you have access