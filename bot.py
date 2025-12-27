import os
import json
import logging
import asyncio
import pickle
import base64
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import uuid
import io
import hashlib

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from telegram.constants import ParseMode

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("8379260877:AAHFpHyQ160STBAl_wA0iNN7-S6x5ZMB2hY")
ADMIN_PASSWORD = os.getenv("killer123")
ADMIN_CHAT_ID = int(os.getenv("1728951776"))
DATABASE_CHAT_ID = int(os.getenv("7445817691"))

# Twitter Account Price
TWITTER_PRICE = 5 # 5₹ per account

# Conversation states
WAITING_FOR_QR, WAITING_FOR_PAYMENT_VERIFICATION, WAITING_FOR_TWITTER_DETAILS = range(3)

# ==================== CHAT DATABASE SYSTEM ====================
class ChatDatabase:
    def __init__(self, bot=None):
        self.bot = bot
        self.data = {
            'users': {},
            'twitter_stock': [],
            'transactions': [],
            'payments': [],
            'admin_settings': {},
            'used_twitter_accounts': set(),
            'admins': [ADMIN_CHAT_ID]  # Default admin list
        }
        self.load_from_chat()
    
    async def save_to_chat(self, context):
        """Save database to chat as encoded message"""
        try:
            # Convert data to JSON and then encode
            data_str = json.dumps(self.data, default=str)
            encoded_data = base64.b64encode(data_str.encode()).decode()
            
            # Save to chat
            await context.bot.send_message(
                chat_id=DATABASE_CHAT_ID,
                text=f"📊 DATABASE BACKUP\nTime: {datetime.now()}\n\n{encoded_data}"
            )
            return True
        except Exception as e:
            logging.error(f"Error saving to chat: {e}")
            return False
    
    async def load_from_chat(self):
        """Load database from chat"""
        try:
            if not self.bot:
                return
            
            # Get messages from database chat
            messages = []
            async for message in self.bot.get_chat_history(chat_id=DATABASE_CHAT_ID, limit=50):
                if "DATABASE BACKUP" in message.text:
                    messages.append(message)
            
            if messages:
                # Get the latest backup
                latest = messages[0]
                lines = latest.text.split('\n')
                for line in lines:
                    if line and not line.startswith("📊") and "Time:" not in line:
                        try:
                            decoded_data = base64.b64decode(line.encode()).decode()
                            loaded_data = json.loads(decoded_data)
                            # Update self.data with loaded data
                            for key in loaded_data:
                                self.data[key] = loaded_data[key]
                            
                            # Ensure default admin is always in list
                            if ADMIN_CHAT_ID not in self.data['admins']:
                                self.data['admins'].append(ADMIN_CHAT_ID)
                            
                            # Convert used_twitter_accounts back to set
                            if 'used_twitter_accounts' in self.data:
                                self.data['used_twitter_accounts'] = set(self.data['used_twitter_accounts'])
                            logging.info("Database loaded from chat successfully")
                            break
                        except Exception as e:
                            logging.error(f"Error decoding data: {e}")
                            continue
        except Exception as e:
            logging.error(f"Error loading from chat: {e}")
    
    def get_user(self, user_id: int):
        """Get user from database"""
        return self.data['users'].get(str(user_id))
    
    def create_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Create new user if not exists"""
        if str(user_id) not in self.data['users']:
            self.data['users'][str(user_id)] = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'balance': 0.0,
                'total_spent': 0.0,
                'total_purchases': 0,
                'join_date': str(datetime.now()),
                'last_active': str(datetime.now())
            }
            return True
        return False
    
    def is_admin(self, user_id: int):
        """Check if user is admin"""
        return user_id in self.data['admins']
    
    def add_admin(self, user_id: int, added_by: int):
        """Add new admin"""
        if user_id not in self.data['admins']:
            self.data['admins'].append(user_id)
            return True
        return False
    
    def remove_admin(self, user_id: int):
        """Remove admin"""
        if user_id in self.data['admins'] and user_id != ADMIN_CHAT_ID:
            self.data['admins'].remove(user_id)
            return True
        return False
    
    def get_all_admins(self):
        """Get all admin IDs"""
        return self.data['admins']
    
    def update_twitter_price(self, new_price: float):
        """Update Twitter account price"""
        self.data['admin_settings']['twitter_price'] = new_price
        return True
    
    def get_twitter_price(self):
        """Get current Twitter account price"""
        return self.data['admin_settings'].get('twitter_price', TWITTER_PRICE)
    
    def update_balance(self, user_id: int, amount: float, add: bool = True):
        """Update user balance"""
        user = self.get_user(user_id)
        if user:
            if add:
                user['balance'] += amount
            else:
                user['balance'] -= amount
            return True
        return False
    
    def add_twitter_account(self, username: str, password: str, email: str, added_by: int):
        """Add Twitter account to stock"""
        account_id = len(self.data['twitter_stock']) + 1
        account = {
            'id': account_id,
            'username': username,
            'password': password,
            'email': email,
            'added_by': added_by,
            'added_date': str(datetime.now()),
            'sold_to': None,
            'sold_date': None,
            'is_sold': False
        }
        self.data['twitter_stock'].append(account)
        
        # Save to chat details
        self.save_twitter_details_to_chat(username, password, email)
        return account_id
    
    def save_twitter_details_to_chat(self, username: str, password: str, email: str):
        """Save Twitter details to chat as separate message"""
        try:
            # This would be called from admin commands
            # The actual sending happens in the handler
            pass
        except:
            pass
    
    def get_available_twitter_count(self):
        """Get count of available Twitter accounts"""
        return sum(1 for acc in self.data['twitter_stock'] if not acc['is_sold'])
    
    def get_twitter_accounts(self, limit: int = 20):
        """Get available Twitter accounts"""
        available = [acc for acc in self.data['twitter_stock'] if not acc['is_sold']]
        return available[:limit]
    
    def purchase_twitter_account(self, user_id: int, quantity: int):
        """Purchase Twitter accounts for user"""
        available_accounts = [acc for acc in self.data['twitter_stock'] if not acc['is_sold']]
        
        if len(available_accounts) < quantity:
            return None
        
        purchased_accounts = []
        current_price = self.get_twitter_price()
        
        for i in range(quantity):
            account = available_accounts[i]
            account['sold_to'] = user_id
            account['sold_date'] = str(datetime.now())
            account['is_sold'] = True
            purchased_accounts.append(account.copy())
            
            # Mark as used
            self.data['used_twitter_accounts'].add(account['username'])
        
        # Update user stats
        user = self.get_user(user_id)
        total_price = quantity * current_price
        
        if user:
            user['balance'] -= total_price
            user['total_spent'] += total_price
            user['total_purchases'] += quantity
        
        # Create transaction record
        transaction_id = f"TWITTER_{user_id}_{int(datetime.now().timestamp())}"
        transaction = {
            'transaction_id': transaction_id,
            'user_id': user_id,
            'amount': total_price,
            'type': 'purchase_twitter',
            'status': 'completed',
            'details': f"Purchased {quantity} Twitter accounts @ ₹{current_price} each",
            'created_at': str(datetime.now()),
            'completed_at': str(datetime.now())
        }
        self.data['transactions'].append(transaction)
        
        return purchased_accounts
    
    def create_payment(self, payment_id: str, user_id: int):
        """Create payment record"""
        payment = {
            'payment_id': payment_id,
            'user_id': user_id,
            'amount': None,
            'utr': None,
            'status': 'pending',
            'qr_sent': True,
            'created_at': str(datetime.now()),
            'verified_at': None,
            'verified_by': None
        }
        self.data['payments'].append(payment)
        return payment
    
    def update_payment_utr(self, payment_id: str, utr: str):
        """Update payment with UTR"""
        for payment in self.data['payments']:
            if payment['payment_id'] == payment_id:
                payment['utr'] = utr
                payment['status'] = 'pending_verification'
                return True
        return False
    
    def verify_payment(self, payment_id: str, amount: float, verified_by: int):
        """Verify a payment"""
        for payment in self.data['payments']:
            if payment['payment_id'] == payment_id:
                payment['status'] = 'verified'
                payment['amount'] = amount
                payment['verified_at'] = str(datetime.now())
                payment['verified_by'] = verified_by
                
                # Update user balance
                self.update_balance(payment['user_id'], amount)
                
                # Create transaction record
                transaction_id = f"PAYMENT_{payment['user_id']}_{int(datetime.now().timestamp())}"
                transaction = {
                    'transaction_id': transaction_id,
                    'user_id': payment['user_id'],
                    'amount': amount,
                    'type': 'add_funds',
                    'status': 'completed',
                    'details': f"Payment via UTR: {payment.get('utr', 'N/A')}",
                    'created_at': str(datetime.now()),
                    'completed_at': str(datetime.now())
                }
                self.data['transactions'].append(transaction)
                return True
        return False
    
    def get_admin_setting(self, key: str):
        """Get admin setting"""
        return self.data['admin_settings'].get(key)
    
    def set_admin_setting(self, key: str, value: str):
        """Set admin setting"""
        self.data['admin_settings'][key] = value
        return True
    
    def get_statistics(self):
        """Get bot statistics"""
        user_count = len(self.data['users'])
        total_balance = sum(user['balance'] for user in self.data['users'].values())
        total_sales = sum(t['amount'] for t in self.data['transactions'] if t['type'] == 'purchase_twitter')
        total_stock = len(self.data['twitter_stock'])
        sold_stock = sum(1 for acc in self.data['twitter_stock'] if acc['is_sold'])
        available_stock = total_stock - sold_stock
        admin_count = len(self.data['admins'])
        current_price = self.get_twitter_price()
        
        recent_transactions = sorted(
            self.data['transactions'],
            key=lambda x: x.get('created_at', ''),
            reverse=True
        )[:10]
        
        return {
            'user_count': user_count,
            'total_balance': total_balance,
            'total_sales': total_sales,
            'total_stock': total_stock,
            'sold_stock': sold_stock,
            'available_stock': available_stock,
            'admin_count': admin_count,
            'current_price': current_price,
            'recent_transactions': recent_transactions
        }
    
    def get_all_users(self):
        """Get all user IDs"""
        return [int(user_id) for user_id in self.data['users'].keys()]

# Initialize database (will be set after bot is initialized)
db = None

# ==================== HELPER FUNCTIONS ====================
async def save_to_database_chat(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Send data to database chat for storage"""
    try:
        await context.bot.send_message(
            chat_id=DATABASE_CHAT_ID,
            text=text,
            parse_mode=ParseMode.MARKDOWN
        )
        return True
    except Exception as e:
        logging.error(f"Error saving to database chat: {e}")
        return False

