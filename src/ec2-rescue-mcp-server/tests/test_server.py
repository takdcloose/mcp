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
from unittest.mock import AsyncMock, MagicMock, patch


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


# 'dmesg' is a non-gathered append-only log module in TAIL_MODULES.
DMESG = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
# 'yumlog' is a gathered append-only log module with a curated single file.
YUMLOG = Ec2rlModule('yumlog', 'mod_out/run/yumlog.log')
# 'messages' is a gathered append-only module with NO curated file set, so it
# discovers files via `find` before reading them.
MESSAGES = Ec2rlModule('messages', 'mod_out/run/messages.log')
# 'aptlog' is a gathered append-only module with MULTIPLE curated files.
APTLOG = Ec2rlModule('aptlog', 'mod_out/run/aptlog.log')


@pytest.fixture()
def registered_tail_modules():
    """Register the tail modules used in tests so validate_command accepts them."""
    prev = dict(ec2rl_module.EC2RL_MODULES)
    ec2rl_module.EC2RL_MODULES['dmesg'] = DMESG
    ec2rl_module.EC2RL_MODULES['yumlog'] = YUMLOG
    ec2rl_module.EC2RL_MODULES['messages'] = MESSAGES
    ec2rl_module.EC2RL_MODULES['aptlog'] = APTLOG
    yield
    ec2rl_module.EC2RL_MODULES.clear()
    ec2rl_module.EC2RL_MODULES.update(prev)


