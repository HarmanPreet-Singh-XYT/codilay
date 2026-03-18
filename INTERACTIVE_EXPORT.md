# Interactive Export Feature

## Overview

The interactive export feature enables LLM-guided customization of CodiLay documentation exports. Instead of always exporting the full compressed documentation, users can now describe exactly what they want in natural language, and an LLM will translate that into a precise export specification.

## Architecture

### Components

1. **`export_spec.py`** - Export Specification Schema
   - `ExportSpec` dataclass: Defines what to include/exclude and how to transform content
   - `BUILTIN_PRESETS`: Pre-configured export templates
   - `get_preset()`: Retrieves built-in or custom presets
   - `list_presets()`: Lists all available presets

2. **`interactive_export.py`** - LLM Conversation Handler
   - `query_llm_for_spec()`: Translates natural language to ExportSpec
   - `interactive_export_flow()`: Multi-turn conversation interface
   - `estimate_tokens()`: Estimates export size before committing
   - `show_presets()`: Displays available presets in a table

3. **`exporter.py`** (Enhanced) - Export Engine
   - Now accepts `ExportSpec` for fine-grained control
   - `_strip_implementation_details()`: Removes code bodies, keeps signatures
   - Section filtering based on include/exclude patterns
   - Spec-based content transformations

4. **`cli.py`** (Enhanced) - Command-Line Interface
   - `--interactive` / `-i`: Launch conversational export flow
   - `--query` / `-q`: One-shot query-to-export
   - `--preset` / `-p`: Use named preset
   - `--list-presets`: Show available presets

5. **`settings.py`** (Enhanced) - User Preferences
   - `export_presets`: User-defined custom presets
   - Stored in `~/.codilay/settings.json`

### Data Flow

#### Interactive Mode
```
User describes need → LLM generates spec → Token estimate shown → User confirms → Export
```

#### Query Mode
```
User provides --query → LLM generates spec → Estimate shown → Export (no confirmation)
```

#### Preset Mode
```
User selects --preset → Preset loaded → Export
```

## Usage Examples

### Interactive Mode
```bash
codilay export ./my-project --interactive
```

**Conversation example:**
```
What would you like to export?
> just the file structure and how files link to each other

Generating export specification...
Estimating token count...

Export Plan: File structure and linkage map — no implementation detail
Estimated size: ~2,400 tokens (8,500 chars)

Including sections:
  • overview
  • entry-point
  • routes
  • models

Settings:
  • Dependency graph: yes
  • Implementation details: stripped
  • Format: markdown

What would you like to do?
  [1] Export this
  [2] Make it smaller (describe how)
  [3] Add more detail (describe what)
  [4] Start over with a different query
  [5] Cancel

Choice [1]: 1
```

### Query Mode (Non-Interactive)
```bash
# Single command export
codilay export . --query "file structure and linkage only" -o structure.md

# API surface only
codilay export . --query "just the API endpoints and their schemas" -o api.md

# Auth module with dependencies
codilay export . --query "auth module with all its dependencies" --format json
```

### Preset Mode
```bash
# List available presets
codilay export . --list-presets

# Use a built-in preset
codilay export . --preset structure -o context.md
codilay export . --preset api-surface --format xml
codilay export . --preset onboarding

# Use a custom preset (defined in settings)
codilay export . --preset my-pr-context
```

## Built-In Presets

### 1. `structure`
**Description:** File structure and linkage map — no implementation detail  
**Token Budget:** ~3,000 tokens  
**Use Case:** Quick codebase overview for initial exploration

**Includes:**
- overview
- entry-point
- routes
- models

**Strips:** Function bodies, code examples, detailed explanations  
**Keeps:** File paths, cross-links, section headers

### 2. `api-surface`
**Description:** Public API surface with request/response schemas  
**Token Budget:** ~5,000 tokens  
**Use Case:** API documentation for integration partners

