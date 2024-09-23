import os
import telebot
import requests
import time
import threading
import matplotlib.pyplot as plt
from io import BytesIO
import difflib  # For fuzzy matching
from telebot.types import InlineQueryResultArticle, InputTextMessageContent
from cachetools import TTLCache  # For caching
from matplotlib.ticker import MultipleLocator

# Use Agg backend for non-GUI rendering to avoid issues with threads
import matplotlib
matplotlib.use('Agg')

# Load environment variables for security (ensure you have TELEGRAM_TOKEN and COINMARKETCAP_API_KEY set)
# You can use a .env file and the python-dotenv package for this
TELEGRAM_TOKEN = '7762094310:AAEL1GgKxThWNxMPfm2NGkpSjw2wlE39W_g'
COINMARKETCAP_API_KEY = '404342be-32e0-4649-b77e-64de96f58225'

if not TELEGRAM_TOKEN or not COINMARKETCAP_API_KEY:
    raise ValueError("Please set the TELEGRAM_TOKEN and COINMARKETCAP_API_KEY environment variables.")

# Initialize the bot object using the token before defining any handlers
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Dictionaries to store user settings and price tracking for each user
user_settings = {}
price_history = {}  # To store price history for generating graphs
notification_count = {}  # To track number of notifications sent per user

# Cache for API responses
price_cache = TTLCache(maxsize=1000, ttl=300)  # Cache prices for 5 minutes
crypto_list_cache = TTLCache(maxsize=1, ttl=3600)  # Cache crypto list for 1 hour

# Lock for thread-safe operations
lock = threading.Lock()

# Supported languages
LANGUAGES = ['en', 'ru']

