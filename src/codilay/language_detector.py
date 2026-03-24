"""
Language detection and import pattern cache.

Two-layer approach:
  1. Built-in EXTENSION_MAP + BUILTIN_PATTERNS: handles all common languages
     instantly — zero LLM calls, zero latency.
  2. Unknown extensions: one LLM call per *language* (not per file), result
     cached permanently to ~/.codilay/language_patterns.json.
     Second project using the same language → cache hit, no LLM.

The cache maps language name → {extensions, import_patterns, uses_file_paths}.
Regex patterns are stored as strings and compiled on load.
"""

import json
import os
import re
from typing import Dict, List, Optional

# ── Built-in extension → language mapping ────────────────────────────────────

EXTENSION_MAP: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".rake": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".hs": "haskell",
    ".lhs": "haskell",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".jl": "julia",
    ".vue": "vue",
    ".svelte": "svelte",
    ".nim": "nim",
    ".zig": "zig",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".elm": "elm",
    ".purs": "purescript",
    ".fs": "fsharp",
    ".fsx": "fsharp",
}

# ── Built-in patterns for languages already handled by DependencyGraph ────────
# These are fallback patterns used by LanguageDetector when the caller wants
# a unified pattern-based API. DependencyGraph still uses its own hand-tuned
# extractors for these languages (more accurate for edge cases).

BUILTIN_PATTERNS: Dict[str, List[str]] = {
    "python": [
        r"^\s*from\s+(\.{0,3}[\w.]*)\s+import",
        r"^\s*import\s+([\w.,\s]+)",
    ],
    "javascript": [
        r"""(?:import\s+.*?from\s+|import\s+)['"]([^'"]+)['"]""",
        r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
        r"""export\s+.*?from\s+['"]([^'"]+)['"]""",
    ],
    "typescript": [
        r"""(?:import\s+.*?from\s+|import\s+)['"]([^'"]+)['"]""",
        r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
        r"""export\s+.*?from\s+['"]([^'"]+)['"]""",
    ],
    "go": [
        r'^\s*import\s+"([^"]+)"',
        r'"([^"]+)"',  # inside grouped import block
    ],
    "rust": [
        r"^\s*(?:use|mod)\s+([\w:]+)",
    ],
    "java": [
        r"^\s*import\s+(?:static\s+)?([\w.]+)",
    ],
    "kotlin": [
        r"^\s*import\s+([\w.]+)",
    ],
    "swift": [
        r"^\s*import\s+([\w.]+)",
    ],
    "dart": [
        r"""^\s*import\s+['"]([^'"]+)['"]""",
        r"""^\s*export\s+['"]([^'"]+)['"]""",
        r"""^\s*part\s+['"]([^'"]+)['"]""",
        r"""^\s*part\s+of\s+['"]([^'"]+)['"]""",
    ],
    "ruby": [
        r"""^\s*require(?:_relative)?\s+['"]([^'"]+)['"]""",
    ],
    "php": [
        r"""^\s*(?:use|require|require_once|include|include_once)\s+['"]?([^\s;'"]+)""",
    ],
    "elixir": [
        r"^\s*(?:import|alias|use)\s+([\w.]+)",
    ],
    "c": [
        r'^\s*#\s*include\s*["<]([^">]+)[">]',
    ],
    "cpp": [
        r'^\s*#\s*include\s*["<]([^">]+)[">]',
    ],
    "csharp": [
        r"^\s*using\s+([\w.]+)",
    ],
    "lua": [
        r"""^\s*(?:require|dofile|loadfile)\s*\(?['"]([^'"]+)['"]""",
    ],
    "r": [
        r"""^\s*(?:library|require|source)\s*\(\s*['"]?([^'",\s)]+)""",
    ],
    "nim": [
        r"^\s*import\s+([\w.,/]+)",
        r"^\s*include\s+([\w.,/]+)",
    ],
    "julia": [
        r"^\s*(?:using|import)\s+([\w.,]+)",
    ],
    "elm": [
        r"^\s*import\s+([\w.]+)",
    ],
}


