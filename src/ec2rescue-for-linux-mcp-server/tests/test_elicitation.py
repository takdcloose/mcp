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

"""Tests for the perfimpact consent gate in elicitation.py."""

import json
import pytest
from awslabs.ec2rescue_for_linux_mcp_server import elicitation as elicitation_module
from awslabs.ec2rescue_for_linux_mcp_server.ec2rl import Ec2rlModule
from awslabs.ec2rescue_for_linux_mcp_server.elicitation import _perfimpact_consent_gate
from unittest.mock import patch


_INSTANCE_ID = 'i-1234567890abcdef0'


@pytest.fixture()
def perfimpact_module():
    """A perfimpact-flagged module (e.g. packet capture / syscall tracing)."""
    return Ec2rlModule(
        'atop', 'mod_out/run/atop.log', perfimpact=True
    )


class TestPerfimpactConsentGate:
    """The gate is fail-closed: a perfimpact module runs only when the
    operator started the server with --allow-perfimpact."""

    def test_denied_when_flag_not_set(self, perfimpact_module):
        """Fail-closed: without --allow-perfimpact the gate aborts the run."""
        with patch.object(elicitation_module, '_ALLOW_PERFIMPACT', False):
            result = _perfimpact_consent_gate(_INSTANCE_ID, perfimpact_module)

        assert result is not None
        data = json.loads(result)
        assert data['status'] == 'Aborted'
        assert data['reason'] == 'perfimpact_not_permitted'
        assert data['module'] == 'atop'
        assert data['instance_id'] == _INSTANCE_ID

    def test_permitted_when_flag_set(self, perfimpact_module):
        """With --allow-perfimpact the gate permits the run (returns None)."""
        with patch.object(elicitation_module, '_ALLOW_PERFIMPACT', True):
            result = _perfimpact_consent_gate(_INSTANCE_ID, perfimpact_module)

        assert result is None
