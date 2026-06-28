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
