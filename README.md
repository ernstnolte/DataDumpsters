# DataDumpsters — Ride-Hailing Analytics Visualizer

A Python toolkit that turns a set of pre-generated CSV result files into
publication-ready charts.

The project has two moving parts:

| File | Purpose |
|---|---|
| `visualize.py` | Reads every CSV from `./data/`, produces one PNG chart per research question into `./graphs/` |
| `requirements.txt` | Python dependencies (pandas, numpy, matplotlib, seaborn) |

The CSV files in `./data/` were generated previously by running the research
queries against an Oracle 11g XE database. **This project does not connect to
any database** — it works entirely from the CSVs on disk.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Layout](#project-layout)
3. [Installation](#installation)
   1. [Install 64-bit Python](#1-install-64-bit-python)
   2. [Create and activate a virtual environment](#2-create-and-activate-a-virtual-environment)
   3. [Install Python dependencies](#3-install-python-dependencies)
4. [Running the Graph Generator](#running-the-graph-generator)
5. [Input Files](#input-files)
6. [Output Files](#output-files)
7. [Troubleshooting](#troubleshooting)
8. [Customising Charts](#customising-charts)

---

## Prerequisites

- **Windows 10 or 11 (64-bit)** — the pipeline is developed and tested on Windows.
- **Internet access** for the initial `pip install`.

You do **not** need Oracle Database, Oracle Instant Client, SQL Developer, or
any database credentials. All the data the charts need is already sitting in
`./data/`.

---

## Project Layout

```
DataDumpsters/
├── visualize.py                # Reads CSVs, produces charts
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── data/                       # Input CSVs (already generated)
│   ├── 2_1_1_Which_times_...csv
│   ├── 2_1_2_In_which_area_...csv
│   ├── ...
│   └── 2_5_4_Do_trip_cancellation_...csv
└── graphs/                     # Created by visualize.py
    ├── 2_1_1_cancellation_by_hour.png
    ├── 2_1_2_cancellation_by_zone.png
    └── ...
```

---

## Installation

### 1. Install 64-bit Python

This project requires **64-bit Python**. 32-bit Python has no prebuilt wheels
for recent versions of `pandas`, which forces `pip` to try compiling from
source and fail.

1. Download **"Windows installer (64-bit)"** from
   <https://www.python.org/downloads/windows/>.
2. During installation, tick **"Add python.exe to PATH"** at the bottom of the
   first screen.
3. Open a fresh terminal and verify:

   ```bat
   python --version
   python -c "import platform; print(platform.architecture())"
   ```

   You should see something like `Python 3.12.x` and
   `('64bit', 'WindowsPE')`.

   > **Note:** Python **3.11 or 3.12** is the safest choice — every package in
   > `requirements.txt` has prebuilt Windows wheels for those versions. If
   > you're on 3.13 or newer, see [Troubleshooting](#troubleshooting).

### 2. Create and activate a virtual environment

From the project root:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

Your prompt should now start with `(.venv)`. Confirm the venv is using the
right interpreter:

```bat
python -c "import sys; print(sys.executable)"
```

The path should contain `.venv\Scripts\python.exe`.

> **To deactivate later:** simply run `deactivate`.

### 3. Install Python dependencies

With the venv still active:

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The `requirements.txt` pins ranges known to have prebuilt Windows wheels:

```txt
pandas>=2.0,<4.0
numpy>=1.24,<3.0
matplotlib>=3.8,<4.0
seaborn>=0.13,<1.0
```

Verify the installation:

```bat
python -c "import pandas, numpy, matplotlib, seaborn; print('OK')"
```

---

## Running the Graph Generator

Make sure the venv is active and `./data/` contains your CSV files, then run:

```bat
python visualize.py
```

Expected output:

```
▶ Loading query results from ./data/ ...
   ✔ Loaded 24 result file(s)

▶ Generating charts into ./graphs/ ...
   💾 graphs\2_1_1_cancellation_by_hour.png
   💾 graphs\2_1_2_cancellation_by_zone.png
   💾 graphs\2_1_3_above_avg_driver_cancellations.png
   ...
   💾 graphs\2_5_4_rates_by_platform.png

✅ All charts saved to ./graphs/
```

Once finished, open the `graphs/` folder and inspect the PNGs. Each file is
named after the query ID, so `2_1_1_cancellation_by_hour.png` corresponds to
question 2.1.1 in the original research.

You can rerun `visualize.py` as many times as you like — it always reads the
CSVs fresh and overwrites the PNGs.

---

## Input Files

The `./data/` directory contains one CSV per research query. The filename
begins with the query ID (e.g. `2_1_1_...`), which is how `visualize.py`
matches each file to the correct chart function.

The CSVs are expected to be UTF-8 encoded, comma-separated, with a header row.
They were produced by `pandas.DataFrame.to_csv()` and can be opened in Excel,
Google Sheets, or loaded directly with `pd.read_csv`.

If you need to regenerate the CSVs, you must do so from the original Oracle
database — that step is outside the scope of this project.

---

## Output Files

`visualize.py` writes one PNG per research question into `./graphs/`. Each
chart is 150 DPI, styled with seaborn, and named after its query ID.

| File | Question it answers |
|---|---|
| `2_1_1_cancellation_by_hour.png` | At what hours are riders most likely to cancel? |
| `2_1_2_cancellation_by_zone.png` | Which zones have the highest cancellation rate? |
| `2_1_3_above_avg_driver_cancellations.png` | Which drivers cancel more than average? |
| `2_1_4_safety_cancellations_count.png` | How many cancellations cited safety concerns? |
| `2_1_5_surge_threshold.png` | At what surge multiplier do riders cite pricing? |
| `2_1_6_cancellation_by_payment.png` | Does preferred payment method correlate with cancellation? |
| `2_2_1_safety_cancellations_by_zone.png` | Which zones have the highest safety-cancellation rate? |
| `2_2_2_lowest_rated_zones.png` | Which zones have the lowest driver ratings? |
| `2_2_3_safety_concern_by_zone.png` | Which zones have the highest safety-concern rate? |
| `2_3_1_vehicle_safety_distribution.png` | How are vehicle safety ratings distributed? |
| `2_3_2_low_rated_vehicle_zones.png` | Which zones have the most low-rated vehicles? |
| `2_3_3_cancellation_vs_safety_rating.png` | Do low-rated vehicles get cancelled more? |
| `2_3_4_avg_vehicle_age_by_zone.png` | What is the average vehicle age per zone? |
| `2_3_5a_rider_cancel_vs_adult_safety.png` | Are cancellations sensitive to adult safety ratings? |
| `2_3_5b_rider_cancel_vs_child_safety.png` | Are cancellations sensitive to child safety ratings? |
| `2_4_1_rating_vs_safety.png` | Does vehicle safety relate to driver ratings? |
| `2_4_2_rating_vs_vehicle_age.png` | Does vehicle age relate to driver ratings? |
| `2_4_4_ratings_by_make.png` | How do ratings compare across car makes? |
| `2_4_5_rates_vs_vehicle_age.png` | Do cancellations vary with vehicle age? |
| `2_4_6_rating_by_category.png` | Does vehicle category influence ratings? |
| `2_5_1_rates_by_rating_tier.png` | Do lower-rated drivers cancel more? |
| `2_5_2_rates_vs_experience.png` | Does experience affect cancellations? |
| `2_5_3_rating_vs_experience.png` | Does more experience mean higher ratings? |
| `2_5_4_rates_by_platform.png` | Do outcome rates differ across platforms? |

---

## Troubleshooting

### `FileNotFoundError: 'data' not found`

`visualize.py` expects a folder called `data` in the project root, containing
the CSV files. Create it and copy your CSVs in:

```bat
mkdir data
copy path\to\your\csvs\*.csv data\
```

### `error: metadata-generation-failed` / `Could not find … vswhere.exe`

`pip` is trying to compile pandas (or another package) from source because no
prebuilt wheel exists for your Python version. This project requires
**Python 3.11 or 3.12** for reliable wheel coverage.

If you must stay on a newer Python, install with wheels only:

```bat
pip install --only-binary=:all: -r requirements.txt
```

If that fails, the fix is to use a supported Python version.

### `UserWarning: set_ticklabels() should only be used with a fixed number of ticks`

Harmless — the charts are still generated correctly. This warning appears when
matplotlib relabels an axis before its tick positions are fixed. To silence it,
see the comment on `_wrap_ticks` in `visualize.py`.

### Some charts are missing

If a CSV is missing or a query returned zero rows, `visualize.py` skips that
chart silently. Check the loader output — it prints how many files it loaded.
If you expected 24 charts and only see 22, two CSVs are missing or empty.

### Charts show `NaN` or blank bars

The CSV probably contains empty cells in a numeric column, which pandas reads
as `NaN`. Open the file in a text editor and confirm every row has the
expected number of fields.

---

## Customising Charts

### Rename an axis label

All axis titles come from a single dictionary called `LABELS` at the top of
`visualize.py`. To change "City zone" to "Zone", edit one line:

```python
LABELS = {
    ...
    "zone_name": "Zone",         # was: "City zone"
    ...
}
```

Every chart that uses `zone_name` on an axis picks up the change on the next
run.

### Change colours

Edit the seaborn theme at the top of `visualize.py`:

```python
sns.set_theme(style="whitegrid", palette="muted")
```

Try palettes like `"deep"`, `"muted"`, `"pastel"`, `"bright"`, `"dark"`, or
`"colorblind"`.

### Add a new chart

Write a function that takes a DataFrame and calls `_save`:

```python
def chart_my_new_query(df):
    df = _safe(df, "col_a", "col_b")
    if df.empty: return
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=df, x="col_a", y="col_b", ax=ax)
    ax.set_title("My new chart", pad=12)
    ax.set_xlabel(LABELS["col_a"])
    ax.set_ylabel(LABELS["col_b"])
    _save(fig, "my_new_query")
```

Then register it in the `DISPATCH` table near the bottom of the file:

```python
DISPATCH = [
    ...
    ("2.6.1", chart_my_new_query),
]
```

The prefix `"2.6.1"` must match the beginning of the CSV filename in
`./data/` — for example, a file called `2_6_1_My_new_query.csv`.

---

## License

Internal research project — not licensed for redistribution.