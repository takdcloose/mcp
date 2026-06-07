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

"""ec2rl command construction primitives and allowlist validators."""

from __future__ import annotations

import re
from awslabs.ec2_rescue_mcp_server.ec2rl.registry import EC2RL_MODULES
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from awslabs.ec2_rescue_mcp_server.ec2rl.module import Ec2rlModule


EC2RL_OUTPUT_BASE_DIR = '/var/tmp/ec2rl'

# Base ec2rl command pattern (without module name and args)
_EC2RL_RUN_PREFIX = 'ec2rl run --only-modules='
_EC2RL_SOFTWARE_CHECK_CMD = 'ec2rl software-check'

# Module-level ec2rl flag required when running a `perfimpact: True` module.
# We hard-code the literal so command construction and allowlist validation
# stay in lock-step; expand to a set if more global flags are introduced.
_PERFIMPACT_FLAG = '--perfimpact=true'

# Allowed characters in argument values: alphanumeric, dot, hyphen, underscore, slash
_ARG_VALUE_RE = re.compile(r'^[A-Za-z0-9._/\-]+$')
# Allowed module names and arg keys: alphanumeric, hyphen, underscore
_IDENTIFIER_RE = re.compile(r'^[A-Za-z0-9_\-]+$')

# journalctl --since=/--until= args (journal, kernelpanic, hungtasks, etc.).
_TIME_ARG_KEYS = frozenset({'since', 'until'})
# systemd.time charset: default set plus ':' and '+' for single-token forms
# like 13:00:00 and +1h. No space — ec2rl runs `$CMD` unquoted, so a value
# with a space (e.g. "2012-10-30 18:17:16") word-splits and loses the time.
_TIME_ARG_VALUE_RE = re.compile(r'^[A-Za-z0-9:+._/\-]+$')


def validate_arg_value(key: str, value: str) -> bool:
    """True if ``value`` is allowed for argument ``key`` (time args get ':'/'+')."""
    if key in _TIME_ARG_KEYS:
        return bool(_TIME_ARG_VALUE_RE.match(value))
    return bool(_ARG_VALUE_RE.match(value))

_TIMESTAMP_RE = r'\d{4}-\d{2}-\d{2}T[\d_.]+'
_OUTPUT_DIR_RE = re.compile(
    rf'^{re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}$'
)
# Legacy `mod_out/run/<name>.log` form, used by non-gathered modules.
_MOD_OUT_LOG_RE = re.compile(
    rf'^cat {re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}'
    r'/mod_out/run/[A-Za-z0-9_\-]+\.log$'
)
# `gathered_out/<module>/<rel-path>` form, used by modules that write via
# $EC2RL_GATHEREDDIR. Each path segment must start with an alnum/_ char so
# `..` and dotfiles are rejected; subsequent chars also allow `.` and `-`
# so filenames like `messages.1` and `cloud-init.log` work.
_GATHERED_READ_CMD_RE = re.compile(
    rf'^cat {re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}'
    r'/gathered_out/[A-Za-z0-9_\-]+'
    r'(?:/[A-Za-z0-9_][A-Za-z0-9_.\-]*)+$'
)
# `find <gathered_out>/<module> -type f` for listing gathered files when the
# caller hasn't curated GATHEREDDIR_FILES and hasn't supplied `files`.
_GATHERED_LIST_CMD_RE = re.compile(
    rf'^find {re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}'
    r'/gathered_out/[A-Za-z0-9_\-]+ -type f$'
)
# `grep -hE '^(KEY1|KEY2|...)=' <gathered file>` — used by modules that
# should only return matching lines for caller-supplied keys (e.g.
# kernelconfig, where each config file is large and only specific
# CONFIG_* settings matter). Each key is a bare identifier (alnum/_).
_GATHERED_GREP_CMD_RE = re.compile(
    r"^grep -hE '\^\("
    r'[A-Za-z0-9_]+(?:\|[A-Za-z0-9_]+)*'
    r"\)=' "
    rf'{re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}'
    r'/gathered_out/[A-Za-z0-9_\-]+'
    r"(?:/[A-Za-z0-9_][A-Za-z0-9_.\-]*)+$"
)
# `grep -vE '^[[:space:]]*#' <gathered file>` — strips comment lines
# (leading-whitespace `#`) before returning the file. Used for config
# modules whose files are dominated by comments (e.g. sysctlconf,
# nsswitch).
_GATHERED_NOCOMMENT_CMD_RE = re.compile(
    r"^grep -vE '\^\[\[:space:\]\]\*#' "
    rf'{re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}'
    r'/gathered_out/[A-Za-z0-9_\-]+'
    r"(?:/[A-Za-z0-9_][A-Za-z0-9_.\-]*)+$"
)
# `grep -hE '^(K1|K2|...)[ \t]*=' <mod_out log>` — sysctl-style grep on
# collect-class module logs where keys contain dots (e.g. net.ipv4.ip_forward).
_LOG_SYSCTL_GREP_CMD_RE = re.compile(
    r"^grep -hE '\^\("
    r'[A-Za-z0-9_.]+(?:\|[A-Za-z0-9_.]+)*'
    r"\)\[ \\t\]\*=' "
    rf'{re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}'
    r'/mod_out/run/[A-Za-z0-9_\-]+\.log$'
)
# `grep -hF -e KEY1 -e KEY2 ... <mod_out log>` — fixed-string grep on
# collect-class module logs (e.g. dpkgpackages, rpmpackages). Keys may
# contain alphanumeric, dot, hyphen, and plus characters.
_LOG_FIXED_GREP_CMD_RE = re.compile(
    r'^grep -hF'
    r'(?: -e [A-Za-z0-9_.+\-]+)+'
    r' '
    rf'{re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}'
    r'/mod_out/run/[A-Za-z0-9_\-]+\.log \|\| true$'
)