async def save_database_backup(context: ContextTypes.DEFAULT_TYPE):
    """Save entire database to chat"""
    if db:
        await db.save_to_chat(context)

def generate_qr_code(data: str):
    """Generate QR code image"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def create_main_menu():
    """Create main menu keyboard"""
    keyboard = [
        [KeyboardButton("💰 Add Funds"), KeyboardButton("🐦 Buy Twitter")],
        [KeyboardButton("📊 Check Balance"), KeyboardButton("📦 Stock")],
        [KeyboardButton("📞 Contact")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def create_twitter_quantity_menu():
    """Create Twitter quantity selection menu"""
    keyboard = []
    for i in range(0, 20, 4):
        row = []
        for j in range(1, 5):
            if i + j <= 20:
                row.append(InlineKeyboardButton(f"Twitter {i+j}", callback_data=f"buy_twitter_{i+j}"))
        if row:
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

# ==================== BOT COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    db.create_user(user.id, user.username, user.first_name, user.last_name)
    
    # Save user details to database chat
    await save_to_database_chat(context, f"""
👤 NEW USER REGISTERED
User ID: `{user.id}`
Username: @{user.username}
Name: {user.first_name} {user.last_name or ''}
Time: {datetime.now()}
    """)
    
    current_price = db.get_twitter_price()
    
    welcome_message = f"""
