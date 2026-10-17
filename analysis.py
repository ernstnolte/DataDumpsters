"""
analysis.py
-----------------
Analytical pass over the ride-hailing research CSVs.

For each of Ernst's 10 selected questions, applies an appropriate
technique (shrinkage ranking, hypothesis testing, regression,
clustering, etc.) and writes:

    ./analysis/<question_id>_<short_name>.png
    ./analysis/summary.txt

Requirements:
    pip install pandas numpy matplotlib seaborn scipy statsmodels scikit-learn
"""

import re
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
DATA_DIR    = Path("data")
ANALYSIS_DIR = Path("analysis")
ANALYSIS_DIR.mkdir(exist_ok=True)

SUMMARY_LOG = ANALYSIS_DIR / "summary.txt"
_summary_buffer: list[str] = []


def log(line: str = ""):
    """Print and buffer a line for summary.txt."""
    print(line)
    _summary_buffer.append(line)


# ─────────────────────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
})


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _save(fig, name: str):
    safe = re.sub(r"[^\w]+", "_", name).strip("_")[:120]
    path = ANALYSIS_DIR / f"{safe}.png"
    fig.savefig(path)
    plt.close(fig)
    log(f"   💾 {path}")


def load_csv(prefix: str) -> pd.DataFrame:
    """
    Load the CSV in ./data/ whose filename begins with `prefix`
    (e.g. '2_1_1' or '2.3.5'). Returns first match or raises.
    """
    pattern = prefix.replace(".", "_")
    matches = sorted(DATA_DIR.glob(f"{pattern}*.csv"))
    if not matches:
        log(f"   !! No CSV found for prefix '{prefix}'")
        return pd.DataFrame()
    return pd.read_csv(matches[0])


def empirical_bayes_rates(successes: np.ndarray,
                          totals: np.ndarray) -> np.ndarray:
    """
    James-Stein style shrinkage of binomial rates toward the global mean.
    Returns adjusted rates.
    """
    successes = np.asarray(successes, dtype=float)
    totals    = np.asarray(totals, dtype=float)

    grand_rate = successes.sum() / totals.sum()
    # Method-of-moments estimate of between-group variance
    raw = successes / np.where(totals == 0, 1, totals)
    obs_var = np.var(raw, ddof=1) if len(raw) > 1 else 0.0
    avg_binom_var = np.mean(grand_rate * (1 - grand_rate) /
                            np.where(totals == 0, 1, totals))
    tau2 = max(obs_var - avg_binom_var, 1e-6)

    weights = tau2 / (tau2 + grand_rate * (1 - grand_rate) /
                      np.where(totals == 0, 1, totals))
    return weights * raw + (1 - weights) * grand_rate


def significance_star(p: float) -> str:
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "ns"


