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

"""MCP elicitation schemas and the perfimpact consent gate."""

from __future__ import annotations

from awslabs.ec2_rescue_mcp_server.ec2rl import Ec2rlModule
from awslabs.ec2_rescue_mcp_server.responses import ModuleResponse
from loguru import logger
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field


class _ReadAllElicitation(BaseModel):
    """Schema for the read-all elicitation prompt to the user."""

    read_all: bool = Field(
        description=(
            'If True, the server reads every file under '
            '<output_dir>/gathered_out/<module>/ and returns their contents. '
            'If False (or you cancel), the server returns just the file '
            'listing and you can re-invoke the tool with specific paths.'
        ),
    )


class _PerfImpactConsent(BaseModel):
    """Schema for asking the user to confirm a perfimpact module run."""

    confirm: bool = Field(
        description=(
            'Confirm that this diagnostic may impact running processes '
            '(packet capture, syscall tracing, CPU profiling). Set true '
            'to proceed; false to abort.'
        ),
    )


class _FetchAllConfirmation(BaseModel):
    """Schema for confirming a full (unfiltered) fetch when grep_keys is omitted."""

    confirm: bool = Field(
        description=(
            'The output of this module can be very large. Set true to '
            'fetch all output without filtering; false to abort and '
            're-invoke with specific grep_keys.'
        ),
    )


class _LargeOutputConfirmation(BaseModel):
    """Schema for confirming execution of a module with potentially large output."""

    confirm: bool = Field(
        description=(
            'This module produces potentially very large output that may '
            'consume significant context. Set true to proceed; false to '
            'abort and consider an alternative module or approach.'
        ),
    )


class _InstallEc2RescueConsent(BaseModel):
    """Schema for asking the user to confirm EC2 Rescue installation."""

    confirm: bool = Field(
        description=(
            'This will run the AWSSupport-InstallEC2Rescue SSM Automation '
            'document on the target instance, which downloads and installs '
            'EC2 Rescue for Linux. Set true to proceed; false to abort.'
        ),
    )


# Operator-level escape hatch for environments whose MCP client does not
# support elicitation. Set by main() from the --skip-perfimpact-confirm
# CLI flag. When True, the server skips the elicitation prompt and
# proceeds straight to running the perfimpact module (still appending
# `--perfimpact=true` to the ec2rl command, which ec2rl itself requires).
_SKIP_PERFIMPACT_CONFIRM: bool = False

# Whether the install_ec2_rescue tool is registered. Set by main() from
# the --allow-install CLI flag. When False (default), the tool is not
# registered and installation requires elicitation consent. When True,
# the tool is registered and proceeds without elicitation (for MCP
# clients that don't support elicitation).
_ALLOW_INSTALL: bool = False


async def _perfimpact_consent_gate(
    ctx: Context,
    instance_id: str,
    module: Ec2rlModule,
) -> str | None:
    """Gate a perfimpact module run on explicit user consent.

    Callers must already have checked ``module.perfimpact`` before invoking
    this function (matching the pattern used by ``_software_precheck``).

    Returns None when the run may proceed (operator override or user
    accepted). Returns an Aborted JSON envelope when the user declined or
    elicitation isn't available and the operator hasn't opted out.
    """
    if _SKIP_PERFIMPACT_CONFIRM:
        logger.info(
            f'Module {module.name!r} is perfimpact; consent gate skipped '
            'by --skip-perfimpact-confirm operator override.'
        )
        return None

    message = (
        f"Module '{module.name}' may impact running processes on "
        f'{instance_id} (packet capture, syscall tracing, or CPU '
        "profiling). The ec2rl '--perfimpact=true' flag is required to "
        'run it. Confirm to proceed.'
    )
    try:
        elicit_result = await ctx.elicit(
            message=message, schema=_PerfImpactConsent
        )
    except Exception as e:
        logger.error(
            f'Elicitation failed for perfimpact gate on {module.name!r}: '
            f'{e!r}; aborting (set --skip-perfimpact-confirm at startup '
            'to bypass when the client does not support elicitation).'
        )
        return ModuleResponse(
            instance_id=instance_id,
            module=module.name,
            status='Aborted',
            reason='perfimpact_consent_unavailable',
            message=(
                'This module requires user consent because it may '
                'impact running processes, but the MCP client does '
                'not support elicitation. Restart the server with '
                '--skip-perfimpact-confirm to bypass.'
            ),
        ).as_json()

    if (
        elicit_result.action == 'accept'
        and elicit_result.data is not None
        and elicit_result.data.confirm
    ):
        logger.info(
            f'User consented to running perfimpact module {module.name!r} '
            f'on {instance_id}.'
        )
        return None

    logger.info(
        f'User declined perfimpact module {module.name!r} on {instance_id} '
        f'(action={elicit_result.action!r}).'
    )
    return ModuleResponse(
        instance_id=instance_id,
        module=module.name,
        status='Aborted',
        reason='perfimpact_consent_denied',
        message=(
            'User declined to run a module that may impact running processes.'
        ),
    ).as_json()


