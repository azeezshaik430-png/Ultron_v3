"""
ULTRON V3
Advanced Ollama Local AI Brain
Conversation + User Memory Integration
Low Latency & Language Responsive System Prompts
"""

import ollama
from brain.memory import load_memory
from brain.conversation_memory import save_chat, get_recent_chats

MODEL = "llama3.2:3b"


def ask_ollama(prompt: str) -> str:
    """Generate response using Ollama local AI model with low latency and language responsiveness."""
    try:
        from core.session import session
        lang_rule = (
            "- Respond in natural Telugu (తెలుగు). Technical terms may remain in English where appropriate."
            if getattr(session, "preferred_language", "en") == "te"
            else "- Speak in clear natural English."
        )

        memory = load_memory()
        memory_context = "User Memory:\n"
        for key, value in memory.items():
            memory_context += f"{key}: {value}\n"

        chat_context = "Recent Conversation:\n"
        chats = get_recent_chats()
        for chat in chats:
            chat_context += f"User: {chat['user']}\nULTRON: {chat['assistant']}\n"

        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are ULTRON V3, a personal AI assistant.\n"
                        f"Rules:\n"
                        f"{lang_rule}\n"
                        f"- Speak naturally, directly, and neutrally. Do NOT start responses with 'Boss' or 'Boss!'.\n"
                        f"- Provide concise, conversational answers of 2 to 3 sentences suitable for speech.\n"
                        f"- Do NOT use markdown tables or long bulleted lists unless requested.\n"
                        f"- Use memory when useful.\n\n"
                        f"{memory_context}\n\n"
                        f"{chat_context}"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "num_predict": 128,
                "temperature": 0.6,
                "keep_alive": "10m",
                "num_ctx": 2048,
            }
        )

        answer = response["message"]["content"]
        save_chat(prompt, answer)
        return answer

    except Exception as e:
        return f"Ollama error: {e}"


def ask_ollama_stream(prompt: str):
    """Stream response tokens incrementally from Ollama local AI model with low latency."""
    try:
        from core.session import session
        lang_rule = (
            "- Respond in natural Telugu (తెలుగు). Technical terms may remain in English where appropriate."
            if getattr(session, "preferred_language", "en") == "te"
            else "- Speak in clear natural English."
        )

        memory = load_memory()
        memory_context = "User Memory:\n"
        for key, value in memory.items():
            memory_context += f"{key}: {value}\n"

        chat_context = "Recent Conversation:\n"
        chats = get_recent_chats()
        for chat in chats:
            chat_context += f"User: {chat['user']}\nULTRON: {chat['assistant']}\n"

        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are ULTRON V3, a personal AI assistant.\n"
                        f"Rules:\n"
                        f"{lang_rule}\n"
                        f"- Speak naturally, directly, and neutrally. Do NOT start responses with 'Boss' or 'Boss!'.\n"
                        f"- Provide concise, conversational answers of 2 to 3 sentences suitable for speech.\n"
                        f"- Do NOT use markdown tables or long bulleted lists unless requested.\n"
                        f"- Use memory when useful.\n\n"
                        f"{memory_context}\n\n"
                        f"{chat_context}"
                    )
                },
                {"role": "user", "content": prompt}
            ],
            options={
                "num_predict": 128,
                "temperature": 0.6,
                "keep_alive": "10m",
                "num_ctx": 2048,
            },
            stream=True
        )

        full_answer = []
        for chunk in response:
            token = chunk.get("message", {}).get("content", "")
            if token:
                full_answer.append(token)
                yield token

        if full_answer:
            save_chat(prompt, "".join(full_answer))

    except Exception as e:
        yield f"Ollama streaming error: {e}"