"""
Platform API client for CodiLay CLI integration.

Handles authentication validation, sync operations, and communication
with the CodiLay platform API and token proxy.
"""

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

    def _auth_headers(self, api_key: Optional[str] = None) -> Dict[str, str]:
        """Return authorization headers for platform API requests."""
        key = api_key or self.settings.api_key
        return {"Authorization": f"Bearer {key}"}

    def validate_api_key(self, api_key: str) -> tuple[bool, Optional[str]]:
        """
        Validate a CodiLay API key by calling GET /api/auth/me.

        Returns:
            (is_valid, error_message) tuple
        """
        if not api_key.startswith("cdk_"):
            return False, "Invalid API key format. Key must start with 'cdk_'"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.settings.api_url}/api/auth/me",
                    headers=self._auth_headers(api_key),
                )

                if response.status_code == 200:
                    return True, None
                elif response.status_code == 401:
                    return False, "Invalid API key"
                elif response.status_code == 403:
                    return False, "No credits remaining or account deactivated"
                else:
                    return False, f"Unexpected response: {response.status_code}"

        except httpx.ConnectError:
            return False, f"Could not connect to platform at {self.settings.api_url}"
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
                # Check token proxy health
                try:
                    resp = client.get(f"{self.settings.proxy_url}/health")
                    proxy_healthy = resp.status_code == 200
                except Exception:
                    pass

                # Check platform API health
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
        repo_slug: str,
        codebase_md_path: Path,
        commit_sha: Optional[str] = None,
        branch: Optional[str] = None,
        links_json_path: Optional[Path] = None,
        state_json_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Upload a completed run to the platform via POST /api/sync.

        Args:
            repo_slug: Repository slug (derived from directory name)
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

        if not codebase_md_path.exists():
            raise FileNotFoundError(f"CODEBASE.md not found at {codebase_md_path}")

        # Build files dict with file contents as strings (JSON body, not multipart)
        files: Dict[str, Optional[str]] = {
            "codebase_md": codebase_md_path.read_text(encoding="utf-8"),
            "links_json": links_json_path.read_text(encoding="utf-8")
            if links_json_path and links_json_path.exists()
            else None,
            "state_json": state_json_path.read_text(encoding="utf-8")
            if state_json_path and state_json_path.exists()
            else None,
        }

        body: Dict[str, Any] = {
            "repo_slug": repo_slug,
            "files": {k: v for k, v in files.items() if v is not None},
        }
        if commit_sha:
            body["commit_sha"] = commit_sha
        if branch:
            body["branch"] = branch

        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                response = client.post(
                    f"{self.settings.api_url}/api/sync",
                    json=body,
                    headers=self._auth_headers(),
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("Authentication failed. Your API key may be invalid.")
            elif e.response.status_code == 403:
                raise Exception("Permission denied. Check your plan limits.")
            elif e.response.status_code == 404:
                raise Exception("Sync endpoint not found. Check your platform URL.")
            else:
                raise Exception(f"Sync failed with status {e.response.status_code}: {e.response.text}")
        except httpx.ConnectError:
            raise Exception(f"Could not connect to platform API at {self.settings.api_url}")
        except httpx.TimeoutException:
            raise Exception("Sync request timed out")
        except Exception as e:
            raise Exception(f"Sync error: {str(e)}")
