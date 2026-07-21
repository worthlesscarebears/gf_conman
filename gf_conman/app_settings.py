"""App Settings"""

# Django
from django.conf import settings

# put your app settings here

def webhook_available():
    try:
        # Third Party
        import discord

        return discord is not None
    except ImportError:
        return False
