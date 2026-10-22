"""
analysis.py
-----------
Compare the Team Rocket sensor logs against the hand-written ground
truth, with fault windows removed from both sides. Produces the same
tables the team's Colab notebook produces:

  per-mode:  ground_truth_h, logged_h, correct_h, precision_pct,
             recall_pct, f1_pct
  overall:   totals, micro-precision = micro-recall = overall
             agreement, macro F1
  per-day:   weighted agreement % for each 24-hour block from the first
             sensor timestamp

Also writes analysis_results.json for the dashboard's Analysis tab.

Usage:
    python3 analysis.py --log-dir /path/to/csvs
"""

import argparse
import bisect
import csv
import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

# ---------------- Ground truth (104 entries, parsed from Ground_Truth_Log_7_Days.docx) ----------------
GROUND_TRUTH = [
    ("2026-10-08T11:31:00", "2026-10-08T12:43:00", "study"),
    ("2026-10-08T12:43:00", "2026-10-08T13:10:00", "relax"),
    ("2026-10-08T13:10:00", "2026-10-08T14:18:00", "study"),
    ("2026-10-08T14:18:00", "2026-10-08T14:25:00", "relax"),
    ("2026-10-08T14:25:00", "2026-10-08T14:58:00", "unoccupied"),
    ("2026-10-08T14:58:00", "2026-10-08T16:04:00", "relax"),
    ("2026-10-08T16:04:00", "2026-10-08T19:48:00", "unoccupied"),
    ("2026-10-08T19:48:00", "2026-10-08T20:09:00", "study"),
    ("2026-10-08T20:09:00", "2026-10-09T00:10:00", "relax"),
    ("2026-10-09T00:10:00", "2026-10-09T00:44:00", "unoccupied"),
    ("2026-10-09T00:44:00", "2026-10-09T08:20:00", "sleep"),
    ("2026-10-09T08:20:00", "2026-10-09T10:51:00", "unoccupied"),
    ("2026-10-09T10:51:00", "2026-10-09T11:30:00", "relax"),
    ("2026-10-09T11:30:00", "2026-10-09T12:07:00", "relax"),
    ("2026-10-09T12:07:00", "2026-10-09T13:18:00", "unoccupied"),
    ("2026-10-09T13:18:00", "2026-10-09T13:26:00", "study"),
    ("2026-10-09T13:26:00", "2026-10-09T13:32:00", "unoccupied"),
    ("2026-10-09T13:32:00", "2026-10-09T18:00:00", "study"),
    ("2026-10-09T18:00:00", "2026-10-09T19:58:00", "unoccupied"),
    ("2026-10-09T19:58:00", "2026-10-09T21:33:00", "relax"),
    ("2026-10-09T21:33:00", "2026-10-09T23:08:00", "relax"),
    ("2026-10-09T23:08:00", "2026-10-09T23:33:00", "unoccupied"),
    ("2026-10-09T23:33:00", "2026-10-10T00:53:00", "relax"),
    ("2026-10-10T00:53:00", "2026-10-10T01:02:00", "unoccupied"),
    ("2026-10-10T01:02:00", "2026-10-10T08:13:00", "sleep"),
    ("2026-10-10T08:13:00", "2026-10-10T11:30:00", "unoccupied"),
    ("2026-10-10T11:30:00", "2026-10-10T13:39:00", "unoccupied"),
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
    ("2026-10-11T01:32:00", "2026-10-11T11:04:00", "sleep"),
    ("2026-10-11T11:04:00", "2026-10-11T11:19:00", "unoccupied"),
    ("2026-10-11T11:19:00", "2026-10-11T11:30:00", "study"),
    ("2026-10-11T11:30:00", "2026-10-11T12:26:00", "study"),
    ("2026-10-11T12:26:00", "2026-10-11T12:49:00", "unoccupied"),
    ("2026-10-11T12:49:00", "2026-10-11T13:04:00", "study"),
    ("2026-10-11T13:04:00", "2026-10-11T18:04:00", "relax"),
    ("2026-10-11T18:04:00", "2026-10-12T16:55:00", "nulled"),
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
    ("2026-10-15T11:30:00", "2026-10-15T12:13:00", "study"),
    ("2026-10-15T12:13:00", "2026-10-15T12:49:00", "relax"),
    ("2026-10-15T12:49:00", "2026-10-15T13:28:00", "study"),
    ("2026-10-15T13:28:00", "2026-10-15T13:40:00", "relax"),
    ("2026-10-15T13:40:00", "2026-10-15T14:48:00", "study"),
    ("2026-10-15T14:48:00", "2026-10-15T14:55:00", "relax"),
    ("2026-10-15T14:55:00", "2026-10-15T15:02:00", "unoccupied"),
    ("2026-10-15T15:02:00", "2026-10-15T16:08:00", "relax"),
    ("2026-10-15T16:08:00", "2026-10-15T16:15:00", "study"),
    ("2026-10-15T16:15:00", "2026-10-15T16:32:00", "unoccupied"),
    ("2026-10-15T16:32:00", "2026-10-15T17:20:00", "relax"),
    ("2026-10-15T17:20:00", "2026-10-15T19:58:00", "unoccupied"),
    ("2026-10-15T19:58:00", "2026-10-15T20:50:00", "relax"),
    ("2026-10-15T20:50:00", "2026-10-15T21:53:00", "study"),
    ("2026-10-15T21:53:00", "2026-10-15T22:14:00", "unoccupied"),
    ("2026-10-15T22:14:00", "2026-10-15T22:50:00", "relax"),
    ("2026-10-15T22:50:00", "2026-10-16T01:02:00", "study"),
    ("2026-10-16T01:02:00", "2026-10-16T08:43:00", "sleep"),
    ("2026-10-16T08:43:00", "2026-10-16T10:51:00", "unoccupied"),
    ("2026-10-16T10:51:00", "2026-10-16T11:30:00", "relax"),
    ("2026-10-16T11:30:00", "2026-10-16T12:07:00", "relax"),
    ("2026-10-16T12:07:00", "2026-10-16T13:09:00", "unoccupied"),
    ("2026-10-16T13:09:00", "2026-10-16T13:28:00", "study"),
    ("2026-10-16T13:28:00", "2026-10-16T14:28:00", "unoccupied"),
    ("2026-10-16T14:28:00", "2026-10-16T19:29:00", "relax"),
    ("2026-10-16T19:29:00", "2026-10-16T20:18:00", "unoccupied"),
    ("2026-10-16T20:18:00", "2026-10-16T20:39:00", "study"),
    ("2026-10-16T20:39:00", "2026-10-17T00:40:00", "relax"),
    ("2026-10-17T00:40:00", "2026-10-17T00:56:00", "unoccupied"),
    ("2026-10-17T00:56:00", "2026-10-17T08:27:00", "sleep"),
    ("2026-10-17T08:27:00", "2026-10-17T09:03:00", "relax"),
    ("2026-10-17T09:03:00", "2026-10-17T09:27:00", "unoccupied"),
    ("2026-10-17T09:27:00", "2026-10-17T11:30:00", "study"),
    ("2026-10-17T11:30:00", "2026-10-17T13:04:00", "study"),
    ("2026-10-17T13:04:00", "2026-10-17T16:04:00", "relax"),
    ("2026-10-17T16:04:00", "2026-10-17T18:33:00", "unoccupied"),
    ("2026-10-17T18:33:00", "2026-10-17T19:29:00", "relax"),
    ("2026-10-17T19:29:00", "2026-10-17T20:27:00", "unoccupied"),
    ("2026-10-17T20:27:00", "2026-10-17T21:05:00", "relax"),
    ("2026-10-17T21:05:00", "2026-10-17T21:20:00", "unoccupied"),
    ("2026-10-17T21:20:00", "2026-10-17T23:40:00", "relax"),
    ("2026-10-17T23:40:00", "2026-10-18T00:14:00", "unoccupied"),
    ("2026-10-18T00:14:00", "2026-10-18T08:13:00", "sleep"),
    ("2026-10-18T08:13:00", "2026-10-18T11:30:00", "unoccupied"),
]


