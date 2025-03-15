import os
import logging
import asyncio
from datetime import datetime
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ENV Vars
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Binance Init
exchange = ccxt.binance({
    "apiKey": BINANCE_API_KEY,
    "secret": BINANCE_API_SECRET,
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# Store Selected Pairs Per User
selected_pair = {}

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bot ready! Use /select_pair to choose a crypto pair.")

# /select_pair command - Allows predefined & manual input
async def select_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(pair, callback_data=f"pair_{pair}") for pair in ['BNB/USDT', 'BTC/USDT', 'ETH/USDT']],
        [InlineKeyboardButton(pair, callback_data=f"pair_{pair}") for pair in ['XRP/USDT', 'SOL/USDT']],
        [InlineKeyboardButton("🔍 Enter Manually", callback_data="manual_pair")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📊 Please select a trading pair:", reply_markup=reply_markup)

# Handle Pair Selection and Manual Entry
async def handle_pair_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "manual_pair":
        await query.edit_message_text("🔍 Please type the pair (e.g., `ADA/USDT`) into the chat.")
        return

    pair = query.data.replace("pair_", "")
    await validate_and_set_pair(update, context, pair)

# Handle User Input for Manual Pair Entry
async def manual_pair_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = update.message.text.upper()
    await validate_and_set_pair(update, context, pair)

# Validate & Set the Trading Pair
async def validate_and_set_pair(update: Update, context: ContextTypes.DEFAULT_TYPE, pair):
    user_id = update.effective_user.id

    try:
        markets = exchange.load_markets()
        if pair in markets:
            selected_pair[user_id] = pair
            await update.message.reply_text(f"✅ Pair set to: {pair}. Fetching analytics now...")
            df = fetch_ohlcv(pair)
            advice, fig = generate_analytics(df, pair)
            await send_chart_with_buttons(context, user_id, advice, fig, df, pair)
        else:
            await update.message.reply_text("❌ Invalid pair! Please enter a valid Binance trading pair (e.g., BNB/USDT).")
    except Exception as e:
        logger.error(f"Error validating pair: {e}")
        await update.message.reply_text("⚠️ Error connecting to Binance. Please try again later.")

# Fetch OHLCV Data from Binance
def fetch_ohlcv(pair):
    try:
        ohlcv = exchange.fetch_ohlcv(pair, timeframe='15m', limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        logger.error(f"Error fetching OHLCV for {pair}: {e}")
        raise

# Generate Technical Analysis + Chart
def generate_analytics(df, pair):
    df['EMA20'] = df['close'].ewm(span=20).mean()
    df['EMA50'] = df['close'].ewm(span=50).mean()
    df['RSI'] = calculate_rsi(df['close'])

    advice = "HOLD"
    if df['RSI'].iloc[-1] < 30 and df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]:
        advice = "🔥 STRONG BUY"
    elif df['RSI'].iloc[-1] > 70 and df['EMA20'].iloc[-1] < df['EMA50'].iloc[-1]:
        advice = "🚨 STRONG SELL"

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df['timestamp'], df['close'], label='Price', linewidth=1.5)
    ax.plot(df['timestamp'], df['EMA20'], label='EMA20', linestyle="dashed")
    ax.plot(df['timestamp'], df['EMA50'], label='EMA50', linestyle="dashed")
    ax.set_title(f'{pair} Analysis | RSI: {df["RSI"].iloc[-1]:.2f} | Advice: {advice}')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    return advice, fig

# RSI Calculation
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Send Chart with Trade Confirmation & Change Pair Option
async def send_chart_with_buttons(context, user_id, advice, fig, df, pair):
    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)

    keyboard = [
        [InlineKeyboardButton("✅ Confirm Buy", callback_data="confirm_buy"),
         InlineKeyboardButton("❌ Confirm Sell", callback_data="confirm_sell")],
        [InlineKeyboardButton("🔄 Change Pair", callback_data="change_pair")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    message_text = f"📊 **Crypto Market Report for {pair}**\n\n" \
                   f"🎯 **Advice:** {advice}\n\n" \
                   f"📈 **EMA20:** {df['EMA20'].iloc[-1]:.2f}\n" \
                   f"📉 **EMA50:** {df['EMA50'].iloc[-1]:.2f}\n" \
                   f"📊 **RSI:** {df['RSI'].iloc[-1]:.2f}\n"

    await context.bot.send_photo(chat_id=user_id, photo=buf, caption=message_text, reply_markup=markup, parse_mode='Markdown')

# Handle Trade Confirmation & Pair Change
async def trade_and_pair_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_pair":
        await select_pair(update, context)
    elif query.data == "confirm_buy":
        await query.edit_message_caption(caption="🟢 BUY Confirmed")
    elif query.data == "confirm_sell":
        await query.edit_message_caption(caption="🔴 SELL Confirmed")

# Main Function
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("select_pair", select_pair))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manual_pair_entry))
    app.add_handler(CallbackQueryHandler(trade_and_pair_callback, pattern="^pair_|^confirm_|^change_pair$"))

    app.run_polling()

if __name__ == "__main__":
    main()
