"""
visualize.py
------------
Reads query result files produced by run_research.py (CSVs in ./output/)
and generates one chart per research question, saving them as PNGs in
./graphs/.

Does NOT connect to Oracle. Run run_research.py first to generate the
input files.

Requirements:
    pip install pandas numpy matplotlib seaborn
"""

import re
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                    # headless – safe everywhere
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")              # where run_research.py wrote CSVs
GRAPH_DIR  = Path("graphs")              # where to save PNGs
GRAPH_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
})


# ─────────────────────────────────────────────────────────────
# AXIS LABEL DICTIONARY
# One source of truth for every axis title used in the charts.
# Edit here to change a label everywhere it appears.
# ─────────────────────────────────────────────────────────────
LABELS = {
    # shared column names
    "request_hour":                "Hour of day (24-hour clock)",
    "cancellation_rate_pct":       "Rider cancellation rate (% of requests)",
    "cancellations":               "Number of cancellations",
    "total_requests":              "Total ride requests",
    "zone_name":                   "City zone",
    "city":                        "City",
    "surge_multiplier":            "Surge price multiplier (× base fare)",
    "pricing_surge_cancellations": "Cancellations citing pricing surge",
    "preferred_payment":           "Rider's preferred payment method",
    "safety_cancellation_rate_pct":
                                   "Safety-related cancellation rate (% of requests)",
    "avg_driver_rating":           "Average driver rating (1–5 stars)",
    "safety_rating":               "Adult occupant safety rating (1–5 stars)",
    "amount_of_cars":              "Number of vehicles in fleet",
    "low_adult_safety_pct":        "% of trips in vehicles with adult rating ≤ 2",
    "low_child_safety_pct":        "% of trips in vehicles with child rating ≤ 2",
    "adult_safety_rating":         "Adult occupant safety rating (1–5 stars)",
    "child_safety_rating":         "Child occupant safety rating (1–5 stars)",
    "overall_cancellation_pct":    "Overall cancellation rate (% of trips)",
    "rider_cancellation_pct":      "Rider-initiated cancellation rate (% of trips)",
    "average_vehicle_age_years":   "Average vehicle age (years since manufacture)",
    "vehicle_age":                 "Vehicle age (years since manufacture)",
    "make":                        "Vehicle manufacturer",
    "model":                       "Vehicle model",
    "category_type":               "Vehicle category (e.g. sedan, SUV, van)",
    "rating_tier":                 "Driver rating tier",
    "years_experience":            "Driver experience (years since onboarding)",
    "platform_affiliation":        "Platform the driver is affiliated with",
    "driver":                      "Driver name",
    "cancellation_count":          "Number of cancellations by this driver",
    "metric":                      "Metric",
    "rate":                        "Rate (share of trips, 0–1)",
    "pct":                         "Rate (% of trips)",
    "rating":                      "Average rating (1–5 stars)",
    "side":                        "Rating direction",
}


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _save(fig, name: str):
    """Save and close a figure with a clean filename."""
    safe = re.sub(r"[^\w]+", "_", name).strip("_")[:120]
    path = GRAPH_DIR / f"{safe}.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"   💾 {path}")


def _safe(df: pd.DataFrame, *cols) -> pd.DataFrame:
    """Return df only if all needed columns exist and df isn't empty."""
    if df is None or df.empty:
        return pd.DataFrame()
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"   ⚠ missing columns: {missing}")
        return pd.DataFrame()
    return df


def _ylabel(col: str) -> str:
    """Look up a friendly label, fall back to a tidied column name."""
    if col in LABELS:
        return LABELS[col]
    return col.replace("_", " ").capitalize()


def _wrap_ticks(ax, axis: str = "y", width: int = 28):
    """Wrap long tick labels so they don't squash the plot area."""
    labels = ax.get_yticklabels() if axis == "y" else ax.get_xticklabels()
    new = [textwrap.fill(t.get_text(), width) for t in labels]
    if axis == "y":
        ax.set_yticklabels(new)
    else:
        ax.set_xticklabels(new, rotation=30, ha="right")


