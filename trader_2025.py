import ccxt
import pandas as pd
import logging
import telegram
import asyncio
import matplotlib.pyplot as plt
import mplfinance as mpf
from ta.trend import MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from io import BytesIO
from dotenv import load_dotenv
import os

class AdvancedBNBBot:
    def __init__(self, api_key, api_secret, telegram_token, chat_id, symbol='BNB/USDT', timeframe='1h'):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        self.symbol = symbol
        self.timeframe = timeframe
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.bot = telegram.Bot(token=self.telegram_token)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    def fetch_market_data(self, limit=100):
        """Fetch OHLCV data from Binance."""
        try:
            bars = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logging.error(f"Error fetching market data: {e}")
            return None

    def analyze_market(self):
        """Perform technical analysis using indicators."""
        df = self.fetch_market_data()
        if df is not None:
            df['RSI'] = RSIIndicator(df['close']).rsi()
            macd = MACD(df['close'])
            df['MACD'] = macd.macd()
            df['MACD_signal'] = macd.macd_signal()
            bb = BollingerBands(df['close'])
            df['BB_upper'] = bb.bollinger_hband()
            df['BB_lower'] = bb.bollinger_lband()

            # Decision Logic
            last_rsi = df['RSI'].iloc[-1]
            last_macd = df['MACD'].iloc[-1]
            last_macd_signal = df['MACD_signal'].iloc[-1]
            last_price = df['close'].iloc[-1]

            signal = "HOLD"
            if last_rsi < 30 and last_macd > last_macd_signal:
                signal = "BUY"
            elif last_rsi > 70 and last_macd < last_macd_signal:
                signal = "SELL"

            return df, signal, last_price
        return None, None, None

    async def send_analysis(self):
        """Send market analysis to Telegram."""
        df, signal, last_price = self.analyze_market()
        if df is not None:
            message = f"BNB Analysis:\nPrice: {last_price}\nSignal: {signal}\nRSI: {df['RSI'].iloc[-1]}\nMACD: {df['MACD'].iloc[-1]}\nMACD Signal: {df['MACD_signal'].iloc[-1]}"
            await self.bot.send_message(chat_id=self.chat_id, text=message)
            self.visualize_market(df)

    def visualize_market(self, df):
        """Generate a market visualization and send it via Telegram."""
        fig, ax = plt.subplots(figsize=(10, 5))
        mpf.plot(df, type='candle', mav=(10, 20), volume=True, ax=ax)
        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        asyncio.run(self.bot.send_photo(chat_id=self.chat_id, photo=buf))

    async def handle_telegram_commands(self, update):
        """Process Telegram commands."""
        command = update.message.text.lower()
        if command == '/analyze':
            await self.send_analysis()
        elif command == '/trade buy':
            self.place_order('buy', 0.01)
            await self.bot.send_message(chat_id=self.chat_id, text="BUY Order Placed.")
        elif command == '/trade sell':
            self.place_order('sell', 0.01)
            await self.bot.send_message(chat_id=self.chat_id, text="SELL Order Placed.")

    def place_order(self, side, quantity):
        """Execute buy or sell order."""
        try:
            order = self.exchange.create_market_order(self.symbol, side, quantity)
            logging.info(f"Placed {side.upper()} order: {order}")
            return order
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return None

if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    telegram_token = "7149979903:AAEdmKT4L1mYBXKHp5A8UWClsPpHET-We2Q"
    chat_id = os.getenv("CHAT_ID")
    
    bot = AdvancedBNBBot(api_key, api_secret, telegram_token, chat_id)
    asyncio.run(bot.send_analysis())
