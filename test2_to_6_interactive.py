r"""
ULTRON VOICE PHYSICAL DIAGNOSTIC -- TESTS 2 through 6
Run from ULTRON_V3 directory with:
    .\ultron_env\Scripts\Activate.ps1
    $env:VOICE_AUTH_ENABLED="false"
    python test2_to_6_interactive.py

Speak CLEARLY into microphone when prompted.
Report the EXACT output of each test.
"""
import sys, os, time, threading
from pathlib import Path

# Ensure project root is in sys.path using pathlib
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["VOICE_AUTH_ENABLED"] = "false"

import speech_recognition as sr
from core.logger import logger

recognizer = sr.Recognizer()

def separator(n, label):
    print()
    print("=" * 60)
    print(f"  TEST {n} — {label}")
    print("=" * 60)

def wait_for_user(prompt, seconds=8):
    print(f"\n  >>> {prompt} <<< ({seconds}s)")
    time.sleep(0.5)  # give user time to read

# ─────────────────────────────────────────────────────────
# TEST 2 — MICROPHONE ONLY
# ─────────────────────────────────────────────────────────
separator(2, "MICROPHONE ONLY")
wait_for_user("Speak any word NOW", 8)

from voice.speech_input import listen as ultron_listen
print("  LISTEN START")
result = ultron_listen()
print(f"  RESULT: {repr(result)}")
if result:
    print("  TEST 2: PASS — microphone captured speech")
else:
    print("  TEST 2: FAIL — listen() returned empty string")
    print("  Possible causes: WaitTimeoutError / UnknownValueError / RequestError")
    print("  (check ULTRON log above for the actual exception)")

# ─────────────────────────────────────────────────────────
# TEST 3 — WAKE LISTENER ONLY
# ─────────────────────────────────────────────────────────
separator(3, "WAKE LISTENER ONLY")
wait_for_user("Say 'Hey Ultron' NOW", 8)

from voice.wake_word import check_wake_word
print("  LISTEN START (silent mode)")
cmd = ultron_listen(silent=True)
print(f"  heard: {repr(cmd)}")
wake = check_wake_word(cmd) if cmd else False
print(f"  WAKE DETECTED: {wake}")
if wake:
    print("  TEST 3: PASS")
elif cmd:
    print(f"  TEST 3: PARTIAL — microphone heard '{cmd}' but wake word not matched")
else:
    print("  TEST 3: FAIL — microphone returned empty")

# ─────────────────────────────────────────────────────────
# TEST 4 — TTS THEN MICROPHONE (no interruption)
# ─────────────────────────────────────────────────────────
separator(4, "TTS THEN MICROPHONE — interruption DISABLED")
# Temporarily disable interruption listener
import voice.speech_input as _si
_orig_start = _si.start_interruption_listener
_orig_stop  = _si.stop_interruption_listener
_si.start_interruption_listener = lambda: print("  [INTERRUPTION] disabled for test 4")
_si.stop_interruption_listener  = lambda: None

from voice.speech_output import speak as ultron_speak
print("  TTS START — listen for 'Voice output test four' from speaker")
t0 = time.perf_counter()
ok = ultron_speak("Voice output test four.")
elapsed = (time.perf_counter() - t0) * 1000
print(f"  TTS END  result={ok}  elapsed={elapsed:.0f}ms")
if elapsed < 500:
    print("  WARNING: TTS completed too fast — audio likely NOT played")

_si.start_interruption_listener = _orig_start
_si.stop_interruption_listener  = _orig_stop

wait_for_user("TTS done. Now speak any word into mic", 8)
print("  LISTEN START")
r2 = ultron_listen()
print(f"  RESULT: {repr(r2)}")
if ok and r2:
    print("  TEST 4: PASS — TTS played AND microphone captured")
elif not ok:
    print("  TEST 4: FAIL — TTS did not complete successfully")
else:
    print("  TEST 4: FAIL — microphone returned empty after TTS")

# ─────────────────────────────────────────────────────────
# TEST 5 — MICROPHONE THEN TTS THEN MICROPHONE
# ─────────────────────────────────────────────────────────
separator(5, "MICROPHONE → TTS → MICROPHONE")
_si.start_interruption_listener = lambda: print("  [INTERRUPTION] disabled for test 5")
_si.stop_interruption_listener  = lambda: None

wait_for_user("Speak any word (first command)", 8)
print("  LISTEN START (1)")
c1 = ultron_listen()
print(f"  Command 1: {repr(c1)}")

print("  TTS START")
t0 = time.perf_counter()
ultron_speak(f"You said {c1}." if c1 else "Nothing heard.")
elapsed = (time.perf_counter() - t0) * 1000
print(f"  TTS END  elapsed={elapsed:.0f}ms")

wait_for_user("TTS done. Speak second word", 8)
print("  LISTEN START (2)")
c2 = ultron_listen()
print(f"  Command 2: {repr(c2)}")

_si.start_interruption_listener = _orig_start
_si.stop_interruption_listener  = _orig_stop

if c1 and c2:
    print("  TEST 5: PASS — full mic→TTS→mic cycle worked")
elif c1 and not c2:
    print("  TEST 5: FAIL — microphone stopped working AFTER TTS")
elif not c1:
    print("  TEST 5: FAIL — first microphone capture failed")

# ─────────────────────────────────────────────────────────
# TEST 6 — WITHOUT INTERRUPTION: Hey Ultron → Hello → Hello again
# ─────────────────────────────────────────────────────────
separator(6, "WITHOUT INTERRUPTION — Hey Ultron → Hello → Hello again")
_si.start_interruption_listener = lambda: print("  [INTERRUPTION] disabled for test 6")
_si.stop_interruption_listener  = lambda: None

wait_for_user("Say 'Hey Ultron'", 8)
cmd = ultron_listen(silent=True)
print(f"  heard: {repr(cmd)}")
wake = check_wake_word(cmd) if cmd else False
print(f"  wake detected: {wake}")

if wake:
    ultron_speak("What can I do for you, Boss?")
    
    wait_for_user("Say 'Hello'", 8)
    cmd2 = ultron_listen()
    print(f"  Command: {repr(cmd2)}")
    
    if cmd2:
        ultron_speak(f"You said {cmd2}.")
        
        wait_for_user("Say 'Hello again'", 8)
        cmd3 = ultron_listen()
        print(f"  Command 2: {repr(cmd3)}")
        
        if cmd3:
            print("  TEST 6: PASS — full pipeline worked WITHOUT interruption listener")
            print("  IF TEST 6 PASSES BUT normal ULTRON fails: ROOT CAUSE = interruption architecture")
        else:
            print("  TEST 6: FAIL at 3rd listen()")
    else:
        print("  TEST 6: FAIL at 2nd listen() after TTS")
else:
    print("  TEST 6: FAIL — wake word not detected")

_si.start_interruption_listener = _orig_start
_si.stop_interruption_listener  = _orig_stop

print()
print("=" * 60)
print("ALL TESTS COMPLETE")
print("Copy and paste the entire output above and report it.")
print("=" * 60)
