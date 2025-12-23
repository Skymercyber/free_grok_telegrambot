import telebot
from telebot import types
import json
import time
import threading
from datetime import datetime
import queue
import os
import random
import traceback
import pickle
import base64

# Core import
try:
    from core import Grok
except ImportError:
    print("❌ Core moduli topilmadi!")
    exit()

# Bot token
TOKEN = "8323193867:AAHVTRwS0ywO0ylKfvJ_A12CV_uZciiS0qI"
bot = telebot.TeleBot(TOKEN)

# Proxy (agar kerak bo'lsa)
PROXY = ""  # "http://user:pass@host:port"

# Global o'zgaruvchilar
user_sessions = {}
request_queue = queue.Queue()
CONVERSATION_FILE = "saved_conversations.dat"  # Binary fayl

class PersistentUserSession:
    """Conversation ma'lumotlarini saqlovchi session"""
    def __init__(self, user_id, username=""):
        self.user_id = user_id
        self.username = username or f"user_{user_id}"
        self.conversation_data = None  # Grok extra_data
        self.message_count = 0
        self.last_active = time.time()
        self.is_processing = False
        self.retry_count = 0
        self.last_error = None
        self.conversation_history = []  # Chat tarixi
        self.created_at = time.time()
        self.modified_at = time.time()
        self.conversation_id = None
        self.parent_response_id = None
        self.last_response = None
        self.conversation_state = "new"  # new, active, saved
        
    def to_save_dict(self):
        """Saqlash uchun dictionary (faqat saqlanishi mumkin bo'lgan ma'lumotlar)"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'message_count': self.message_count,
            'last_active': self.last_active,
            'retry_count': self.retry_count,
            'last_error': self.last_error,
            'conversation_history': self.conversation_history[:10],
            'created_at': self.created_at,
            'modified_at': time.time(),
            'conversation_id': self.conversation_id,
            'parent_response_id': self.parent_response_id,
            'last_response': self.last_response[:200] + "..." if self.last_response and len(self.last_response) > 200 else self.last_response,
            'conversation_state': self.conversation_state,
            'has_conversation': bool(self.conversation_data)
        }
    
    def update_from_grok(self, grok_result):
        """Grok natijasidan conversation ma'lumotlarini yangilash"""
        if "extra_data" in grok_result:
            # To'liq extra_data ni saqlash
            self.conversation_data = grok_result["extra_data"]
            
            # Muhim ID larni alohida saqlash
            self.conversation_id = grok_result["extra_data"].get("conversationId")
            self.parent_response_id = grok_result["extra_data"].get("parentResponseId")
            
            print(f"💾 Conversation saqlandi: {self.conversation_id}")
        
        if "response" in grok_result:
            self.last_response = grok_result["response"]
            # Chat tarixiga qo'shish
            self.conversation_history.append({
                'time': time.time(),
                'type': 'bot',
                'content': grok_result["response"][:100] + "..." if len(grok_result["response"]) > 100 else grok_result["response"]
            })
        
        self.message_count += 1
        self.last_active = time.time()
        self.modified_at = time.time()
        self.retry_count = 0
        self.last_error = None
        self.conversation_state = "active"

