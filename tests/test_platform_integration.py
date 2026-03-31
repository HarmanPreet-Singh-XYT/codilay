"""
Tests for platform integration (auth commands and sync).
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from codilay.platform_client import PlatformClient
from codilay.platform_settings import PlatformSettings


@pytest.fixture
def temp_settings_file(tmp_path, monkeypatch):
    """Override settings file location for tests."""
    settings_dir = tmp_path / ".codilay"
    settings_file = settings_dir / "settings.json"
    settings_dir.mkdir(parents=True, exist_ok=True)

    # Monkey-patch the settings module to use temp location
    import codilay.platform_settings

    monkeypatch.setattr(codilay.platform_settings, "SETTINGS_DIR", settings_dir)
    monkeypatch.setattr(codilay.platform_settings, "SETTINGS_FILE", settings_file)

    return settings_file


class TestPlatformSettings:
    """Test PlatformSettings class."""

    def test_default_settings(self, temp_settings_file):
        """Test default settings are created."""
        settings = PlatformSettings.load()
        assert settings.api_key is None
        assert settings.api_url == "http://localhost:8000"
        assert settings.proxy_url == "http://localhost:8001"
        assert settings.org_slug is None
        assert settings.sync is True

    def test_save_and_load(self, temp_settings_file):
        """Test saving and loading settings."""
        settings = PlatformSettings()
        settings.api_key = "cdk_test123456789"
        settings.org_slug = "test-org"
        settings.sync = False
        settings.save()

        # Load and verify
        loaded = PlatformSettings.load()
        assert loaded.api_key == "cdk_test123456789"
        assert loaded.org_slug == "test-org"
        assert loaded.sync is False

    def test_is_logged_in(self, temp_settings_file):
        """Test login status check."""
        settings = PlatformSettings()
        assert not settings.is_logged_in()

        settings.api_key = "invalid_key"
        assert not settings.is_logged_in()

        settings.api_key = "cdk_valid_key"
        assert settings.is_logged_in()

    def test_clear(self, temp_settings_file):
        """Test clearing credentials."""
        settings = PlatformSettings()
        settings.api_key = "cdk_test123"
        settings.org_slug = "test-org"
        settings.save()

        settings.clear()
        assert settings.api_key is None
        assert settings.org_slug is None

    def test_mask_key(self):
        """Test API key masking."""
        # The mask_key function shows first 12 chars, then masks the rest
        assert PlatformSettings.mask_key("cdk_abcdefghijklmnop") == "cdk_abcdefgh••••••••"
        assert PlatformSettings.mask_key("short") == "****"
        assert PlatformSettings.mask_key("") == "****"

    def test_merge_with_existing_settings(self, temp_settings_file):
        """Test that platform settings merge with existing settings file."""
        # Write existing settings
        temp_settings_file.write_text(
            json.dumps(
                {
                    "api_keys": {"anthropic": "sk-ant-test"},
                    "default_provider": "anthropic",
                    "verbose": True,
                }
            )
        )

        # Save platform settings
        settings = PlatformSettings()
        settings.api_key = "cdk_test"
        settings.save()

        # Load and verify both are present
        data = json.loads(temp_settings_file.read_text())
        assert data["api_keys"]["anthropic"] == "sk-ant-test"
        assert data["default_provider"] == "anthropic"
        assert data["verbose"] is True
        assert data["platform_api_key"] == "cdk_test"


class TestPlatformClient:
    """Test PlatformClient class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock platform settings."""
        settings = PlatformSettings()
        settings.api_key = "cdk_test123456789"
        settings.api_url = "http://localhost:8000"
        settings.proxy_url = "http://localhost:8001"
        settings.org_slug = "test-org"
        return settings

    def test_validate_api_key_format(self, mock_settings):
        """Test API key format validation."""
        client = PlatformClient(mock_settings)

        is_valid, error = client.validate_api_key("invalid_key")
        assert not is_valid
        assert "must start with 'cdk_'" in error

    @patch("httpx.Client")
    def test_validate_api_key_success(self, mock_httpx, mock_settings):
        """Test successful API key validation."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_httpx.return_value = mock_client

        client = PlatformClient(mock_settings)
        is_valid, error = client.validate_api_key("cdk_valid_key")

        assert is_valid
        assert error is None

    @patch("httpx.Client")
    def test_validate_api_key_invalid(self, mock_httpx, mock_settings):
        """Test invalid API key validation."""
        # Mock HTTP response - 401 Unauthorized
        mock_response = Mock()
        mock_response.status_code = 401
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_httpx.return_value = mock_client

        client = PlatformClient(mock_settings)
        is_valid, error = client.validate_api_key("cdk_invalid_key")

        assert not is_valid
        assert "Invalid API key" in error

    @patch("httpx.Client")
    def test_validate_api_key_no_credits(self, mock_httpx, mock_settings):
        """Test API key validation when no credits remain."""
        # Mock HTTP response - 403 Forbidden
        mock_response = Mock()
        mock_response.status_code = 403
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_httpx.return_value = mock_client

        client = PlatformClient(mock_settings)
        is_valid, error = client.validate_api_key("cdk_no_credits")

        assert not is_valid
        assert "No credits" in error or "deactivated" in error

    @patch("httpx.Client")
    def test_check_health(self, mock_httpx, mock_settings):
        """Test health check."""
        # Mock successful health responses
        mock_responses = [Mock(status_code=200), Mock(status_code=200)]
        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.side_effect = mock_responses
        mock_httpx.return_value = mock_client

        client = PlatformClient(mock_settings)
        proxy_healthy, api_healthy = client.check_health()

        assert proxy_healthy
        assert api_healthy

    @patch("httpx.Client")
    def test_sync_run_success(self, mock_httpx, mock_settings, tmp_path):
        """Test successful run sync."""
        # Create test files
        codebase_md = tmp_path / "CODEBASE.md"
        codebase_md.write_text("# Test Documentation")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "run-123",
            "repo_id": "repo-456",
            "status": "completed",
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_httpx.return_value = mock_client

        client = PlatformClient(mock_settings)
        result = client.sync_run(
            org_slug="test-org",
            repo_slug="test-repo",
            codebase_md_path=codebase_md,
            commit_sha="abc123",
            branch="main",
        )

        assert result["id"] == "run-123"
        assert result["status"] == "completed"

    @patch("httpx.Client")
    def test_sync_run_unauthorized(self, mock_httpx, mock_settings, tmp_path):
        """Test sync run with unauthorized error."""
        codebase_md = tmp_path / "CODEBASE.md"
        codebase_md.write_text("# Test")

        # Mock 401 response
        from httpx import HTTPStatusError, Request, Response

        mock_response = Response(401, request=Request("POST", "http://test"))
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.side_effect = HTTPStatusError(
            "Unauthorized", request=mock_response.request, response=mock_response
        )
        mock_httpx.return_value = mock_client

        client = PlatformClient(mock_settings)

        with pytest.raises(Exception) as exc_info:
            client.sync_run(
                org_slug="test-org",
                repo_slug="test-repo",
                codebase_md_path=codebase_md,
            )

        assert "Authentication failed" in str(exc_info.value)

    def test_sync_run_missing_file(self, mock_settings, tmp_path):
        """Test sync run with missing CODEBASE.md."""
        client = PlatformClient(mock_settings)

        with pytest.raises(FileNotFoundError):
            client.sync_run(
                org_slug="test-org",
                repo_slug="test-repo",
                codebase_md_path=tmp_path / "nonexistent.md",
            )

    def test_sync_run_no_api_key(self, tmp_path):
        """Test sync run without API key."""
        settings = PlatformSettings()
        settings.api_key = None

        codebase_md = tmp_path / "CODEBASE.md"
        codebase_md.write_text("# Test")

        client = PlatformClient(settings)

        with pytest.raises(ValueError) as exc_info:
            client.sync_run(
                org_slug="test-org",
                repo_slug="test-repo",
                codebase_md_path=codebase_md,
            )

        assert "No API key configured" in str(exc_info.value)
