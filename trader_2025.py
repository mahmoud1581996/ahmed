import os
import logging
import asyncio
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.util import astimezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Telegram & Binance API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot_analytics.log"),
        logging.StreamHandler()
    ]
)

# Initialize Binance API
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'adjustForTimeDifference': True}
})

# Store Selected Pairs for Users
selected_pair = {}

# Initialize Scheduler with Correct Timezone
scheduler = AsyncIOScheduler(timezone=astimezone(pytz.utc))
scheduler.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Start command: Show trading pair selection """
    await select_pair(update, context)

async def select_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Show predefined pairs & allow custom pair entry """
    pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT"]
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in pairs]
    keyboard.append([InlineKeyboardButton("🔍 Enter Custom Pair", callback_data="custom_pair")])

    await update.message.reply_text(
        "📊 Select a Trading Pair or Enter a Custom One:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_pair_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Handle pair selection from buttons """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "custom_pair":
        await query.edit_message_text("✏️ Please type your custom trading pair (e.g., `ADA/USDT`).")
        return

    pair = query.data.replace("pair_", "")
    selected_pair[user_id] = pair
    await query.edit_message_text(f"✅ Selected Pair: {pair}. Fetching market data now...")
    await send_analytics(update, user_id, pair)

async def manual_pair_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Handle manually entered pairs """
    user_id = update.effective_user.id
    pair = update.message.text.upper().strip()

    # Validate Pair
    markets = exchange.load_markets()
    if pair in markets:
        selected_pair[user_id] = pair
        await update.message.reply_text(f"✅ Custom Pair Set: {pair}. Fetching market data...")
        await send_analytics(update, user_id, pair)
    else:
        await update.message.reply_text("❌ Invalid pair! Please enter a valid Binance trading pair (e.g., BNB/USDT).")

async def send_analytics(update: Update, user_id, pair):
    """ Fetch market data, analyze, and send results """
    try:
        df = await asyncio.to_thread(fetch_ohlcv, pair)
        analysis, fig = generate_analytics(df, pair)
        await send_chart(update, user_id, analysis, fig, pair)
    except Exception as e:
        logging.error(f"Error fetching analytics for {pair}: {e}")
        await update.message.reply_text("⚠️ Failed to fetch market data. Try again later.")

def fetch_ohlcv(pair):
    """ Fetch OHLCV data from Binance """
    ohlcv = exchange.fetch_ohlcv(pair, timeframe="15m", limit=50)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def generate_analytics(df, pair):
    """ Perform technical analysis """
    df["EMA20"] = df["close"].ewm(span=20).mean()
    df["EMA50"] = df["close"].ewm(span=50).mean()
    df["RSI"] = calculate_rsi(df["close"])

    # MACD Calculation
    df["MACD"] = df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()

    # Bollinger Bands
    df["BB_MID"] = df["close"].rolling(window=20).mean()
    df["BB_STD"] = df["close"].rolling(window=20).std()
    df["BB_UPPER"] = df["BB_MID"] + (df["BB_STD"] * 2)
    df["BB_LOWER"] = df["BB_MID"] - (df["BB_STD"] * 2)

    trend = "Bullish" if df["EMA20"].iloc[-1] > df["EMA50"].iloc[-1] else "Bearish"
    advice = "HOLD"
    if df["RSI"].iloc[-1] < 30:
        advice = "BUY 📈 (Oversold)"
    elif df["RSI"].iloc[-1] > 70:
        advice = "SELL 📉 (Overbought)"

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df["timestamp"], df["close"], label="Price", linewidth=1.5)
    ax.plot(df["timestamp"], df["EMA20"], label="EMA20", linestyle="dashed", color="green")
    ax.plot(df["timestamp"], df["EMA50"], label="EMA50", linestyle="dashed", color="red")
    ax.set_title(f"{pair} | RSI: {df['RSI'].iloc[-1]:.2f} | Trend: {trend}")
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    return advice, fig

async def send_chart(update: Update, user_id, advice, fig, pair):
    """ Send analysis chart with action buttons """
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

def main():
    """ Start the bot """
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("select_pair", select_pair))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manual_pair_handler))
    app.add_handler(CallbackQueryHandler(handle_pair_callback, pattern="^pair_|^custom_pair$"))

    scheduler.start()
    app.run_polling()

if __name__ == "__main__":
    main()