async def _fetch_all_elicitation_gate(
    ctx: Context,
    instance_id: str,
    module: Ec2rlModule,
    key_description: str,
) -> bool:
    """Ask the user whether to fetch all output when grep_keys was omitted.

    Returns True when the user explicitly confirmed (proceed with full
    fetch). Returns False on decline, cancel, or elicitation failure —
    the caller should return an Aborted response prompting the user to
    specify keys.
    """
    message = (
        f"Module '{module.name}' output can be very large when "
        f'`grep_keys` is not specified. For targeted results, re-invoke '
        f'with `grep_keys=["<key1>", ...]` (each key: {key_description}). '
        f'Confirm to fetch ALL output anyway.'
    )
    try:
        elicit_result = await ctx.elicit(
            message=message, schema=_FetchAllConfirmation
        )
    except Exception as e:
        logger.info(
            f'Elicitation unavailable for fetch-all gate on {module.name!r}: '
            f'{e!r}; denying full fetch.'
        )
        return False

    if (
        elicit_result.action == 'accept'
        and elicit_result.data is not None
        and elicit_result.data.confirm
    ):
        logger.info(
            f'User confirmed fetching all output for {module.name!r} on '
            f'{instance_id}.'
        )
        return True

    logger.info(
        f'User declined full fetch for {module.name!r} on {instance_id} '
        f'(action={elicit_result.action!r}).'
    )
    return False


async def _large_output_elicitation_gate(
    ctx: Context,
    instance_id: str,
    module: Ec2rlModule,
    warning_message: str,
) -> str | None:
    """Gate modules with potentially large output on user confirmation.

    Returns None when the run may proceed (user confirmed). Returns an
    Aborted JSON envelope when the user declined, cancelled, or
    elicitation is unavailable.
    """
    try:
        elicit_result = await ctx.elicit(
            message=warning_message, schema=_LargeOutputConfirmation
        )
    except Exception as e:
        logger.info(
            f'Elicitation unavailable for large-output gate on '
            f'{module.name!r}: {e!r}; aborting.'
        )
        return ModuleResponse(
            instance_id=instance_id,
            module=module.name,
            status='Aborted',
            reason='large_output_not_confirmed',
            hint=warning_message,
        ).as_json()

    if (
        elicit_result.action == 'accept'
        and elicit_result.data is not None
        and elicit_result.data.confirm
    ):
        logger.info(
            f'User confirmed large-output module {module.name!r} on '
            f'{instance_id}.'
        )
        return None

    logger.info(
        f'User declined large-output module {module.name!r} on '
        f'{instance_id} (action={elicit_result.action!r}).'
    )
    return ModuleResponse(
        instance_id=instance_id,
        module=module.name,
        status='Aborted',
        reason='large_output_not_confirmed',
        hint=warning_message,
    ).as_json()


async def _install_consent_gate(
    ctx: Context,
    instance_id: str,
) -> str | None:
    """Gate the install_ec2_rescue tool on explicit user consent.

    Returns None when the install may proceed (operator --allow-install
    flag or user accepted elicitation). Returns an Aborted JSON string
    when the user declined or elicitation isn't available and the
    operator hasn't opted in.
    """
    if _ALLOW_INSTALL:
        logger.info(
            f'install_ec2_rescue on {instance_id}: consent gate skipped '
            'by --allow-install operator override.'
        )
        return None

    message = (
        f'This will run the AWSSupport-InstallEC2Rescue SSM Automation '
        f'document on {instance_id}, which downloads and installs '
        f'EC2 Rescue for Linux. Confirm to proceed.'
    )
    try:
        elicit_result = await ctx.elicit(
            message=message, schema=_InstallEc2RescueConsent
        )
    except Exception as e:
        logger.warning(
            f'Elicitation unavailable for install gate on {instance_id}: '
            f'{e!r}; aborting (start the server with --allow-install to '
            'bypass when the client does not support elicitation).'
        )
        return ModuleResponse(
            instance_id=instance_id,
            module='install_ec2_rescue',
            status='Aborted',
            reason='install_consent_unavailable',
            message=(
                'Installing EC2 Rescue requires user consent, but the MCP '
                'client does not support elicitation. Restart the server '
                'with --allow-install to bypass.'
            ),
        ).as_json()

    if (
        elicit_result.action == 'accept'
        and elicit_result.data is not None
        and elicit_result.data.confirm
    ):
        logger.info(
            f'User consented to installing EC2 Rescue on {instance_id}.'
        )
        return None

    logger.info(
        f'User declined EC2 Rescue installation on {instance_id} '
        f'(action={elicit_result.action!r}).'
    )
    return ModuleResponse(
        instance_id=instance_id,
        module='install_ec2_rescue',
        status='Aborted',
        reason='install_consent_denied',
        message='User declined to install EC2 Rescue on the instance.',
    ).as_json()
