import telebot
from telebot import types
import random
import time
import json
import os
from threading import Timer

# Токен бота
TOKEN = '8019174987:AAFd_qG434htnd94mnCOZfd2ejD0hgTGUJk'
bot = telebot.TeleBot(TOKEN)

# Владелец и канал
OWNER_USERNAME = '@kyniks'
CHANNEL_USERNAME = '@werdoxz_wiinere'

# Файлы для хранения данных
DATA_FILE = 'bot_data.json'
USERNAME_CACHE_FILE = 'username_cache.json'
PROMO_FILE = 'promocodes.json'
MARKET_FILE = 'market_data.json'  # Новый файл для маркета

# Максимальная ставка
MAX_BET = 1000000
# Таймаут игры в секундах (5 минут)
GAME_TIMEOUT = 300
# Пароль администратора
ADMIN_PASSWORD = '18472843'

# Банковские параметры
BANK_INTEREST_RATE = 0.001          # 0.1% за период
BANK_INTEREST_INTERVAL = 24 * 60 * 60  # 24 часа (в секундах)

# Данные пользователей: {user_id: {'balance': int, 'game': {...}, 'referrals': int, 'referrer': int, 'banned': bool, 'bank': {...}, 'beavers': {}}}
users = {}
# Кэш username -> user_id
username_cache = {}
# Таймеры для игр
game_timers = {}
# Таймеры обновления краш-игры
crash_update_timers = {}
# Множество ID администраторов (в памяти)
admin_users = set()
# Промокоды: {code: {'amount': int, 'uses_left': int, 'created_by': str}}
promocodes = {}

# ====================== ДАННЫЕ МАРКЕТА ======================
# Доступные бобры (id: данные)
BEAVERS_DATA = {
    'las': {
        'name': 'bober las',
        'price': 125000,
        'total': 100,  # Всего доступно
        'sold': 0,      # Продано
        'rarity': 'Обычный',
        'description': 'Простой, но стильный бобёр. Любит собирать монетки.',
        'bonus': '+5% к доходу от рефералов'
    },
    'tuntun': {
        'name': 'bober tuntun',
        'price': 300000,
        'total': 75,
        'sold': 0,
        'rarity': 'Редкий',
        'description': 'Музыкальный бобёр. По ночам поёт серенады.',
        'bonus': '+10% к выигрышу в слотах'
    },
    'lotlot': {
        'name': 'boberlotlot',
        'price': 500000,
        'total': 50,
        'sold': 0,
        'rarity': 'Эпический',
        'description': 'Бобёр-путешественник. Побывал во всех казино мира.',
        'bonus': '+15% к шансу в русской рулетке'
    },
    'kredi': {
        'name': 'bober kredi',
        'price': 750000,
        'total': 35,
        'sold': 0,
        'rarity': 'Легендарный',
        'description': 'Банкир среди бобров. Умеет приумножать капитал.',
        'bonus': '+20% к банковским процентам'
    },
    'vanddos': {
        'name': 'bober vanddos',
        'price': 1000000,
        'total': 15,
        'sold': 0,
        'rarity': 'Мифический',
        'description': 'Древний бобёр-маг. Исполняет желания удачливых.',
        'bonus': '+25% к максимальной ставке и +30% к множителю краша'
    }
}

# Коллекции пользователей: {user_id: {'las': 0, 'tuntun': 0, ...}}
# Эти данные хранятся в users[user_id]['beavers']

# Коэффициенты для башни (уровень -> множитель)
TOWER_MULTIPLIERS = {
    1: 1.3,
    2: 2.1,
    3: 3.7,
    4: 4.55,
    5: 5.4,
    6: 6.21,
    7: 8.3
}

# Коэффициент для очка
BLACKJACK_MULTIPLIER = 1.87

# Символы для слотов и их веса (для реалистичности, но можно просто равновероятно)
SLOTS_SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '7️⃣', 'BAR']

# Таблица выплат для слотов (комбинация -> множитель)
SLOTS_PAYOUTS = {
    ('BAR', 'BAR', 'BAR'): 10,
    ('7️⃣', '7️⃣', '7️⃣'): 7,
    ('🍇', '🍇', '🍇'): 5,
    ('🍊', '🍊', '🍊'): 3,
    ('🍋', '🍋', '🍋'): 2,
    ('🍒', '🍒', '🍒'): 1.5
    # Два одинаковых - возврат ставки (обрабатывается отдельно)
}

# ====================== ДАННЫЕ ДЛЯ РУЛЕТКИ ======================
ROULETTE_NUMBERS = list(range(0, 37))
RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
BLACK_NUMBERS = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
ZERO = 0

# Множители для ставок в рулетке
ROULETTE_MULTIPLIERS = {
    'straight': 36,      # Ставка на число
    'red': 2,            # На красное
    'black': 2,          # На чёрное
    'even': 2,           # Чётное
    'odd': 2,            # Нечётное
    '1-18': 2,           # Меньше 19
    '19-36': 2,          # Больше 18
    'dozen': 3           # Дюжина (1-12, 13-24, 25-36)
}

# Загрузка данных из файлов
def load_data():
    global users, username_cache, promocodes
    # Загрузка пользователей
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
            # Конвертируем ключи в строки для единообразия
            users = {str(k): v for k, v in users.items()}
            # Добавляем поля, если отсутствуют
            for uid in users:
                if 'banned' not in users[uid]:
                    users[uid]['banned'] = False
                if 'bank' not in users[uid]:
                    users[uid]['bank'] = {'balance': 0, 'last_interest': time.time(), 'history': []}
                if 'beavers' not in users[uid]:  # Добавляем коллекцию бобров
                    users[uid]['beavers'] = {}
    
    # Загрузка кэша username'ов
    if os.path.exists(USERNAME_CACHE_FILE):
        with open(USERNAME_CACHE_FILE, 'r', encoding='utf-8') as f:
            username_cache = json.load(f)
    
    # Загрузка промокодов
    if os.path.exists(PROMO_FILE):
        with open(PROMO_FILE, 'r', encoding='utf-8') as f:
            promocodes = json.load(f)
    
    # Загружаем данные о продажах бобров из отдельного файла
    if os.path.exists(MARKET_FILE):
        with open(MARKET_FILE, 'r', encoding='utf-8') as f:
            market_data = json.load(f)
            # Восстанавливаем количество проданных бобров
            for beaver_id, data in market_data.get('beavers_sold', {}).items():
                if beaver_id in BEAVERS_DATA:
                    BEAVERS_DATA[beaver_id]['sold'] = data

# Сохранение данных в файлы
def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    
    with open(USERNAME_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(username_cache, f, ensure_ascii=False, indent=2)
    
    with open(PROMO_FILE, 'w', encoding='utf-8') as f:
        json.dump(promocodes, f, ensure_ascii=False, indent=2)
    
    # Сохраняем данные о продажах бобров
    market_data = {
        'beavers_sold': {bid: BEAVERS_DATA[bid]['sold'] for bid in BEAVERS_DATA}
    }
    with open(MARKET_FILE, 'w', encoding='utf-8') as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)

# Инициализация пользователя
def get_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            'balance': 1000,
            'game': None,
            'referrals': 0,
            'referrer': None,
            'banned': False,
            'bank': {'balance': 0, 'last_interest': time.time(), 'history': []},
            'beavers': {}  # Коллекция бобров
        }
        save_data()
    return users[user_id]

# Проверка, не забанен ли пользователь
def is_banned(user_id):
    user = get_user(user_id)
    return user.get('banned', False)

# Проверка, является ли пользователь админом
def is_admin(user_id):
    return str(user_id) in admin_users

# Обновление кэша username'ов
def update_username_cache(user_id, username):
    if username:
        username_cache[username.lower()] = str(user_id)
        save_data()

# Установка таймера на игру
def set_game_timer(user_id):
    user_id = str(user_id)
    # Отменяем предыдущий таймер, если был
    if user_id in game_timers:
        game_timers[user_id].cancel()
        time.sleep(0.1)  # Даём время на остановку
    
    # Создаём новый таймер
    timer = Timer(GAME_TIMEOUT, game_timeout, [user_id])
    timer.daemon = True
    game_timers[user_id] = timer
    timer.start()

def game_timeout(user_id):
    """Функция вызывается при таймауте игры"""
    try:
        user_id = str(user_id)
        # Останавливаем обновления краша, если они есть
        if user_id in crash_update_timers:
            crash_update_timers[user_id].cancel()
            del crash_update_timers[user_id]
        
        if user_id in users and users[user_id]['game'] is not None:
            game = users[user_id]['game']
            chat_id = game.get('chat_id', int(user_id))
            # Возвращаем ставку при таймауте
            if 'bet' in game:
                users[user_id]['balance'] += game['bet']
            users[user_id]['game'] = None
            save_data()
            bot.send_message(chat_id, 
                           "⏰ Время игры истекло. Ставка возвращена.\n"
                           "🔁 Используй меню чтобы начать заново.",
                           reply_markup=main_menu_keyboard())
    except Exception as e:
        print(f"Ошибка при таймауте игры: {e}")

# Клавиатура главного меню
def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🏰 Башня'),
        types.KeyboardButton('⚫️⚪️ Фишки'),
        types.KeyboardButton('🏀 Мячик'),
        types.KeyboardButton('🎲 X2/X3/X5'),
        types.KeyboardButton('🔫 Русская рулетка'),
        types.KeyboardButton('🃏 Очко (21)'),
        types.KeyboardButton('🚀 Краш'),
        types.KeyboardButton('🎰 Слоты'),
        types.KeyboardButton('🎲 Кости'),
        types.KeyboardButton('🎰 РУЛЕТКА'),  # Добавил рулетку
        types.KeyboardButton('💰 Баланс'),
        types.KeyboardButton('👥 Рефералы'),
        types.KeyboardButton('🏆 Топ'),
        types.KeyboardButton('🏦 Банк'),
        types.KeyboardButton('🦫 Маркет'),   # Добавил маркет
        types.KeyboardButton('❓ Помощь')
    )
    return markup

# ====================== ПОЛУЧЕНИЕ БОНУСОВ ОТ БОБРОВ ======================
def get_beaver_bonuses(user_id):
    """Возвращает словарь с бонусами от всех бобров пользователя"""
    user = get_user(user_id)
    beavers = user.get('beavers', {})
    bonuses = {
        'referral_bonus': 0,      # +% к доходу от рефералов
        'slots_bonus': 0,          # +% к выигрышу в слотах
        'roulette_bonus': 0,       # +% к шансу в русской рулетке
        'bank_interest_bonus': 0,  # +% к банковским процентам
        'max_bet_bonus': 0,        # +% к максимальной ставке
        'crash_mult_bonus': 0      # +% к множителю краша
    }
    
    for beaver_id, count in beavers.items():
        if count > 0 and beaver_id in BEAVERS_DATA:
            if beaver_id == 'las':
                bonuses['referral_bonus'] += 5 * count
            elif beaver_id == 'tuntun':
                bonuses['slots_bonus'] += 10 * count
            elif beaver_id == 'lotlot':
                bonuses['roulette_bonus'] += 15 * count
            elif beaver_id == 'kredi':
                bonuses['bank_interest_bonus'] += 20 * count
            elif beaver_id == 'vanddos':
                bonuses['max_bet_bonus'] += 25 * count
                bonuses['crash_mult_bonus'] += 30 * count
    
    return bonuses

