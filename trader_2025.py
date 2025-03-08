import os
import logging
import ccxt
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
EXCHANGE_NAME = "binance"  # Set your exchange

# Initialize exchange
exchange = getattr(ccxt, EXCHANGE_NAME)({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {'defaultType': 'spot'}
})

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Start command
def start(update, context):
    update.message.reply_text("Welcome to BNB Trading Bot! Use /help for commands.")

# Help command
def help_command(update, context):
    update.message.reply_text("""Available commands:
    /analytics - Get advanced trading analytics
    /visualize - Get BNB price chart
    /order <price> <qty> - Place a limit order
    "/"")

# Advanced analytics
def analytics(update, context):
    ticker = exchange.fetch_ticker("BNB/USDT")
    price = ticker['last']
    spread = ticker['ask'] - ticker['bid']
    update.message.reply_text(f"BNB Price: {price} USDT\nSpread: {spread} USDT")

# Visualization
def visualize(update, context):
    prices = np.random.normal(300, 50, 100)  # Simulated price data
    plt.figure()
    plt.plot(prices, label='BNB Price')
    plt.legend()
    plt.xlabel('Time')
    plt.ylabel('Price (USDT)')
    plt.title('BNB Price Chart')
    plt.grid()
    plt.savefig("chart.png")
    update.message.reply_photo(photo=open("chart.png", "rb"))
    os.remove("chart.png")

# Place order
def place_order(update, context):
    try:
        args = context.args
        price, qty = float(args[0]), float(args[1])
        order = exchange.create_limit_buy_order("BNB/USDT", qty, price)
        update.message.reply_text(f"Order placed: {order}")
    except Exception as e:
        update.message.reply_text(f"Error: {e}")

# Main function
if __name__ == "__main__":
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("analytics", analytics))
    dp.add_handler(CommandHandler("visualize", visualize))
    dp.add_handler(CommandHandler("order", place_order, pass_args=True))
    updater.start_polling()
    updater.idle()