# ═════════════════════════════════════════════════════════════
# Q 7.2.1 (2.1.1) — Cancellations by Hour
# ─────────────────────────────────────────────────────────────
# Appropriate technique: cyclical pattern detection + statistical
# significance of peak vs off-peak cancellation rates.
# ═════════════════════════════════════════════════════════════
def q_7_2_1():
    log("\n" + "=" * 70)
    log("7.2.1 (Q2.1.1) — Cancellations by Hour")
    log("=" * 70)

    df = load_csv("2_1_1")
    if df.empty:
        return
    df = df.sort_values("request_hour").reset_index(drop=True)

    # Basic descriptive
    mean_rate = df["cancellation_rate_pct"].mean()
    std_rate  = df["cancellation_rate_pct"].std()
    top_hours = df.nlargest(3, "cancellation_rate_pct")["request_hour"].tolist()
    log(f"   Mean cancellation rate across hours : {mean_rate:.2f}%")
    log(f"   Std dev                              : {std_rate:.2f}%")
    log(f"   Top 3 hours by cancellation rate     : {top_hours}")

    # Chi-square: are cancellations independent of hour-of-day?
    contingency = np.vstack([
        df["cancellations"].values,
        (df["total_requests"] - df["cancellations"]).values,
    ])
    chi2, p_chi, dof, _ = stats.chi2_contingency(contingency)
    log(f"   Chi-square test (hour × cancelled)   : χ²={chi2:.2f}, "
        f"df={dof}, p={p_chi:.3g} {significance_star(p_chi)}")
    log(f"   Interpretation                       : "
        f"{'cancellation rate depends on hour' if p_chi < 0.05 else 'no hour effect detected'}")

    # Peak / off-peak comparison via two-proportion z-test
    peak_hours    = [7, 8, 9, 17, 18, 19]
    off_hours     = [h for h in df["request_hour"] if h not in peak_hours]
    peak_df = df[df["request_hour"].isin(peak_hours)]
    off_df  = df[df["request_hour"].isin(off_hours)]

    p_peak  = peak_df["cancellations"].sum() / peak_df["total_requests"].sum()
    p_off   = off_df["cancellations"].sum()  / off_df["total_requests"].sum()
    n_peak  = peak_df["total_requests"].sum()
    n_off   = off_df["total_requests"].sum()

    p_pool  = (peak_df["cancellations"].sum() + off_df["cancellations"].sum()) / (n_peak + n_off)
    se      = np.sqrt(p_pool * (1 - p_pool) * (1/n_peak + 1/n_off))
    z       = (p_peak - p_off) / se
    p_z     = 2 * (1 - stats.norm.cdf(abs(z)))
    log(f"   Peak hours rate  : {p_peak*100:.2f}%  (n={int(n_peak):,})")
    log(f"   Off-peak rate    : {p_off*100:.2f}%  (n={int(n_off):,})")
    log(f"   Two-proportion z : z={z:.2f}, p={p_z:.3g} {significance_star(p_z)}")

    # Chart: smoothed curve + peak shading
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["request_hour"], df["cancellation_rate_pct"],
            marker="o", color="#3b7dd8", label="Observed")
    smooth = df["cancellation_rate_pct"].rolling(3, center=True, min_periods=1).mean()
    ax.plot(df["request_hour"], smooth, linestyle="--",
            color="#d85555", linewidth=2, label="3-hour rolling mean")
    ax.axhline(mean_rate, color="grey", linestyle=":", label=f"Mean = {mean_rate:.2f}%")
    for h in peak_hours:
        ax.axvspan(h - 0.5, h + 0.5, color="orange", alpha=0.08)
    ax.set_xticks(range(0, 24))
    ax.set_xlabel("Hour of day (24-hour clock)")
    ax.set_ylabel("Rider cancellation rate (%)")
    ax.set_title(f"Cancellation rate by hour — χ² p={p_chi:.3g}, "
                 f"peak vs off-peak z={z:.2f} ({significance_star(p_z)})")
    ax.legend(loc="upper left")
    _save(fig, "7_2_1_cancellations_by_hour")


# ═════════════════════════════════════════════════════════════
# Q 7.2.2 (2.1.2) — Cancellations by Zone
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Empirical Bayes shrinkage ranking to
# eliminate small-sample bias.
# ═════════════════════════════════════════════════════════════
def q_7_2_2():
    log("\n" + "=" * 70)
    log("7.2.2 (Q2.1.2) — Cancellations by Zone")
    log("=" * 70)

    df = load_csv("2_1_2")
    if df.empty:
        return
    df = df.copy()
    df["raw_rate"] = df["cancellations"] / df["total_requests"]

    df["adj_rate"] = empirical_bayes_rates(
        df["cancellations"].values, df["total_requests"].values)
    df["shrinkage"] = df["raw_rate"] - df["adj_rate"]

    df = df.sort_values("adj_rate", ascending=False)

    log(f"   Zones analysed                : {len(df)}")
    log(f"   Global cancellation rate      : "
        f"{df['cancellations'].sum()/df['total_requests'].sum()*100:.2f}%")
    log(f"   Max raw rate                  : {df['raw_rate'].max()*100:.2f}% "
        f"(n={int(df.loc[df['raw_rate'].idxmax(), 'total_requests']):,})")
    log(f"   Max adjusted (EB) rate        : {df['adj_rate'].max()*100:.2f}%")

    log(f"\n   Top 10 zones — adjusted vs raw:")
    log(f"   {'Zone':<35} {'City':<15} {'Raw%':>7} {'Adj%':>7} {'n':>8}")
    for _, row in df.head(10).iterrows():
        log(f"   {row['zone_name'][:34]:<35} {row['city'][:14]:<15} "
            f"{row['raw_rate']*100:>7.2f} {row['adj_rate']*100:>7.2f} "
            f"{int(row['total_requests']):>8,}")

    # Chart: raw vs adjusted top 15
    top = df.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 8))
    y = np.arange(len(top))
    ax.barh(y + 0.2, top["raw_rate"] * 100, height=0.4,
            color="#a8c4e8", label="Raw rate")
    ax.barh(y - 0.2, top["adj_rate"] * 100, height=0.4,
            color="#3b7dd8", label="Adjusted (Empirical Bayes)")
    ax.set_yticks(y)
    ax.set_yticklabels(top["zone_name"])
    ax.set_xlabel("Cancellation rate (%)")
    ax.set_ylabel("City zone")
    ax.set_title("Top 15 zones — raw vs empirical-Bayes-adjusted cancellation rate")
    ax.legend(loc="lower right")
    _save(fig, "7_2_2_cancellations_by_zone")


