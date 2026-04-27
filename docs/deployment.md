# Deployment Notes

Suggested server layout:

```text
/opt/context-os/
  personal_agent/
  scripts/
  data/
  .venv/
```

Bootstrap:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/init_db.py
```

Start the API with the provided systemd unit as a template:

- [`../deploy/systemd/context-os.service`](../deploy/systemd/context-os.service)

Example health check:

```bash
curl http://127.0.0.1:5000/health
```

## Scheduled Radar Job

Run the full radar job manually:

```bash
python3 scripts/run_radar_job.py --repo owner/repo --analysis-limit 5 --send
```

Example cron entry:

```cron
0 9 */3 * * /usr/bin/flock -n /tmp/context-os-radar.lock /opt/context-os/.venv/bin/python /opt/context-os/scripts/run_radar_job.py --repo owner/repo --analysis-limit 5 --send >> /var/log/context-os-radar.log 2>&1
```

Keep runtime secrets in an environment file such as `/etc/context-os.env`.
Do not commit production `.env` files.
