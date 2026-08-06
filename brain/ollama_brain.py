"""
ULTRON V3
Advanced Ollama Local AI Brain
Conversation + User Memory Integration
"""

import ollama

from brain.memory import load_memory

from brain.conversation_memory import (
    save_chat,
    get_recent_chats
)


MODEL = "llama3.2:3b"



def ask_ollama(prompt):

    try:

        memory = load_memory()


        memory_context = "User Memory:\n"


        for key, value in memory.items():

            memory_context += f"{key}: {value}\n"



        chat_context = "Recent Conversation:\n"


        chats = get_recent_chats()


        for chat in chats:

            chat_context += (
                f"User: {chat['user']}\n"
                f"ULTRON: {chat['assistant']}\n"
            )



        response = ollama.chat(

            model=MODEL,

            messages=[

                {
                    "role": "system",

                    "content": f"""
You are ULTRON V3,
personal AI assistant.

Rules:
- Always call user Boss.
- Use memory when useful.
- Remember previous conversations.
- Give short helpful answers.

{memory_context}

{chat_context}
"""
                },


                {
                    "role": "user",

                    "content": prompt
                }

            ]

        )


        answer = response["message"]["content"]



        # Save conversation

        save_chat(

            prompt,

            answer

        )


        return answer




    except Exception as e:


        return f"Ollama error: {e}"