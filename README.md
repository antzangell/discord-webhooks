# Discord Webhooks

Automated Discord webhook that posts Path of Exile item prices from [poe.ninja](https://poe.ninja) every hour.

## Tracked Items

- Divine Orb
- Mirror of Kalandra
- Mirror Shard
- Hinekora's Lock
- Mageblood
- Headhunter

## Features

- Hourly price updates via GitHub Actions
- 7-day price chart for Divine Orb
- `@everyone` alert when Divine Orbs hit 350+ chaos

## Setup

1. Fork this repo
2. Add repository secrets:
   - `DISCORD_WEBHOOK_URL` — your Discord webhook URL
3. Add repository variable (optional):
   - `LEAGUE` — league name (defaults to `Mirage`)
4. Enable GitHub Actions

## Running Locally

```bash
pip install -r scripts/requirements.txt
DISCORD_WEBHOOK_URL=your_url python scripts/price-webhook.py
# or dry run:
python scripts/price-webhook.py --local
```

## Contributing

PRs welcome! Open an issue or submit a pull request.

## License

MIT
