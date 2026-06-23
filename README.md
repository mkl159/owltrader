# 🦉 OwlTrader

**Bot Telegram gratuit et open source qui surveille les marchés (actions · matières premières · devises · crypto), détecte les signaux et te dit quand acheter, vendre ou conserver — clairement, sans te noyer d'infos.**

> ⚠️ Outil **informatif et éducatif**. Aucune recommandation d'investissement réglementée.
> Aucune exécution d'ordre réel. Tu restes seul responsable de tes décisions.

---

## ✨ Ce que fait OwlTrader

- 📡 **Données de marché** — récupère, nettoie et stocke cours, volumes et séries financières depuis **plusieurs sources gratuites**, en gardant **toujours la donnée la plus récente** (multi-sources + repli automatique).
- 📐 **Indicateurs & patterns** — moyennes mobiles, RSI, MACD, Bollinger, ATR… et détection de configurations (croisements, ruptures de niveaux, figures chartistes).
- 🧪 **Backtest** — teste des stratégies sur données historiques avec des métriques de performance.
- 📰 **Actualités + IA** — agrège des flux d'actu gratuits et les fait **résumer/noter** périodiquement par une IA.
- 💼 **Portefeuille** — suit *ce que tu as* (P&L) et t'alerte **quand vendre**.
- 🤖 **Bot Telegram** — messages simples, en français, jamais surchargés (3 lignes max + détail à la demande).

## 🗺️ Statut

MVP **fonctionnel** : suivi multi-actifs en quasi temps réel (actions, indices, matières premières,
devises, crypto) via sources gratuites (**Yahoo Finance** + **Stooq** en repli, sélection de la
donnée la plus fraîche), indicateurs, signaux et bot Telegram.
Le **[cahier des charges complet](CAHIER_DES_CHARGES.md)** décrit la suite (actus + IA, backtest, patterns avancés).

## 🚀 Démarrage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Tester tout de suite, sans Telegram

```bash
python -m src.cli prix AAPL
python -m src.cli analyse STOCK:MSFT
python -m src.cli prix CRYPTO:BTC      # crypto
python -m src.cli prix FX:EURUSD       # devise
python -m src.cli prix COMMO:GOLD      # matière première
```

### Lancer le bot Telegram

```bash
cp .env.example .env        # puis renseigner TELEGRAM_BOT_TOKEN (via @BotFather)
python -m src.main
```

Commandes du bot :
- 💡 `/idees` (filtrable : `/idees crypto`) · 🚀 `/movers` — scan du marché & pistes d'achat
- 📊 `/prix` · `/analyse` (avec sentiment des actus) · 📈 `/graph` · 🧪 `/backtest` · 📰 `/actu`
- 👁️ `/watch` · `/unwatch` · `/liste`
- 💼 `/ajouter` · `/portefeuille` · `/perf`
- ⚙️ `/reglages` · `/digest` · `/menu` · `/aide`

**Alertes automatiques** : signaux acheter/vendre sur la watchlist, **alertes de vente sur le
portefeuille** (signal de vente ou perte importante), et **résumé quotidien**.
Tout est aussi pilotable **aux boutons** via `/menu`.

## 🆓 100 % gratuit

OwlTrader fonctionne **sans aucune clé payante** (yfinance, Stooq, CoinGecko, Frankfurter, flux RSS…).
Des clés gratuites optionnelles ne servent qu'à renforcer la robustesse.

## 📜 Licence

[MIT](LICENSE) — libre d'utilisation, de modification et de partage.