# ═════════════════════════════════════════════════════════════
# Q 7.2.3 (2.1.3) — Drivers Above Average
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Concentration analysis (Gini, Lorenz).
# ═════════════════════════════════════════════════════════════
def q_7_2_3():
    log("\n" + "=" * 70)
    log("7.2.3 (Q2.1.3) — Drivers Above Avg Cancellations")
    log("=" * 70)

    df = load_csv("2_1_3")
    if df.empty:
        return
    df = df.sort_values("cancellation_count", ascending=False).reset_index(drop=True)
    counts = df["cancellation_count"].values.astype(float)

    sorted_counts = np.sort(counts)
    n = len(sorted_counts)
    cumulative = np.cumsum(sorted_counts)
    gini = (n + 1 - 2 * np.sum(cumulative) / cumulative[-1]) / n
    top_10_share = sorted_counts[-max(1, int(n * 0.1)):].sum() / sorted_counts.sum()

    log(f"   Drivers above average        : {n}")
    log(f"   Total cancellations by them  : {int(counts.sum()):,}")
    log(f"   Mean per driver              : {counts.mean():.1f}")
    log(f"   Median per driver            : {np.median(counts):.1f}")
    log(f"   Gini coefficient             : {gini:.3f}")
    log(f"   Top 10% share of cancellations: {top_10_share*100:.1f}%")
    log(f"   {'Highly concentrated' if top_10_share > 0.5 else 'Moderately concentrated'}"
        f" — {'targeted intervention sensible' if top_10_share > 0.5 else 'broad intervention may be needed'}")

    # ── Chart ──
    # constrained_layout reserves enough horizontal space for the long
    # driver names on the right panel, and places the suptitle cleanly.
    fig, axes = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)

    ax = axes[0]
    lorenz_x = np.linspace(0, 1, n + 1)
    lorenz_y = np.concatenate([[0], cumulative / cumulative[-1]])
    ax.plot(lorenz_x, lorenz_y, color="#3b7dd8", linewidth=2, label="Drivers")
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="Perfect equality")
    ax.fill_between(lorenz_x, lorenz_y, lorenz_x, alpha=0.15, color="#3b7dd8")
    ax.set_title(f"Lorenz curve — Gini = {gini:.3f}")
    ax.set_xlabel("Cumulative share of drivers")
    ax.set_ylabel("Cumulative share of cancellations")
    ax.legend(loc="upper left")

    ax = axes[1]
    top15 = df.head(15).iloc[::-1]
    names = (top15["first_name"].astype(str).str.strip() + " "
             + top15["last_name"].astype(str).str.strip())
    ax.barh(names, top15["cancellation_count"], color="#d85555")
    # Move driver names to the right side so they never overlap the left panel
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.set_xlabel("Number of cancellations")
    ax.set_ylabel("Driver")
    ax.set_title("Top 15 drivers by cancellation count")
    # Give labels a little breathing room on the right
    ax.tick_params(axis="y", pad=6)

    fig.suptitle("Driver cancellation concentration", fontweight="bold")
    _save(fig, "7_2_3_drivers_above_avg")

