import os
import ccxt
import json
import logging
import telegram
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Load environment variables
load_dotenv()
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Initialize Binance API
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
    'enableRateLimit': True
})

# Initialize Telegram bot
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def get_bnb_price():
    """Fetches the latest BNB price."""
    ticker = exchange.fetch_ticker('BNB/USDT')
    return ticker['last']

def send_telegram_message(message):
    """Sends a message to Telegram chat."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

def start(update, context):
    update.message.reply_text("Hello! I'm your Binance BNB trading bot! Use /price to check BNB price.")

def get_price(update, context):
    price = get_bnb_price()
    update.message.reply_text(f"BNB Current Price: ${price}")

def buy_bnb(update, context):
    amount = 0.1  # Adjust as needed
    order = exchange.create_market_buy_order('BNB/USDT', amount)
    update.message.reply_text(f"Buy Order Executed: {order}")
    send_telegram_message(f"✅ Bought {amount} BNB at market price.")

def sell_bnb(update, context):
    amount = 0.1  # Adjust as needed
    order = exchange.create_market_sell_order('BNB/USDT', amount)
    update.message.reply_text(f"Sell Order Executed: {order}")
    send_telegram_message(f"❌ Sold {amount} BNB at market price.")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", get_price))
    dp.add_handler(CommandHandler("buy", buy_bnb))
    dp.add_handler(CommandHandler("sell", sell_bnb))
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
