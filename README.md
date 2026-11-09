# costfence

Real-time spending guard for AI API usage. A lightweight proxy that sits between your AI tools and the API, counts tokens, and kills the connection when your budget is hit.

Stop worrying about runaway agent loops burning through your credits.

## Features

- **Budget enforcement** — per-session, hourly, daily, and per-project spending limits
- **Kill switch** — returns 429 when budget is exceeded, stopping all API calls
- **Multi-provider** — supports OpenAI, Anthropic, and AWS Bedrock
- **Real-time tracking** — token counting from request/response bodies
- **TUI dashboard** — live Rich terminal dashboard showing spend, budgets, and recent requests
- **Persistent logging** — SQLite database for usage history
- **Streaming support** — tracks costs through SSE streaming responses
- **Zero config start** — sensible defaults, customize via YAML or env vars

## Quick Start

```bash
pip install -e .

# Initialize config (optional — defaults work out of the box)
costfence init

# Start the proxy
costfence start

# Point your AI tools to the proxy
export OPENAI_BASE_URL=http://127.0.0.1:8990
export ANTHROPIC_BASE_URL=http://127.0.0.1:8990
```

## Usage

### Start the proxy

```bash
costfence start                          # default: 127.0.0.1:8990
costfence start --port 9000              # custom port
costfence start --config ./myconfig.yaml # custom config
```

### Check spending

```bash
costfence status
```

```
  costfence — session a1b2c3d4e5f6

  Session     $0.0342 / $5.00  (remaining: $4.9658)
  Hourly      $0.0342 / $10.00 (remaining: $9.9658)
  Daily       $0.1205 / $50.00 (remaining: $49.8795)
  Project     $0.1205 / unlimited  (remaining: -)

  Tokens — input: 12,450  output: 3,200
```

### Live dashboard

```bash
costfence dashboard
```

### Reset counters

```bash
costfence reset                # reset session
costfence reset --scope all    # reset everything
```

## Configuration

Create `~/.costfence/config.yaml`:

```yaml
budgets:
  per_session: 5.0    # USD
  per_hour: 10.0
  per_day: 50.0
  per_project: 100.0

targets:
  openai: https://api.openai.com
  anthropic: https://api.anthropic.com

port: 8990
host: 127.0.0.1
project: my-project
```

Or use environment variables:

```bash
export COSTFENCE_SESSION_BUDGET=5.0
export COSTFENCE_HOURLY_BUDGET=10.0
export COSTFENCE_DAILY_BUDGET=50.0
export COSTFENCE_PROJECT=my-project
export COSTFENCE_PORT=8990
```

## Using with AI Tools

### Claude Code

```bash
costfence start &
export ANTHROPIC_BASE_URL=http://127.0.0.1:8990
claude
```

### Cursor / Continue / Aider

Set the OpenAI base URL in your tool's settings to `http://127.0.0.1:8990`.

### AWS Bedrock

Configure the Bedrock endpoint in `config.yaml`:

```yaml
targets:
  bedrock: https://bedrock-runtime.us-east-1.amazonaws.com
```

## How It Works

1. costfence starts a FastAPI reverse proxy on `127.0.0.1:8990`
2. Your AI tools send requests to costfence instead of the API directly
3. costfence forwards requests to the real API, tracking tokens in real-time
4. When a budget limit is hit, costfence returns `429 Too Many Requests`
5. All usage is logged to `~/.costfence/usage.db` (SQLite)

## API

The proxy exposes two management endpoints:

- `GET /costfence/status` — current spend, budgets, and token counts
- `POST /costfence/reset?scope=session|all` — reset spending counters

## License

MIT
