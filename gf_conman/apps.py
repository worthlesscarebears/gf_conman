"""App Configuration"""

# Django
from django.apps import AppConfig

# AA Example App
from gf_conman import __version__


class ExampleConfig(AppConfig):
    """App Config"""

    name = "allianceauth-gf-conman"
    label = "allianceauth-gf-conman"
    verbose_name = f"GeorgeForge ConMan v{__version__}"
