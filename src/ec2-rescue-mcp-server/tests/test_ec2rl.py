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

"""Tests for the ec2rl module."""

import pytest
from awslabs.ec2_rescue_mcp_server.ec2rl import (
    Ec2rlModule,
    validate_command,
    validate_log_read_command,
)


EC2RL_SAMPLE_STDOUT = """
-----------[Backup  Creation]-----------

No backup option selected. Please consider backing up your volumes or instance

----------[Configuration File]----------

Configuration file saved:
/var/tmp/ec2rl/2026-04-14T02_50_34.749027/configuration.cfg

-------------[Output  Logs]-------------

The output logs are located in:
/var/tmp/ec2rl/2026-04-14T02_50_34.749027

--------------[Module Run]--------------

Running Modules:
dmesg

--------------[Run  Stats]--------------

Total modules run:               1
'collect' modules run:           1
"""


class TestEc2rlModule:
    """Tests for the Ec2rlModule class."""

    def test_run_command(self):
        """Generate run command for a basic module."""
        module = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
        assert module.run_command == 'ec2rl run --only-modules=dmesg'

    def test_run_command_other_module(self):
        """Generate run command for a different module name."""
        module = Ec2rlModule('syslog', 'mod_out/run/syslog.log')
        assert module.run_command == 'ec2rl run --only-modules=syslog'

    def test_build_run_command_with_args(self):
        """build_run_command appends --key=value pairs for declared args."""
        module = Ec2rlModule('top', 'mod_out/run/top.log', required_args=['times'])
        assert module.build_run_command({'times': '5'}) == (
            'ec2rl run --only-modules=top --times=5'
        )

    def test_log_read_command(self):
        """Generate cat command for a valid output directory."""
        module = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
        cmd = module.log_read_command('/var/tmp/ec2rl/2026-04-14T02_50_34.749027')
        assert cmd == 'cat /var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'

    def test_log_read_command_rejects_invalid_dir(self):
        """Reject output directory outside /var/tmp/ec2rl."""
        module = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
        with pytest.raises(ValueError, match='Invalid ec2rl output directory'):
            module.log_read_command('/tmp/evil')

    def test_log_read_command_rejects_path_traversal(self):
        """Reject path traversal in output directory."""
        module = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
        with pytest.raises(ValueError):
            module.log_read_command('/var/tmp/ec2rl/../../../etc')

    def test_parse_output_dir(self):
        """Parse output directory from ec2rl stdout."""
        result = Ec2rlModule.parse_output_dir(EC2RL_SAMPLE_STDOUT)
        assert result == '/var/tmp/ec2rl/2026-04-14T02_50_34.749027'

    def test_parse_output_dir_returns_none_for_empty(self):
        """Return None for empty stdout."""
        assert Ec2rlModule.parse_output_dir('') is None

    def test_parse_output_dir_returns_none_for_no_match(self):
        """Return None when output dir pattern is absent."""
        assert Ec2rlModule.parse_output_dir('no output dir here') is None

    def test_repr(self):
        """Include module name in repr."""
        module = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
        assert 'dmesg' in repr(module)


class TestValidateLogReadCommand:
    """Tests for validate_log_read_command."""

    def test_accepts_valid_command(self):
        """Accept cat of a valid ec2rl log path."""
        cmd = 'cat /var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'
        assert validate_log_read_command(cmd) is True

    def test_rejects_arbitrary_cat(self):
        """Reject cat of an arbitrary path."""
        assert validate_log_read_command('cat /etc/passwd') is False

    def test_rejects_empty(self):
        """Reject empty string."""
        assert validate_log_read_command('') is False

    def test_rejects_non_cat_command(self):
        """Reject non-cat commands even with ec2rl path."""
        assert validate_log_read_command('rm /var/tmp/ec2rl/2026-04-14T02_50_34.749027/x.log') is False


@pytest.fixture()
def registry():
    """A small ad-hoc module registry for validate_command tests."""
    return {
        'dmesg': Ec2rlModule('dmesg', 'mod_out/run/dmesg.log'),
        'top': Ec2rlModule('top', 'mod_out/run/top.log', required_args=['times']),
    }


class TestValidateCommand:
    """Tests for the validate_command function (registry-driven)."""

    def test_accepts_known_run_command(self, registry):
        """Accept an ec2rl run command for a module in the registry."""
        assert validate_command('ec2rl run --only-modules=dmesg', registry) is True

    def test_accepts_known_run_command_with_args(self, registry):
        """Accept a run command with a declared --key=value arg."""
        assert validate_command(
            'ec2rl run --only-modules=top --times=5', registry
        ) is True

    def test_accepts_log_read_command(self, registry):
        """Accept a valid log read command regardless of registry."""
        cmd = 'cat /var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'
        assert validate_command(cmd, registry) is True

    def test_rejects_arbitrary_cat(self, registry):
        """Reject arbitrary cat commands."""
        assert validate_command('cat /etc/passwd', registry) is False

    def test_rejects_unknown_command(self, registry):
        """Reject unknown commands."""
        assert validate_command('rm -rf /', registry) is False

    def test_rejects_empty_string(self, registry):
        """Reject empty strings."""
        assert validate_command('', registry) is False

    def test_rejects_partial_match(self, registry):
        """Reject partial matches."""
        assert validate_command('ec2rl run', registry) is False
        assert validate_command('ec2rl', registry) is False

    def test_rejects_undeclared_arg(self, registry):
        """Reject a run command with an arg the module didn't declare."""
        assert validate_command(
            'ec2rl run --only-modules=dmesg --extra', registry
        ) is False

    def test_rejects_module_absent_from_registry(self, registry):
        """Reject a run command for a module not in the registry."""
        assert validate_command('ec2rl run --only-modules=syslog', registry) is False
