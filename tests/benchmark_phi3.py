"""
READ-ONLY BENCHMARK: phi3:3.8b on Computer-Use task
No production code modified. Calls Ollama API directly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama
import time
import psutil
import re
import json
import pygetwindow as gw
from PIL import ImageGrab

TASK = "Open Calculator and calculate 123 + 456"
SCREEN_W, SCREEN_H = 1920, 1080
MAX_RESPONSES = 10
HARD_TIMEOUT = 180  # 3 minutes
NO_PROGRESS_TIMEOUT = 30

def build_prompt(screen_text, iteration):
    return (
        f"You are ULTRON controlling a computer.\n"
        f"Screen: {SCREEN_W}x{SCREEN_H} pixels. Coordinate origin: top-left (0,0).\n"
        f"Valid coordinates: 0 <= x < {SCREEN_W}, 0 <= y < {SCREEN_H}.\n"
        f"NEVER use (0,0) unless you literally mean the top-left pixel.\n\n"
        f"Current task: '{TASK}'\n"
        f"Screen OCR text (iteration {iteration}):\n{screen_text[:800]}\n\n"
        f'Decide the NEXT action. Respond with ONLY a JSON object:\n'
        f'{{"action_type": "click"|"type"|"key_press"|"scroll"|"wait"|"done"|"fail",'
        f' "details": "description", "x": number_or_null, "y": number_or_null}}\n'
        f'For key_press: use details like "win", "enter", "escape", "tab".\n'
        f'For type: put the text to type in details.\n'
        f'If the task appears complete, use action_type "done".\n'
        f'If you cannot determine what to do, use "fail".\n'
        f'If no action needed yet, use "wait".\n'
        f'You may also return a "plan" array for multi-step sequences.'
    )

def parse_response(raw):
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None

def execute_action(action):
    """Execute an action via ctypes (no pyautogui dependency)."""
    import ctypes
    user32 = ctypes.windll.user32
    action_type = action.get("action_type", "")

    if action_type == "click":
        x, y = int(action.get("x", 0)), int(action.get("y", 0))
        if x == 0 and y == 0:
            return "SKIPPED (0,0)"
        user32.SetCursorPos(x, y)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        return f"click({x},{y})"

    elif action_type == "type":
        text = action.get("details", "")
        for char in text:
            user32.keybd_event(0, ord(char.upper()), 0x0004, 0)
            user32.keybd_event(0, ord(char.upper()), 0x0004 | 0x0002, 0)
        return f"type('{text}')"

    elif action_type == "key_press":
        key = action.get("details", "").lower()
        key_map = {"win": 0x5B, "enter": 0x0D, "escape": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08}
        vk = key_map.get(key)
        if vk is not None:
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            return f"key_press({key})"
        return f"key_press({key}) UNKNOWN"

    elif action_type == "wait":
        return "wait"

    elif action_type == "scroll":
        return "scroll"

    return f"unknown({action_type})"


def main():
    print("=" * 60)
    print("PHI3:3.8b COMPUTER-USE BENCHMARK")
    print(f"Task: {TASK}")
    print("=" * 60)

    # Clean state
    calc = [w for w in gw.getAllWindows() if w.title and "calc" in w.title.lower()]
    if calc:
        calc[0].close()
        time.sleep(1)

    ram_start = psutil.virtual_memory().used / (1024**3)
    task_start = time.time()
    last_progress_time = task_start
    actions_taken = []
    llm_latencies = []
    calculator_opened = False
    calculation_entered = False
    result_579 = False

    # Capture initial screenshot
    img = ImageGrab.grab()
    screen_w, screen_h = img.size

    # OCR
    from core.computer_use import _fallback_ocr
    screen_text = _fallback_ocr(img)

    for iteration in range(1, MAX_RESPONSES + 1):
        elapsed = time.time() - task_start
        if elapsed > HARD_TIMEOUT:
            print(f"\n[HARD TIMEOUT] {elapsed:.0f}s > {HARD_TIMEOUT}s")
            break

        # Check no-progress timeout
        if time.time() - last_progress_time > NO_PROGRESS_TIMEOUT:
            print(f"\n[NO PROGRESS] {NO_PROGRESS_TIMEOUT}s without action")
            break

        # LLM call
        prompt = build_prompt(screen_text, iteration)
        print(f"\n--- Iteration {iteration}/{MAX_RESPONSES} ({elapsed:.1f}s) ---")

        t_llm = time.time()
        try:
            response = ollama.chat(model="phi3:3.8b", messages=[{"role": "user", "content": prompt}])
            raw = response.get("message", {}).get("content", "")
        except Exception as e:
            print(f"  LLM ERROR: {e}")
            break
        llm_latency = time.time() - t_llm
        llm_latencies.append(llm_latency)

        parsed = parse_response(raw)
        if not parsed:
            print(f"  Could not parse: {raw[:150]}")
            continue

        action_type = parsed.get("action_type", "?")
        details = parsed.get("details", "")
        plan = parsed.get("plan", [])

        print(f"  LLM response: {llm_latency:.1f}s")
        print(f"  action: {action_type} | details: {str(details)[:60]}")

        # Handle done/fail
        if action_type == "done":
            print(f"  TASK COMPLETE: {details}")
            break
        if action_type == "fail":
            print(f"  TASK FAILED: {details}")
            break

        # Execute plan steps if present
        if plan and isinstance(plan, list):
            print(f"  PLAN: {len(plan)} steps")
            for pi, step in enumerate(plan):
                result = execute_action(step)
                actions_taken.append({"iter": iteration, "action": step.get("action_type"), "result": result})
                print(f"    Step {pi+1}: {result}")
                last_progress_time = time.time()
                time.sleep(0.5)

        # Execute current action
        result = execute_action(parsed)
        actions_taken.append({"iter": iteration, "action": action_type, "result": result})
        print(f"  EXEC: {result}")
        last_progress_time = time.time()

        # Brief delay
        time.sleep(0.5)

        # Re-capture screen for next iteration
        img = ImageGrab.grab()
        screen_text = _fallback_ocr(img)

        # Check if Calculator opened
        calc = [w for w in gw.getAllWindows() if w.title and "calc" in w.title.lower()]
        if calc and not calculator_opened:
            calculator_opened = True
            print(f"  ** CALCULATOR OPENED **")
            last_progress_time = time.time()

        # Check for 579 in OCR
        if "579" in screen_text:
            result_579 = True
            calculation_entered = True
            print(f"  ** RESULT 579 FOUND IN OCR **")

        # Check for calculation tokens
        if any(t in screen_text for t in ["123", "456", "+"]):
            if calculator_opened:
                calculation_entered = True

    # --- RESULTS ---
    total_time = time.time() - task_start
    ram_end = psutil.virtual_memory().used / (1024**3)
    avg_latency = sum(llm_latencies) / len(llm_latencies) if llm_latencies else 0

    print(f"\n{'='*60}")
    print(f"PHI3:3.8b BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"Total time:       {total_time:.1f}s")
    print(f"Iterations:       {len(actions_taken)}/{MAX_RESPONSES}")
    print(f"LLM calls:        {len(llm_latencies)}")
    print(f"Avg LLM latency:  {avg_latency:.1f}s")
    print(f"RAM delta:        +{ram_end - ram_start:.1f} GB ({ram_start:.1f} -> {ram_end:.1f} GB)")
    print(f"Calculator open:  {'YES' if calculator_opened else 'NO'}")
    print(f"Calc entered:     {'YES' if calculation_entered else 'NO'}")
    print(f"Result 579:       {'YES' if result_579 else 'NO'}")
    print(f"\nActions:")
    for a in actions_taken:
        print(f"  Iter {a['iter']}: {a['action']:12s} -> {a['result']}")

    # Clean up
    calc = [w for w in gw.getAllWindows() if w.title and "calc" in w.title.lower()]
    if calc:
        calc[0].close()
        print("\nCalculator closed.")


if __name__ == "__main__":
    main()