👋 Welcome *{user.first_name}* to Twitter Accounts Bot!

*Available Commands:*
• Use buttons below to navigate
• Each Twitter account: *₹{current_price}*

*Main Features:*
💰 *Add Funds* - Add money to your account
🐦 *Buy Twitter* - Purchase Twitter accounts
📊 *Check Balance* - View your balance & history
📦 *Stock* - Check available accounts
📞 *Contact* - Get help & support
    """
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=create_main_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages (button clicks)"""
    text = update.message.text
    
    if text == "💰 Add Funds":
        await add_funds(update, context)
    elif text == "🐦 Buy Twitter":
        await buy_twitter_menu(update, context)
    elif text == "📊 Check Balance":
        await check_balance(update, context)
    elif text == "📦 Stock":
        await check_stock(update, context)
    elif text == "📞 Contact":
        await contact_us(update, context)

# ==================== BUTTON FUNCTION HANDLERS ====================
async def add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Add Funds button"""
    # Check if QR is set
    qr_image_id = db.get_admin_setting('qr_image')
    
    if not qr_image_id:
        await update.message.reply_text(
            "❌ Payment QR is not set up yet. Please contact admin.",
            reply_markup=create_main_menu()
        )
        return
    
    # Generate payment ID
    payment_id = f"PAY_{update.effective_user.id}_{int(datetime.now().timestamp())}"
    
    # Create payment record
    db.create_payment(payment_id, update.effective_user.id)
    
    keyboard = [[InlineKeyboardButton("✅ Check Payment", callback_data=f"check_payment_{payment_id}")]]
    
    await update.message.reply_photo(
        photo=qr_image_id,
        caption=f"""
💳 *Add Funds*

*Payment ID:* `{payment_id}`
*Instructions:*
1. Scan QR code to pay
2. Click 'Check Payment' below
3. Enter UTR/Transaction ID

*Note:* Minimum deposit ₹10
        """,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Save to database chat
    await save_to_database_chat(context, f"""
