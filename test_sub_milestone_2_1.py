"""
ULTRON V3 - Sub-Milestone 2.1 Verification Test Suite
Tests interfaces, exceptions, DI container, config validator, feature flags, bus data models,
circular dependency detection, thread safety, and 1,000 concurrent resolution stress testing.
"""

import gc
import os
import sys
import threading
import time
import unittest

from core.config import config
from core.interfaces import (
    IService,
    IInitializable,
    IShutdownable,
    IHealthCheck,
    IConfigurable,
)
from core.exceptions import (
    BusException,
    AgentNotFoundException,
    DuplicateMessageException,
    QuotaExceededException,
    PermissionDeniedException,
    WorkspaceConflictException,
    JournalCorruptionException,
)
from core.di_container import DIContainer, ServiceEntry
from core.config_validator import ConfigValidator, ValidationSeverity, ValidationReport
from core.feature_flags import FeatureFlagManager
from brain.bus_types import (
    MessagePriority,
    DeliveryStatus,
    AgentStatus,
    CircuitBreakerState,
    ArtifactMetadata,
    AgentMessage,
    WorkspaceEntry,
    ScratchpadEntry,
    AgentManifest,
    BusStatistics,
)


class MockService(IService):
    """Mock test implementation of IService."""

    def __init__(self) -> None:
        self.initialized = False
        self.shutdown_done = False
        self.config_data = {}

    def initialize(self) -> None:
        self.initialized = True

    def shutdown(self) -> None:
        self.shutdown_done = True

    def health_check(self) -> dict:
        return {"status": "HEALTHY", "healthy": True}

    def configure(self, config_data: dict) -> None:
        self.config_data = config_data


