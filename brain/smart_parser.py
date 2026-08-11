"""
ULTRON V3
Smart Command Parser
"""


def clean_command(command):
    command = command.lower().strip()

    protected_phrases = [
        "shutdown ultron", "exit ultron", "close ultron",
        "stop ultron", "quit ultron", "terminate ultron",
        "shutdown computer", "shutdown pc", "turn off computer",
        "turn off pc", "power off computer", "power off windows",
        "restart computer", "restart pc", "reboot computer", "reboot pc",
        "sign out", "log out windows", "lock computer", "lock pc",
        "factory reset", "system reset", "reset my computer",
        "reinstall windows", "restore factory settings",
        "format drive", "format disk", "format c drive", "format d drive",
        "delete all files", "delete files", "delete everything", "erase all files",
        "confirm reset", "confirm format", "confirm delete",
        "yes boss", "never mind", "telugu lo cheppu"
    ]

    for phrase in protected_phrases:
        if phrase in command:
            return command

    remove_words = [
        "please",
        "can you",
        "could you",
        "my",
        "naaku",
        "kavali",
        "cheyyi",
        "chey"
    ]

    for word in remove_words:
        command = command.replace(word, "")

    words = command.split()
    if "ultron" in words and len(words) > 1:
        words = [w for w in words if w != "ultron"]

    result = " ".join(words).strip()
    return result if result else command


def detect_language_intent(command: str):
    """
    Returns (input_lang, explicit_switch)
    input_lang: 'en' or 'te'
    explicit_switch: 'en' or 'te' if user explicitly asks to switch, else None
    """
    command = command.lower().strip()
    
    # Check explicit switch requests
    if any(x in command for x in ["speak english", "speak in english", "change your language to english", "switch to english", "english lo cheppu"]):
        return ("en", "en")
    
    if any(x in command for x in ["speak telugu", "speak in telugu", "change your language to telugu", "switch to telugu", "telugu lo cheppu", "telugu lo matladu"]):
        return ("te", "te")

    # Explicit English markers
    english_keywords = ["what is", "how are", "open", "close", "who is", "where is", "why", "when"]
    
    # Tanglish/Telugu heuristics
    telugu_keywords = [
        "nuvvu", "nenu", "ela", "unnav", "cheppu", "cheyyi", "undi", 
        "kavali", "vaddu", "avunu", "kadhu", "bagundi", "bagoledhu", 
        "cheppandi", "chey", "ekkada", "eppudu", "enduku", "emiti", 
        "entandi", "evaru", "meeku", "naaku", "vallu", "peru", "enti",
        "matladagalava", "ivvu", "chusi", "meeda", "lo"
    ]
    
    words = command.split()
    te_score = sum(1 for w in words if w in telugu_keywords)
    en_score = sum(1 for w in words if w in english_keywords)
    
    # "youtube open cheyyi" -> Mixed command, Tanglish dominant context
    if te_score > 0:
        return ("te", None)
        
    return ("en", None)


def detect_action(command):
    command = clean_command(command)

    # OPEN
    if "open" in command or "start" in command or "launch" in command or "teru" in command:
        return "OPEN"

    # CLOSE
    if "close" in command or "exit" in command or "muyyi" in command or "museti" in command:
        return "CLOSE"

    # SLEEP
    if "sleep" in command or "nidra" in command:
        return "SLEEP"

    # STOP
    if "stop" in command or "shutdown" in command or "aapu" in command:
        return "STOP"

    return "UNKNOWN"