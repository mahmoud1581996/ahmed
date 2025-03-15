import asyncio
import logging
import ccxt
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import matplotlib.pyplot as plt
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Telegram & Binance Config
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

binance = ccxt.binance()
selected_pair = "BTC/USDT"
previous_price = None
scheduler = AsyncIOScheduler()

logging.basicConfig(level=logging.INFO)

# 📊 Fetch Market Data
async def fetch_binance_data(symbol, timeframe='5m', limit=100):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        logging.error(f"Error fetching Binance data: {e}")
        return None

# 📈 Perform Technical Analysis
async def analyze_market(pair):
    global previous_price
    df = await fetch_binance_data(pair)
    if df is None or df.empty:
        return "⚠️ Error fetching data."

    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.bbands(length=20, std=2, append=True)

    last_close = df.iloc[-1]['close']
    previous_price = last_close if previous_price is None else previous_price
    price_change = (last_close - previous_price) / previous_price * 100

    report = (
        f"📊 *Technical Analysis for {pair}*\n"
        f"📈 Price: *{last_close:.2f} USDT*\n"
        f"🔹 RSI: {df.iloc[-1]['RSI_14']:.2f}\n"
        f"🔸 MACD: {df.iloc[-1]['MACD_12_26_9']:.2f}\n"
        f"🔹 EMA 50: {df.iloc[-1]['EMA_50']:.2f}\n"
        f"🔸 EMA 200: {df.iloc[-1]['EMA_200']:.2f}\n"
        f"🔹 Bollinger Upper: {df.iloc[-1]['BBU_20_2.0']:.2f}\n"
        f"🔸 Bollinger Lower: {df.iloc[-1]['BBL_20_2.0']:.2f}\n"
        f"📊 *Price Change:* {price_change:.2f}%\n"
    )

    previous_price = last_close
    await generate_chart(df, pair)
    return report

# 📉 Generate Chart
async def generate_chart(df, pair):
    df.set_index("timestamp", inplace=True)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)

    mpf.plot(
        df.tail(50),
        type='candle',
        style='charles',
        title=f"{pair} - Last 50 Candles",
        ylabel='Price (USDT)',
        volume=True,
        mav=(50, 200),
        savefig="chart.png"
    )

# 🛒 Telegram Inline Buttons
def get_trade_buttons():
    buttons = [
        [InlineKeyboardButton("✅ Buy", callback_data="buy"),
         InlineKeyboardButton("❌ Sell", callback_data="sell")],
        [InlineKeyboardButton("🔄 Change Pair", callback_data="change_pair")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# 🏦 Handle Trade Confirmation
@dp.callback_query_handler(lambda c: c.data in ["buy", "sell"])
async def process_trade(callback_query: types.CallbackQuery):
    action = "BUY" if callback_query.data == "buy" else "SELL"
    await bot.send_message(callback_query.from_user.id, f"✅ Confirmed {action} order for {selected_pair}")

# 🔄 Handle Pair Change
@dp.callback_query_handler(lambda c: c.data == "change_pair")
async def change_pair(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "📊 Enter the trading pair (e.g., BTC/USDT):")

@dp.message_handler()
async def handle_new_pair(message: types.Message):
    global selected_pair
    selected_pair = message.text.upper()
    await bot.send_message(message.chat.id, f"✅ Selected Pair: {selected_pair}")
    await send_market_analysis(message.chat.id)

# 📌 Send Market Analysis
async def send_market_analysis(chat_id):
    report = await analyze_market(selected_pair)
    await bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_trade_buttons())
    await bot.send_photo(chat_id, photo=open("chart.png", "rb"))

# ⏳ Periodic Market Updates
async def periodic_analysis():
    chat_id = YOUR_TELEGRAM_CHAT_ID
    report = await analyze_market(selected_pair)
    await bot.send_message(chat_id, report, parse_mode="Markdown", reply_markup=get_trade_buttons())
    await bot.send_photo(chat_id, photo=open("chart.png", "rb"))

# 🚀 Start Bot
async def main():
    scheduler.add_job(periodic_analysis, "interval", minutes=10)
    scheduler.start()
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