def apply_beaver_bonuses(user_id, bet=None, game_type=None):
    """Применяет бонусы бобров к игре"""
    bonuses = get_beaver_bonuses(user_id)
    
    # Увеличиваем максимальную ставку
    effective_max_bet = MAX_BET * (1 + bonuses['max_bet_bonus'] / 100)
    
    # Для краша увеличиваем множитель
    crash_mult_bonus = 1 + bonuses['crash_mult_bonus'] / 100
    
    # Для слотов увеличиваем выигрыш
    slots_bonus = 1 + bonuses['slots_bonus'] / 100
    
    # Для русской рулетки увеличиваем шанс
    roulette_bonus = bonuses['roulette_bonus'] / 100  # добавляется к шансу
    
    return {
        'effective_max_bet': effective_max_bet,
        'crash_mult_bonus': crash_mult_bonus,
        'slots_bonus': slots_bonus,
        'roulette_bonus': roulette_bonus,
        'referral_bonus': bonuses['referral_bonus'],
        'bank_interest_bonus': bonuses['bank_interest_bonus']
    }

# ====================== АДМИН-КОМАНДЫ ======================
@bot.message_handler(commands=['admin'])
def admin_login(message):
    user_id = str(message.from_user.id)
    args = message.text.split()
    
    if len(args) != 2:
        bot.send_message(message.chat.id, "❌ Использование: /admin пароль")
        return
    
    if args[1] == ADMIN_PASSWORD:
        admin_users.add(user_id)
        bot.send_message(message.chat.id, 
                        "🔑✅ Вы вошли в режим администратора!\n\n"
                        "📋 Доступные команды:\n"
                        "➕ /addbalance @username сумма — начислить валюту\n"
                        "🚫 /ban @username — забанить игрока\n"
                        "✅ /unban @username — разбанить\n"
                        "🎟 /createpromo сумма [лимит] — создать промокод\n"
                        "📊 /adminstats — статистика бота\n"
                        "🚪 /admin_exit — выйти из админ-режима")
    else:
        bot.send_message(message.chat.id, "🔑❌ Неверный пароль!")

@bot.message_handler(commands=['admin_exit'])
def admin_exit(message):
    user_id = str(message.from_user.id)
    if user_id in admin_users:
        admin_users.remove(user_id)
        bot.send_message(message.chat.id, "👋 Вы вышли из режима администратора.")
    else:
        bot.send_message(message.chat.id, "❌ Вы не в режиме администратора.")

