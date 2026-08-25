"""
ULTRON V3
Memory Consolidation System

Provides automatic memory maintenance:
- Importance scoring for memories
- Stale memory detection and cleanup
- Duplicate/overlapping memory merging
- Memory size management
- Periodic consolidation trigger
"""

import time
import threading
from typing import Dict, Any, List, Tuple, Optional
from core.logger import logger


# Importance keywords that boost memory score
_HIGH_IMPORTANCE = {
    "name", "boss", "creator", "owner", "password", "api_key",
    "favorite", "important", "remember", "never forget", "always",
    "critical", "urgent", "project", "deadline", "meeting",
}

_LOW_IMPORTANCE = {
    "temp", "test", "example", "maybe", "sometimes", "might",
}


def score_memory(key: str, value: Any) -> float:
    """
    Score a memory entry's importance from 0.0 (least) to 1.0 (most).
    
    Scoring factors:
    - Key specificity (longer, more specific keys score higher)
    - Value richness (longer values with more info score higher)
    - Keyword presence (important keywords boost score)
    - Recency (newer memories score higher — caller should pass mtime)
    """
    key_lower = str(key).lower()
    value_str = str(value).lower()
    combined = f"{key_lower} {value_str}"

    score = 0.3  # Base score

    # Key specificity: longer, more specific keys are more important
    key_words = len(key_lower.split("_"))
    score += min(key_words * 0.05, 0.15)

    # Value richness
    if len(str(value)) > 20:
        score += 0.1
    if len(str(value)) > 50:
        score += 0.05

    # High importance keywords
    for word in _HIGH_IMPORTANCE:
        if word in combined:
            score += 0.15
            break

    # Low importance keywords
    for word in _LOW_IMPORTANCE:
        if word in key_lower:
            score -= 0.15
            break

    # Technical keys (likely more important)
    if any(k in key_lower for k in ["password", "api", "token", "key", "config", "setting"]):
        score += 0.2

    # Personal identity (always important)
    if any(k in key_lower for k in ["name", "boss", "owner", "creator"]):
        score += 0.2

    return max(0.0, min(1.0, score))


