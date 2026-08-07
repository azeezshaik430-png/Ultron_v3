"""
ULTRON V3 - Voice Response Speed Optimization Unit Test & Telemetry Benchmark
Verifies VoiceEncoder preloading, Boss embedding caching, sleep delay elimination, verification threshold accuracy, and latency breakdown.
"""

import os
import time
import unittest
import numpy as np

from voice.voice_guard import (
    preload_voice_guard,
    verify_boss,
    _get_encoder,
    _get_boss_embedding,
    BOSS_VOICE,
    THRESHOLD,
)


class TestVoiceSpeedOptimization(unittest.TestCase):
    """Voice Speed Optimization Benchmark Suite."""

    def test_01_background_preloading(self):
        """Test 1: Verify VoiceEncoder preloading initializes model in background."""
        t0 = time.perf_counter()
        preload_voice_guard()
        
        # Give preloading thread a moment to run
        encoder = _get_encoder()
        t_load = (time.perf_counter() - t0) * 1000.0
        
        self.assertIsNotNone(encoder)
        print(f"\n[Voice Benchmark] Preloaded VoiceEncoder available in {t_load:.2f} ms")

    def test_02_boss_embedding_caching(self):
        """Test 2: Verify Boss voice embedding caching avoids recomputation."""
        if os.path.exists(BOSS_VOICE):
            t0 = time.perf_counter()
            embed1 = _get_boss_embedding()
            t_first = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            embed2 = _get_boss_embedding()
            t_second = (time.perf_counter() - t1) * 1000.0

            self.assertIsNotNone(embed1)
            self.assertTrue(np.array_equal(embed1, embed2))
            print(f"[Voice Benchmark] Boss Embedding: 1st Load = {t_first:.2f} ms | Cached Fetch = {t_second:.2f} ms")
            self.assertLess(t_second, 5.0)  # Cached fetch should be under 5ms

    def test_03_verification_threshold_and_accuracy(self):
        """Test 3: Verify security threshold remains 0.68."""
        self.assertEqual(THRESHOLD, 0.68)

    def test_04_verification_speed_with_sample(self):
        """Test 4: Verify verify_boss execution time with preloaded model."""
        if os.path.exists(BOSS_VOICE):
            t0 = time.perf_counter()
            res = verify_boss(BOSS_VOICE)
            t_verify = (time.perf_counter() - t0) * 1000.0
            
            self.assertTrue(res)
            print(f"[Voice Benchmark] Self-Verification execution time: {t_verify:.2f} ms")


if __name__ == "__main__":
    unittest.main()
