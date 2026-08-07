"""
ULTRON V3
Session Manager
"""

SESSION_VERIFIED = False


def is_verified():
    return SESSION_VERIFIED


def set_verified(value=True):
    global SESSION_VERIFIED
    SESSION_VERIFIED = value


def reset_session():
    global SESSION_VERIFIED
    SESSION_VERIFIED = False