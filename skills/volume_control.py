"""
ULTRON V3
Volume Control
"""

from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import (
    AudioUtilities,
    IAudioEndpointVolume
)


def get_volume():

    devices = AudioUtilities.GetSpeakers()

    interface = devices.Activate(
        IAudioEndpointVolume._iid_,
        CLSCTX_ALL,
        None
    )

    return cast(
        interface,
        POINTER(IAudioEndpointVolume)
    )


def volume_up():

    volume = get_volume()

    current = volume.GetMasterVolumeLevelScalar()

    current = min(current + 0.1, 1.0)

    volume.SetMasterVolumeLevelScalar(current, None)

    return "Volume increased Boss."


def volume_down():

    volume = get_volume()

    current = volume.GetMasterVolumeLevelScalar()

    current = max(current - 0.1, 0.0)

    volume.SetMasterVolumeLevelScalar(current, None)

    return "Volume decreased Boss."


def mute():

    volume = get_volume()

    volume.SetMute(1, None)

    return "Volume muted Boss."


def unmute():

    volume = get_volume()

    volume.SetMute(0, None)

    return "Volume unmuted Boss."


def max_volume():

    volume = get_volume()

    volume.SetMasterVolumeLevelScalar(1.0, None)

    return "Maximum volume activated Boss."


def min_volume():

    volume = get_volume()

    volume.SetMasterVolumeLevelScalar(0.0, None)

    return "Minimum volume activated Boss."