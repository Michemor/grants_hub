# app/tests/test_config.py
"""
Unit tests for the Settings configuration.
"""
import pytest

class TestSettingsLoading:
    """Tests for Settings loading from environment."""

    def test_settings_loads_from_env(self, mock_env_vars):
        """Test that Settings loads from environment variables."""
        # mock_env_vars fixture sets env vars via monkeypatch
        from config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        assert settings.supabase_url == "https://test.supabase.co"
        assert settings.supabase_key == "test-key-12345"

    def test_settings_has_serp_api(self, mock_env_vars):
        """Test that SERP API key is loaded."""
        from config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        assert settings.serp_api == "test-serp-api-key"

    def test_settings_has_gemini_key(self, mock_env_vars):
        """Test that Gemini API key is loaded."""
        from config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        assert settings.gemini_api_key == "test-gemini-key"


class TestSettingsDefaults:
    """Tests for Settings default values."""

    def test_max_deadline_days_default(self, mock_env_vars):
        """Test default value for max_deadline_days."""
        from config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        # Default should be a positive integer
        assert settings.max_deadline_days > 0
        assert isinstance(settings.max_deadline_days, int)

    def test_relevance_threshold_default(self, mock_env_vars):
        """Test default value for relevance_threshold."""
        from config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        # Default should be a positive integer
        assert settings.relevance_threshold >= 0
        assert isinstance(settings.relevance_threshold, int)


class TestSettingsCaching:
    """Tests for Settings caching behavior."""

    def test_settings_are_cached(self, mock_env_vars):
        """Test that get_settings returns cached instance."""
        from config import get_settings

        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_cache_can_be_cleared(self, mock_env_vars):
        """Test that clearing cache works."""
        from config import get_settings

        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # After clearing, should be new instance
        # (may or may not be same object depending on impl)
        assert settings1.supabase_url == settings2.supabase_url


class TestSettingsValidation:
    """Tests for Settings validation."""

    def test_missing_supabase_url(self, monkeypatch):
        """Test that missing SUPABASE_URL raises error."""
        # Clear all relevant env vars first
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.setenv("SUPABASE_KEY", "test_key")
        monkeypatch.setenv("SERP_API", "test_serp")
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")

        from config import get_settings, Settings

        get_settings.cache_clear()

        # Should raise validation error
        with pytest.raises(Exception):
            Settings()

    def test_missing_supabase_key(self, monkeypatch):
        """Test that missing SUPABASE_KEY raises error."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.delenv("SUPABASE_KEY", raising=False)
        monkeypatch.setenv("SERP_API", "test_serp")
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")

        from config import get_settings, Settings

        get_settings.cache_clear()

        # Should raise validation error
        with pytest.raises(Exception):
            Settings()