💸 PAYMENT INITIATED
User ID: `{update.effective_user.id}`
Payment ID: `{payment_id}`
Time: {datetime.now()}
Status: Pending
    """)

async def buy_twitter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Twitter quantity selection menu"""
    available = db.get_available_twitter_count()
    current_price = db.get_twitter_price()
    
    if available == 0:
        await update.message.reply_text(
            "❌ No Twitter accounts available in stock.\nPlease wait 24 hours or contact admin.",
            reply_markup=create_main_menu()
        )
        return
    
    message = f"""
🐦 *Buy Twitter Accounts*

*Available in stock:* {available} accounts
*Price:* ₹{current_price} per account

Select quantity to purchase:
    """
    
    if update.message:
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_twitter_quantity_menu()
        )
    else:
        await update.callback_query.message.edit_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_twitter_quantity_menu()
        )

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Check Balance button"""
    user = db.get_user(update.effective_user.id)
    
    if not user:
        await update.message.reply_text(
            "❌ User not found. Please use /start first.",
            reply_markup=create_main_menu()
        )
        return
    
    # Get user transactions
    user_transactions = [
        t for t in db.data['transactions'] 
        if t['user_id'] == user['user_id']
    ]
    recent_transactions = sorted(
        user_transactions,
        key=lambda x: x.get('created_at', ''),
        reverse=True
    )[:5]
    
    # Format transactions
    trans_text = "\n".join([
        f"• {t['type'].replace('_', ' ').title()}: ₹{t['amount']} ({t['status']})"
        for t in recent_transactions
    ]) if recent_transactions else "No transactions yet"
    
    current_price = db.get_twitter_price()
    
    message = f"""
📊 *Your Account Details*

*User ID:* `{user['user_id']}`
*Username:* @{user['username'] or 'N/A'}
*Balance:* *₹{user['balance']:.2f}*
*Total Spent:* ₹{user['total_spent']:.2f}
*Total Purchases:* {user['total_purchases']} accounts
*Member Since:* {user['join_date']}

*Recent Transactions:*
{trans_text}

*Note:* 1 Twitter account = ₹{current_price}
    """
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=create_main_menu()
    )

async def check_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Stock button"""
    available = db.get_available_twitter_count()
    current_price = db.get_twitter_price()
    
    message = f"""
📦 *Stock Information*

*Twitter Accounts Available:* {available}
*Price per account:* ₹{current_price}
*Status:* {'✅ In Stock' if available > 0 else '❌ Out of Stock'}

{'*Note:* Stock updates automatically when admin adds new accounts.' if available > 0 else '*Note:* Please wait 24 hours for stock update or contact admin.'}
    """
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=create_main_menu()
    )

