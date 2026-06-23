# 📊 Cahier des charges — Bot d'analyse multi-marchés (actions · matières premières · devises · crypto)

> Document de référence du projet. Version 1.0 — 2026-06-23.
> Statut : **spécification** (avant développement). Tout choix marqué `[DÉFAUT]` est une
> décision prise par défaut, modifiable ; les points marqués `[À ARBITRER]` attendent ta validation.

---

## 1. Vision en une phrase

Un **bot Telegram gratuit et open source** qui surveille en continu les marchés (actions,
matières premières, devises, crypto) à partir de **plusieurs sources de données gratuites**,
calcule des indicateurs et détecte des configurations (patterns), suit **ton portefeuille**,
et t'envoie des **signaux clairs « acheter / vendre / conserver »** — simples, lisibles, jamais
surchargés, avec un bon ratio risque/rendement.

---

## 2. Nom du projet `[À ARBITRER]`

Critères : descriptif, facile à retenir, emoji dans le titre. Propositions :

| Nom | Slug GitHub | Idée |
|-----|-------------|------|
| 📊 **MarketPulse** | `marketpulse` | « le pouls du marché » — court, mémorisable |
| 📈 **TradeSignal** | `tradesignal` | centré sur le signal acheter/vendre |
| 🦉 **OwlTrader** | `owltrader` | la chouette qui veille (sagesse, vigilance) |
| 🧭 **BoursePilote** | `bourse-pilote` | « ton copilote de marché » (français) |

→ **À choisir ensemble avant le push GitHub.** Défaut proposé : **📊 MarketPulse**.

---

## 3. Objectifs & non-objectifs

### 3.1 Objectifs (ce que le produit FAIT)
- Récupérer **automatiquement** les dernières données de marché depuis plusieurs sources gratuites.
- **Toujours utiliser la donnée la plus récente** (sélection multi-sources par fraîcheur + repli).
- Calculer indicateurs techniques et détecter des **patterns** (chartistes + croisements).
- Agréger des **actualités** (flux RSS/API gratuits) et les faire **résumer/noter par une IA**.
- Suivre le **portefeuille de l'utilisateur** (« ce que j'ai ») et dire **quand vendre**.
- Émettre des **signaux** acheter/vendre/conserver avec **justification courte** et **niveau de risque**.
- Tout livrer dans un **bot Telegram** simple, en français, non surchargé.

### 3.2 Non-objectifs (ce que le produit NE fait PAS)
- ❌ **Pas de passage d'ordre réel** / pas de connexion à un broker (aucune exécution d'achat/vente).
- ❌ **Pas de conseil financier réglementé** — outil informatif/éducatif (voir §13 disclaimer).
- ❌ Pas de données « tick » temps réel niveau pro (les sources gratuites sont en léger différé).
- ❌ Pas de promesse de gains.

---

## 4. Utilisateurs & cas d'usage

