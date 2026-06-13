# AWS Labs EC2 Rescue MCP Server

An MCP server that enables AI agents to diagnose EC2 instance issues by running [EC2 Rescue Linux](https://github.com/awslabs/aws-ec2rescue-linux) modules through AWS Systems Manager (SSM). Each `ec2rl` diagnostic module is exposed as an individual MCP tool — agents can collect logs and metrics without SSH access, arbitrary shell commands, or manual module knowledge.

```
AI Client (Claude, Kiro, etc.)
    │  MCP (stdio / Streamable HTTP)
    ▼
EC2 Rescue MCP Server
    │  boto3 (SSM SendCommand / EC2 DescribeInstances)
    ▼
AWS Systems Manager ──▶ EC2 instance (SSM Agent + ec2rl)
```

### Why use this server?

- **No arbitrary commands** — Agents can only call registered `ec2rl` modules, not run arbitrary shell commands on the instance.
- **No interactive shell needed** — Diagnostics run through SSM `SendCommand`, eliminating the need to open SSH or Session Manager sessions.
- **Symptom-driven module selection** — The AI sees a structured tool list and can match modules to symptoms like "high CPU" or "kernel panic."
- **Accessible triage** — Less-experienced engineers can ask questions like "Why is `i-0abc123` slow?" and receive AI-gathered diagnostic outputs with explanations.
- **Credentials stay server-side** — AWS keys remain on the MCP server; clients never hold them.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (package manager)
- AWS credentials configured (via environment variables or AWS profile)
- Target EC2 instances must be [SSM managed nodes](https://docs.aws.amazon.com/systems-manager/latest/userguide/managed_instances.html)
- [EC2 Rescue Linux](https://github.com/awslabs/aws-ec2rescue-linux) installed on target instances (or use the `install_ec2_rescue` tool to install it)

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

## Quickstart


| Kiro | Cursor | VS Code |
|:----:|:------:|:-------:|
| [![Add to Kiro](https://kiro.dev/images/add-to-kiro.svg)](https://kiro.dev/launch/mcp/add?name=awslabs.ec2-rescue-mcp-server&config=%7B%22command%22%3A%20%22uvx%22%2C%20%22args%22%3A%20%5B%22awslabs.ec2-rescue-mcp-server%40latest%22%5D%2C%20%22env%22%3A%20%7B%22FASTMCP_LOG_LEVEL%22%3A%20%22ERROR%22%2C%20%22AWS_PROFILE%22%3A%20%22your-aws-profile%22%2C%20%22AWS_REGION%22%3A%20%22us-east-1%22%7D%2C%20%22disabled%22%3A%20false%2C%20%22autoApprove%22%3A%20%5B%5D%7D) | [![Install MCP Server](https://cursor.com/deeplink/mcp-install-light.svg)](https://cursor.com/en/install-mcp?name=awslabs.ec2-rescue-mcp-server&config=eyJjb21tYW5kIjoidXZ4IGF3c2xhYnMuZWMyLXJlc2N1ZS1tY3Atc2VydmVyQGxhdGVzdCIsImVudiI6eyJGQVNUTUNQX0xPR19MRVZFTCI6IkVSUk9SIiwiQVdTX1BST0ZJTEUiOiJ5b3VyLWF3cy1wcm9maWxlIiwiQVdTX1JFR0lPTiI6InVzLWVhc3QtMSJ9LCJkaXNhYmxlZCI6ZmFsc2UsImF1dG9BcHByb3ZlIjpbXX0%3D) | [![Install on VS Code](https://img.shields.io/badge/Install_on-VS_Code-FF9900?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=awslabs.ec2-rescue-mcp-server&config=%7B%22command%22%3A%22uvx%20awslabs.ec2-rescue-mcp-server%40latest%22%2C%22env%22%3A%7B%22FASTMCP_LOG_LEVEL%22%3A%22ERROR%22%2C%22AWS_PROFILE%22%3A%22your-aws-profile%22%2C%22AWS_REGION%22%3A%22us-east-1%22%7D%2C%22disabled%22%3Afalse%2C%22autoApprove%22%3A%5B%5D%7D) |

You can modify the settings of your MCP client to run your local server (e.g. for Kiro, ~/.kiro/settings/mcp.json)

### For Mac/Linux:

```json
{
  "mcpServers": {
    "awslabs.ec2-rescue-mcp-server": {
      "command": "uvx",
      "args": [
        "awslabs.ec2-rescue-mcp-server@latest"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_PROFILE": "your-profile"
        "AWS_REGION": "us-east-1",
      },
      "autoApprove": [],
      "disabled": false
    }
  }
}
```

### For Windows:

```json
{
  "mcpServers": {
    "awslabs.ec2-rescue-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "awslabs.ec2-rescue-mcp-server@latest",
        "awslabs.ec2-rescue-mcp-server.exe"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_PROFILE": "your-profile"
        "AWS_REGION": "us-east-1",
      },
      "autoApprove": [],
      "disabled": false
    }
  }
}
```

To specify a flag (for example, to enable all modules), add it to the `args` array:

```json
{
  "mcpServers": {
    "awslabs.ec2-rescue-mcp-server": {
      "command": "uvx",
      "args": [
        "awslabs.ec2-rescue-mcp-server@latest",
        "-all"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_PROFILE": "your-profile"
        "AWS_REGION": "us-east-1",
      },
      "autoApprove": [],
      "disabled": false
    }
  }
}
```

> **Note:** Replace `your-profile` with your AWS profile name and `us-east-1` with your target region.

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
| `--allow-perfimpact` | off | Permit perfimpact modules (tcpdump, perf, strace). Off by default — only a human operator can enable this at server startup; agents cannot turn it on. |
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