class LanguageDetector:
    """
    Detects languages from file extensions and provides import extraction
    patterns. Learns unknown languages via one LLM call per language, cached
    permanently.
    """

    CACHE_PATH = os.path.expanduser("~/.codilay/language_patterns.json")

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._cache: Dict[str, Dict] = {}
        self._load_cache()

    # ── Public API ───────────────────────────────────────────────────────────

    def get_language(self, ext: str) -> Optional[str]:
        """Return the language name for a file extension, or None if unknown."""
        return EXTENSION_MAP.get(ext.lower())

    def has_builtin_extractor(self, ext: str) -> bool:
        """True if DependencyGraph has a hand-tuned extractor for this extension."""
        hand_tuned = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".mjs",
            ".cjs",
            ".vue",
            ".svelte",
            ".go",
            ".rs",
            ".java",
            ".kt",
            ".kts",
            ".scala",
            ".c",
            ".h",
            ".cpp",
            ".hpp",
            ".cc",
            ".cxx",
            ".rb",
            ".rake",
            ".php",
            ".ex",
            ".exs",
        }
        return ext.lower() in hand_tuned

    def get_import_patterns(self, ext: str) -> List[re.Pattern]:
        """
        Return compiled regex patterns for import extraction.
        Order of preference:
          1. Cache (from a previous LLM call)
          2. BUILTIN_PATTERNS
          3. Empty list (unknown language, no LLM client)
        """
        language = self.get_language(ext)
        if not language:
            return []

        # Check cache first (LLM-learned patterns override built-ins for obscure langs)
        if language in self._cache:
            return [re.compile(p, re.MULTILINE) for p in self._cache[language].get("import_patterns", [])]

        # Built-in patterns
        if language in BUILTIN_PATTERNS:
            return [re.compile(p, re.MULTILINE) for p in BUILTIN_PATTERNS[language]]

        return []

    def extract_imports(self, ext: str, content: str) -> List[str]:
        """
        Extract raw import strings from file content using stored patterns.
        Only used for languages NOT already handled by DependencyGraph's
        hand-tuned extractors.
        """
        imports: List[str] = []
        for pattern in self.get_import_patterns(ext):
            for m in pattern.finditer(content):
                val = m.group(1).strip()
                if val:
                    imports.append(val)
        return imports

    def learn_unknown_languages(
        self,
        unknown_exts_with_samples: Dict[str, str],
    ) -> Dict[str, List[str]]:
        """
        For each unknown extension, ask the LLM for import patterns.
        Groups extensions by language to avoid duplicate calls (.ex and .exs
        are both Elixir — one call covers both).

        Args:
            unknown_exts_with_samples: {ext: sample_file_content}

        Returns:
            {ext: [pattern_strings]} for newly learned languages.
        """
        if not self.llm:
            return {}

        # Group by language so .ex and .exs only produce one LLM call
        lang_to_exts: Dict[str, List[str]] = {}
        lang_to_sample: Dict[str, str] = {}
        for ext, sample in unknown_exts_with_samples.items():
            lang = self.get_language(ext)
            if not lang:
                # Truly unknown extension — skip for now (triage handles these)
                continue
            if lang not in self._cache and lang not in BUILTIN_PATTERNS:
                lang_to_exts.setdefault(lang, []).append(ext)
                if lang not in lang_to_sample:
                    lang_to_sample[lang] = sample[:1500]  # first 1500 chars is enough

        if not lang_to_exts:
            return {}

        learned: Dict[str, List[str]] = {}
        for lang, exts in lang_to_exts.items():
            sample = lang_to_sample.get(lang, "")
            patterns = self._ask_llm_for_patterns(lang, sample)
            if patterns:
                self._cache[lang] = {
                    "extensions": exts,
                    "import_patterns": patterns,
                    "learned_at": __import__("datetime").datetime.now().isoformat(),
                }
                for ext in exts:
                    learned[ext] = patterns

        if learned:
            self._save_cache()

        return learned

    # ── LLM pattern learning ─────────────────────────────────────────────────

    def _ask_llm_for_patterns(self, language: str, sample_content: str) -> List[str]:
        """Ask the LLM for import statement regex patterns for a language."""
        prompt = (
            f"You are a static code analyzer. For the programming language '{language}', "
            "provide regex patterns that match import/dependency statements.\n\n"
            f"Sample file content:\n```\n{sample_content}\n```\n\n"
            "Return a JSON object with exactly this structure:\n"
            '{"import_patterns": ["pattern1", "pattern2"], "uses_file_paths": true|false}\n\n'
            "Rules:\n"
            "- Each pattern must be a Python regex string (re.MULTILINE is applied)\n"
            "- Each pattern must have exactly one capture group that extracts the imported path/module\n"
            "- Include all import statement forms for this language\n"
            "- Return ONLY the JSON object, no other text"
        )

        try:
            response = self.llm.call(
                "You are a regex expert for static code analysis. Return only valid JSON.",
                prompt,
                json_mode=False,
            )
            answer = response.get("answer", "") if isinstance(response, dict) else str(response)

            # Extract JSON from response
            start = answer.find("{")
            end = answer.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(answer[start:end])
                patterns = data.get("import_patterns", [])
                # Validate each pattern compiles
                valid = []
                for p in patterns:
                    try:
                        re.compile(p, re.MULTILINE)
                        valid.append(p)
                    except re.error:
                        pass
                return valid
        except Exception:
            pass

        return []

    # ── Cache management ─────────────────────────────────────────────────────

    def _load_cache(self):
        if os.path.exists(self.CACHE_PATH):
            try:
                with open(self.CACHE_PATH, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self):
        os.makedirs(os.path.dirname(self.CACHE_PATH), exist_ok=True)
        with open(self.CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)

    def get_cache_stats(self) -> Dict:
        return {
            "cached_languages": list(self._cache.keys()),
            "builtin_languages": list(BUILTIN_PATTERNS.keys()),
            "cache_path": self.CACHE_PATH,
        }
