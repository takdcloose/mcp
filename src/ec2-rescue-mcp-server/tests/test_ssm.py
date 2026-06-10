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

"""Tests for the SSM module."""

import pytest
from awslabs.ec2_rescue_mcp_server.ssm import (
    _list_ssm_instances_sync,
    _run_ssm_command_sync,
    list_ssm_instances,
    run_ssm_command,
)
from unittest.mock import MagicMock, patch


class TestListSsmInstancesSync:
    """Tests for _list_ssm_instances_sync."""

    def test_returns_instances(self, mock_session):
        """Should return merged SSM and EC2 instance data."""
        mock_ssm = MagicMock()
        mock_ec2 = MagicMock()
        mock_session.client.side_effect = lambda svc, **kw: {'ssm': mock_ssm, 'ec2': mock_ec2}[svc]

        mock_paginator = MagicMock()
        mock_ssm.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'InstanceInformationList': [
                    {
                        'InstanceId': 'i-1234567890abcdef0',
                        'PlatformType': 'Linux',
                        'PingStatus': 'Online',
                        'IPAddress': '10.0.0.1',
                    }
                ]
            }
        ]

        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'InstanceType': 't3.micro',
                            'Tags': [{'Key': 'Name', 'Value': 'test-instance'}],
                        }
                    ]
                }
            ]
        }

        result = _list_ssm_instances_sync(mock_session)

        assert len(result) == 1
        assert result[0]['instance_id'] == 'i-1234567890abcdef0'
        assert result[0]['name'] == 'test-instance'
        assert result[0]['platform'] == 'Linux'
        assert result[0]['ping_status'] == 'Online'
        assert result[0]['ip_address'] == '10.0.0.1'
        assert result[0]['instance_type'] == 't3.micro'

    def test_returns_empty_when_no_instances(self, mock_session):
        """Should return empty list when no SSM instances found."""
        mock_ssm = MagicMock()
        mock_session.client.side_effect = lambda svc, **kw: {'ssm': mock_ssm}[svc]

        mock_paginator = MagicMock()
        mock_ssm.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{'InstanceInformationList': []}]

        result = _list_ssm_instances_sync(mock_session)

        assert result == []

    def test_handles_instance_without_tags(self, mock_session):
        """Should handle instances without Name tag."""
        mock_ssm = MagicMock()
        mock_ec2 = MagicMock()
        mock_session.client.side_effect = lambda svc, **kw: {'ssm': mock_ssm, 'ec2': mock_ec2}[svc]

        mock_paginator = MagicMock()
        mock_ssm.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'InstanceInformationList': [
                    {
                        'InstanceId': 'i-abcdef1234567890',
                        'PlatformType': 'Linux',
                        'PingStatus': 'Online',
                        'IPAddress': '10.0.0.2',
                    }
                ]
            }
        ]

        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-abcdef1234567890',
                            'InstanceType': 't3.small',
                        }
                    ]
                }
            ]
        }

        result = _list_ssm_instances_sync(mock_session)

        assert len(result) == 1
        assert result[0]['name'] == ''


