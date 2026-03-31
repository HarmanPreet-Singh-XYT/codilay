"""
Platform API client for CodiLay CLI integration.

Handles authentication validation, sync operations, and communication
with the CodiLay platform API and token proxy.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from codilay.platform_settings import PlatformSettings


class PlatformClient:
    """Client for interacting with CodiLay platform services."""

    def __init__(self, settings: PlatformSettings):
        """Initialize the platform client with settings."""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for platform integration. Install with: pip install httpx")
        self.settings = settings
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def validate_api_key(self, api_key: str) -> tuple[bool, Optional[str]]:
        """
        Validate a CodiLay API key by making a test request to the token proxy.

        Returns:
            (is_valid, error_message) tuple
        """
        if not api_key.startswith("cdk_"):
            return False, "Invalid API key format. Key must start with 'cdk_'"

        try:
            # Make a minimal test request to the proxy
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.settings.proxy_url}/v1/messages",
                    headers={
                        "X-CodiLay-API-Key": api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )

                # 200 = valid response, 4xx from Anthropic API = key works but request issue
                if response.status_code == 200 or 400 <= response.status_code < 500:
                    # Check if it's an auth error specifically
                    if response.status_code == 401:
                        return False, "Invalid API key"
                    elif response.status_code == 403:
                        return False, "No credits remaining or account deactivated"
                    # Any other response means the key authenticated successfully
                    return True, None

                return False, f"Unexpected response: {response.status_code}"

        except httpx.ConnectError:
            return False, f"Could not connect to proxy at {self.settings.proxy_url}"
        except httpx.TimeoutException:
            return False, "Request timed out"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def check_health(self) -> tuple[bool, bool]:
        """
        Check health of platform services.

        Returns:
            (proxy_healthy, api_healthy) tuple
        """
        proxy_healthy = False
        api_healthy = False

        try:
            with httpx.Client(timeout=self.timeout) as client:
                # Check proxy
                try:
                    resp = client.get(f"{self.settings.proxy_url}/health")
                    proxy_healthy = resp.status_code == 200
                except Exception:
                    pass

                # Check platform API
                try:
                    resp = client.get(f"{self.settings.api_url}/health")
                    api_healthy = resp.status_code == 200
                except Exception:
                    pass

        except Exception:
            pass

        return proxy_healthy, api_healthy

    def sync_run(
        self,
        org_slug: str,
        repo_slug: str,
        codebase_md_path: Path,
        commit_sha: Optional[str] = None,
        branch: Optional[str] = None,
        links_json_path: Optional[Path] = None,
        state_json_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Upload a completed run to the platform.

        Args:
            org_slug: Organization slug
            repo_slug: Repository slug
            codebase_md_path: Path to CODEBASE.md file
            commit_sha: Git commit SHA (optional)
            branch: Git branch name (optional)
            links_json_path: Path to links.json (optional)
            state_json_path: Path to state.json (optional)

        Returns:
            Run metadata dict from the API response

        Raises:
            Exception: On sync failure
        """
        if not self.settings.api_key:
            raise ValueError("No API key configured. Run 'codilay auth login' first.")

        # Prepare form data
        files = {}
        data = {
            "org_slug": org_slug,
            "repo_slug": repo_slug,
        }

        if commit_sha:
            data["commit_sha"] = commit_sha
        if branch:
            data["branch"] = branch

        # Add files
        if not codebase_md_path.exists():
            raise FileNotFoundError(f"CODEBASE.md not found at {codebase_md_path}")

        files["codebase_md"] = ("CODEBASE.md", codebase_md_path.open("rb"), "text/markdown")

        if links_json_path and links_json_path.exists():
            files["links_json"] = ("links.json", links_json_path.open("rb"), "application/json")

        if state_json_path and state_json_path.exists():
            files["state_json"] = ("state.json", state_json_path.open("rb"), "application/json")

        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                response = client.post(
                    f"{self.settings.api_url}/api/sync/upload",
                    headers={
                        "X-CodiLay-API-Key": self.settings.api_key,
                    },
                    data=data,
                    files=files,
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("Authentication failed. Your API key may be invalid.")
            elif e.response.status_code == 403:
                raise Exception("Permission denied. Check your organization membership or plan limits.")
            elif e.response.status_code == 404:
                raise Exception(f"Organization '{org_slug}' not found.")
            else:
                raise Exception(f"Sync failed with status {e.response.status_code}: {e.response.text}")
        except httpx.ConnectError:
            raise Exception(f"Could not connect to platform API at {self.settings.api_url}")
        except httpx.TimeoutException:
            raise Exception("Sync request timed out")
        except Exception as e:
            raise Exception(f"Sync error: {str(e)}")
        finally:
            # Close file handles
            for file_obj in files.values():
                if hasattr(file_obj[1], "close"):
                    file_obj[1].close()
