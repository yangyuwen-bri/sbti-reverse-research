#!/usr/bin/env python3
"""
Generate visualization charts from reverse-analysis outputs.

Inputs:
- docs/data/type_distribution_full.csv
- docs/data/type_distribution_non_drunk.csv

Outputs:
- docs/figures/full_distribution.png
- docs/figures/non_drunk_distribution.png
- docs/figures/top10_full.png
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
FIG = DOCS / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def plot_bar(df, label_col, value_col, title, out_path, color="#4C78A8"):
    plt.figure(figsize=(14, 7))
    plt.bar(df[label_col], df[value_col], color=color)
    plt.xticks(rotation=60, ha="right")
    plt.ylabel("Percentage (%)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def main():
    full_csv = DATA / "type_distribution_full.csv"
    non_csv = DATA / "type_distribution_non_drunk.csv"

    if not full_csv.exists() or not non_csv.exists():
        raise FileNotFoundError("Please run scripts/analyze_sbti.py first.")

    full = pd.read_csv(full_csv)
    non = pd.read_csv(non_csv)

    # full distribution (includes DRUNK / HHHH)
    plot_bar(
        full,
        label_col="type",
        value_col="percentage",
        title="SBTI Full Theoretical Distribution (All Branches)",
        out_path=FIG / "full_distribution.png",
        color="#4C78A8",
    )

    # top 10 full
    top10 = full.nlargest(10, "percentage").copy()
    plot_bar(
        top10,
        label_col="type",
        value_col="percentage",
        title="Top 10 Types by Theoretical Share (Full)",
        out_path=FIG / "top10_full.png",
        color="#F58518",
    )

    # non-drunk normalized
    non = non.sort_values("percentage_non_drunk", ascending=False)
    plot_bar(
        non,
        label_col="type",
        value_col="percentage_non_drunk",
        title="SBTI Distribution Excluding DRUNK (Renormalized)",
        out_path=FIG / "non_drunk_distribution.png",
        color="#54A24B",
    )

    print("Generated charts:")
    print(f"- {FIG / 'full_distribution.png'}")
    print(f"- {FIG / 'top10_full.png'}")
    print(f"- {FIG / 'non_drunk_distribution.png'}")


if __name__ == "__main__":
    main()
