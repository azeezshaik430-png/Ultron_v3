"""
ULTRON V3
Ollama Client
"""

import ollama

from config.settings import OLLAMA_MODEL


def ask_ai(prompt: str) -> str:
    """
    Send a prompt to Ollama
    and return the response.
    """

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]

    except Exception as e:
        return f"AI Error: {e}"