# ---------------- Fault windows excluded from both GT and system ----------------
# NULLED window + the five other fault windows from the handoff files.
FAULT_WINDOWS = [
    (datetime(2026,10, 8,13,25), datetime(2026,10, 8,13,34), "Wire pulled"),
    (datetime(2026,10, 9,13,32), datetime(2026,10, 9,15,30), "Light sensor loose"),
    (datetime(2026,10,10,11, 3), datetime(2026,10,10,11, 4), "Multiplug unplugged"),
    (datetime(2026,10,10,20,27), datetime(2026,10,10,20,45), "Desk pad intermittent"),
    (datetime(2026,10,11,11,48), datetime(2026,10,11,12,30), "Both pads unreliable"),
    (datetime(2026,10,11,18, 4), datetime(2026,10,12,16,55), "NULLED (pad broken)"),
]

MODES = ["sleep", "study", "relax", "unoccupied"]

# ---------------- Day boundaries from the ground truth doc ----------------
# Day 1-4 are the real-data days; Day 4 spans the NULLED window.
# Days 5-7 are the synthetic days continuing from Block 1's end.
DAY_BOUNDARIES = [
    (1, datetime(2026,10, 8,11,31), datetime(2026,10, 9,11,30)),
    (2, datetime(2026,10, 9,11,30), datetime(2026,10,10,11,30)),
    (3, datetime(2026,10,10,11,30), datetime(2026,10,11,11,30)),
    (4, datetime(2026,10,11,11,30), datetime(2026,10,13,20,17)),
    (5, datetime(2026,10,15,11,30), datetime(2026,10,16,11,30)),
    (6, datetime(2026,10,16,11,30), datetime(2026,10,17,11,30)),
    (7, datetime(2026,10,17,11,30), datetime(2026,10,18,11,30)),
]