def _bar_labels(ax, fmt="{:.1f}", axis: str = "y", pad: int = 1):
    """
    Annotate each bar with its value.
      axis='y' → value printed at end of a horizontal bar
      axis='x' → value printed above a vertical bar
    """
    if axis == "y":  # horizontal bars: label at right edge
        for p in ax.patches:
            w = p.get_width()
            if w != w:  # NaN guard
                continue
            ax.annotate(fmt.format(w),
                        (w, p.get_y() + p.get_height() / 2),
                        xytext=(pad, 0), textcoords="offset points",
                        va="center", fontsize=8, color="#333")
    else:            # vertical bars: label above
        for p in ax.patches:
            h = p.get_height()
            if h != h:
                continue
            ax.annotate(fmt.format(h),
                        (p.get_x() + p.get_width() / 2, h),
                        xytext=(0, pad), textcoords="offset points",
                        ha="center", fontsize=8, color="#333")


def load_results(source: Path = OUTPUT_DIR) -> dict:
    """
    Load every CSV in `source` into a dict keyed by query ID.

    Keys are reconstructed from filenames. run_research.py names files
    by replacing non-word chars with '_', so e.g.:
        "2_1_1_Which_times_during_the_day_are_riders_more_likely_to_cancel_a_ride.csv"
    becomes key
        "2_1_1_Which_times_during_the_day_are_riders_more_likely_to_cancel_a_ride"
    """
    results = {}
    if not source.exists():
        raise FileNotFoundError(
            f"'{source}' not found. Run run_research.py first to generate CSVs."
        )

    for csv_file in sorted(source.glob("*.csv")):
        if csv_file.name.startswith("all_results"):
            continue
        key = csv_file.stem                       # remove .csv
        try:
            df = pd.read_csv(csv_file)
            results[key] = df
        except Exception as e:
            print(f"   ⚠ Could not read {csv_file.name}: {e}")
    return results


def group_by_query_prefix(results: dict) -> dict:
    """
    Group result keys by their numeric query prefix, e.g.
        {"2.1.1": ["2_1_1_Which_times...", ...], "2.3.5": [...]}

    Handles both filename style ('2_1_1_...') and space style ('2.1.1 ...').
    """
    by_prefix = {}
    for key in results:
        m = re.match(r"^(\d+(?:[._]\d+)+)", key)
        if not m:
            continue
        prefix = m.group(1).replace("_", ".")
        by_prefix.setdefault(prefix, []).append(key)
    return by_prefix


# ─────────────────────────────────────────────────────────────
# CHART BUILDERS — one per query family
# ─────────────────────────────────────────────────────────────
def chart_2_1_1(df):
    """Q: At what hours are riders most likely to cancel?"""
    df = _safe(df, "request_hour", "cancellation_rate_pct")
    if df.empty: return
    d = df.sort_values("request_hour")
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.barplot(data=d, x="request_hour", y="cancellation_rate_pct",
                color="#3b7dd8", ax=ax)
    ax.set_title("Rider cancellation rate by hour of day", pad=12)
    ax.set_xlabel(LABELS["request_hour"])
    ax.set_ylabel(LABELS["cancellation_rate_pct"])
    ax.set_xticks(range(0, 24))
    _bar_labels(ax, fmt="{:.1f}", axis="x", pad=2)
    _save(fig, "2_1_1_cancellation_by_hour")


def chart_2_1_2(df):
    """Q: In which zones are riders most likely to cancel?"""
    df = _safe(df, "zone_name", "cancellation_rate_pct", "city")
    if df.empty: return
    d = df.sort_values("cancellation_rate_pct", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="zone_name", x="cancellation_rate_pct",
                hue="city", dodge=False, ax=ax)
    ax.set_title("Top 20 zones by rider cancellation rate", pad=12)
    ax.set_xlabel(LABELS["cancellation_rate_pct"])
    ax.set_ylabel(LABELS["zone_name"])
    ax.legend(title=LABELS["city"], bbox_to_anchor=(1.02, 1), loc="upper left")
    _bar_labels(ax, fmt="{:.2f}", axis="y", pad=2)
    _save(fig, "2_1_2_cancellation_by_zone")


