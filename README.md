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

Projet en cours de construction. Le **[cahier des charges complet](CAHIER_DES_CHARGES.md)** décrit la
vision, l'architecture, les sources de données, les patterns et le plan de livraison.

## 🚀 Démarrage (à venir)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Renseigner TELEGRAM_BOT_TOKEN dans .env, puis lancer le bot.
```

## 🆓 100 % gratuit

OwlTrader fonctionne **sans aucune clé payante** (yfinance, Stooq, CoinGecko, Frankfurter, flux RSS…).
Des clés gratuites optionnelles ne servent qu'à renforcer la robustesse.

## 📜 Licence

[MIT](LICENSE) — libre d'utilisation, de modification et de partage.
