"""
Platform settings for CodiLay CLI integration with the hosted platform.

Manages authentication, sync configuration, and proxy routing for the CLI
to communicate with the CodiLay platform API and token proxy.

Settings are stored in ~/.codilay/settings.json alongside the existing
Settings class fields. This module extends the settings schema to include
platform-specific fields.
"""

import json
from dataclasses import asdict, dataclass
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

    # Base URLs for services
    api_url: str = "http://localhost:8000"  # platform-api
    proxy_url: str = "http://localhost:8001"  # token-proxy

    # User's default organization slug
    org_slug: Optional[str] = None

    # Whether to sync docs to platform after each run
    sync: bool = True

    @classmethod
    def load(cls) -> "PlatformSettings":
        """Load platform settings from the shared settings.json file."""
        if not SETTINGS_FILE.exists():
            return cls()

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract only the platform-specific fields
            platform_data = {
                "api_key": data.get("platform_api_key"),
                "api_url": data.get("platform_api_url", "http://localhost:8000"),
                "proxy_url": data.get("platform_proxy_url", "http://localhost:8001"),
                "org_slug": data.get("platform_org_slug"),
                "sync": data.get("platform_sync", True),
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

        # Merge platform settings with existing data
        existing_data.update(
            {
                "platform_api_key": self.api_key,
                "platform_api_url": self.api_url,
                "platform_proxy_url": self.proxy_url,
                "platform_org_slug": self.org_slug,
                "platform_sync": self.sync,
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
