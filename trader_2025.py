#!/usr/bin/env python3
import os
import asyncio
import hmac
import hashlib
import logging
import ccxt.async_support as ccxt
import pandas as pd
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from ta import momentum, trend, volatility

class BinanceTradeManager:
    """Integrated Binance trading with proper authentication"""
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': os.getenv("BINANCE_API_KEY"),
            'secret': os.getenv("BINANCE_API_SECRET"),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True
            }
        })

    async def execute_order(self, pair: str, side: str, amount: float, order_type: str = 'market'):
        """Execute market order with risk checks"""
        try:
            # Get current price for amount validation
            ticker = await self.exchange.fetch_ticker(pair)
            min_notional = self.get_min_notional(pair)
            
            # Calculate notional value
            notional = amount * ticker['last']
            
            if notional < min_notional:
                raise ValueError(f"Order size too small. Minimum: {min_notional:.2f} USDT")
            
            return await self.exchange.create_order(
                symbol=pair,
                type=order_type,
                side=side,
                amount=amount,
                params={'test': os.getenv("TEST_MODE", False)}  # Safety flag
            )
        except ccxt.InsufficientFunds as e:
            logging.error(f"Insufficient funds: {str(e)}")
            raise
        except ccxt.InvalidOrder as e:
            logging.error(f"Invalid order: {str(e)}")
            raise

    def get_min_notional(self, pair: str):
        """Get exchange minimum order requirements"""
        market = self.exchange.market(pair)
        return float(market['info']['filters'][3]['minNotional'])

class CryptoBot(BinanceTradeManager):
    """Enhanced trading bot with integrated Binance execution"""
    def __init__(self):
        super().__init__()
        self.app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
        self.active_orders = {}
        
        # Register handlers
        self.app.add_handler(CommandHandler("start", self.start_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Safety checks
        if not os.getenv("TEST_MODE", False):
            logging.warning("RUNNING IN LIVE TRADING MODE!")

    async def handle_trade_action(self, query, action: str):
        """Enhanced order handling with confirmation"""
        user_id = query.from_user.id
        pair = self.active_orders.get(user_id, {}).get('pair')
        
        if not pair:
            await query.message.reply_text("⚠️ No active pair selected!")
            return

        # Get order details from user
        await query.message.reply_text(f"Enter {action} amount for {pair}:")
        self.user_states[user_id] = {'action': action, 'pair': pair}

    async def process_trade_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process trade execution with amount validation"""
        user_id = update.message.from_user.id
        state = self.user_states.get(user_id)
        
        if not state:
            return

        try:
            amount = float(update.message.text)
            pair = state['pair']
            
            # Execute order
            order = await self.execute_order(
                pair=pair,
                side=state['action'],
                amount=amount
            )
            
            # Format response
            msg = (
                f"✅ {state['action'].capitalize()} Order Executed!\n"
                f"• Pair: {pair}\n"
                f"• Amount: {amount:.4f}\n"
                f"• Price: {order['price']:.2f}\n"
                f"• Cost: {float(order['cost']):.2f} USDT"
            )
            
            await update.message.reply_text(msg)
            
            # Store order details
            self.active_orders[user_id] = {
                'id': order['id'],
                'pair': pair,
                'side': state['action'],
                'amount': amount,
                'timestamp': pd.Timestamp.now()
            }
            
        except ValueError as e:
            await update.message.reply_text(f"⚠️ Invalid amount: {str(e)}")
        except Exception as e:
            await update.message.reply_text(f"🚨 Trade failed: {str(e)}")
        finally:
            self.user_states.pop(user_id, None)

    # Add this to your existing message handler
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_states.get(update.message.from_user.id, {}).get('action'):
            await self.process_trade_amount(update, context)
        else:
            # Existing message handling logic
            ...

    # Add order confirmation buttons
    async def show_order_confirmation(self, user_id: int, pair: str):
        """Show trade confirmation dialog"""
        keyboard = [
            [InlineKeyboardButton("Confirm Buy", callback_data=f"confirm_buy_{pair}"),
             InlineKeyboardButton("Confirm Sell", callback_data=f"confirm_sell_{pair}")],
            [InlineKeyboardButton("Cancel", callback_data="cancel_trade")]
        ]
        
        await self.app.bot.send_message(
            chat_id=user_id,
            text=f"⚠️ Confirm trade for {pair}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Enhanced button handler
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("confirm_"):
            action, pair = query.data.split("_")[1], query.data.split("_")[2]
            await self.handle_confirmed_trade(query, action, pair)
        elif query.data == "cancel_trade":
            await query.message.edit_text("❌ Trade canceled")
        else:
            # Existing button handling logic
            ...

    async def handle_confirmed_trade(self, query, action: str, pair: str):
        """Execute confirmed trade"""
        try:
            # Get cached amount from previous state
            user_id = query.from_user.id
            amount = self.user_states[user_id].get('amount')
            
            if not amount:
                raise ValueError("No trade amount specified")
            
            order = await self.execute_order(pair, action, amount)
            await query.message.edit_text(
                f"✅ {action.capitalize()} order executed successfully!\n"
                f"• ID: {order['id']}\n"
                f"• Executed: {order['filled']} {pair.split('/')[0]}\n"
                f"• Avg. Price: {order['average']:.2f}"
            )
        except Exception as e:
            await query.message.edit_text(f"🚨 Trade execution failed: {str(e)}")

# Keep all the TA and charting logic from previous implementation
# Add risk management features below

class RiskManager:
    """Add this to your existing bot class"""
    MAX_DAILY_LOSS = 0.02  # 2% of portfolio
    MAX_POSITION_SIZE = 0.1  # 10% per trade
    
    async def check_risk_parameters(self, user_id: int, amount: float, pair: str):
        # Get portfolio balance
        balance = await self.exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        
        # Get position size in USDT
        ticker = await self.exchange.fetch_ticker(pair)
        position_size = amount * ticker['last']
        
        # Check max position size
        if position_size > usdt_balance * self.MAX_POSITION_SIZE:
            raise ValueError(
                f"Position size exceeds {self.MAX_POSITION_SIZE*100}% of portfolio"
            )
        
        # Check daily loss limit (implement your own tracking)
        if self.daily_pnl(user_id) < -abs(usdt_balance * self.MAX_DAILY_LOSS):
            raise ValueError("Daily loss limit reached")
        
        return True

# Add to your execute_order method
# await self.check_risk_parameters(user_id, amount, pair)