# ═════════════════════════════════════════════════════════════
# Q 7.3.1 (2.2.1) — Safety Cancellations by Zone
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Shrinkage ranking + z-test against the
# global safety-cancellation rate with FDR correction.
# ═════════════════════════════════════════════════════════════
def q_7_3_1():
    log("\n" + "=" * 70)
    log("7.3.1 (Q2.2.1) — Safety Cancellations by Zone")
    log("=" * 70)

    df = load_csv("2_2_1")
    if df.empty:
        return
    df = df.copy()
    df["raw_rate"] = df["safety_cancellations"] / df["total_requests"]
    df["adj_rate"] = empirical_bayes_rates(
        df["safety_cancellations"].values, df["total_requests"].values)

    global_rate = df["safety_cancellations"].sum() / df["total_requests"].sum()

    # Per-zone z-test vs global
    df["se"] = np.sqrt(global_rate * (1 - global_rate) / df["total_requests"])
    df["z"]  = (df["raw_rate"] - global_rate) / df["se"]
    df["p"]  = 2 * (1 - stats.norm.cdf(abs(df["z"])))
    # Benjamini-Hochberg FDR
    order = np.argsort(df["p"].values)
    ranked = np.empty_like(order); ranked[order] = np.arange(1, len(df) + 1)
    df["p_adj"] = np.minimum(df["p"].values * len(df) / ranked, 1.0)
    df["sig"]   = df["p_adj"].apply(lambda p: significance_star(p))

    sig_count = (df["p_adj"] < 0.05).sum()
    log(f"   Global safety-cancel rate      : {global_rate*100:.3f}%")
    log(f"   Zones significantly different  : {sig_count} / {len(df)} (FDR-adjusted)")
    log(f"\n   Top 10 zones by adjusted rate:")
    log(f"   {'Zone':<35} {'City':<15} {'Adj%':>8} {'p_adj':>8}")
    for _, row in df.sort_values("adj_rate", ascending=False).head(10).iterrows():
        log(f"   {row['zone_name'][:34]:<35} {row['city'][:14]:<15} "
            f"{row['adj_rate']*100:>8.3f} {row['p_adj']:>8.3f} {row['sig']}")

    # Chart
    top = df.sort_values("adj_rate", ascending=False).head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 8))
    colors = ["#d85555" if s != "ns" else "#a8c4e8" for s in top["sig"]]
    ax.barh(top["zone_name"], top["adj_rate"] * 100, color=colors)
    for i, (_, row) in enumerate(top.iterrows()):
        ax.text(row["adj_rate"] * 100 + 0.01, i,
                f"{row['sig']}", va="center", fontsize=9)
    ax.axvline(global_rate * 100, color="black", linestyle="--",
               label=f"Global rate = {global_rate*100:.3f}%")
    ax.set_xlabel("Adjusted safety-cancellation rate (%)")
    ax.set_ylabel("City zone")
    ax.set_title("Top 15 zones — safety cancellations "
                 "(red = significantly above global after FDR)")
    ax.legend(loc="lower right")
    _save(fig, "7_3_1_safety_cancellations_by_zone")


# ═════════════════════════════════════════════════════════════
# Q 7.4.1 (2.3.1 + 2.3.2) — Vehicle Safety Distribution
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Distribution analysis with entropy +
# concentration of low-rated fleet by zone.
# ═════════════════════════════════════════════════════════════
def q_7_4_1():
    log("\n" + "=" * 70)
    log("7.4.1 (Q2.3.1 + Q2.3.2) — Vehicle Safety Distribution")
    log("=" * 70)

    dist_df = load_csv("2_3_1")
    zone_df = load_csv("2_3_2")

    entropy = np.nan
    if not dist_df.empty:
        counts = dist_df["amount_of_cars"].values
        total  = counts.sum()
        probs  = counts / total
        entropy = -np.sum(probs * np.log(probs)) / np.log(len(probs))
        log(f"   Distribution of adult safety ratings")
        log(f"   Total fleet                         : {int(total):,}")
        log(f"   Entropy (normalised, 0–1)           : {entropy:.3f}")
        log(f"   {'Well spread' if entropy > 0.85 else 'Concentrated'}"
            f" across the 5 rating bands")
        weighted_mean = (dist_df["safety_rating"] * counts).sum() / total
        log(f"   Fleet-weighted mean safety rating   : {weighted_mean:.2f}")

    if not zone_df.empty:
        log(f"\n   Zones analysed                      : {len(zone_df)}")
        log(f"   Mean low-rated-vehicle share        : "
            f"{zone_df['low_adult_safety_pct'].mean():.2f}%")
        log(f"   Max low-rated share                 : "
            f"{zone_df['low_adult_safety_pct'].max():.2f}% "
            f"({zone_df.loc[zone_df['low_adult_safety_pct'].idxmax(), 'zone_name']})")

    # ── Chart ──
    # Wider figure + constrained_layout for the long zone names.
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)

    if not dist_df.empty:
        ax = axes[0]
        ax.bar(dist_df["safety_rating"], dist_df["amount_of_cars"],
               color="#3b7dd8")
        for _, row in dist_df.iterrows():
            ax.text(row["safety_rating"], row["amount_of_cars"],
                    f"{int(row['amount_of_cars']):,}",
                    ha="center", va="bottom", fontsize=9)
        ax.set_xlabel("Adult occupant safety rating (1–5 stars)")
        ax.set_ylabel("Number of vehicles in fleet")
        ax.set_title(f"Fleet safety rating distribution\nEntropy = {entropy:.3f}")
        ax.set_xticks([1, 2, 3, 4, 5])

    if not zone_df.empty:
        ax = axes[1]
        top = zone_df.sort_values("low_adult_safety_pct",
                                  ascending=False).head(15).iloc[::-1]
        ax.barh(top["zone_name"], top["low_adult_safety_pct"], color="#d85555")
        # Move the zone names to the right-hand side, away from the left panel
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.set_xlabel("% of trips in vehicles with adult rating ≤ 2")
        ax.set_ylabel("City zone")
        ax.set_title("Zones with highest share of low-rated vehicles")
        ax.tick_params(axis="y", pad=6)

    fig.suptitle("Vehicle safety — distribution and zonal concentration",
                 fontweight="bold")
    _save(fig, "7_4_1_vehicle_safety_distribution")


