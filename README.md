# Stock Intel

A DIY market intelligence platform — like Unusual Whales, but yours, for ~$3/month.

Interact via **Telegram** from your phone. Deployed serverless on **AWS**. Tracks portfolio P&L, scans for unusual options flow, congressional stock trades, dark pool activity, and technical signals. Pushes proactive alerts.

## Features

**27 commands** across 5 categories:

| Category | What It Does | Uses AI? |
|----------|-------------|:--------:|
| **Portfolio** | Live P&L, options Greeks, trade logging | No |
| **Research** | News, options flow, technicals, dark pool, Congress, earnings | No |
| **Intelligence** | Movers, sector heatmap, full ticker scan, comparison | No |
| **AI Analysis** | Morning brief, catalyst analysis, risk scan, deep analysis | Yes |
| **Config** | Watchlist, alert settings, price thresholds | No |

**8 automated scanners** push alerts to Telegram:
- Price thresholds & big movers (every 5 min)
- Unusual options activity (every 30 min)
- Congressional trades & cluster detection (every 6 hours)
- Dark pool anomalies (daily after close)
- Technical signals — RSI/MACD extremes (every hour)
- Earnings countdown — 14d, 7d, 3d, 1d (daily)
- Breaking news keywords (every 30 min)

## Architecture

```
┌──────────┐       ┌─────────────┐       ┌─────────────────┐
│ Telegram │◄─────►│ API Gateway │──────►│ Lambda: Bot     │
│ (phone)  │       │ (HTTP API)  │       │ (Docker/ARM64)  │
└──────────┘       └─────────────┘       └────────┬────────┘
                                                  │
     ┌───────────────────────────┬────────────────┤
     │                           │                │
┌────▼─────┐  ┌─────────────┐  ┌▼────────┐  ┌────▼────┐
│ DynamoDB │  │ EventBridge  │  │ Claude  │  │   S3    │
│ 5 tables │  │ 8 schedules  │  │ Sonnet  │  │ Dashboard│
└──────────┘  └──────┬───────┘  └─────────┘  └─────────┘
                     │
              ┌──────▼───────┐       ┌──────────┐
              │ Lambda:      │──────►│   SQS    │───► Telegram alerts
              │ Scanners     │       │  Queue   │
              └──────────────┘       └──────────┘
```

## Cost

| Component | Monthly Cost |
|-----------|-------------|
| AWS (Lambda, DynamoDB, S3, API Gateway, SQS, EventBridge) | ~$0.03 |
| Claude API (AI commands only — 80% of commands skip it) | ~$1-3 |
| Data sources (yfinance, Capitol Trades, FINRA, Yahoo RSS) | $0 |
| Telegram Bot API | $0 |
| **Total** | **~$1-3/month** |

## Quick Start

### Prerequisites

- AWS account + CLI configured
- Docker
- Terraform >= 1.5
- Python 3.12
- Telegram account

### Setup

```bash
# 1. Clone
git clone https://github.com/yourusername/stock-intel.git
cd stock-intel

# 2. Create Telegram bot
# Message @BotFather → /newbot → copy the token

# 3. Get your chat ID
# Send a message to your bot, then:
curl https://api.telegram.org/bot<TOKEN>/getUpdates
# Find "chat":{"id": YOUR_CHAT_ID}

# 4. Configure
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
# Edit terraform.tfvars with your token, chat_id, and Anthropic API key

# 5. Deploy
cd infrastructure
terraform init
terraform apply

# 6. Build & push Docker images
bash scripts/build.sh

# 7. Update Lambda functions + set webhook
bash scripts/deploy.sh

# 8. Seed your portfolio
TELEGRAM_CHAT_ID=your-id AWS_REGION=us-east-1 python scripts/seed_portfolio.py

# 9. Test — send /help to your bot!
```

### Local Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt
pip install pytest

# Run tests
python -m pytest tests/ -v
```

## Commands Reference

### Portfolio
```
/pnl [TICKER]           Live P&L table (all positions or one)
/portfolio               All positions with status
/options                 Analyze all open options (Greeks, recommendations)
/put                     Analyze open puts specifically
/update [trade]          Record a trade ("sold 50 AMZN at 195")
/history                 Recent trade log
```

### Research
```
/news TICKER             Latest headlines from Yahoo Finance
/flow TICKER             Unusual options activity scan
/technicals TICKER       RSI, MACD, SMA, Bollinger, support/resistance
/darkpool TICKER         Dark pool volume % and short volume
/congress TICKER         Congressional trades on this ticker
/earnings TICKER         Next earnings date and countdown
```

### Intelligence
```
/flow                    Unusual activity across all held + watched tickers
/congress                All recent congressional trades + cluster alerts
/darkpool                Dark pool flags across portfolio + watchlist
/movers                  Biggest portfolio movers today
/sector                  Congressional trading by sector
/scan TICKER             Run ALL checks on a single ticker
/compare T1 T2           Side-by-side comparison
```

### AI-Powered
```
/brief                   Full morning intelligence brief
/catalyst TICKER         Upcoming catalysts + impact analysis
/risk                    Portfolio risk scan + recommendations
/analyze TICKER          Complete picture + investment thesis
/ask [question]          Ask anything ("Should I roll my put?")
```

### Watchlist & Alerts
```
/watch TICKER [T2 T3]    Add to watchlist
/unwatch TICKER          Remove from watchlist
/watchlist               Show watched tickers
/alerts                  Show alert config
/alerts on/off           Enable/disable all alerts
/alerts mute 2h          Snooze alerts
/threshold T above $N    Set price alert
/threshold clear T       Remove price alerts
/help [command]          Show all commands or details for one
```

## Data Sources

| Source | Data | Cost | Delay |
|--------|------|------|-------|
| **yfinance** | Prices, options chains, earnings, history | Free | Real-time |
| **Capitol Trades** | Congressional stock trades | Free | 1-2 days |
| **FINRA** | Dark pool / short volume | Free | T+1 |
| **Yahoo Finance RSS** | News headlines | Free | Real-time |
| **Claude Sonnet** | AI analysis & recommendations | ~$3/MTok in / $15/MTok out | — |

## Testing

```bash
# Full suite: 286 tests in ~3.5s
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/ -v --ignore=tests/test_e2e.py

# E2E only (every command through the full stack)
python -m pytest tests/test_e2e.py -v

# Single test file
python -m pytest tests/test_math_utils.py -v
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI | Claude Sonnet via Anthropic API |
| Interface | Telegram Bot API (webhook) |
| Compute | AWS Lambda (Docker, ARM64/Graviton) |
| API | AWS API Gateway (HTTP API) |
| Database | DynamoDB (5 tables) |
| Storage | S3 (dashboard + historical data) |
| Scheduling | EventBridge (8 scanner schedules) |
| Queue | SQS (alert delivery) |
| IaC | Terraform |
| CI/CD | Docker build → ECR push → Lambda update |

## License

MIT