# Translations dictionary
translations = {
    'en': {
        'welcome': (
            "👋 *Welcome to the Crypto Price Bot!*\n\n"
            "*How to Use:*\n"
            "1. 🔎 *Search Currency*: Find and add cryptocurrencies to your watchlist.\n"
            "2. ⏲️ *Set Interval*: Set the frequency (in minutes) for price updates.\n"
            "3. 👁️ *Show Selected*: View the list of cryptocurrencies you are tracking.\n"
            "4. ❌ *Delete Token*: Remove a cryptocurrency from your watchlist.\n"
            "5. 📊 *Request Graph*: Get the price history graph of your selected cryptocurrencies.\n"
            "6. 🛑 *Stop Updates*: Stop receiving updates and clear your data.\n\n"
            "You can change the language anytime by sending /language."
        ),
        'choose_language': "🌐 *Please choose your language:*",
        'language_set': "✅ *Language set to English.*",
        'search_currency_prompt': "🔎 *Enter the symbol or name of the cryptocurrency:*",
        'set_interval_prompt': "⏲️ *Enter the update interval in minutes (e.g., 120 for 2 hours):*",
        'invalid_input': "❌ Invalid input. Please try again.",
        'currency_added': "✅ *{crypto}* has been added to your monitoring list.",
        'currency_exists': "⚠️ *{crypto}* is already in your list.",
        'no_currencies_selected': "ℹ️ You have not selected any cryptocurrencies yet.",
        'selected_currencies': "👁️ *Selected Currencies:* {currencies}",
        'delete_token_prompt': "❌ *Select a token to delete:*",
        'token_deleted': "❌ *{crypto}* removed from your list.",
        'token_not_found': "⚠️ *{crypto}* not found in your list.",
        'updates_stopped': "🛑 Updates stopped and all your data has been cleared.",
        'price_not_available': "⚠️ *{crypto}*: Price not available",
        'price_difference': "📉 *Price Differences Since Last Update:*",
        'no_previous_data': "ℹ️ *{crypto}*: No previous data to calculate difference.",
        'alert_set': "⏰ Alert set for *{crypto}* at ${price:,.2f}",
        'alert_triggered': "🚨 *{crypto}* has reached your alert price of ${price:,.2f}!",
        'enter_alert': "❌ Usage: /set_alert SYMBOL PRICE",
        'invalid_price': "❌ Invalid price. Please enter a numeric value.",
        'language_prompt': "🌐 *Choose your language:*",
        'language_changed': "✅ *Language changed successfully.*",
        'invalid_option': "❓ Invalid option. Please select an action from the menu.",
        'not_enough_data': "ℹ️ Not enough data to generate a graph. Please wait for more price updates."
    },
    'ru': {
        'welcome': (
            "👋 *Добро пожаловать в Crypto Price Bot!*\n\n"
            "*Как использовать:*\n"
            "1. 🔎 *Поиск валюты*: Найдите и добавьте криптовалюты в свой список отслеживания.\n"
            "2. ⏲️ *Установить интервал*: Задайте частоту (в минутах) для обновлений цен.\n"
            "3. 👁️ *Показать выбранные*: Просмотрите список криптовалют, которые вы отслеживаете.\n"
            "4. ❌ *Удалить токен*: Удалите криптовалюту из вашего списка отслеживания.\n"
            "5. 📊 *Запросить график*: Получите график истории цен выбранных криптовалют.\n"
            "6. 🛑 *Остановить обновления*: Прекратите получать обновления и очистите ваши данные.\n\n"
            "Вы можете изменить язык в любое время, отправив /language."
        ),
        'choose_language': "🌐 *Пожалуйста, выберите язык:*",
        'language_set': "✅ *Язык установлен на русский.*",
        'search_currency_prompt': "🔎 *Введите символ или название криптовалюты:*",
        'set_interval_prompt': "⏲️ *Введите интервал обновления в минутах (например, 120 для 2 часов):*",
        'invalid_input': "❌ Неверный ввод. Пожалуйста, попробуйте снова.",
        'currency_added': "✅ *{crypto}* добавлен в ваш список наблюдения.",
        'currency_exists': "⚠️ *{crypto}* уже есть в вашем списке.",
        'no_currencies_selected': "ℹ️ Вы еще не выбрали ни одной криптовалюты.",
        'selected_currencies': "👁️ *Выбранные валюты:* {currencies}",
        'delete_token_prompt': "❌ *Выберите токен для удаления:*",
        'token_deleted': "❌ *{crypto}* удален из вашего списка.",
        'token_not_found': "⚠️ *{crypto}* не найден в вашем списке.",
        'updates_stopped': "🛑 Обновления остановлены, и все ваши данные были очищены.",
        'price_not_available': "⚠️ *{crypto}*: Цена недоступна",
        'price_difference': "📉 *Изменения цен с момента последнего обновления:*",
        'no_previous_data': "ℹ️ *{crypto}*: Нет предыдущих данных для расчета разницы.",
        'alert_set': "⏰ Уведомление установлено для *{crypto}* на ${price:,.2f}",
        'alert_triggered': "🚨 *{crypto}* достиг вашей установленной цены ${price:,.2f}!",
        'enter_alert': "❌ Использование: /set_alert SYMBOL PRICE",
        'invalid_price': "❌ Неверная цена. Пожалуйста, введите числовое значение.",
        'language_prompt': "🌐 *Пожалуйста, выберите язык:*",
        'language_changed': "✅ *Язык успешно изменен.*",
        'invalid_option': "❓ Неверный вариант. Пожалуйста, выберите действие из меню.",
        'not_enough_data': "ℹ️ Недостаточно данных для создания графика. Пожалуйста, подождите больше обновлений цен."
    }
}

# Function to get user's language
def get_user_language(chat_id):
    return user_settings.get(chat_id, {}).get('language', 'en')

# Function to get translated text
def tr(chat_id, text_key, **kwargs):
    language = get_user_language(chat_id)
    text = translations.get(language, translations['en']).get(text_key, '')
    return text.format(**kwargs)

# Function to get all cryptocurrencies
def get_all_cryptos():
    if 'all_cryptos' in crypto_list_cache:
        return crypto_list_cache['all_cryptos']
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': COINMARKETCAP_API_KEY,
    }
    try:
        response = requests.get('https://pro-api.coinmarketcap.com/v1/cryptocurrency/map', headers=headers)
        data = response.json()
        cryptos = [{'symbol': item['symbol'], 'name': item['name']} for item in data['data']]
        crypto_list_cache['all_cryptos'] = cryptos
        return cryptos
    except Exception as e:
        print(f"Error fetching cryptos: {e}")
        return []

# Main menu with custom keyboard
def generate_menu(chat_id):
    language = get_user_language(chat_id)
    if language == 'ru':
        buttons = [
            "🔎 Поиск валюты",
            "⏲️ Установить интервал",
            "👁️ Показать выбранные",
            "❌ Удалить токен",
            "📊 Запросить график",
            "🛑 Остановить обновления"
        ]
    else:
        buttons = [
            "🔎 Search Currency",
            "⏲️ Set Interval",
            "👁️ Show Selected",
            "❌ Delete Token",
            "📊 Request Graph",
            "🛑 Stop Updates"
        ]
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*buttons)
    return markup

