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

"""Tests for the consts module."""

from awslabs.ec2_rescue_mcp_server.consts import (
    DEFAULT_AWS_REGION,
    SERVER_INSTRUCTIONS,
    SERVER_NAME,
    SSM_COMMAND_TIMEOUT_SECONDS,
    SSM_DOCUMENT_NAME,
    SSM_POLL_INTERVAL_SECONDS,
)


class TestSsmConstants:
    """Tests for SSM configuration constants."""

    def test_document_name(self):
        """Document name is AWS-RunShellScript."""
        assert SSM_DOCUMENT_NAME == 'AWS-RunShellScript'

    def test_timeout_is_positive(self):
        """Command timeout is positive."""
        assert SSM_COMMAND_TIMEOUT_SECONDS > 0

    def test_poll_interval_is_positive(self):
        """Poll interval is positive."""
        assert SSM_POLL_INTERVAL_SECONDS > 0


class TestServerMetadata:
    """Tests for server metadata constants."""

    def test_server_name(self):
        """Server name matches expected value."""
        assert SERVER_NAME == 'awslabs.ec2-rescue-mcp-server'

    def test_default_region(self):
        """Default region is us-east-1."""
        assert DEFAULT_AWS_REGION == 'us-east-1'

    def test_instructions_not_empty(self):
        """Server instructions are not empty."""
        assert len(SERVER_INSTRUCTIONS.strip()) > 0

    def test_instructions_mentions_tools(self):
        """Server instructions reference all tool names."""
        assert 'list_instances' in SERVER_INSTRUCTIONS
        assert 'run_ec2rl_dmesg' in SERVER_INSTRUCTIONS
        assert 'run_ec2rl_top' in SERVER_INSTRUCTIONS
