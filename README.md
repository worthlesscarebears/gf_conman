# George Forge - Contract Manager

An app for george and indy.

mostly private and hand-maintained by denny

## Settings

None exist yet.

## Installation

We depend on
[GeorgeForge](https://github.com/worthlesscarebears/georgeforge)
AND all its deps.
so follow those instructions. Also corptools
and invoices.

has no ui, all in admin for now

```bash
python manage.py migrate
```

```python
CELERYBEAT_SCHEDULE['gf_conman_contract_pulls'] = {
    'task': 'gf_conman.tasks.pull_contracts',
    'schedule': crontab(minute='*/10'),
}
CELERYBEAT_SCHEDULE['gf_conman_discover_contracts'] = {
    'task': 'gf_conman.tasks.discover_new_contracts',
    'schedule': crontab(minute='*/10'),
    'args': (1,), #
}
CELERYBEAT_SCHEDULE['gf_conman_check'] = {
    'task': 'gf_conman.tasks.check_monitored_contracts',
    'schedule': crontab(minute='*/10'),
}
```