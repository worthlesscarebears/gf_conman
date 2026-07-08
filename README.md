# George Forge - Contract Manager

An app for george and indy.

mostly private and hand-maintained by denny

## Settings

All are optional.

```python
# Georgeforge - conman

# Webhook to post orders to
CONTRACT_ADMIN_WEBHOOK = "https://discord.com/api/webhooks/1/abcd"
# Discord role ID to ping when a new order is placed
CONTRACT_ADMIN_WEBHOOK_ROLE_ID = 123456789
```

## Installation

We depend on
[GeorgeForge](https://github.com/worthlesscarebears/georgeforge)
AND all its deps.
so follow those instructions. Also corptools
and invoices.

```bash
python manage.py migrate
python manage.py collectstatic --no-input
```