async def contact_us(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Contact button"""
    message = """
📞 *Contact & Support*

Hi dear,

If you need any help, have any queries, or face any issues, please DM me:

👉 *@KILLERxVIPP*

I will help you resolve your problems as soon as possible.

*Common Issues:*
• Payment verification
• Account delivery
• Balance issues
• Technical problems

*Response Time:* Usually within 1-2 hours
    """
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=create_main_menu()
    )

# ==================== CALLBACK QUERY HANDLERS ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "main_menu":
        await query.message.delete()
        await query.message.reply_text(
            "Main Menu",
            reply_markup=create_main_menu()
        )
    
    elif data.startswith("buy_twitter_"):
        quantity = int(data.split("_")[2])
        await purchase_twitter_accounts(query, context, quantity)
    
    elif data.startswith("check_payment_"):
        payment_id = data.split("_")[2]
        await verify_payment(query, context, payment_id)

async def purchase_twitter_accounts(query, context, quantity: int):
    """Process Twitter account purchase"""
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    current_price = db.get_twitter_price()
    total_price = quantity * current_price
    
    # Check balance
    if user['balance'] < total_price:
        await query.message.edit_text(
            f"""
❌ *Insufficient Balance*

*Required:* ₹{total_price}
*Your Balance:* ₹{user['balance']:.2f}
*Short by:* ₹{total_price - user['balance']:.2f}

Please add funds first.
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Add Funds", callback_data="main_menu")]
            ])
        )
        return
    
    # Check stock
    available = db.get_available_twitter_count()
    if available < quantity:
        await query.message.edit_text(
            f"""
❌ *Insufficient Stock*

*Requested:* {quantity} accounts
*Available:* {available} accounts
*Short by:* {quantity - available} accounts

Please wait 24 hours or reduce quantity.
            """,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Process purchase
    purchased_accounts = db.purchase_twitter_account(user_id, quantity)
    
    if not purchased_accounts:
        await query.message.edit_text(
            "❌ Purchase failed. Please try again.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Save purchase to database chat
    account_details = []
    for acc in purchased_accounts:
        account_details.append(f"Username: {acc['username']} | Pass: {acc['password']} | Email: {acc['email']}")
    
    await save_to_database_chat(context, f"""
🐦 TWITTER ACCOUNTS SOLD
━━━━━━━━━━━━━━━━━━━━━━
👤 User: {user_id} (@{user['username']})
📦 Quantity: {quantity} accounts
💰 Total: ₹{total_price}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
Accounts Sold:
{chr(10).join(account_details)}
━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    # Send success message
    await query.message.edit_text(
        f"""
✅ *Purchase Successful!*

*Quantity:* {quantity} Twitter accounts
*Amount Paid:* ₹{total_price}
*New Balance:* ₹{user['balance']:.2f}
*Transaction Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*Your accounts will be sent in the next message...*
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send accounts individually
    for i, acc in enumerate(purchased_accounts, 1):
        account_message = f"""
🐦 *Twitter Account {i}/{quantity}*

*Username:* `{acc['username']}`
*Password:* `{acc['password']}`
*Email:* `{acc['email']}`

*Instructions:*
1. Login at twitter.com
2. Change password immediately
3. Enable 2FA for security

*Note:* This account is for one-time use only
        """
        await context.bot.send_message(
            chat_id=user_id,
            text=account_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    await context.bot.send_message(
        chat_id=user_id,
        text=f"🎉 All {quantity} accounts delivered! Thank you for your purchase.",
        reply_markup=create_main_menu()
    )

async def verify_payment(query, context, payment_id):
    """Handle payment verification"""
    await query.message.reply_text(
        f"""
✅ *Payment Verification*

Please send your *UTR/Transaction ID* for payment verification.

*Payment ID:* `{payment_id}`
*Format:* Send UTR as a message

Example: `123456789012345`
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Store payment ID in context for next message
    context.user_data['awaiting_utr'] = payment_id

# ==================== PAYMENT VERIFICATION HANDLER ====================
async def handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle UTR input for payment verification"""
    if 'awaiting_utr' not in context.user_data:
        return
    
    payment_id = context.user_data['awaiting_utr']
    utr = update.message.text.strip()
    
    # Validate UTR format
    if not utr.isdigit() or len(utr) < 10:
        await update.message.reply_text(
            "❌ Invalid UTR format. Please enter a valid numeric UTR/Transaction ID.",
            reply_markup=create_main_menu()
        )
        del context.user_data['awaiting_utr']
        return
    
    # Update payment record with UTR
    db.update_payment_utr(payment_id, utr)
    
    # Save to database chat
    user = update.effective_user
    await save_to_database_chat(context, f"""
💳 PAYMENT UTR RECEIVED
━━━━━━━━━━━━━━━━━━━━━━
👤 User: {user.id} (@{user.username})
📋 Payment ID: `{payment_id}`
🔢 UTR: `{utr}`
⏰ Time: {datetime.now()}
🔄 Status: Pending Verification
━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    await update.message.reply_text(
        f"""
✅ *UTR Received*

*Payment ID:* `{payment_id}`
*UTR:* `{utr}`

Your payment is under verification. This usually takes 2-5 minutes.

*If payment is not received:* Click Retry
*If payment is deducted but not credited:* Contact @KILLERxVIPP
        """,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Retry Payment", callback_data=f"check_payment_{payment_id}")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="main_menu")]
        ])
    )
    
    # Notify admin
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"""
🔔 *New Payment Verification Request*

*User:* {user.first_name} (@{user.username})
*User ID:* `{user.id}`
*Payment ID:* `{payment_id}`
*UTR:* `{utr}`
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*To verify:* Check payment and use /verify {payment_id} <amount>
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    del context.user_data['awaiting_utr']

# ==================== ADMIN COMMANDS ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /adminpanel command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adminpanel <password>")
        return
    
    password = context.args[0]
    if password != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Invalid password.")
        return
    
    current_price = db.get_twitter_price()
    admin_guide = f"""
🔐 *Admin Panel Activated*

*Available Commands:*

1. *Update QR Code:*
   `/updateqr` - Upload QR code image as reply

2. *Set PayTM Details:*
   `/valid <merchant_id> <merchant_key> <website>`
   Example: `/valid YOUR_MID YOUR_KEY WEBSTAGING`

3. *Add Twitter Stock:*
   `/addtw <username> <password> <email>`
   Example: `/addtw user123 pass123 user@email.com`

4. *Add Funds to User:*
   `/tfund <user_id> <amount>`
   Example: `/tfund 123456789 1000`

5. *View Statistics:*
   `/statics` - View all statistics

6. *Verify Payment:*
   `/verify <payment_id> <amount>`
   Example: `/verify PAY_12345_67890 500`

7. *Save Database Backup:*
   `/backup` - Force save database backup

8. *Add New Admin:*
   `/newadmin <user_id>`
   Example: `/newadmin 123456789`
   *Only admins can use this command*

9. *Change Twitter Price:*
   `/prchange <new_price>`
   Example: `/prchange 5`
   Current Price: ₹{current_price}

10. *Broadcast Message:*
    `/broadcast <message>`
    Example: `/broadcast Hello users!`
    *Send message to all users*

*Admin Panel will remain active for this session.*
    """
    
    await update.message.reply_text(
        admin_guide,
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== NEW ADMIN FEATURES ====================
async def add_new_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /newadmin command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access. Only admins can use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /newadmin <user_id>\nExample: /newadmin 123456789")
        return
    
    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")
        return
    
    # Check if user exists
    user = db.get_user(new_admin_id)
    if not user:
        await update.message.reply_text("❌ User not found. User must have used /start at least once.")
        return
    
    # Check if already admin
    if db.is_admin(new_admin_id):
        await update.message.reply_text("❌ User is already an admin.")
        return
    
    # Add as admin
    success = db.add_admin(new_admin_id, update.effective_user.id)
    
    if success:
        # Save to database chat
        await save_to_database_chat(context, f"""
👑 NEW ADMIN ADDED
━━━━━━━━━━━━━━━━━━━━━━
🆔 New Admin ID: {new_admin_id}
👤 Username: @{user['username'] or 'N/A'}
👨‍💼 Added by: {update.effective_user.id}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
        """)
        
        await update.message.reply_text(
            f"""
✅ *New Admin Added Successfully!*

*User ID:* `{new_admin_id}`
*Username:* @{user['username'] or 'N/A'}
*Name:* {user['first_name']} {user['last_name'] or ''}
*Added by:* {update.effective_user.id}

*Note:* New admin can now access admin panel and add other admins.
            """,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Notify the new admin
        try:
            await context.bot.send_message(
                chat_id=new_admin_id,
                text=f"""
🎉 *You have been promoted to Admin!*

Congratulations! You have been added as an admin by {update.effective_user.id}.

*Admin Privileges:*
• Access admin panel with `/adminpanel {ADMIN_PASSWORD}`
• Add/remove Twitter accounts
• Verify payments
• Add other admins
• Change Twitter price
• Broadcast messages

*Total Admins:* {len(db.get_all_admins())}

Use `/adminpanel {ADMIN_PASSWORD}` to access admin panel.
                """,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Error notifying new admin: {e}")
        
        # Save database backup
        await save_database_backup(context)
    else:
        await update.message.reply_text("❌ Failed to add admin. Please try again.")

async def change_twitter_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /prchange command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access. Only admins can use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /prchange <new_price>\nExample: /prchange 5")
        return
    
    try:
        new_price = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Please provide a valid number.")
        return
    
    if new_price <= 0:
        await update.message.reply_text("❌ Price must be greater than 0.")
        return
    
    old_price = db.get_twitter_price()
    
    # Update price
    db.update_twitter_price(new_price)
    
    # Save to database chat
    await save_to_database_chat(context, f"""
💰 TWITTER PRICE CHANGED
━━━━━━━━━━━━━━━━━━━━━━
👨‍💼 Changed by: {update.effective_user.id}
📈 Old Price: ₹{old_price}
📉 New Price: ₹{new_price}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    await update.message.reply_text(
        f"""
✅ *Twitter Price Updated!*

*Old Price:* ₹{old_price}
*New Price:* ₹{new_price}
*Changed by:* {update.effective_user.id}

*Note:* This change will affect all future purchases.
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Save database backup
    await save_database_backup(context)

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access. Only admins can use this command.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /broadcast <message>\nExample: /broadcast Hello users!")
        return
    
    message = ' '.join(context.args)
    all_users = db.get_all_users()
    
    if not all_users:
        await update.message.reply_text("❌ No users found in database.")
        return
    
    await update.message.reply_text(
        f"""
📢 *Broadcast Started*

*Message:* {message}
*Total Users:* {len(all_users)}
*Started by:* {update.effective_user.id}
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Sending messages to all users...
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Save to database chat
    await save_to_database_chat(context, f"""
📢 BROADCAST MESSAGE
━━━━━━━━━━━━━━━━━━━━━━
👨‍💼 Sent by: {update.effective_user.id}
👥 Total Users: {len(all_users)}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
Message: {message}
━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    # Send to all users
    success_count = 0
    fail_count = 0
    
    for user_id in all_users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"""
📢 *Announcement from Admin*

{message}

*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_This is an automated broadcast message._
                """,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Error sending broadcast to {user_id}: {e}")
            fail_count += 1
    
    # Send report
    await update.message.reply_text(
        f"""
✅ *Broadcast Completed!*

*Message:* {message}
*Total Users:* {len(all_users)}
*Successful:* {success_count}
*Failed:* {fail_count}
*Completion Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*Note:* Failed messages may be due to users blocking the bot.
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Save database backup
    await save_database_backup(context)

# ==================== EXISTING ADMIN COMMANDS (UPDATED) ====================
async def update_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /updateqr command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    await update.message.reply_text(
        "📤 Please upload the QR code image as a photo."
    )
    return WAITING_FOR_QR

async def receive_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save QR code"""
    if not db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    if update.message.photo:
        # Get the largest photo
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Save to database
        db.set_admin_setting('qr_image', file_id)
        
        # Save to database chat
        await save_to_database_chat(context, f"""
🏦 PAYMENT QR UPDATED
━━━━━━━━━━━━━━━━━━━━━━
🆔 File ID: `{file_id}`
👤 Updated by: {update.effective_user.id}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
        """)
        
        await update.message.reply_text(
            "✅ QR code updated successfully!",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ Please send a photo (QR code image)."
        )
    
    # Save database backup
    await save_database_backup(context)
    return ConversationHandler.END

async def set_paytm_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /valid command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    if len(context.args) != 3:
        await update.message.reply_text(
            "Usage: /valid <merchant_id> <merchant_key> <website>\n"
            "Example: /valid YOUR_MID YOUR_KEY WEBSTAGING"
        )
        return
    
    merchant_id, merchant_key, website = context.args
    
    # Save to database
    db.set_admin_setting('merchant_id', merchant_id)
    db.set_admin_setting('merchant_key', merchant_key)
    db.set_admin_setting('paytm_website', website)
    
    # Save to database chat (without exposing full key)
    masked_key = merchant_key[:10] + "..." if len(merchant_key) > 10 else "***"
    await save_to_database_chat(context, f"""
🏦 PAYTM DETAILS UPDATED
━━━━━━━━━━━━━━━━━━━━━━
🆔 Merchant ID: `{merchant_id}`
🔑 Merchant Key: `{masked_key}`
🌐 Website: {website}
👤 Updated by: {update.effective_user.id}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    await update.message.reply_text(
        "✅ PayTM details updated successfully!\n"
        "Details have been approved and saved.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Save database backup
    await save_database_backup(context)

async def add_twitter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addtw command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    if len(context.args) != 3:
        await update.message.reply_text(
            "Usage: /addtw <username> <password> <email>\n"
            "Example: /addtw user123 pass123 user@email.com"
        )
        return
    
    username, password, email = context.args
    
    # Check if username already exists
    existing_accounts = [acc for acc in db.data['twitter_stock'] if acc['username'] == username]
    if existing_accounts:
        await update.message.reply_text("❌ This Twitter username already exists in stock.")
        return
    
    # Add to stock
    account_id = db.add_twitter_account(username, password, email, update.effective_user.id)
    
    # Save Twitter details to database chat
    await save_to_database_chat(context, f"""
🐦 TWITTER ACCOUNT ADDED
━━━━━━━━━━━━━━━━━━━━━━
🆔 Account ID: {account_id}
👤 Username: `{username}`
🔑 Password: `{password}`
📧 Email: `{email}`
👨‍💼 Added by: {update.effective_user.id}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    available_count = db.get_available_twitter_count()
    
    await update.message.reply_text(
        f"""
✅ Twitter account added to stock!

*Username:* `{username}`
*Password:* `{password}`
*Email:* `{email}`

*Total available in stock:* {available_count} accounts
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Save database backup
    await save_database_backup(context)

async def transfer_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tfund command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /tfund <user_id> <amount>\n"
            "Example: /tfund 123456789 1000"
        )
        return
    
    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount.")
        return
    
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("❌ User not found.")
        return
    
    # Add funds
    db.update_balance(user_id, amount)
    
    # Create transaction record
    transaction_id = f"ADMIN_{user_id}_{int(datetime.now().timestamp())}"
    transaction = {
        'transaction_id': transaction_id,
        'user_id': user_id,
        'amount': amount,
        'type': 'admin_add_funds',
        'status': 'completed',
        'details': f"Admin added funds",
        'created_at': str(datetime.now()),
        'completed_at': str(datetime.now())
    }
    db.data['transactions'].append(transaction)
    
    # Save to database chat
    await save_to_database_chat(context, f"""
💰 ADMIN FUND TRANSFER
━━━━━━━━━━━━━━━━━━━━━━
👤 To User: {user_id}
👨‍💼 Admin: {update.effective_user.id}
💵 Amount: ₹{amount}
🆔 Transaction ID: `{transaction_id}`
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    await update.message.reply_text(
        f"""
✅ Funds transferred successfully!

*User ID:* `{user_id}`
*Username:* @{user['username'] or 'N/A'}
*Amount Added:* ₹{amount}
*New Balance:* ₹{user['balance']:.2f}
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Notify user
    await context.bot.send_message(
        chat_id=user_id,
        text=f"""
🎉 *Funds Added by Admin*

*Amount:* ₹{amount}
*New Balance:* ₹{user['balance']:.2f}
*Transaction ID:* `{transaction_id}`
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Thank you for using our service!
        """,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Save database backup
    await save_database_backup(context)

async def verify_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verify command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /verify <payment_id> <amount>\n"
            "Example: /verify PAY_12345_67890 500"
        )
        return
    
    payment_id = context.args[0]
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return
    
    # Verify payment
    success = db.verify_payment(payment_id, amount, update.effective_user.id)
    
    if success:
        # Save to database chat
        await save_to_database_chat(context, f"""
✅ PAYMENT VERIFIED
━━━━━━━━━━━━━━━━━━━━━━
📋 Payment ID: `{payment_id}`
💵 Amount: ₹{amount}
👨‍💼 Verified by: {update.effective_user.id}
⏰ Time: {datetime.now()}
━━━━━━━━━━━━━━━━━━━━━━
        """)
        
        await update.message.reply_text(
            f"✅ Payment verified successfully! ₹{amount} added to user's account.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ Payment not found or already verified.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Save database backup
    await save_database_backup(context)

async def view_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /statics command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    stats = db.get_statistics()
    
    # Format recent transactions
    trans_text = "\n".join([
        f"• {t.get('user_id', 'N/A')}: ₹{t['amount']} ({t['type']})"
        for t in stats['recent_transactions']
    ]) if stats['recent_transactions'] else "No transactions"
    
    # Get all admins
    admins = db.get_all_admins()
    admin_text = "\n".join([f"• {admin_id}" for admin_id in admins])
    
    stats_message = f"""
📊 *Bot Statistics*

*Users:* {stats['user_count']}
*Total Balance:* ₹{stats['total_balance']:.2f}
*Total Sales:* ₹{stats['total_sales']:.2f}

*Twitter Stock:*
• Total: {stats['total_stock']} accounts
• Sold: {stats['sold_stock']} accounts
• Available: {stats['available_stock']} accounts
• Current Price: ₹{stats['current_price']}
• Value: ₹{stats['available_stock'] * stats['current_price']}

*Admins:* {stats['admin_count']}
{admin_text}

*Recent Transactions:*
{trans_text}

*PayTM Status:* {'✅ Configured' if db.get_admin_setting('merchant_id') else '❌ Not Configured'}
    """
    
    await update.message.reply_text(
        stats_message,
        parse_mode=ParseMode.MARKDOWN
    )

async def backup_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /backup command"""
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    
    await update.message.reply_text("💾 Saving database backup...")
    success = await save_database_backup(context)
    
    if success:
        await update.message.reply_text("✅ Database backup saved successfully!")
    else:
        await update.message.reply_text("❌ Failed to save database backup.")

# ==================== MAIN FUNCTION ====================
async def post_init(application: Application):
    """Initialize database after bot is created"""
    global db
    db = ChatDatabase(application.bot)
    # Try to load existing data from chat
    await db.load_from_chat()

def main():
    """Start the bot"""
    # Setup logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adminpanel", admin_panel))
    application.add_handler(CommandHandler("valid", set_paytm_details))
    application.add_handler(CommandHandler("addtw", add_twitter))
    application.add_handler(CommandHandler("tfund", transfer_funds))
    application.add_handler(CommandHandler("verify", verify_payment_command))
    application.add_handler(CommandHandler("statics", view_statistics))
    application.add_handler(CommandHandler("backup", backup_database))
    
    # Add new admin feature handlers
    application.add_handler(CommandHandler("newadmin", add_new_admin))
    application.add_handler(CommandHandler("prchange", change_twitter_price))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    
    # Add conversation handler for QR update
    qr_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("updateqr", update_qr)],
        states={
            WAITING_FOR_QR: [MessageHandler(filters.PHOTO, receive_qr)]
        },
        fallbacks=[]
    )
    application.add_handler(qr_conv_handler)
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\d+$'), handle_utr))
    
    # Start the bot
    print("🤖 Bot is starting...")
    print(f"📊 Database Chat ID: {DATABASE_CHAT_ID}")
    print(f"👑 Admin Chat ID: {ADMIN_CHAT_ID}")
    print(f"🔑 Default Admin ID: {ADMIN_CHAT_ID}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
