"""App Tasks"""

# Standard Library
import logging
from datetime import timedelta

# Third Party
from corptools.models.contracts import Contract

# Django
from celery import shared_task
from django.utils import timezone

# George Forge + Modules
from gf_conman.models import ContractFilter, MonitoredContract

logger = logging.getLogger(__name__)
#                    finished cancelled rejected failed deleted reversed
TERMINAL_STATUSES = {"finished", "expired", "cancelled", "rejected", "deleted", "reversed"}

@shared_task
def discover_new_contracts(hours: int = 24) -> None:
    """Run the full filter sweep against contracts issued in the last `hours`.

    No historical backfill / cursor tracking: if a contract is missed
    (e.g. beat downtime longer than `hours`), it's simply never
    discovered — acceptable per requirements.
    """

    cutoff = timezone.now() - timedelta(hours=hours)
    recent_contracts = Contract.objects.filter(date_issued__gte=cutoff)

    for contract_filter in ContractFilter.objects.all():
        matched = contract_filter.matching_contracts(recent_contracts)

        for contract in matched.iterator(chunk_size=500):
            monitored, created = MonitoredContract.objects.get_or_create(
                contract=contract,
                triggered_filter=contract_filter,
                defaults={"last_status": contract.status},
            )
            if created:
                send_webhook_notification(
                    url=contract_filter.webhook_url,
                    contract=contract,
                    color=contract_filter.color,
                )

@shared_task
def check_monitored_contracts() -> None:
    """Cheap pass: only re-checks contracts already known to match a filter.

    Only ever touches MonitoredContract rows (bounded to "contracts
    currently in flight"), never the full Contract table. Rows are
    pruned once a contract reaches a terminal status.
    """
    monitored = MonitoredContract.objects.select_related("contract", "triggered_filter")

    for entry in monitored.iterator(chunk_size=500):
        current_status = entry.contract.status

        if current_status != entry.last_status:
            send_webhook_notification(
                url=entry.triggered_filter.webhook_url,
                contract=entry.contract,
                color=entry.triggered_filter.color,
            )
            entry.last_status = current_status

            if current_status in TERMINAL_STATUSES:
                entry.delete()
                continue

            entry.save(update_fields=["last_status"])


def send_webhook_notification(*, url: str, contract, color: str) -> None:
    """
    Stub — replace with your actual Discord/webhook sending implementation.
    """
    raise NotImplementedError