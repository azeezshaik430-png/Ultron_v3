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


def build_system_prompt(prompt: str) -> str:
    """Build structured system prompt with User Memory, Semantic Memory, and Conversation History."""
    from core.session import session
    from brain.semantic_memory import SemanticMemoryStore

    lang_rule = (
        "- Respond in natural Telugu (తెలుగు). Technical terms may remain in English where appropriate."
        if getattr(session, "preferred_language", "en") == "te"
        else "- Speak in clear natural English."
    )

    memory = load_memory()
    memory_context = "User Memory:\n"
    existing_keys = set(memory.keys())
    for key, value in memory.items():
        memory_context += f"{key}: {value}\n"

    # Semantic Memory Vector Relevance Retrieval
    semantic_context = ""
    try:
        store = SemanticMemoryStore()
        sem_entries = store.query_semantic_memory(prompt, top_k=3, min_score=0.15)
        filtered_sem = [
            e for e in sem_entries
            if e.get("key") not in existing_keys
        ]
        if filtered_sem:
            semantic_context = "Relevant Semantic Context:\n"
            for item in filtered_sem:
                semantic_context += f"- {item['key']}: {item['value']}\n"
    except Exception:
        pass

    chat_context = "Recent Conversation:\n"
    chats = get_recent_chats()
    for chat in chats:
        chat_context += f"User: {chat['user']}\nULTRON: {chat['assistant']}\n"

    parts = [
        f"You are ULTRON V3, a personal AI assistant.\nRules:\n{lang_rule}\n- Speak naturally, directly, and neutrally. Do NOT start responses with 'Boss' or 'Boss!'.\n- Provide concise, conversational answers of 2 to 3 sentences suitable for speech.\n- Do NOT use markdown tables or long bulleted lists unless requested.\n- Use memory when useful.",
        memory_context.strip(),
    ]
    if semantic_context:
        parts.append(semantic_context.strip())
    parts.append(chat_context.strip())

    return "\n\n".join(parts)


def _build_messages(prompt: str, system_content: str, history_limit: int = 10) -> list:
    """Build multi-turn message list with conversation history for Ollama."""
    messages = [{"role": "system", "content": system_content}]

    # Include recent conversation turns as proper message roles
    chats = get_recent_chats(limit=history_limit)
    for chat in chats:
        user_msg = chat.get("user", "")
        assistant_msg = chat.get("assistant", "")
        if user_msg:
            messages.append({"role": "user", "content": user_msg})
        if assistant_msg:
            messages.append({"role": "assistant", "content": assistant_msg})

    # Current user message
    messages.append({"role": "user", "content": prompt})
    return messages


def ask_ollama(prompt: str) -> str:
    """Generate response using Ollama local AI model with multi-turn context."""
    try:
        system_content = build_system_prompt(prompt)
        messages = _build_messages(prompt, system_content)

        response = ollama.chat(
            model=MODEL,
            messages=messages,
            options={
                "num_predict": 256,
                "temperature": 0.6,
                "keep_alive": "10m",
                "num_ctx": 4096,
            }
        )

        answer = response["message"]["content"]
        save_chat(prompt, answer)
        return answer

    except Exception as e:
        return f"Ollama error: {e}"


def ask_ollama_stream(prompt: str):
    """Stream response tokens incrementally with multi-turn context."""
    try:
        system_content = build_system_prompt(prompt)
        messages = _build_messages(prompt, system_content)

        response = ollama.chat(
            model=MODEL,
            messages=messages,
            options={
                "num_predict": 256,
                "temperature": 0.6,
                "keep_alive": "10m",
                "num_ctx": 4096,
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