# ═════════════════════════════════════════════════════════════
# Q 7.4.2 (2.3.3 + 2.3.5) — Safety Rating vs Cancellations
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Regression of cancellation rate on
# safety rating (adult + child separately).
# ═════════════════════════════════════════════════════════════
def q_7_4_2():
    log("\n" + "=" * 70)
    log("7.4.2 (Q2.3.3 + Q2.3.5) — Safety Rating vs Cancellations")
    log("=" * 70)

    overall = load_csv("2_3_3")
    adult   = load_csv("2_3_5")
    # The 2.3.5b child file will sort after 2.3.5a adult
    child_matches = sorted(DATA_DIR.glob("2_3_5*.csv"))
    child = pd.read_csv(child_matches[1]) if len(child_matches) > 1 else pd.DataFrame()

    def _fit(df, xcol, ycol, label):
        if df.empty or xcol not in df or ycol not in df:
            log(f"   ⚠ {label}: missing columns")
            return None
        d = df.dropna(subset=[xcol, ycol])
        if len(d) < 3:
            return None
        X = sm.add_constant(d[[xcol]])
        model = sm.OLS(d[ycol], X).fit()
        coef  = model.params[xcol]
        p_val = model.pvalues[xcol]
        log(f"   {label:<30} slope={coef:+.4f}, "
            f"R²={model.rsquared:.3f}, p={p_val:.3g} {significance_star(p_val)}")
        return model

    log("   Linear regression of cancellation rate on safety rating:")
    _fit(overall, "adult_safety_rating", "overall_cancellation_pct",
         "Adult (overall cancellations)")
    _fit(adult,   "adult_safety_rating", "rider_cancellation_pct",
         "Adult (rider-initiated)")
    _fit(child,   "child_safety_rating", "rider_cancellation_pct",
         "Child (rider-initiated)")

    # Two-panel chart
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    if not overall.empty:
        d = overall.sort_values("adult_safety_rating")
        ax.plot(d["adult_safety_rating"], d["overall_cancellation_pct"],
                marker="o", color="#3b7dd8", label="Overall cancellations")
    if not adult.empty:
        d = adult.sort_values("adult_safety_rating")
        ax.plot(d["adult_safety_rating"], d["rider_cancellation_pct"],
                marker="s", linestyle="--", color="#d85555",
                label="Rider-initiated")
    ax.set_xlabel("Adult occupant safety rating (1–5 stars)")
    ax.set_ylabel("Cancellation rate (%)")
    ax.set_title("Adult safety rating vs cancellation")
    ax.legend()

    ax = axes[1]
    if not child.empty:
        d = child.sort_values("child_safety_rating")
        ax.plot(d["child_safety_rating"], d["rider_cancellation_pct"],
                marker="s", color="#5aab6b")
    ax.set_xlabel("Child occupant safety rating (1–5 stars)")
    ax.set_ylabel("Rider-initiated cancellation rate (%)")
    ax.set_title("Child safety rating vs cancellation")

    fig.suptitle("Does vehicle safety rating correlate with cancellations?",
                 fontweight="bold", y=1.02)
    _save(fig, "7_4_2_safety_rating_vs_cancellations")