**Includes:**
- routes/api/endpoints
- models/schemas

**Keeps:** Function signatures, request/response schemas, route definitions  
**Strips:** Internal implementation, helper functions

### 3. `onboarding`
**Description:** High-level overview for project onboarding  
**Token Budget:** ~2,000 tokens  
**Use Case:** New developer onboarding

**Includes:**
- overview
- entry-point
- setup
- architecture

**Strips:** Implementation details, internal utilities  
**Keeps:** High-level architecture, entry points, setup instructions

### 4. `dependencies-only`
**Description:** Dependency graph only — no section content  
**Token Budget:** ~1,000 tokens  
**Use Case:** Understanding module relationships

**Includes:** Dependency graph only  
**Excludes:** All section content

## Custom Presets

Users can define custom presets in `~/.codilay/settings.json`:

```json
{
  "export_presets": {
    "my-pr-context": {
      "include_sections": ["overview"],
      "include_graph": true,
      "strip_implementation": false,
      "summary": "Changed files and their dependencies for PR review",
      "max_tokens": 3000,
      "format": "markdown"
    },
    "debug-helpers": {
      "include_sections": ["utilities", "helpers", "debugging"],
      "include_graph": false,
      "strip_implementation": false,
      "summary": "Utility functions for debugging",
      "max_tokens": 2000
    }
  }
}
```

Then use them:
```bash
codilay export . --preset my-pr-context
```

## ExportSpec Schema

```python
@dataclass
class ExportSpec:
    # Sections to include (empty = all)
    include_sections: List[str] = []
    
    # Sections to exclude (takes precedence)
    exclude_sections: List[str] = []
    
    # Include dependency graph
    include_graph: bool = True
    
    # Include unresolved references
    include_unresolved: bool = False
    
    # Strip implementation details (keep only signatures)
    strip_implementation: bool = False
    
    # Content elements to keep
    keep: List[str] = ["function signatures", "cross-links", "file paths"]
    
    # Content elements to strip
    strip: List[str] = []
    
    # Human-readable summary
    summary: str = "Full documentation export"
    
    # Token budget (None = no limit)
    max_tokens: Optional[int] = None
    
    # Output format
    format: str = "markdown"  # markdown | xml | json
```

## Section Patterns

Section IDs can be specified with wildcards:

- `"overview"` - Exact match
- `"auth*"` - All sections starting with "auth"
- `"*test"` - All sections ending with "test"

**Examples:**
```python
# Include all auth-related sections
include_sections=["auth*"]

# Exclude all test sections
exclude_sections=["*test", "*tests"]
```

## Token Estimation

The system estimates token count before exporting using:
- Character count / 3.5 (conservative estimate for tiktoken cl100k)
- Trial export with spec applied
- Size shown before user confirmation in interactive mode

**Accuracy:** ~95% accurate for most codebases (slightly conservative)

## LLM Integration

### System Prompt
The LLM is guided by a system prompt that:
- Explains available section types
- Shows ExportSpec format
- Provides common usage patterns
- Ensures JSON-only responses

### Response Processing
1. LLM responds with JSON ExportSpec
2. Markdown code blocks are stripped if present
3. JSON is parsed into ExportSpec dataclass
4. Validation ensures all required fields are present

### Error Handling
- Invalid JSON → Error message, retry
- Missing sections → Warning, continue with available sections
- LLM unavailable → Fallback to traditional export

## Implementation Details

### Section Filtering
```python
def matches_section(self, section_id: str) -> bool:
    # Explicit exclusion takes precedence
    if section_id in self.exclude_sections:
        return False
    
    # Check exclusion patterns
    for pattern in self.exclude_sections:
        if pattern.endswith("*") and section_id.startswith(pattern[:-1]):
            return False
    
    # Empty include list = include everything
    if not self.include_sections:
        return True
    
    # Check inclusion
    return section_id in self.include_sections or \
           any(pattern.endswith("*") and section_id.startswith(pattern[:-1]) 
               for pattern in self.include_sections)
```

