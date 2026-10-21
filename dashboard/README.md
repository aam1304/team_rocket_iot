# Team Rocket Dashboard

Lightweight local web dashboard for the room-mode monitor. Runs on the
Pi (live) or anywhere else (replay against collected CSVs). Everything
is served over HTTP on the home network; no cloud, no external
dependencies at runtime (Chart.js is vendored under `static/`).

## Two ways to run

### 1. Live, on the Pi

Reads the newest `sensor_log_*.csv` the main service is writing and
tails it. Everyone on the same WiFi can open the dashboard in a
browser at `http://<pi-ip>:5000/`.

```bash
pip install -r requirements.txt
python3 app.py --mode live --log-dir /home/rpi/team_rocket_iot/logs
```

Or, as a systemd service (so it auto-starts with the Pi):

```bash
sudo cp team-rocket-dashboard.service /etc/systemd/system/
# Edit WorkingDirectory and ExecStart paths first if the project is
# in a different location.
sudo systemctl daemon-reload
sudo systemctl enable --now team-rocket-dashboard.service
sudo systemctl status team-rocket-dashboard.service
```

### 2. Replay, on a laptop

Reads every `sensor_log_*.csv` in `--log-dir` and plays them back
in order at `--speed` x real time. Open in a browser at
`http://localhost:5000/`.

```bash
pip install -r requirements.txt
python3 app.py --mode replay --log-dir ../logs --speed 300
```

Playback speed of 300 covers the whole collection week (~7 days)
in roughly 30 minutes of real time. For a demo screenshot, 500 or
1000 is fine.

## Analysis tab

If `analysis_results.json` is present alongside `app.py` (or passed
via `--analysis path/to/file.json`), the dashboard shows an
Analysis tab with mode share, matched % per mode and the full
confusion matrix. Generate it with:

```bash
python3 ../analysis.py --log-dir ../logs --out dashboard/analysis_results.json
```

## Files

- `app.py` - Flask server, two threads (data source + HTTP)
- `templates/index.html` - single-page dashboard
- `static/chart.umd.min.js` - vendored Chart.js 4.4.1
- `requirements.txt` - just Flask
- `team-rocket-dashboard.service` - systemd unit for Pi deployment
