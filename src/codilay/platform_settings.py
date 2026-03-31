"""
Platform settings for CodiLay CLI integration with the hosted platform.

Manages authentication, sync configuration, and proxy routing for the CLI
to communicate with the CodiLay platform API and token proxy.

Settings are stored in ~/.codilay/settings.json alongside the existing
Settings class fields. This module extends the settings schema to include
platform-specific fields.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Use the same directory as the existing Settings class
SETTINGS_DIR = Path.home() / ".codilay"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class PlatformSettings:
    """Platform-specific settings for CLI integration."""

    # Primary credential for platform API and token proxy
    api_key: Optional[str] = None

    # Base URL for the CodiLay platform API
    api_url: str = "https://api.codilay.com"

    # User's default organization slug (optional — org is resolved from token on backend)
    org_slug: Optional[str] = None

    # Whether to sync docs to platform after each run
    sync_enabled: bool = True

    # Whether to route LLM calls through the token proxy when no local key is set
    token_proxy_enabled: bool = True

    @property
    def proxy_url(self) -> str:
        """Token proxy URL — always derived from api_url."""
        return f"{self.api_url}/api/llm"

    @classmethod
    def load(cls) -> "PlatformSettings":
        """Load platform settings from the shared settings.json file."""
        if not SETTINGS_FILE.exists():
            return cls()

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract only the platform-specific fields.
            # Backward-compat: old keys used "platform_sync" and "platform_proxy_url".
            platform_data = {
                "api_key": data.get("platform_api_key"),
                "api_url": data.get("platform_api_url", "https://api.codilay.com"),
                "org_slug": data.get("platform_org_slug"),
                # Prefer new key, fall back to old "platform_sync" key
                "sync_enabled": data.get("platform_sync_enabled", data.get("platform_sync", True)),
                "token_proxy_enabled": data.get("platform_token_proxy_enabled", True),
            }

            return cls(**platform_data)
        except (json.JSONDecodeError, TypeError):
            return cls()

    def save(self) -> None:
        """
        Save platform settings to the shared settings.json file.

        This merges platform settings with existing settings to avoid
        overwriting the existing Settings class data.
        """
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing data
        existing_data = {}
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, TypeError):
                pass

        # Remove stale keys from older schema
        existing_data.pop("platform_proxy_url", None)
        existing_data.pop("platform_sync", None)

        # Merge platform settings with existing data
        existing_data.update(
            {
                "platform_api_key": self.api_key,
                "platform_api_url": self.api_url,
                "platform_org_slug": self.org_slug,
                "platform_sync_enabled": self.sync_enabled,
                "platform_token_proxy_enabled": self.token_proxy_enabled,
            }
        )

        # Write atomically
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2)

    def is_logged_in(self) -> bool:
        """Check if user has a valid platform API key configured."""
        return bool(self.api_key and self.api_key.startswith("cdk_"))

    def clear(self) -> None:
        """Clear platform authentication (logout)."""
        self.api_key = None
        self.org_slug = None
        self.save()

    @staticmethod
    def mask_key(key: str) -> str:
        """Return a masked version of an API key for display."""
        if not key or len(key) < 10:
            return "****"
        return key[:12] + "•" * (len(key) - 12)
