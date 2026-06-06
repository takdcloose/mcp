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

"""Constants for the EC2 Rescue MCP Server."""

from awslabs.ec2_rescue_mcp_server import __version__
from botocore.config import Config


# AWS SSM
SSM_DOCUMENT_NAME: str = 'AWS-RunShellScript'
SSM_DELIVERY_TIMEOUT_SECONDS: int = 60  # SSM waits for the agent to pick up the command
SSM_EXECUTION_TIMEOUT_SECONDS: int = 3600  # agent kills the command after this
SSM_POLL_DEADLINE_SECONDS: int = 3600  # client gives up polling after this
SSM_POLL_INTERVAL_SECONDS: float = 2.0

DEFAULT_AWS_REGION: str = 'us-east-1'
SERVER_NAME: str = 'awslabs.ec2-rescue-mcp-server'
DEFAULT_MOD_DIR: str = 'mod.d'  # bundled mod.d/, resolved by server.main()

BOTO_CONFIG: Config = Config(
    user_agent_extra=f'md/awslabs#mcp#ec2-rescue-mcp-server#{__version__}'
)

# SSM Automation — AWSSupport-InstallEC2Rescue
SSM_INSTALL_DOCUMENT_NAME: str = 'AWSSupport-InstallEC2Rescue'
SSM_AUTOMATION_POLL_INTERVAL_SECONDS: float = 5.0
SSM_AUTOMATION_POLL_DEADLINE_SECONDS: float = 300.0
