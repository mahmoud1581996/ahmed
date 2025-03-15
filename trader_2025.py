import os
import logging
import asyncio
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Binance API Setup
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

class CryptoAnalyticsBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'adjustForTimeDifference': True}
        })
        self.selected_pair = {}  # Stores user-selected pairs
        self._configure_handlers()
        self._setup_logging()

    def _configure_handlers(self):
        handlers = [
            CommandHandler("start", self._start_handler),
            CommandHandler("select_pair", self._display_pair_selection),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._manual_pair_handler),
            CallbackQueryHandler(self._button_handler)
        ]
        for handler in handlers:
            self.app.add_handler(handler)

    def _setup_logging(self):
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
            handlers=[
                logging.FileHandler("bot_analytics.log"),
                logging.StreamHandler()
            ]
        )

    async def _start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._display_pair_selection(update)

    async def _display_pair_selection(self, update: Update):
        """Display available trading pairs and allow manual entry"""
        pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT"]
        keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in pairs]
        keyboard.append([InlineKeyboardButton("🔍 Enter Custom Pair", callback_data="custom_pair")])
        
        await update.message.reply_text(
            "🔍 Select a Trading Pair or Enter a Custom One:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if query.data == "custom_pair":
            await query.edit_message_text("✏️ Please type your custom trading pair (e.g., `ADA/USDT`).")
            return

        pair = query.data.replace("pair_", "")
        self.selected_pair[user_id] = pair

        await query.edit_message_text(f"✅ Selected Pair: {pair}. Fetching market data now...")
        await self._send_analytics(update, user_id, pair)

    async def _manual_pair_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle manually entered pairs"""
        user_id = update.effective_user.id
        pair = update.message.text.upper().strip()

        # Validate custom pair
        markets = self.exchange.load_markets()
        if pair in markets:
            self.selected_pair[user_id] = pair
            await update.message.reply_text(f"✅ Custom Pair Set: {pair}. Fetching market data...")
            await self._send_analytics(update, user_id, pair)
        else:
            await update.message.reply_text("❌ Invalid pair! Please enter a valid Binance trading pair (e.g., BNB/USDT).")

    async def _send_analytics(self, update: Update, user_id, pair):
        """Fetch market data, analyze, and send to user"""
        try:
            df = await asyncio.to_thread(self._fetch_ohlcv, pair)
            analysis, fig = self._generate_analytics(df, pair)
            await self._send_chart(update, user_id, analysis, fig, pair)
        except Exception as e:
            logging.error(f"Error fetching analytics for {pair}: {e}")
            await update.message.reply_text("⚠️ Failed to fetch market data. Try again later.")

    def _fetch_ohlcv(self, pair):
        """Fetch OHLCV data from Binance"""
        ohlcv = self.exchange.fetch_ohlcv(pair, timeframe="15m", limit=50)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    def _generate_analytics(self, df, pair):
        """Perform technical analysis"""
        df["EMA20"] = df["close"].ewm(span=20).mean()
        df["EMA50"] = df["close"].ewm(span=50).mean()
        df["RSI"] = self._calculate_rsi(df["close"])

        # Determine trend strength
        trend = "Bullish" if df["EMA20"].iloc[-1] > df["EMA50"].iloc[-1] else "Bearish"
        advice = "HOLD"
        if df["RSI"].iloc[-1] < 30:
            advice = "BUY 📈 (Oversold)"
        elif df["RSI"].iloc[-1] > 70:
            advice = "SELL 📉 (Overbought)"

        # Create Chart
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df["timestamp"], df["close"], label="Price", linewidth=1.5)
        ax.plot(df["timestamp"], df["EMA20"], label="EMA20", linestyle="dashed", color="green")
        ax.plot(df["timestamp"], df["EMA50"], label="EMA50", linestyle="dashed", color="red")
        ax.set_title(f"{pair} | RSI: {df['RSI'].iloc[-1]:.2f} | Trend: {trend}")
        ax.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()

        return advice, fig

    async def _send_chart(self, update: Update, user_id, advice, fig, pair):
        """Send generated analytics chart and buttons"""
        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)

        keyboard = [
            [InlineKeyboardButton("✅ Confirm Buy", callback_data="confirm_buy"),
             InlineKeyboardButton("❌ Confirm Sell", callback_data="confirm_sell")],
            [InlineKeyboardButton("🔄 Change Pair", callback_data="change_pair")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_photo(
            photo=buf, caption=f"📊 **{pair} Market Analysis**\n🎯 **Advice:** {advice}",
            reply_markup=reply_markup, parse_mode="Markdown"
        )

    def run(self):
        """Start the bot"""
        self.app.run_polling()

if __name__ == "__main__":
    bot = CryptoAnalyticsBot()
    bot.run()
