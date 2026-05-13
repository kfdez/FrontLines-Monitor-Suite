# FrontLines VPS Deployment

This branch adds a FastAPI web admin while preserving `main.py` for the Tkinter desktop app.

## Local run

```powershell
python -m pip install -r requirements.txt
python -c "from server.auth import hash_password; print(hash_password('frontlines'))"
$env:FRONTLINES_DATA_DIR = "F:\Coding Projects\FrontLinesMonitorSuite_3.0_desktop"
$env:FRONTLINES_ADMIN_USERNAME = "admin"
$env:FRONTLINES_ADMIN_PASSWORD_HASH = "paste-hash-here"
$env:FRONTLINES_SESSION_SECRET = "replace-with-a-long-random-string"
$env:FRONTLINES_PORT = "8001"
python web_main.py
```

Open `http://127.0.0.1:8001`.

## Ubuntu install outline

```bash
sudo adduser --system --group --home /var/lib/frontlines-monitor frontlines
sudo mkdir -p /opt/frontlines-monitor /var/lib/frontlines-monitor
sudo chown -R frontlines:frontlines /opt/frontlines-monitor /var/lib/frontlines-monitor

cd /opt/frontlines-monitor
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "from server.auth import hash_password; print(hash_password('frontlines'))"
```

Copy `deployment/frontlines.env.example` to `/etc/frontlines-monitor.env`, fill in the hash and a real session secret, then install the service:

```bash
sudo cp deployment/frontlines-monitor.service /etc/systemd/system/frontlines-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now frontlines-monitor
sudo systemctl status frontlines-monitor
```

Use the nginx snippet if you want to expose it on port 80/443. Keep `FRONTLINES_HOST=127.0.0.1` when nginx is in front.
