#!/usr/bin/env python3
"""Create summary tables and figures for SCI transfer results.

Inputs expected from scripts/evaluate_transfer_sci_s3_s4.py.

Usage:
  python scripts/summarize_transfer_results.py \
      --results-csv results-analysis/transfer_sci_s3_s4.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def write_markdown_summary(df: pd.DataFrame, output_md: Path) -> None:
    lines = []
    lines.append("# SCI Transfer Summary (S3/S4)")
    lines.append("")
    lines.append("## Aggregate Metrics")
    lines.append("")

    agg = (
        df.groupby("model_type")[["before_accuracy", "after_accuracy", "delta_accuracy", "before_balanced_accuracy", "after_balanced_accuracy", "delta_balanced_accuracy"]]
        .mean()
        .reset_index()
    )
    lines.append(agg.to_markdown(index=False))
    lines.append("")

    lines.append("## Per Subject and Model")
    lines.append("")
    cols = [
        "subject",
        "model_type",
        "before_accuracy",
        "after_accuracy",
        "delta_accuracy",
        "before_balanced_accuracy",
        "after_balanced_accuracy",
        "delta_balanced_accuracy",
        "after_variant",
        "n_test",
    ]
    lines.append(df[cols].to_markdown(index=False))
    lines.append("")

    output_md.write_text("\n".join(lines), encoding="utf-8")


def make_plots(df: pd.DataFrame, output_dir: Path) -> None:
    sns.set_theme(style="whitegrid")

    plot_df = df.melt(
        id_vars=["subject", "model_type"],
        value_vars=["before_accuracy", "after_accuracy"],
        var_name="stage",
        value_name="accuracy",
    )

    plt.figure(figsize=(9, 5))
    sns.barplot(data=plot_df, x="subject", y="accuracy", hue="stage", ci=None)
    plt.ylim(0, 1)
    plt.title("SCI S3/S4 Accuracy Before vs After Transfer")
    plt.tight_layout()
    plt.savefig(output_dir / "accuracy_before_after.png", dpi=160)
    plt.close()

    plt.figure(figsize=(9, 5))
    sns.barplot(data=df, x="subject", y="delta_balanced_accuracy", hue="model_type", ci=None)
    plt.axhline(0, color="black", linewidth=1)
    plt.title("Balanced Accuracy Gain After Transfer")
    plt.tight_layout()
    plt.savefig(output_dir / "delta_balanced_accuracy.png", dpi=160)
    plt.close()

    heat = (
        df.pivot_table(index="subject", columns="model_type", values="after_accuracy", aggfunc="mean")
        .sort_index()
    )
    plt.figure(figsize=(8, 4))
    sns.heatmap(heat, annot=True, fmt=".3f", cmap="YlGnBu", vmin=0, vmax=1)
    plt.title("Post-Transfer Accuracy Heatmap")
    plt.tight_layout()
    plt.savefig(output_dir / "post_transfer_accuracy_heatmap.png", dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize SCI transfer evaluation outputs")
    parser.add_argument("--results-csv", type=str, default="results-analysis/transfer_sci_s3_s4.csv")
    parser.add_argument("--output-dir", type=str, default="results-analysis/transfer_summary")
    args = parser.parse_args()

    results_csv = Path(args.results_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not results_csv.exists():
        raise SystemExit(f"Results file not found: {results_csv}")

    df = pd.read_csv(results_csv)
    if df.empty:
        raise SystemExit("Results CSV is empty. Run evaluation first.")

    summary_csv = output_dir / "transfer_summary_table.csv"
    summary_md = output_dir / "transfer_summary.md"

    df.to_csv(summary_csv, index=False)
    write_markdown_summary(df, summary_md)
    make_plots(df, output_dir)

    print(f"Saved table: {summary_csv}")
    print(f"Saved report: {summary_md}")
    print(f"Saved figures in: {output_dir}")


if __name__ == "__main__":
    main()
