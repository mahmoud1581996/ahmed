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
# More Advanced Analytics with Bollinger Bands, Trend Detection, and Support/Resistance Levels
def generate_analytics(df, pair):
    # Calculate Moving Averages
    df['EMA20'] = df['close'].ewm(span=20).mean()
    df['EMA50'] = df['close'].ewm(span=50).mean()

    # RSI Calculation
    df['RSI'] = calculate_rsi(df['close'])

    # MACD Calculation
    df['MACD'] = df['close'].ewm(span=12).mean() - df['close'].ewm(span=26).mean()

    # Bollinger Bands
    df['BB_MID'] = df['close'].rolling(window=20).mean()
    df['BB_STD'] = df['close'].rolling(window=20).std()
    df['BB_UPPER'] = df['BB_MID'] + (df['BB_STD'] * 2)
    df['BB_LOWER'] = df['BB_MID'] - (df['BB_STD'] * 2)

    # Support & Resistance (Simple Highs & Lows)
    df['Support'] = df['low'].rolling(window=20).min()
    df['Resistance'] = df['high'].rolling(window=20).max()

    # Volume Surge Alert
    df['Volume_Surge'] = df['volume'] > df['volume'].rolling(window=20).mean() * 1.5

    # Determine Trading Advice
    latest_rsi = df['RSI'].iloc[-1]
    latest_macd = df['MACD'].iloc[-1]
    latest_price = df['close'].iloc[-1]
    latest_volume_surge = df['Volume_Surge'].iloc[-1]
    latest_ema20 = df['EMA20'].iloc[-1]
    latest_ema50 = df['EMA50'].iloc[-1]
    latest_bb_upper = df['BB_UPPER'].iloc[-1]
    latest_bb_lower = df['BB_LOWER'].iloc[-1]

    advice = "HOLD"

    if latest_rsi < 30 and latest_macd > 0 and latest_ema20 > latest_ema50 and latest_price < latest_bb_lower:
        advice = "🔥 STRONG BUY - Oversold with trend reversal"
    elif latest_rsi > 70 and latest_macd < 0 and latest_ema20 < latest_ema50 and latest_price > latest_bb_upper:
        advice = "🚨 STRONG SELL - Overbought with downtrend starting"
    elif latest_volume_surge:
        advice = "⚠️ CAUTION - Unusual volume detected, possible trend shift"
    
    # Plotting Chart
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df['timestamp'], df['close'], label='Price', linewidth=1.5, color='blue')
    ax.plot(df['timestamp'], df['EMA20'], label='EMA20', linestyle="dashed", color="orange")
    ax.plot(df['timestamp'], df['EMA50'], label='EMA50', linestyle="dashed", color="red")
    ax.fill_between(df['timestamp'], df['BB_LOWER'], df['BB_UPPER'], color='gray', alpha=0.2, label="Bollinger Bands")
    ax.plot(df['timestamp'], df['Support'], linestyle='dotted', color="green", label="Support")
    ax.plot(df['timestamp'], df['Resistance'], linestyle='dotted', color="red", label="Resistance")

    ax.set_title(f'{pair} Analysis | RSI: {latest_rsi:.2f} | Advice: {advice}')
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

# Send chart + buttons
def send_chart_with_buttons(bot, user_id, advice, fig):
    try:
        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)

        # Inline Buttons for Manual Trading Confirmation
        keyboard = [[
            InlineKeyboardButton("✅ Confirm Buy", callback_data="confirm_buy"),
            InlineKeyboardButton("❌ Confirm Sell", callback_data="confirm_sell")
        ]]
        markup = InlineKeyboardMarkup(keyboard)

        # Send Message with Detailed Analytics
        message_text = f"📊 **Crypto Market Report**\n\n" \
                       f"🎯 **Advice:** {advice}\n\n" \
                       f"📈 **EMA20:** {df['EMA20'].iloc[-1]:.2f}\n" \
                       f"📉 **EMA50:** {df['EMA50'].iloc[-1]:.2f}\n" \
                       f"📊 **RSI:** {df['RSI'].iloc[-1]:.2f}\n" \
                       f"📉 **MACD:** {df['MACD'].iloc[-1]:.2f}\n" \
                       f"📊 **Volume Change:** {'🔺' if df['Volume_Surge'].iloc[-1] else '🔻'}\n"

        bot.send_photo(chat_id=user_id, photo=buf, caption=message_text, reply_markup=markup, parse_mode='Markdown')
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
