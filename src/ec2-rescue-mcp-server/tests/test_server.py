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

"""Tests for the EC2 Rescue MCP Server tools."""

import json
import pytest
from awslabs.ec2_rescue_mcp_server.server import (
    list_allowed_commands,
    list_instances,
    run_ec2rl_dmesg,
    run_ec2rl_top,
)
from unittest.mock import patch


class TestListInstances:
    """Tests for the list_instances tool."""

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.list_ssm_instances')
    async def test_returns_instances(self, mock_list, mock_ctx):
        """Should return JSON with instances."""
        mock_list.return_value = [
            {
                'instance_id': 'i-1234567890abcdef0',
                'name': 'test-instance',
                'platform': 'Linux',
                'ping_status': 'Online',
                'ip_address': '10.0.0.1',
                'instance_type': 't3.micro',
            }
        ]

        result = await list_instances(mock_ctx)
        data = json.loads(result)

        assert len(data['instances']) == 1
        assert data['instances'][0]['instance_id'] == 'i-1234567890abcdef0'
        assert data['instances'][0]['name'] == 'test-instance'

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.list_ssm_instances')
    async def test_returns_empty_list(self, mock_list, mock_ctx):
        """Should return empty instances with message when none found."""
        mock_list.return_value = []

        result = await list_instances(mock_ctx)
        data = json.loads(result)

        assert data['instances'] == []
        assert 'message' in data

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.list_ssm_instances')
    async def test_handles_exception(self, mock_list, mock_ctx):
        """Should call ctx.error and re-raise on exception."""
        mock_list.side_effect = Exception('AWS error')

        with pytest.raises(Exception, match='AWS error'):
            await list_instances(mock_ctx)

        mock_ctx.error.assert_called_once()


class TestRunEc2rlDmesg:
    """Tests for the run_ec2rl_dmesg tool."""

    EC2RL_RUN_STDOUT = (
        '-------------[Output  Logs]-------------\n'
        '\n'
        'The output logs are located in:\n'
        '/var/tmp/ec2rl/2026-04-14T02_50_34.749027\n'
        '\n'
        '--------------[Module Run]--------------\n'
    )

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_successful_run(self, mock_run, mock_ctx):
        """Should run ec2rl then cat the log and return log content."""
        mock_run.side_effect = [
            # First call: ec2rl run
            {
                'status': 'Success',
                'stdout': self.EC2RL_RUN_STDOUT,
                'stderr': '',
                'exit_code': 0,
            },
            # Second call: cat log file
            {
                'status': 'Success',
                'stdout': '[  0.000000] Linux version 5.10.0\n[  1.234567] EXT4-fs mounted',
                'stderr': '',
                'exit_code': 0,
            },
        ]

        result = await run_ec2rl_dmesg(mock_ctx, instance_id='i-1234567890abcdef0')
        data = json.loads(result)

        assert data['instance_id'] == 'i-1234567890abcdef0'
        assert data['module'] == 'dmesg'
        assert data['status'] == 'Success'
        assert data['output_dir'] == '/var/tmp/ec2rl/2026-04-14T02_50_34.749027'
        assert 'Linux version' in data['log_content']
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_failed_run(self, mock_run, mock_ctx):
        """Should return JSON with failure details without reading log."""
        mock_run.return_value = {
            'status': 'Failed',
            'stdout': '',
            'stderr': 'ec2rl not found',
            'exit_code': 127,
        }

        result = await run_ec2rl_dmesg(mock_ctx, instance_id='i-1234567890abcdef0')
        data = json.loads(result)

        assert data['status'] == 'Failed'
        assert data['stderr'] == 'ec2rl not found'
        assert data['log_content'] == ''
        assert mock_run.call_count == 1

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_parse_output_dir_failure(self, mock_run, mock_ctx):
        """Should return raw stdout when output dir cannot be parsed."""
        mock_run.return_value = {
            'status': 'Success',
            'stdout': 'unexpected output format',
            'stderr': '',
            'exit_code': 0,
        }

        result = await run_ec2rl_dmesg(mock_ctx, instance_id='i-1234567890abcdef0')
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert data['log_content'] == ''
        assert 'raw_stdout' in data
        assert mock_run.call_count == 1

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_handles_exception(self, mock_run, mock_ctx):
        """Should call ctx.error and re-raise on exception."""
        mock_run.side_effect = Exception('SSM error')

        with pytest.raises(Exception, match='SSM error'):
            await run_ec2rl_dmesg(mock_ctx, instance_id='i-1234567890abcdef0')

        mock_ctx.error.assert_called()


