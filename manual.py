from core import Log, Grok
from json import dumps

proxy = ""
q = ''
while q != 'exit':
    q = input("Enter your message to Grok (or 'exit' to quit): ")
    if q == 'exit':
        break
    else:
        message1: str = q
        try:
            data1 = Grok(proxy).start_convo(message1, extra_data=None)
            
            # Error bor-yo'qligini tekshirish
            if "error" in data1:
                Log.Error(f"Xato: {data1['error']}")
                continue
                
            if "response" in data1:
                Log.Info("GROK: " + data1["response"])
            else:
                Log.Error("Javob olinmadi. Data: " + dumps(data1))
                
        except Exception as e:
            Log.Error(f"So'rovda xato: {str(e)}")
        

# message2: str = "cool stuff"
# Log.Info("USER: " + message2)
# data2 = Grok(proxy).start_convo(message2, extra_data=data1["extra_data"])
# Log.Info("GROK: " + data2["response"])

# message3: str = "crazy"
# Log.Info("USER: " + message3)
# data3 = Grok(proxy).start_convo(message3, extra_data=data2["extra_data"])
# Log.Info("GROK: " + data3["response"])

# message4: str = "Well this is the 4th message in our chat now omg"
# Log.Info("USER: " + message4)
# data4 = Grok(proxy).start_convo(message4, extra_data=data3["extra_data"])
# Log.Info("GROK: " + data4["response"])

# message5: str = "And now the 5th omg"
# Log.Info("USER: " + message5)
# data5 = Grok(proxy).start_convo(message5, extra_data=data4["extra_data"])
# Log.Info("GROK: " + data5["response"])