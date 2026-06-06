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
    ALLOWED_COMMANDS,
    DMESG,
    EC2RL_MODULES,
    TOP,
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

    def test_run_command_with_extra_args(self):
        """Generate run command with extra_args appended."""
        module = Ec2rlModule('top', 'mod_out/run/top.log', extra_args='--times=5')
        assert module.run_command == 'ec2rl run --only-modules=top --times=5'

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


class TestModuleRegistry:
    """Tests for the module registry."""

    def test_dmesg_registered(self):
        """DMESG module is in the registry."""
        assert 'dmesg' in EC2RL_MODULES
        assert EC2RL_MODULES['dmesg'] is DMESG

    def test_dmesg_module_values(self):
        """DMESG has correct name and log_subpath."""
        assert DMESG.name == 'dmesg'
        assert DMESG.log_subpath == 'mod_out/run/dmesg.log'

    def test_top_registered(self):
        """TOP module is in the registry."""
        assert 'top' in EC2RL_MODULES
        assert EC2RL_MODULES['top'] is TOP

    def test_top_module_values(self):
        """TOP has correct name, log_subpath, and extra_args."""
        assert TOP.name == 'top'
        assert TOP.log_subpath == 'mod_out/run/top.log'
        assert TOP.extra_args == '--times=5'

    def test_top_run_command_includes_times(self):
        """TOP run command includes --times=5."""
        assert TOP.run_command == 'ec2rl run --only-modules=top --times=5'


class TestAllowedCommands:
    """Tests for the ALLOWED_COMMANDS constant."""

    def test_is_tuple(self):
        """ALLOWED_COMMANDS should be an immutable tuple."""
        assert isinstance(ALLOWED_COMMANDS, tuple)

    def test_not_empty(self):
        """ALLOWED_COMMANDS should contain at least one command."""
        assert len(ALLOWED_COMMANDS) > 0

    def test_contains_ec2rl_dmesg(self):
        """ALLOWED_COMMANDS should contain the ec2rl dmesg command."""
        assert DMESG.run_command in ALLOWED_COMMANDS

    def test_ec2rl_dmesg_command_value(self):
        """ALLOWED_COMMANDS should contain the correct ec2rl dmesg command string."""
        assert 'ec2rl run --only-modules=dmesg' in ALLOWED_COMMANDS


class TestValidateCommand:
    """Tests for the validate_command function."""

    def test_accepts_allowed_command(self):
        """validate_command should accept the ec2rl dmesg command."""
        assert validate_command(DMESG.run_command) is True

    def test_accepts_log_read_command(self):
        """validate_command should accept valid log read commands."""
        cmd = 'cat /var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'
        assert validate_command(cmd) is True

    def test_rejects_arbitrary_cat(self):
        """validate_command should reject arbitrary cat commands."""
        assert validate_command('cat /etc/passwd') is False

    def test_rejects_unknown_command(self):
        """validate_command should reject unknown commands."""
        assert validate_command('rm -rf /') is False

    def test_rejects_empty_string(self):
        """validate_command should reject empty strings."""
        assert validate_command('') is False

    def test_rejects_partial_match(self):
        """validate_command should reject partial matches."""
        assert validate_command('ec2rl run') is False
        assert validate_command('ec2rl') is False

    def test_rejects_command_with_extra_args(self):
        """validate_command should reject commands with extra arguments."""
        assert validate_command('ec2rl run --only-modules=dmesg --extra') is False

    def test_rejects_similar_command(self):
        """validate_command should reject similar but different commands."""
        assert validate_command('ec2rl run --only-modules=syslog') is False