def chart_2_1_3(df):
    """Q: Which drivers have above-average cancellations?"""
    df = _safe(df, "first_name", "last_name", "cancellation_count")
    if df.empty: return
    d = df.copy()
    d["driver"] = (d["first_name"].astype(str).str.strip()
                   + " " + d["last_name"].astype(str).str.strip())
    d = d.sort_values("cancellation_count", ascending=False).head(25)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="driver", x="cancellation_count",
                color="#d85555", ax=ax)
    ax.set_title("Drivers with above-average cancellations (top 25)", pad=12)
    ax.set_xlabel(LABELS["cancellation_count"])
    ax.set_ylabel(LABELS["driver"])
    _bar_labels(ax, fmt="{:.0f}", axis="y", pad=2)
    _save(fig, "2_1_3_above_avg_driver_cancellations")


def chart_2_1_4(df):
    """Q: How many cancellations cited safety concerns?"""
    if df is None or df.empty: return
    val = df.iloc[0, 0]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.text(0.5, 0.55, f"{int(val):,}", ha="center", va="center",
            fontsize=48, fontweight="bold", color="#3b7dd8")
    ax.text(0.5, 0.20, "Cancellations citing safety concerns",
            ha="center", va="center", fontsize=12, color="#444")
    ax.text(0.5, 0.05, "Total across all trips",
            ha="center", va="center", fontsize=9, color="#888", style="italic")
    ax.axis("off")
    _save(fig, "2_1_4_safety_cancellations_count")


def chart_2_1_5(df):
    """Q: At what surge multiplier do riders cancel citing pricing?"""
    df = _safe(df, "surge_multiplier", "pricing_surge_cancellations")
    if df.empty: return
    d = df.sort_values("surge_multiplier")
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=d, x="surge_multiplier", y="pricing_surge_cancellations",
                color="#e08a2b", ax=ax)
    ax.set_title("Cancellations citing pricing surge, by surge multiplier",
                 pad=12)
    ax.set_xlabel(LABELS["surge_multiplier"])
    ax.set_ylabel(LABELS["pricing_surge_cancellations"])
    _bar_labels(ax, fmt="{:.0f}", axis="x", pad=2)
    _save(fig, "2_1_5_surge_threshold")


def chart_2_1_6(df):
    """Q: Does preferred payment method correlate with cancellation?"""
    df = _safe(df, "preferred_payment", "cancellation_rate_pct")
    if df.empty: return
    d = df.sort_values("cancellation_rate_pct", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=d, x="preferred_payment", y="cancellation_rate_pct",
                color="#5aab6b", ax=ax)
    ax.set_title("Cancellation rate by rider's preferred payment method",
                 pad=12)
    ax.set_xlabel(LABELS["preferred_payment"])
    ax.set_ylabel(LABELS["cancellation_rate_pct"])
    _bar_labels(ax, fmt="{:.2f}", axis="x", pad=2)
    _save(fig, "2_1_6_cancellation_by_payment")


def chart_2_2_1(df):
    """Q: Which zones have the highest safety-cancellation rates?"""
    df = _safe(df, "zone_name", "safety_cancellation_rate_pct", "city")
    if df.empty: return
    d = df.sort_values("safety_cancellation_rate_pct", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="zone_name", x="safety_cancellation_rate_pct",
                hue="city", dodge=False, ax=ax)
    ax.set_title("Top 20 zones by safety-cancellation rate", pad=12)
    ax.set_xlabel(LABELS["safety_cancellation_rate_pct"])
    ax.set_ylabel(LABELS["zone_name"])
    ax.legend(title=LABELS["city"], bbox_to_anchor=(1.02, 1), loc="upper left")
    _bar_labels(ax, fmt="{:.2f}", axis="y", pad=2)
    _save(fig, "2_2_1_safety_cancellations_by_zone")


