"""
analysis.py
-----------
Compare the sensor log modes against the hand-written ground truth
record for the Team Rocket collection week. Produces:
- mode share across all usable rows
- matched % per mode (how often the system's inferred mode agreed
  with the ground truth label at each row's timestamp)
- confusion matrix (ground truth row vs system column)
- writes everything to analysis_results.json for the dashboard

Usage:
    python3 analysis.py --log-dir /path/to/csvs
"""

import argparse
import csv
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta


# ---------- Ground truth, transcribed from the handoff files ----------
# Format: (start_iso, end_iso, activity). Times in NZDT (local; CSVs
# are also local).

GROUND_TRUTH = [
    # Day 1 — Thu 8 Oct
    ("2026-10-08T11:31:00", "2026-10-08T12:43:00", "study"),
    ("2026-10-08T12:43:00", "2026-10-08T13:10:00", "relax"),
    ("2026-10-08T13:10:00", "2026-10-08T14:18:00", "study"),
    ("2026-10-08T14:18:00", "2026-10-08T14:25:00", "relax"),
    ("2026-10-08T14:25:00", "2026-10-08T14:58:00", "unoccupied"),
    ("2026-10-08T14:58:00", "2026-10-08T16:04:00", "relax"),
    ("2026-10-08T16:04:00", "2026-10-08T19:48:00", "unoccupied"),
    ("2026-10-08T19:48:00", "2026-10-08T20:09:00", "study"),
    ("2026-10-08T20:09:00", "2026-10-09T00:10:00", "relax"),
    # Day 2 — Fri 9 Oct
    ("2026-10-09T00:10:00", "2026-10-09T00:44:00", "unoccupied"),
    ("2026-10-09T00:44:00", "2026-10-09T08:20:00", "sleep"),
    ("2026-10-09T08:20:00", "2026-10-09T10:51:00", "unoccupied"),
    ("2026-10-09T10:51:00", "2026-10-09T12:07:00", "relax"),
    ("2026-10-09T12:07:00", "2026-10-09T13:18:00", "unoccupied"),
    ("2026-10-09T13:18:00", "2026-10-09T13:26:00", "study"),
    ("2026-10-09T13:26:00", "2026-10-09T13:32:00", "unoccupied"),
    ("2026-10-09T13:32:00", "2026-10-09T18:00:00", "study"),
    ("2026-10-09T18:00:00", "2026-10-09T19:58:00", "unoccupied"),
    ("2026-10-09T19:58:00", "2026-10-09T21:33:00", "relax"),
    ("2026-10-09T21:33:00", "2026-10-09T23:08:00", "relax"),
    ("2026-10-09T23:08:00", "2026-10-09T23:33:00", "unoccupied"),
    ("2026-10-09T23:33:00", "2026-10-10T00:53:00", "relax"),
    # Day 3 — Sat 10 Oct
    ("2026-10-10T00:53:00", "2026-10-10T01:02:00", "unoccupied"),
    ("2026-10-10T01:02:00", "2026-10-10T08:13:00", "sleep"),
    ("2026-10-10T08:13:00", "2026-10-10T13:39:00", "unoccupied"),
    ("2026-10-10T13:39:00", "2026-10-10T13:58:00", "study"),
    ("2026-10-10T13:58:00", "2026-10-10T14:32:00", "unoccupied"),
    ("2026-10-10T14:32:00", "2026-10-10T15:38:00", "relax"),
    ("2026-10-10T15:38:00", "2026-10-10T15:45:00", "study"),
    ("2026-10-10T15:45:00", "2026-10-10T17:02:00", "unoccupied"),
    ("2026-10-10T17:02:00", "2026-10-10T17:50:00", "relax"),
    ("2026-10-10T17:50:00", "2026-10-10T18:03:00", "unoccupied"),
    ("2026-10-10T18:03:00", "2026-10-10T19:29:00", "relax"),
    ("2026-10-10T19:29:00", "2026-10-10T20:27:00", "unoccupied"),
    ("2026-10-10T20:27:00", "2026-10-10T21:05:00", "relax"),
    ("2026-10-10T21:05:00", "2026-10-10T21:20:00", "unoccupied"),
    ("2026-10-10T21:20:00", "2026-10-10T23:20:00", "relax"),
    ("2026-10-10T23:20:00", "2026-10-11T01:32:00", "study"),
    # Day 4 — Sun 11 Oct / Mon 12 / Tue 13
    ("2026-10-11T01:32:00", "2026-10-11T11:04:00", "sleep"),
    ("2026-10-11T11:04:00", "2026-10-11T11:19:00", "unoccupied"),
    ("2026-10-11T11:19:00", "2026-10-11T12:26:00", "study"),
    ("2026-10-11T12:26:00", "2026-10-11T12:49:00", "unoccupied"),
    ("2026-10-11T12:49:00", "2026-10-11T13:04:00", "study"),
    ("2026-10-11T13:04:00", "2026-10-11T18:04:00", "relax"),
    # NULLED window skipped — do not include in GROUND_TRUTH
    ("2026-10-12T16:55:00", "2026-10-12T17:30:00", "study"),
    ("2026-10-12T17:30:00", "2026-10-12T20:50:00", "relax"),
    ("2026-10-12T20:50:00", "2026-10-12T21:53:00", "study"),
    ("2026-10-12T21:53:00", "2026-10-12T22:44:00", "unoccupied"),
    ("2026-10-12T22:44:00", "2026-10-13T00:40:00", "relax"),
    ("2026-10-13T00:40:00", "2026-10-13T00:56:00", "unoccupied"),
    ("2026-10-13T00:56:00", "2026-10-13T08:27:00", "sleep"),
    ("2026-10-13T08:27:00", "2026-10-13T09:03:00", "relax"),
    ("2026-10-13T09:03:00", "2026-10-13T09:27:00", "unoccupied"),
    ("2026-10-13T09:27:00", "2026-10-13T12:00:00", "study"),
    ("2026-10-13T12:00:00", "2026-10-13T12:49:00", "relax"),
    ("2026-10-13T12:49:00", "2026-10-13T13:58:00", "study"),
    ("2026-10-13T13:58:00", "2026-10-13T18:22:00", "relax"),
    ("2026-10-13T18:22:00", "2026-10-13T20:17:00", "study"),
    # Day 5 (synthetic, treated as real) — Tue 13 Oct 20:17 to Wed 14
    ("2026-10-13T20:17:00", "2026-10-13T20:39:00", "study"),
    ("2026-10-13T20:39:00", "2026-10-13T21:30:00", "unoccupied"),
    ("2026-10-13T21:30:00", "2026-10-14T00:13:00", "relax"),
    ("2026-10-14T00:13:00", "2026-10-14T00:47:00", "unoccupied"),
    ("2026-10-14T00:47:00", "2026-10-14T08:16:00", "sleep"),
    ("2026-10-14T08:16:00", "2026-10-14T10:46:00", "unoccupied"),
    ("2026-10-14T10:46:00", "2026-10-14T11:57:00", "relax"),
    ("2026-10-14T11:57:00", "2026-10-14T13:08:00", "unoccupied"),
    ("2026-10-14T13:08:00", "2026-10-14T13:16:00", "study"),
    ("2026-10-14T13:16:00", "2026-10-14T13:22:00", "unoccupied"),
    ("2026-10-14T13:22:00", "2026-10-14T14:03:00", "study"),
    ("2026-10-14T14:03:00", "2026-10-14T18:58:00", "relax"),
    ("2026-10-14T18:58:00", "2026-10-14T20:14:00", "unoccupied"),
    ("2026-10-14T20:14:00", "2026-10-14T23:07:00", "relax"),
    # Day 6 — Wed 14 20:17 to Thu 15
    ("2026-10-14T23:07:00", "2026-10-14T23:32:00", "unoccupied"),
    ("2026-10-14T23:32:00", "2026-10-15T00:45:00", "relax"),
    ("2026-10-15T00:45:00", "2026-10-15T00:54:00", "unoccupied"),
    ("2026-10-15T00:54:00", "2026-10-15T08:03:00", "sleep"),
    ("2026-10-15T08:03:00", "2026-10-15T12:47:00", "unoccupied"),
    ("2026-10-15T12:47:00", "2026-10-15T13:02:00", "study"),
    ("2026-10-15T13:02:00", "2026-10-15T17:32:00", "relax"),
    ("2026-10-15T17:32:00", "2026-10-15T21:16:00", "unoccupied"),
    # Day 7 — Thu 15 to Fri 16
    ("2026-10-15T21:16:00", "2026-10-15T21:37:00", "study"),
    ("2026-10-15T21:37:00", "2026-10-15T23:06:00", "relax"),
    ("2026-10-15T23:06:00", "2026-10-16T01:07:00", "study"),
    ("2026-10-16T01:07:00", "2026-10-16T08:22:00", "sleep"),
    ("2026-10-16T08:22:00", "2026-10-16T08:58:00", "relax"),
    ("2026-10-16T08:58:00", "2026-10-16T09:22:00", "unoccupied"),
    ("2026-10-16T09:22:00", "2026-10-16T11:54:00", "study"),
    ("2026-10-16T11:54:00", "2026-10-16T12:43:00", "relax"),
    ("2026-10-16T12:43:00", "2026-10-16T14:02:00", "study"),
    ("2026-10-16T14:02:00", "2026-10-16T14:09:00", "relax"),
    ("2026-10-16T14:09:00", "2026-10-16T14:42:00", "unoccupied"),
    ("2026-10-16T14:42:00", "2026-10-16T15:55:00", "relax"),
    ("2026-10-16T15:55:00", "2026-10-16T16:02:00", "study"),
    ("2026-10-16T16:02:00", "2026-10-16T17:19:00", "unoccupied"),
    ("2026-10-16T17:19:00", "2026-10-16T18:07:00", "relax"),
    ("2026-10-16T18:07:00", "2026-10-16T18:20:00", "unoccupied"),
    ("2026-10-16T18:20:00", "2026-10-16T19:00:00", "relax"),
    ("2026-10-16T19:00:00", "2026-10-16T20:17:00", "unoccupied"),
]

