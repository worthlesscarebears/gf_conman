"""App Configuration"""

# Django
from django.apps import AppConfig

# AA Example App
from gf_conman import __version__


class ConmanConfig(AppConfig):
    """App Config"""

    name = "gf_conman"
    label = "gf_conman"
    verbose_name = f"GeorgeForge ConMan v{__version__}"