# Start command with language selection
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('English', 'Русский')
    msg = bot.send_message(message.chat.id, tr(message.chat.id, 'language_prompt'), reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, set_language_start)

def set_language_start(message):
    lang_choice = message.text.strip().lower()
    if lang_choice in ['english', 'английский']:
        language = 'en'
    elif lang_choice in ['русский', 'russian', 'русский']:
        language = 'ru'
    else:
        language = 'en'  # Default to English
    with lock:
        user_settings[message.chat.id] = {
            'language': language,
            'currencies': [],
            'interval': 120,
            'last_prices': {},
            'alerts': {}
        }
    bot.send_message(message.chat.id, tr(message.chat.id, 'language_set'), reply_markup=generate_menu(message.chat.id), parse_mode="Markdown")
    bot.send_message(message.chat.id, tr(message.chat.id, 'welcome'), parse_mode="Markdown", reply_markup=generate_menu(message.chat.id))

# Command to change language
@bot.message_handler(commands=['language'])
def change_language(message):
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('English', 'Русский')
    msg = bot.send_message(message.chat.id, tr(message.chat.id, 'language_prompt'), reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, set_language)

def set_language(message):
    lang_choice = message.text.strip().lower()
    if lang_choice in ['english', 'английский']:
        language = 'en'
    elif lang_choice in ['русский', 'russian', 'русский']:
        language = 'ru'
    else:
        language = 'en'  # Default to English
    with lock:
        user_settings[message.chat.id]['language'] = language
    bot.send_message(message.chat.id, tr(message.chat.id, 'language_changed'), reply_markup=generate_menu(message.chat.id), parse_mode="Markdown")

# Message handler for main menu buttons
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    text = message.text.strip()
    language = get_user_language(message.chat.id)

    # Map text to actions based on language
    if language == 'ru':
        options = {
            "🔎 Поиск валюты": 'search_currency',
            "⏲️ Установить интервал": 'set_interval',
            "👁️ Показать выбранные": 'show_selected',
            "❌ Удалить токен": 'delete_token',
            "📊 Запросить график": 'request_graph',
            "🛑 Остановить обновления": 'stop_updates'
        }
    else:
        options = {
            "🔎 Search Currency": 'search_currency',  # Corrected this line
            "⏲️ Set Interval": 'set_interval',
            "👁️ Show Selected": 'show_selected',
            "❌ Delete Token": 'delete_token',
            "📊 Request Graph": 'request_graph',
            "🛑 Stop Updates": 'stop_updates'
        }

    action = options.get(text, None)

    if action == 'search_currency':
        msg = bot.send_message(message.chat.id, tr(message.chat.id, 'search_currency_prompt'), parse_mode="Markdown")
        bot.register_next_step_handler(msg, search_currency)
    elif action == 'set_interval':
        msg = bot.send_message(message.chat.id, tr(message.chat.id, 'set_interval_prompt'), parse_mode="Markdown")
        bot.register_next_step_handler(msg, set_interval)
    elif action == 'show_selected':
        show_selected_currencies(message)
    elif action == 'delete_token':
        delete_token(message)
    elif action == 'request_graph':
        send_price_history(message.chat.id)
    elif action == 'stop_updates':
        stop_updates(message)
    else:
        bot.send_message(message.chat.id, tr(message.chat.id, 'invalid_option'), reply_markup=generate_menu(message.chat.id))
