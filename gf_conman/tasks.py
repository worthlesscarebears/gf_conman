"""App Tasks"""

# Standard Library
import json
import logging
import time
from datetime import timedelta

# Third Party
import requests
from discord import Color, Embed

# Django
from celery import shared_task
from django.utils import timezone

# Alliance Auth
from allianceauth.framework.api.evecharacter import get_user_from_evecharacter, get_sentinel_user
from allianceauth.eveonline.models import EveCharacter

# Alliance Auth (External Libs)
from corptools.models.contracts import Contract, ContractItem
from corptools.tasks.character.wallet import update_char_contracts
from corptools.tasks.corporation.contracts import corp_contract_update

# George Forge + Modules
from georgeforge import models as forge_models
from georgeforge import tasks as forge_tasks
from gf_conman.models import ContractFilter, MonitoredCharacter, MonitoredContract

logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {"finished", "expired", "cancelled", "rejected", "deleted", "reversed"}

@shared_task
def pull_contracts() -> None:
    """Scan our filters for chars/corps we want to know about, and pull their contracts from ESI - more often that normal"""
    for cf in ContractFilter.objects.all():
        if cf.from_character:
            update_char_contracts.delay(cf.from_character.character_id)
        elif cf.from_corporation:
            corp_contract_update(cf.from_corporation.corporation_id)
    for mc in MonitoredCharacter.objects.all():
        update_char_contracts.delay(mc.character.character_id)

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
                send_webhook_notification(monitored)

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
            send_webhook_notification(entry)
            entry.last_status = current_status

            if current_status in "finished":
                if entry.triggered_filter.gf_integration:
                    sale_items = []
                    for i in forge_models.ForSale.objects.all().order_by("-price"):
                        sale_items.append(i.eve_type)
                    detected_item = None
                    for x in ContractItem.objects.filter(contract=entry.contract):
                        for i in sale_items:
                            if i == x.type_name:
                                detected_item = x.type_name
                                detected_quantity = x.quantity
                                break

                        if not detected_item:
                            logger.warning(f"Contract {entry.contract.contract_id} completed, but no matching ForSale item found for type {x.type_name.name}.")
                            send_update_to_webhook.delay(
                                webhook=entry.triggered_filter.webhook.url,
                                content=f"Contract {entry.contract.contract_id} completed, but no matching ForSale item found for type {x.type_name.name}.",
                            )
                            continue
                    _evechr = EveCharacter.objects.get_character_by_id(character_id=entry.contract.acceptor_id)
                    if _evechr is None:
                        logger.warning(f"Contract {entry.contract.contract_id} completed, but acceptor {entry.contract.acceptor_name} is not known to us.")
                        _evechr = EveCharacter.objects.create_character(entry.contract.acceptor_id)
                    detected_user = get_user_from_evecharacter(_evechr)
                    if detected_user is get_sentinel_user():
                        logger.warning(f"Contract {entry.contract.contract_id} completed, but acceptor {entry.contract.acceptor_name} is not linked to an Alliance Auth user.")
                        send_update_to_webhook.delay(
                            webhook=entry.triggered_filter.webhook.url,
                            content=f"Contract {entry.contract.contract_id} completed, but acceptor {entry.contract.acceptor_name} is not linked to an Alliance Auth user.",
                        )
                        detected_user = get_user_from_evecharacter(EveCharacter.objects.get(character_id=entry.contract.issuer_id))

                    o = forge_models.Order.objects.create(
                        user=detected_user,
                        status=forge_models.Order.OrderStatus.DELIVERED,
                        price=entry.contract.price,
                        paid=entry.contract.price,
                        totalcost=entry.contract.price,
                        deposit=0,
                        quantity=detected_quantity,
                        notes=f"Contract {entry.contract.contract_id}",
                        deliverysystem=forge_models.DeliverySystem.objects.filter(enabled=True).first().system,
                        cart_session_id="00000000-0000-0000-0000-000000000000",
                        eve_type=detected_item,
                    )
                    forge_tasks.send_order_webhook(o.id)
            if current_status in TERMINAL_STATUSES:        
                entry.delete()
                continue

            entry.save(update_fields=["last_status"])

@shared_task(rate_limit="5/s")
def send_update_to_webhook(webhook, embed=None, content=None) -> None:
    custom_headers = {"Content-Type": "application/json"}
    payload = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content
    elif not embed:
        payload["content"] = "Contract update notification"
    r = requests.post(
        webhook,
        headers=custom_headers,
        data=json.dumps(payload),
    )
    logger.debug(f"Got status code {r.status_code} after sending ping")
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        if r.status_code == 429: #Handle webhook rate-limit (5/1s as of testing 2026/6/3)
            send_update_to_webhook.retry(content=content, embed=embed,
                                            exc=e, max_retries=3, countdown=2)
        else:
            logger.error(e, exc_info=1)
    except Exception as e:
        logger.error(e, exc_info=1)

def send_webhook_notification(monitor: MonitoredContract) -> None:
    """Send a notification to the webhook for a contract.

    Args:
        contract (MonitoredContract): The monitored contract object to include in the notification.
    """
    contract = monitor.contract
    webhook = monitor.triggered_filter.webhook
    content = None
    if monitor.triggered_filter.ping_id:
        if monitor.triggered_filter.role_ping:
            content = f"<@&{monitor.triggered_filter.ping_id}>"
        else:
            content = f"<@{monitor.triggered_filter.ping_id}>"

    title = f"Contract {contract.contract_id} status changed to {monitor.contract.status}"
    status = "Changed"
    colour = Color.fuchsia()
    datestamp = int(time.time())
    match monitor.contract.status:
        case "outstanding":
            title = f"New contract matched filter {monitor.triggered_filter.name}"
            status = "New"
            colour = Color.blue()
        case "in_progress":
            title = f"Contract in progress"
            status = "In Progress"
            colour = Color.gold()
        case "finished":
            title = f"Contract completed"
            status = "Completed"
            colour = Color.green()
            datestamp = int(contract.date_completed.timestamp())
        case "expired":
            title = f"Contract expired"
            status = "Expired"
            colour = Color.red()
            datestamp = int(contract.date_expired.timestamp())
        case "cancelled":
            title = f"Contract cancelled"
            status = "Cancelled"
            colour = Color.red()
            datestamp = int(contract.date_completed.timestamp())
        case "rejected":
            title = f"Contract rejected"
            status = "Rejected"
            colour = Color.dark_red()
            datestamp = int(contract.date_completed.timestamp())
        case "deleted":
            title = f"Contract deleted"
            status = "Deleted"
            colour = Color.black()
            datestamp = int(contract.date_completed.timestamp())
        case "reversed":
            title = f"Contract reversed"
            status = "Reversed"
            colour = Color.purple()
            datestamp = int(contract.date_completed.timestamp())
    
    embed = Embed(
        title=f"{title}",
        description=f"{status} | ID: {contract.contract_id} | \"{contract.title}\" | Issuer: {contract.issuer_name} | Completed by: {contract.acceptor_name} | <t:{datestamp}:R>",
        color=colour
    )
    send_update_to_webhook.delay(webhook=webhook.url, embed=embed.to_dict(), content=content)