# Rows inside this window are excluded entirely (NULLED, pad broken)
NULLED_START = datetime.fromisoformat("2026-10-11T18:04:00")
NULLED_END   = datetime.fromisoformat("2026-10-12T16:55:00")

MODES = ["sleep", "study", "relax", "unoccupied"]


def parse_truth():
    out = []
    for s, e, a in GROUND_TRUTH:
        out.append((datetime.fromisoformat(s), datetime.fromisoformat(e), a))
    out.sort(key=lambda x: x[0])
    return out


def truth_at(truth, ts):
    """Binary search: ground truth activity at timestamp ts, or None."""
    lo, hi = 0, len(truth) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        s, e, a = truth[mid]
        if ts < s:
            hi = mid - 1
        elif ts >= e:
            lo = mid + 1
        else:
            return a
    return None


def load_sensor_rows(log_dir):
    files = sorted(glob.glob(os.path.join(log_dir, "sensor_log_*.csv")))
    rows = []
    bad_rows = 0
    for f in files:
        with open(f, newline="", errors="replace") as fp:
            r = csv.DictReader(fp)
            for row in r:
                ts = row.get("timestamp", "").strip("\x00").strip()
                mode = (row.get("mode") or "").strip("\x00").strip()
                if not ts or not mode:
                    bad_rows += 1
                    continue
                try:
                    t = datetime.fromisoformat(ts)
                except Exception:
                    bad_rows += 1
                    continue
                if (row.get("label") or "").strip() == "MOCK":
                    continue
                if NULLED_START <= t < NULLED_END:
                    continue
                rows.append({
                    "timestamp": t,
                    "mode": mode,
                    "bed_pad_raw": row.get("bed_pad_raw", ""),
                    "desk_pad_raw": row.get("desk_pad_raw", ""),
                    "bed_occupied": row.get("bed_occupied", ""),
                    "desk_occupied": row.get("desk_occupied", ""),
                    "light_raw": row.get("light_raw", ""),
                    "sound_committed_state": row.get("sound_committed_state", ""),
                    "temperature_c": row.get("temperature_c", ""),
                    "humidity_pct": row.get("humidity_pct", ""),
                    "score": row.get("score", ""),
                })
    rows.sort(key=lambda r: r["timestamp"])
    return rows, bad_rows