class TestTailModules:
    """Tests for the tail behavior of append-only log modules.

    Append-only modules (messages, dmesg, yumlog) return only the last N lines
    by default. ``tail_lines`` overrides the count; ``tail_lines=0`` requests
    the full log (which re-enables the large-output elicitation gate for
    modules that have one).
    """

    EC2RL_RUN_STDOUT = TestRunEc2rlModule.EC2RL_RUN_STDOUT

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_dmesg_default_tail(self, mock_run, mock_ctx, registered_tail_modules):
        """Default dmesg run tails the last 100 lines of the mod_out log."""
        mock_run.side_effect = [
            {'status': 'Success', 'stdout': self.EC2RL_RUN_STDOUT, 'stderr': '', 'exit_code': 0},
            {'status': 'Success', 'stdout': 'last 100 kernel lines', 'stderr': '', 'exit_code': 0},
        ]

        result = await _run_ec2rl_module(mock_ctx, 'i-1234567890abcdef0', DMESG)
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert data['tail_lines'] == 100
        assert data['log_content'] == 'last 100 kernel lines'
        # The second SSM call must be a `tail -n 100` of the dmesg log.
        read_cmd = mock_run.call_args_list[1].args[2]
        assert read_cmd.startswith('tail -n 100 ')
        assert read_cmd.endswith('/mod_out/run/dmesg.log')

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_dmesg_custom_tail(self, mock_run, mock_ctx, registered_tail_modules):
        """A positive tail_lines overrides the module default."""
        mock_run.side_effect = [
            {'status': 'Success', 'stdout': self.EC2RL_RUN_STDOUT, 'stderr': '', 'exit_code': 0},
            {'status': 'Success', 'stdout': 'last 25 lines', 'stderr': '', 'exit_code': 0},
        ]

        result = await _run_ec2rl_module(
            mock_ctx, 'i-1234567890abcdef0', DMESG, tail_lines=25
        )
        data = json.loads(result)

        assert data['tail_lines'] == 25
        read_cmd = mock_run.call_args_list[1].args[2]
        assert read_cmd.startswith('tail -n 25 ')

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_dmesg_full_output_triggers_gate(self, mock_run, mock_ctx, registered_tail_modules):
        """tail_lines=0 requests the full log and re-enables the large-output gate.

        The gate elicits confirmation; when the client accepts, the module
        cats the whole log (no tail_lines in the response).
        """
        accept = MagicMock()
        accept.action = 'accept'
        accept.data = MagicMock(confirm=True)
        mock_ctx.elicit = AsyncMock(return_value=accept)

        mock_run.side_effect = [
            {'status': 'Success', 'stdout': self.EC2RL_RUN_STDOUT, 'stderr': '', 'exit_code': 0},
            {'status': 'Success', 'stdout': 'full kernel ring buffer', 'stderr': '', 'exit_code': 0},
        ]

        result = await _run_ec2rl_module(
            mock_ctx, 'i-1234567890abcdef0', DMESG, tail_lines=0
        )
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert 'tail_lines' not in data
        mock_ctx.elicit.assert_awaited_once()
        read_cmd = mock_run.call_args_list[1].args[2]
        assert read_cmd.startswith('cat ')

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_dmesg_full_output_declined_aborts(self, mock_run, mock_ctx, registered_tail_modules):
        """tail_lines=0 with a declined gate aborts before reading the log."""
        decline = MagicMock()
        decline.action = 'decline'
        decline.data = None
        mock_ctx.elicit = AsyncMock(return_value=decline)

        result = await _run_ec2rl_module(
            mock_ctx, 'i-1234567890abcdef0', DMESG, tail_lines=0
        )
        data = json.loads(result)

        assert data['status'] == 'Aborted'
        # The gate runs before ec2rl executes, so no SSM command is issued.
        assert mock_run.call_count == 0

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_yumlog_default_tail(self, mock_run, mock_ctx, registered_tail_modules):
        """Gathered yumlog defaults to `tail -n 100` on its curated file."""
        mock_run.side_effect = [
            {'status': 'Success', 'stdout': self.EC2RL_RUN_STDOUT, 'stderr': '', 'exit_code': 0},
            {'status': 'Success', 'stdout': 'last 100 yum.log lines', 'stderr': '', 'exit_code': 0},
        ]

        result = await _run_ec2rl_module(mock_ctx, 'i-1234567890abcdef0', YUMLOG)
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert data['tail_lines'] == 100
        assert 'yum.log' in data['files']
        read_cmd = mock_run.call_args_list[1].args[2]
        assert read_cmd.startswith('tail -n 100 ')
        assert read_cmd.endswith('/gathered_out/yumlog/yum.log')

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_messages_discovers_then_tails(self, mock_run, mock_ctx, registered_tail_modules):
        """Gathered messages (no curated files) discovers via find, then tails.

        The tail path bypasses the read-all elicitation, so ctx.elicit is
        never called even though the file set was discovered dynamically.
        """
        mock_ctx.elicit = AsyncMock()
        base = '/var/tmp/ec2rl/2026-04-14T02_50_34.749027/gathered_out/messages/'
        mock_run.side_effect = [
            # ec2rl run
            {'status': 'Success', 'stdout': self.EC2RL_RUN_STDOUT, 'stderr': '', 'exit_code': 0},
            # find listing of gathered files
            {'status': 'Success', 'stdout': f'{base}messages\n{base}messages-1', 'stderr': '', 'exit_code': 0},
            # tail of each discovered file
            {'status': 'Success', 'stdout': 'recent messages', 'stderr': '', 'exit_code': 0},
            {'status': 'Success', 'stdout': 'recent messages-1', 'stderr': '', 'exit_code': 0},
        ]

        result = await _run_ec2rl_module(mock_ctx, 'i-1234567890abcdef0', MESSAGES)
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert data['tail_lines'] == 100
        assert set(data['files']) == {'messages', 'messages-1'}
        mock_ctx.elicit.assert_not_called()
        # The two file reads (calls 3 and 4) must be tail commands.
        for call in mock_run.call_args_list[2:]:
            assert call.args[2].startswith('tail -n 100 ')

    @pytest.mark.asyncio
    @patch('awslabs.ec2_rescue_mcp_server.execution.run_ssm_command')
    async def test_aptlog_tails_all_curated_files(self, mock_run, mock_ctx, registered_tail_modules):
        """Gathered aptlog tails each of its multiple curated files."""
        mock_run.side_effect = [
            {'status': 'Success', 'stdout': self.EC2RL_RUN_STDOUT, 'stderr': '', 'exit_code': 0},
            {'status': 'Success', 'stdout': 'recent history.log', 'stderr': '', 'exit_code': 0},
            {'status': 'Success', 'stdout': 'recent dpkg.log', 'stderr': '', 'exit_code': 0},
        ]

        result = await _run_ec2rl_module(mock_ctx, 'i-1234567890abcdef0', APTLOG)
        data = json.loads(result)

        assert data['status'] == 'Success'
        assert data['tail_lines'] == 100
        assert set(data['files']) == {'history.log', 'dpkg.log'}
        for call in mock_run.call_args_list[1:]:
            assert call.args[2].startswith('tail -n 100 ')