# Function to search and add a cryptocurrency with fuzzy search and pagination
def search_currency(message):
    query = message.text.strip().upper()
    if not query:
        bot.send_message(message.chat.id, tr(message.chat.id, 'invalid_input'))
        return

    cryptos = get_all_cryptos()
    # Use difflib for fuzzy matching
    matches = difflib.get_close_matches(query, [crypto['symbol'].upper() for crypto in cryptos] + [crypto['name'].upper() for crypto in cryptos], n=50, cutoff=0.1)
    matched_cryptos = [crypto for crypto in cryptos if crypto['symbol'].upper() in matches or crypto['name'].upper() in matches]

    if not matched_cryptos:
        bot.send_message(message.chat.id, tr(message.chat.id, 'invalid_input'))
        return

    # Implement pagination
    page_size = 5
    pages = [matched_cryptos[i:i + page_size] for i in range(0, len(matched_cryptos), page_size)]
    current_page = 0

    def send_page(page_index):
        if page_index < 0 or page_index >= len(pages):
            bot.send_message(message.chat.id, tr(message.chat.id, 'invalid_input'))
            return
        page = pages[page_index]
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        for crypto in page:
            btn_text = f"{crypto['symbol']} - {crypto['name']}"
            markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"select_{crypto['symbol']}"))
        # Pagination buttons
        pagination_buttons = []
        if page_index > 0:
            pagination_buttons.append(telebot.types.InlineKeyboardButton("⬅️", callback_data=f"page_{page_index - 1}"))
        if page_index < len(pages) - 1:
            pagination_buttons.append(telebot.types.InlineKeyboardButton("➡️", callback_data=f"page_{page_index + 1}"))
        if pagination_buttons:
            markup.add(*pagination_buttons)
        bot.send_message(message.chat.id, tr(message.chat.id, 'search_currency_prompt'), parse_mode="Markdown", reply_markup=markup)

    send_page(current_page)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
    def pagination_handler(call):
        page_index = int(call.data.split("_")[1])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_page(page_index)

# Callback handler for selecting a cryptocurrency to add
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
def select_currency(call):
    crypto_symbol = call.data.split("_")[1].upper()
    with lock:
        if call.message.chat.id not in user_settings:
            user_settings[call.message.chat.id] = {
                'language': 'en',
                'currencies': [],
                'interval': 120,  # default 120 minutes (2 hours)
                'last_prices': {},
                'alerts': {}
            }
        if crypto_symbol not in user_settings[call.message.chat.id]['currencies']:
            user_settings[call.message.chat.id]['currencies'].append(crypto_symbol)
            user_settings[call.message.chat.id]['last_prices'][crypto_symbol] = None  # Initialize last price as None
            price_history.setdefault(call.message.chat.id, {}).setdefault(crypto_symbol, [])
            bot.answer_callback_query(call.id, tr(call.message.chat.id, 'currency_added', crypto=crypto_symbol))
        else:
            bot.answer_callback_query(call.id, tr(call.message.chat.id, 'currency_exists', crypto=crypto_symbol))
    # Refresh the menu or provide further instructions
    bot.send_message(call.message.chat.id, tr(call.message.chat.id, 'currency_added', crypto=crypto_symbol), parse_mode="Markdown", reply_markup=generate_menu(call.message.chat.id))

# Function to set update interval
def set_interval(message):
    input_text = message.text.strip()
    if not input_text.isdigit():
        bot.send_message(message.chat.id, tr(message.chat.id, 'invalid_input'))
        return

    interval = int(input_text)
    if interval < 1:
        bot.send_message(message.chat.id, tr(message.chat.id, 'invalid_input'))
        return

    with lock:
        if message.chat.id not in user_settings:
            user_settings[message.chat.id] = {
                'language': 'en',
                'currencies': [],
                'interval': interval,
                'last_prices': {},
                'alerts': {}
            }
        else:
            user_settings[message.chat.id]['interval'] = interval
    bot.send_message(message.chat.id, tr(message.chat.id, 'language_changed'), parse_mode="Markdown", reply_markup=generate_menu(message.chat.id))

# Function to show selected cryptocurrencies
def show_selected_currencies(message):
    with lock:
        if message.chat.id in user_settings and user_settings[message.chat.id]['currencies']:
            currencies = ", ".join(user_settings[message.chat.id]['currencies'])
            bot.send_message(message.chat.id, tr(message.chat.id, 'selected_currencies', currencies=currencies), parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, tr(message.chat.id, 'no_currencies_selected'), parse_mode="Markdown")

# Function to delete a selected cryptocurrency
def delete_token(message):
    with lock:
        if message.chat.id in user_settings and user_settings[message.chat.id]['currencies']:
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)  # Uniform button sizes
            for crypto in user_settings[message.chat.id]['currencies']:
                markup.add(telebot.types.InlineKeyboardButton(crypto, callback_data=f"delete_{crypto}"))
            bot.send_message(message.chat.id, tr(message.chat.id, 'delete_token_prompt'), parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, tr(message.chat.id, 'no_currencies_selected'), parse_mode="Markdown")

