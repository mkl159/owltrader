# 🛠️ Installation & Configuration

[English](#english) · [Français](#français)

---

## English

### 1. Prerequisites
- Python 3.11+
- A Telegram account

### 2. Get the code
```bash
git clone https://github.com/mkl159/owltrader.git
cd owltrader
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create your Telegram bot (30 seconds)
1. In Telegram, open a chat with **@BotFather**.
2. Send `/newbot`, choose a name and a username ending in `bot`.
3. BotFather replies with a **token** like `123456789:AAH...`.

### 4. Configuration file (your token)
Copy the example and fill in your token:
```bash
cp .env.example .env
```
Open `.env` and set:
```ini
TELEGRAM_BOT_TOKEN=123456789:AAH...your-token...
```
> 🔒 `.env` holds your secrets and is **never** committed to Git (it's git-ignored). Optional free API keys (Alpaca paper-trading, etc.) go here too.

Want to tweak behavior (universe, fees, risk)? Copy `config.example.yaml` to `config.yaml` and edit it — everything is documented inside.

### 5. Try it without Telegram
```bash
python -m src.cli analyse STOCK:AAPL
```

### 6. Run the bot
```bash
python -m src.main
```
Open your bot in Telegram and send `/start`. Switch language anytime with `/langue` (or `/language`).

### 7. Run it 24/7 (Linux, optional)
```bash
sudo bash deploy/install-systemd.sh    # auto-start at boot + auto-restart
journalctl -u owltrader -f             # live logs
```

### 8. Protect access with a password (recommended)
In Telegram, set a password — anyone opening the bot must type it first:
```
/set ACCESS_PASSWORD your-password
```
The message containing the password is automatically **deleted from the chat**, and the value is stored **encrypted**. Check `/securite` for the audit log and intrusion attempts.

### 9. Autonomous trading on Alpaca (optional, free paper account)
1. Create a free account on [alpaca.markets](https://alpaca.markets) and generate **paper** API keys.
2. In Telegram:
   ```
   /set ALPACA_API_KEY_ID your-key
   /set ALPACA_API_SECRET your-secret
   ```
3. Open `/alpaca` → **Auto on Alpaca PAPER** → *Test connection*.

The bot then scans the **entire S&P 500** every hour and trades on your Alpaca account by itself. Watch it with `/cockpit` and `/bilanalpaca`. Only switch to LIVE once you trust it — real money.

### 10. AI advisor (optional, OpenAI key)
```
/set OPENAI_API_KEY sk-...your-key
```
Then open `/ia` and pick a mode (e.g. *Autonomous + AI*). The AI gives one automatic consultation per day (mid US session), executes its orders, and hands the robot a 24-hour plan. The manual "ask now" button is unlimited (each call uses your OpenAI tokens).

---

## Français

### 1. Prérequis
- Python 3.11+
- Un compte Telegram

### 2. Récupérer le code
```bash
git clone https://github.com/mkl159/owltrader.git
cd owltrader
python3 -m venv .venv
source .venv/bin/activate           # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Créer ton bot Telegram (30 secondes)
1. Dans Telegram, ouvre une discussion avec **@BotFather**.
2. Envoie `/newbot`, choisis un nom puis un identifiant finissant par `bot`.
3. BotFather te répond avec un **token** du type `123456789:AAH...`.

### 4. Fichier de configuration (ton token)
Copie l'exemple et renseigne ton token :
```bash
cp .env.example .env
```
Ouvre `.env` et mets :
```ini
TELEGRAM_BOT_TOKEN=123456789:AAH...ton-token...
```
> 🔒 `.env` contient tes secrets et n'est **jamais** envoyé sur Git (il est ignoré). Les clés API gratuites optionnelles (Alpaca paper-trading…) se mettent ici aussi.

Pour personnaliser le comportement (univers, frais, risque) ? Copie `config.example.yaml` en `config.yaml` et édite-le — tout est documenté dedans.

### 5. Essayer sans Telegram
```bash
python -m src.cli analyse STOCK:AAPL
```

### 6. Lancer le bot
```bash
python -m src.main
```
Ouvre ton bot dans Telegram et envoie `/start`. Change de langue quand tu veux avec `/langue`.

### 7. Le faire tourner en 24/7 (Linux, optionnel)
```bash
sudo bash deploy/install-systemd.sh    # démarre au boot + redémarre seul
journalctl -u owltrader -f             # logs en direct
```

### 8. Protéger l'accès par mot de passe (recommandé)
Dans Telegram, définis un mot de passe — quiconque ouvre le bot devra le taper :
```
/set ACCESS_PASSWORD ton-mot-de-passe
```
Le message contenant le mot de passe est automatiquement **supprimé du chat**, et la valeur est stockée **chiffrée**. Consulte `/securite` pour le journal d'audit et les tentatives d'intrusion.

### 9. Trading autonome sur Alpaca (optionnel, compte paper gratuit)
1. Crée un compte gratuit sur [alpaca.markets](https://alpaca.markets) et génère des clés API **paper**.
2. Dans Telegram :
   ```
   /set ALPACA_API_KEY_ID ta-clé
   /set ALPACA_API_SECRET ton-secret
   ```
3. Ouvre `/alpaca` → **Auto sur Alpaca PAPER** → *Tester la connexion*.

Le bot scanne alors **tout le S&P 500** chaque heure et trade seul sur ton compte Alpaca. Suis-le avec `/cockpit` et `/bilanalpaca`. Ne passe en RÉEL que quand tu lui fais confiance — vrai argent.

### 10. Conseiller IA (optionnel, clé OpenAI)
```
/set OPENAI_API_KEY sk-...ta-clé
```
Puis ouvre `/ia` et choisis un mode (ex. *Autonome + IA*). L'IA donne une consultation automatique par jour (en pleine séance US), exécute ses ordres et transmet au robot un plan de trade sur 24 h. Le bouton manuel « demander maintenant » est illimité (chaque appel consomme tes tokens OpenAI).