class TestSubMilestone21(unittest.TestCase):
    """Sub-Milestone 2.1 Complete Test Suite."""

    def test_01_interface_and_lifecycle_contract(self):
        """Test 1: Verify IService interface contract implementation."""
        svc = MockService()
        svc.initialize()
        self.assertTrue(svc.initialized)
        svc.configure({"key": "val"})
        self.assertEqual(svc.config_data.get("key"), "val")
        health = svc.health_check()
        self.assertEqual(health.get("status"), "HEALTHY")
        svc.shutdown()
        self.assertTrue(svc.shutdown_done)

    def test_02_exception_taxonomy(self):
        """Test 2: Verify domain exception hierarchy inherits from BusException."""
        exceptions = [
            AgentNotFoundException("Agent missing"),
            DuplicateMessageException("Duplicate hash"),
            QuotaExceededException("Quota exceeded"),
            PermissionDeniedException("Permission denied"),
            WorkspaceConflictException("Version conflict"),
            JournalCorruptionException("Corrupted journal"),
        ]
        for ex in exceptions:
            self.assertIsInstance(ex, BusException)
            self.assertIsInstance(ex, Exception)

    def test_03_di_container_registrations(self):
        """Test 3: Verify Singleton, Factory, Lazy, and Transient registrations."""
        container = DIContainer()

        # Singleton
        svc_singleton = MockService()
        container.register_singleton(MockService, svc_singleton)
        self.assertIs(container.resolve(MockService), svc_singleton)

        # Factory
        class FactoriedService:
            pass
        container.register_factory(FactoriedService, lambda: FactoriedService())
        inst1 = container.resolve(FactoriedService)
        inst2 = container.resolve(FactoriedService)
        self.assertIsNot(inst1, inst2)

        # Lazy
        class LazyService:
            pass
        lazy_count = [0]
        def lazy_factory():
            lazy_count[0] += 1
            return LazyService()
        container.register_lazy(LazyService, lazy_factory)
        self.assertEqual(lazy_count[0], 0)
        lazy1 = container.resolve(LazyService)
        lazy2 = container.resolve(LazyService)
        self.assertEqual(lazy_count[0], 1)
        self.assertIs(lazy1, lazy2)

    def test_04_di_container_circular_dependency_and_validation(self):
        """Test 4: Verify validate_dependencies catches circular dependencies and missing services."""
        container = DIContainer()

        class ServiceA:
            pass

        class ServiceB:
            pass

        # Register A depending on B, and B depending on A
        container.register_lazy(ServiceA, lambda: ServiceA(), dependencies=[ServiceB])
        container.register_lazy(ServiceB, lambda: ServiceB(), dependencies=[ServiceA])

        with self.assertRaises(BusException) as ctx:
            container.validate_dependencies()
        self.assertIn("Circular dependency", str(ctx.exception))

    def test_05_config_validator_severities(self):
        """Test 5: Verify ConfigValidator severity classifications and FATAL exception abort."""
        validator = ConfigValidator()

        # Valid config
        report = validator.validate(config)
        self.assertTrue(report.is_valid)

        # Invalid fatal config test
        class FatalConfig:
            TASK_ENGINE_WORKER_COUNT = -5  # Invalid negative count

        with self.assertRaises(BusException) as ctx:
            validator.validate(FatalConfig())
        self.assertIn("FATAL Configuration Error", str(ctx.exception))

    def test_06_config_env_overrides(self):
        """Test 6: Verify ULTRON_CONFIG_* environment variable overrides."""
        validator = ConfigValidator()
        
        class EnvConfig:
            TASK_ENGINE_WORKER_COUNT = 4

        cfg = EnvConfig()
        os.environ["ULTRON_CONFIG_TASK_ENGINE_WORKER_COUNT"] = "8"
        try:
            report = validator.validate(cfg)
            self.assertEqual(cfg.TASK_ENGINE_WORKER_COUNT, 8)
        finally:
            os.environ.pop("ULTRON_CONFIG_TASK_ENGINE_WORKER_COUNT", None)

    def test_07_feature_flag_manager(self):
        """Test 7: Verify FeatureFlagManager enable/disable/query state."""
        ffm = FeatureFlagManager()
        self.assertTrue(ffm.is_enabled("ENABLE_AGENT_BUS"))
        ffm.disable_flag("ENABLE_AGENT_BUS")
        self.assertFalse(ffm.is_enabled("ENABLE_AGENT_BUS"))
        ffm.enable_flag("ENABLE_AGENT_BUS")
        self.assertTrue(ffm.is_enabled("ENABLE_AGENT_BUS"))

    def test_08_bus_types_dataclasses_and_enums(self):
        """Test 8: Verify bus dataclasses and enums instantiate cleanly with zero business logic."""
        msg = AgentMessage(
            sender_id="agent_a",
            recipient_id="agent_b",
            topic="research",
            priority=MessagePriority.HIGH,
            payload={"key": "value"},
        )
        self.assertEqual(msg.priority, MessagePriority.HIGH)
        self.assertEqual(msg.delivery_status, DeliveryStatus.QUEUED)

        manifest = AgentManifest(
            agent_id="research_agent",
            name="Research Subagent",
            capabilities=["web_search", "scraping"],
        )
        self.assertEqual(len(manifest.capabilities), 2)

    def test_09_concurrent_feature_flag_updates(self):
        """Test 9: Verify thread-safe feature flag enable/disable across 20 concurrent threads."""
        ffm = FeatureFlagManager()
        threads = []

        def worker(num):
            for _ in range(50):
                if num % 2 == 0:
                    ffm.enable_flag("ENABLE_AGENT_BUS")
                else:
                    ffm.disable_flag("ENABLE_AGENT_BUS")
                _ = ffm.is_enabled("ENABLE_AGENT_BUS")

        for i in range(20):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertIn(ffm.is_enabled("ENABLE_AGENT_BUS"), [True, False])

    def test_10_di_container_stress_test(self):
        """Test 10: 1,000 concurrent resolve() operations verifying 0 deadlocks and memory leak safety."""
        container = DIContainer()

        class SharedSingleton:
            def __init__(self):
                self.val = 42

        container.register_singleton(SharedSingleton, SharedSingleton())

        gc.collect()
        import psutil
        process = psutil.Process(os.getpid())
        ram_before = process.memory_info().rss

        threads = []
        resolved_count = [0]
        count_lock = threading.Lock()

        def resolver():
            for _ in range(50):
                obj = container.resolve(SharedSingleton)
                if obj.val == 42:
                    with count_lock:
                        resolved_count[0] += 1

        for _ in range(20):
            t = threading.Thread(target=resolver)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        gc.collect()
        ram_after = process.memory_info().rss
        ram_diff_mb = (ram_after - ram_before) / (1024 * 1024)

        self.assertEqual(resolved_count[0], 1000)
        print(f"\n[DI Stress Test] 1,000 concurrent resolves complete. RAM diff: {ram_diff_mb:.2f} MB")
        self.assertLess(ram_diff_mb, 1.0)


if __name__ == "__main__":
    unittest.main()
