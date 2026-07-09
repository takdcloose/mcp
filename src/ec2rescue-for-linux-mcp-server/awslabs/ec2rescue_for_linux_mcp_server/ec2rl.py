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

"""EC2 Rescue Linux module definitions and output parsing."""

import re


EC2RL_OUTPUT_BASE_DIR = '/var/tmp/ec2rl'

_TIMESTAMP_RE = r'\d{4}-\d{2}-\d{2}T[\d_.]+'
_OUTPUT_DIR_RE = re.compile(
    rf'^{re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}$'
)
_LOG_READ_CMD_RE = re.compile(
    rf'^cat {re.escape(EC2RL_OUTPUT_BASE_DIR)}/{_TIMESTAMP_RE}/[a-zA-Z0-9_/]+\.log$'
)


class Ec2rlModule:
    """An EC2 Rescue Linux diagnostic module.

    Subclass or instantiate to define new ec2rl modules.
    Each module knows its name, the subpath to its log file,
    and how to generate/validate commands.

    To add a new module, create an instance and register it in EC2RL_MODULES::

        SYSLOG = Ec2rlModule('syslog', 'mod_out/run/syslog.log')
        EC2RL_MODULES['syslog'] = SYSLOG

    For modules requiring extra arguments::

        TOP = Ec2rlModule('top', 'mod_out/run/top.log', extra_args='--times=5')
        EC2RL_MODULES['top'] = TOP
    """

    def __init__(self, name: str, log_subpath: str, extra_args: str = ''):
        """Initialize an ec2rl module definition."""
        self.name = name
        self.log_subpath = log_subpath
        self.extra_args = extra_args

    @property
    def run_command(self) -> str:
        """The ec2rl command to run this module."""
        base_cmd = f'ec2rl run --only-modules={self.name}'
        if self.extra_args:
            return f'{base_cmd} {self.extra_args}'
        return base_cmd

    def log_read_command(self, output_dir: str) -> str:
        """Generate a command to read this module's log file.

        Args:
            output_dir: The ec2rl output directory (e.g. /var/tmp/ec2rl/2026-...).

        Returns:
            A shell command to cat the log file.

        Raises:
            ValueError: If output_dir doesn't match the expected pattern.
        """
        if not _OUTPUT_DIR_RE.match(output_dir):
            raise ValueError(f'Invalid ec2rl output directory: {output_dir}')
        return f'cat {output_dir}/{self.log_subpath}'

    @staticmethod
    def parse_output_dir(stdout: str) -> str | None:
        """Extract the output directory path from ec2rl stdout.

        Looks for the path after the 'output logs are located in' line.

        Args:
            stdout: The stdout from an ec2rl run command.

        Returns:
            The output directory path, or None if not found.
        """
        lines = stdout.splitlines()
        for i, line in enumerate(lines):
            if 'output logs are located in' in line.lower():
                for j in range(i + 1, len(lines)):
                    stripped = lines[j].strip()
                    if stripped:
                        if _OUTPUT_DIR_RE.match(stripped):
                            return stripped
                        break
        return None

    def __repr__(self) -> str:
        """Return a string representation of the module."""
        args = f'name={self.name!r}, log_subpath={self.log_subpath!r}'
        if self.extra_args:
            args += f', extra_args={self.extra_args!r}'
        return f'Ec2rlModule({args})'


def validate_log_read_command(command: str) -> bool:
    """Check if a command is a valid ec2rl log read command."""
    return bool(_LOG_READ_CMD_RE.match(command))


# --- Module registry ---
DMESG = Ec2rlModule('dmesg', 'mod_out/run/dmesg.log')
TOP = Ec2rlModule('top', 'mod_out/run/top.log', extra_args='--times=5')

EC2RL_MODULES: dict[str, Ec2rlModule] = {
    'dmesg': DMESG,
    'top': TOP,
}

# Allowlist of permitted commands — auto-generated from module registry
ALLOWED_COMMANDS: tuple[str, ...] = tuple(m.run_command for m in EC2RL_MODULES.values())


def validate_command(command: str) -> bool:
    """Check if a command is permitted.

    Accepts commands in the static allowlist (ec2rl run commands)
    and validated log-read commands (cat of ec2rl output files).

    Args:
        command: The command string to validate.

    Returns:
        True if the command is allowed, False otherwise.
    """
    if not command:
        return False
    if command in ALLOWED_COMMANDS:
        return True
    return validate_log_read_command(command)
