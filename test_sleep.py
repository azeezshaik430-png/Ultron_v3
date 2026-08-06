from voice.sleep_manager import SleepManager


ultron = SleepManager()


print(
    ultron.is_sleeping()
)


ultron.sleep()


print(
    ultron.is_sleeping()
)


ultron.wake()


print(
    ultron.is_sleeping()
)