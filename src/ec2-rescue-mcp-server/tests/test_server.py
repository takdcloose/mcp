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
from awslabs.ec2_rescue_mcp_server import ec2rl as ec2rl_module
from awslabs.ec2_rescue_mcp_server.ec2rl import Ec2rlModule
from awslabs.ec2_rescue_mcp_server.execution import _run_ec2rl_module
from awslabs.ec2_rescue_mcp_server.server import list_instances
from unittest.mock import patch


# 'top' declares no `software`, so it skips the software precheck — keeping the
# run_ssm_command call count predictable (run + log-read = 2).
TOP = Ec2rlModule('top', 'mod_out/run/top.log', required_args=['times'])


@pytest.fixture()
def registered_top():
    """Register TOP in the global registry so validate_command accepts it.

    _run_ec2rl_module validates the built command against EC2RL_MODULES, which
    is empty until modules are loaded; snapshot and restore around the test.
    """
    prev = dict(ec2rl_module.EC2RL_MODULES)
    ec2rl_module.EC2RL_MODULES['top'] = TOP
    yield
    ec2rl_module.EC2RL_MODULES.clear()
    ec2rl_module.EC2RL_MODULES.update(prev)


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


class TestRunEc2rlModule:
    """Tests for _run_ec2rl_module (the impl behind dynamic run_ec2rl_* tools).

    Uses the 'top' module (no `software` field → no software precheck), so the
    SSM call sequence is exactly: ec2rl run, then cat the log.
    """

    EC2RL_RUN_STDOUT = (
        '-------------[Output  Logs]-------------\n'
        '\n'
        'The output logs are located in:\n'
        '/var/tmp/ec2rl/2026-04-14T02_50_34.749027\n'
        '\n'
        '--------------[Module Run]--------------\n'
    )

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_successful_run(self, mock_run, mock_ctx, registered_top):
        """Should run ec2rl then cat the log and return log content."""
        mock_run.side_effect = [
            {
                'status': 'Success',
                'stdout': self.EC2RL_RUN_STDOUT,
                'stderr': '',
                'exit_code': 0,
            },
            {
                'status': 'Success',
                'stdout': 'top - 12:34:56 up 1 day, load average: 0.00, 0.01, 0.05',
                'stderr': '',
                'exit_code': 0,
            },
        ]

        result = await _run_ec2rl_module(
            mock_ctx, 'i-1234567890abcdef0', TOP, args={'times': '1'}
        )
        data = json.loads(result)

        assert data['instance_id'] == 'i-1234567890abcdef0'
        assert data['module'] == 'top'
        assert data['status'] == 'Success'
        assert data['output_dir'] == '/var/tmp/ec2rl/2026-04-14T02_50_34.749027'
        assert 'load average' in data['log_content']
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_failed_run(self, mock_run, mock_ctx, registered_top):
        """Should return JSON with failure details without reading log."""
        mock_run.return_value = {
            'status': 'Failed',
            'stdout': '',
            'stderr': 'ec2rl not found',
            'exit_code': 127,
        }

        result = await _run_ec2rl_module(
            mock_ctx, 'i-1234567890abcdef0', TOP, args={'times': '1'}
        )
        data = json.loads(result)

        assert data['status'] == 'Failed'
        assert data['stderr'] == 'ec2rl not found'
        assert data['log_content'] == ''
        assert mock_run.call_count == 1

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_parse_output_dir_failure(self, mock_run, mock_ctx, registered_top):
        """Should return raw stdout when output dir cannot be parsed."""
        mock_run.return_value = {
            'status': 'Success',
            'stdout': 'unexpected output format',
            'stderr': '',
            'exit_code': 0,
        }

        result = await _run_ec2rl_module(
            mock_ctx, 'i-1234567890abcdef0', TOP, args={'times': '1'}
        )
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert data['log_content'] == ''
        assert 'raw_stdout' in data
        assert mock_run.call_count == 1

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_propagates_exception(self, mock_run, mock_ctx, registered_top):
        """Should propagate an exception raised during SSM execution."""
        mock_run.side_effect = Exception('SSM error')

        with pytest.raises(Exception, match='SSM error'):
            await _run_ec2rl_module(
                mock_ctx, 'i-1234567890abcdef0', TOP, args={'times': '1'}
            )
