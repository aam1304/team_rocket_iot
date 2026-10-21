"""
Team Rocket dashboard
---------------------
Lightweight local web dashboard. Serves one page over the home network
showing the current mode, live sensor readings, recent transitions and
an analysis view (mode share, matched vs ground truth).

Two operating modes:
  --live   Reads the newest sensor_log_*.csv in --log-dir and polls its
           last row. Use this on the Pi next to main.py.
  --replay Plays back one or more sensor_log_*.csv files at --speed x
           real time. Use this on a laptop against the collected logs.

Usage:
  python3 app.py --mode live    --log-dir /home/rpi/team_rocket_iot/logs
  python3 app.py --mode replay  --log-dir ./logs --speed 300
"""

import argparse
import csv
import glob
import json
import os
import threading
import time
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, render_template, send_from_directory

app = Flask(__name__)

# Shared state updated by the background thread, read by the HTTP handlers.
# A plain dict is fine here because Python assignments are atomic and the
# dashboard tolerates a slightly stale snapshot.
STATE = {
    "latest": None,            # most recent row (dict)
    "history": deque(maxlen=5000),  # recent rows for the chart
    "transitions": deque(maxlen=50),
    "started_at": datetime.now().isoformat(timespec="seconds"),
    "mode_source": "unknown",
    "replay_at": None,         # replay cursor time
    "analysis": None,          # loaded from analysis_results.json if present
}

ARGS = None


def row_to_point(row):
    """Pull the dashboard-relevant fields out of a CSV row dict."""
    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    return {
        "timestamp": row.get("timestamp", ""),
        "mode": row.get("mode", ""),
        "score": num(row.get("score")),
        "bed_pad_raw": num(row.get("bed_pad_raw")),
        "desk_pad_raw": num(row.get("desk_pad_raw")),
        "bed_occupied": row.get("bed_occupied") == "True",
        "desk_occupied": row.get("desk_occupied") == "True",
        "light_raw": num(row.get("light_raw")),
        "sound_committed_state": row.get("sound_committed_state", ""),
        "temperature_c": num(row.get("temperature_c")),
        "humidity_pct": num(row.get("humidity_pct")),
        "label": row.get("label", ""),
    }


def push_row(row):
    """Update the shared state with a new row, record transitions."""
    pt = row_to_point(row)
    prev = STATE["latest"]
    if prev and prev["mode"] != pt["mode"]:
        STATE["transitions"].appendleft({
            "timestamp": pt["timestamp"],
            "old_mode": prev["mode"],
            "new_mode": pt["mode"],
        })
    STATE["latest"] = pt
    STATE["history"].append(pt)


def iter_rows_from_file(path):
    """Yield row dicts from a CSV, skipping unreadable/MOCK rows."""
    with open(path, newline="", errors="replace") as fp:
        for row in csv.DictReader(fp):
            ts = (row.get("timestamp") or "").strip("\x00").strip()
            if not ts:
                continue
            if (row.get("label") or "").strip() == "MOCK":
                continue
            yield row


# ---------------- live mode ----------------

def live_watcher():
    """Watch the newest sensor_log_*.csv in --log-dir and push new rows."""
    last_file = None
    last_size = 0
    while True:
        try:
            files = sorted(glob.glob(os.path.join(ARGS.log_dir, "sensor_log_*.csv")))
            if not files:
                time.sleep(2)
                continue
            newest = files[-1]
            if newest != last_file:
                last_file = newest
                last_size = 0
                STATE["mode_source"] = f"live: {os.path.basename(newest)}"

            # Open each poll and read everything from last_size on
            with open(newest, "rb") as fp:
                fp.seek(last_size)
                chunk = fp.read()
                last_size = fp.tell()
            if chunk:
                # Parse the new bytes as CSV rows (header already seen if last_size > 0)
                lines = chunk.decode(errors="replace").splitlines()
                if last_size == len(chunk):
                    # First read of the file: includes the header
                    reader = csv.DictReader(lines)
                else:
                    # Append read: reuse the header from the first row we saw
                    fieldnames = None
                    if STATE["history"]:
                        fieldnames = list(STATE["history"][0].keys()) + ["label"]
                    reader = csv.DictReader(lines, fieldnames=fieldnames) if fieldnames else []
                for row in reader:
                    if not row.get("timestamp"):
                        continue
                    push_row(row)
        except Exception as e:
            print(f"[live_watcher] {e}")
        time.sleep(ARGS.poll)