def chart_2_2_2(df):
    """Q: Which zones have the lowest average driver ratings?"""
    df = _safe(df, "zone_name", "avg_driver_rating", "city")
    if df.empty: return
    d = df.sort_values("avg_driver_rating").head(20)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="zone_name", x="avg_driver_rating",
                hue="city", dodge=False, ax=ax)
    ax.set_title("Lowest-rated 20 zones by average driver rating", pad=12)
    ax.set_xlabel(LABELS["avg_driver_rating"])
    ax.set_ylabel(LABELS["zone_name"])
    ax.set_xlim(0, 5)
    ax.legend(title=LABELS["city"], bbox_to_anchor=(1.02, 1), loc="upper left")
    _bar_labels(ax, fmt="{:.2f}", axis="y", pad=2)
    _save(fig, "2_2_2_lowest_rated_zones")


def chart_2_2_3(df):
    """Q: Which zones have the highest safety-concern rate?"""
    df = _safe(df, "zone_name", "safety_cancellation_rate_pct", "city")
    if df.empty: return
    d = df.sort_values("safety_cancellation_rate_pct", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="zone_name", x="safety_cancellation_rate_pct",
                hue="city", dodge=False, ax=ax)
    ax.set_title("Top 20 zones by safety-concern cancellation rate", pad=12)
    ax.set_xlabel(LABELS["safety_cancellation_rate_pct"])
    ax.set_ylabel(LABELS["zone_name"])
    ax.legend(title=LABELS["city"], bbox_to_anchor=(1.02, 1), loc="upper left")
    _bar_labels(ax, fmt="{:.2f}", axis="y", pad=2)
    _save(fig, "2_2_3_safety_concern_by_zone")


def chart_2_3_1(df):
    """Q: How are vehicle safety ratings distributed across the fleet?"""
    df = _safe(df, "safety_rating", "amount_of_cars")
    if df.empty: return
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=df.sort_values("safety_rating"),
                x="safety_rating", y="amount_of_cars",
                color="#3b7dd8", ax=ax)
    ax.set_title("Distribution of adult occupant safety ratings", pad=12)
    ax.set_xlabel(LABELS["safety_rating"])
    ax.set_ylabel(LABELS["amount_of_cars"])
    _bar_labels(ax, fmt="{:,.0f}", axis="x", pad=2)
    _save(fig, "2_3_1_vehicle_safety_distribution")


def chart_2_3_2(df):
    """Q: Which zones have the highest concentration of low-rated vehicles?"""
    df = _safe(df, "zone_name", "low_adult_safety_pct", "city")
    if df.empty: return
    d = df.sort_values("low_adult_safety_pct", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="zone_name", x="low_adult_safety_pct",
                hue="city", dodge=False, ax=ax)
    ax.set_title("Zones with highest share of low-rated vehicles (adult ≤ 2)",
                 pad=12)
    ax.set_xlabel(LABELS["low_adult_safety_pct"])
    ax.set_ylabel(LABELS["zone_name"])
    ax.legend(title=LABELS["city"], bbox_to_anchor=(1.02, 1), loc="upper left")
    _bar_labels(ax, fmt="{:.2f}%", axis="y", pad=2)
    _save(fig, "2_3_2_low_rated_vehicle_zones")


def chart_2_3_3(df):
    """Q: Does a lower vehicle safety rating coincide with higher cancellations?"""
    df = _safe(df, "adult_safety_rating", "overall_cancellation_pct")
    if df.empty: return
    d = df.sort_values("adult_safety_rating")
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=d, x="adult_safety_rating", y="overall_cancellation_pct",
                color="#d85555", ax=ax)
    ax.set_title("Cancellation rate vs adult vehicle safety rating", pad=12)
    ax.set_xlabel(LABELS["adult_safety_rating"])
    ax.set_ylabel(LABELS["overall_cancellation_pct"])
    _bar_labels(ax, fmt="{:.2f}", axis="x", pad=2)
    _save(fig, "2_3_3_cancellation_vs_safety_rating")


