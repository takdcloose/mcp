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

"""YAML loader for EC2 Rescue Linux module definitions in ``mod.d/``."""

import os
import yaml
from awslabs.ec2_rescue_mcp_server.ec2rl import Ec2rlModule
from loguru import logger


_EC2RL_MODULE_TAG = '!ec2rlcore.module.Module'


def _parse_space_separated(value: object) -> list[str]:
    """Split a whitespace-separated string; non-strings become ``[]``."""
    if not isinstance(value, str):
        return []
    return [part for part in value.split() if part]


def _parse_package(value: object) -> str:
    """First valid identifier token from the YAML ``package:`` list, or ``''``.

    Entries look like ``- atop http://...`` or ``- !!str`` (empty).
    """
    if not isinstance(value, list):
        return ''
    for entry in value:
        if not isinstance(entry, str):
            continue
        stripped = entry.strip()
        if not stripped:
            continue
        first = stripped.split()[0]
        if first and all(c.isalnum() or c in '-_' for c in first):
            return first
    return ''


def _parse_bool(value: object) -> bool:
    """Coerce bool or ``"True"``/``"False"`` strings; anything else → False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == 'true'
    return False


def _module_from_yaml_doc(doc: dict) -> Ec2rlModule | None:
    """Build an Ec2rlModule from a parsed YAML doc; returns None if invalid."""
    if not isinstance(doc, dict):
        return None
    name = doc.get('name')
    if not isinstance(name, str) or not name:
        return None

    constraint = doc.get('constraint') or {}
    if not isinstance(constraint, dict):
        constraint = {}

    return Ec2rlModule(
        name=name,
        log_subpath=f'mod_out/run/{name}.log',
        title=str(doc.get('title') or ''),
        helptext=str(doc.get('helptext') or ''),
        required_args=_parse_space_separated(constraint.get('required')),
        optional_args=_parse_space_separated(constraint.get('optional')),
        remediation=_parse_bool(doc.get('remediation')),
        constraint_class=str(constraint.get('class') or ''),
        domain=str(constraint.get('domain') or ''),
        package=_parse_package(doc.get('package')),
        software=str(constraint.get('software') or '').strip(),
        perfimpact=_parse_bool(constraint.get('perfimpact')),
    )


def load_modules_from_yaml_dir(
    mod_dir: str,
    include_remediation: bool = False,
) -> dict[str, Ec2rlModule]:
    """Load ``*.yaml`` from ``mod_dir``; skips remediation modules unless enabled."""
    if not os.path.isdir(mod_dir):
        logger.warning(f'Module directory does not exist: {mod_dir}')
        return {}

    modules: dict[str, Ec2rlModule] = {}
    for filename in sorted(os.listdir(mod_dir)):
        if not filename.endswith('.yaml'):
            continue
        path = os.path.join(mod_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace(_EC2RL_MODULE_TAG, '')
            doc = yaml.safe_load(content)
        except (OSError, yaml.YAMLError) as e:
            logger.warning(f'Skipping {filename}: failed to parse YAML: {e}')
            continue

        module = _module_from_yaml_doc(doc)
        if module is None:
            logger.warning(f'Skipping {filename}: missing or invalid module name')
            continue

        if module.remediation and not include_remediation:
            logger.debug(
                f'Skipping remediation module {module.name!r} '
                f'(use --remediate to enable)'
            )
            continue

        modules[module.name] = module

    logger.info(
        f'Loaded {len(modules)} ec2rl modules from {mod_dir} '
        f'(include_remediation={include_remediation})'
    )
    return modules
