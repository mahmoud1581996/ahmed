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

# Fetch historical data for Bitcoin (BTC/USDT)
symbol = 'BTC/USDT'
timeframe = '1d'  # Daily data
since = exchange.parse8601('2015-01-01T00:00:00Z')  # Start date for historical data
limit = 2000  # Number of data points to fetch

# Fetch OHLCV (Open, High, Low, Close, Volume) data from Binance
data = exchange.fetch_ohlcv(symbol, timeframe, since, limit)

# Convert the data to a pandas DataFrame
df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

# Calculate the 50-day and 200-day EMAs
df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()

# Generate Buy and Sell signals
df['Signal'] = 0
df.loc[50:, 'Signal'] = np.where(df['EMA50'][50:] > df['EMA200'][50:], 1, 0)  # Fix for chained assignment
df['Position'] = df['Signal'].diff()

# Plot the closing price and EMAs
plt.figure(figsize=(14,7))
plt.plot(df['close'], label='BTC-USD Closing Price', color='blue', alpha=0.5)
plt.plot(df['EMA50'], label='50-Day EMA', color='red')
plt.plot(df['EMA200'], label='200-Day EMA', color='green')

# Plot Buy signals
plt.plot(df[df['Position'] == 1].index, 
         df['EMA50'][df['Position'] == 1], 
         '^', markersize=10, color='g', lw=0, label='Buy Signal')

# Plot Sell signals
plt.plot(df[df['Position'] == -1].index, 
         df['EMA50'][df['Position'] == -1], 
         'v', markersize=10, color='r', lw=0, label='Sell Signal')

plt.title('Bitcoin Price and EMA Crossover Strategy')
plt.legend(loc='best')
plt.show()

# Calculate performance metrics
initial_balance = 10000
balance = initial_balance
positions = []

# Simulate strategy performance
for i in range(1, len(df)):
    if df['Position'][i] == 1:
        # Buy signal: invest at close price
        positions.append(balance / df['close'][i])
        balance = 0
    elif df['Position'][i] == -1 and positions:
        # Sell signal: liquidate at close price
        balance = positions.pop() * df['close'][i]

# Final balance calculation
if positions:
    balance = positions[-1] * df['close'][-1]

total_return = (balance - initial_balance) / initial_balance * 100

# Calculate annualized return
years = (df.index[-1] - df.index[0]).days / 365.25  # Correct calculation of years
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
win_trades = sum([1 for i in range(1, len(df)) if df['Position'][i] == -1 and df['close'][i] > df['close'][i-1]])
total_trades = len(df[df['Position'] != 0])
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