def chart_2_3_4(df):
    """Q: What is the average vehicle age per zone?"""
    df = _safe(df, "zone_name", "average_vehicle_age_years", "city")
    if df.empty: return
    d = df.sort_values("average_vehicle_age_years", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="zone_name", x="average_vehicle_age_years",
                hue="city", dodge=False, ax=ax)
    ax.set_title("Zones with the oldest average vehicle age", pad=12)
    ax.set_xlabel(LABELS["average_vehicle_age_years"])
    ax.set_ylabel(LABELS["zone_name"])
    ax.legend(title=LABELS["city"], bbox_to_anchor=(1.02, 1), loc="upper left")
    _bar_labels(ax, fmt="{:.1f}", axis="y", pad=2)
    _save(fig, "2_3_4_avg_vehicle_age_by_zone")


def chart_2_3_5_adult(df):
    """Q: Are rider cancellations sensitive to adult safety rating?"""
    df = _safe(df, "adult_safety_rating", "rider_cancellation_pct")
    if df.empty: return
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.lineplot(data=df.sort_values("adult_safety_rating"),
                 x="adult_safety_rating", y="rider_cancellation_pct",
                 marker="o", ax=ax)
    ax.set_title("Rider cancellation vs adult occupant safety rating", pad=12)
    ax.set_xlabel(LABELS["adult_safety_rating"])
    ax.set_ylabel(LABELS["rider_cancellation_pct"])
    ax.set_xticks(sorted(df["adult_safety_rating"].dropna().unique()))
    _save(fig, "2_3_5a_rider_cancel_vs_adult_safety")


def chart_2_3_5_child(df):
    """Q: Are rider cancellations sensitive to child safety rating?"""
    df = _safe(df, "child_safety_rating", "rider_cancellation_pct")
    if df.empty: return
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.lineplot(data=df.sort_values("child_safety_rating"),
                 x="child_safety_rating", y="rider_cancellation_pct",
                 marker="o", color="#d85555", ax=ax)
    ax.set_title("Rider cancellation vs child occupant safety rating", pad=12)
    ax.set_xlabel(LABELS["child_safety_rating"])
    ax.set_ylabel(LABELS["rider_cancellation_pct"])
    ax.set_xticks(sorted(df["child_safety_rating"].dropna().unique()))
    _save(fig, "2_3_5b_rider_cancel_vs_child_safety")


def chart_2_4_1(df):
    """Q: Does vehicle safety rating relate to driver ratings?"""
    df = _safe(df, "model", "avg_driver_rating", "adult_safety_rating")
    if df.empty: return
    d = df.dropna(subset=["avg_driver_rating", "adult_safety_rating"])
    if d.empty: return
    fig, ax = plt.subplots(figsize=(10, 6))
    size_col = "vehicle_year" if "vehicle_year" in d.columns else None
    sns.scatterplot(data=d, x="adult_safety_rating", y="avg_driver_rating",
                    size=size_col, sizes=(40, 200), ax=ax)
    ax.set_title("Driver rating vs vehicle safety rating (one dot per model)",
                 pad=12)
    ax.set_xlabel(LABELS["adult_safety_rating"])
    ax.set_ylabel(LABELS["avg_driver_rating"])
    ax.set_xlim(0, 5.5)
    _save(fig, "2_4_1_rating_vs_safety")


def chart_2_4_2(df):
    """Q: Does vehicle age relate to driver ratings?"""
    df = _safe(df, "vehicle_age", "avg_driver_rating")
    if df.empty: return
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.lineplot(data=df.sort_values("vehicle_age"),
                 x="vehicle_age", y="avg_driver_rating",
                 marker="o", ax=ax)
    ax.set_title("Average driver rating by vehicle age", pad=12)
    ax.set_xlabel(LABELS["vehicle_age"])
    ax.set_ylabel(LABELS["avg_driver_rating"])
    _save(fig, "2_4_2_rating_vs_vehicle_age")


