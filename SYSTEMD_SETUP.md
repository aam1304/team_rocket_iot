# Running as a systemd service

This makes `main.py` start automatically on boot and restart itself
if it crashes or the Pi loses power - the mitigation the official
plan names for that risk.

## Setup

1. Edit `team-rocket.service` first - set `WorkingDirectory` and the
   path in `ExecStart` to wherever the project actually sits on the
   Pi (e.g. `/home/pi/team_rocket_iot`), and set `User` to whichever
   account should run it.

1a. Create the `.env` file the service references, in the project
    folder on the Pi (same folder as `main.py`):

    ```bash
    nano /home/pi/team_rocket_iot/.env
    ```

    Put exactly one line in it, with the real webhook URL:

    ```
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your-real-url-here
    ```

    Save and exit (Ctrl+O, Enter, Ctrl+X in nano). This file is
    listed in `.gitignore` and must never be committed - it's the
    only place the real URL should exist on the Pi.

2. Copy it into place and enable it:

   ```bash
   sudo cp team-rocket.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable team-rocket.service
   sudo systemctl start team-rocket.service
   ```

3. Check it's actually running:

   ```bash
   sudo systemctl status team-rocket.service
   ```

4. Watch its live output (same as watching the terminal, but through
   systemd's own log):

   ```bash
   journalctl -u team-rocket.service -f
   ```

## Stopping / restarting it manually

```bash
sudo systemctl stop team-rocket.service
sudo systemctl restart team-rocket.service
```

## Before the real data collection run

Confirm this actually survives a reboot - power-cycle the Pi once
and check `systemctl status` afterwards, rather than assuming
`enable` alone is enough. This is the explicit test the plan calls
for before collection week starts, not something to skip.