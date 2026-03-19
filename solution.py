"""
anomaly_detection.py
Sentio Mind · Project 5 · Behavioral Anomaly & Early Distress Detection

Copy this file to solution.py and fill in every TODO block.
Do not rename any function. No OpenCV needed — pure data analysis.
Run: python solution.py
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict, Counter

# ---------------------------------------------------------------------------
# CONFIG — adjust thresholds here, nowhere else
# ---------------------------------------------------------------------------
DATA_DIR   = Path("sample_data")
REPORT_OUT = Path("alert_digest.html")
FEED_OUT   = Path("alert_feed.json")
SCHOOL     = "International School"

THRESHOLDS = {
    "sudden_drop_delta":           20,   # baseline - today >= this → SUDDEN_DROP
    "sudden_drop_high_std_delta":  30,   # used when baseline_std > 15
    "sustained_low_score":         45,   # below this = low
    "sustained_low_days":           3,   # consecutive days below threshold
    "social_withdrawal_delta":     25,   # social_engagement drop
    "hyperactivity_delta":         40,   # combined energy spike
    "regression_recover_days":      3,   # days improving before regression counts
    "regression_drop":             15,   # drop after recovery
    "gaze_avoidance_days":          3,   # consecutive days no eye contact
    "absence_days":                 2,   # days not detected
    "baseline_window":              3,   # days used for baseline
    "high_std_baseline":           15,   # if std above this, use relaxed threshold
}


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------

def load_daily_data(folder: Path) -> dict:
    """
    Read all analysis_*.json files from folder.
    Return: { "YYYY-MM-DD": { "PERSON_ID": { wellbeing, traits, gaze, name, ... }, ... }, ... }

    Each Sentio Mind daily file has the structure from the README.
    Parse it and flatten into the above format.
    If your dataset uses a different format, adapt the parsing here.

    TODO: implement
    """
    daily = {}
    for fp in sorted(folder.glob("*.json")):
        # TODO: load and parse each file
        with open(fp, "r") as f:
            data = json.load(f)

        date = data.get("date")
        persons = data.get("persons", [])

        daily[date] = {}

        for person in persons:
            person_id = person.get("person_id")

            daily[date][person_id] = {
                "name": person.get("name"),
                "wellbeing": person.get("wellbeing_score"),

                "social_engagement": person.get("traits", {}).get("social_engagement"),
                "physical_energy": person.get("traits", {}).get("physical_energy"),
                "movement_energy": person.get("traits", {}).get("movement_energy"),
                
                "gaze_direction": person.get("gaze_direction"),
                "eye_contact": person.get("eye_contact")
            }

    return daily


# ---------------------------------------------------------------------------
# BASELINE
# ---------------------------------------------------------------------------

def compute_baseline(history: list) -> dict:
    """
    history: list of daily dicts (oldest first), each has at minimum:
      { wellbeing: int, traits: {}, gaze_direction: str }

    Use first THRESHOLDS['baseline_window'] days.
    Return:
      { wellbeing_mean, wellbeing_std, trait_means: {}, avg_gaze: str }

    TODO: implement
    """
    window = THRESHOLDS['baseline_window']

    #Take first N days
    baseline_days = history[:window]

    wellbeing_values = [
        day.get("wellbeing", 0) for day in baseline_days
        if day.get("wellbeing") is not None
    ]

    if wellbeing_values:
        wellbeing_mean = np.mean(wellbeing_values)
        wellbeing_std = np.std(wellbeing_values)
    else:
        wellbeing_mean = 0
        wellbeing_std = 0

    trait_keys = ["social_engagement", "physical_energy", "movement_energy"]
    trait_means = {}

    for key in trait_keys:
        values = [
            day.get(key) for day in baseline_days
            if day.get(key) is not None
        ]

        trait_means[key] = np.round(float(np.mean(values)), 2) if values else 0

    gaze_values = [
        day.get("gaze_direction") for day in baseline_days
        if day.get("gaze_direction") is not None
    ]

    if gaze_values:
        avg_gaze = Counter(gaze_values).most_common(1)[0][0]
    else:
        avg_gaze = "forward"
    
    # TODO

    return {
        "wellbeing_mean": np.round(float(wellbeing_mean), 2),
        "wellbeing_std":  np.round(float(wellbeing_std), 2),
        "trait_means":    trait_means,
        "avg_gaze":       avg_gaze,
    }


# ---------------------------------------------------------------------------
# ANOMALY DETECTORS  — each returns an alert dict or None
# ---------------------------------------------------------------------------

def detect_sudden_drop(today: dict, baseline: dict) -> dict | None:
    """
    today['wellbeing'] vs baseline['wellbeing_mean'].
    If baseline_std > 15, raise threshold to sudden_drop_high_std_delta.
    Severity: delta > 35 = urgent, else monitor.
    TODO: implement
    """
    if not today or not baseline:
        return None
    
    today_wellbeing = today.get("wellbeing")
    baseline_mean = baseline.get("wellbeing_mean",0)
    baseline_std = baseline.get("wellbeing_std",0)

    if today_wellbeing is None:
        return None
    
    delta = baseline_mean - today_wellbeing

    if baseline_std > THRESHOLDS["high_std_baseline"]:
        threshold = THRESHOLDS["sudden_drop_high_std_delta"]
    else:
        threshold = THRESHOLDS["sudden_drop_delta"]
    
    if delta >= threshold:
        severity = "urgent" if delta >= 35 else "monitor"

        return {
            "category": "SUDDEN_DROP",
            "severity": severity,
            "value": round(delta, 2),
            "description": f"Wellbeing dropped by {delta:.1f} points from baseline",
            "recommended_action": "Check-in with student; monitor mood and engagement"
        }
    
    # TODO
    return None


def detect_sustained_low(history: list) -> dict | None:
    """
    Check the last sustained_low_days entries in history.
    If all have wellbeing < sustained_low_score → alert.
    Severity: urgent.
    TODO: implement
    """
    days_required = THRESHOLDS["sustained_low_days"]
    threshold = THRESHOLDS["sustained_low_score"]

    if len(history) < days_required:
        return None
    
    recent_days = history[-days_required:]

    low_days = [
        day.get("wellbeing")
        for day in recent_days
        if day.get("wellbeing") is not None   
    ] 

    if len(low_days) < days_required:
        return None
    
    if all(w < threshold for w in low_days):
        return {
            "category": "SUSTAINED_LOW",
            "severity": "urgent",
            "value": min(low_days),
            "description": f"Wellbeing below {threshold} for {days_required} consecutive days",
            "recommended_action": "Immediate intervention recommended; check student wellbeing"
        }
    
    # TODO
    return None


def detect_social_withdrawal(today: dict, baseline: dict) -> dict | None:
    """
    social_engagement dropped >= social_withdrawal_delta AND
    today's gaze_direction is "down" or "side".
    Severity: monitor.
    TODO: implement
    """
    if not today or not baseline:
        return None
    
    today_social = today.get("social_engagement")
    baseline_social = baseline.get("trait_means", {}).get("social_engagement")

    gaze = today.get("gaze_direction")
    
    if today_social is None or baseline_social is None:
        return None
    
    delta = baseline_social - today_social

    threshold = THRESHOLDS["social_withdrawal_delta"]

    if delta >= threshold and gaze in ["down", "side"]:
        return {
            "category": "SOCIAL_WITHDRAWAL",
            "severity": "monitor",
            "value" : round(delta, 2),
            "description": f"Social engagement dropped by {delta:.1f} with downward/size gaze",
            "recommended_action": "Encourage social interaction; monitor peer engagement"
        }
    
    # TODO
    return None


def detect_hyperactivity_spike(today: dict, baseline: dict) -> dict | None:
    """
    (today.physical_energy + today.movement_energy) minus
    (baseline.physical_energy_mean + baseline.movement_energy_mean) >= hyperactivity_delta.
    Severity: monitor.
    TODO: implement
    """
    if not today or not baseline:
        return None
    
    today_physical = today.get("physical_energy")
    today_movement = today.get("movement_energy")

    baseline_traits = baseline.get("trait_means", {})
    base_physical = baseline_traits.get("physical_energy")
    base_movement = baseline_traits.get("movement_energy")

    if None in [today_physical, today_movement, base_physical, base_movement]:
        return None
    
    today_total = today_physical + today_movement
    baseline_total = base_physical + base_movement

    delta = today_total - baseline_total

    threshold = THRESHOLDS["hyperactivity_delta"]

    if delta >= threshold:
        return {
            "category": "HYPERACTIVITY_SPIKE",
            "severity": "monitor",
            "value": round(delta, 2),
            "description": f"Energy levels increased by {delta:.1f} above baseline",
            "recommended_action": "Observe for restlessness or overstimulation"
        }

    # TODO
    return None


def detect_regression(history: list) -> dict | None:
    """
    Find if the last regression_recover_days entries were all improving (each > previous),
    then today dropped > regression_drop.
    Severity: monitor.
    TODO: implement
    """
    recover_days = THRESHOLDS["regression_recover_days"]
    drop_threshold = THRESHOLDS["regression_drop"]

    if len(history) < recover_days + 1:
        return None
    
    recovery_phase = history[-(recover_days + 1):-1]
    today = history[-1]

    recovery_values = [
        day.get("wellbeing")
        for day in recovery_phase
        if day.get("wellbeing") is not None
    ]

    today_wellbeing = today.get("wellbeing")

    if len(recovery_values) < recover_days or today_wellbeing is None:
        return None
    
    is_increasing = all(
        recovery_values[i] > recovery_values[i - 1]
        for i in range(1, len(recovery_values))
    )   

    if not is_increasing:
        return None
    
    last_recovery = recovery_values[-1]
    drop = last_recovery - today_wellbeing

    if drop >= drop_threshold:
        return {
            "category": "REGRESSION",
            "severity": "monitor",
            "value": round(drop, 2),
            "description": f"Wellbeing improved then dropped by {drop:.1f}",
            "recommended_action": "Monitor closely; investigate possible setbacks"
        }


    # TODO
    return None


def detect_gaze_avoidance(history: list) -> dict | None:
    """
    Last gaze_avoidance_days entries all have eye_contact == False (or missing).
    Severity: monitor.
    TODO: implement
    """
    days_required = THRESHOLDS["gaze_avoidance_days"]

    if len(history) < days_required:
        return None
    
    recent_days = history[-days_required:]

    no_eye_contact = [
        day.get("eye_contact") for day in recent_days
    ]

    if all(ec is False or ec is None for ec in no_eye_contact):
        return {
            "category": "GAZE_AVOIDANCE",
            "severity": "monitor",
            "value": days_required,
            "description": f"No eye contact observed for {days_required} consecutive days",
            "recommended_action": "Encourage engagement; monitor emotional state"
        }
    
    # TODO
    return None


# ---------------------------------------------------------------------------
# ANALYSE ONE PERSON
# ---------------------------------------------------------------------------

def analyse_person(person_id: str, sorted_days: dict, info: dict) -> list:
    """
    sorted_days: { "YYYY-MM-DD": person_data_dict } — keys in date order
    info: { name, profile_image_b64, ... }

    Build history list, compute baseline, run all detectors.
    Return list of alert dicts. Each alert must include person_id, person_name, date,
    and all fields from anomaly_detection.json schema.

    TODO: implement
    """
    alerts = []

    history = []

    person_name = next(iter(sorted_days.values())).get("name", person_id)
    
    profile_image = info.get("profile_image_b64", "")

    alert_counter = 1
    
    consecutive_flags = defaultdict(int)

    for date, today_data in sorted_days.items():
        history.append(today_data)

        if len(history) < THRESHOLDS["baseline_window"]:
            continue

        baseline = compute_baseline(history)

        # Run detectors
        detector_outputs = [
            detect_sudden_drop(today_data, baseline),
            detect_sustained_low(history),
            detect_social_withdrawal(today_data, baseline),
            detect_hyperactivity_spike(today_data, baseline),
            detect_regression(history),
            detect_gaze_avoidance(history),
        ]

        for det in detector_outputs:
            if not det:
                continue

            category = det["category"]

            # Track consecutive flags
            consecutive_flags[category] += 1

            today_wb = today_data.get("wellbeing", 0)
            base_wb  = baseline.get("wellbeing_mean", 0)
            delta    = today_wb - base_wb

            # Last 5 days trend
            trend = [
                d.get("wellbeing", 0)
                for d in history[-5:]
            ]

            # Lowest trait
            traits = {
                "social_engagement": today_data.get("social_engagement"),
                "physical_energy": today_data.get("physical_energy"),
                "movement_energy": today_data.get("movement_energy"),
            }

            valid_traits = {k: v for k, v in traits.items() if v is not None}
            if valid_traits:
                lowest_trait = min(valid_traits, key=valid_traits.get)
                lowest_value = valid_traits[lowest_trait]
            else:
                lowest_trait = None
                lowest_value = None

            alert = {
                "alert_id": f"ALT_{alert_counter:03d}",
                "person_id": person_id,
                "person_name": person_name,
                "date": date,
                "severity": det.get("severity"),
                "_note_severity": "one of: urgent / monitor / informational",
                "category": category,
                "_note_category": "one of: SUDDEN_DROP / SUSTAINED_LOW / SOCIAL_WITHDRAWAL / HYPERACTIVITY_SPIKE / REGRESSION / GAZE_AVOIDANCE / ABSENCE_FLAG",

                "title": category.replace("_", " ").title(),

                "description": f"{person_name}'s wellbeing changed from baseline {base_wb:.1f} to {today_wb}.",

                "baseline_wellbeing": round(base_wb, 2),
                "today_wellbeing": today_wb,
                "delta": round(delta, 2),

                "days_flagged_consecutively": consecutive_flags[category],

                "trend_last_5_days": trend,

                "lowest_trait": lowest_trait,
                "lowest_trait_value": lowest_value,

                "recommended_action": det.get("recommended_action"),

                "profile_image_b64": profile_image
            }

            alerts.append(alert)
            alert_counter += 1

    return alerts


# ---------------------------------------------------------------------------
# HTML REPORT
# ---------------------------------------------------------------------------

def generate_alert_digest(alerts: list, absence_flags: list,
                           school_summary: dict, output_path: Path):
    """
    Self-contained HTML — no CDN, inline CSS only.

    Section 1: Today's alerts sorted by severity.
      Each card: person name, badge (urgent=red, monitor=amber), description,
      5-day sparkline (inline SVG or just coloured squares — keep it simple).

    Section 2: School summary numbers.

    Section 3: Persons flagged 3+ consecutive days.

    TODO: implement
    """

    today_str = str(date.today())

    # ----------------------------
    # Today's alerts
    # ----------------------------
    todays_alerts = [a for a in alerts if a.get("date") == today_str]

    severity_order = {"urgent": 0, "monitor": 1, "informational": 2}
    todays_alerts.sort(key=lambda x: severity_order.get(x.get("severity"), 3))

    # ----------------------------
    # Persistent alerts (3+ days)
    # ----------------------------
    persistent = [
        a for a in alerts
        if a.get("days_flagged_consecutively", 0) >= 3
    ]

    seen = set()
    persistent_people = []
    for a in persistent:
        if a["person_id"] not in seen:
            persistent_people.append(a["person_name"])
            seen.add(a["person_id"])

    # ----------------------------
    # HTML START
    # ----------------------------
    html = f"""
    <html>
    <head>
        <title>Alert Digest</title>
        <style>
            body {{ font-family: Arial; background: #f5f5f5; padding: 20px; }}
            .card {{ background: white; padding: 15px; margin-bottom: 12px; border-radius: 8px; }}
            .urgent {{ border-left: 6px solid red; }}
            .monitor {{ border-left: 6px solid orange; }}

            .badge {{
                padding: 4px 8px;
                border-radius: 5px;
                color: white;
                font-size: 12px;
                margin-left: 10px;
            }}

            .badge-urgent {{ background: red; }}
            .badge-monitor {{ background: orange; }}

            .spark span {{
                display:inline-block;
                width:10px;
                height:10px;
                margin-right:2px;
                border-radius:2px;
            }}
        </style>
    </head>
    <body>

    <h1>📊 Alert Digest - {SCHOOL}</h1>

    <h2>🚨 Today's Alerts</h2>
    """

    # ----------------------------
    # Section 1: Alerts
    # ----------------------------
    if not todays_alerts:
        html += "<p>No alerts today 🎉</p>"
    else:
        for a in todays_alerts:
            severity = a["severity"]
            trend = a.get("trend_last_5_days", [])

            # simple sparkline (green → red)
            spark = ""
            for val in trend:
                color = "#4caf50" if val > 60 else "#ff9800" if val > 40 else "#f44336"
                spark += f'<span style="background:{color}"></span>'

            html += f"""
            <div class="card {severity}">
                <b>{a['person_name']}</b>
                <span class="badge badge-{severity}">{severity.upper()}</span>

                <p><b>{a['category']}</b>: {a['description']}</p>

                <div class="spark">{spark}</div>
            </div>
            """

    # ----------------------------
    # Section 2: School Summary
    # ----------------------------
    html += f"""
    <h2>🏫 School Summary</h2>
    <ul>
        <li>Total Persons: {school_summary.get("total_persons_tracked", 0)}</li>
        <li>Flagged Today: {school_summary.get("persons_flagged_today", 0)}</li>
        <li>Flagged Yesterday: {school_summary.get("persons_flagged_yesterday", 0)}</li>
        <li>Most Common Issue: {school_summary.get("most_common_anomaly_this_week", "N/A")}</li>
    </ul>
    """

    # ----------------------------
    # Section 3: Persistent Alerts
    # ----------------------------
    html += "<h2>⚠️ Persistent Alerts (3+ days)</h2>"

    if not persistent_people:
        html += "<p>None</p>"
    else:
        html += "<ul>"
        for name in persistent_people:
            html += f"<li>{name}</li>"
        html += "</ul>"

    # ----------------------------
    # Absence Section
    # ----------------------------
    if absence_flags:
        html += "<h2>🚫 Absence Alerts</h2><ul>"
        for a in absence_flags:
            html += f"<li>{a['person_name']} - {a['days_absent']} days absent</li>"
        html += "</ul>"

    html += "</body></html>"

    # ----------------------------
    # Write file
    # ----------------------------
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    daily_data = load_daily_data(DATA_DIR)
    all_dates  = sorted(daily_data.keys())
    print(f"Loaded {len(daily_data)} days: {all_dates}")

    # Build per-person history
    person_days = defaultdict(dict)
    person_info = {}
    for d, persons in daily_data.items():
        for pid, pdata in persons.items():
            person_days[pid][d] = pdata
            if pid not in person_info:
                person_info[pid] = pdata.get("person_info", {"name": pid, "profile_image_b64": ""})

    all_alerts    = []
    absence_flags = []

    for pid, days in person_days.items():
        sorted_days   = dict(sorted(days.items()))
        person_alerts = analyse_person(pid, sorted_days, person_info.get(pid, {}))
        all_alerts.extend(person_alerts)

        # Check absence
        present   = set(days.keys())
        absent    = 0
        for d in reversed(all_dates):
            if d not in present:
                absent += 1
            else:
                break
        if absent >= THRESHOLDS["absence_days"]:
            last_seen = sorted(present)[-1] if present else "unknown"
            absence_flags.append({
                "person_id":        pid,
                "person_name":      person_info.get(pid, {}).get("name", pid),
                "last_seen_date":   last_seen,
                "days_absent":      absent,
                "recommended_action": "Welfare check — contact family if absent again tomorrow",
            })

    sev_order = {"urgent": 0, "monitor": 1, "informational": 2}
    all_alerts.sort(key=lambda a: sev_order.get(a.get("severity", "informational"), 3))

    today_str = str(date.today())
    flagged_today = sum(1 for a in all_alerts if a.get("date") == today_str)
    cat_counter   = Counter(a.get("category") for a in all_alerts)
    top_category  = cat_counter.most_common(1)[0][0] if cat_counter else "none"

    school_summary = {
        "total_persons_tracked":       len(person_days),
        "persons_flagged_today":       flagged_today,
        "persons_flagged_yesterday":   0,   # extend if you have yesterday's run stored
        "most_common_anomaly_this_week": top_category,
        "school_avg_wellbeing_today":  0,   # compute from daily_data[today_str] if available
    }

    feed = {
        "source":        "p5_anomaly_detection",
        "generated_at":  datetime.now().isoformat(),
        "school":        SCHOOL,
        "alert_summary": {
            "total_alerts":  len(all_alerts),
            "urgent":        sum(1 for a in all_alerts if a.get("severity") == "urgent"),
            "monitor":       sum(1 for a in all_alerts if a.get("severity") == "monitor"),
            "informational": sum(1 for a in all_alerts if a.get("severity") == "informational"),
        },
        "alerts":        all_alerts,
        "absence_flags": absence_flags,
        "school_summary": school_summary,
    }

    with open(FEED_OUT, "w") as f:
        json.dump(feed, f, indent=2)

    generate_alert_digest(all_alerts, absence_flags, school_summary, REPORT_OUT)

    print()
    print("=" * 50)
    print(f"  Alerts:  {feed['alert_summary']['total_alerts']} total  "
          f"({feed['alert_summary']['urgent']} urgent, {feed['alert_summary']['monitor']} monitor)")
    print(f"  Absence flags: {len(absence_flags)}")
    print(f"  Report → {REPORT_OUT}")
    print(f"  JSON   → {FEED_OUT}")
    print("=" * 50)

