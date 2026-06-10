# AWS Labs EC2 Rescue MCP Server

An AWS Labs Model Context Protocol (MCP) server for EC2 Rescue.
Uses AWS Systems Manager (SSM) `SendCommand` to run [EC2 Rescue Linux](https://github.com/awslabs/aws-ec2rescue-linux) diagnostic modules on EC2 instances and return results to AI tools.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (package manager)
- AWS credentials configured (via environment variables or AWS profile)
- Target EC2 instances must have:
  - SSM Agent installed and running
  - [EC2 Rescue Linux](https://github.com/awslabs/aws-ec2rescue-linux) installed (or use the `install_ec2_rescue` tool to install it)
  - An IAM instance profile with `AmazonSSMManagedInstanceCore` policy attached

## Available Tools

By default, the server registers 32 curated modules plus 2 utility tools. Use `--all` to register all 209+ modules.

### Utility Tools

| Tool | Description |
|------|-------------|
| `list_instances` | List EC2 instances accessible via SSM |
| `install_ec2_rescue` | Install EC2 Rescue for Linux via `AWSSupport-InstallEC2Rescue` SSM Automation |

### Default ec2rl Modules (32 tools)

Each module is exposed as `run_ec2rl_<name>`.

| Category | Modules |
|----------|---------|
| System basics | `cpuinfo`, `meminfo`, `kernelversion`, `osrelease`, `lsblk`, `mounts`, `ps` |
| Network | `ifconfig`, `iproute`, `netstatanp`, `ethtool`, `resolvconf`, `dig` |
| Logs | `journal`, `dmesg`, `messages`, `cloudinitlog` |
| Kernel / boot | `kernelpanic`, `hungtasks`, `oomkiller`, `softlockup`, `fstabfailures`, `kernelcmdline`, `lsmod` |
| Performance | `iostat`, `vmstat`, `top`, `sysctl` |
| Packages / config | `dpkgpackages`, `rpmpackages`, `kernelconfig`, `fstab` |

Use `--modules=tcpdump,strace` to add specific modules beyond the defaults, or `--all` for all 209+.

### Not supported

These upstream [EC2 Rescue for Linux](https://github.com/awslabs/aws-ec2rescue-linux) features are intentionally not exposed by this MCP server:

- **Upload** (`ec2rl upload`) — uploading results to S3 or an AWS Support URL.
- **Bug report** (`ec2rl bug-report`) — generating a bug report bundle.
- **Version / config** (`ec2rl version`, `version-check`, `menu-config`, `save-config`) — version checks and interactive/saved configuration.
- **Batch runs** — modules run one at a time (`run_ec2rl_<module>`); ec2rl's bulk `run` over all modules or by class/domain is not exposed.

## Setup

### Install dependencies

```bash
uv sync
```

### Run the server directly

```bash
AWS_REGION=ap-northeast-1 AWS_PROFILE=your-profile uv run awslabs.ec2-rescue-mcp-server
```

### Claude Code (claude)

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "awslabs.ec2-rescue-mcp-server": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ec2-rescue-mcp-server",
        "run",
        "awslabs.ec2-rescue-mcp-server"
      ],
      "env": {
        "AWS_REGION": "ap-northeast-1",
        "AWS_PROFILE": "your-profile"
      }
    }
  }
}
```

### Kiro

Add to `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "awslabs.ec2-rescue-mcp-server": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ec2-rescue-mcp-server",
        "run",
        "awslabs.ec2-rescue-mcp-server"
      ],
      "env": {
        "AWS_REGION": "ap-northeast-1",
        "AWS_PROFILE": "your-profile"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS):

```json
{
  "mcpServers": {
    "ec2-rescue": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ec2-rescue-mcp-server",
        "run",
        "awslabs.ec2-rescue-mcp-server"
      ],
      "env": {
        "AWS_REGION": "ap-northeast-1",
        "AWS_PROFILE": "your-profile"
      }
    }
  }
}
```

