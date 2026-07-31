"""
App Models
Create your models in here
"""

# Standard Library
from datetime import timedelta

# Django
from django.db import models
from django.db.models import Q, QuerySet

# Alliance Auth
from allianceauth.eveonline.models import (
    EveCharacter,
    EveCorporationInfo,
)

# Alliance Auth (External Libs)
from corptools.models.contracts import Contract


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        """Meta definitions"""

        managed = False
        default_permissions = ()
        permissions = (("basic_access", "Can access this app"),)

class Webhook(models.Model):
    """Webhook model for storing webhook URLs"""

    class Meta:
        default_permissions = ()

    description = models.CharField(
        "Description",
        max_length=255,
        help_text="Description of the webhook",
    )

    username = models.CharField(
        "Username",
        max_length=80,
        help_text="Username to send the notification as",
    )
    
    url = models.URLField(
        "Webhook URL",
        help_text="URL to send the notification to",
    )

    def __str__(self):
        return self.description


class ContractFilter(models.Model):
    """Filters to route contract notifications to the right webhook"""

    class Meta:
        default_permissions = ()

    name = models.CharField(
        "Name",
        max_length=255,
        help_text="Name of the filter",
    )

    gf_integration = models.BooleanField(
        "GeorgeForge Integration",
        default=False,
    )

    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.SET_NULL,
        null=True,
    )
    
    ping_id = models.BigIntegerField(
        "Ping ID",
        null=True,
        blank=True,
        help_text="Optional ID to ping on Discord",
    )

    role_ping = models.BooleanField(
        "Role Ping",
        default=False,
        help_text="Is the Ping ID a role ID",
    )

    from_character = models.ForeignKey(
        EveCharacter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_filters_from_character",
        help_text="Filter contracts from this character",
    )

    from_corporation = models.ForeignKey(
        EveCorporationInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_filters_from_corporation",
        help_text="Filter contracts from this corporation",
    )

    description_filter = models.TextField(
        "Description Filter",
        null=True,
        blank=True,
        help_text="Filter contracts by description (case insensitive)",
    )

    def build_query(self) -> Q:
        """Build a Q object representing this filter's conditions."""
        query = Q()

        if self.from_character:
            query &= Q(issuer_name_id=self.from_character.character_id)

        if self.from_corporation:
            query &= Q(issuer_corporation_name_id=self.from_corporation.corporation_id)

        if self.description_filter:
            query &= Q(title__icontains=self.description_filter)

        return query

    def matching_contracts(self, queryset: QuerySet["Contract"]) -> QuerySet["Contract"]:
        """Return the subset of queryset that satisfies this filter, via the DB."""
        return queryset.filter(self.build_query())

    def __str__(self):
        return self.name


class MonitoredContract(models.Model):
    """Tracks a (contract, filter) pair that matched, to watch for status changes."""

    class Meta:
        default_permissions = ()
        unique_together = (("contract", "triggered_filter"),)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="monitored_by",
    )
    triggered_filter = models.ForeignKey(
        ContractFilter,
        on_delete=models.CASCADE,
        related_name="monitored_contracts",
    )
    last_status = models.CharField(max_length=25)