# ═════════════════════════════════════════════════════════════
# Q 7.5.1 (2.4.1 + 2.4.2) — Safety/Age vs Driver Rating
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Simple linear regressions on each
# predictor separately.
# ═════════════════════════════════════════════════════════════
def q_7_5_1():
    log("\n" + "=" * 70)
    log("7.5.1 (Q2.4.1 + Q2.4.2) — Safety/Age vs Driver Rating")
    log("=" * 70)

    safety_df = load_csv("2_4_1")
    age_df    = load_csv("2_4_2")

    m_safety = None
    m_age    = None

    if not safety_df.empty:
        d = safety_df.dropna(subset=["avg_driver_rating", "adult_safety_rating"])
        X = sm.add_constant(d[["adult_safety_rating"]])
        m_safety = sm.OLS(d["avg_driver_rating"], X).fit()
        log(f"   Rating ~ Adult safety rating")
        log(f"   Slope:  {m_safety.params['adult_safety_rating']:+.4f} "
            f"(p={m_safety.pvalues['adult_safety_rating']:.3g} "
            f"{significance_star(m_safety.pvalues['adult_safety_rating'])})")
        log(f"   R²:     {m_safety.rsquared:.4f}")

    if not age_df.empty:
        d = age_df.dropna(subset=["avg_driver_rating", "vehicle_age"])
        X = sm.add_constant(d[["vehicle_age"]])
        m_age = sm.OLS(d["avg_driver_rating"], X).fit()
        log(f"\n   Rating ~ Vehicle age")
        log(f"   Slope:  {m_age.params['vehicle_age']:+.4f} "
            f"(p={m_age.pvalues['vehicle_age']:.3g} "
            f"{significance_star(m_age.pvalues['vehicle_age'])})")
        log(f"   R²:     {m_age.rsquared:.4f}")

    # Chart: two-panel
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    if not safety_df.empty and m_safety is not None:
        d = safety_df.dropna(subset=["avg_driver_rating", "adult_safety_rating"])
        ax.scatter(d["adult_safety_rating"], d["avg_driver_rating"],
                   alpha=0.6, s=60, color="#3b7dd8", edgecolor="white")
        if len(d) > 1:
            xr = np.linspace(d["adult_safety_rating"].min(),
                             d["adult_safety_rating"].max(), 50)
            X = sm.add_constant(pd.DataFrame({"adult_safety_rating": xr}))
            ax.plot(xr, m_safety.predict(X), color="#d85555", linewidth=2)
        ax.set_xlabel("Adult occupant safety rating (1–5 stars)")
        ax.set_ylabel("Average driver rating (1–5 stars)")
        ax.set_title("Driver rating vs vehicle safety rating")

    ax = axes[1]
    if not age_df.empty:
        d = age_df.sort_values("vehicle_age")
        ax.plot(d["vehicle_age"], d["avg_driver_rating"],
                marker="o", color="#3b7dd8")
        ax.set_xlabel("Vehicle age (years since manufacture)")
        ax.set_ylabel("Average driver rating (1–5 stars)")
        ax.set_title("Driver rating by vehicle age")

    fig.suptitle("Fleet characteristics vs driver performance",
                 fontweight="bold", y=1.02)
    _save(fig, "7_5_1_safety_age_vs_driver_rating")


