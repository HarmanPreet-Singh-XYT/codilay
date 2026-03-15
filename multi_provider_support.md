# Multi-Provider LLM Support

CodyLay now supports **10 LLM providers** out of the box:

## Supported Providers

| Provider | Flag | Default Model | API Key Env Var |
|---|---|---|---|
| **Anthropic** | `-p anthropic` | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| **OpenAI** | `-p openai` | `gpt-4o` | `OPENAI_API_KEY` |
| **Ollama** (local) | `-p ollama` | `llama3.2` | *(none needed)* |
| **Google Gemini** | `-p gemini` | `gemini-2.0-flash` | `GEMINI_API_KEY` |
| **DeepSeek** | `-p deepseek` | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| **Mistral** | `-p mistral` | `mistral-large-latest` | `MISTRAL_API_KEY` |
| **Groq** | `-p groq` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| **xAI (Grok)** | `-p xai` | `grok-2-latest` | `XAI_API_KEY` |
| **Llama Cloud** | `-p llama` | `Llama-4-Maverick-17B-128E` | `LLAMA_API_KEY` |
| **Custom** | `-p custom` | *(must specify)* | `CUSTOM_LLM_API_KEY` |

## Usage Examples

```bash
# Use Google Gemini
export GEMINI_API_KEY=your-key
codylay . -p gemini

# Use local Ollama (no API key needed)
codylay . -p ollama

# Use Groq with a specific model
codylay . -p groq -m mixtral-8x7b-32768

# Use a custom OpenAI-compatible endpoint
export CUSTOM_LLM_API_KEY=your-key
codylay . -p custom --base-url https://your-endpoint.com/v1 -m your-model

# Override any provider's base URL
codylay . -p openai --base-url https://your-proxy.com/v1
```

## Config File ([codylay.config.json](file:///Users/harmanpreetsingh/Public/Code/codylay/codylay.config.json))

```json
{
  "llm": {
    "provider": "gemini",
    "model": "gemini-2.0-flash",
    "baseUrl": "https://custom-url.com/v1",
    "maxTokensPerCall": 4096
  }
}
```

## Architecture

All providers except Anthropic route through the **OpenAI SDK** with a custom `base_url`. This works because all these providers offer OpenAI-compatible APIs.

### Files Changed

| File | Change |
|---|---|
| [llm_client.py](file:///Users/harmanpreetsingh/Public/Code/codylay/src/codylay/llm_client.py) | Provider registry, SDK routing, graceful `response_format` fallback |
| [config.py](file:///Users/harmanpreetsingh/Public/Code/codylay/src/codylay/config.py) | Added `llm_base_url`, default model is now `None` (auto-select) |
| [cli.py](file:///Users/harmanpreetsingh/Public/Code/codylay/src/codylay/cli.py) | 10 providers in `--provider`, added `--base-url`, smart model defaulting |
| [ui.py](file:///Users/harmanpreetsingh/Public/Code/codylay/src/codylay/ui.py) | Shows base URL in config table, handles `None` model display |

### Smart Provider/Model Defaulting

- `codylay .` → Uses config file settings (or anthropic default)
- `codylay . -p gemini` → Auto-selects `gemini-2.0-flash` (ignores config model)
- `codylay . -p gemini -m gemini-1.5-pro` → Uses explicit model
- `codylay . -m gpt-4o-mini` → Uses config provider with overridden model