# Callback handler for deleting a cryptocurrency
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_selected_token(call):
    crypto = call.data.split("_")[1].upper()
    with lock:
        if call.message.chat.id in user_settings and crypto in user_settings[call.message.chat.id]['currencies']:
            user_settings[call.message.chat.id]['currencies'].remove(crypto)
            # Optionally remove last price
            if crypto in user_settings[call.message.chat.id]['last_prices']:
                del user_settings[call.message.chat.id]['last_prices'][crypto]
            # Optionally remove price history
            if call.message.chat.id in price_history and crypto in price_history[call.message.chat.id]:
                del price_history[call.message.chat.id][crypto]
            bot.answer_callback_query(call.id, tr(call.message.chat.id, 'token_deleted', crypto=crypto))
        else:
            bot.answer_callback_query(call.id, tr(call.message.chat.id, 'token_not_found', crypto=crypto))
    # Refresh the delete menu
    delete_token(call.message)

# Function to stop updates
def stop_updates(message):
    with lock:
        if message.chat.id in user_settings:
            del user_settings[message.chat.id]
        if message.chat.id in price_history:
            del price_history[message.chat.id]
        if message.chat.id in notification_count:
            del notification_count[message.chat.id]
    bot.send_message(message.chat.id, tr(message.chat.id, 'updates_stopped'), reply_markup=generate_menu(message.chat.id))

# Function to fetch current crypto price with caching
def get_crypto_price(crypto):
    if crypto in price_cache:
        return price_cache[crypto]
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': COINMARKETCAP_API_KEY,
    }
    params = {
        'symbol': crypto.upper(),
        'convert': 'USD'
    }
    try:
        response = requests.get('https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest', headers=headers, params=params)
        data = response.json()
        if 'data' in data and crypto.upper() in data['data']:
            price = data['data'][crypto.upper()]['quote']['USD']['price']
            price_cache[crypto] = price
            return price
        else:
            print(f"Error: Unexpected response structure for {crypto}.")
            return None
    except Exception as e:
        print(f"Error fetching price for {crypto}: {e}")
        return None

