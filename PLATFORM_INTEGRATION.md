# Platform Integration

CodiLay CLI supports optional integration with the CodiLay platform for enhanced collaboration, cloud storage, and token proxy features.

## Features

### 1. **Cloud Sync**
Automatically sync your generated documentation to the CodiLay platform after each run. This enables:
- Version history tracking
- Team access to documentation
- Web-based documentation viewer
- Cross-device synchronization

### 2. **Token Proxy**
Route LLM API calls through the CodiLay platform's token proxy, eliminating the need for your own API keys:
- No need to manage your own Anthropic/OpenAI API keys
- Usage-based billing or prepaid credits
- Centralized token usage tracking
- Shared team credits

### 3. **GitHub Integration** (Coming Soon)
Connect your GitHub repositories for automatic documentation updates on every commit.

---

## Getting Started

### Prerequisites

Install the platform integration dependencies:

```bash
pip install codilay[platform]
# or
pip install codilay[all]
```

### Authentication

#### 1. Get a CodiLay API Key

Sign up at [codilay.dev](https://codilay.dev) (or your self-hosted instance) and create an API key from your dashboard.

#### 2. Log In

```bash
codilay auth login --key cdk_xxxxxxxxxxxxx
```

You'll be prompted for:
- **Organization slug**: Your organization identifier
- **API URL** (optional): Platform API base URL (defaults to `http://localhost:8000`)
- **Proxy URL** (optional): Token proxy base URL (defaults to `http://localhost:8001`)

For production use:

```bash
codilay auth login \
  --key cdk_xxxxxxxxxxxxx \
  --org my-company \
  --api-url https://api.codilay.dev \
  --proxy-url https://proxy.codilay.dev
```

#### 3. Verify Status

```bash
codilay auth status
```

This displays:
- Login status
- Organization
- Service health (API and proxy)
- Sync settings

---

## Usage

### Automatic Sync

Once logged in, CodiLay automatically syncs your documentation to the platform after each run:

```bash
codilay .
# ... docs generated ...
# ✓ Synced to CodiLay platform (run a1b2c3d4)
```

The sync uploads:
- `CODEBASE.md` — your generated documentation
- `links.json` — cross-reference data (if available)
- `state.json` — agent state (if available)
- Git metadata — commit SHA and branch (if in a git repo)

### Disable Sync

To disable automatic sync without logging out:

```bash
codilay auth config --no-sync
```

Re-enable with:

```bash
codilay auth config --sync
```

### Using the Token Proxy

If you're logged in and **don't have a local Anthropic API key** configured, CodiLay automatically routes LLM requests through the platform proxy:

```bash
# Remove local API key
unset ANTHROPIC_API_KEY

# Run normally — uses platform proxy automatically
codilay .
```

The CLI detects the missing local key, checks for platform credentials, and routes all LLM calls through the proxy. Your usage is tracked and billed according to your platform plan.

**Note**: Local API keys always take precedence. If `ANTHROPIC_API_KEY` is set, the CLI uses it directly.

---

## Configuration

### Organization

Set your default organization:

```bash
codilay auth config --org my-company
```

### Service URLs

Update API or proxy URLs:

```bash
codilay auth config --api-url https://api.codilay.dev
codilay auth config --proxy-url https://proxy.codilay.dev
```

---

## Logout

To clear all platform credentials:

```bash
codilay auth logout
```

This removes:
- API key
- Organization slug
- All platform settings

Your local documentation and settings remain unchanged.

---

## Self-Hosting

The CodiLay platform is designed to be self-hosted. Follow the [platform deployment guide](https://github.com/your-platform-repo) to run your own instance.

Key components:
- **platform-api** — Authentication, sync, and management (port 8000)
- **token-proxy** — LLM request forwarding and usage tracking (port 8001)
- **PostgreSQL** — User, org, and run metadata
- **S3-compatible storage** — Documentation files

Once deployed, configure the CLI to point at your instance:

```bash
codilay auth login \
  --key cdk_xxxxxxxxxxxxx \
  --api-url http://your-platform:8000 \
  --proxy-url http://your-proxy:8001
```

---

## Troubleshooting

### "Platform sync failed (non-fatal)"

Sync errors never block documentation generation. Common causes:

1. **Network issues** — Check connectivity to the platform API
2. **Invalid credentials** — Run `codilay auth status` to verify
3. **Org not found** — Ensure your org slug is correct
4. **Plan limits exceeded** — Check your platform dashboard

To debug, run with verbose logging:

```bash
codilay . --verbose
```

### "httpx is required for platform integration"

Install the platform dependencies:

```bash
pip install httpx
# or
pip install codilay[platform]
```

### Token Proxy Not Used

The token proxy is only used when:
1. You're logged in (`codilay auth status` shows "Logged in")
2. You're using the Anthropic provider
3. No local `ANTHROPIC_API_KEY` is set

Check your configuration:

```bash
echo $ANTHROPIC_API_KEY  # Should be empty
codilay auth status      # Should show "Logged in"
```

---

## Privacy & Security

### What Gets Synced?

When sync is enabled, only these files are uploaded:
- `CODEBASE.md` — generated documentation
- `links.json` — cross-reference data
- `state.json` — agent processing state
- Git metadata — commit SHA and branch name

**Your source code is never uploaded.** The platform receives only the documentation output.

### API Key Storage

CodiLay API keys are stored in `~/.codilay/settings.json` in plaintext. Protect this file:

```bash
chmod 600 ~/.codilay/settings.json
```

Do not commit this file to version control. It's automatically gitignored by CodiLay.

### Token Proxy Security

When using the token proxy:
- All LLM requests include your `X-CodiLay-API-Key` header
- The proxy validates the key, forwards to Anthropic/OpenAI, and returns the response
- Your conversations are **not logged** by the proxy (only token counts)
- The proxy never sees your source code (only the prompts CodiLay generates)

---

## API Reference

For building custom integrations, see the [Platform API Reference](./PLATFORM_API.md).

Key endpoints:
- `POST /api/sync/upload` — Upload documentation
- `GET /health` — Health check
- `POST /v1/messages` (proxy) — Anthropic Messages API

---

## Examples

### Local Development Workflow

```bash
# Set up local platform (Docker)
cd codilay-platform
docker compose up -d

# Log in
codilay auth login --key cdk_dev_key

# Document a project
cd ~/projects/my-app
codilay .

# View in web UI
open http://localhost:8000/orgs/my-org/repos/my-app
```

### Team Collaboration

```bash
# Team member 1: Initial setup
codilay auth login --key cdk_team_key --org acme-corp
cd project
codilay .
# Docs synced to platform

# Team member 2: Access synced docs
codilay auth login --key cdk_team_key --org acme-corp
# Visit web UI to view team member 1's docs
```

### CI/CD Integration

```yaml
# .github/workflows/docs.yml
name: Generate Docs
on: [push]
jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install codilay[platform]
      - run: |
          codilay auth login \
            --key ${{ secrets.CODILAY_API_KEY }} \
            --org ${{ secrets.CODILAY_ORG }} \
            --api-url https://api.codilay.dev \
            --proxy-url https://proxy.codilay.dev
      - run: codilay .
      # Docs automatically synced to platform
```

---

## Feedback

Platform integration is in active development. Report issues or request features:

- **GitHub Issues**: [codilay/issues](https://github.com/HarmanPreet-Singh-XYT/codilay/issues)
- **Email**: support@codilay.dev
