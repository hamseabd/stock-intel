# Stock Intel — DIY Market Intelligence Platform

## What This Is

A serverless market intelligence platform deployed on AWS. Interact via Telegram from your phone. Tracks your portfolio, scans for unusual options flow, congressional trades, dark pool activity, technical signals, and pushes alerts proactively.

## Architecture

```
Telegram ←→ API Gateway ←→ Lambda (bot handler)
                                  ↓
                           Command Router
                          /              \
                   Direct ($0)         AI (~$0.02)
                   22 commands         5 commands
                       ↓                    ↓
                   Tools layer         Tools layer → Claude
                       ↓                    ↓
                   Formatters          Formatters + AI synthesis
                       ↓                    ↓
                   Telegram response   Telegram response

EventBridge (cron) → Lambda (scanners) → SQS → Lambda (alert sender) → Telegram
```

## Project Structure

```
infrastructure/           Terraform IaC
src/bot/                  Telegram handler, command router, AI commands
src/tools/                Data tools (prices, options, congress, darkpool, etc.)
src/scanners/             8 proactive scanners on cron
src/shared/               Config, DB, S3, math, formatters, logging
src/dashboard/            S3 static site (HTML/JS)
scripts/                  Build, deploy, seed
tests/                    286 tests (unit + E2E)
```

## Commands

| Category | Commands | Claude? |
|----------|----------|:-------:|
| Portfolio | `/pnl`, `/portfolio`, `/options`, `/put`, `/update`, `/history` | No |
| Research | `/news`, `/flow`, `/technicals`, `/darkpool`, `/congress`, `/earnings` | No |
| Intel | `/movers`, `/sector`, `/scan`, `/compare` | No |
| AI | `/brief`, `/catalyst`, `/risk`, `/analyze`, `/ask` | Yes |
| Config | `/watch`, `/unwatch`, `/watchlist`, `/alerts`, `/threshold`, `/help` | No |

## Key Design Decisions

- **Two-path router**: Direct commands are pure code ($0). AI commands gather data with code, then send a compact summary to Claude (~$0.02).
- **Docker Lambda images**: Avoids binary compatibility issues (numpy/scipy on ARM64).
- **NaN handling**: yfinance returns NaN for volume/OI. All numeric parsing uses safe conversion.
- **Structured logging**: JSON in Lambda (CloudWatch), colored locally. Timer context manager for durations.
- **Single mock point**: `telegram_client._post()` — all Telegram calls go through one function.

## Deploy

```bash
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
cd infrastructure && terraform init && terraform apply
bash scripts/build.sh
bash scripts/deploy.sh
```

## Test

```bash
python -m pytest tests/ -v   # 286 tests, ~3.5s
```

## Adding a New Tool

1. Create function in `src/tools/` with type hints and docstring
2. Import in `src/bot/commands.py`, add a `cmd_` function and register in `DIRECT_COMMANDS`
3. Add help text in `src/bot/help.py` HELP_DETAIL dict
4. Add tests in `tests/` (unit + E2E)
5. Optionally add a scanner in `src/scanners/`

## Adding a New Scanner

1. Create `src/scanners/new_scanner.py` with a `run_new_scan()` function
2. Register in `src/scanners/handler.py` SCANNERS dict
3. Add EventBridge rule in `infrastructure/main.tf`
4. Add Lambda permission for the new EventBridge rule
