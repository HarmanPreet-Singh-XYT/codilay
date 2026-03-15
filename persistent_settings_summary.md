# CodyLay — Persistent Settings & Interactive Menu

## What Changed

CodyLay is now a **full interactive application**, not just a one-time CLI tool. Here's what was added:

---

### 🔑 Persistent API Key Storage
> [!IMPORTANT]
> API keys are now stored in `~/.codylay/settings.json` — **no more `export` commands!**

Keys persist across terminal sessions, restarts, and new terminal windows. The settings file is automatically created when you first configure CodyLay.

### 🖥️ Interactive Menu
Running `codylay` (no arguments) launches a full interactive menu:

```
   ██████╗ ██████╗ ██████╗ ██╗   ██╗██╗      █████╗ ██╗   ██╗
  ██╔════╝██╔═══██╗██╔══██╗╚██╗ ██╔╝██║     ██╔══██╗╚██╗ ██╔╝
  ...

  [1] 📝  Document a codebase
  [2] ⚙️   Setup / First-time configuration
  [3] 🔑  Manage API keys
  [4] 🤖  Change provider & model
  [5] 🔧  Preferences
  [6] 📊  View current settings
  [7] ❓  Help
  [0] 🚪  Exit
```

---

## New Files

| File | Purpose |
|------|---------|
| [settings.py](file:///Users/harmanpreetsingh/Public/Code/codedoc/src/codylay/settings.py) | Persistent settings store (`~/.codylay/settings.json`) |
| [menu.py](file:///Users/harmanpreetsingh/Public/Code/codedoc/src/codylay/menu.py) | Interactive menu system with Rich UI |

## Modified Files

| File | Changes |
|------|---------|
| [cli.py](file:///Users/harmanpreetsingh/Public/Code/codedoc/src/codylay/cli.py) | Settings integration, smart routing, new subcommands |

---

## New CLI Commands

| Command | What it does |
|---------|--------------|
| `codylay` | Launches interactive menu |
| `codylay setup` | First-time setup wizard (provider, API key, model) |
| `codylay config` | View all current settings |
| `codylay keys` | Add, view, or remove stored API keys |

## Existing Commands (unchanged)

| Command | What it does |
|---------|--------------|
| `codylay .` | Document current directory |
| `codylay /path` | Document a specific project |
| `codylay . -p openai` | Use a specific provider |
| `codylay status .` | Show doc status |
| `codylay diff .` | Show what changed |
| `codylay clean .` | Remove generated files |
| `codylay init .` | Create config file |

---

## Architecture

```mermaid
graph TD
    A[codylay CLI] -->|no args| B[Interactive Menu]
    A -->|path arg| C[run command]
    A -->|setup| D[Setup Wizard]
    A -->|config| E[View Settings]
    A -->|keys| F[Manage API Keys]
    
    B --> G[~/.codylay/settings.json]
    D --> G
    F --> G
    
    G -->|inject_env_vars| H[Environment Variables]
    H --> I[LLM Client]
    
    style G fill:#2d5016,stroke:#4ade80
    style B fill:#1e3a5f,stroke:#60a5fa
```

> [!TIP]
> The old `export ANTHROPIC_API_KEY=...` method **still works** as a fallback. Stored keys take priority, then environment variables.