# Function to generate and send combined price history graph
def send_price_history(chat_id):
    with lock:
        user_currencies = user_settings.get(chat_id, {}).get('currencies', [])
        user_history = price_history.get(chat_id, {})

    if not user_currencies:
        bot.send_message(chat_id, tr(chat_id, 'no_currencies_selected'), parse_mode="Markdown")
        return  # No currencies to plot

    plt.figure(figsize=(10, 6))
    plotted = False

    for crypto in user_currencies:
        history_prices = user_history.get(crypto, [])
        if len(history_prices) < 2:
            continue  # Not enough data to plot
        if not all(isinstance(price, (int, float)) for price in history_prices):
            continue  # Invalid price data
        plt.plot(history_prices, marker='o', label=crypto)
        plotted = True

    if not plotted:
        bot.send_message(chat_id, tr(chat_id, 'not_enough_data'), parse_mode="Markdown")
        return  # No valid data to plot

    plt.title('Cryptocurrency Price History')
    plt.xlabel('Data Points')
    plt.ylabel('Price (USD)')
    plt.legend()
    plt.tight_layout()

    # Set y-axis ticks every $10
    ax = plt.gca()
    y_min, y_max = ax.get_ylim()
    ax.yaxis.set_major_locator(MultipleLocator(10))
    # Adjust y-limits to nearest multiples of 10
    y_min = 10 * (int(y_min) // 10)
    y_max = 10 * ((int(y_max) // 10) + 1)
    ax.set_ylim(y_min, y_max)

    # Optionally, add grid lines for better readability
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    bot.send_photo(chat_id, buf)

# Function to generate and send price difference message
def send_price_differences(chat_id, differences):
    if not differences:
        return  # No differences to send

    message_lines = [tr(chat_id, 'price_difference')]
    for crypto, diff in differences.items():
        if diff['last_price'] is None:
            message_lines.append(tr(chat_id, 'no_previous_data', crypto=crypto))
            continue
        price_change = diff['current_price'] - diff['last_price']
        percent_change = (price_change / diff['last_price']) * 100 if diff['last_price'] != 0 else 0
        if price_change > 0:
            emoji = "📈"
        elif price_change < 0:
            emoji = "📉"
        else:
            emoji = "➖"
        message_lines.append(f"{emoji} *{crypto}*: {'+' if price_change >=0 else ''}${price_change:,.2f} ({'+' if percent_change >=0 else ''}{percent_change:.2f}%)")

    message = "\n".join(message_lines)
    bot.send_message(chat_id, message, parse_mode="Markdown")

# Background thread for sending price updates
def price_update_loop():
    while True:
        with lock:
            users = list(user_settings.keys())
        for chat_id in users:
            with lock:
                settings = user_settings.get(chat_id, {})
                currencies = settings.get('currencies', [])
                interval = settings.get('interval', 120)
                count = notification_count.get(chat_id, 0) + 1
                notification_count[chat_id] = count
            if not currencies:
                continue
            price_messages = []
            differences = {}
            for crypto in currencies:
                price = get_crypto_price(crypto)
                if price is not None:
                    price_messages.append(f"📈 *{crypto}*: ${price:,.2f}")
                    # Calculate difference
                    with lock:
                        last_price = settings['last_prices'].get(crypto)
                        differences[crypto] = {
                            'current_price': price,
                            'last_price': last_price
                        }
                        # Update last price
                        user_settings[chat_id]['last_prices'][crypto] = price
                        # Update price history
                        price_history.setdefault(chat_id, {}).setdefault(crypto, []).append(price)
                else:
                    price_messages.append(tr(chat_id, 'price_not_available', crypto=crypto))
            message = "\n".join(price_messages)
            bot.send_message(chat_id, message, parse_mode="Markdown")
            # Send differences
            send_price_differences(chat_id, differences)
            # Check if it's time to send a graph automatically every 7 notifications
            if count % 7 == 0:
                send_price_history(chat_id)
            # Check for price alerts
            check_price_alerts(chat_id, differences)
        # Sleep based on the smallest interval among users
        time.sleep(60)

# Function to check for price alerts
def check_price_alerts(chat_id, differences):
    with lock:
        alerts = user_settings[chat_id].get('alerts', {})
    for crypto, diff in differences.items():
        alert_price = alerts.get(crypto)
        if alert_price is not None:
            current_price = diff['current_price']
            if current_price >= alert_price:
                bot.send_message(chat_id, tr(chat_id, 'alert_triggered', crypto=crypto, price=alert_price), parse_mode="Markdown")
                # Remove alert
                with lock:
                    del user_settings[chat_id]['alerts'][crypto]

# Inline query handler for quick price lookup
@bot.inline_handler(func=lambda query: len(query.query.strip()) > 0)
def inline_query_handler(query):
    cryptos = get_all_cryptos()
    query_text = query.query.strip().upper()
    matches = difflib.get_close_matches(query_text, [crypto['symbol'].upper() for crypto in cryptos], n=10, cutoff=0.3)
    results = []
    for crypto in cryptos:
        if crypto['symbol'].upper() in matches:
            price = get_crypto_price(crypto['symbol'])
            if price is not None:
                content = InputTextMessageContent(f"*{crypto['symbol']}* - {crypto['name']}\nPrice: ${price:,.2f}", parse_mode='Markdown')
                result = InlineQueryResultArticle(id=crypto['symbol'], title=f"{crypto['symbol']} - ${price:,.2f}", input_message_content=content)
                results.append(result)
    bot.answer_inline_query(query.id, results)

# Command to set price alerts
@bot.message_handler(commands=['set_alert'])
def set_price_alert(message):
    parts = message.text.strip().split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, tr(message.chat.id, 'enter_alert'))
        return
    symbol = parts[1].upper()
    try:
        price = float(parts[2])
    except ValueError:
        bot.send_message(message.chat.id, tr(message.chat.id, 'invalid_price'))
        return
    with lock:
        if message.chat.id not in user_settings:
            user_settings[message.chat.id] = {
                'language': 'en',
                'currencies': [],
                'interval': 120,
                'last_prices': {},
                'alerts': {}
            }
        user_settings[message.chat.id]['alerts'][symbol] = price
    bot.send_message(message.chat.id, tr(message.chat.id, 'alert_set', crypto=symbol, price=price), parse_mode="Markdown")

# Start the background thread
threading.Thread(target=price_update_loop, daemon=True).start()

# Polling to keep the bot running
bot.infinity_polling()
