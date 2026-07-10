# 🤖 Commands / Commandes

The bot is bilingual — switch with `/langue` (FR) or `/language` (EN).
Le bot est bilingue — changez avec `/langue` (FR) ou `/language` (EN).

| Command | 🇬🇧 English | 🇫🇷 Français |
|---------|------------|-------------|
| `/start` | Start + main menu | Démarrer + menu principal |
| `/menu` | Open the button menu | Ouvrir le menu à boutons |
| `/apercu` | Full market briefing (all-in-one) | Briefing complet du marché (tout en un) |
| **🎛️ Cockpit & emergency / Cockpit & urgence** | | |
| `/cockpit` `/desk` | Live dashboard: equity + sparkline, position cards with P&L bars, AI plan, in-place 🔄 refresh | Tableau de bord vivant : équity + sparkline, cartes de positions avec barres de P&L, plan IA, 🔄 actualisation sur place |
| `/stopachats` `/pause` | Handbrake: stop ALL buying (robot + AI); sells & stop-loss stay active | Frein à main : suspend TOUS les achats (robot + IA) ; ventes et stop-loss actifs |
| `/reprendre` `/resume` | Resume trading | Reprendre le trading |
| `/toutvendre` `/panic` | Liquidate ALL positions (internal + Alpaca), with confirmation, then pause | Liquider TOUTES les positions (interne + Alpaca), avec confirmation, puis pause |
| `/paractif` `/performance` | Realized P&L per asset (who earns, who costs) | P&L réalisé par actif (qui rapporte, qui coûte) |
| `/jours` `/daily` | Day-by-day gains/losses | Gains/pertes jour par jour |
| **🤖 Autonomous mode / Mode autonome** | | |
| `/auto 1000` | Start internal autonomous mode with €1000 fictional | Démarrer le mode autonome interne avec 1000 € fictifs |
| `/bilan` | Account status + equity chart | Bilan du compte + graphique |
| `/simuler` | Backtest + pro metrics | Backtest + métriques pro |
| `/agressivite` | Conservative / normal / aggressive profile | Profil prudent / normal / agressif |
| `/autotune` | Re-tune the strategy on history | Ré-régler la stratégie sur l'historique |
| `/reset` | Reset the fictional account | Réinitialiser le compte fictif |
| `/stopauto` | Pause the internal autonomous mode | Mettre en pause le mode autonome interne |
| **🦙 Alpaca (autonomous on a real API)** | | |
| `/alpaca` | Panel: enable auto-trading on your Alpaca account (paper/live), test connection | Panneau : activer le trading auto sur ton compte Alpaca (paper/réel), tester la connexion |
| `/bilanalpaca` | Alpaca account report: value, gain/loss, positions + equity chart | Bilan Alpaca : valeur, gain/perte, positions + courbe d'équity |
| | The bot scans the **entire S&P 500** (weekly-refreshed list) and buys the strongest (momentum ranking) — decisions on closed candles only, never while the market is closed | Le bot scanne **tout le S&P 500** (liste rafraîchie chaque semaine) et achète les plus fortes (classement momentum) — décisions sur bougies clôturées, jamais marché fermé |
| **🧠 AI advisor / Conseiller IA (optional, OpenAI)** | | |
| `/ia` | Panel: modes (autonomous ± AI, simulation ± AI), "ask now" button (unlimited), active 24h plan | Panneau : modes (autonome ± IA, simulation ± IA), bouton « demander maintenant » (illimité), plan 24 h actif |
| | The AI issues immediate orders **and a 24h plan** (bias, focus, avoid) that steers the robot; its buys are protected 7 days | L'IA émet des ordres immédiats **et un plan 24 h** (biais, priorités, interdits) qui pilote le robot ; ses achats sont protégés 7 jours |
| **📊 Market & ideas / Marché & idées** | | |
| `/idees` | Best buy opportunities (`/idees crypto`) | Meilleures opportunités (`/idees crypto`) |
| `/equipe AAPL` | The strategy team's vote | Le vote de l'équipe de stratégies |
| `/maitres` | The legendary traders behind the bot | Les traders légendaires derrière le bot |
| `/tendance AAPL` | Aggregated trend (multi-source) | Tendance agrégée (multi-sources) |
| `/marche` | Overall market trend + regime | Tendance générale du marché + régime |
| `/risque` | Macro / geopolitical risk climate (VIX) | Climat macro / géopolitique (VIX) |
| `/saison` | Seasonality + market holidays | Saisonnalité + jours fériés |
| `/movers` | Biggest movers of the day | Plus fortes hausses/baisses du jour |
| **📈 Research an asset / Analyser un actif** | | |
| `/prix AAPL` | Latest price | Dernier cours |
| `/analyse AAPL` | Full card + signal | Fiche complète + signal |
| `/graph AAPL` | Pro dark chart: price, SMAs, volume, RSI | Graphique sombre pro : cours, SMA, volume, RSI |
| `/backtest AAPL` | Backtest a strategy on one asset | Tester une stratégie sur un actif |
| `/actu AAPL` | News + sentiment | Actualités + sentiment |
| **🔔 Alerts & universe / Alertes & univers** | | |
| `/alerte AAPL 200` | Price alert | Alerte de prix |
| `/alertes` | View / delete my alerts | Voir / supprimer mes alertes |
| `/univers` | View / edit traded assets | Voir / modifier les actifs tradés |
| `/sources` | Active data sources | Sources de données actives |
| **👁️ Watchlist** | | |
| `/watch AAPL` · `/unwatch AAPL` · `/liste` | Add / remove / list watched assets | Ajouter / retirer / lister la watchlist |
| **💼 Portfolio / Portefeuille** | | |
| `/ajouter AAPL 10 180` | Add a position (qty, buy price) | Ajouter une position (qté, prix d'achat) |
| `/portefeuille` · `/perf` | Holdings · performance | Positions · performance |
| **🔌 Brokers & security / Brokers & sécurité** | | |
| `/brokers` | Brokers hub: Alpaca, Trade Republic, crypto exchanges | Hub brokers : Alpaca, Trade Republic, échanges crypto |
| `/traderepublic` | Read your real Trade Republic account (cash, positions) — read-only | Lire ton compte Trade Republic réel (cash, positions) — lecture seule |
| `/broker` | Connect a crypto exchange (Binance, Kraken… via CCXT) | Connecter un échange crypto (Binance, Kraken… via CCXT) |
| `/config` · `/set` · `/del` | Manage API keys — encrypted in DB, key messages deleted from chat | Gérer les clés API — chiffrées en base, messages de clés supprimés du chat |
| `/securite` | Security dashboard: authorized users, audit log, intrusion attempts | Tableau de bord sécurité : accès autorisés, journal d'audit, tentatives d'intrusion |
| `/deconnexion` | Log out (password asked again) | Se déconnecter (mot de passe redemandé) |
| `/export` · `/sauvegarde` | Export config · backup the database | Exporter la config · sauvegarder la base |
| **⚙️ Settings / Réglages** | | |
| `/reglages` | Settings (alerts, digest, language) | Réglages (alertes, digest, langue) |
| `/langue` `/language` | Switch language FR ⇄ EN | Changer de langue FR ⇄ EN |
| `/digest` | Today's summary | Résumé du jour |
| `/aide` `/help` | Help | Aide |

> ⚠️ Educational tool — not investment advice. / Outil éducatif — aucun conseil en investissement.