class TestRunEc2rlTop:
    """Tests for the run_ec2rl_top tool."""

    EC2RL_RUN_STDOUT = (
        '-------------[Output  Logs]-------------\n'
        '\n'
        'The output logs are located in:\n'
        '/var/tmp/ec2rl/2026-04-14T02_50_34.749027\n'
        '\n'
        '--------------[Module Run]--------------\n'
    )

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_successful_run(self, mock_run, mock_ctx):
        """Should run ec2rl then cat the log and return log content."""
        mock_run.side_effect = [
            # First call: ec2rl run
            {
                'status': 'Success',
                'stdout': self.EC2RL_RUN_STDOUT,
                'stderr': '',
                'exit_code': 0,
            },
            # Second call: cat log file
            {
                'status': 'Success',
                'stdout': 'top - 12:34:56 up 1 day,  2:34,  1 user,  load average: 0.00, 0.01, 0.05',
                'stderr': '',
                'exit_code': 0,
            },
        ]

        result = await run_ec2rl_top(mock_ctx, instance_id='i-1234567890abcdef0')
        data = json.loads(result)

        assert data['instance_id'] == 'i-1234567890abcdef0'
        assert data['module'] == 'top'
        assert data['status'] == 'Success'
        assert data['output_dir'] == '/var/tmp/ec2rl/2026-04-14T02_50_34.749027'
        assert 'load average' in data['log_content']
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_failed_run(self, mock_run, mock_ctx):
        """Should return JSON with failure details without reading log."""
        mock_run.return_value = {
            'status': 'Failed',
            'stdout': '',
            'stderr': 'ec2rl not found',
            'exit_code': 127,
        }

        result = await run_ec2rl_top(mock_ctx, instance_id='i-1234567890abcdef0')
        data = json.loads(result)

        assert data['status'] == 'Failed'
        assert data['stderr'] == 'ec2rl not found'
        assert data['log_content'] == ''
        assert mock_run.call_count == 1

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_parse_output_dir_failure(self, mock_run, mock_ctx):
        """Should return raw stdout when output dir cannot be parsed."""
        mock_run.return_value = {
            'status': 'Success',
            'stdout': 'unexpected output format',
            'stderr': '',
            'exit_code': 0,
        }

        result = await run_ec2rl_top(mock_ctx, instance_id='i-1234567890abcdef0')
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert data['log_content'] == ''
        assert 'raw_stdout' in data
        assert mock_run.call_count == 1

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.server.run_ssm_command')
    async def test_handles_exception(self, mock_run, mock_ctx):
        """Should call ctx.error and re-raise on exception."""
        mock_run.side_effect = Exception('SSM error')

        with pytest.raises(Exception, match='SSM error'):
            await run_ec2rl_top(mock_ctx, instance_id='i-1234567890abcdef0')

        mock_ctx.error.assert_called()


class TestListAllowedCommands:
    """Tests for the list_allowed_commands tool."""

    @pytest.mark.asyncio
    async def test_returns_commands(self, mock_ctx):
        """Should return JSON with allowed commands."""
        result = await list_allowed_commands(mock_ctx)
        data = json.loads(result)

        assert 'allowed_commands' in data
        assert 'ec2rl run --only-modules=dmesg' in data['allowed_commands']
        assert 'ec2rl run --only-modules=top --times=5' in data['allowed_commands']

    @pytest.mark.asyncio
    async def test_returns_non_empty_list(self, mock_ctx):
        """Should return at least one command."""
        result = await list_allowed_commands(mock_ctx)
        data = json.loads(result)

        assert len(data['allowed_commands']) > 0