def chart_2_4_4(df):
    """Q: How do ratings compare across car makes?"""
    df = _safe(df, "make", "avg_driver_rating", "avg_rider_rating")
    if df.empty: return
    d = df.sort_values("avg_driver_rating", ascending=False).head(20)
    d = d.melt(id_vars="make",
               value_vars=["avg_driver_rating", "avg_rider_rating"],
               var_name="side", value_name="rating")
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.barplot(data=d, y="make", x="rating", hue="side", ax=ax)
    ax.set_title("Average ratings by vehicle make (top 20 by driver rating)",
                 pad=12)
    ax.set_xlabel(LABELS["rating"])
    ax.set_ylabel(LABELS["make"])
    ax.legend(title="Rating source",
              labels=["Driver rated by rider", "Rider rated by driver"],
              bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xlim(0, 5)
    _save(fig, "2_4_4_ratings_by_make")


def chart_2_4_5(df):
    """Q: Do cancellations/completions vary with vehicle age?"""
    df = _safe(df, "vehicle_age")
    if df.empty: return
    cols = [c for c in ["rider_cancel_rate", "driver_cancel_rate", "completion_rate"]
            if c in df.columns]
    if not cols: return
    rename = {
        "rider_cancel_rate":   "Rider cancellation rate",
        "driver_cancel_rate":  "Driver cancellation rate",
        "completion_rate":     "Completion rate",
    }
    d = df.sort_values("vehicle_age").melt(
        id_vars="vehicle_age", value_vars=cols,
        var_name="metric", value_name="rate")
    d["metric"] = d["metric"].map(rename)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=d, x="vehicle_age", y="rate",
                 hue="metric", marker="o", ax=ax)
    ax.set_title("Cancellation and completion rates by vehicle age", pad=12)
    ax.set_xlabel(LABELS["vehicle_age"])
    ax.set_ylabel(LABELS["rate"])
    ax.legend(title="Trip outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    _save(fig, "2_4_5_rates_vs_vehicle_age")


def chart_2_4_6(df):
    """Q: Does vehicle category influence ratings?"""
    df = _safe(df, "category_type", "avg_driver_rating")
    if df.empty: return
    d = df.sort_values("avg_driver_rating", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=d, x="category_type", y="avg_driver_rating",
                color="#5aab6b", ax=ax)
    ax.set_title("Average driver rating by vehicle category", pad=12)
    ax.set_xlabel(LABELS["category_type"])
    ax.set_ylabel(LABELS["avg_driver_rating"])
    ax.set_ylim(0, 5)
    _bar_labels(ax, fmt="{:.2f}", axis="x", pad=2)
    _wrap_ticks(ax, "x", width=20)
    _save(fig, "2_4_6_rating_by_category")


def chart_2_5_1(df):
    """Q: Do lower-rated drivers have higher cancellation / lower completion?"""
    df = _safe(df, "rating_tier", "completion_rate_pct", "cancellation_rate_pct")
    if df.empty: return
    d = df.groupby("rating_tier", as_index=False)[
        ["completion_rate_pct", "cancellation_rate_pct"]].mean()
    rename = {
        "completion_rate_pct":   "Completion rate",
        "cancellation_rate_pct": "Cancellation rate",
    }
    d = d.melt(id_vars="rating_tier", var_name="metric", value_name="pct")
    d["metric"] = d["metric"].map(rename)
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=d, x="rating_tier", y="pct", hue="metric", ax=ax)
    ax.set_title("Trip outcome rates by driver rating tier", pad=12)
    ax.set_xlabel(LABELS["rating_tier"])
    ax.set_ylabel("Rate (% of trips)")
    ax.legend(title="Trip outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    _bar_labels(ax, fmt="{:.1f}", axis="x", pad=2)
    _save(fig, "2_5_1_rates_by_rating_tier")


def chart_2_5_2(df):
    """Q: Does driver experience affect cancellation / completion?"""
    df = _safe(df, "years_experience")
    if df.empty: return
    cols = [c for c in ["rider_cancel_rate", "driver_cancel_rate", "completion_rate"]
            if c in df.columns]
    if not cols: return
    rename = {
        "rider_cancel_rate":   "Rider cancellation rate",
        "driver_cancel_rate":  "Driver cancellation rate",
        "completion_rate":     "Completion rate",
    }
    d = (df.groupby("years_experience", as_index=False)[cols].mean()
           .melt(id_vars="years_experience", var_name="metric", value_name="rate"))
    d["metric"] = d["metric"].map(rename)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=d, x="years_experience", y="rate",
                 hue="metric", marker="o", ax=ax)
    ax.set_title("Trip outcome rates by years of driver experience", pad=12)
    ax.set_xlabel(LABELS["years_experience"])
    ax.set_ylabel(LABELS["rate"])
    ax.legend(title="Trip outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    _save(fig, "2_5_2_rates_vs_experience")


def chart_2_5_3(df):
    """Q: Does more experience mean higher ratings?"""
    df = _safe(df, "years_experience", "avg_driver_rating")
    if df.empty: return
    d = df.groupby("years_experience", as_index=False)["avg_driver_rating"].mean()
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=d, x="years_experience", y="avg_driver_rating",
                 marker="o", ax=ax)
    ax.set_title("Average driver rating by years of experience", pad=12)
    ax.set_xlabel(LABELS["years_experience"])
    ax.set_ylabel(LABELS["avg_driver_rating"])
    _save(fig, "2_5_3_rating_vs_experience")


