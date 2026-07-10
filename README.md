<div align="center">

# 🦉 OwlTrader

**A full trading desk inside Telegram — free and open source. It scans the entire S&P 500, trades autonomously (paper or via Alpaca), and an optional AI advisor steers the robot with a daily trading plan.**

[English](README.md) · [Français](README.fr.md)

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![CI](https://github.com/mkl159/owltrader/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-60%20passing-brightgreen)
![Paper trading](https://img.shields.io/badge/default-paper%20trading-orange)

</div>

> ⚠️ **Educational tool. Not financial advice.** By default OwlTrader trades **fictional** money (internal simulator or a free Alpaca *paper* account). A live mode exists through Alpaca — enable it knowingly, at your own risk.

---

## 📸 Preview

| Asset analysis (`/graph`) | Equity curve (`/bilan`, `/simuler`) |
|---|---|
| ![Chart](docs/images/chart-aapl.png) | ![Equity curve](docs/images/equity-curve.png) |

**Pro dark-theme charts** (TradingView-style): price + change in the title, gradient fill, volume, RSI, and a drawdown subplot (how the risk *feels*). 5-year simulation of the autonomous mode at the time of writing: **€1000 → ~€1420 (+42%)**, brokerage fees included — windows shift, run `/simuler` for today's number.

---

## ✨ What it does

### 🤖 Autonomous trading
- **Scans the ENTIRE S&P 500** (≈503 stocks, list **auto-refreshed weekly**) plus your cryptos, and buys the strongest ones (momentum ranking).
- **Internal paper-trading** (fictional money, fees included) **or real execution through [Alpaca](https://alpaca.markets)** (free *paper* account first, optional live mode) — the bot places its own orders, every hour.
- **Pro-grade anti-whipsaw** (freqtrade practices): decisions only on **closed candles**, no orders while the asset's market is **closed** (US 9:30–16:00 NY, Europe 9:00–17:30 Paris, crypto 24/7).
- Risk: automatic stop-loss, regime filter (S&P > 200-day MA), volatility sizing, absolute momentum.

### 🧠 AI advisor (optional, OpenAI)
- Aggregates **everything** (positions, indicators, cross-asset macro regime, RSS news, costs) and gives decisive advice.
- **AI ↔ robot osmosis**: the AI is the *desk chief* — it issues a **24-hour trading plan** (aggressive/defensive bias, assets to prioritize/avoid) that the autonomous cycle applies every hour.
- Its buys are **protected for 7 days** from the autonomous cycle (only the AI may sell them) — no more sterile back-and-forth between the two brains.
- **Global hunting**: through the news, the AI can discover and buy stocks **outside** your list.
- Controlled budget: 1 automatic consultation/day (mid US session, never when markets are closed); the manual button is unlimited.

### 🎛️ Cockpit & emergency (UX inspired by Maestro/Trojan and freqtrade)
- `/cockpit` — **live dashboard**: equity + sparkline `▁▂▄▆█`, position cards with P&L bars `🟩🟩🟩⬜⬜`, active AI plan, and a **🔄 Refresh** button that updates the card *in place*.
- `/pause` — **handbrake**: no more buys (robot + AI), sells and stop-losses stay active. `/resume` to restart.
- `/panic` — full liquidation with confirmation.
- `/performance` (realized P&L per asset) · `/daily` (day-by-day P&L).

### 📊 Analysis & market
- **Free multi-source data** (Yahoo Finance, CoinGecko, Stooq) — always keeps the freshest quote, automatic fallback.
- Indicators: RSI, MACD, moving averages, Bollinger, ATR, ADX, golden/death cross…
- `/apercu` — full briefing: trend, regime, **cross-asset macro** (RSP/SPY, HYG/LQD…), geopolitical risk (VIX), seasonality, top opportunities.
- Backtests with pro metrics: Sharpe, Sortino, Calmar, CAGR, max drawdown, profit factor.
- Aggregated RSS news + sentiment, price alerts.

### 🔌 Brokers & security
- `/brokers` hub: **Alpaca** (autonomous, paper/live), **Trade Republic** (read-only: cash, positions), **100+ crypto exchanges** via CCXT.
- **Encrypted secrets** (AES/Fernet) in the database, messages containing keys are **deleted from the chat**, **password-protected** access, audit log + intrusion detection (`/securite`).
- Bilingual 🇫🇷/🇬🇧 (`/language`), runs 24/7 (systemd), daily backups.

## 📖 Documentation

- 🛠️ [Install & configuration tutorial](docs/INSTALL.md)
- 🤖 [Full command reference (EN/FR)](docs/COMMANDS.md)

---

## 🧠 The strategy (and why trust it)

OwlTrader is **not** a black box stuffed with 50 magic variables. Every rule is **battle-tested**, and anything that doesn't survive rigorous out-of-sample testing (5 **and** 10 years) is **discarded** — circuit breakers, trailing stops and seasonal filters were tested and rejected for exactly that reason.

It stands on the shoulders of legendary traders:

| Rule | Inspired by |
|------|-------------|
| 📈 Trend-following ensemble | Jesse Livermore / Ed Seykota |
| 🛡️ Regime filter (only buy when S&P > its 200-day MA) | Paul Tudor Jones |
| ⚖️ Volatility-based position sizing | Ray Dalio |
| 🎯 Relative + absolute momentum ranking | Jegadeesh-Titman / Gary Antonacci |
| ✂️ Stop-losses, let winners run | Ed Seykota |
| 🕯️ Decisions on closed candles, never with markets closed | freqtrade (`process_only_new_candles`) |

**Validated over ~98 years** of S&P 500 history (since 1927, through every major crash) and on 3/5/10-year windows.

> The real edge isn't a secret formula — it's the **discipline** of testing everything and keeping only what's robust.

---

## 🚀 Quick start

```bash
git clone https://github.com/mkl159/owltrader.git
cd owltrader
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Instant try-out, no Telegram needed:
python -m src.cli analyse STOCK:AAPL

# Run the bot:
cp .env.example .env        # add your TELEGRAM_BOT_TOKEN (from @BotFather)
python -m src.main
```

Then, in Telegram: `/start` → the menu guides you. For autonomous trading on Alpaca and the AI advisor, follow the [tutorial](docs/INSTALL.md).

### Run it 24/7

```bash
sudo bash deploy/install-systemd.sh    # starts at boot, restarts itself on crash
```

---

## 🤖 Telegram commands (essentials)

| | |
|---|---|
| 🎛️ `/cockpit` | Live dashboard (positions, P&L, AI plan, in-place refresh) |
| 📊 `/apercu` | Full market briefing (everything at a glance) |
| 🤖 `/auto 1000` | Internal autonomous mode with €1000 fictional |
| 🦙 `/alpaca` | Autonomous trading on your Alpaca account (paper/live) + chart report |
| 🧠 `/ia` | AI advisor: advice, executed orders, 24h plan for the robot |
| 🧪 `/simuler` | Backtest + pro metrics |
| 🛑 `/pause` · `/panic` | Handbrake · full liquidation (confirmed) |
| 📈 `/analyse AAPL` · `/graph AAPL` | Pro analysis & chart of an asset |
| 📊 `/performance` · `/daily` | P&L per asset · P&L per day |
| 🔌 `/brokers` | Brokers hub: Alpaca, Trade Republic, crypto exchanges |
| 🛡️ `/securite` | Security dashboard + audit log |

[→ Full command reference](docs/COMMANDS.md) — everything is also reachable through button menus (`/menu`).

---

## 🆓 100% free

Works **without any paid key** (yfinance, CoinGecko, Stooq, RSS feeds). Optional keys are free (Alpaca paper) or your own (OpenAI for the AI advisor — ~1 request/day).

## 🙏 Sources & inspirations

- **Data**: [Yahoo Finance](https://finance.yahoo.com) (via yfinance), [CoinGecko](https://www.coingecko.com), [Stooq](https://stooq.com), public RSS feeds, [S&P 500 constituents](https://github.com/datasets/s-and-p-500-companies).
- **Execution**: [Alpaca](https://alpaca.markets) (paper/live API), [CCXT](https://github.com/ccxt/ccxt), [pytr](https://github.com/pytr-org/pytr) (Trade Republic, read-only).
- **Anti-whipsaw practices & emergency commands**: [freqtrade](https://www.freqtrade.io) (`process_only_new_candles`, protections, `/stopentry`, `/forceexit`, `/performance`, `/daily`).
- **Position-card UX**: the [Maestro](https://www.maestrobots.com/) / Trojan Telegram bots (live panels, visual P&L).
- **Cross-asset macro regime**: inspired by [agentic-trading-desk](https://github.com/Oft3r/agentic-trading-desk).

## 📜 License

[MIT](LICENSE) — free to use, modify and share.

---

<div align="center">
<sub>Built with discipline, not hype. ⚠️ Educational only — you remain responsible for your decisions.</sub>
</div>