@bot.message_handler(commands=['addbalance'])
def add_balance(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ У вас нет прав администратора.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Использование: /addbalance @username сумма")
            return
        
        target_username = parts[1].replace('@', '').lower()
        amount = int(parts[2])
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть положительной.")
            return
        
        target_user = username_cache.get(target_username)
        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден.")
            return
        
        users[target_user]['balance'] += amount
        save_data()
        
        bot.send_message(message.chat.id, f"➕✅ Пользователю @{target_username} начислено {amount} кредитов.")
        try:
            bot.send_message(int(target_user), f"💰 Вам начислено {amount} кредитов администратором.")
        except:
            pass
    except ValueError:
        bot.send_message(message.chat.id, "❌ Сумма должна быть числом.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ У вас нет прав администратора.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Использование: /ban @username")
            return
        
        target_username = parts[1].replace('@', '').lower()
        target_user = username_cache.get(target_username)
        
        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден.")
            return
        
        if target_user == user_id:
            bot.send_message(message.chat.id, "❌ Нельзя забанить самого себя.")
            return
        
        users[target_user]['banned'] = True
        save_data()
        
        bot.send_message(message.chat.id, f"🔨✅ Пользователь @{target_username} забанен.")
        try:
            bot.send_message(int(target_user), "⛔ Вы были забанены администратором.")
        except:
            pass
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ У вас нет прав администратора.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Использование: /unban @username")
            return
        
        target_username = parts[1].replace('@', '').lower()
        target_user = username_cache.get(target_username)
        
        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден.")
            return
        
        users[target_user]['banned'] = False
        save_data()
        
        bot.send_message(message.chat.id, f"✅ Пользователь @{target_username} разбанен.")
        try:
            bot.send_message(int(target_user), "✅ Вы были разбанены администратором.")
        except:
            pass
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['createpromo'])
def create_promo(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ У вас нет прав администратора.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2 or len(parts) > 3:
            bot.send_message(message.chat.id, "❌ Использование: /createpromo сумма [лимит использований]")
            return
        
        amount = int(parts[1])
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть положительной.")
            return
        
        limit = int(parts[2]) if len(parts) == 3 else 1
        if limit <= 0:
            bot.send_message(message.chat.id, "❌ Лимит должен быть положительным.")
            return
        
        # Генерируем уникальный код
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        while code in promocodes:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        promocodes[code] = {
            'amount': amount,
            'uses_left': limit,
            'created_by': user_id
        }
        save_data()
        
        bot.send_message(message.chat.id, 
                        f"🎟✅ Промокод создан!\n"
                        f"🔑 Код: `{code}`\n"
                        f"💰 Сумма: {amount} кредитов\n"
                        f"📦 Лимит использований: {limit}",
                        parse_mode='Markdown')
    except ValueError:
        bot.send_message(message.chat.id, "❌ Сумма и лимит должны быть числами.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['promo'])
def use_promo(message):
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if is_banned(user_id):
        bot.send_message(message.chat.id, "⛔ Вы забанены и не можете использовать промокоды.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Использование: /promo код")
            return
        
        code = parts[1].upper()
        if code not in promocodes:
            bot.send_message(message.chat.id, "❌ Промокод не найден.")
            return
        
        promo = promocodes[code]
        if promo['uses_left'] <= 0:
            bot.send_message(message.chat.id, "❌ Промокод уже использован.")
            del promocodes[code]
            save_data()
            return
        
        # Начисляем валюту
        user['balance'] += promo['amount']
        promo['uses_left'] -= 1
        
        if promo['uses_left'] == 0:
            del promocodes[code]
        
        save_data()
        
        bot.send_message(message.chat.id, 
                        f"🎁✅ Промокод активирован! Вы получили {promo['amount']} кредитов.\n"
                        f"💰 Новый баланс: {user['balance']}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['adminstats'])
def admin_stats(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ У вас нет прав администратора.")
        return
    
    total_users = len(users)
    total_balance = sum(u['balance'] for u in users.values())
    total_bank = sum(u.get('bank', {}).get('balance', 0) for u in users.values())
    active_games = sum(1 for u in users.values() if u['game'] is not None)
    banned_count = sum(1 for u in users.values() if u.get('banned', False))
    total_promos = len(promocodes)
    
    # Статистика бобров
    total_beavers_sold = sum(b['sold'] for b in BEAVERS_DATA.values())
    total_beavers_revenue = sum(b['sold'] * b['price'] for b in BEAVERS_DATA.values())
    
    stats = (
        f"📊 **Статистика бота**\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Общий баланс: {total_balance} кредитов\n"
        f"🏦 Общий банк: {total_bank} кредитов\n"
        f"🎮 Активных игр: {active_games}\n"
        f"⛔ Забанено: {banned_count}\n"
        f"🎟 Активных промокодов: {total_promos}\n\n"
        f"🦫 **Маркет бобров**\n"
        f"📦 Продано бобров: {total_beavers_sold}\n"
        f"💵 Выручка: {total_beavers_revenue} кредитов"
    )
    bot.send_message(message.chat.id, stats, parse_mode='Markdown')

# ====================== ОСНОВНЫЕ КОМАНДЫ ======================

def get_help_text():
    return (
        "🕹 **Доступные игры:**\n\n"
        "🏰 **Башня:** выбираешь количество мин (1-4) и открываешь ячейки. "
        "За каждую безопасную ячейку множитель растёт. Можно остановиться и забрать выигрыш.\n\n"
        "⚫️⚪️ **Фишки:** угадай цвет. Шанс 50%, коэффициент x2.\n\n"
        "🏀 **Мячик:** кинь мяч. Попадание — x2.2, промах — проигрыш.\n\n"
        "🎲 **X2/X3/X5:** выбери множитель и испытай удачу!\n"
        "   • x2 — шанс 50%\n"
        "   • x3 — шанс 30%\n"
        "   • x5 — шанс 20%\n\n"
        "🔫 **Русская рулетка:** рискни! Шанс выжить 5/6, множитель x2.135\n\n"
        "🃏 **Очко (21):** игра против бота. Кто ближе к 21, не перебирая. Выигрыш x1.87.\n\n"
        "🚀 **Краш:** ракета взлетает, множитель растёт. Успей забрать выигрыш до взрыва! Макс. x10000.\n\n"
        "🎰 **Слоты:** классический однорукий бандит. Комбинации дают множители до x10.\n\n"
        "🎲 **Кости:** выбери тип ставки (число, чёт/нечет, больше/меньше 7) и испытай удачу.\n\n"
        "🎰 **РУЛЕТКА:** европейская рулетка. Ставки на числа, цвета, дюжины и т.д. Коэффициенты до x36!\n\n"
        "💰 **Баланс** — проверить счёт\n"
        "👥 **Рефералы** — получить ссылку для приглашения друзей\n"
        "🏆 **Топ** — лучшие игроки\n"
        "🏦 **Банк** — управление депозитом и проценты\n"
        "🦫 **Маркет** — магазин коллекционных бобров с бонусами\n\n"
        "💸 **Перевод валюты:** /give @username сумма\n"
        "🚫 **Отмена игры:** /cancel\n"
        "🎟 **Активировать промокод:** /promo код\n\n"
        f"👑 Владелец: {OWNER_USERNAME}\n📢 Канал: {CHANNEL_USERNAME}"
    )

# Команда /help
@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = str(message.from_user.id)
    if is_banned(user_id):
        bot.send_message(message.chat.id, "⛔ Вы забанены.")
        return
    bot.send_message(message.chat.id, get_help_text(), parse_mode='Markdown')

# Команда /start
@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = str(message.from_user.id)
    
    if is_banned(user_id):
        bot.send_message(message.chat.id, "⛔ Вы забанены и не можете использовать бота.")
        return
    
    args = message.text.split()
    
    # Обновляем кэш username
    if message.from_user.username:
        update_username_cache(message.from_user.id, message.from_user.username)
    
    # Реферальная система с учётом бонусов от бобров
    if len(args) > 1 and args[1].isdigit():
        referrer_id = args[1]
        if referrer_id != user_id:  # Нельзя пригласить самого себя
            user = get_user(user_id)
            if user['referrer'] is None:
                user['referrer'] = referrer_id
                # Начисляем бонус пригласившему (с учётом бонуса от бобров)
                if referrer_id in users:
                    bonuses = get_beaver_bonuses(referrer_id)
                    referral_bonus = 3000 * (1 + bonuses['referral_bonus'] / 100)
                    referral_bonus = int(referral_bonus)
                    
                    users[referrer_id]['balance'] += referral_bonus
                    users[referrer_id]['referrals'] += 1
                    try:
                        bot.send_message(int(referrer_id), 
                                       f"🎉 По твоей реферальной ссылке зарегистрировался новый пользователь! +{referral_bonus} кредитов (с учётом бонуса бобров)! 🎁")
                    except:
                        pass
                save_data()
    
    get_user(user_id)
    
    # Показываем количество бобров у пользователя
    beavers_count = sum(users[user_id].get('beavers', {}).values())
    
    bot.send_message(
        message.chat.id,
        f"👋 Добро пожаловать в игрового бота!\n\n"
        f"👑 Владелец: {OWNER_USERNAME}\n"
        f"📢 Канал: {CHANNEL_USERNAME}\n\n"
        f"💰 Твой текущий баланс: {users[user_id]['balance']} кредитов.\n"
        f"🦫 Коллекция бобров: {beavers_count} шт.\n"
        f"🎮 Выбери игру в меню ниже.",
        reply_markup=main_menu_keyboard()
    )

# Команда /balance
@bot.message_handler(commands=['balance'])
def balance_command(message):
    user_id = str(message.from_user.id)
    
    if is_banned(user_id):
        bot.send_message(message.chat.id, "⛔ Вы забанены.")
        return
    
    user = get_user(user_id)
    bank = user.get('bank', {'balance': 0})
    beavers_count = sum(user.get('beavers', {}).values())
    
    bot.send_message(message.chat.id, 
                    f"💰 Твой баланс: {user['balance']} кредитов.\n"
                    f"🏦 Банк: {bank['balance']} кредитов.\n"
                    f"🦫 Бобров в коллекции: {beavers_count}")

# Команда /give (передача валюты)
@bot.message_handler(commands=['give'])
def give_money(message):
    user_id = str(message.from_user.id)
    
    if is_banned(user_id):
        bot.send_message(message.chat.id, "⛔ Вы забанены.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Использование: /give @username сумма")
            return
        
        target_username = parts[1].replace('@', '').lower()
        amount = int(parts[2])
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть положительной.")
            return
        
        bonuses = get_beaver_bonuses(user_id)
        effective_max_bet = MAX_BET * (1 + bonuses['max_bet_bonus'] / 100)
        
        if amount > effective_max_bet:
            bot.send_message(message.chat.id, f"❌ Максимальная сумма перевода с твоими бобрами: {int(effective_max_bet)}")
            return
        
        # Поиск пользователя по username в кэше
        target_user = username_cache.get(target_username)
        
        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден или не начинал диалог с ботом.")
            return
        
        if target_user == user_id:
            bot.send_message(message.chat.id, "❌ Нельзя перевести средства самому себе.")
            return
        
        user = get_user(user_id)
        if user['balance'] < amount:
            bot.send_message(message.chat.id, f"❌ Недостаточно средств. Твой баланс: {user['balance']}")
            return
        
        # Переводим средства
        user['balance'] -= amount
        users[target_user]['balance'] += amount
        save_data()
        
        # Отправляем уведомления
        sender_name = f"@{message.from_user.username}" if message.from_user.username else f"ID {message.from_user.id}"
        bot.send_message(message.chat.id, f"✅ Ты перевёл {amount} кредитов пользователю @{target_username} 💸")
        
        try:
            bot.send_message(int(target_user), 
                           f"💰 Тебе перевели {amount} кредитов от {sender_name}\n"
                           f"💰 Текущий баланс: {users[target_user]['balance']}")
        except:
            pass
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Сумма должна быть числом.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# Команда /top
@bot.message_handler(commands=['top'])
def top_command(message):
    if is_banned(str(message.from_user.id)):
        bot.send_message(message.chat.id, "⛔ Вы забанены.")
        return
    show_top(message.chat.id)

# Команда /cancel для отмены текущей игры
@bot.message_handler(commands=['cancel'])
def cancel_game(message):
    user_id = str(message.from_user.id)
    
    if is_banned(user_id):
        bot.send_message(message.chat.id, "⛔ Вы забанены.")
        return
    
    user = get_user(user_id)
    
    # Останавливаем обновления краша, если они есть
    if user_id in crash_update_timers:
        crash_update_timers[user_id].cancel()
        del crash_update_timers[user_id]
    
    # Отменяем таймер игры
    if user_id in game_timers:
        game_timers[user_id].cancel()
        del game_timers[user_id]
    
    if user['game'] is not None:
        # Возвращаем ставку при отмене, если игра ещё не началась
        if user['game'].get('stage') == 'waiting_bet' and 'bet' in user['game']:
            user['balance'] += user['game']['bet']
        
        user['game'] = None
        save_data()
        bot.send_message(message.chat.id, 
                        "🛑 Текущая игра отменена. Ставка возвращена (если была).", 
                        reply_markup=main_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "У тебя нет активной игры.")

def show_top(chat_id):
    # Сортируем пользователей по балансу (конвертируем ID в строки для безопасности)
    sorted_users = sorted(
        [(str(k), v) for k, v in users.items()], 
        key=lambda x: x[1]['balance'], 
        reverse=True
    )[:10]
    
    if not sorted_users:
        bot.send_message(chat_id, "Пока нет пользователей в топе.")
        return
    
    text = "🏆 ТОП 10 ПО БАЛАНСУ:\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        try:
            user = bot.get_chat(int(uid))
            name = user.first_name
            if user.username:
                name = f"@{user.username}"
                # Обновляем кэш
                update_username_cache(int(uid), user.username)
        except:
            name = f"ID {uid}"
        
        beavers_count = sum(data.get('beavers', {}).values())
        text += f"{i}. 👤 {name} — 💰 {data['balance']} кредитов (🦫 {beavers_count})\n"
    
    bot.send_message(chat_id, text)

# Функция для генерации случайной карты (значение 2-11 с учётом частот)
def get_card():
    # 2-9: по 1, 10: 4 варианта (10, J, Q, K), 11: 1 (туз)
    values = list(range(2, 10)) + [10]*4 + [11]
    return random.choice(values)

# Функция для подсчёта суммы с учётом туза (упрощённо: туз всегда 11, если перебор, то проигрыш)
def calc_hand(hand):
    return sum(hand)

def hand_to_str(hand):
    cards = []
    for card in hand:
        if card == 11:
            cards.append('Т')
        elif card == 10:
            cards.append('10')
        else:
            cards.append(str(card))
    return ' + '.join(cards)

# ====================== КРАШ ======================
def update_crash(user_id):
    """Обновляет множитель в краш-игре, проверяет взрыв"""
    user_id = str(user_id)
    user = users.get(user_id)
    if not user or user.get('game') is None or user['game'].get('type') != 'crash':
        if user_id in crash_update_timers:
            del crash_update_timers[user_id]
        return
    game = user['game']
    chat_id = game.get('chat_id', int(user_id))
    current = game['current_mult']
    crash_point = game['crash_point']
    message_id = game['message_id']
    bet = game['bet']
    
    # Получаем бонус от бобров для краша
    bonuses = get_beaver_bonuses(user_id)
    crash_bonus = bonuses['crash_mult_bonus'] / 100

    # Проверка взрыва
    if current >= crash_point:
        try:
            bot.edit_message_text(
                f"💥 Ракета взорвалась на множителе {current:.2f}x! Ты проиграл {bet} кредитов.\n💰 Баланс: {user['balance']}",
                chat_id,
                message_id
            )
        except Exception as e:
            print(f"Ошибка при редактировании сообщения о краше: {e}")
        # Очистка
        if user_id in crash_update_timers:
            crash_update_timers[user_id].cancel()
            del crash_update_timers[user_id]
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        user['game'] = None
        save_data()
        return

    # Увеличиваем множитель (2% за шаг)
    new_mult = current * 1.02
    new_mult = round(new_mult, 2)
    game['current_mult'] = new_mult
    save_data()

    # Обновляем сообщение
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 Забрать", callback_data="crash_take"))
    try:
        bot.edit_message_text(
            f"🚀 Краш игра!\n\n💰 Ставка: {bet}\n📈 Текущий множитель: {new_mult:.2f}x\n"
            f"✨ Бонус бобров: +{int(crash_bonus*100)}% к финальному выигрышу\n\n"
            f"Забери выигрыш до взрыва!",
            chat_id,
            message_id,
            reply_markup=markup
        )
    except Exception as e:
        print(f"Ошибка обновления краш: {e}")
        # Если не удалось обновить (сообщение удалено), возвращаем ставку и завершаем
        if user_id in crash_update_timers:
            crash_update_timers[user_id].cancel()
            del crash_update_timers[user_id]
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        user['balance'] += bet
        user['game'] = None
        save_data()
        return

    # Сбрасываем таймаут игры
    set_game_timer(user_id)

    # Запускаем следующий апдейт через 0.3 сек
    timer = Timer(0.3, update_crash, [user_id])
    timer.daemon = True
    crash_update_timers[user_id] = timer
    timer.start()

# ====================== СЛОТЫ ======================
def slots_spin(user_id, game):
    """Генерирует случайную комбинацию и определяет выигрыш с учётом бонусов"""
    bet = game['bet']
    
    # Получаем бонус от бобров для слотов
    bonuses = get_beaver_bonuses(user_id)
    slots_bonus = bonuses['slots_bonus'] / 100
    
    # Генерируем три случайных символа
    symbols = [random.choice(SLOTS_SYMBOLS) for _ in range(3)]
    combo = tuple(symbols)
    
    # Определяем выигрыш
    if combo in SLOTS_PAYOUTS:
        mult = SLOTS_PAYOUTS[combo]
        win = int(bet * mult * (1 + slots_bonus))
        result_text = f"🎰 {symbols[0]} | {symbols[1]} | {symbols[2]} 🎰\n\n"
        result_text += f"🎉 Выигрышная комбинация! x{mult}\n"
        result_text += f"✨ Бонус бобров: +{int(slots_bonus*100)}%\n"
        result_text += f"💰 Выигрыш: {win} кредитов."
    elif symbols[0] == symbols[1] or symbols[1] == symbols[2] or symbols[0] == symbols[2]:
        # Два одинаковых - возврат ставки
        win = bet
        result_text = f"🎰 {symbols[0]} | {symbols[1]} | {symbols[2]} 🎰\n\n"
        result_text += f"🤝 Два одинаковых! Ставка возвращена.\n💰 Возврат: {bet} кредитов."
    else:
        win = 0
        result_text = f"🎰 {symbols[0]} | {symbols[1]} | {symbols[2]} 🎰\n\n"
        result_text += f"❌ Неудачная комбинация. Ты проиграл {bet} кредитов."
    
    # Обновляем баланс
    if win > 0:
        user = users[user_id]
        user['balance'] += win
        result_text += f"\n💰 Новый баланс: {user['balance']}"
    else:
        result_text += f"\n💰 Баланс: {users[user_id]['balance']}"
    
    return result_text, win

# ====================== КОСТИ ======================
def roll_dice():
    """Возвращает сумму двух кубиков"""
    return random.randint(1, 6) + random.randint(1, 6)

def dice_result(bet, bet_type, chosen_number=None):
    """Определяет результат игры в кости"""
    total = roll_dice()
    win = 0
    if bet_type == 'number':
        if total == chosen_number:
            win = bet * 6
            result = f"🎲 Выпало {total}! Ты угадал число! x6"
        else:
            result = f"🎲 Выпало {total}. Ты не угадал."
    elif bet_type == 'even_odd':
        if chosen_number == 'even' and total % 2 == 0:
            win = bet * 2
            result = f"🎲 Выпало {total} (чётное)! Ты выиграл! x2"
        elif chosen_number == 'odd' and total % 2 == 1:
            win = bet * 2
            result = f"🎲 Выпало {total} (нечётное)! Ты выиграл! x2"
        else:
            result = f"🎲 Выпало {total}. Ты проиграл."
    elif bet_type == 'range':
        if chosen_number == 'over7' and total > 7:
            win = bet * 2
            result = f"🎲 Выпало {total} (больше 7)! Ты выиграл! x2"
        elif chosen_number == 'under7' and total < 7:
            win = bet * 2
            result = f"🎲 Выпало {total} (меньше 7)! Ты выиграл! x2"
        else:
            result = f"🎲 Выпало {total}. Ты проиграл."
    return result, win, total

# ====================== РУЛЕТКА ======================
def roulette_spin():
    """Возвращает результат вращения рулетки"""
    number = random.choice(ROULETTE_NUMBERS)
    color = 'green' if number == 0 else ('red' if number in RED_NUMBERS else 'black')
    return number, color

def roulette_result(bet, bet_type, bet_value, number, color):
    """Определяет результат ставки в рулетке"""
    win = 0
    multiplier = 0
    
    if bet_type == 'straight':  # Ставка на конкретное число
        if number == bet_value:
            multiplier = ROULETTE_MULTIPLIERS['straight']
            win = bet * multiplier
    elif bet_type == 'color':  # Ставка на цвет
        if color == bet_value:
            multiplier = ROULETTE_MULTIPLIERS['color']
            win = bet * multiplier
    elif bet_type == 'even_odd':  # Чёт/нечет
        if number != 0:  # 0 не считается
            if bet_value == 'even' and number % 2 == 0:
                multiplier = ROULETTE_MULTIPLIERS['even']
                win = bet * multiplier
            elif bet_value == 'odd' and number % 2 == 1:
                multiplier = ROULETTE_MULTIPLIERS['odd']
                win = bet * multiplier
    elif bet_type == 'range':  # Меньше 19 / больше 18
        if number != 0:
            if bet_value == '1-18' and 1 <= number <= 18:
                multiplier = ROULETTE_MULTIPLIERS['1-18']
                win = bet * multiplier
            elif bet_value == '19-36' and 19 <= number <= 36:
                multiplier = ROULETTE_MULTIPLIERS['19-36']
                win = bet * multiplier
    elif bet_type == 'dozen':  # Дюжина
        if number != 0:
            if bet_value == '1st' and 1 <= number <= 12:
                multiplier = ROULETTE_MULTIPLIERS['dozen']
                win = bet * multiplier
            elif bet_value == '2nd' and 13 <= number <= 24:
                multiplier = ROULETTE_MULTIPLIERS['dozen']
                win = bet * multiplier
            elif bet_value == '3rd' and 25 <= number <= 36:
                multiplier = ROULETTE_MULTIPLIERS['dozen']
                win = bet * multiplier
    
    return win, multiplier

def get_roulette_bet_keyboard():
    """Клавиатура для выбора типа ставки в рулетке"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔢 Число (x36)", callback_data="roulette_type_straight"),
        types.InlineKeyboardButton("🔴 Красное (x2)", callback_data="roulette_type_red"),
        types.InlineKeyboardButton("⚫️ Чёрное (x2)", callback_data="roulette_type_black"),
        types.InlineKeyboardButton("🟢 0 (x36)", callback_data="roulette_type_zero"),
        types.InlineKeyboardButton("🔲 Чётное (x2)", callback_data="roulette_type_even"),
        types.InlineKeyboardButton("🔳 Нечётное (x2)", callback_data="roulette_type_odd"),
        types.InlineKeyboardButton("1-18 (x2)", callback_data="roulette_type_1-18"),
        types.InlineKeyboardButton("19-36 (x2)", callback_data="roulette_type_19-36"),
        types.InlineKeyboardButton("1-12 (x3)", callback_data="roulette_type_1st"),
        types.InlineKeyboardButton("13-24 (x3)", callback_data="roulette_type_2nd"),
        types.InlineKeyboardButton("25-36 (x3)", callback_data="roulette_type_3rd")
    )
    return markup

# ====================== МАРКЕТ БОБРОВ ======================
def show_market_menu(chat_id, user_id):
    """Отображает главное меню маркета"""
    user = get_user(user_id)
    
    text = "🦫 **Магазин коллекционных бобров**\n\n"
    text += "Каждый бобёр даёт уникальные бонусы:\n\n"
    
    for beaver_id, data in BEAVERS_DATA.items():
        available = data['total'] - data['sold']
        emoji = "✅" if available > 0 else "❌"
        text += f"{emoji} **{data['name']}**\n"
        text += f"└ Цена: {data['price']} кредитов\n"
        text += f"└ Редкость: {data['rarity']}\n"
        text += f"└ Бонус: {data['bonus']}\n"
        text += f"└ Осталось: {available} шт.\n\n"
    
    text += f"\n💰 Твой баланс: {user['balance']} кредитов\n"
    text += f"🦫 Твои бобры: {sum(user.get('beavers', {}).values())} шт.\n\n"
    text += "Выбери бобра для покупки:"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for beaver_id, data in BEAVERS_DATA.items():
        available = data['total'] - data['sold']
        if available > 0:
            btn_text = f"{data['name']} - {data['price']}💰"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"market_buy_{beaver_id}"))
    
    markup.add(types.InlineKeyboardButton("📊 Моя коллекция", callback_data="market_collection"))
    markup.add(types.InlineKeyboardButton("🚪 Выход", callback_data="market_exit"))
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def show_collection(chat_id, user_id):
    """Показывает коллекцию пользователя"""
    user = get_user(user_id)
    beavers = user.get('beavers', {})
    
    if not beavers:
        bot.send_message(chat_id, "🦫 У тебя пока нет бобров. Купи их в маркете!")
        return
    
    text = "📊 **Твоя коллекция бобров:**\n\n"
    
    for beaver_id, count in beavers.items():
        if count > 0 and beaver_id in BEAVERS_DATA:
            data = BEAVERS_DATA[beaver_id]
            text += f"🦫 **{data['name']}** — {count} шт.\n"
            text += f"└ Редкость: {data['rarity']}\n"
            text += f"└ Бонус: {data['bonus']}\n\n"
    
    # Показываем суммарные бонусы
    bonuses = get_beaver_bonuses(user_id)
    text += "**Твои бонусы:**\n"
    if bonuses['referral_bonus'] > 0:
        text += f"└ Рефералы: +{bonuses['referral_bonus']}%\n"
    if bonuses['slots_bonus'] > 0:
        text += f"└ Слоты: +{bonuses['slots_bonus']}%\n"
    if bonuses['roulette_bonus'] > 0:
        text += f"└ Русская рулетка: +{bonuses['roulette_bonus']}%\n"
    if bonuses['bank_interest_bonus'] > 0:
        text += f"└ Банк: +{bonuses['bank_interest_bonus']}%\n"
    if bonuses['max_bet_bonus'] > 0:
        text += f"└ Макс. ставка: +{bonuses['max_bet_bonus']}%\n"
    if bonuses['crash_mult_bonus'] > 0:
        text += f"└ Краш: +{bonuses['crash_mult_bonus']}%\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Назад в маркет", callback_data="market_back"))
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def buy_beaver(user_id, beaver_id):
    """Покупка бобра"""
    user = get_user(user_id)
    
    if beaver_id not in BEAVERS_DATA:
        return False, "❌ Такого бобра не существует."
    
    beaver = BEAVERS_DATA[beaver_id]
    available = beaver['total'] - beaver['sold']
    
    if available <= 0:
        return False, f"❌ {beaver['name']} закончились!"
    
    if user['balance'] < beaver['price']:
        return False, f"❌ Недостаточно средств. Нужно: {beaver['price']} кредитов."
    
    # Покупаем
    user['balance'] -= beaver['price']
    beaver['sold'] += 1
    
    # Добавляем в коллекцию пользователя
    if 'beavers' not in user:
        user['beavers'] = {}
    user['beavers'][beaver_id] = user['beavers'].get(beaver_id, 0) + 1
    
    save_data()
    
    return True, f"✅ Ты купил {beaver['name']} за {beaver['price']} кредитов!"

# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИГР ======================
def clear_game(user_id):
    """Полностью очищает игру пользователя и останавливает таймеры"""
    user_id = str(user_id)
    if user_id in game_timers:
        game_timers[user_id].cancel()
        del game_timers[user_id]
    if user_id in crash_update_timers:
        crash_update_timers[user_id].cancel()
        del crash_update_timers[user_id]
    if user_id in users:
        users[user_id]['game'] = None
    save_data()

def show_ref_info(user_id, chat_id):
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    bonuses = get_beaver_bonuses(user_id)
    referral_bonus = bonuses['referral_bonus']
    
    text = f"👥 Твоя реферальная ссылка:\n{ref_link}\n\n"
    text += f"📊 Приглашено друзей: {users[user_id]['referrals']}\n"
    text += f"🎁 За каждого друга ты получаешь 3000 кредитов"
    
    if referral_bonus > 0:
        text += f" + {referral_bonus}% бонус от бобров"
    
    bot.send_message(chat_id, text)

def start_game_by_command(user_id, chat_id, game_type, bet, **kwargs):
    """Запускает игру по команде с переданными параметрами"""
    user = get_user(user_id)
    bonuses = get_beaver_bonuses(user_id)
    effective_max_bet = MAX_BET * (1 + bonuses['max_bet_bonus'] / 100)
    
    # проверки
    if bet <= 0:
        bot.send_message(chat_id, "❌ Ставка должна быть положительной.")
        return False
    if bet > user['balance']:
        bot.send_message(chat_id, f"❌ Недостаточно средств. Твой баланс: {user['balance']}.")
        return False
    if bet > effective_max_bet:
        bot.send_message(chat_id, f"❌ Максимальная ставка с твоими бобрами: {int(effective_max_bet)}")
        return False

    # списываем ставку
    user['balance'] -= bet
    user['game'] = {
        'type': game_type,
        'bet': bet,
        'chat_id': chat_id,
        'stage': 'playing'  # базовая стадия, потом изменится
    }
    save_data()
    set_game_timer(user_id)

    if game_type == 'tower':
        mines = kwargs.get('mines')
        if mines is None:
            bot.send_message(chat_id, "❌ Не указано количество мин.")
            clear_game(user_id)
            return False
        # генерируем поле
        cells = list(range(1, 8))
        random.shuffle(cells)
        mine_positions = set(cells[:mines])
        safe_positions = set(cells[mines:])
        user['game']['mines'] = list(mine_positions)
        user['game']['safe'] = list(safe_positions)
        user['game']['opened'] = []
        user['game']['steps'] = 0
        user['game']['stage'] = 'playing_tower'
        save_data()
        show_tower_field(chat_id, user['game'])
        return True

    elif game_type == 'color':
        color = kwargs.get('color')
        if color is None:
            bot.send_message(chat_id, "❌ Не указан цвет.")
            clear_game(user_id)
            return False
        # сразу играем
        result = random.choice(['black', 'white'])
        if color == result:
            win = bet * 2
            user['balance'] += win
            result_text = f"🎉 Выпало {'⚫️ чёрное' if result == 'black' else '⚪️ белое'}! Ты угадал!\n💰 Ты выиграл {win} кредитов!\n💰 Новый баланс: {user['balance']}"
        else:
            result_text = f"❌ Выпало {'⚫️ чёрное' if result == 'black' else '⚪️ белое'}. Ты проиграл {bet} кредитов.\n💰 Баланс: {user['balance']}"
        bot.send_message(chat_id, result_text)
        clear_game(user_id)
        return True

    elif game_type == 'ball':
        # показываем кнопку броска
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏀 Кинуть мяч", callback_data="ball_throw"))
        bot.send_message(chat_id, f"💰 Ставка: {bet} кредитов.\n🏀 Нажми, чтобы кинуть мяч:", reply_markup=markup)
        user['game']['stage'] = 'playing'
        save_data()
        return True

    elif game_type == 'random_x':
        mult = kwargs.get('mult')
        if mult is None:
            bot.send_message(chat_id, "❌ Не указан множитель.")
            clear_game(user_id)
            return False
        chances = {2:50, 3:30, 5:20}
        chance = chances.get(mult)
        if not chance:
            bot.send_message(chat_id, "❌ Некорректный множитель.")
            clear_game(user_id)
            return False
        # сразу играем
        if random.randint(1, 100) <= chance:
            win = bet * mult
            user['balance'] += win
            result_text = f"🎉 Удача! x{mult} сработало!\n💰 Ты выиграл {win} кредитов!"
        else:
            result_text = f"❌ Не повезло. Ты проиграл {bet} кредитов."
        bot.send_message(chat_id, f"{result_text}\n💰 Новый баланс: {user['balance']}")
        clear_game(user_id)
        return True

    elif game_type == 'russian_roulette':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔫 Крутить барабан и стрелять", callback_data="roulette_shoot"))
        bot.send_message(chat_id, f"💰 Ставка: {bet} кредитов.\n🔫 Готов рискнуть?", reply_markup=markup)
        user['game']['stage'] = 'playing'
        save_data()
        return True

    elif game_type == 'blackjack':
        player_hand = [get_card(), get_card()]
        dealer_hand = [get_card(), get_card()]
        user['game']['player_hand'] = player_hand
        user['game']['dealer_hand'] = dealer_hand
        user['game']['stage'] = 'playing_21'
        save_data()
        player_sum = calc_hand(player_hand)
        dealer_visible = dealer_hand[0]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🎴 Ещё", callback_data="21_hit"),
            types.InlineKeyboardButton("🛑 Хватит", callback_data="21_stand")
        )
        msg = (f"🃏 **Очко (21)**\n\n"
               f"💰 Ставка: {bet} кредитов\n"
               f"👤 Твои карты: {hand_to_str(player_hand)} = **{player_sum}**\n"
               f"🤵 Карта дилера: {dealer_visible}\n\n"
               f"Выбери действие:")
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode='Markdown')
        return True

    elif game_type == 'crash':
        crash_point = min(10000, int(1 / random.random()))
        if crash_point < 1:
            crash_point = 1
        user['game']['crash_point'] = crash_point
        user['game']['current_mult'] = 1.0
        user['game']['stage'] = 'playing_crash'
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Забрать", callback_data="crash_take"))
        msg = bot.send_message(chat_id,
            f"🚀 Краш игра!\n\n💰 Ставка: {bet}\n📈 Текущий множитель: 1.00x\n\nЗабери выигрыш до взрыва!",
            reply_markup=markup)
        user['game']['message_id'] = msg.message_id
        save_data()
        timer = Timer(0.3, update_crash, [user_id])
        timer.daemon = True
        crash_update_timers[user_id] = timer
        timer.start()
        return True

    elif game_type == 'slots':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎰 Крутить", callback_data="slots_spin"))
        bot.send_message(chat_id, f"💰 Ставка: {bet} кредитов.\n🎰 Нажми, чтобы крутить барабаны:", reply_markup=markup)
        user['game']['stage'] = 'playing_slots'
        save_data()
        return True

    elif game_type == 'dice':
        dice_type = kwargs.get('dice_type')
        dice_choice = kwargs.get('dice_choice')
        if dice_type is None or dice_choice is None:
            bot.send_message(chat_id, "❌ Не указан тип ставки для костей.")
            clear_game(user_id)
            return False
        # сразу бросаем
        result_text, win, total = dice_result(bet, dice_type, dice_choice)
        user['balance'] += win
        bot.send_message(chat_id, f"{result_text}\n💰 Новый баланс: {user['balance']}")
        clear_game(user_id)
        return True

    elif game_type == 'roulette':
        # Для рулетки просто устанавливаем ставку и ждём выбора типа
        user['game']['stage'] = 'choosing_roulette_bet'
        save_data()
        
        markup = get_roulette_bet_keyboard()
        bot.send_message(chat_id, 
                        f"🎰 **Рулетка**\n\n"
                        f"💰 Ставка: {bet} кредитов\n"
                        f"🎯 Выбери тип ставки:",
                        reply_markup=markup,
                        parse_mode='Markdown')
        return True

    return False

# ====================== БАНКОВСКАЯ СИСТЕМА ======================
def apply_bank_interest(user_id):
    """Начисляет проценты на банковский счёт, если прошёл интервал (с учётом бонуса бобров)"""
    user = get_user(user_id)
    bank = user.get('bank', {'balance': 0, 'last_interest': time.time(), 'history': []})
    now = time.time()
    
    if now - bank['last_interest'] >= BANK_INTEREST_INTERVAL and bank['balance'] > 0:
        # Получаем бонус от бобров
        bonuses = get_beaver_bonuses(user_id)
        bank_bonus = 1 + bonuses['bank_interest_bonus'] / 100
        
        interest = int(bank['balance'] * BANK_INTEREST_RATE * bank_bonus)
        if interest > 0:
            bank['balance'] += interest
            # Запись в историю
            timestamp = time.strftime("%d.%m %H:%M")
            bank['history'].insert(0, f"💹 Проценты +{interest} (с бонусом {int((bank_bonus-1)*100)}%) — {timestamp}")
            bank['history'] = bank['history'][:10]
        bank['last_interest'] = now
        user['bank'] = bank
        save_data()

def show_bank_menu(chat_id, user_id):
    """Отображает главное меню банка"""
    user = get_user(user_id)
    bank = user.get('bank', {'balance': 0})
    
    bonuses = get_beaver_bonuses(user_id)
    bank_bonus = bonuses['bank_interest_bonus']
    
    text = (f"🏦 **Банк**\n\n"
            f"💰 Основной баланс: {user['balance']} кредитов\n"
            f"🏦 На депозите: {bank['balance']} кредитов\n"
            f"📈 Процентная ставка: {BANK_INTEREST_RATE*100}% в 24ч")
    
    if bank_bonus > 0:
        text += f" (+{bank_bonus}% от бобров)\n"
    else:
        text += "\n"
    
    text += f"\nВыбери действие:"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Баланс", callback_data="bank_balance"),
        types.InlineKeyboardButton("📥 Положить", callback_data="bank_deposit"),
        types.InlineKeyboardButton("📤 Снять", callback_data="bank_withdraw"),
        types.InlineKeyboardButton("📜 История", callback_data="bank_history"),
        types.InlineKeyboardButton("🚪 Выход", callback_data="bank_exit")
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def add_bank_history(user_id, operation):
    """Добавляет запись в историю банка (до 10)"""
    user = get_user(user_id)
    bank = user.get('bank', {'balance': 0, 'history': []})
    timestamp = time.strftime("%d.%m %H:%M")
    bank['history'].insert(0, f"{operation} — {timestamp}")
    bank['history'] = bank['history'][:10]
    user['bank'] = bank
    save_data()

# ====================== ОБРАБОТКА ТЕКСТА ======================
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = str(message.from_user.id)
    
    if is_banned(user_id):
        bot.send_message(message.chat.id, "⛔ Вы забанены и не можете использовать бота.")
        return
    
    user = get_user(user_id)
    text = message.text
    
    # Обновляем кэш username
    if message.from_user.username:
        update_username_cache(message.from_user.id, message.from_user.username)

    # ---- Команды, которые работают всегда (даже во время игры) ----
    lower_text = text.lower()
    if lower_text in ['помощь', 'help']:
        bot.send_message(message.chat.id, get_help_text(), parse_mode='Markdown')
        return

    if lower_text in ['реф', 'рефералы']:
        show_ref_info(user_id, message.chat.id)
        return

    if lower_text == 'топ':
        show_top(message.chat.id)
        return

    # ---- Банк (тоже работает всегда) ----
    if text == '🏦 Банк' or lower_text in ['банк', '/bank']:
        if user['game'] is not None:
            bot.send_message(message.chat.id, "❌ Сначала заверши текущую игру. Используй /cancel для отмены.")
            return
        apply_bank_interest(user_id)
        show_bank_menu(message.chat.id, user_id)
        return

    # ---- Маркет бобров ----
    if text == '🦫 Маркет' or lower_text in ['маркет', 'магазин', 'market']:
        if user['game'] is not None:
            bot.send_message(message.chat.id, "❌ Сначала заверши текущую игру. Используй /cancel для отмены.")
            return
        show_market_menu(message.chat.id, user_id)
        return

    # ---- Обработка команд для запуска игр (только если нет активной игры) ----
    if user['game'] is None:
        parts = lower_text.split()
        if len(parts) >= 2:
            cmd = parts[0]
            # очко / 21
            if cmd in ['очко', '21'] and len(parts) == 2:
                try:
                    bet = int(parts[1])
                    start_game_by_command(user_id, message.chat.id, 'blackjack', bet)
                    return
                except:
                    pass
            # слоты
            elif cmd == 'слоты' and len(parts) == 2:
                try:
                    bet = int(parts[1])
                    start_game_by_command(user_id, message.chat.id, 'slots', bet)
                    return
                except:
                    pass
            # х2, х3, х5 или дабл
            elif cmd in ['х2', 'х3', 'х5', 'дабл']:
                if cmd == 'дабл' and len(parts) == 3:
                    try:
                        mult = int(parts[1])
                        bet = int(parts[2])
                        if mult in [2,3,5]:
                            start_game_by_command(user_id, message.chat.id, 'random_x', bet, mult=mult)
                            return
                    except:
                        pass
                elif cmd in ['х2','х3','х5'] and len(parts) == 2:
                    try:
                        bet = int(parts[1])
                        mult = int(cmd[1])  # извлечь цифру
                        start_game_by_command(user_id, message.chat.id, 'random_x', bet, mult=mult)
                        return
                    except:
                        pass
            # краш
            elif cmd == 'краш' and len(parts) == 2:
                try:
                    bet = int(parts[1])
                    start_game_by_command(user_id, message.chat.id, 'crash', bet)
                    return
                except:
                    pass
            # мячик
            elif cmd == 'мячик' and len(parts) == 2:
                try:
                    bet = int(parts[1])
                    start_game_by_command(user_id, message.chat.id, 'ball', bet)
                    return
                except:
                    pass
            # рулетка
            elif cmd in ['рулетка', 'roulette'] and len(parts) == 2:
                try:
                    bet = int(parts[1])
                    start_game_by_command(user_id, message.chat.id, 'roulette', bet)
                    return
                except:
                    pass
            # кости
            elif cmd == 'кости' and len(parts) >= 3:
                try:
                    bet = int(parts[1])
                    bet_type = parts[2]
                    if bet_type in ['чет', 'нечет']:
                        choice = 'even' if bet_type == 'чет' else 'odd'
                        start_game_by_command(user_id, message.chat.id, 'dice', bet, dice_type='even_odd', dice_choice=choice)
                        return
                    elif bet_type in ['>7', '<7']:
                        range_choice = 'over7' if bet_type == '>7' else 'under7'
                        start_game_by_command(user_id, message.chat.id, 'dice', bet, dice_type='range', dice_choice=range_choice)
                        return
                    elif len(parts) == 3 and parts[2].isdigit():
                        number = int(parts[2])
                        if 2 <= number <= 12:
                            start_game_by_command(user_id, message.chat.id, 'dice', bet, dice_type='number', dice_choice=number)
                            return
                except:
                    pass
            # русская рулетка (рр)
            elif cmd in ['рр', 'русская'] and len(parts) == 2:
                try:
                    bet = int(parts[1])
                    start_game_by_command(user_id, message.chat.id, 'russian_roulette', bet)
                    return
                except:
                    pass
            # фишки
            elif cmd == 'фишки' and len(parts) == 3:
                try:
                    bet = int(parts[1])
                    color = parts[2]
                    if color in ['ч', 'б']:
                        color_full = 'black' if color == 'ч' else 'white'
                        start_game_by_command(user_id, message.chat.id, 'color', bet, color=color_full)
                        return
                except:
                    pass
            # башня
            elif cmd == 'башня' and len(parts) == 3:
                try:
                    bet = int(parts[1])
                    mines = int(parts[2])
                    if 1 <= mines <= 4:
                        start_game_by_command(user_id, message.chat.id, 'tower', bet, mines=mines)
                        return
                except:
                    pass

    # ---- Обработка кнопок меню (если не обработано выше) ----
    if text == '💰 Баланс':
        bank = user.get('bank', {'balance': 0})
        beavers_count = sum(user.get('beavers', {}).values())
        bot.send_message(message.chat.id, 
                        f"💰 Твой баланс: {user['balance']} кредитов.\n"
                        f"🏦 На депозите: {bank['balance']} кредитов.\n"
                        f"🦫 Бобров в коллекции: {beavers_count}")
    
    elif text == '👥 Рефералы':
        show_ref_info(user_id, message.chat.id)
    
    elif text == '🏆 Топ':
        show_top(message.chat.id)
    
    elif text == '❓ Помощь':
        bot.send_message(message.chat.id, get_help_text(), parse_mode='Markdown')
    
    elif text in ['🏰 Башня', '⚫️⚪️ Фишки', '🏀 Мячик', '🎲 X2/X3/X5', '🔫 Русская рулетка', '🃏 Очко (21)', '🚀 Краш', '🎰 Слоты', '🎲 Кости', '🎰 РУЛЕТКА']:
        if user['game'] is not None:
            bot.send_message(message.chat.id, "❌ Сначала заверши текущую игру. Используй /cancel для отмены.")
            return
        if user['balance'] <= 0:
            bot.send_message(message.chat.id, "❌ У тебя нет средств для игры. Пополни баланс или пригласи друзей.")
            return
        
        # Словарь для соответствия текста кнопки и типа игры
        game_types = {
            '🏰 Башня': 'tower',
            '⚫️⚪️ Фишки': 'color',
            '🏀 Мячик': 'ball',
            '🎲 X2/X3/X5': 'random_x',
            '🔫 Русская рулетка': 'russian_roulette',
            '🃏 Очко (21)': 'blackjack',
            '🚀 Краш': 'crash',
            '🎰 Слоты': 'slots',
            '🎲 Кости': 'dice',
            '🎰 РУЛЕТКА': 'roulette'
        }
        
        bot.send_message(message.chat.id, 
                        "💰 Введите сумму ставки (целое число).\n"
                        f"🔝 Максимальная ставка зависит от твоих бобров\n"
                        "🚫 Для отмены введи /cancel:")
        user['game'] = {'type': game_types[text], 'stage': 'waiting_bet'}
        save_data()
        # Устанавливаем таймер на ожидание ставки
        set_game_timer(user_id)
    
    else:
        # Проверяем, не ожидаем ли мы ставку или действие в банке
        if user.get('game') and user['game'].get('stage') == 'waiting_bet':
            try:
                bet = int(text)
                if bet <= 0:
                    bot.send_message(message.chat.id, "❌ Ставка должна быть положительной.")
                    return
                
                bonuses = get_beaver_bonuses(user_id)
                effective_max_bet = MAX_BET * (1 + bonuses['max_bet_bonus'] / 100)
                
                if bet > user['balance']:
                    bot.send_message(message.chat.id, f"❌ Недостаточно средств. Твой баланс: {user['balance']}.")
                    return
                if bet > effective_max_bet:
                    bot.send_message(message.chat.id, f"❌ Максимальная ставка с твоими бобрами: {int(effective_max_bet)}")
                    return
                
                user['balance'] -= bet
                user['game']['bet'] = bet
                user['game']['chat_id'] = message.chat.id
                game_type = user['game']['type']
                
                # Обновляем таймер
                set_game_timer(user_id)
                
                if game_type == 'tower':
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    for i in range(1, 5):
                        markup.add(types.InlineKeyboardButton(f"{i} 💣 мина(ы)", callback_data=f"tower_mines_{i}"))
                    bot.send_message(message.chat.id, f"✅ Ставка принята: {bet} кредитов.\n💣 Выбери количество мин:", reply_markup=markup)
                    user['game']['stage'] = 'choosing_mines'
                
                elif game_type == 'color':
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("⚫️ Чёрное", callback_data="color_black"),
                        types.InlineKeyboardButton("⚪️ Белое", callback_data="color_white")
                    )
                    bot.send_message(message.chat.id, f"✅ Ставка: {bet} кредитов.\n🎨 Выбери цвет:", reply_markup=markup)
                    user['game']['stage'] = 'playing'
                
                elif game_type == 'ball':
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🏀 Кинуть мяч", callback_data="ball_throw"))
                    bot.send_message(message.chat.id, f"✅ Ставка: {bet} кредитов.\n🏀 Нажми, чтобы кинуть мяч:", reply_markup=markup)
                    user['game']['stage'] = 'playing'
                
                elif game_type == 'random_x':
                    markup = types.InlineKeyboardMarkup(row_width=3)
                    markup.add(
                        types.InlineKeyboardButton("x2 (50%)", callback_data="random_x2"),
                        types.InlineKeyboardButton("x3 (30%)", callback_data="random_x3"),
                        types.InlineKeyboardButton("x5 (20%)", callback_data="random_x5")
                    )
                    bot.send_message(message.chat.id, f"✅ Ставка: {bet} кредитов.\n🎲 Выбери множитель:", reply_markup=markup)
                    user['game']['stage'] = 'playing'
                
                elif game_type == 'russian_roulette':
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔫 Крутить барабан и стрелять", callback_data="roulette_shoot"))
                    bot.send_message(message.chat.id, f"✅ Ставка: {bet} кредитов.\n🔫 Готов рискнуть?", reply_markup=markup)
                    user['game']['stage'] = 'playing'
                
                elif game_type == 'blackjack':
                    player_hand = [get_card(), get_card()]
                    dealer_hand = [get_card(), get_card()]
                    user['game']['player_hand'] = player_hand
                    user['game']['dealer_hand'] = dealer_hand
                    user['game']['stage'] = 'playing_21'
                    save_data()
                    
                    player_sum = calc_hand(player_hand)
                    dealer_visible = dealer_hand[0]
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("🎴 Ещё", callback_data="21_hit"),
                        types.InlineKeyboardButton("🛑 Хватит", callback_data="21_stand")
                    )
                    msg = (f"🃏 **Очко (21)**\n\n"
                           f"💰 Ставка: {bet} кредитов\n"
                           f"👤 Твои карты: {hand_to_str(player_hand)} = **{player_sum}**\n"
                           f"🤵 Карта дилера: {dealer_visible}\n\n"
                           f"Выбери действие:")
                    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='Markdown')
                    
                elif game_type == 'crash':
                    crash_point = min(10000, int(1 / random.random()))
                    if crash_point < 1:
                        crash_point = 1
                    user['game']['crash_point'] = crash_point
                    user['game']['current_mult'] = 1.0
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🚀 Забрать", callback_data="crash_take"))
                    msg = bot.send_message(message.chat.id,
                        f"🚀 Краш игра!\n\n💰 Ставка: {bet}\n📈 Текущий множитель: 1.00x\n\nЗабери выигрыш до взрыва!",
                        reply_markup=markup)
                    user['game']['message_id'] = msg.message_id
                    user['game']['stage'] = 'playing_crash'
                    save_data()
                    timer = Timer(0.3, update_crash, [user_id])
                    timer.daemon = True
                    crash_update_timers[user_id] = timer
                    timer.start()
                
                elif game_type == 'slots':
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🎰 Крутить", callback_data="slots_spin"))
                    bot.send_message(message.chat.id, f"✅ Ставка: {bet} кредитов.\n🎰 Нажми, чтобы крутить барабаны:", reply_markup=markup)
                    user['game']['stage'] = 'playing_slots'
                
                elif game_type == 'dice':
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton("🔢 Число (x6)", callback_data="dice_type_number"),
                        types.InlineKeyboardButton("🔲 Чёт/Нечет (x2)", callback_data="dice_type_even_odd"),
                        types.InlineKeyboardButton("📈 Больше 7 (x2)", callback_data="dice_type_over7"),
                        types.InlineKeyboardButton("📉 Меньше 7 (x2)", callback_data="dice_type_under7")
                    )
                    bot.send_message(message.chat.id, f"✅ Ставка: {bet} кредитов.\n🎲 Выбери тип ставки:", reply_markup=markup)
                    user['game']['stage'] = 'choosing_dice_type'
                
                elif game_type == 'roulette':
                    user['game']['stage'] = 'choosing_roulette_bet'
                    save_data()
                    markup = get_roulette_bet_keyboard()
                    bot.send_message(message.chat.id, 
                                    f"🎰 **Рулетка**\n\n"
                                    f"💰 Ставка: {bet} кредитов\n"
                                    f"🎯 Выбери тип ставки:",
                                    reply_markup=markup,
                                    parse_mode='Markdown')
                
                save_data()
                
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введи число.")
        # Проверяем состояние банка (ожидание суммы для пополнения/снятия)
        elif user.get('game') and user['game'].get('type') == 'bank' and user['game'].get('stage') in ['deposit', 'withdraw']:
            try:
                amount = int(text)
                if amount <= 0:
                    bot.send_message(message.chat.id, "❌ Сумма должна быть положительной.")
                    return
                
                action = user['game']['stage']
                if action == 'deposit':
                    if amount > user['balance']:
                        bot.send_message(message.chat.id, f"❌ Недостаточно средств. Твой баланс: {user['balance']}.")
                        return
                    user['balance'] -= amount
                    user['bank']['balance'] += amount
                    add_bank_history(user_id, f"📥 Пополнение +{amount}")
                    bot.send_message(message.chat.id, f"✅ Ты положил {amount} кредитов на депозит.")
                elif action == 'withdraw':
                    bank_bal = user['bank']['balance']
                    if amount > bank_bal:
                        bot.send_message(message.chat.id, f"❌ Недостаточно средств на депозите. Доступно: {bank_bal}.")
                        return
                    user['bank']['balance'] -= amount
                    user['balance'] += amount
                    add_bank_history(user_id, f"📤 Снятие -{amount}")
                    bot.send_message(message.chat.id, f"✅ Ты снял {amount} кредитов с депозита.")
                
                save_data()
                # Возвращаемся в меню банка
                apply_bank_interest(user_id)
                show_bank_menu(message.chat.id, user_id)
                user['game'] = None
                save_data()
            except ValueError:
                bot.send_message(message.chat.id, "❌ Введи число.")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
        else:
            bot.send_message(message.chat.id, "Я тебя не понимаю. Используй меню.")

# ====================== ОБРАБОТКА КНОПОК ======================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    
    if is_banned(user_id):
        bot.answer_callback_query(call.id, "⛔ Вы забанены!")
        return
    
    user = get_user(user_id)
    
    # Обновляем кэш username
    if call.from_user.username:
        update_username_cache(call.from_user.id, call.from_user.username)

    # ---- МАРКЕТ БОБРОВ ----
    if call.data.startswith('market_'):
        # Если есть активная игра, блокируем доступ к маркету
        if user.get('game') and user['game'].get('type') not in [None, 'bank', 'market']:
            bot.answer_callback_query(call.id, "❌ Сначала заверши текущую игру.")
            return
        
        if call.data == 'market_collection':
            show_collection(call.message.chat.id, user_id)
            bot.answer_callback_query(call.id)
            return
        
        elif call.data == 'market_back':
            show_market_menu(call.message.chat.id, user_id)
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
            return
        
        elif call.data == 'market_exit':
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
            return
        
        elif call.data.startswith('market_buy_'):
            beaver_id = call.data.replace('market_buy_', '')
            success, message = buy_beaver(user_id, beaver_id)
            bot.answer_callback_query(call.id, message)
            
            if success:
                # Обновляем сообщение с маркетом
                bot.delete_message(call.message.chat.id, call.message.message_id)
                show_market_menu(call.message.chat.id, user_id)
        
        return

    # ---- БАНК ----
    if call.data.startswith('bank_'):
        # Если есть активная игра, блокируем доступ к банку (кроме выхода)
        if user.get('game') and user['game'].get('type') not in [None, 'bank']:
            bot.answer_callback_query(call.id, "❌ Сначала заверши текущую игру.")
            return
        
        apply_bank_interest(user_id)
        bank = user.get('bank', {'balance': 0, 'history': []})
        
        if call.data == 'bank_balance':
            text = (f"🏦 **Твой банк**\n\n"
                    f"💰 Основной баланс: {user['balance']} кредитов\n"
                    f"🏦 На депозите: {bank['balance']} кредитов")
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            # Добавляем кнопку назад
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="bank_back"))
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)
        
        elif call.data == 'bank_deposit':
            # Переходим в состояние ожидания суммы для пополнения
            user['game'] = {'type': 'bank', 'stage': 'deposit'}
            save_data()
            bot.edit_message_text("📥 Введите сумму для пополнения (целое число):", 
                                 call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
        
        elif call.data == 'bank_withdraw':
            user['game'] = {'type': 'bank', 'stage': 'withdraw'}
            save_data()
            bot.edit_message_text("📤 Введите сумму для снятия (целое число):", 
                                 call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
        
        elif call.data == 'bank_history':
            history = bank.get('history', [])
            if not history:
                text = "📜 История операций пуста."
            else:
                text = "📜 **Последние операции:**\n\n" + "\n".join(history)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="bank_back"))
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)
        
        elif call.data == 'bank_exit':
            # Удаляем сообщение с меню банка
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
            if user.get('game') and user['game'].get('type') == 'bank':
                user['game'] = None
                save_data()
        
        elif call.data == 'bank_back':
            # Возврат в главное меню банка
            show_bank_menu(call.message.chat.id, user_id)
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
        
        return

    # ---- ИГРЫ ----
    if not user.get('game'):
        bot.answer_callback_query(call.id, "❓ Игра не активна. Начни новую.")
        try:
            bot.edit_message_reply_markup(call.from_user.id, call.message.message_id, reply_markup=None)
        except:
            pass
        return

    game = user['game']
    data = call.data
    
    # Обновляем таймер при любом действии
    set_game_timer(user_id)

    # ===== РУЛЕТКА =====
    if data.startswith('roulette_type_'):
        if game['type'] != 'roulette' or game.get('stage') != 'choosing_roulette_bet':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        
        bet = game['bet']
        bet_type = data.replace('roulette_type_', '')
        
        # Определяем тип ставки и значение
        if bet_type in ['red', 'black', 'zero']:
            # Ставка на цвет
            number, color = roulette_spin()
            
            if bet_type == 'red':
                win, mult = roulette_result(bet, 'color', 'red', number, color)
            elif bet_type == 'black':
                win, mult = roulette_result(bet, 'color', 'black', number, color)
            else:  # zero
                win, mult = roulette_result(bet, 'straight', 0, number, color)
            
            if win > 0:
                user['balance'] += win
                result_text = f"🎉 Выпало {number} {self.get_color_emoji(color)}! Ты выиграл {win} кредитов"
                if mult > 0:
                    result_text += f" (x{mult})"
            else:
                result_text = f"❌ Выпало {number} {self.get_color_emoji(color)}. Ты проиграл {bet} кредитов."
            
            result_text += f"\n💰 Новый баланс: {user['balance']}"
            
            bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id)
            clear_game(user_id)
            bot.answer_callback_query(call.id)
        
        elif bet_type in ['even', 'odd']:
            # Ставка на чёт/нечет
            number, color = roulette_spin()
            win, mult = roulette_result(bet, 'even_odd', bet_type, number, color)
            
            if win > 0:
                user['balance'] += win
                result_text = f"🎉 Выпало {number} {self.get_color_emoji(color)}! Ты выиграл {win} кредитов (x{mult})"
            else:
                result_text = f"❌ Выпало {number} {self.get_color_emoji(color)}. Ты проиграл {bet} кредитов."
            
            result_text += f"\n💰 Новый баланс: {user['balance']}"
            bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id)
            clear_game(user_id)
            bot.answer_callback_query(call.id)
        
        elif bet_type in ['1-18', '19-36']:
            # Ставка на диапазон
            number, color = roulette_spin()
            win, mult = roulette_result(bet, 'range', bet_type, number, color)
            
            if win > 0:
                user['balance'] += win
                result_text = f"🎉 Выпало {number} {self.get_color_emoji(color)}! Ты выиграл {win} кредитов (x{mult})"
            else:
                result_text = f"❌ Выпало {number} {self.get_color_emoji(color)}. Ты проиграл {bet} кредитов."
            
            result_text += f"\n💰 Новый баланс: {user['balance']}"
            bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id)
            clear_game(user_id)
            bot.answer_callback_query(call.id)
        
        elif bet_type in ['1st', '2nd', '3rd']:
            # Ставка на дюжину
            number, color = roulette_spin()
            win, mult = roulette_result(bet, 'dozen', bet_type, number, color)
            
            if win > 0:
                user['balance'] += win
                result_text = f"🎉 Выпало {number} {self.get_color_emoji(color)}! Ты выиграл {win} кредитов (x{mult})"
            else:
                result_text = f"❌ Выпало {number} {self.get_color_emoji(color)}. Ты проиграл {bet} кредитов."
            
            result_text += f"\n💰 Новый баланс: {user['balance']}"
            bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id)
            clear_game(user_id)
            bot.answer_callback_query(call.id)
        
        elif bet_type == 'straight':
            # Для ставки на число показываем клавиатуру с числами
            markup = types.InlineKeyboardMarkup(row_width=6)
            buttons = []
            for num in range(0, 37):
                buttons.append(types.InlineKeyboardButton(str(num), callback_data=f"roulette_number_{num}"))
            # Разбиваем на ряды по 6
            rows = [buttons[i:i+6] for i in range(0, len(buttons), 6)]
            for row in rows:
                markup.add(*row)
            bot.edit_message_text("🎰 Выбери число от 0 до 36:", call.message.chat.id, call.message.message_id, reply_markup=markup)
            user['game']['stage'] = 'choosing_roulette_number'
            save_data()
            bot.answer_callback_query(call.id)
    
    elif data.startswith('roulette_number_'):
        if game['type'] != 'roulette' or game.get('stage') != 'choosing_roulette_number':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        
        bet = game['bet']
        chosen_number = int(data.replace('roulette_number_', ''))
        number, color = roulette_spin()
        win, mult = roulette_result(bet, 'straight', chosen_number, number, color)
        
        if win > 0:
            user['balance'] += win
            result_text = f"🎉 Выпало {number} {self.get_color_emoji(color)}! Ты угадал число {chosen_number}!\n💰 Ты выиграл {win} кредитов (x{mult})"
        else:
            result_text = f"❌ Выпало {number} {self.get_color_emoji(color)}. Ты не угадал число {chosen_number}.\n💰 Ты проиграл {bet} кредитов."
        
        result_text += f"\n💰 Новый баланс: {user['balance']}"
        bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id)
        clear_game(user_id)
        bot.answer_callback_query(call.id)

    # ===== БАШНЯ =====
    elif data.startswith('tower_mines_'):
        if game['type'] != 'tower' or game['stage'] != 'choosing_mines':
            bot.answer_callback_query(call.id, "❌ Ошибка состояния игры.")
            return
        mines = int(data.split('_')[2])
        if mines < 1 or mines > 4:
            bot.answer_callback_query(call.id, "❌ Некорректное количество мин.")
            return
        cells = list(range(1, 8))
        random.shuffle(cells)
        mine_positions = set(cells[:mines])
        safe_positions = set(cells[mines:])
        game['mines'] = list(mine_positions)
        game['safe'] = list(safe_positions)
        game['opened'] = []
        game['steps'] = 0
        game['stage'] = 'playing_tower'
        save_data()
        show_tower_field(call.message.chat.id, game)
        bot.answer_callback_query(call.id)

    elif data.startswith('tower_cell_'):
        if game['type'] != 'tower' or game['stage'] != 'playing_tower':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        cell = int(data.split('_')[2])
        if cell in game['opened']:
            bot.answer_callback_query(call.id, "📦 Ячейка уже открыта.")
            return
        if cell in game['mines']:
            bot.edit_message_text(
                f"💥 Ты открыл мину! Ты проиграл {game['bet']} кредитов.\n💰 Баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
            if user_id in game_timers:
                game_timers[user_id].cancel()
                del game_timers[user_id]
            user['game'] = None
            save_data()
            bot.answer_callback_query(call.id, "💥 Ты проиграл!")
        else:
            game['opened'].append(cell)
            game['steps'] += 1
            current_mult = TOWER_MULTIPLIERS[game['steps']]
            current_win = int(game['bet'] * current_mult)

            if len(game['opened']) == len(game['safe']):
                user['balance'] += current_win
                bot.edit_message_text(
                    f"🎉 Ты открыл все безопасные ячейки!\n💰 Твой выигрыш: {current_win} кредитов (x{current_mult})\n💰 Новый баланс: {user['balance']}",
                    call.message.chat.id,
                    call.message.message_id
                )
                if user_id in game_timers:
                    game_timers[user_id].cancel()
                    del game_timers[user_id]
                user['game'] = None
                save_data()
                bot.answer_callback_query(call.id, "🎉 Ты выиграл!")
            else:
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("✅ Забрать", callback_data="tower_take"),
                    types.InlineKeyboardButton("🔄 Продолжить", callback_data="tower_continue")
                )
                bot.edit_message_text(
                    f"✅ Ячейка {cell} безопасна!\n📦 Ты открыл {game['steps']} ячеек.\n"
                    f"📈 Текущий множитель: x{current_mult}\n"
                    f"💰 Если остановишься, получишь {current_win} кредитов.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup
                )
                save_data()
                bot.answer_callback_query(call.id)

    elif data == 'tower_take':
        if game['type'] != 'tower' or game['stage'] != 'playing_tower':
            bot.answer_callback_query(call.id, "❌ Ошибка.")
            return
        steps = game['steps']
        if steps == 0:
            bot.answer_callback_query(call.id, "📦 Ты ещё не открыл ни одной ячейки.")
            return
        current_mult = TOWER_MULTIPLIERS[steps]
        win = int(game['bet'] * current_mult)
        user['balance'] += win
        bot.edit_message_text(
            f"✅ Ты забрал выигрыш: {win} кредитов (x{current_mult})\n💰 Новый баланс: {user['balance']}",
            call.message.chat.id,
            call.message.message_id
        )
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

    elif data == 'tower_continue':
        if game['type'] != 'tower' or game['stage'] != 'playing_tower':
            bot.answer_callback_query(call.id, "❌ Ошибка.")
            return
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_tower_field(call.message.chat.id, game)
        bot.answer_callback_query(call.id)

    # ===== ЦВЕТ =====
    elif data.startswith('color_'):
        if game['type'] != 'color' or game['stage'] != 'playing':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        bet = game['bet']
        choice = data.split('_')[1]
        result = random.choice(['black', 'white'])
        
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        
        if choice == result:
            win = bet * 2
            user['balance'] += win
            bot.edit_message_text(
                f"🎉 Выпало {'⚫️ чёрное' if result == 'black' else '⚪️ белое'}! Ты угадал!\n"
                f"💰 Ты выиграл {win} кредитов!\n💰 Новый баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.edit_message_text(
                f"❌ Выпало {'⚫️ чёрное' if result == 'black' else '⚪️ белое'}. Ты проиграл {bet} кредитов.\n"
                f"💰 Баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

    # ===== МЯЧИК =====
    elif data == 'ball_throw':
        if game['type'] != 'ball' or game['stage'] != 'playing':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        bet = game['bet']
        
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        
        if random.random() < 0.5:
            win = int(bet * 2.2)
            user['balance'] += win
            bot.edit_message_text(
                f"🏀 Мяч попал! Ты выиграл {win} кредитов (x2.2)!\n💰 Новый баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.edit_message_text(
                f"❌ Мяч не попал. Ты проиграл {bet} кредитов.\n💰 Баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

    # ===== X2/X3/X5 =====
    elif data.startswith('random_x'):
        if game['type'] != 'random_x' or game['stage'] != 'playing':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        
        bet = game['bet']
        chosen = data.split('_')[1]  # x2, x3, x5
        
        chances = {
            'x2': (2, 50),
            'x3': (3, 30),
            'x5': (5, 20)
        }
        
        win_mult, chance = chances[chosen]
        
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        
        if random.randint(1, 100) <= chance:
            win = bet * win_mult
            user['balance'] += win
            result_text = f"🎉 Удача! x{win_mult} сработало!\n💰 Ты выиграл {win} кредитов!"
        else:
            result_text = f"❌ Не повезло. Ты проиграл {bet} кредитов."
        
        bot.edit_message_text(
            f"{result_text}\n💰 Новый баланс: {user['balance']}",
            call.message.chat.id,
            call.message.message_id
        )
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

    # ===== РУССКАЯ РУЛЕТКА =====
    elif data == 'roulette_shoot':
        if game['type'] != 'russian_roulette' or game['stage'] != 'playing':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        
        bet = game['bet']
        
        # Получаем бонус от бобров для русской рулетки
        bonuses = get_beaver_bonuses(user_id)
        roulette_bonus = bonuses['roulette_bonus'] / 100
        
        # Шанс выжить 5/6 + бонус
        survival_chance = 5/6 + roulette_bonus
        
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        
        if random.random() < survival_chance:
            win = int(bet * 2.135)
            user['balance'] += win
            bot.edit_message_text(
                f"😌 Щелчок... Ты выжил!\n💰 Ты выиграл {win} кредитов (x2.135)!\n💰 Новый баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.edit_message_text(
                f"💥 Бах! Тебе не повезло...\nТы проиграл {bet} кредитов.\n💰 Баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
        
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

    # ===== ОЧКО (21) =====
    elif data in ['21_hit', '21_stand']:
        if game['type'] != 'blackjack' or game['stage'] != 'playing_21':
            bot.answer_callback_query(call.id, "❌ Ошибка состояния игры.")
            return
        
        bet = game['bet']
        player_hand = game['player_hand']
        dealer_hand = game['dealer_hand']
        
        if data == '21_hit':
            new_card = get_card()
            player_hand.append(new_card)
            player_sum = calc_hand(player_hand)
            dealer_visible = dealer_hand[0]
            
            if player_sum > 21:
                if user_id in game_timers:
                    game_timers[user_id].cancel()
                    del game_timers[user_id]
                user['game'] = None
                save_data()
                bot.edit_message_text(
                    f"❌ Перебор! Ты набрал {player_sum}. Ты проиграл {bet} кредитов.\n💰 Баланс: {user['balance']}",
                    call.message.chat.id,
                    call.message.message_id
                )
                bot.answer_callback_query(call.id, "💥 Перебор!")
                return
            else:
                game['player_hand'] = player_hand
                save_data()
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🎴 Ещё", callback_data="21_hit"),
                    types.InlineKeyboardButton("🛑 Хватит", callback_data="21_stand")
                )
                msg = (f"🃏 **Очко (21)**\n\n"
                       f"💰 Ставка: {bet} кредитов\n"
                       f"👤 Твои карты: {hand_to_str(player_hand)} = **{player_sum}**\n"
                       f"🤵 Карта дилера: {dealer_visible}\n\n"
                       f"Выбери действие:")
                bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                                     reply_markup=markup, parse_mode='Markdown')
                bot.answer_callback_query(call.id)
                return
        
        elif data == '21_stand':
            dealer_sum = calc_hand(dealer_hand)
            while dealer_sum < 17:
                dealer_hand.append(get_card())
                dealer_sum = calc_hand(dealer_hand)
            
            player_sum = calc_hand(player_hand)
            
            if dealer_sum > 21:
                win = int(bet * BLACKJACK_MULTIPLIER)
                user['balance'] += win
                result_text = (f"🎉 Дилер перебрал! Ты выиграл {win} кредитов (x{BLACKJACK_MULTIPLIER})!\n"
                               f"💰 Новый баланс: {user['balance']}")
            elif player_sum > dealer_sum:
                win = int(bet * BLACKJACK_MULTIPLIER)
                user['balance'] += win
                result_text = (f"🎉 Ты набрал больше дилера! Ты выиграл {win} кредитов (x{BLACKJACK_MULTIPLIER})!\n"
                               f"💰 Новый баланс: {user['balance']}")
            elif player_sum < dealer_sum:
                result_text = f"❌ Дилер набрал больше. Ты проиграл {bet} кредитов.\n💰 Баланс: {user['balance']}"
            else:
                user['balance'] += bet
                result_text = f"🤝 Ничья! Ставка возвращена.\n💰 Баланс: {user['balance']}"
            
            dealer_cards_str = hand_to_str(dealer_hand)
            msg = (f"🃏 **Очко (21)**\n\n"
                   f"👤 Твои карты: {hand_to_str(player_hand)} = **{player_sum}**\n"
                   f"🤵 Карты дилера: {dealer_cards_str} = **{dealer_sum}**\n\n"
                   f"{result_text}")
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            
            if user_id in game_timers:
                game_timers[user_id].cancel()
                del game_timers[user_id]
            user['game'] = None
            save_data()
            bot.answer_callback_query(call.id)

    # ===== КРАШ =====
    elif data == 'crash_take':
        if game['type'] != 'crash' or game.get('stage') != 'playing_crash':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        bet = game['bet']
        current_mult = game['current_mult']
        
        # Получаем бонус от бобров для краша
        bonuses = get_beaver_bonuses(user_id)
        crash_bonus = 1 + bonuses['crash_mult_bonus'] / 100
        
        win = int(bet * current_mult * crash_bonus)
        user['balance'] += win
        if user_id in crash_update_timers:
            crash_update_timers[user_id].cancel()
            del crash_update_timers[user_id]
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        try:
            bot.edit_message_text(
                f"🚀 Ты забрал выигрыш на множителе {current_mult:.2f}x!\n"
                f"✨ Бонус бобров: +{int((crash_bonus-1)*100)}%\n"
                f"💰 Ты выиграл {win} кредитов!\n"
                f"💰 Новый баланс: {user['balance']}",
                call.message.chat.id,
                call.message.message_id
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"✅ Ты выиграл {win} кредитов! Новый баланс: {user['balance']}")
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id, f"🎉 Ты выиграл {win}!")

    # ===== СЛОТЫ =====
    elif data == 'slots_spin':
        if game['type'] != 'slots' or game.get('stage') != 'playing_slots':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        bet = game['bet']
        result_text, win = slots_spin(user_id, game)
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id)
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

    # ===== КОСТИ =====
    elif data.startswith('dice_type_'):
        if game['type'] != 'dice' or game.get('stage') != 'choosing_dice_type':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        bet = game['bet']
        # Определяем тип ставки
        if data == 'dice_type_number':
            # Показать клавиатуру с числами 2-12
            markup = types.InlineKeyboardMarkup(row_width=4)
            buttons = []
            for num in range(2, 13):
                buttons.append(types.InlineKeyboardButton(str(num), callback_data=f"dice_number_{num}"))
            markup.add(*buttons)
            bot.edit_message_text("🎲 Выбери число от 2 до 12:", call.message.chat.id, call.message.message_id, reply_markup=markup)
            user['game']['dice_bet_type'] = 'number'
            user['game']['stage'] = 'choosing_dice_number'
            save_data()
            bot.answer_callback_query(call.id)
        else:
            # Для остальных типов сразу бросаем кости
            if data == 'dice_type_even_odd':
                # Спросим чёт/нечет
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("Чётное", callback_data="dice_even"),
                    types.InlineKeyboardButton("Нечётное", callback_data="dice_odd")
                )
                bot.edit_message_text("🎲 Выбери чёт или нечет:", call.message.chat.id, call.message.message_id, reply_markup=markup)
                user['game']['dice_bet_type'] = 'even_odd'
                user['game']['stage'] = 'choosing_even_odd'
                save_data()
                bot.answer_callback_query(call.id)
            elif data == 'dice_type_over7':
                # Сразу бросаем для "больше 7"
                result_text, win, total = dice_result(bet, 'range', 'over7')
                user['balance'] += win
                if user_id in game_timers:
                    game_timers[user_id].cancel()
                    del game_timers[user_id]
                bot.edit_message_text(f"{result_text}\n💰 Новый баланс: {user['balance']}", call.message.chat.id, call.message.message_id)
                user['game'] = None
                save_data()
                bot.answer_callback_query(call.id)
            elif data == 'dice_type_under7':
                result_text, win, total = dice_result(bet, 'range', 'under7')
                user['balance'] += win
                if user_id in game_timers:
                    game_timers[user_id].cancel()
                    del game_timers[user_id]
                bot.edit_message_text(f"{result_text}\n💰 Новый баланс: {user['balance']}", call.message.chat.id, call.message.message_id)
                user['game'] = None
                save_data()
                bot.answer_callback_query(call.id)

    elif data.startswith('dice_number_'):
        if game['type'] != 'dice' or game.get('stage') != 'choosing_dice_number':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        bet = game['bet']
        chosen_number = int(data.split('_')[2])
        result_text, win, total = dice_result(bet, 'number', chosen_number)
        user['balance'] += win
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        bot.edit_message_text(f"{result_text}\n💰 Новый баланс: {user['balance']}", call.message.chat.id, call.message.message_id)
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

    elif data in ['dice_even', 'dice_odd']:
        if game['type'] != 'dice' or game.get('stage') != 'choosing_even_odd':
            bot.answer_callback_query(call.id, "❌ Игра неактивна.")
            return
        bet = game['bet']
        choice = 'even' if data == 'dice_even' else 'odd'
        result_text, win, total = dice_result(bet, 'even_odd', choice)
        user['balance'] += win
        if user_id in game_timers:
            game_timers[user_id].cancel()
            del game_timers[user_id]
        bot.edit_message_text(f"{result_text}\n💰 Новый баланс: {user['balance']}", call.message.chat.id, call.message.message_id)
        user['game'] = None
        save_data()
        bot.answer_callback_query(call.id)

def get_color_emoji(self, color):
    """Возвращает эмодзи для цвета рулетки"""
    if color == 'red':
        return '🔴'
    elif color == 'black':
        return '⚫️'
    else:
        return '🟢'

def show_tower_field(chat_id, game):
    """Отображает поле башни с неоткрытыми ячейками"""
    markup = types.InlineKeyboardMarkup(row_width=4)
    buttons = []
    for cell in range(1, 8):
        if cell not in game['opened']:
            buttons.append(types.InlineKeyboardButton(f"📦 {cell}", callback_data=f"tower_cell_{cell}"))
    if buttons:
        markup.add(*buttons)
    bot.send_message(chat_id, "📦 Выбери ячейку, чтобы открыть:", reply_markup=markup)

# Загрузка данных при старте
load_data()

# Запуск бота
if __name__ == '__main__':
    print("🚀 Бот запущен...")
    print(f"👥 Загружено пользователей: {len(users)}")
    print(f"📇 Загружено username'ов: {len(username_cache)}")
    print(f"🎟 Загружено промокодов: {len(promocodes)}")
    print(f"🦫 Загружен маркет бобров")
    bot.infinity_polling()