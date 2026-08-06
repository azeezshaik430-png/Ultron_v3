"""
ULTRON V3
Ollama Local AI Brain
Memory Connected
"""

import ollama

from brain.memory import load_memory


MODEL = "llama3.2:3b"


def ask_ollama(prompt):

    try:

        memory = load_memory()


        memory_context = f"""
User Memory:

Name: {memory.get("name", "Unknown")}
Likes: {memory.get("likes", "Unknown")}
Favorite Game: {memory.get("favorite_game", "Unknown")}
"""


        response = ollama.chat(

            model=MODEL,

            messages=[

                {
                    "role": "system",

                    "content": f"""
You are ULTRON V3,
a personal AI assistant.

Always call the user Boss.

Use the user's memory when helpful.

Give short and useful answers.

{memory_context}
"""
                },


                {
                    "role": "user",

                    "content": prompt
                }

            ]

        )


        return response["message"]["content"]


    except Exception as e:

        return f"Ollama error: {e}"