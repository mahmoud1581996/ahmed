import os
import requests
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

# Load the environment variables from the .env file
load_dotenv()

# Telegram details from .env
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # Your Telegram bot token
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')  # Your chat ID

# Binance API details from .env
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')  # Binance API Key
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')  # Binance Secret Key

# Telegram message sending function
def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage'
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
    }
    response = requests.get(url, params=params)
    return response

# Function to send results to Telegram
def send_results_to_telegram(results):
    message = "\n".join([f"{key}: {value}" for key, value in results.items()])
    send_telegram_message(message)

# Initialize the Binance connection using ccxt
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
})

# Fetch historical data for Binance Coin (BNB/USDT)
symbol = 'BNB/USDT'
timeframe = '1d'  # Daily data
since = exchange.parse8601('2021-01-01T00:00:00Z')  # Start date for historical data
limit = 2000  # Number of data points to fetch

# Fetch OHLCV (Open, High, Low, Close, Volume) data from Binance
data = exchange.fetch_ohlcv(symbol, timeframe, since, limit)

# Convert the data to a pandas DataFrame
df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

# Calculate the RSI (Relative Strength Index)
def compute_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

df['RSI'] = compute_rsi(df['close'], window=14)

# Generate Buy and Sell signals based on RSI
df['Signal'] = 0
df.loc[df['RSI'] < 30, 'Signal'] = 1  # Buy signal when RSI < 30
df.loc[df['RSI'] > 70, 'Signal'] = -1  # Sell signal when RSI > 70

# Plot the RSI and signals
plt.figure(figsize=(14,7))
plt.plot(df['timestamp'], df['RSI'], label='RSI', color='blue')
plt.axhline(y=30, color='green', linestyle='--', label='Buy Signal (RSI < 30)')
plt.axhline(y=70, color='red', linestyle='--', label='Sell Signal (RSI > 70)')

# Plot Buy signals
plt.plot(df[df['Signal'] == 1]['timestamp'], df['RSI'][df['Signal'] == 1], '^', markersize=10, color='g', lw=0, label='Buy Signal')

# Plot Sell signals
plt.plot(df[df['Signal'] == -1]['timestamp'], df['RSI'][df['Signal'] == -1], 'v', markersize=10, color='r', lw=0, label='Sell Signal')

plt.title('RSI Strategy: Buy (RSI < 30) / Sell (RSI > 70)')
plt.legend(loc='best')
plt.show()

# Backtesting the strategy
initial_balance = 10000
balance = initial_balance
positions = []
buy_price = 0
sell_price = 0

for i in range(1, len(df)):
    if df['Signal'][i] == 1 and balance > 0:  # Buy signal (RSI < 30)
        buy_price = df['close'][i]
        positions.append(balance / buy_price)
        balance = 0
    elif df['Signal'][i] == -1 and positions:  # Sell signal (RSI > 70)
        sell_price = df['close'][i]
        balance = positions.pop() * sell_price

# Final balance calculation
if positions:
    if len(positions) > 0:
    balance = positions[-1] * df['close'][-1]  # Correctly access last element
    else:
    balance = initial_balance  # No positions, so balance stays the same


# Performance Metrics Calculation
total_return = (balance - initial_balance) / initial_balance * 100

# Calculate annualized return
years = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days / 365.25
annualized_return = (1 + total_return / 100) ** (1 / years) - 1

# Calculate Sharpe Ratio
daily_returns = df['close'].pct_change().dropna()
sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

# Calculate Max Drawdown
cumulative_returns = (1 + daily_returns).cumprod()
peak = cumulative_returns.cummax()
drawdown = (cumulative_returns - peak) / peak
max_drawdown = drawdown.min()

# Calculate Win Rate
win_trades = sum([1 for i in range(1, len(df)) if df['Signal'][i] == -1 and df['close'][i] > df['close'][i-1]])
total_trades = len(df[df['Signal'] != 0])
win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0

# Store results in a dictionary
results = {
    'Total Return': f"{total_return:.2f}%",
    'Annualized Return': f"{annualized_return * 100:.2f}%",
    'Sharpe Ratio': f"{sharpe_ratio:.2f}",
    'Max Drawdown': f"{max_drawdown:.2f}",
    'Win Rate': f"{win_rate:.2f}%",
}

# Send the results to Telegram
send_results_to_telegram(results)

