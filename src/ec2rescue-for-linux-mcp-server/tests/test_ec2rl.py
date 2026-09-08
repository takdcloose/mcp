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
from awslabs.ec2rescue_for_linux_mcp_server.ec2rl import (
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

    def test_log_read_command_tail(self):
        """Generate tail command for an append-only mod_out log."""
        module = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
        cmd = module.log_read_command(
            '/var/tmp/ec2rl/2026-04-14T02_50_34.749027', tail_lines=100
        )
        assert cmd == (
            'tail -n 100 '
            '/var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'
        )

    def test_log_read_command_rejects_non_positive_tail(self):
        """Reject zero or negative tail line counts."""
        module = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
        for bad in (0, -1):
            with pytest.raises(ValueError, match='Invalid tail line count'):
                module.log_read_command(
                    '/var/tmp/ec2rl/2026-04-14T02_50_34.749027', tail_lines=bad
                )

    def test_gathered_read_commands_tail(self):
        """Generate tail commands for append-only gathered files."""
        module = Ec2rlModule('yumlog', 'mod_out/run/yumlog.log')
        cmds = module.gathered_read_commands(
            '/var/tmp/ec2rl/2026-04-14T02_50_34.749027',
            files=['yum.log'],
            tail_lines=100,
        )
        assert cmds == [(
            'yum.log',
            'tail -n 100 '
            '/var/tmp/ec2rl/2026-04-14T02_50_34.749027/gathered_out/yumlog/yum.log',
        )]

    def test_gathered_read_commands_tail_rejects_traversal(self):
        """Reject path traversal in the gathered tail relative path."""
        module = Ec2rlModule('yumlog', 'mod_out/run/yumlog.log')
        with pytest.raises(ValueError, match='Invalid gathered file path'):
            module.gathered_read_commands(
                '/var/tmp/ec2rl/2026-04-14T02_50_34.749027',
                files=['../../../etc/passwd'],
                tail_lines=100,
            )

    def test_gathered_read_commands_rejects_non_positive_tail(self):
        """Reject zero or negative tail line counts for gathered files."""
        module = Ec2rlModule('yumlog', 'mod_out/run/yumlog.log')
        with pytest.raises(ValueError, match='Invalid tail line count'):
            module.gathered_read_commands(
                '/var/tmp/ec2rl/2026-04-14T02_50_34.749027',
                files=['yum.log'],
                tail_lines=0,
            )

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

    def test_accepts_mod_out_tail_command(self):
        """Accept tail of a valid mod_out log path."""
        cmd = 'tail -n 100 /var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'
        assert validate_log_read_command(cmd) is True

    def test_accepts_gathered_tail_command(self):
        """Accept tail of a valid gathered file path."""
        cmd = (
            'tail -n 50 '
            '/var/tmp/ec2rl/2026-04-14T02_50_34.749027/gathered_out/yumlog/yum.log'
        )
        assert validate_log_read_command(cmd) is True

    def test_rejects_tail_with_oversized_count(self):
        """Reject tail commands whose line count exceeds the allowlist bound."""
        cmd = 'tail -n 99999999 /var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'
        assert validate_log_read_command(cmd) is False

    def test_rejects_tail_with_zero_count(self):
        """Reject tail commands with a zero line count."""
        cmd = 'tail -n 0 /var/tmp/ec2rl/2026-04-14T02_50_34.749027/mod_out/run/dmesg.log'
        assert validate_log_read_command(cmd) is False

    def test_rejects_tail_arbitrary_path(self):
        """Reject tail of an arbitrary path outside ec2rl output."""
        assert validate_log_read_command('tail -n 100 /etc/passwd') is False


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


# Shell metacharacters and control bytes that must never survive validation
# when smuggled through an argument *value*. Each keeps a valid
# `ec2rl run --only-modules=top --times=<value>` prefix and a registered
# module -- the only command shape that could plausibly reach the SSM layer
# while still looking allowlisted.
_INJECTION_ARG_VALUES: tuple[str, ...] = (
    '5;id',
    '5 id',
    '5&&id',
    '5&id',
    '5|id',
    '5||id',
    '5$(id)',
    '5`id`',
    '5${IFS}id',
    '5>/tmp/x',
    '5</etc/passwd',
    '5#comment',
    '5\\id',
    "5'id",
    '5"id',
    '5*',
    '5?',
    '5~',
    '5!id',
    '5\nid',        # embedded LF
    '5\rid',        # embedded CR
    '5\r\nid',      # CRLF
    '5\x00id',      # NUL
    '5\tid',        # tab
    '5%0aid',       # URL-encoded LF (must stay literal, not be decoded)
    '5%3Bid',       # URL-encoded ';'
    '5\\nid',       # literal backslash-n
)
# Note: trailing-newline / trailing-whitespace payloads (e.g. '5\n') are
# covered separately by the regex anchoring tests, since rejecting them
# requires full-string matching rather than value-charset filtering.


class TestArgumentInjection:
    """Reject shell syntax smuggled through an argument value.

    A command that keeps a valid ``ec2rl run --only-modules=<module>`` prefix
    and a registered module, but carries shell metacharacters or control bytes
    inside an argument value, must be rejected so no payload reaches the SSM
    execution layer. This is distinct from a structurally invalid command
    (e.g. ``cat /etc/passwd``): the prefix is well-formed and only the value
    is hostile.
    """

    @pytest.mark.parametrize('value', _INJECTION_ARG_VALUES)
    def test_rejects_injection_through_declared_arg_value(self, registry, value):
        """Reject shell syntax / control bytes smuggled through a declared arg."""
        command = f'ec2rl run --only-modules=top --times={value}'
        assert validate_command(command, registry) is False

    @pytest.mark.parametrize('value', _INJECTION_ARG_VALUES)
    def test_rejects_injection_through_time_arg_value(self, registry, value):
        """Reject the same payloads on a time arg (wider charset, still bounded).

        ``since``/``until`` allow ``:`` and ``+`` in addition to the default
        set, so they need independent coverage -- a payload could pass the
        default validator's rejection for the wrong reason.
        """
        module = Ec2rlModule('journal', 'mod_out/run/journal.log', optional_args=['since'])
        reg = {'journal': module}
        command = f'ec2rl run --only-modules=journal --since={value}'
        assert validate_command(command, reg) is False

    def test_rejects_injection_as_separate_token(self, registry):
        """Reject an injected token that word-splits away from a valid --key=value.

        A space in the value makes the injection a separate argv token. It can
        no longer hide inside the value charset check and must instead fail the
        ``--key=value`` shape check applied to every token after the module.
        """
        for command in (
            'ec2rl run --only-modules=top --times=5 ;id',
            'ec2rl run --only-modules=top --times=5 id',
            'ec2rl run --only-modules=top --times=5 cat /etc/passwd',
            'ec2rl run --only-modules=top --times=5 &',
        ):
            assert validate_command(command, registry) is False

    def test_rejects_bare_token_without_double_dash(self, registry):
        """Reject a trailing token that is not a ``--key=value`` pair."""
        for command in (
            'ec2rl run --only-modules=dmesg extra',
            'ec2rl run --only-modules=dmesg -times=5',   # single dash
            'ec2rl run --only-modules=dmesg times=5',    # no dash at all
        ):
            assert validate_command(command, registry) is False

    def test_rejects_flag_shaped_token_without_value(self, registry):
        """Reject a ``--flag`` token that carries no ``=value``."""
        for command in (
            'ec2rl run --only-modules=top --times',      # key, no =value
            'ec2rl run --only-modules=top --verbose',    # unknown bare flag
        ):
            assert validate_command(command, registry) is False

    def test_rejects_unknown_key_even_with_valid_value(self, registry):
        """Reject a well-formed ``--key=value`` whose key the module never declared."""
        assert validate_command(
            'ec2rl run --only-modules=top --unknownkey=5', registry
        ) is False

    def test_rejects_perfimpact_flag_on_non_perfimpact_module(self, registry):
        """Reject the module-level perfimpact flag on a module not marked perfimpact.

        The literal flag is accepted only for perfimpact-flagged modules, so it
        must not be smuggleable onto an arbitrary allowlisted module.
        """
        assert validate_command(
            'ec2rl run --only-modules=dmesg --perfimpact=true', registry
        ) is False

    def test_rejects_injection_in_module_name_position(self, registry):
        """Reject shell syntax placed in the module-name slot itself."""
        for command in (
            'ec2rl run --only-modules=dmesg;id',
            'ec2rl run --only-modules=dmesg,top',        # comma-chained modules
            'ec2rl run --only-modules=$(id)',
        ):
            assert validate_command(command, registry) is False

    def test_rejects_double_space_producing_empty_token(self, registry):
        """Reject collapsed/empty tokens from repeated separators.

        Splitting on a single space turns a double space into an empty token,
        which is neither the perfimpact flag nor a ``--key=value`` pair.
        """
        assert validate_command(
            'ec2rl run --only-modules=top  --times=5', registry
        ) is False

    def test_accepts_benign_value_baseline(self, registry):
        """Sanity check: a clean value on the same prefix is still accepted.

        Guards against a future over-broad fix that rejects everything and
        makes the injection assertions pass vacuously.
        """
        assert validate_command(
            'ec2rl run --only-modules=top --times=5', registry
        ) is True