def find_duplicate_memories(memories: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """
    Find potentially duplicate/overlapping memory entries.
    Returns list of (key1, key2, reason) tuples.
    """
    duplicates = []
    keys = list(memories.keys())

    for i, k1 in enumerate(keys):
        v1 = str(memories[k1]).lower()
        for k2 in keys[i + 1:]:
            v2 = str(memories[k2]).lower()

            # Exact value match
            if v1 == v2 and k1 != k2:
                duplicates.append((k1, k2, "identical_values"))
                continue

            # Key containment (e.g., "favorite_color" and "fav_color")
            k1_words = set(k1.lower().replace("_", " ").split())
            k2_words = set(k2.lower().replace("_", " ").split())
            if k1_words == k2_words:
                duplicates.append((k1, k2, "identical_keys"))
                continue

            # Value containment
            if len(v1) > 5 and len(v2) > 5:
                if v1 in v2 or v2 in v1:
                    duplicates.append((k1, k2, "overlapping_values"))

    return duplicates


def consolidate_memories(
    memories: Dict[str, Any],
    max_entries: int = 200,
    min_importance: float = 0.15,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Consolidate memories by:
    1. Scoring all entries by importance
    2. Removing entries below min_importance threshold
    3. Merging duplicates (keeping higher-scored version)
    4. Trimming to max_entries if over limit

    Returns:
        (cleaned_memories, consolidation_report)
    """
    report = {
        "original_count": len(memories),
        "removed_low_importance": 0,
        "merged_duplicates": 0,
        "trimmed": 0,
        "final_count": 0,
    }

    # 1. Score all memories
    scored = {}
    for key, value in memories.items():
        s = score_memory(key, value)
        scored[key] = {"value": value, "score": s}

    # 2. Remove low importance
    cleaned = {}
    for key, data in scored.items():
        if data["score"] >= min_importance:
            cleaned[key] = data["value"]
        else:
            report["removed_low_importance"] += 1
            logger.debug(
                f"[MemoryConsolidator] Removed low-importance memory: '{key}' "
                f"(score: {data['score']:.2f})"
            )

    # 3. Merge duplicates (keep higher-scored version)
    duplicates = find_duplicate_memories(cleaned)
    removed_keys = set()
    for k1, k2, reason in duplicates:
        if k1 in removed_keys or k2 in removed_keys:
            continue
        s1 = scored.get(k1, {}).get("score", 0)
        s2 = scored.get(k2, {}).get("score", 0)
        # Remove the lower-scored duplicate
        loser = k2 if s1 >= s2 else k1
        removed_keys.add(loser)
        report["merged_duplicates"] += 1
        logger.debug(
            f"[MemoryConsolidator] Merged duplicate: removed '{loser}' "
            f"(kept {'{k1}' if loser == k2 else '{k2}'}, reason: {reason})"
        )

    for k in removed_keys:
        cleaned.pop(k, None)

    # 4. Trim to max_entries if over limit
    if len(cleaned) > max_entries:
        # Sort by importance and keep top entries
        sorted_items = sorted(
            cleaned.items(),
            key=lambda x: scored.get(x[0], {}).get("score", 0),
            reverse=True,
        )
        trimmed_count = len(cleaned) - max_entries
        cleaned = dict(sorted_items[:max_entries])
        report["trimmed"] = trimmed_count
        logger.info(
            f"[MemoryConsolidator] Trimmed {trimmed_count} memories "
            f"to stay under {max_entries} limit"
        )

    report["final_count"] = len(cleaned)
    return cleaned, report


def auto_consolidate() -> Optional[Dict[str, Any]]:
    """
    Run automatic memory consolidation on brain.memory.
    Returns consolidation report or None if no action needed.
    """
    try:
        from brain.memory import load_memory, save_memory

        memories = load_memory()
        if not memories:
            return None

        original_count = len(memories)
        cleaned, report = consolidate_memories(memories)

        # Only save if something changed
        if cleaned != memories:
            save_memory(cleaned)
            logger.info(
                f"[MemoryConsolidator] Auto-consolidation complete: "
                f"{report['original_count']} → {report['final_count']} memories "
                f"(removed: {report['removed_low_importance']}, "
                f"merged: {report['merged_duplicates']}, "
                f"trimmed: {report['trimmed']})"
            )
            return report
        else:
            logger.debug("[MemoryConsolidator] No consolidation needed.")
            return None

    except Exception as e:
        logger.error(f"[MemoryConsolidator] Auto-consolidation error: {e}")
        return None


class MemoryConsolidationScheduler:
    """
    Background scheduler that periodically runs memory consolidation.
    """

    def __init__(self, interval_minutes: int = 60):
        self._interval = interval_minutes * 60
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_consolidation: float = 0.0

    def start(self) -> None:
        """Start the background consolidation scheduler."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="MemoryConsolidator",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"[MemoryConsolidator] Scheduler started "
            f"(interval: {self._interval // 60} minutes)"
        )

    def stop(self) -> None:
        """Stop the consolidation scheduler."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("[MemoryConsolidator] Scheduler stopped.")

    def consolidate_now(self) -> Optional[Dict[str, Any]]:
        """Trigger immediate consolidation."""
        self._last_consolidation = time.time()
        return auto_consolidate()

    def _loop(self) -> None:
        """Background loop running consolidation at intervals."""
        while not self._stop_event.is_set():
            self._stop_event.wait(self._interval)
            if self._stop_event.is_set():
                break

            try:
                report = auto_consolidate()
                if report:
                    self._last_consolidation = time.time()
            except Exception as e:
                logger.error(f"[MemoryConsolidator] Scheduler error: {e}")


# Global singleton
memory_consolidator = MemoryConsolidationScheduler()
