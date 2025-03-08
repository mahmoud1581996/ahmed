import ccxt
import time
import pandas as pd
import logging
import telegram
import asyncio


class BinanceTradingBot:
    def __init__(self, api_key, api_secret, telegram_token, chat_id, symbol='BNB/USDT', timeframe='1h', ema_fast=12,
                 ema_slow=26, risk_reward=2.0, paper_trading=True):
        """
        Initialize the Binance Trading Bot
        """
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        self.symbol = symbol
        self.timeframe = timeframe
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.risk_reward = risk_reward
        self.position = None
        self.paper_trading = paper_trading  # Enable/disable real trading
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.bot = telegram.Bot(token=self.telegram_token)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    async def send_telegram_message(self, message):
        """Send a Telegram notification"""
        await self.bot.send_message(chat_id=self.chat_id, text=message)

    def fetch_market_data(self, limit=50):
        """Fetch historical OHLCV data"""
        try:
            bars = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logging.error(f"Error fetching market data: {e}")
            return None

    def calculate_indicators(self, df):
        """Calculate EMA indicators"""
        df[f'EMA_{self.ema_fast}'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df[f'EMA_{self.ema_slow}'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        return df

    def generate_signal(self, df):
        """Determine buy/sell signals based on EMA crossover"""
        if df[f'EMA_{self.ema_fast}'].iloc[-2] < df[f'EMA_{self.ema_slow}'].iloc[-2] and \
                df[f'EMA_{self.ema_fast}'].iloc[-1] > df[f'EMA_{self.ema_slow}'].iloc[-1]:
            return 'buy'
        elif df[f'EMA_{self.ema_fast}'].iloc[-2] > df[f'EMA_{self.ema_slow}'].iloc[-2] and \
                df[f'EMA_{self.ema_fast}'].iloc[-1] < df[f'EMA_{self.ema_slow}'].iloc[-1]:
            return 'sell'
        return None

    async def send_market_update(self):
        """Send a market update report every 20 minutes"""
        df = self.fetch_market_data()
        if df is not None:
            df = self.calculate_indicators(df)
            signal = self.generate_signal(df)
            latest_price = df['close'].iloc[-1]
            message = f"Market Update:\nSymbol: {self.symbol}\nLatest Price: {latest_price}\nEMA {self.ema_fast}: {df[f'EMA_{self.ema_fast}'].iloc[-1]}\nEMA {self.ema_slow}: {df[f'EMA_{self.ema_slow}'].iloc[-1]}\nCurrent Signal: {signal if signal else 'No trade signal'}"
            await self.send_telegram_message(message)

    async def run(self):
        """Main bot loop"""
        counter = 0
        while True:
            df = self.fetch_market_data()
            if df is not None:
                df = self.calculate_indicators(df)
                signal = self.generate_signal(df)

                if signal == 'buy' and self.position is None:
                    self.position = self.place_order('buy', 0.01)  # Adjust position size
                elif signal == 'sell' and self.position is not None:
                    self.place_order('sell', 0.01)
                    self.position = None

            if counter % 20 == 0:
                await self.send_market_update()
            counter += 1
            await asyncio.sleep(60)  # Adjust based on timeframe

if __name__ == "__main__":
       from dotenv import load_dotenv
            import os
            load_dotenv()

             api_key = os.getenv("api_key")
             api_secret = os.getenv("api_secret")
             telegram_token = os.getenv("telegram_token")
             chat_id = os.getenv("chat_id"

        bot = BinanceTradingBot(api_key, api_secret, telegram_token, chat_id, paper_trading=True)
        asyncio.run(bot.run())