# ---------------- replay mode ----------------

def replay_runner():
    """Play back every CSV in --log-dir in order, at --speed x real time."""
    files = sorted(glob.glob(os.path.join(ARGS.log_dir, "sensor_log_*.csv")))
    if not files:
        print(f"[replay] no sensor_log_*.csv in {ARGS.log_dir}")
        return
    STATE["mode_source"] = f"replay x{ARGS.speed} across {len(files)} files"

    # Collect every row in order
    rows = []
    for f in files:
        for row in iter_rows_from_file(f):
            try:
                row["_t"] = datetime.fromisoformat(row["timestamp"].strip("\x00").strip())
            except Exception:
                continue
            rows.append(row)
    rows.sort(key=lambda r: r["_t"])
    print(f"[replay] {len(rows):,} rows across {len(files)} files")

    if not rows:
        return
    start_real = time.monotonic()
    start_sim = rows[0]["_t"]
    for i, row in enumerate(rows):
        STATE["replay_at"] = row["_t"].isoformat(timespec="seconds")
        push_row(row)
        if i + 1 < len(rows):
            sim_dt = (rows[i + 1]["_t"] - start_sim).total_seconds()
            target_real_elapsed = sim_dt / ARGS.speed
            now_elapsed = time.monotonic() - start_real
            wait = target_real_elapsed - now_elapsed
            if wait > 0:
                time.sleep(min(wait, 0.5))
    print("[replay] finished")


# ---------------- routes ----------------

@app.route("/")
def index():
    return render_template("index.html", source=STATE["mode_source"])


@app.route("/api/live")
def api_live():
    return jsonify({
        "latest": STATE["latest"],
        "source": STATE["mode_source"],
        "replay_at": STATE["replay_at"],
        "transitions": list(STATE["transitions"])[:20],
    })


@app.route("/api/history")
def api_history():
    # Return a downsampled view of the history ring buffer
    rows = list(STATE["history"])
    stride = max(1, len(rows) // 1200)
    return jsonify({
        "rows": rows[::stride],
        "total": len(rows),
    })


@app.route("/api/analysis")
def api_analysis():
    if STATE["analysis"] is None:
        return jsonify({"available": False})
    return jsonify({"available": True, "data": STATE["analysis"]})


# ---------------- main ----------------

def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["live", "replay"], required=True)
    ap.add_argument("--log-dir", required=True,
                    help="Directory containing sensor_log_*.csv files")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--host", default="0.0.0.0",
                    help="Bind address. 0.0.0.0 exposes it on the home network.")
    ap.add_argument("--speed", type=float, default=300.0,
                    help="Replay speed (times real time). Default 300.")
    ap.add_argument("--poll", type=float, default=5.0,
                    help="Live mode: seconds between file checks.")
    ap.add_argument("--analysis", default="analysis_results.json",
                    help="Path to analysis_results.json for the Analysis tab.")
    ARGS = ap.parse_args()

    # Load the analysis results if the JSON file is sitting next to us
    if os.path.exists(ARGS.analysis):
        with open(ARGS.analysis) as fp:
            STATE["analysis"] = json.load(fp)
        print(f"[main] loaded analysis from {ARGS.analysis}")

    # Start the data source thread
    if ARGS.mode == "live":
        t = threading.Thread(target=live_watcher, daemon=True)
    else:
        t = threading.Thread(target=replay_runner, daemon=True)
    t.start()

    print(f"[main] serving dashboard on http://{ARGS.host}:{ARGS.port}  (mode={ARGS.mode})")
    app.run(host=ARGS.host, port=ARGS.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
