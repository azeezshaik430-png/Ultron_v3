import time
import statistics
import sys
import os

# Add root directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from brain.orchestrator import orchestrator
from core.session import session

def run_benchmark():
    print("==================================================")
    print("ULTRON V3 - RESPONSE LATENCY BENCHMARK")
    print("==================================================")
    
    commands = [
        "What is Java?",
        "Hello Ultron",
        "What is AI?",
        "Tell me about AI agents",
        "Open YouTube",
        "Go back",
        "Play third video"
    ]
    
    results = {cmd: [] for cmd in commands}
    
    # Warmup
    print("Warming up...")
    try:
        orchestrator.process_command("wake up")
    except Exception:
        pass
        
    for _ in range(3):
        for cmd in commands:
            session.reset()
            t0 = time.perf_counter()
            try:
                res = orchestrator.process_command(cmd)
            except Exception as e:
                res = f"Error: {e}"
            t1 = time.perf_counter()
            duration_ms = (t1 - t0) * 1000
            results[cmd].append(duration_ms)
            print(f"Command '{cmd}' took {duration_ms:.2f}ms")
            
    print("\n==================================================")
    print("FINAL BENCHMARK REPORT (Total Response Latency)")
    print("==================================================")
    for cmd, times in results.items():
        if times:
            min_t = min(times)
            max_t = max(times)
            median_t = statistics.median(times)
            print(f"{cmd:<30} | Min: {min_t:>7.2f}ms | Median: {median_t:>7.2f}ms | Max: {max_t:>7.2f}ms")

if __name__ == "__main__":
    run_benchmark()