class TestRunSsmCommandSync:
    """Tests for _run_ssm_command_sync."""

    def test_successful_command(self, mock_session):
        """Should return successful command result."""
        mock_ssm = MagicMock()
        mock_session.client.return_value = mock_ssm

        mock_ssm.send_command.return_value = {'Command': {'CommandId': 'cmd-123'}}
        mock_ssm.get_command_invocation.return_value = {
            'Status': 'Success',
            'StandardOutputContent': 'dmesg output here',
            'StandardErrorContent': '',
            'ResponseCode': 0,
        }

        result = _run_ssm_command_sync(
            mock_session, 'i-1234567890abcdef0', 'ec2rl run --only-modules=dmesg'
        )

        assert result['status'] == 'Success'
        assert result['stdout'] == 'dmesg output here'
        assert result['stderr'] == ''
        assert result['exit_code'] == 0

    def test_failed_command(self, mock_session):
        """Should return failed command result."""
        mock_ssm = MagicMock()
        mock_session.client.return_value = mock_ssm

        mock_ssm.send_command.return_value = {'Command': {'CommandId': 'cmd-456'}}
        mock_ssm.get_command_invocation.return_value = {
            'Status': 'Failed',
            'StandardOutputContent': '',
            'StandardErrorContent': 'command not found',
            'ResponseCode': 1,
        }

        result = _run_ssm_command_sync(
            mock_session, 'i-1234567890abcdef0', 'ec2rl run --only-modules=dmesg'
        )

        assert result['status'] == 'Failed'
        assert result['stderr'] == 'command not found'
        assert result['exit_code'] == 1

    @patch('awslabs.ec2_rescue_mcp_server.ssm.time')
    def test_retries_on_invocation_not_exist(self, mock_time, mock_session):
        """Should retry when InvocationDoesNotExist is raised."""
        mock_ssm = MagicMock()
        mock_session.client.return_value = mock_ssm

        mock_ssm.send_command.return_value = {'Command': {'CommandId': 'cmd-789'}}

        # Simulate monotonic time progression
        mock_time.monotonic.side_effect = [0, 1, 2, 3]
        mock_time.sleep = MagicMock()

        # First call raises InvocationDoesNotExist, second succeeds
        exc = mock_ssm.exceptions.InvocationDoesNotExist
        mock_ssm.get_command_invocation.side_effect = [
            exc('not yet'),
            {
                'Status': 'Success',
                'StandardOutputContent': 'output',
                'StandardErrorContent': '',
                'ResponseCode': 0,
            },
        ]

        result = _run_ssm_command_sync(
            mock_session,
            'i-1234567890abcdef0',
            'ec2rl run --only-modules=dmesg',
            poll_deadline_seconds=60,
            poll_interval=2.0,
        )

        assert result['status'] == 'Success'
        assert mock_time.sleep.called

    @patch('awslabs.ec2_rescue_mcp_server.ssm.time')
    def test_timeout(self, mock_time, mock_session):
        """Should return TimedOut when deadline is exceeded."""
        mock_ssm = MagicMock()
        mock_session.client.return_value = mock_ssm

        mock_ssm.send_command.return_value = {'Command': {'CommandId': 'cmd-timeout'}}

        # Simulate time exceeding deadline immediately
        mock_time.monotonic.side_effect = [0, 100]
        mock_time.sleep = MagicMock()

        result = _run_ssm_command_sync(
            mock_session,
            'i-1234567890abcdef0',
            'ec2rl run --only-modules=dmesg',
            poll_deadline_seconds=5,
        )

        assert result['status'] == 'TimedOut'
        assert result['exit_code'] == -1


class TestAsyncWrappers:
    """Tests for the async wrapper functions."""

    @pytest.mark.asyncio
    async def test_list_ssm_instances_async(self, mock_session):
        """list_ssm_instances should delegate to _list_ssm_instances_sync."""
        with patch(
            'awslabs.ec2_rescue_mcp_server.ssm._list_ssm_instances_sync',
            return_value=[{'instance_id': 'i-test'}],
        ) as mock_sync:
            result = await list_ssm_instances(mock_session)
            mock_sync.assert_called_once_with(mock_session)
            assert result == [{'instance_id': 'i-test'}]

    @pytest.mark.asyncio
    async def test_run_ssm_command_async(self, mock_session):
        """run_ssm_command should delegate to _run_ssm_command_sync."""
        with patch(
            'awslabs.ec2_rescue_mcp_server.ssm._run_ssm_command_sync',
            return_value={'status': 'Success', 'stdout': 'ok', 'stderr': '', 'exit_code': 0},
        ) as mock_sync:
            result = await run_ssm_command(mock_session, 'i-test', 'test cmd')
            mock_sync.assert_called_once_with(mock_session, 'i-test', 'test cmd', 60, 3600, 3600, 2.0)
            assert result['status'] == 'Success'