- **Utilisateur principal** : particulier qui veut des signaux clairs sans lire des graphiques toute la journée.
- Parcours type :
  1. `/start` → le bot se présente, propose un menu.
  2. L'utilisateur ajoute des actifs à surveiller (`/watch AAPL`, `/watch BTC`, `/watch EURUSD`, `/watch GOLD`).
  3. Il déclare son portefeuille (`/portefeuille` → ajoute lignes : actif, quantité, prix d'achat).
  4. Le bot envoie des **alertes** (signal d'achat/vente, franchissement de seuil, actu importante).
  5. À la demande : `/analyse AAPL` → fiche synthétique (prix, tendance, indicateurs, actu, reco).

---

## 5. Périmètre fonctionnel détaillé

### 5.1 Classes d'actifs
| Classe | Exemples | Identifiant interne |
|--------|----------|---------------------|
| Actions | AAPL, MC.PA, TSLA | `STOCK:AAPL` |
| Indices | ^GSPC (S&P500), ^FCHI (CAC40) | `INDEX:^FCHI` |
| Matières premières | Or (GC=F), Pétrole (CL=F), Argent (SI=F) | `COMMO:GOLD` |
| Devises (FX) | EURUSD, USDJPY | `FX:EURUSD` |
| Crypto | BTC, ETH, SOL | `CRYPTO:BTC` |

### 5.2 Fonctions du bot Telegram (commandes)
| Commande | Rôle |
|----------|------|
| `/start`, `/aide` | Présentation + menu boutons |
| `/watch <actif>` / `/unwatch <actif>` | Gérer la liste de surveillance |
| `/liste` | Voir la watchlist avec mini-statut (▲▼ tendance) |
| `/analyse <actif>` | Fiche complète à la demande |
| `/portefeuille` | Voir / éditer ses positions |
| `/ajouter <actif> <qté> <prixAchat>` | Ajouter une position |
| `/perf` | Performance globale du portefeuille (P&L, %) |
| `/alertes` | Régler la sensibilité (peu / normal / beaucoup) |
| `/actu <actif>` | Dernières actus + résumé IA |
| `/reglages` | Langue, fréquence, fuseau horaire |

### 5.3 Types de messages poussés (proactifs)
- 🟢 **Signal d'achat** / 🔴 **Signal de vente** / 🟡 **Conserver**.
- ⚠️ **Alerte risque** (stop-loss conseillé franchi, volatilité forte).
- 📰 **Actu importante** (impact potentiel détecté par l'IA).
- 📅 **Résumé quotidien** (digest) optionnel — 1 message clair par jour.

### 5.4 Principe « anti-surcharge »
- Max **1 message de signal par actif et par fenêtre** (anti-spam / debounce, ex. 4 h).
- Un signal = **3 lignes max** : *Quoi · Pourquoi (1 raison clé) · Quel risque*.
- Détail uniquement sur demande (bouton « Voir détails »).

---

## 6. Architecture & flux de données

```
                    ┌──────────────────────────────────────────────┐
                    │                ORDONNANCEUR                   │
                    │  (APScheduler) — déclenche les tâches cycliques│
                    └───────────────┬──────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐          ┌─────────────────┐         ┌────────────────┐
│ COLLECTEUR    │          │ COLLECTEUR      │         │ COLLECTEUR     │
│ MARCHÉ        │          │ ACTUALITÉS      │         │ (extensible)   │
│ (prix/volumes)│          │ (RSS/API news)  │         │                │
└──────┬────────┘          └────────┬────────┘         └────────────────┘
       │ multi-sources + repli      │
       ▼                            ▼
┌─────────────────┐        ┌──────────────────┐
│  NORMALISATION  │        │  MODULE IA NEWS  │
│  + cache + choix │        │ (résumé + score  │
│  "plus récent"  │        │  de sentiment)   │
└──────┬──────────┘        └────────┬─────────┘
       ▼                            │
┌─────────────────┐                 │
│   STOCKAGE      │◄────────────────┘
│ (SQLite + Parquet)
└──────┬──────────┘
       ▼
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  INDICATEURS    │────▶│ MOTEUR DE SIGNAUX │────▶│   BOT TELEGRAM   │
│  + PATTERNS     │     │ (règles + ratios) │     │ (UX, messages)   │
└─────────────────┘     └──────────────────┘     └──────────────────┘
                                  ▲
                          ┌───────┴────────┐
                          │  PORTEFEUILLE  │
                          │  (positions)   │
                          └────────────────┘
```

### 6.1 Cycle de mise à jour (« toujours la dernière mise à jour »)
1. L'ordonnanceur réveille le **Collecteur marché** selon la fréquence configurée (voir §8).
2. Pour chaque actif, on interroge les sources **par ordre de priorité**, en parallèle.
3. Chaque réponse porte un **timestamp**. On **retient la valeur dont l'horodatage est le plus récent**
   (et on ignore les sources en erreur / périmées → mécanisme de **repli**).
4. La donnée est **normalisée** (même format OHLCV quelle que soit la source) puis mise en cache + stockée.
5. Indicateurs recalculés → moteur de signaux → notification si signal nouveau et non redondant.

---

## 7. Sources de données gratuites (multi-sources + repli)

> Principe : **abstraction `DataProvider`** commune ; chaque source l'implémente. Le `DataRouter`
> interroge les providers par priorité, compare les **timestamps**, garde le plus frais, bascule en
> repli si l'un échoue ou dépasse un quota. Aucune clé payante requise (clés gratuites optionnelles).

### 7.1 Prix / cours
| Source | Couverture | Clé ? | Notes |
|--------|-----------|-------|-------|
| **yfinance** (Yahoo) | Actions, indices, FX, matières (futures), crypto | Non | Source large par défaut `[DÉFAUT]` |
| **Stooq** | Actions, indices, FX, matières | Non | Bon repli, CSV simple |
| **CoinGecko** | Crypto | Non | Très complet crypto, sans clé |
| **Binance public API / ccxt** | Crypto | Non | Données fraîches crypto |
| **Frankfurter (BCE)** | Devises (FX) | Non | Taux de change officiels BCE |
| **exchangerate.host** | Devises | Non | Repli FX |
| **Alpha Vantage** | Actions, FX, crypto | Clé gratuite | Quota limité → source d'appoint |
| **Twelve Data / Finnhub** | Actions, FX, crypto | Clé gratuite | Sources d'appoint |

### 7.2 Actualités (flux gratuits)
| Source | Type | Clé ? |
|--------|------|-------|
| **Yahoo Finance RSS** (par ticker) | RSS | Non |
| **Investing.com / Reuters / CoinDesk RSS** | RSS | Non |
| **GDELT** | API actu mondiale | Non |
| **Finnhub news** | API | Clé gratuite |
| **NewsAPI** | API | Clé gratuite (quota) |

→ Toutes les sources sont **configurables/activables** dans `config.yaml`. Le produit fonctionne
**sans aucune clé** (yfinance + Stooq + CoinGecko + Frankfurter + RSS), les clés gratuites
n'ajoutent que de la robustesse.

---

## 8. Fréquence de mise à jour `[DÉFAUT]`

| Classe d'actif | Fréquence de rafraîchissement | Justification |
|----------------|------------------------------|---------------|
| Crypto | 1–5 min | Marché 24/7, volatil |
| FX / devises | 5–15 min | 24/5 |
| Actions / indices / matières | 15 min en séance, sinon horaire | Sources gratuites en différé léger |
| Actualités | 15–30 min | Suffisant pour le contexte |
| Résumé IA des news | par lots (batch) toutes les 30–60 min | Maîtrise du coût/charge |

Anti-abus : respect des quotas via **cache + back-off** ; jamais d'appel inutile si la donnée
en cache est encore fraîche.

---

## 9. Indicateurs & patterns

### 9.1 Indicateurs techniques
- Tendance : **SMA/EMA** (20/50/200), **MACD**, **ADX**.
- Momentum : **RSI**, **Stochastique**.
- Volatilité : **Bandes de Bollinger**, **ATR** (utile pour le stop-loss).
- Volume : **OBV**, volume moyen.

### 9.2 Patterns détectés
- **Croisements** : golden cross / death cross (SMA50 vs SMA200), croisement MACD.
- **Niveaux** : franchissement de support/résistance, plus-hauts/plus-bas (rupture).
- **Chartistes** (phase 2) : double top/bottom, tête-épaules, triangles, drapeaux.
- **Bougies** : marteau, étoile filante, engulfing (via lib `ta`/`pandas-ta`).

### 9.3 Du signal au message
Le **moteur de signaux** combine plusieurs critères pondérés → un **score** par actif :
- Score = f(tendance, momentum, rupture de niveau, volume, sentiment actu IA).
- Seuils → 🟢 Acheter / 🟡 Conserver / 🔴 Vendre.
- Chaque signal porte : **direction, force (0–100), raison principale, niveau de risque, stop conseillé (ATR)**.

---

## 10. Gestion du risque & ratios `[DÉFAUT — à valider]`

- **Stop-loss** suggéré = prix − k×ATR (k≈2) ; **take-profit** via ratio risque/rendement (R/R ≥ 1.5).
- Affichage du **ratio R/R** estimé sur chaque signal d'achat.
- Avertissement si volatilité (ATR%) anormalement élevée.
- **Aucune recommandation de taille de position** chiffrée par défaut (éviter le conseil financier),
  mais possibilité d'afficher un % de risque par position si l'utilisateur l'active.

---

## 11. Suivi du portefeuille (« ce que j'ai »)

- Stockage des positions : `actif, quantité, prix_achat, date`.
- Calcul en continu : **valeur courante, P&L (€ et %), variation jour**.
- Règles de **vente** déclenchées par : signal 🔴, franchissement stop-loss, objectif atteint,
  retournement de tendance, ou actu très négative (score IA).
- `/perf` → vue synthétique : top gagnants/perdants, P&L total.

---

## 12. Module IA pour les actualités

- **Rôle** : pour chaque lot d'actus pertinentes à un actif suivi → **résumé court** (2–3 phrases)
  + **score de sentiment** (-1 négatif … +1 positif) + **niveau d'impact** (faible/moyen/fort).
- **Architecture pluggable** (`NewsAnalyzer` interface) :
  - Mode **gratuit/local par défaut** `[DÉFAUT]` : analyse de sentiment par modèle léger
    (lexique financier / petit modèle) — fonctionne sans clé ni coût.
  - Mode **LLM optionnel** : si l'utilisateur fournit une clé API (ex. Claude/Anthropic), résumés
    de meilleure qualité. **Désactivé par défaut**, activable dans `config.yaml`.
- **Périodicité** : traitement par **batch** (voir §8) pour rester gratuit et léger.
- Le sentiment alimente le score du moteur de signaux (pondération faible mais utile).

---

## 13. Aspects légaux & éthiques

- Bandeau **disclaimer** au `/start` et en pied des fiches : *« Outil informatif et éducatif.
  Aucune recommandation d'investissement. Vous restez seul responsable de vos décisions. »*
- Respect des **conditions d'usage** des sources gratuites (rate limits, attribution si requise).
- Aucune donnée personnelle sensible ; les positions du portefeuille restent **locales** (voir §15).
- Licence **open source** : **MIT** `[DÉFAUT]` (simple, permissive).

---

## 14. Stack technique `[DÉFAUT]`

| Brique | Choix |
|--------|-------|
| Langage | Python 3.11+ |
| Bot | `python-telegram-bot` (async) |
| Données | `yfinance`, `requests`, `ccxt`, `pandas`, `numpy` |
| Indicateurs | `ta` / `pandas-ta` |
| Planification | `APScheduler` |
| Stockage | **SQLite** (positions, config, cache méta) + **Parquet** (séries OHLCV) |
| Actus | `feedparser` (RSS), `requests` |
| IA news | interface pluggable (local par défaut, LLM optionnel) |
| Visualisation | `matplotlib`/`plotly` (graphiques envoyés en image) |
| Config | `config.yaml` + `.env` (secrets) |
| Tests | `pytest` |
| Qualité | `ruff` (lint/format) |

---

## 15. Configuration & secrets

- `config.yaml` : actifs par défaut, fréquences, sources activées, seuils de signaux, langue.
- `.env` (jamais commité — déjà dans `.gitignore`) : `TELEGRAM_BOT_TOKEN`, clés API optionnelles.
- `config.example.yaml` et `.env.example` fournis pour démarrer en 2 minutes.

---

## 16. Structure de dépôt cible

```
src/
  collectors/      # providers marché + actus (un fichier par source)
  core/            # DataRouter (multi-source, choix du + récent), normalisation, cache
  storage/         # SQLite + Parquet
  indicators/      # calcul indicateurs + détection patterns
  signals/         # moteur de signaux, scoring, gestion du risque/ratios
  news/            # collecte + NewsAnalyzer (IA pluggable)
  portfolio/       # positions, P&L, règles de vente
  bot/             # handlers Telegram, mise en forme des messages, menus
  scheduler.py     # tâches cycliques
  config.py
tests/
config.example.yaml
.env.example
CAHIER_DES_CHARGES.md
README.md
LICENSE
```

---

## 17. Patrons de conception (design patterns) utilisés

| Pattern | Où | Pourquoi |
|---------|-----|---------|
| **Strategy** | `DataProvider`, `NewsAnalyzer`, règles de signaux | Brancher/débrancher des sources et algos sans toucher au cœur |
| **Adapter** | chaque source de données/actu | Uniformiser des API hétérogènes vers un format commun |
| **Chain of Responsibility / Fallback** | `DataRouter` multi-sources | Repli automatique + choix de la donnée la plus fraîche |
| **Observer / Pub-Sub** | moteur de signaux → bot | Émettre des notifications quand un signal apparaît |
| **Repository** | `storage/` | Isoler l'accès aux données (SQLite/Parquet) |
| **Factory** | création des providers depuis `config.yaml` | Activer les sources par configuration |
| **Facade** | service d'analyse appelé par le bot | Une API simple pour `/analyse` qui cache la complexité |

---

## 18. Plan de livraison (jalons)

- **M0 — Fondations** : structure, config, stockage, 1 source (yfinance), 1 commande `/analyse`.
- **M1 — Multi-sources + repli** : DataRouter, choix du plus récent, crypto/FX/matières.
- **M2 — Indicateurs & signaux** : indicateurs, scoring, messages clairs anti-surcharge.
- **M3 — Portefeuille** : positions, P&L, règles de vente, `/perf`.
- **M4 — Actus + IA** : collecte RSS, NewsAnalyzer local, intégration au score.
- **M5 — Finition** : alertes proactives, digest quotidien, graphiques, doc, tests.
- **M6 — Publication** : README soigné, LICENSE MIT, push GitHub, badges.

---

## 19. Critères d'acceptation (produit « fini »)

- ✅ Installable en < 5 min (`pip install -r requirements.txt`, token Telegram, `python -m src.bot`).
- ✅ Fonctionne **sans aucune clé payante**.
- ✅ Couvre actions + matières + devises + crypto.
- ✅ Donne des signaux acheter/vendre/conserver **clairs et justifiés**.
- ✅ Suit un portefeuille et alerte sur la vente.
- ✅ Messages **non surchargés** (règle des 3 lignes + détail sur demande).
- ✅ Multi-sources avec repli et **donnée la plus récente** garantie.
- ✅ Open source (MIT), documenté, sur GitHub avec emoji dans le titre.

---

## 20. Points à arbitrer avant de coder

1. **Nom + emoji** du projet (§2) — défaut : 📊 MarketPulse.
2. **Langue** des messages — défaut : français.
3. **IA news** : local gratuit seul, ou prévoir le branchement LLM optionnel dès le départ ?
4. **Actifs par défaut** dans la watchlist de démo.
5. **Licence** — défaut : MIT.
6. **Push GitHub** : compte/visibilité (public), et nom final du dépôt.
