# ULTRON V3 — Autonomous AI Personal Voice Assistant

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Architecture](https://img.shields.io/badge/Architecture-Modular%20Event--Driven-orange.svg)
![Security](https://img.shields.io/badge/Security-Strict%20Confirmation-red.svg)

**ULTRON V3** is an ultra-fast, local-first personal AI desktop assistant designed for Windows. Built with an event-driven architecture, ULTRON V3 integrates voice recognition, intelligent intent parsing, local memory management, skill execution modules, and local LLM fallbacks (Ollama / Llama 3) with zero latency.

---

## 🌟 Key Features

- 🔒 **Zero-Trust Security Confirmation Flow**: Strict, multi-step validation for system actions (Windows Shutdown, Restart, Lock PC, Sign Out) with a 15-second timeout, cancellation handling, and audit logging (`logs/security.log`).
- 🎙️ **Offline & Online Voice Processing**: Built-in wake-word detection (`Hey Ultron`), speech-to-text listener, and fast offline TTS speech output (`pyttsx3`).
- 🧠 **Smart Memory Engine**: Automatic context extraction and persistent personal memory without unnecessary LLM calls.
- ⚡ **Local LLM Fallback (Ollama)**: Local intelligence powered by `llama3.2:3b` for general conversational queries and complex reasoning.
- 🎛️ **Windows Control & App Automation**: Deep OS automation for opening/closing desktop apps, controlling system volumes, searching files, and managing system settings.
- 🧩 **Modular Plugin & Agent Framework**: Dynamic agent registry and plugin loader supporting modular extensions.

---

## 🏗️ Architecture

ULTRON V3 follows a strict unidirectional pipeline:

```
User Voice Input
       │
       ▼
Wake Word Listener
       │
       ▼
Speech-to-Text Parser ─── (smart_parser.py)
       │
       ▼
Central Orchestrator ──── (brain/orchestrator.py)
       │
       ├─► Security Guard & Pending Confirmation Validation
       ├─► Personal Memory Recall (zero-latency local memory)
       ├─► Skill Routing (skills/windows_control.py, app_control.py, etc.)
       └─► LLM Manager Fallback (Ollama / Llama 3)
       │
       ▼
Speech Synthesis (TTS) ── (voice/speech_output.py)
```

---

## 📁 Repository Structure

```
ULTRON_V3/
├── agents/             # Autonomous subagent registry and definitions
├── brain/              # Core brain orchestrator, planner, router, & smart parser
│   ├── llm_manager.py  # Universal LLM dispatcher (Ollama)
│   ├── memory.py       # Persistent key-value memory system
│   ├── orchestrator.py # Master brain controller & security validation
│   ├── planner.py      # Task planning framework
│   ├── router.py       # Universal intent router
│   ├── smart_memory.py # Memory extraction engine
│   └── smart_parser.py # Sanitizer & protected phrase parser
├── core/               # System foundation
│   ├── config.py       # Central dataclass configuration
│   ├── event_bus.py    # Pub/Sub event bus
│   ├── logger.py       # Thread-safe rotating logger
│   └── session.py      # Thread-safe session manager & confirmation state
├── data/               # App databases & system aliases
│   ├── aliases.json    # Application launch aliases
│   └── apps.json       # Discovered executable paths
├── marketplace/        # External plugin & extension marketplace
├── plugins/            # Runtime plugin modules & loader
├── skills/             # Production skills
│   ├── app_control.py  # Application launcher/closer
│   ├── app_scanner.py  # System executable indexer
│   ├── file_manager.py # Explorer directory navigation
│   ├── search_files.py # System file search
│   ├── system_control.py# Battery, date, time, system status
│   ├── volume_control.py# Master Windows audio control
│   └── windows_control.py# Locked OS control & guarded shutdown
├── voice/              # Speech I/O modules
│   ├── speech_input.py # Speech-to-text listener
│   ├── speech_output.py# Offline pyttsx3 text-to-speech engine
│   └── wake_listener.py# Wake word detection engine
├── main.py             # System entry point & master execution loop
├── test_phase1_runtime.py# Comprehensive runtime verification test suite
├── requirements.txt    # Project dependencies
├── .gitignore          # Repository exclusion rules
├── LICENSE             # MIT Open Source License
└── README.md           # Documentation
```

---

## ⚙️ Requirements & Prerequisites

- **Operating System**: Windows 10 / Windows 11
- **Python**: Python 3.10+
- **Ollama**: [Ollama for Windows](https://ollama.com/) (Required for local LLM fallback)
  - Download model: `ollama run llama3.2:3b`

---

## 🚀 Quick Start & Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/azeezshaik430-png/Ultron_v3.git
   cd Ultron_v3
   ```

2. **Create & Activate Virtual Environment**:
   ```powershell
   python -m venv ultron_env
   .\ultron_env\Scripts\Activate.ps1
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify Runtime Core & Security**:
   ```bash
   python test_phase1_runtime.py
   ```

5. **Launch ULTRON V3**:
   ```bash
   python main.py
   ```

---

## 🛡️ Windows Shutdown Confirmation Security Specification

ULTRON V3 guarantees **ZERO** unconfirmed Windows OS shutdowns:

1. **Trigger Phrase**: Saying `"Shutdown PC"` or `"Turn off computer"` will **NEVER** execute shutdown immediately.
2. **Speech Response**:
   > *"Are you sure, Boss? You requested to shut down your computer. Please say 'Yes' to continue or 'Cancel' to abort."*
3. **Confirmation Options**:
   - **Confirm**: Saying `"Yes"`, `"Yes Boss"`, `"Confirm"`, `"Continue"`, or `"Proceed"` triggers shutdown after confirmation speech:
     > *"Confirmation received. Shutting down your computer. Goodbye, Boss."*
   - **Cancel**: Saying `"No"`, `"Cancel"`, `"Stop"`, or `"Never mind"` cancels the request.
   - **Unrelated Command**: Saying any other command (e.g. `"Open Chrome"`) immediately cancels pending shutdown and executes the new command.
   - **Timeout**: If no response is received within 15 seconds, the request times out automatically.

---

## 🗺️ Roadmap

- [x] Phase 1 Core Brain, Security Guard, & Windows Automation
- [x] Phase 2 Offline Voice I/O & Memory Engine
- [ ] Phase 3 GUI Dashboard & Real-Time Voice Waveform Interface
- [ ] Phase 4 Multi-Agent Autonomous Workflow Pipeline

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