> **Note:** Replace `/path/to/ec2-rescue-mcp-server` with the absolute path to this repository, and `your-profile` with your AWS profile name.

## IAM Policy (MCP Server Side)

The IAM principal running this MCP server needs the following minimum permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SSMReadOnly",
      "Effect": "Allow",
      "Action": [
        "ssm:DescribeInstanceInformation",
        "ssm:GetCommandInvocation",
        "ssm:ListCommands",
        "ssm:ListCommandInvocations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SSMSendCommand",
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ssm:*::document/AWS-RunShellScript",
        "arn:aws:ssm:*::document/AWS-ConfigureAWSPackage",
        "arn:aws:ec2:*:ACCOUNT_ID:instance/*",
        "arn:aws:ssm:*:ACCOUNT_ID:managed-instance/*"
      ]
    },
    {
      "Sid": "EC2DescribeInstances",
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
    },
    {
      "Sid": "SSMAutomationInstallStart",
      "Effect": "Allow",
      "Action": "ssm:StartAutomationExecution",
      "Resource": "arn:aws:ssm:*::automation-definition/AWSSupport-InstallEC2Rescue:*"
    },
    {
      "Sid": "SSMAutomationInstallDescribe",
      "Effect": "Allow",
      "Action": "ssm:DescribeAutomationExecutions",
      "Resource": "*"
    }
  ]
}
```

> **Note:** Replace `ACCOUNT_ID` with your AWS account ID. The `managed-instance/*` resource covers hybrid-activated nodes (`mi-*`). To restrict further, narrow instance resources to specific IDs or use tag-based conditions. The `SSMAutomationInstall` statement is only required if you use the `install_ec2_rescue` tool.

## Authentication

AWS credentials are passed via environment variables. Supported options:

| Variable | Description |
|----------|-------------|
| `AWS_PROFILE` | AWS CLI named profile |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | Static credentials |

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--all` | off | Register all 209+ ec2rl modules as MCP tools. |
| `--modules NAME,...` | (none) | Additional module names beyond the default 32. |
| `--remediate` | off | Register remediation modules (openssh, rebuildinitrd, etc.). |
| `--allow-install` | off | Allow `install_ec2_rescue` without elicitation consent. |
| `--allow-perfimpact` | off | Permit perfimpact modules (tcpdump, perf, strace). Denied by default. |
| `--mod-dir PATH` | bundled `mod.d/` | Override module YAML directory. |
| `--transport {stdio,streamable-http}` | `stdio` | MCP transport. |
| `--host HOST` | `127.0.0.1` | Bind host (streamable-http only). |
| `--port PORT` | `8000` | Bind port (streamable-http only). |

### Streamable HTTP example

```bash
uv run awslabs.ec2-rescue-mcp-server \
    --transport streamable-http --host 0.0.0.0 --port 8080
```

Endpoint: `http://<host>:<port>/mcp`.

### All modules with installation enabled

```bash
uv run awslabs.ec2-rescue-mcp-server --all --allow-install --remediate
```

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest --cov --cov-branch --cov-report=term-missing
```

## Elicitation (User Consent)

The server uses [MCP elicitation](https://modelcontextprotocol.io/docs/concepts/elicitation) to request user confirmation before:

- **Installing EC2 Rescue** (`install_ec2_rescue`) — bypass with `--allow-install`
- **Fetching large output** (messages, dmesg) — suggests `journal` with `--since`/`--until` instead
- **Omitting grep_keys** (kernelconfig, sysctl, dpkgpackages, rpmpackages) — warns about large output

If your MCP client does not support elicitation, use the CLI bypass flags listed above.

> **Note on agentic clients:** MCP elicitation is **not** a reliable safety control when the client is an agent (e.g. Claude Code), because the agent can auto-answer the consent prompt without a human in the loop. For this reason **perfimpact modules** (tcpdump, perf, strace) are **fail-closed**: they are denied unless an operator explicitly starts the server with `--allow-perfimpact`. This is a startup flag precisely so the permission is an operator decision the agent cannot grant itself — not a runtime prompt.
