from core import Log, Grok
from json import dumps
import time
import random

proxy = ""

def send_with_retry(message, max_retries=5, use_extra_data=None):
    """Retry bilan so'rov yuborish"""
    extra_data = use_extra_data
    
    for attempt in range(max_retries):
        print(f"\n[Urinish {attempt+1}/{max_retries}]")
        
        try:
            # Har bir urinishda yangi Grok instance
            grok = Grok(model="grok-3-fast", proxy=proxy)
            data = grok.start_convo(message, extra_data=extra_data)
            
            # Xato tahlili
            if "error" in data:
                error_msg = str(data.get("error", "")).lower()
                
                # 429 - Rate limit
                if "429" in error_msg or "heavy" in error_msg or "usage" in error_msg:
                    wait_time = 30 * (attempt + 1) + random.randint(5, 15)
                    Log.Info(f"⏳ Rate limit. {wait_time} soniya kutish...")
                    time.sleep(wait_time)
                    continue
                    
                # Bot bloklangan
                elif "bot" in error_msg or "anti-bot" in error_msg:
                    Log.Error(f"🤖 Bot deb hisoblangan. Proxy o'zgartiring.")
                    return {"error": "Bot detected - change proxy"}
                    
                # Boshqa xatolar
                else:
                    Log.Error(f"❌ Xato: {data['error']}")
                    if attempt < max_retries - 1:
                        time.sleep(20)
                        continue
                        
            # Muvaffaqiyatli javob
            elif "response" in data:
                Log.Success(f"✅ So'rov muvaffaqiyatli!")
                return data
                
            # G'alati javob
            else:
                Log.Error(f"⚠️ G'alati javob format")
                print(f"Data keys: {list(data.keys())}")
                if attempt < max_retries - 1:
                    time.sleep(15)
                    continue
                    
        except Exception as e:
            Log.Error(f"⚠️ Exception: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(20)
    
    return {"error": f"{max_retries} marta urinish muvaffaqiyatsiz"}

def print_response_info(data):
    """Javob ma'lumotlarini chiroyli chiqarish"""
    print("\n" + "="*60)
    
    if "error" in data:
        print(f"❌ XATO: {data['error']}")
        return False
        
    elif "response" in data:
        print(f"🤖 GROK JAVOBI:")
        print("-"*40)
        print(data["response"])
        print("-"*40)
        
        # Qo'shimcha ma'lumotlar
        if "stream_response" in data:
            print(f"📊 Stream tokens: {len(data['stream_response'])} ta")
            
        if "images" in data and data["images"]:
            print(f"🖼️  Rasmlar: {len(data['images'])} ta")
            for img in data["images"]:
                print(f"   • {img[:80]}...")
                
        if "extra_data" in data:
            extra = data["extra_data"]
            print(f"📦 Conversation ID: {extra.get('conversationId', 'N/A')}")
            print(f"🔑 Anon User: {extra.get('anon_user', 'N/A')[:20]}...")
            
        return True
        
    else:
        print(f"⚠️ Noma'lum javob formati")
        print(f"Data: {dumps(data, indent=2)}")
        return False

def main():
    """Asosiy interaktiv dastur"""
    print("="*60)
    print("GROK AI CHAT - INTERAKTIV VERSIYA")
    print("="*60)
    
    saved_data = None
    conversation_count = 0
    
    while True:
        print(f"\n💬 Chat messages: {conversation_count}")
        print("-"*40)
        
        q = input("Foydalanuvchi: ").strip()
        
        if q.lower() in ['exit', 'quit', 'chiq']:
            print("\nDastur tugatildi. Xayr!")
            break
            
        if not q:
            print("❌ Xabar bo'sh bo'lmasligi kerak!")
            continue
        
        # So'rovni yuborish
        Log.Info(f"So'rov yuborilmoqda: '{q[:50]}...'")
        
        # Extra_data ni ishlatish (agar mavjud bo'lsa)
        if saved_data and conversation_count > 0:
            use_data = saved_data.get("extra_data")
            Log.Info("Oldingi conversation davom ettirilmoqda...")
        else:
            use_data = None
            Log.Info("Yangi conversation boshlanmoqda...")
        
        # Retry bilan so'rov yuborish
        result = send_with_retry(q, max_retries=3, use_extra_data=use_data)
        
        # Natijani ko'rsatish
        success = print_response_info(result)
        
        # Agar muvaffaqiyatli bo'lsa, ma'lumotlarni saqlash
        if success and "extra_data" in result:
            saved_data = result
            conversation_count += 1
            
            # Conversation davom ettirish uchun taklif
            if conversation_count == 1:
                print(f"\n💡 Maslahat: Endi siz conversation davom ettirishingiz mumkin.")
                print(f"   Keyingi so'rovda avvalgi chat tarixi saqlanadi.")
        
        # Conversation orasida qisqa pauza
        if success and conversation_count > 0:
            pause_time = random.randint(5, 10)
            print(f"\n⏱️  Keyingi so'rov uchun {pause_time} soniya kutish...")
            time.sleep(pause_time)

def quick_test():
    """Tezkor test"""
    print("\n🚀 TEZKOR TEST BOSHLANDI")
    
    test_messages = [
        "Salom, qandaysan?",
        "Ob-havo qanday?",
        "Python dasturlash tili haqida gapir"
    ]
    
    saved_data = None
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{'='*50}")
        print(f"TEST {i}/3: '{message}'")
        
        result = send_with_retry(message, max_retries=2, use_extra_data=saved_data)
        
        if "response" in result:
            print(f"\n✅ Javob ({len(result['response'])} belgi):")
            print(f"{result['response'][:150]}...")
            
            if "extra_data" in result:
                saved_data = result["extra_data"]
                print(f"📁 Conversation saqlandi")
        else:
            print(f"\n❌ Xato: {result.get('error')}")
            break
        
        if i < len(test_messages):
            print(f"\n⏳ Keyingi test uchun 10 soniya...")
            time.sleep(10)
    
    print(f"\n{'='*50}")
    print("✅ TEST TUGALLANDI")

if __name__ == "__main__":
    print("Tanlang:")
    print("1. Interaktiv chat")
    print("2. Tezkor test (3 ta so'rov)")
    print("3. Chiqish")
    
    choice = input("\nTanlov (1/2/3): ").strip()
    
    if choice == "1":
        main()
    elif choice == "2":
        quick_test()
    else:
        print("Xayr!")