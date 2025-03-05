# Binance Trading Bot

## Overview
The **Binance Trading Bot** is an automated trading bot that uses the **Binance exchange** via the **CCXT** library. The bot implements **EMA crossover strategies** to generate buy and sell signals and sends **market updates via Telegram**.

## Features
- Fetches real-time market data from Binance.
- Calculates **Exponential Moving Averages (EMA)** for trend analysis.
- Implements **EMA crossover strategy** for trading signals.
- Automates order placement (with paper trading mode available).
- Sends **Telegram notifications** for market updates.
- Uses **asynchronous execution** for efficient performance.

## Requirements
- **Python 3.x** installed.
- A **Binance API key and secret** (for real trading).
- A **Telegram bot token and chat ID** for notifications.
- Required dependencies:
  ```sh
  pip install ccxt pandas telegram asyncio
  ```

## Installation
1. **Clone the repository**
   ```sh
   git clone https://github.com/yourusername/binance-trading-bot.git
   cd binance-trading-bot
   ```
2. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```
3. **Set up your API keys**
   - Update the **API key**, **secret**, and **Telegram token** in the script (`trader_2025.py`).

## How to Use
1. **Modify bot parameters** (symbol, timeframe, EMA settings, risk-reward ratio) as needed.
2. **Run the bot**
   ```sh
   python trader_2025.py
   ```
3. The bot will:
   - Continuously fetch market data.
   - Generate buy/sell signals.
   - Place trades if paper trading is disabled.
   - Send periodic market updates via Telegram.

## Configuration
Modify these parameters in `trader_2025.py`:
```python
symbol = 'BTC/USDT'      # Trading pair
ema_fast = 12            # Fast EMA period
ema_slow = 26            # Slow EMA period
paper_trading = True     # Set False to enable live trading
```

## Security Warning 🚨
**Do NOT expose your API keys in public repositories.** Use environment variables or a separate config file to manage secrets securely.

## License
This project is licensed under the **MIT License**.

## Disclaimer
This bot is for **educational purposes only**. Use at your own risk. The author is not responsible for any financial losses incurred while using this bot.

---
### Happy Trading! 📈🚀
