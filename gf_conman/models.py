"""
App Models
Create your models in here
"""

# Standard Library
from datetime import timedelta

# Third Party
from corptools.models.contracts import Contract

# Django
from django.db import models
from django.db.models import Q, QuerySet

# Alliance Auth
from allianceauth.eveonline.models import (
    EveCharacter,
    EveCorporationInfo,
)



class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        """Meta definitions"""

        managed = False
        default_permissions = ()
        permissions = (("basic_access", "Can access this app"),)


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
    webhook_url = models.URLField(
        "Webhook URL",
        help_text="URL to send the notification to",
    )
    color = models.CharField(
        "Embed Color",
        max_length=7,
        default="",
        blank=True,
        help_text=(
            "Optional color for embed on Discord - #000000 / "
            "black means no color selected."
        ),
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

