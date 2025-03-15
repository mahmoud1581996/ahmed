import os
import logging
import asyncio
from datetime import datetime
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ENV Vars
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
CHAT_ID = os.getenv("CHAT_ID")

# Logging
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

# Globals
selected_pair = {}

# Command: /start
def start(update: Update, context: CallbackContext):
    logger.info("/start command received")
    update.message.reply_text("👋 Bot ready! Use /select_pair to choose a crypto pair.")

# Command: /select_pair
def select_pair(update: Update, context: CallbackContext):
    reply_keyboard = [['BNB/USDT', 'BTC/USDT', 'ETH/USDT'], ['XRP/USDT', 'SOL/USDT']]
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(pair, callback_data=f"pair_{pair}") for pair in row]
        for row in reply_keyboard
    ])
    update.message.reply_text("Please select a trading pair:", reply_markup=markup)

# Pair Selection Callback
# Pair Selection Callback - Immediate Analytics
def handle_pair_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    pair = query.data.replace("pair_", "")
    user_id = query.from_user.id
    selected_pair[user_id] = pair
    logger.info(f"Pair selected by user {user_id}: {pair}")

    # Notify user and send analytics immediately
    query.edit_message_text(f"✅ Pair selected: {pair}. Fetching analytics now...")

    try:
        df = fetch_ohlcv(pair)
        advice, fig = generate_analytics(df, pair)
        send_chart_with_buttons(context.bot, user_id, advice, fig)
        logger.info(f"Immediate analytics sent to user {user_id} for {pair}")
    except Exception as e:
        logger.error(f"Error during immediate analytics for {pair}: {e}")


# Scheduled Job
def scheduled_analytics(context: CallbackContext):
    for user_id, pair in selected_pair.items():
        try:
            df = fetch_ohlcv(pair)
            advice, fig = generate_analytics(df, pair)
            send_chart_with_buttons(context.bot, user_id, advice, fig)
            logger.info(f"Analytics sent to user {user_id} for {pair}")
        except Exception as e:
            logger.error(f"Error during analytics for {pair}: {e}")

# Fetch OHLCV Data
def fetch_ohlcv(pair):
    try:
        ohlcv = exchange.fetch_ohlcv(pair, timeframe='15m', limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        logger.error(f"Error fetching OHLCV for {pair}: {e}")
        raise

# Generate Analytics + Plot
def generate_analytics(df, pair):
    df['EMA20'] = df['close'].ewm(span=20).mean()
    df['EMA50'] = df['close'].ewm(span=50).mean()
    df['RSI'] = calculate_rsi(df['close'])
    df['MACD'] = df['close'].ewm(span=12).mean() - df['close'].ewm(span=26).mean()

    advice = "HOLD"
    if df['RSI'].iloc[-1] < 30 and df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]:
        advice = "BUY"
    elif df['RSI'].iloc[-1] > 70 and df['EMA20'].iloc[-1] < df['EMA50'].iloc[-1]:
        advice = "SELL"

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.plot(df['timestamp'], df['close'], label='Price', linewidth=1.5)
    ax1.plot(df['timestamp'], df['EMA20'], label='EMA20')
    ax1.plot(df['timestamp'], df['EMA50'], label='EMA50')
    ax1.set_title(f'{pair} Price + EMA | RSI: {df["RSI"].iloc[-1]:.2f} | Advice: {advice}')
    ax1.legend()
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

# Send chart + buttons
def send_chart_with_buttons(bot, user_id, advice, fig):
    try:
        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        keyboard = [[
            InlineKeyboardButton("✅ Confirm Buy", callback_data="confirm_buy"),
            InlineKeyboardButton("❌ Confirm Sell", callback_data="confirm_sell")
        ]]
        markup = InlineKeyboardMarkup(keyboard)
        bot.send_photo(chat_id=user_id, photo=buf, caption=f"📊 Advice: {advice}", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error sending chart to user {user_id}: {e}")

# Handle trade confirmation
def trade_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    action = query.data
    pair = selected_pair.get(query.from_user.id)

    if action == "confirm_buy":
        query.edit_message_caption(caption=f"🟢 BUY Confirmed for {pair}")
        logger.info(f"User {query.from_user.id} confirmed BUY for {pair}")
    elif action == "confirm_sell":
        query.edit_message_caption(caption=f"🔴 SELL Confirmed for {pair}")
        logger.info(f"User {query.from_user.id} confirmed SELL for {pair}")

# MAIN
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("select_pair", select_pair))
    dp.add_handler(CallbackQueryHandler(handle_pair_callback, pattern="^pair_"))
    dp.add_handler(CallbackQueryHandler(trade_callback, pattern="^confirm_"))

    job_queue = updater.job_queue
    job_queue.run_repeating(scheduled_analytics, interval=600, first=10)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
