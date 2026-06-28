<div align="center">

# 🦉 OwlTrader

**Un bot Telegram gratuit et open source qui surveille les marchés — actions, crypto, devises, matières premières — et te dit quand acheter, vendre ou conserver. Clairement, sans le bruit.**

[English](README.md) · [Français](README.fr.md)

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/Licence-MIT-green)
![CI](https://github.com/mkl159/owltrader/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-33%20passing-brightgreen)
![Paper trading](https://img.shields.io/badge/trading-100%25%20fictif-orange)

</div>

> ⚠️ **Outil éducatif. Aucun conseil financier. Aucun ordre réel n'est jamais passé.** OwlTrader trade avec de l'argent *fictif* : tu apprends et tu expérimentes sans aucun risque.

---

## 📸 Aperçu

| Graphique en direct (`/graph`) | Backtest autonome (`/simuler`) |
|---|---|
| ![Graphique](docs/images/chart-aapl.png) | ![Courbe de capital](docs/images/equity-curve.png) |

Une vraie simulation 5 ans du mode autonome : **1000 € → 2211 € (+121 %)**, frais inclus.

---

## ✨ Ce qu'il fait

- 📡 **Données de marché quasi temps réel** depuis **plusieurs sources gratuites** (Yahoo Finance + CoinGecko + Stooq) — garde toujours la cotation **la plus fraîche**, avec repli automatique.
- 📐 **Indicateurs & patterns** — RSI, MACD, moyennes mobiles, Bollinger, ATR, golden/death cross…
- 🤖 **Paper-trading autonome** — confie-lui 1000 € fictifs : il achète/vend tout seul, frais de courtage inclus, en loguant chaque action.
- 🧪 **Backtest** avec métriques pro — Sharpe, Sortino, Calmar, CAGR, drawdown max, profit factor.
- 💡 **Idées d'achat** — scanne le marché et classe les meilleures opportunités.
- 📊 **Briefing marché en un tap** (`/apercu`) — tendance, régime, risque géopolitique, saisonnalité et top opportunités, en une vue.
- 📰 **Actus + sentiment** — agrège des flux RSS gratuits et les note.
- 🔔 **Alertes de prix** et **alertes de vente** sur tes positions.
- 🌍 **Bilingue** — français & anglais, bascule à tout moment avec `/langue`.
- 🔒 **Accès protégé par mot de passe** (1re connexion) — configurable.
- 🔌 **Connecteurs broker** — Alpaca (paper) + 100+ échanges crypto via CCXT (Binance, Kraken…).
- 💾 **Export/import de config** et sauvegardes locales, depuis Telegram.
- 🛡️ Tourne en **24/7** (systemd), avec sauvegardes quotidiennes.

## 📖 Documentation

- 🛠️ [Tutoriel d'installation & configuration](docs/INSTALL.md)
- 🤖 [Référence complète des commandes (EN/FR)](docs/COMMANDS.md)

---

## 🧠 La stratégie (et pourquoi lui faire confiance)

OwlTrader n'est **pas** une boîte noire bourrée de 50 variables magiques. Chaque règle est **éprouvée**, et tout ce qui ne survit pas à un test rigoureux hors-échantillon est **jeté**.

Il s'appuie sur les épaules de traders légendaires :

| Règle | Inspirée par |
|-------|--------------|
| 📈 Ensemble suiveur de tendance | Jesse Livermore / Ed Seykota |
| 🛡️ Filtre de régime (n'acheter que si le S&P > sa moyenne 200 jours) | Paul Tudor Jones |
| ⚖️ Dimensionnement par volatilité | Ray Dalio |
| 🎯 Classement par momentum relatif + absolu | Jegadeesh-Titman / Gary Antonacci |
| ✂️ Stop-loss, laisser courir les gagnants | Ed Seykota |

**Validé sur ~98 ans** d'historique du S&P 500 (depuis 1927, à travers tous les grands krachs) et sur des fenêtres de 3/5/10 ans. Profil risque-ajusté typique : **CAGR ~15–20 %, Sharpe ~0,55–0,62** en backtest fictif.

> Le vrai avantage n'est pas une formule secrète — c'est la **discipline** de tout tester et de ne garder que ce qui est robuste.

---

## 🚀 Démarrage rapide

```bash
git clone https://github.com/mkl159/owltrader.git
cd owltrader
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Essai immédiat, sans Telegram :
python -m src.cli analyse STOCK:AAPL

# Lancer le bot :
cp .env.example .env        # ajoute ton TELEGRAM_BOT_TOKEN (via @BotFather)
python -m src.main
```

### Le faire tourner en 24/7

```bash
sudo bash deploy/install-systemd.sh    # démarre au boot, redémarre seul en cas de crash
```

---

## 🤖 Commandes Telegram

| | |
|---|---|
| 📊 `/apercu` | Briefing complet du marché (tout en un coup d'œil) |
| 🤖 `/auto 1000` | Démarrer le mode autonome avec 1000 € fictifs |
| 🧪 `/simuler` | Backtest + métriques pro |
| 💡 `/idees` | Meilleures opportunités d'achat |
| 📈 `/analyse AAPL` · `/graph AAPL` | Analyse & graphique d'un actif |
| 🌍 `/marche` · `/risque` · `/saison` | Tendance marché, climat de risque, saisonnalité |
| 🔔 `/alerte AAPL 200` | Alerte de prix |
| 🌐 `/univers` · `/sources` | Personnaliser l'univers / voir les sources |
| 🏆 `/maitres` | Les traders légendaires derrière le bot |

Tout est aussi accessible via des menus à boutons (`/menu`).

---

## 🆓 100 % gratuit

Fonctionne **sans aucune clé payante** (yfinance, CoinGecko, Stooq, flux RSS). Des clés gratuites optionnelles (Alpaca paper-trading…) ne font qu'ajouter de la robustesse.

## 📜 Licence

[MIT](LICENSE) — libre d'utilisation, de modification et de partage.

---

<div align="center">
<sub>Construit avec discipline, pas avec du hype. ⚠️ Éducatif uniquement — tu restes responsable de tes décisions.</sub>
</div>