# ═════════════════════════════════════════════════════════════
# Q 7.5.3 (2.4.4) — Ratings by Car Make
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Pearson correlation between the two
# rating dimensions per make, plus a scatter of makes.
# ═════════════════════════════════════════════════════════════
def q_7_5_3():
    log("\n" + "=" * 70)
    log("7.5.3 (Q2.4.4) — Ratings by Car Make")
    log("=" * 70)

    df = load_csv("2_4_4")
    if df.empty:
        return
    df = df.dropna(subset=["avg_driver_rating", "avg_rider_rating"])
    df = df.sort_values("avg_driver_rating", ascending=False)

    log(f"   Car makes analysed              : {len(df)}")
    log(f"   Global mean (driver rating)     : {df['avg_driver_rating'].mean():.3f}")
    log(f"   Global mean (rider rating)      : {df['avg_rider_rating'].mean():.3f}")
    log(f"\n   Top 5 by driver rating:")
    for _, row in df.head(5).iterrows():
        log(f"     {row['make']:<20} driver={row['avg_driver_rating']:.3f}  "
            f"rider={row['avg_rider_rating']:.3f}")

    # Correlation between the two rating directions per make
    corr_r, corr_p = np.nan, np.nan
    if len(df) > 2:
        corr_r, corr_p = stats.pearsonr(df["avg_driver_rating"],
                                        df["avg_rider_rating"])
        log(f"\n   Correlation (driver vs rider rating across makes): "
            f"r={corr_r:.3f}, p={corr_p:.3g} {significance_star(corr_p)}")

    # Chart: paired bars + scatter
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))

    ax = axes[0]
    top = df.head(15).iloc[::-1]
    y = np.arange(len(top))
    ax.barh(y + 0.2, top["avg_driver_rating"], height=0.4,
            color="#3b7dd8", label="Driver rated by rider")
    ax.barh(y - 0.2, top["avg_rider_rating"], height=0.4,
            color="#5aab6b", label="Rider rated by driver")
    ax.set_yticks(y)
    ax.set_yticklabels(top["make"])
    ax.set_xlabel("Average rating (1–5 stars)")
    ax.set_ylabel("Vehicle manufacturer")
    ax.set_xlim(0, 5)
    ax.set_title("Top 15 car makes by driver rating")
    ax.legend(loc="lower right")

    ax = axes[1]
    ax.scatter(df["avg_driver_rating"], df["avg_rider_rating"],
               s=80, color="#3b7dd8", edgecolor="white")
    for _, row in df.iterrows():
        ax.annotate(row["make"],
                    (row["avg_driver_rating"], row["avg_rider_rating"]),
                    fontsize=8, alpha=0.75,
                    xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel("Average driver rating (rated by rider)")
    ax.set_ylabel("Average rider rating (rated by driver)")
    if not np.isnan(corr_r):
        ax.set_title(f"Per-make ratings — r={corr_r:.2f} "
                     f"{significance_star(corr_p)}")
    else:
        ax.set_title("Per-make ratings")
    ax.plot([3.5, 5], [3.5, 5], linestyle="--", color="grey", alpha=0.5)

    fig.suptitle("Car make vs ratings", fontweight="bold", y=1.02)
    _save(fig, "7_5_3_ratings_by_car_make")


# ═════════════════════════════════════════════════════════════
# Q 7.5.5 (2.4.6) — Vehicle Category vs Ratings
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Spread analysis across categories.
# ═════════════════════════════════════════════════════════════
def q_7_5_5():
    log("\n" + "=" * 70)
    log("7.5.5 (Q2.4.6) — Vehicle Category vs Ratings")
    log("=" * 70)

    df = load_csv("2_4_6")
    if df.empty:
        return
    df = df.dropna(subset=["avg_driver_rating"])
    df = df.sort_values("avg_driver_rating", ascending=False)

    grand_mean = df["avg_driver_rating"].mean()
    spread = df["avg_driver_rating"].max() - df["avg_driver_rating"].min()

    log(f"   Categories analysed             : {len(df)}")
    log(f"   Grand mean rating               : {grand_mean:.3f}")
    log(f"   Rating range across categories  : "
        f"{df['avg_driver_rating'].min():.3f} – {df['avg_driver_rating'].max():.3f}")
    log(f"   Spread (max − min)              : {spread:.3f} stars")
    log(f"   {'Worth investigating' if spread > 0.2 else 'Differences likely minor'}")

    log(f"\n   Category breakdown:")
    for _, row in df.iterrows():
        delta = row["avg_driver_rating"] - grand_mean
        log(f"     {row['category_type']:<20} "
            f"rating={row['avg_driver_rating']:.3f}  "
            f"Δ vs mean={delta:+.3f}")

    # Chart
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(df["category_type"], df["avg_driver_rating"],
                  color="#5aab6b")
    ax.axhline(grand_mean, color="black", linestyle="--",
               label=f"Grand mean = {grand_mean:.3f}")
    for b, v in zip(bars, df["avg_driver_rating"]):
        ax.text(b.get_x() + b.get_width()/2, v,
                f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, 5)
    ax.set_xlabel("Vehicle category")
    ax.set_ylabel("Average driver rating (1–5 stars)")
    ax.set_title("Average driver rating by vehicle category")
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    _save(fig, "7_5_5_vehicle_category_vs_ratings")


# ═════════════════════════════════════════════════════════════
# Q 7.6.2 (2.5.2 + 2.5.3) — Experience vs Cancellations/Ratings
# ─────────────────────────────────────────────────────────────
# Appropriate technique: Pearson correlation on year-binned
# means to reveal the trend.
# ═════════════════════════════════════════════════════════════
def q_7_6_2():
    log("\n" + "=" * 70)
    log("7.6.2 (Q2.5.2 + Q2.5.3) — Experience vs Cancellations/Ratings")
    log("=" * 70)

    cancel_df = load_csv("2_5_2")
    rating_df = load_csv("2_5_3")

    # Cancellations vs experience — pool by year
    if not cancel_df.empty:
        cols = [c for c in ["rider_cancel_rate", "driver_cancel_rate",
                            "completion_rate"] if c in cancel_df.columns]
        d = cancel_df.groupby("years_experience", as_index=False)[cols].mean()
        log(f"   Experience range                : "
            f"{d['years_experience'].min()}–{d['years_experience'].max()} years")
        for c in cols:
            if len(d) > 2:
                corr_r, corr_p = stats.pearsonr(d["years_experience"], d[c])
                log(f"   {c:<22} vs experience: r={corr_r:+.3f}, "
                    f"p={corr_p:.3g} {significance_star(corr_p)}")

    # Ratings vs experience
    if not rating_df.empty:
        d = rating_df.groupby("years_experience",
                              as_index=False)["avg_driver_rating"].mean()
        if len(d) > 2:
            corr_r, corr_p = stats.pearsonr(d["years_experience"],
                                            d["avg_driver_rating"])
            log(f"   {'avg_driver_rating':<22} vs experience: "
                f"r={corr_r:+.3f}, p={corr_p:.3g} {significance_star(corr_p)}")

    # Chart: two-panel
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    if not cancel_df.empty:
        cols = [c for c in ["rider_cancel_rate", "driver_cancel_rate",
                            "completion_rate"] if c in cancel_df.columns]
        d = cancel_df.groupby("years_experience", as_index=False)[cols].mean()
        for c in cols:
            ax.plot(d["years_experience"], d[c], marker="o", label=c)
        ax.set_xlabel("Driver experience (years since onboarding)")
        ax.set_ylabel("Rate (0–1)")
        ax.set_title("Trip outcome rates by experience")
        ax.legend()

    ax = axes[1]
    if not rating_df.empty:
        d = rating_df.groupby("years_experience",
                              as_index=False)["avg_driver_rating"].mean()
        ax.plot(d["years_experience"], d["avg_driver_rating"],
                marker="o", color="#3b7dd8")
        ax.set_xlabel("Driver experience (years since onboarding)")
        ax.set_ylabel("Average driver rating (1–5 stars)")
        ax.set_title("Driver rating by experience")

    fig.suptitle("Driver experience vs performance outcomes",
                 fontweight="bold", y=1.02)
    _save(fig, "7_6_2_experience_vs_cancellations_ratings")


# ═════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════
ANALYSES = [
    ("7.2.1", q_7_2_1),
    ("7.2.2", q_7_2_2),
    ("7.2.3", q_7_2_3),
    ("7.3.1", q_7_3_1),
    ("7.4.1", q_7_4_1),
    ("7.4.2", q_7_4_2),
    ("7.5.1", q_7_5_1),
    ("7.5.3", q_7_5_3),
    ("7.5.5", q_7_5_5),
    ("7.6.2", q_7_6_2),
]


def main():
    log(f"▶ Running {len(ANALYSES)} analyses — reading from ./{DATA_DIR}/")
    log(f"▶ Output folder: ./{ANALYSIS_DIR}/\n")

    for qid, fn in ANALYSES:
        try:
            fn()
        except Exception as e:
            log(f"\n   ⚠ {qid} failed: {e}")

    SUMMARY_LOG.write_text("\n".join(_summary_buffer), encoding="utf-8")
    print(f"\n✅ Done. Chart(s) + summary.txt in ./{ANALYSIS_DIR}/")


if __name__ == "__main__":
    main()