def validate_log_read_command(command: str) -> bool:
    """True if ``command`` is an allowed read of an ec2rl output location.

    Accepts:

    * Legacy ``cat <output_dir>/mod_out/run/<name>.log`` form.
    * ``cat <output_dir>/gathered_out/<module>/<rel>`` for gathered modules.
    * ``find <output_dir>/gathered_out/<module> -type f`` for listing
      gathered files when the caller wants to discover paths.
    * ``grep -hE '^(KEY1|KEY2|...)=' <gathered file>`` for extracting only
      caller-supplied keys (e.g. kernelconfig CONFIG_* settings).
    * ``grep -vE '^[[:space:]]*#' <gathered file>`` for stripping comment
      lines from config files (e.g. sysctlconf, nsswitch).
    * ``grep -hF -e K1 -e K2 ... <mod_out log> || true`` for fixed-string
      grep on collect-class logs (e.g. dpkgpackages, rpmpackages).
    """
    return bool(
        _MOD_OUT_LOG_RE.match(command)
        or _GATHERED_READ_CMD_RE.match(command)
        or _GATHERED_LIST_CMD_RE.match(command)
        or _GATHERED_GREP_CMD_RE.match(command)
        or _LOG_SYSCTL_GREP_CMD_RE.match(command)
        or _GATHERED_NOCOMMENT_CMD_RE.match(command)
        or _LOG_FIXED_GREP_CMD_RE.match(command)
    )


# Matches: ec2rl software-check | grep -i '<package>' || true
# where <package> is a single identifier (alnum/_/-).
_SOFTWARE_CHECK_CMD_RE = re.compile(
    rf"^{re.escape(_EC2RL_SOFTWARE_CHECK_CMD)}"
    r" \| grep -i '(?P<pkg>[A-Za-z0-9_\-]+)' \|\| true$"
)
# Matches: which <binary>
# where <binary> is a known software binary name (alnum/_/./- starting with alnum/_).
# The caller uses SSM exit code (0 = found, non-zero = not found) rather than
# parsing stdout, which varies across OSes and can include login shell noise.
_WHICH_BINARY_CHECK_CMD_RE = re.compile(
    r'^which (?P<binary>[A-Za-z0-9_][A-Za-z0-9_.\-]*)$'
)


def _validate_software_check_command(
    command: str,
    registry: dict[str, 'Ec2rlModule'],
) -> bool:
    """True if ``command`` is a grep-filtered software-check for a known package."""
    match = _SOFTWARE_CHECK_CMD_RE.match(command)
    if not match:
        return False
    pkg = match.group('pkg')
    return any(module.package == pkg for module in registry.values())


def _validate_which_binary_command(
    command: str,
    registry: dict[str, 'Ec2rlModule'],
) -> bool:
    """True if ``command`` is a ``which <binary>`` check for a known module's software."""
    match = _WHICH_BINARY_CHECK_CMD_RE.match(command)
    if not match:
        return False
    binary = match.group('binary')
    return any(module.software == binary for module in registry.values())


def validate_command(
    command: str,
    modules: dict[str, 'Ec2rlModule'] | None = None,
) -> bool:
    """True if ``command`` is an allowed ec2rl run/software-check/log-read form.

    ``modules`` defaults to :data:`EC2RL_MODULES`.
    """
    if not command:
        return False
    if validate_log_read_command(command):
        return True

    registry = modules if modules is not None else EC2RL_MODULES

    if _validate_software_check_command(command, registry):
        return True

    if _validate_which_binary_command(command, registry):
        return True

    if not command.startswith(_EC2RL_RUN_PREFIX):
        return False

    remainder = command[len(_EC2RL_RUN_PREFIX):]
    tokens = remainder.split(' ')
    if not tokens:
        return False

    module_name = tokens[0]
    module = registry.get(module_name)
    if module is None:
        return False

    # Validate remaining tokens as --key=value pairs with allowed keys/values.
    # The literal `--perfimpact=true` flag is also accepted (only on
    # perfimpact-flagged modules) — it's a module-level ec2rl flag, not a
    # per-argument key. Reject the flag when the module isn't perfimpact so
    # tampering can't sneak it onto arbitrary modules.
    allowed_keys = set(module.required_args) | set(module.optional_args)
    for token in tokens[1:]:
        if token == _PERFIMPACT_FLAG:
            if not module.perfimpact:
                return False
            continue
        if not token.startswith('--'):
            return False
        kv = token[2:]
        if '=' not in kv:
            return False
        key, _, value = kv.partition('=')
        if key not in allowed_keys:
            return False
        if not validate_arg_value(key, value):
            return False
    return True
