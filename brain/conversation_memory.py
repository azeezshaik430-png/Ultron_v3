"""
ULTRON V3
Conversation Memory System
"""

import json
import os
from datetime import datetime


CHAT_FILE = "data/conversation_history.json"



def load_chat_history():

    if not os.path.exists(CHAT_FILE):

        return []


    with open(CHAT_FILE, "r") as file:

        return json.load(file)




def save_chat(user, assistant):

    history = load_chat_history()


    conversation = {

        "time": str(datetime.now()),

        "user": user,

        "assistant": assistant

    }


    history.append(conversation)


    # Last 50 conversations matrame store cheyyi

    history = history[-50:]


    with open(CHAT_FILE, "w") as file:

        json.dump(

            history,

            file,

            indent=4

        )




def get_recent_chats(limit=5):

    history = load_chat_history()


    return history[-limit:]