def analyse(rows, truth):
    confusion = defaultdict(lambda: defaultdict(int))  # truth -> system -> n
    rows_in_truth = 0
    for row in rows:
        t = row["timestamp"]
        system = row["mode"]
        gt = truth_at(truth, t)
        if gt is None:
            continue
        rows_in_truth += 1
        confusion[gt][system] += 1

    # Share of time per system mode across all rows
    system_counts = defaultdict(int)
    for row in rows:
        system_counts[row["mode"]] += 1
    total = sum(system_counts.values())

    # Share per ground truth mode across covered rows
    truth_counts = {m: sum(confusion[m].values()) for m in MODES}
    truth_total = sum(truth_counts.values())

    # Matched percentages: for ground truth mode M, what fraction of
    # rows was the system also in mode M
    matched = {}
    for m in MODES:
        n = truth_counts.get(m, 0)
        if n == 0:
            matched[m] = None
        else:
            matched[m] = 100.0 * confusion[m][m] / n

    # Overall matched (micro average)
    correct = sum(confusion[m][m] for m in MODES)
    overall = 100.0 * correct / truth_total if truth_total else 0.0

    # Hours per system mode (one row ~= 5 seconds)
    POLL_SEC = 5.0
    system_hours = {m: system_counts.get(m, 0) * POLL_SEC / 3600.0 for m in MODES}
    truth_hours = {m: truth_counts.get(m, 0) * POLL_SEC / 3600.0 for m in MODES}

    return {
        "total_rows": total,
        "rows_in_truth": rows_in_truth,
        "overall_matched_pct": round(overall, 1),
        "per_mode": [
            {
                "mode": m,
                "system_rows": system_counts.get(m, 0),
                "system_hours": round(system_hours[m], 2),
                "system_share_pct": round(100.0 * system_counts.get(m, 0) / total, 1) if total else 0,
                "truth_rows": truth_counts.get(m, 0),
                "truth_hours": round(truth_hours[m], 2),
                "truth_share_pct": round(100.0 * truth_counts.get(m, 0) / truth_total, 1) if truth_total else 0,
                "matched_pct": round(matched[m], 1) if matched[m] is not None else None,
            }
            for m in MODES
        ],
        "confusion": {
            m: {s: confusion[m].get(s, 0) for s in MODES} for m in MODES
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--out", default="analysis_results.json")
    args = ap.parse_args()

    print(f"Loading sensor logs from {args.log_dir}...")
    rows, bad = load_sensor_rows(args.log_dir)
    print(f"  {len(rows)} usable rows, {bad} unreadable/incomplete rows skipped")

    truth = parse_truth()
    print(f"  {len(truth)} ground truth windows")

    result = analyse(rows, truth)

    print()
    print(f"Total rows analysed: {result['total_rows']:,}")
    print(f"Rows with ground truth coverage: {result['rows_in_truth']:,}")
    print(f"Overall matched vs ground truth: {result['overall_matched_pct']}%")
    print()
    print(f"{'Mode':<12} {'Sys hours':>10} {'Sys %':>8}   {'GT hours':>10} {'GT %':>8}   {'Matched':>8}")
    for pm in result["per_mode"]:
        matched = f"{pm['matched_pct']}%" if pm['matched_pct'] is not None else "n/a"
        print(f"{pm['mode']:<12} {pm['system_hours']:>10.2f} {pm['system_share_pct']:>7.1f}%   {pm['truth_hours']:>10.2f} {pm['truth_share_pct']:>7.1f}%   {matched:>8}")
    print()
    print("Confusion matrix (rows = ground truth, cols = system mode):")
    header = f"{'':<12}" + "".join(f"{m:>12}" for m in MODES) + f"{'row total':>12}"
    print(header)
    for m in MODES:
        row = result["confusion"][m]
        row_total = sum(row.values())
        line = f"{m:<12}" + "".join(f"{row[s]:>12,}" for s in MODES) + f"{row_total:>12,}"
        print(line)

    with open(args.out, "w") as fp:
        json.dump(result, fp, indent=2, default=str)
    print(f"\nWritten to {args.out}")


if __name__ == "__main__":
    main()
