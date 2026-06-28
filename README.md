<div align="center">

# 🦉 OwlTrader

**A free, open-source Telegram bot that watches the markets — stocks, crypto, forex, commodities — and tells you when to buy, sell or hold. Clearly, without the noise.**

[English](README.md) · [Français](README.fr.md)

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![CI](https://github.com/mkl159/owltrader/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-33%20passing-brightgreen)
![Paper trading](https://img.shields.io/badge/trading-100%25%20fictional-orange)

</div>

> ⚠️ **Educational tool. Not financial advice. No real orders are ever placed.** OwlTrader trades with *fictional* money so you can learn and experiment with zero risk.

---

## 📸 Glimpse

| Live chart (`/graph`) | Autonomous backtest (`/simuler`) |
|---|---|
| ![Price chart](docs/images/chart-aapl.png) | ![Equity curve](docs/images/equity-curve.png) |

A real 5-year simulation of the autonomous mode: **€1000 → €2211 (+121%)**, fees included.

---

## ✨ What it does

- 📡 **Real-time-ish market data** from **multiple free sources** (Yahoo Finance + CoinGecko + Stooq) — always keeps the **freshest** quote, with automatic fallback.
- 📐 **Indicators & patterns** — RSI, MACD, moving averages, Bollinger, ATR, golden/death cross…
- 🤖 **Autonomous paper-trading** — give it €1000 of fictional money and it buys/sells on its own, brokerage fees included, logging every move.
- 🧪 **Backtesting** with pro metrics — Sharpe, Sortino, Calmar, CAGR, max drawdown, profit factor.
- 💡 **Buy ideas** — scans the market and ranks the best opportunities.
- 📊 **One-tap market briefing** (`/apercu`) — trend, regime, geopolitical risk, seasonality and top picks, all in one view.
- 📰 **News + sentiment** — aggregates free RSS feeds and scores them.
- 🔔 **Price alerts** and **sell alerts** on your holdings.
- 🌍 **Bilingual** — English & French, switch anytime with `/langue`.
- 🔒 **Password-protected** access (first connection) — configurable.
- 🔌 **Broker connectors** — Alpaca (paper) + 100+ crypto exchanges via CCXT (Binance, Kraken…).
- 💾 **Config export/import** and local backups, all from Telegram.
- 🛡️ Runs **24/7** (systemd), with daily backups.

## 📖 Documentation

- 🛠️ [Installation & configuration tutorial](docs/INSTALL.md)
- 🤖 [Full command reference (EN/FR)](docs/COMMANDS.md)

---

## 🧠 The strategy (and why it's trustworthy)

OwlTrader is **not** a black box stuffed with 50 magic variables. Every rule is **battle-tested**, and anything that doesn't survive rigorous out-of-sample testing is **thrown away**.

It stands on the shoulders of legendary traders:

| Rule | Inspired by |
|------|-------------|
| 📈 Trend-following ensemble | Jesse Livermore / Ed Seykota |
| 🛡️ Market regime filter (only buy when S&P > its 200-day average) | Paul Tudor Jones |
| ⚖️ Volatility-based position sizing | Ray Dalio |
| 🎯 Relative + absolute momentum ranking | Jegadeesh-Titman / Gary Antonacci |
| ✂️ Stop-loss, let winners run | Ed Seykota |

**Validated across ~98 years** of S&P 500 history (since 1927, through every major crash) and on 3/5/10-year windows. Typical risk-adjusted profile: **CAGR ~15–20%, Sharpe ~0.55–0.62** in fictional backtests.

> The real edge isn't a secret formula — it's the **discipline** of testing everything and keeping only what is robust.

---

## 🚀 Quick start

```bash
git clone https://github.com/mkl159/owltrader.git
cd owltrader
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Try it instantly, no Telegram needed:
python -m src.cli analyse STOCK:AAPL

# Run the bot:
cp .env.example .env        # add your TELEGRAM_BOT_TOKEN (from @BotFather)
python -m src.main
```

### Keep it running 24/7

```bash
sudo bash deploy/install-systemd.sh    # auto-start at boot, auto-restart on crash
```

---

## 🤖 Telegram commands

| | |
|---|---|
| 📊 `/apercu` | Full market briefing (everything at a glance) |
| 🤖 `/auto 1000` | Start autonomous mode with €1000 fictional |
| 🧪 `/simuler` | Backtest + pro metrics |
| 💡 `/idees` | Best buy opportunities |
| 📈 `/analyse AAPL` · `/graph AAPL` | Asset analysis & chart |
| 🌍 `/marche` · `/risque` · `/saison` | Market trend, risk climate, seasonality |
| 🔔 `/alerte AAPL 200` | Price alert |
| 🌐 `/univers` · `/sources` | Customize universe / see data sources |
| 🏆 `/maitres` | The legendary traders behind the bot |

Everything is also reachable through tap-friendly menus (`/menu`).

---

## 🆓 100% free

Works with **no paid keys** (yfinance, CoinGecko, Stooq, free RSS). Optional free keys (Alpaca paper trading, etc.) only add robustness.

## 📜 License

[MIT](LICENSE) — free to use, modify and share.

---

<div align="center">
<sub>Built with discipline, not hype. ⚠️ Educational only — you are responsible for your own decisions.</sub>
</div>
