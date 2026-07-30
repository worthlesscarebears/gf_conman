"""Admin models"""

# Django
from django.contrib import admin  # noqa: F401

from gf_conman.models import ContractFilter, MonitoredContract, Webhook

# Register your models here.
@admin.register(ContractFilter)
class ContractFilterAdmin(admin.ModelAdmin):
    """  """
    list_display = ["name", "gf_integration"]


@admin.register(MonitoredContract)
class MonitoredContractAdmin(admin.ModelAdmin):
    """  """
    list_display = ["contract"]

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    """  """
    list_display = ["description", "username", "url"]