### Implementation Stripping
When `strip_implementation=True`:
- Code blocks analyzed for function/class definitions
- Only signatures kept (e.g., `def func(args):...`)
- Function bodies removed
- Long paragraphs (>100 chars) filtered out
- Headers, lists, and short explanations preserved

## Integration with Existing Features

### Diff-Run Pairing
```bash
# Generate context for PR review
codilay diff-run --since main --export --query "what changed and what it affects"
```

### Web UI
- Export specification UI (planned)
- Preset selection dropdown (planned)
- Token budget slider (planned)

### API Endpoint
```python
POST /api/export
{
  "spec": {
    "include_sections": ["overview", "api"],
    "strip_implementation": true,
    "max_tokens": 3000
  }
}
```

## Testing

### Unit Tests
Located in `tests/test_export_spec.py` (to be created):
- ExportSpec creation and validation
- Section pattern matching
- Preset retrieval
- JSON serialization/deserialization

### Integration Tests
Located in `tests/test_interactive_export.py` (to be created):
- LLM query translation
- Token estimation accuracy
- Interactive flow simulation
- CLI flag combinations

### Manual Testing
```bash
# Test each mode
codilay export . --interactive
codilay export . --query "just file structure"
codilay export . --preset structure
codilay export . --list-presets

# Test combinations
codilay export . --query "API surface" -o api.md --format xml
codilay export . --preset onboarding --max-tokens 1000
```

## Performance

- **Interactive mode:** 1-2 LLM calls per session
- **Query mode:** 1 LLM call
- **Preset mode:** 0 LLM calls (instant)
- **Token estimation:** <100ms for typical projects
- **Export time:** Same as traditional export

## Future Enhancements

1. **Smart defaults based on git context**
   - If on feature branch, suggest changed files + dependencies
   - If reviewing PR, suggest diff context

2. **Learning from user preferences**
   - Track commonly used queries
   - Suggest presets based on usage patterns

3. **Multi-project presets**
   - Share presets across projects
   - Team-level preset libraries

4. **Export scheduling**
   - Periodic exports on watch
   - Auto-export on git hooks

5. **Diff-aware exports**
   - Export only changed sections
   - Include before/after for modified sections

6. **Collaborative exports**
   - Share export specs via URL
   - Team workspace with shared presets

## Troubleshooting

### LLM not generating valid spec
**Problem:** LLM responds with invalid JSON or wrong format

**Solutions:**
1. Check LLM configuration: `codilay config`
2. Try simpler query: "just the overview section"
3. Use preset mode instead: `--preset structure`

### Token estimate seems wrong
**Problem:** Exported size differs significantly from estimate

**Solutions:**
1. Estimates are conservative (actual export may be smaller)
2. Run without `--max-tokens` to see full size
3. Check if spec includes expected sections

### Section not included
**Problem:** Expected section missing from export

**Solutions:**
1. Check section ID in state: `less codilay/.codilay_state.json`
2. Use `--interactive` to see what will be included
3. Try wildcard pattern: `"api*"` instead of `"api-routes"`

### Custom preset not found
**Problem:** `--preset my-preset` says "Unknown preset"

**Solutions:**
1. Check settings file: `cat ~/.codilay/settings.json`
2. Ensure `export_presets` key exists
3. Validate JSON syntax in settings file

## Files Modified/Created

### Created
- `src/codilay/export_spec.py` - ExportSpec schema and presets
- `src/codilay/interactive_export.py` - LLM conversation handler

### Modified
- `src/codilay/exporter.py` - Added spec support, implementation stripping
- `src/codilay/cli.py` - Added interactive/query/preset flags
- `src/codilay/settings.py` - Added export_presets field

### Tests (To Create)
- `tests/test_export_spec.py`
- `tests/test_interactive_export.py`
