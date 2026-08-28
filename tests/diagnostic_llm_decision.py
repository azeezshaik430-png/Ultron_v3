"""
READ-ONLY Diagnostic: LLM Decision Quality Test
Tests the EXACT decision prompt from computer_use._decide()
against the current desktop OCR output. 3 trials, no actions executed.
"""
import sys
import os
import time
import json
import re

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from brain.llm_manager import llm_manager
from PIL import ImageGrab
from core.computer_use import _fallback_ocr

# 1. Capture fresh screenshot
print("STEP 1: Capturing fresh 1920x1080 desktop...")
img = ImageGrab.grab()
print(f"  Resolution: {img.size[0]}x{img.size[1]}")

# 2. Run OCR
print("\nSTEP 2: Running OCR...")
screen_text = _fallback_ocr(img)
print(f"  OCR length: {len(screen_text)} chars")
print(f"  Full OCR text:")
print(f"  ---BEGIN OCR---")
print(f"  {screen_text}")
print(f"  ---END OCR---")

# 3. Build the EXACT prompt from _decide()
task = "Open Calculator"
iteration = 1
prompt = (
    f"You are ULTRON controlling a computer. Current task: '{task}'\n"
    f"Screen OCR text (iteration {iteration}):\n{screen_text[:800]}\n\n"
    f'Decide the NEXT action. Respond with ONLY a JSON object:\n'
    f'{{"action_type": "click"|"type"|"scroll"|"wait"|"done"|"fail",\n'
    f' "details": "description of what to do",\n'
    f' "x": null, "y": null}}\n'
    f'If the task appears complete, use action_type "done".\n'
    f'If you cannot determine what to do, use "fail".\n'
    f'If no action needed yet, use "wait".'
)

print(f"\nSTEP 3: EXACT PROMPT SENT TO OLLAMA:")
print(f"{'='*60}")
print(prompt)
print(f"{'='*60}")

# 4. Send 3 trials
results = []
for trial in range(1, 4):
    print(f"\n{'='*60}")
    print(f"TRIAL {trial}/3")
    print(f"{'='*60}")
    t0 = time.time()
    response = llm_manager.ask(prompt)
    elapsed = time.time() - t0
    print(f"  Response time: {elapsed:.1f}s")
    print(f"  Raw response:")
    print(f"  {response}")

    # Parse JSON
    json_match = re.search(r'\{[^}]+\}', response)
    parsed = None
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            print(f"\n  PARSED:")
            print(f"    action_type: {parsed.get('action_type')}")
            print(f"    details:     {parsed.get('details')}")
            print(f"    x:           {parsed.get('x')}")
            print(f"    y:           {parsed.get('y')}")
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
    else:
        print(f"  No JSON found in response")

    results.append({
        "trial": trial,
        "elapsed": elapsed,
        "raw": response,
        "parsed": parsed,
    })

# 5. Summary
print(f"\n{'='*60}")
print("DIAGNOSTIC SUMMARY")
print(f"{'='*60}")
print(f"Screen: {img.size[0]}x{img.size[1]}")
print(f"OCR chars: {len(screen_text)}")
print(f"Task: {task}")
print(f"Model: llama3.2:3b")
print()

for r in results:
    p = r["parsed"] or {}
    print(f"  Trial {r['trial']}: action={p.get('action_type','?')}, "
          f"x={p.get('x')}, y={p.get('y')}, "
          f"details='{str(p.get('details',''))[:60]}'")

print(f"\nANALYSIS:")
print(f"  A. Does OCR contain Calculator info?")
calc_in_ocr = "calc" in screen_text.lower()
calc_msg = 'FOUND in OCR' if calc_in_ocr else 'NOT found in OCR'
print(f"     {calc_msg}")

print(f"  B. Does prompt include screen dimensions?")
print(f"     NO — prompt contains zero coordinate reference points")

print(f"  C. Does model understand the goal?")
actions = [r["parsed"].get("action_type") if r["parsed"] else "?" for r in results]
print(f"     Actions chosen: {actions}")

coords = [(r["parsed"].get("x"), r["parsed"].get("y")) for r in results if r["parsed"]]
print(f"  D. Coordinates: {coords}")

all_zero = all(x == 0 and y == 0 for x, y in coords) if coords else False
all_null = all(x is None and y is None for x, y in coords) if coords else False
print(f"  E. All (0,0): {all_zero} | All null: {all_null}")
