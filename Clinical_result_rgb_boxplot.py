from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


DATA_BY_COLUMN: dict[str, list[float]] = {
    "Col 1": [8, 5, 7, 9, 9],
    "Col 2": [0, -5, 0, 0, 0],
    "Col 3": [4, 0, 5, 8, 4],
    "Col 4": [-2, -8, -4, -1, -6],
    "Col 5": [7, 5, 5, 5, 4],
    "Col 6": [-1, -4, -4, -3, 0],
    "Col 7": [7, 8, 9, 8, 7],
    "Col 8": [-1, -1, 0, -1, -4],
    "Col 9": [7, 7, 9, 6, 7],
    "Col 10": [0, -1, -2, 0, -1],
    "Col 11": [8, 6, 8, 10, 8],
    "Col 12": [-2, -1, -2, 0, -1],
    "Col 13": [10, 8, 6, 6, 8],
    "Col 14": [0, -1, -2, -2, 0],
    "Col 15": [9, 10, 7, 6, 7],
    "Col 16": [-1, -1, -1, -1, -1],
    "Col 17": [10, 6, 6, 9, 8],
    "Col 18": [-1, -2, -2, -2, -2],
}


RGB_GROUPS: list[tuple[tuple[int, int, int], tuple[int, ...]]] = [
    ((45, 94, 127), (1, 2)),
    ((72, 155, 207), (3, 4)),
    ((146, 52, 142), (5, 6)),
    ((218, 120, 66), (7, 8)),
    ((255, 255, 84), tuple(range(9, 19))),
]


def rgb_to_unit(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in rgb)


def build_column_colors() -> dict[str, tuple[float, float, float]]:
    colors: dict[str, tuple[float, float, float]] = {}
    for rgb, columns in RGB_GROUPS:
        color = rgb_to_unit(rgb)
        for column_index in columns:
            colors[f"Col {column_index}"] = color
    return colors


def build_excel_like_stats(label: str, values: list[float]) -> dict[str, float | list[float] | str]:
    array = np.sort(np.asarray(values, dtype=float))
    q1 = float(np.percentile(array, 25, method="weibull"))
    q3 = float(np.percentile(array, 75, method="weibull"))
    median = float(np.median(array))
    mean = float(np.mean(array))
    return {
        "label": label,
        "whislo": float(array.min()),
        "q1": q1,
        "med": median,
        "q3": q3,
        "whishi": float(array.max()),
        "mean": mean,
        "fliers": [],
    }


def create_figure() -> plt.Figure:
    labels = list(DATA_BY_COLUMN.keys())
    colors = build_column_colors()
    positions = np.arange(1, len(labels) + 1, dtype=float)
    stats = [build_excel_like_stats(label, DATA_BY_COLUMN[label]) for label in labels]

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "axes.linewidth": 0.8,
            "xtick.color": "#5F6368",
            "ytick.color": "#5F6368",
        }
    )

    fig, ax = plt.subplots(figsize=(7.4, 5.2), facecolor="white")
    boxplot = ax.bxp(
        stats,
        positions=positions,
        widths=0.6,
        patch_artist=True,
        showmeans=True,
        meanprops={
            "marker": "x",
            "markerfacecolor": "none",
            "markeredgecolor": "#303030",
            "markeredgewidth": 0.8,
            "markersize": 5.5,
        },
        medianprops={"color": "#202020", "linewidth": 0.8},
        whiskerprops={"color": "#666666", "linewidth": 0.7},
        capprops={"color": "#666666", "linewidth": 0.7},
        flierprops={"marker": "", "markersize": 0},
        showfliers=False,
    )

    for box_index, (patch, label) in enumerate(zip(boxplot["boxes"], labels, strict=True)):
        color = colors[label]
        patch.set_facecolor(color)
        patch.set_edgecolor(color)
        patch.set_alpha(1.0)
        patch.set_linewidth(0.7)
        boxplot["medians"][box_index].set_color("#333333")
        boxplot["means"][box_index].set_markeredgecolor(color)
        boxplot["means"][box_index].set_color(color)

    ax.set_xlim(0, 18.5)
    ax.set_ylim(-10, 12)
    ax.set_yticks(np.arange(-10, 13, 2))
    ax.set_xticks([])
    ax.tick_params(axis="x", which="both", bottom=False, top=False, labelbottom=False)
    ax.tick_params(axis="y", which="both", length=0, colors="#6F6F6F", labelsize=8)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D0D0D0")
    ax.spines["bottom"].set_color("#D0D0D0")
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)

    ax.margins(x=0)
    fig.subplots_adjust(left=0.07, right=0.998, bottom=0.02, top=0.998)
    return fig


def main() -> None:
    fig = create_figure()
    output_dir = Path(__file__).resolve().parent
    stem = "clinical_result_rgb_boxplot"
    png_path = output_dir / f"{stem}.png"
    pdf_path = output_dir / f"{stem}.pdf"
    svg_path = output_dir / f"{stem}.svg"
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(pdf_path, dpi=600, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    print(f"Saved: {png_path.name}, {pdf_path.name}, and {svg_path.name}")


if __name__ == "__main__":
    main()