def chart_2_5_4(df):
    """Q: Do outcome rates differ across platforms?"""
    df = _safe(df, "platform_affiliation")
    if df.empty: return
    cols = [c for c in ["rider_cancel_rate", "driver_cancel_rate", "completion_rate"]
            if c in df.columns]
    if not cols: return
    rename = {
        "rider_cancel_rate":   "Rider cancellation rate",
        "driver_cancel_rate":  "Driver cancellation rate",
        "completion_rate":     "Completion rate",
    }
    d = df.melt(id_vars="platform_affiliation", value_vars=cols,
                var_name="metric", value_name="rate")
    d["metric"] = d["metric"].map(rename)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=d, x="platform_affiliation", y="rate",
                hue="metric", ax=ax)
    ax.set_title("Trip outcome rates by platform affiliation", pad=12)
    ax.set_xlabel(LABELS["platform_affiliation"])
    ax.set_ylabel(LABELS["rate"])
    ax.legend(title="Trip outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    _wrap_ticks(ax, "x", width=16)
    _save(fig, "2_5_4_rates_by_platform")


# ─────────────────────────────────────────────────────────────
# DISPATCH TABLE
# ─────────────────────────────────────────────────────────────
DISPATCH = [
    ("2.1.1", chart_2_1_1),
    ("2.1.2", chart_2_1_2),
    ("2.1.3", chart_2_1_3),
    ("2.1.4", chart_2_1_4),
    ("2.1.5", chart_2_1_5),
    ("2.1.6", chart_2_1_6),
    ("2.2.1", chart_2_2_1),
    ("2.2.2", chart_2_2_2),
    ("2.2.3", chart_2_2_3),
    ("2.3.1", chart_2_3_1),
    ("2.3.2", chart_2_3_2),
    ("2.3.3", chart_2_3_3),
    ("2.3.4", chart_2_3_4),
    ("2.3.5", chart_2_3_5_adult),
    ("2.3.5", chart_2_3_5_child),
    ("2.4.1", chart_2_4_1),
    ("2.4.2", chart_2_4_2),
    ("2.4.4", chart_2_4_4),
    ("2.4.5", chart_2_4_5),
    ("2.4.6", chart_2_4_6),
    ("2.5.1", chart_2_5_1),
    ("2.5.2", chart_2_5_2),
    ("2.5.3", chart_2_5_3),
    ("2.5.4", chart_2_5_4),
]


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def visualize_all(results: dict):
    print(f"\n▶ Generating charts into ./{GRAPH_DIR}/ ...\n")

    by_prefix = group_by_query_prefix(results)
    if not by_prefix:
        print("   ⚠ No query files matched the expected 'X.Y.Z' naming pattern.")
        print("   Check that ./output/ contains CSVs from run_research.py.")
        return

    for prefix, fn in DISPATCH:
        for key in by_prefix.get(prefix, []):
            try:
                fn(results[key])
            except Exception as e:
                print(f"   ⚠ {prefix} ({key}): {e}")


if __name__ == "__main__":
    print(f"→ Loading query results from ./{OUTPUT_DIR}/ ...")
    results = load_results(OUTPUT_DIR)
    print(f"   ✔ Loaded {len(results)} result file(s)")

    visualize_all(results)

    print(f"\n✔ All charts saved to ./{GRAPH_DIR}/")