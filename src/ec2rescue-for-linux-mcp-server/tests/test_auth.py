# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the auth module."""

import pytest
from unittest.mock import patch

from awslabs.ec2rescue_for_linux_mcp_server.auth import (
    get_auth_type_from_env,
    get_server_auth,
)


class TestGetAuthTypeFromEnv:
    """Tests for get_auth_type_from_env."""

    def test_returns_none_when_not_set(self):
        """Should return None when AUTH_TYPE is not set."""
        with patch.dict('os.environ', {}, clear=True):
            assert get_auth_type_from_env() is None

    def test_returns_no_auth(self):
        """Should return 'no-auth' when AUTH_TYPE=no-auth."""
        with patch.dict('os.environ', {'AUTH_TYPE': 'no-auth'}):
            assert get_auth_type_from_env() == 'no-auth'

    def test_returns_oauth(self):
        """Should return 'oauth' when AUTH_TYPE=oauth."""
        with patch.dict('os.environ', {'AUTH_TYPE': 'oauth'}):
            assert get_auth_type_from_env() == 'oauth'

    def test_case_insensitive(self):
        """Should handle case-insensitive values."""
        with patch.dict('os.environ', {'AUTH_TYPE': 'OAuth'}):
            assert get_auth_type_from_env() == 'oauth'

    def test_strips_whitespace(self):
        """Should strip whitespace from value."""
        with patch.dict('os.environ', {'AUTH_TYPE': '  no-auth  '}):
            assert get_auth_type_from_env() == 'no-auth'

    def test_raises_on_invalid_value(self):
        """Should raise ValueError for invalid AUTH_TYPE values."""
        with patch.dict('os.environ', {'AUTH_TYPE': 'basic'}):
            with pytest.raises(ValueError, match='must be "no-auth" or "oauth"'):
                get_auth_type_from_env()


class TestGetServerAuth:
    """Tests for get_server_auth."""

    def test_stdio_returns_none(self):
        """Should return (None, None) for stdio transport."""
        auth_settings, token_verifier = get_server_auth('stdio')
        assert auth_settings is None
        assert token_verifier is None

    def test_streamable_http_requires_auth_type(self):
        """Should raise when AUTH_TYPE is not set for streamable-http."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match='AUTH_TYPE environment variable must be set'):
                get_server_auth('streamable-http')

    def test_streamable_http_no_auth(self):
        """Should return (None, None) when AUTH_TYPE=no-auth."""
        with patch.dict('os.environ', {'AUTH_TYPE': 'no-auth'}):
            auth_settings, token_verifier = get_server_auth('streamable-http')
            assert auth_settings is None
            assert token_verifier is None

    def test_streamable_http_oauth_missing_issuer(self):
        """Should raise when AUTH_TYPE=oauth but AUTH_ISSUER is missing."""
        with patch.dict('os.environ', {'AUTH_TYPE': 'oauth'}, clear=True):
            with pytest.raises(ValueError, match='AUTH_ISSUER and AUTH_JWKS_URI'):
                get_server_auth('streamable-http')

    def test_streamable_http_oauth_missing_jwks_uri(self):
        """Should raise when AUTH_TYPE=oauth but AUTH_JWKS_URI is missing."""
        env = {'AUTH_TYPE': 'oauth', 'AUTH_ISSUER': 'https://example.com'}
        with patch.dict('os.environ', env, clear=True):
            with pytest.raises(ValueError, match='AUTH_ISSUER and AUTH_JWKS_URI'):
                get_server_auth('streamable-http')

    def test_streamable_http_oauth_configured(self):
        """Should return auth settings and verifier when fully configured."""
        env = {
            'AUTH_TYPE': 'oauth',
            'AUTH_ISSUER': 'https://auth.example.com',
            'AUTH_JWKS_URI': 'https://auth.example.com/.well-known/jwks.json',
        }
        with patch.dict('os.environ', env, clear=True):
            auth_settings, token_verifier = get_server_auth('streamable-http')
            assert auth_settings is not None
            assert str(auth_settings.issuer_url) == 'https://auth.example.com/'
            assert token_verifier is not None

    def test_streamable_http_oauth_with_audience(self):
        """Should configure audience when AUTH_AUDIENCE is set."""
        env = {
            'AUTH_TYPE': 'oauth',
            'AUTH_ISSUER': 'https://auth.example.com',
            'AUTH_JWKS_URI': 'https://auth.example.com/.well-known/jwks.json',
            'AUTH_AUDIENCE': 'ec2rescue-mcp',
        }
        with patch.dict('os.environ', env, clear=True):
            auth_settings, token_verifier = get_server_auth('streamable-http')
            assert auth_settings is not None
            assert token_verifier is not None
            # Verify audience is stored in verifier
            assert token_verifier._audience == 'ec2rescue-mcp'