# Cap on how long a single sensor row is treated as covering. If a
# logger restart leaves a 30-minute gap, we don't want to count the
# whole gap as the final row's mode persisting.
MAX_ROW_INTERVAL_SEC = 15.0


# ---------------- Helpers ----------------

def overlap(a_s, a_e, b_s, b_e):
    """Overlap in seconds between [a_s,a_e) and [b_s,b_e)."""
    s, e = max(a_s, b_s), min(a_e, b_e)
    return max(0.0, (e - s).total_seconds())


def subtract_windows(interval_start, interval_end, windows):
    """Return a list of (sub_start, sub_end) that is interval minus every window."""
    # Collect fault edges that fall inside the interval
    cuts = []
    for w_s, w_e, _ in windows:
        ov_s, ov_e = max(interval_start, w_s), min(interval_end, w_e)
        if ov_s < ov_e:
            cuts.append((ov_s, ov_e))
    if not cuts:
        return [(interval_start, interval_end)]
    cuts.sort()
    # Merge overlapping/touching cuts
    merged = [cuts[0]]
    for s, e in cuts[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    # Produce the complement within [interval_start, interval_end)
    pieces = []
    cursor = interval_start
    for s, e in merged:
        if cursor < s:
            pieces.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < interval_end:
        pieces.append((cursor, interval_end))
    return pieces


def load_sensor_rows(log_dir):
    """Yield (timestamp, mode) tuples from all sensor_log_*.csv files,
    skipping MOCK rows and the one incomplete file-tail row."""
    files = sorted(glob.glob(os.path.join(log_dir, "sensor_log_*.csv")))
    rows = []
    bad = 0
    for f in files:
        with open(f, newline="", errors="replace") as fp:
            r = csv.DictReader(fp)
            for row in r:
                ts = (row.get("timestamp") or "").strip("\x00").strip()
                mode = (row.get("mode") or "").strip("\x00").strip()
                if not ts or not mode:
                    bad += 1
                    continue
                try:
                    t = datetime.fromisoformat(ts)
                except Exception:
                    bad += 1
                    continue
                if (row.get("label") or "").strip() == "MOCK":
                    continue
                rows.append((t, mode))
    rows.sort(key=lambda x: x[0])
    return rows, bad


# ---------------- Core analysis ----------------

def day_for(ts):
    """Return the ground-truth-doc Day number for a timestamp, or None."""
    for day, s, e in DAY_BOUNDARIES:
        if s <= ts < e:
            return day
    return None


def analyse(rows, truth):
    """Build the per-mode and per-day tables.

    rows:  list of (datetime, system_mode)
    truth: list of (iso_start, iso_end, gt_mode)
    """
    # Build row intervals (capped)
    intervals = []
    for i, (t, mode) in enumerate(rows):
        if i + 1 < len(rows):
            dt = (rows[i + 1][0] - t).total_seconds()
            if dt > MAX_ROW_INTERVAL_SEC:
                dt = MAX_ROW_INTERVAL_SEC
        else:
            dt = MAX_ROW_INTERVAL_SEC / 3
        intervals.append((t, t + timedelta(seconds=dt), mode))

    # Parse and sort GT
    gt = [(datetime.fromisoformat(s), datetime.fromisoformat(e), a) for s, e, a in truth]
    gt.sort(key=lambda x: x[0])
    gt_starts = [g[0] for g in gt]

    # Confusion: gt_mode -> sys_mode -> seconds
    confusion = defaultdict(lambda: defaultdict(float))
    # Per-day running: day -> (correct_seconds, total_seconds)
    day_correct = defaultdict(float)
    day_total = defaultdict(float)

    for i_s, i_e, sys_mode in intervals:
        # Exclude fault windows from this row interval
        for s, e in subtract_windows(i_s, i_e, FAULT_WINDOWS):
            # For each sub-piece, find overlapping GT entries
            # Candidate GT indices: those with start < e, walk back until end <= s
            idx = bisect.bisect_left(gt_starts, e)
            j = idx - 1
            piece_total_matched = 0.0
            piece_correct = 0.0
            while j >= 0:
                g_s, g_e, g_a = gt[j]
                if g_e <= s:
                    break
                ov = overlap(s, e, g_s, g_e)
                if ov > 0:
                    confusion[g_a][sys_mode] += ov
                    piece_total_matched += ov
                    if g_a == sys_mode:
                        piece_correct += ov
                j -= 1
            # Day bucket: based on the midpoint of this piece, using GT-doc days
            mid = s + (e - s) / 2
            day = day_for(mid)
            if day is not None:
                day_correct[day] += piece_correct
                day_total[day] += piece_total_matched

    # Build per-mode table
    ground_truth_sec = defaultdict(float)
    logged_sec = defaultdict(float)
    for m in MODES:
        for s in MODES:
            ground_truth_sec[m] += confusion[m][s]  # row sum = GT hours (fault-excluded)
            logged_sec[s] += confusion[m][s]        # col sum = logged hours (GT-covered)

    per_mode = {}
    for m in MODES:
        gt_h = ground_truth_sec[m] / 3600
        lg_h = logged_sec[m] / 3600
        correct_h = confusion[m][m] / 3600
        precision = (100.0 * correct_h / lg_h) if lg_h > 0 else None
        recall    = (100.0 * correct_h / gt_h) if gt_h > 0 else None
        if precision is None or recall is None or (precision + recall) == 0:
            f1 = None
        else:
            f1 = 2 * precision * recall / (precision + recall)
        per_mode[m] = {
            "ground_truth_h": round(gt_h, 1),
            "logged_h": round(lg_h, 1),
            "correct_h": round(correct_h, 1),
            "precision_pct": round(precision, 1) if precision is not None else None,
            "recall_pct": round(recall, 1) if recall is not None else None,
            "f1_pct": round(f1, 1) if f1 is not None else None,
        }

    # Overall row
    total_gt = sum(ground_truth_sec[m] for m in MODES) / 3600
    total_logged = sum(logged_sec[m] for m in MODES) / 3600
    total_correct = sum(confusion[m][m] for m in MODES) / 3600
    micro_precision = 100.0 * total_correct / total_logged if total_logged > 0 else None
    micro_recall    = 100.0 * total_correct / total_gt    if total_gt    > 0 else None
    f1s = [per_mode[m]["f1_pct"] for m in MODES if per_mode[m]["f1_pct"] is not None]
    macro_f1 = sum(f1s) / len(f1s) if f1s else None
    overall = {
        "ground_truth_h": round(total_gt, 1),
        "logged_h": round(total_logged, 1),
        "correct_h": round(total_correct, 1),
        "precision_pct": round(micro_precision, 1) if micro_precision is not None else None,
        "recall_pct": round(micro_recall, 1) if micro_recall is not None else None,
        "f1_pct": round(macro_f1, 1) if macro_f1 is not None else None,
    }

    # Per-day agreement
    day_tbl = {}
    for day in sorted(day_total.keys()):
        if day_total[day] == 0:
            continue
        day_tbl[day] = round(100.0 * day_correct[day] / day_total[day], 1)

    # Confusion matrix as hours (for the dashboard and the report writeup)
    confusion_h = {m: {s: round(confusion[m][s] / 3600, 2) for s in MODES} for m in MODES}

    # Backward-compatible fields for the dashboard's Analysis tab
    legacy_per_mode = [{
        "mode": m,
        "system_hours": per_mode[m]["logged_h"],
        "truth_hours": per_mode[m]["ground_truth_h"],
        "matched_pct": per_mode[m]["recall_pct"],
        "system_share_pct": round(100.0 * per_mode[m]["logged_h"] / total_logged, 1) if total_logged else 0,
        "truth_share_pct": round(100.0 * per_mode[m]["ground_truth_h"] / total_gt, 1) if total_gt else 0,
    } for m in MODES]

    legacy_confusion = {
        gt_m: {sys_m: int(confusion[gt_m][sys_m]) for sys_m in MODES}
        for gt_m in MODES
    }

    return {
        # Team-style tables
        "per_mode": per_mode,
        "overall": overall,
        "per_day_agreement_pct": day_tbl,
        "confusion_hours": confusion_h,

        # Dashboard legacy fields (so the existing Analysis tab keeps working)
        "overall_matched_pct": overall["recall_pct"],
        "total_rows": len(rows),
        "rows_in_truth": len(rows),  # approximation; the dashboard shows this for context only
        "per_mode_legacy": legacy_per_mode,
        "confusion": legacy_confusion,
    }


# ---------------- CLI ----------------

def print_tables(result):
    pm, ov = result["per_mode"], result["overall"]
    print("Per-mode agreement (fault windows excluded from both GT and system logs):")
    print(f"{'mode':<12} {'ground_truth_h':>14} {'logged_h':>10} {'correct_h':>11} "
          f"{'precision_pct':>14} {'recall_pct':>12} {'f1_pct':>8}")
    for m in MODES:
        r = pm[m]
        print(f"{m:<12} {r['ground_truth_h']:>14.1f} {r['logged_h']:>10.1f} {r['correct_h']:>11.1f} "
              f"{r['precision_pct']:>14.1f} {r['recall_pct']:>12.1f} {r['f1_pct']:>8.1f}")
    print(f"{'overall':<12} {ov['ground_truth_h']:>14.1f} {ov['logged_h']:>10.1f} {ov['correct_h']:>11.1f} "
          f"{ov['precision_pct']:>14.1f} {ov['recall_pct']:>12.1f} {ov['f1_pct']:>8.1f}")

    print("\nPer-day agreement (weighted by overlap seconds):")
    print(f"{'day':<5} {'agreement_pct':>14}")
    for day, pct in result["per_day_agreement_pct"].items():
        print(f"{day:<5} {pct:>14.1f}")

    print("\nConfusion matrix (hours, rows = GT, cols = system):")
    print(f"{'':<12}" + "".join(f"{m:>12}" for m in MODES))
    for m in MODES:
        row = result["confusion_hours"][m]
        print(f"{m:<12}" + "".join(f"{row[s]:>12.2f}" for s in MODES))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--out", default="analysis_results.json")
    args = ap.parse_args()

    rows, bad = load_sensor_rows(args.log_dir)
    print(f"Loaded {len(rows):,} sensor rows ({bad} unreadable), {len(GROUND_TRUTH)} GT entries, "
          f"{len(FAULT_WINDOWS)} fault windows excluded")
    if not rows:
        return

    print(f"Day boundaries from the GT doc (Day 1-4 real, Day 5-7 synthetic):")
    for day, s, e in DAY_BOUNDARIES:
        print(f"  Day {day}: {s} to {e}")
    print()

    result = analyse(rows, GROUND_TRUTH)
    print_tables(result)

    with open(args.out, "w") as fp:
        json.dump(result, fp, indent=2, default=str)
    print(f"\nWritten to {args.out}")


if __name__ == "__main__":
    main()