def load_conversations():
    """Saqlangan conversationlarni yuklash"""
    global user_sessions
    
    user_sessions = {}  # Yangilash
    
    if os.path.exists(CONVERSATION_FILE):
        try:
            with open(CONVERSATION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            loaded_count = 0
            for user_id_str, session_data in data.items():
                user_id = int(user_id_str)
                session = PersistentUserSession(user_id, session_data.get('username', ''))
                
                # Asosiy ma'lumotlarni yuklash
                session.message_count = session_data.get('message_count', 0)
                session.last_active = session_data.get('last_active', time.time())
                session.retry_count = session_data.get('retry_count', 0)
                session.last_error = session_data.get('last_error')
                session.conversation_history = session_data.get('conversation_history', [])
                session.created_at = session_data.get('created_at', time.time())
                session.modified_at = session_data.get('modified_at', time.time())
                session.conversation_id = session_data.get('conversation_id')
                session.parent_response_id = session_data.get('parent_response_id')
                session.last_response = session_data.get('last_response')
                session.conversation_state = session_data.get('conversation_state', 'new')
                
                # Conversation mavjudligini belgilash
                if session_data.get('has_conversation'):
                    session.conversation_data = {"restored": True, "conversation_id": session.conversation_id}
                    session.conversation_state = "restored"
                    loaded_count += 1
                
                user_sessions[user_id] = session
            
            print(f"✅ {loaded_count}/{len(data)} ta conversation yuklandi")
            
        except Exception as e:
            print(f"❌ Conversation yuklash xatosi: {e}")
            user_sessions = {}
    else:
        print("📭 Conversation fayli topilmadi. Yangi yaratiladi...")
        user_sessions = {}

def save_conversations():
    """Conversationlarni saqlash"""
    try:
        data = {}
        active_conversations = 0
        
        for user_id, session in user_sessions.items():
            data[str(user_id)] = session.to_save_dict()
            if session.conversation_data:
                active_conversations += 1
        
        with open(CONVERSATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 {active_conversations} ta active conversation saqlandi")
        
    except Exception as e:
        print(f"❌ Conversation saqlash xatosi: {e}")

def get_or_create_session(user_id, username=""):
    """Sessionni olish yoki yaratish"""
    global user_sessions
    
    if user_id not in user_sessions:
        user_sessions[user_id] = PersistentUserSession(user_id, username)
        print(f"👤 Yangi session: {user_id} ({username})")
    
    return user_sessions[user_id]

def cleanup_old_sessions():
    """Eski sessionlarni tozalash"""
    global user_sessions
    
    current_time = time.time()
    to_remove = []
    
    for user_id, session in user_sessions.items():
        if current_time - session.last_active > 86400:  # 24 soat
            to_remove.append(user_id)
    
    for user_id in to_remove:
        del user_sessions[user_id]
    
    if to_remove:
        print(f"🧹 {len(to_remove)} eski session tozalandi")

def escape_markdown(text):
    """Markdown maxsus belgilarini escape qilish"""
    if not text:
        return text
    
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def infinite_retry_with_backoff(message_text, session):
    """Cheksiz retry qilish"""
    extra_data = session.conversation_data
    retry_count = 0
    max_backoff = 300
    
    # Agar restored conversation bo'lsa, yangi boshlash
    if extra_data and extra_data.get("restored"):
        print(f"🔄 Restored conversation: {session.conversation_id}. Yangi boshlanmoqda...")
        extra_data = None
    
    while True:
        try:
            print(f"\n🔄 [User:{session.user_id} Retry:{retry_count + 1}] So'rov: '{message_text[:30]}...'")
            
            # Grok obyekti yaratish
            grok = Grok(model="grok-3-fast", proxy=PROXY)
            
            # User xabarini tarixga qo'shish
            if message_text:
                session.conversation_history.append({
                    'time': time.time(),
                    'type': 'user',
                    'content': message_text[:100] + "..." if len(message_text) > 100 else message_text
                })
                if len(session.conversation_history) > 20:
                    session.conversation_history = session.conversation_history[-20:]
            
            # So'rov yuborish
            result = grok.start_convo(message_text, extra_data=extra_data)
            
            # Agar error bo'lsa
            if "error" in result:
                error_msg = str(result.get("error", ""))
                print(f"❌ Xato ({retry_count + 1}): {error_msg[:100]}")
                session.last_error = error_msg[:200]
                
                # Exponential backoff
                backoff_time = min(30 * (2 ** retry_count) + random.randint(5, 15), max_backoff)
                
                if "too many requests" in error_msg.lower() or "429" in error_msg or "heavy" in error_msg:
                    print(f"⏳ Rate limit. {backoff_time}s kutish...")
                    time.sleep(backoff_time)
                elif "bot" in error_msg.lower() or "anti-bot" in error_msg.lower():
                    print(f"🤖 Bot aniqlandi. {backoff_time}s kutish...")
                    time.sleep(backoff_time)
                else:
                    print(f"⚠️ Boshqa xato. {backoff_time}s kutish...")
                    time.sleep(backoff_time)
                
                retry_count += 1
                session.retry_count = retry_count
                continue
            
            # Agar muvaffaqiyatli bo'lsa
            elif "response" in result:
                print(f"✅ Muvaffaqiyatli! (Retry: {retry_count}, Msg: {session.message_count + 1})")
                
                # Sessionni yangilash
                session.update_from_grok(result)
                
                return result
            
            # G'alati javob
            else:
                print(f"⚠️ G'alati javob format. 30s kutish...")
                time.sleep(30)
                retry_count += 1
                session.retry_count = retry_count
                continue
                
        except Exception as e:
            print(f"🔥 Exception ({retry_count + 1}): {str(e)}")
            backoff_time = min(60 * (retry_count + 1), max_backoff)
            print(f"⏳ Exception uchun {backoff_time}s kutish...")
            time.sleep(backoff_time)
            
            retry_count += 1
            session.retry_count = retry_count
            session.last_error = str(e)[:200]
            continue

def process_requests():
    """Navbatdagi so'rovlarni qayta ishlash"""
    global request_queue, user_sessions
    
    while True:
        try:
            if not request_queue.empty():
                user_id, message_id, text, chat_id = request_queue.get()
                
                session = get_or_create_session(user_id)
                session.is_processing = True
                
                bot.send_chat_action(chat_id, 'typing')
                result = infinite_retry_with_backoff(text, session)
                
                session.is_processing = False
                
                if "response" in result:
                    response_text = escape_markdown(result["response"])
                    
                    # Telegram limiti uchun bo'laklarga bo'lish
                    if len(response_text) > 4096:
                        parts = [response_text[i:i+4096] for i in range(0, len(response_text), 4096)]
                        for i, part in enumerate(parts, 1):
                            bot.send_message(chat_id, part, parse_mode='Markdown')
                            time.sleep(0.3)
                    else:
                        bot.send_message(chat_id, response_text, parse_mode='Markdown')
                    
                    # Conversation ma'lumoti
                    time.sleep(0.5)
                    status_msg = f"""💾 *CONVERSATION SAQLANDI*

🆔 Conversation ID: `{session.conversation_id or 'Yangi'}`
📝 Jami xabarlar: {session.message_count}
🔄 Retrylar: {session.retry_count}
⏰ Status: ✅ *ACTIVE*

💡 *Eslatma:* Conversation saqlandi. Bot qayta ishga tushganda tiklanadi."""
                    
                    bot.send_message(chat_id, status_msg, parse_mode='Markdown')
                
                request_queue.task_done()
                
            else:
                time.sleep(0.1)
                
        except Exception as e:
            print(f"🔥 Process requests xatosi: {str(e)}")
            time.sleep(5)

# /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.first_name or message.from_user.username or ""
    
    session = get_or_create_session(user_id, username)
    
    if session.conversation_data or session.conversation_state == "restored":
        welcome_text = f"""🤖 *XUSH KELIBSIZ, {escape_markdown(username)}!*

🎯 *SAQLANGAN CONVERSATION TOPILDI!*

📊 *Conversation ma'lumotlari:*
• Conversation ID: `{session.conversation_id or 'Noma\'lum'}`
• Xabarlar soni: *{session.message_count}*
• Oxirgi faollik: {time.ctime(session.last_active)[:19]}
• Status: {'✅ SAQLANGAN' if session.conversation_data else '🔄 TIKLANMOQDA'}

💾 *Conversation tiklandi!*
Avvalgi chat davom ettiriladi.

📋 *Buyruqlar:*
/continue - Chatni davom ettirish
/new - Yangi conversation boshlash
/info - Conversation ma'lumotlari
/stats - Statistika
"""
    else:
        welcome_text = f"""🤖 *XUSH KELIBSIZ, {escape_markdown(username)}!*

✨ *YANGI CONVERSATION BOSHLANDI*

💾 *Conversation saqlanadi:*
• Bot o'chirilsa ham saqlanadi
• Qayta ishga tushganda tiklanadi
• Chat tarixi saqlanadi

✍️ *Xabaringizni yozing!*
"""
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

# /continue command
@bot.message_handler(commands=['continue'])
def continue_command(message):
    user_id = message.from_user.id
    session = get_or_create_session(user_id)
    
    if session.conversation_data or session.conversation_state == "restored":
        bot.send_message(
            message.chat.id,
            f"✅ *CONVERSATION DAVOM ETMOQDA*\n\n"
            f"🆔 Conversation ID: `{session.conversation_id}`\n"
            f"📝 Jami xabarlar: {session.message_count}\n"
            f"💾 Status: SAQLANGAN\n\n"
            f"Endi menga xabar yozing. Chat davom ettiriladi.",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ *SAQLANGAN CONVERSATION TOPILMADI*\n\n"
            "Yangi conversation boshlash uchun xabar yozing.",
            parse_mode='Markdown'
        )

# /new command
@bot.message_handler(commands=['new'])
def new_command(message):
    user_id = message.from_user.id
    session = get_or_create_session(user_id)
    
    old_id = session.conversation_id
    
    # Yangi conversation
    session.conversation_data = None
    session.conversation_id = None
    session.parent_response_id = None
    session.conversation_history = []
    session.conversation_state = "new"
    session.message_count = 0
    
    bot.send_message(
        message.chat.id,
        f"🔄 *YANGI CONVERSATION BOSHLANDI*\n\n"
        f"Eski conversation ID: `{old_id or 'Yo\'q'}`\n"
        f"Yangi conversation yaratildi.\n\n"
        f"✍️ Xabaringizni yozing.",
        parse_mode='Markdown'
    )

# /info command
@bot.message_handler(commands=['info'])
def info_command(message):
    user_id = message.from_user.id
    session = get_or_create_session(user_id)
    
    info_text = f"""📋 *CONVERSATION MA'LUMOTLARI*

👤 Foydalanuvchi: {escape_markdown(session.username)}
🆔 User ID: `{user_id}`

💾 *Conversation:*
• ID: `{session.conversation_id or 'Yangi'}`
• Status: {session.conversation_state.upper()}
• Parent ID: `{session.parent_response_id or 'Yo\'q'}`
• Xabarlar: {session.message_count}

📅 *Vaqt:*
• Yaratilgan: {time.ctime(session.created_at)[:19]}
• Oxirgi faollik: {time.ctime(session.last_active)[:19]}
• Yangilangan: {time.ctime(session.modified_at)[:19]}

📜 *Tarix:*
• Xabarlar: {len(session.conversation_history)} ta
• Oxirgi xato: {session.last_error or 'Yo\'q'}
• Retrylar: {session.retry_count}
"""
    
    bot.send_message(message.chat.id, info_text, parse_mode='Markdown')

# /stats command
@bot.message_handler(commands=['stats'])
def show_stats(message):
    user_id = message.from_user.id
    session = get_or_create_session(user_id)
    
    # Fayl ma'lumotlari
    file_exists = os.path.exists(CONVERSATION_FILE)
    file_size = os.path.getsize(CONVERSATION_FILE) if file_exists else 0
    
    # Barcha sessionlar
    total_sessions = len(user_sessions)
    active_conversations = sum(1 for s in user_sessions.values() if s.conversation_data or s.conversation_state == "restored")
    
    stats_text = f"""📊 *BOT STATISTIKASI*

👤 *SIZ:*
• Ism: {escape_markdown(session.username)}
• Conversation: {session.conversation_state.upper()}
• ID: `{session.conversation_id or 'Yangi'}`
• Xabarlar: *{session.message_count}*
• Retry: *{session.retry_count}*

💾 *SAQLASH TIZIMI:*
• Fayl: `{CONVERSATION_FILE}`
• Hajm: {file_size:,} bayt
• Sessionlar: {total_sessions} ta
• Faol conversationlar: {active_conversations} ta

🌐 *BOT:*
• Holat: ✅ *ISHLAYAPTI*
• Navbat: *{request_queue.qsize()}*
• Server: {'✅ ON' if file_exists else '⚠️ OFFLINE'}
• Versiya: 2.0 \(Persistent\)
"""
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# /save command
@bot.message_handler(commands=['save'])
def save_command(message):
    save_conversations()
    
    active_conversations = sum(1 for s in user_sessions.values() if s.conversation_data or s.conversation_state == "restored")
    
    bot.send_message(
        message.chat.id,
        f"💾 *CONVERSATION SAQLANDI!*\n\n"
        f"• Faol conversationlar: {active_conversations} ta\n"
        f"• Jami sessionlar: {len(user_sessions)} ta\n"
        f"• Fayl: `{CONVERSATION_FILE}`\n"
        f"• Hajm: {os.path.getsize(CONVERSATION_FILE) if os.path.exists(CONVERSATION_FILE) else 0:,} bayt\n\n"
        f"Bot qayta ishga tushganda conversationlar tiklanadi.",
        parse_mode='Markdown'
    )

# Barcha text xabarlar
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    session = get_or_create_session(user_id)
    
    if session.is_processing:
        bot.send_message(
            chat_id,
            f"⏳ *Hozirda oldingi so'rov qayta ishlanmoqda...*\n\n"
            f"Retrylar: {session.retry_count}\n"
            f"Conversation ID: `{session.conversation_id or 'Yangi'}`\n\n"
            f"Iltimos, biroz kuting...",
            parse_mode='Markdown',
            reply_to_message_id=message.message_id
        )
        return
    
    # Navbatga qo'shish
    request_queue.put((user_id, message.message_id, message.text, chat_id))
    
    # Agar conversation restored bo'lsa
    if session.conversation_state == "restored":
        status_msg = f"""🎯 *SAQLANGAN CONVERSATION DAVOM ETMOQDA*

🆔 Conversation ID: `{session.conversation_id}`
📝 Xabarlar: {session.message_count}
💾 Status: TIKLANGAN

Bot hozir sizning xabaringiz uchun javob izlaydi.
Conversation saqlanib, keyin tiklanadi."""
    else:
        status_msg = f"""🎯 *YANGI CONVERSATION BOSHLANDI*

Bot hozir sizning xabaringiz uchun javob izlaydi.
Conversation saqlanadi va keyin tiklanadi."""

    bot.send_message(
        chat_id,
        status_msg,
        parse_mode='Markdown',
        reply_to_message_id=message.message_id
    )

# Asosiy dastur
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 PERSISTENT CONVERSATION GROK BOT v2.0")
    print("=" * 60)
    print("💾 Conversationlarni to'liq saqlaydi")
    print("♾️ Hech qachon to'xtamaydi")
    print("🔄 Bot qayta ishga tushganda tiklanadi")
    print("=" * 60)
    
    # Conversationlarni yuklash
    print("📂 Conversation fayllarini yuklash...")
    load_conversations()
    
    # Auto-save thread
    def auto_save():
        while True:
            try:
                save_conversations()
                time.sleep(60)  # Har 1 daqiqa
            except Exception as e:
                print(f"Auto-save error: {e}")
                time.sleep(30)
    
    save_thread = threading.Thread(target=auto_save, daemon=True)
    save_thread.start()
    
    # Request processor thread
    def process_thread():
        process_requests()
    
    processor_thread = threading.Thread(target=process_thread, daemon=True)
    processor_thread.start()
    
    print(f"✅ Bot tayyor! {len(user_sessions)} ta session yuklandi")
    
    # Botni ishga tushirish
    while True:
        try:
            print(f"\n🔄 Polling ishga tushirilmoqda... {datetime.now().strftime('%H:%M:%S')}")
            bot.polling(none_stop=True, interval=1, timeout=30)
            
        except Exception as e:
            print(f"🔥 POLLING XATOSI: {str(e)}")
            save_conversations()
            
            wait_time = 10
            print(f"⏳ {wait_time} soniya kutish...")
            time.sleep(wait_time)