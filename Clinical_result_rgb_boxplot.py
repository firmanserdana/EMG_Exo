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


FONT_FAMILY = "DejaVu Sans"
AXIS_GRID_COLOR = "#E6E6E6"
AXIS_SPINE_COLOR = "#CFCFCF"
TEXT_COLOR = "#222222"
YELLOW_DOT_EDGE_COLOR = "#8A7800"


def rgb_to_unit(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in rgb)


def build_column_colors() -> dict[str, tuple[float, float, float]]:
    colors: dict[str, tuple[float, float, float]] = {}
    for rgb, columns in RGB_GROUPS:
        color = rgb_to_unit(rgb)
        for column_index in columns:
            colors[f"Col {column_index}"] = color
    return colors


def split_odd_even_columns(labels: list[str]) -> tuple[list[str], list[str]]:
    odd = [label for label in labels if int(label.split()[1]) % 2 == 1]
    even = [label for label in labels if int(label.split()[1]) % 2 == 0]
    return odd, even


def apply_theme() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [FONT_FAMILY, "Arial", "Helvetica"],
            "axes.linewidth": 0.8,
            "axes.labelcolor": TEXT_COLOR,
            "xtick.color": "#555555",
            "ytick.color": "#555555",
            "axes.titlecolor": TEXT_COLOR,
        }
    )


def style_axis(ax: plt.Axes, ymin: float, ymax: float) -> None:
    ax.set_ylim(ymin, ymax)
    ax.grid(axis="y", color=AXIS_GRID_COLOR, linewidth=0.8)
    ax.axhline(0.0, color="#A8A8A8", linewidth=0.9)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS_SPINE_COLOR)
    ax.spines["bottom"].set_color(AXIS_SPINE_COLOR)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(axis="both", labelsize=8, length=0)


def values_for_label(label: str, positive_only: bool) -> np.ndarray:
    values = np.asarray(DATA_BY_COLUMN[label], dtype=float)
    if positive_only:
        values = np.abs(values)
    return values


def dot_edge_color(label: str, default_color: tuple[float, float, float]) -> tuple[float, float, float] | str:
    column_index = int(label.split()[1])
    if column_index >= 9:
        return YELLOW_DOT_EDGE_COLOR
    return default_color


def draw_bars(
    ax: plt.Axes,
    labels: list[str],
    colors: dict[str, tuple[float, float, float]],
    positive_only: bool,
) -> None:
    positions = np.arange(1, len(labels) + 1, dtype=float)
    means = np.array([float(np.mean(values_for_label(label, positive_only))) for label in labels], dtype=float)
    stds = np.array([float(np.std(values_for_label(label, positive_only), ddof=0)) for label in labels], dtype=float)

    ax.bar(
        positions,
        means,
        width=0.68,
        color=[colors[label] for label in labels],
        edgecolor=[colors[label] for label in labels],
        linewidth=0.8,
        alpha=0.9,
        zorder=2,
    )
    ax.errorbar(positions, means, yerr=stds, fmt="none", ecolor="#4D4D4D", elinewidth=0.8, capsize=2.5, zorder=3)

    for position, label in zip(positions, labels, strict=True):
        values = values_for_label(label, positive_only)
        jitter = np.linspace(-0.12, 0.12, num=len(values))
        ax.scatter(
            np.full_like(values, position) + jitter,
            values,
            s=18,
            facecolors="white",
            edgecolors=dot_edge_color(label, colors[label]),
            linewidths=0.8,
            zorder=4,
        )

    ax.set_xlim(0.35, len(labels) + 0.65)
    ax.set_xticks([])
    ax.tick_params(axis="x", which="both", bottom=False, top=False, labelbottom=False)


def compute_ylims(labels: list[str], positive_only: bool) -> tuple[float, float]:
    all_values = np.asarray(
        [value for label in labels for value in values_for_label(label, positive_only)],
        dtype=float,
    )
    if positive_only:
        ymin = 0.0
    else:
        ymin = float(np.floor(all_values.min() - 1.0))
    ymax = float(np.ceil(all_values.max() + 1.0))
    return ymin, ymax


def create_panel_figure(
    labels: list[str],
    positive_only: bool,
) -> plt.Figure:
    apply_theme()

    colors = build_column_colors()
    y_min, y_max = compute_ylims(labels, positive_only)

    fig, ax = plt.subplots(figsize=(11.6, 4.0), facecolor="white")

    style_axis(ax, y_min, y_max)
    draw_bars(ax, labels, colors, positive_only)

    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.16, top=0.96)
    return fig


def main() -> None:
    labels = list(DATA_BY_COLUMN.keys())
    odd_labels, even_labels = split_odd_even_columns(labels)

    blocks_fig = create_panel_figure(
        labels=odd_labels,
        positive_only=False,
    )
    drops_fig = create_panel_figure(
        labels=even_labels,
        positive_only=True,
    )

    output_dir = Path(__file__).resolve().parent

    blocks_stem = "clinical_result_rgb_blocks_moved_barplot"
    blocks_png = output_dir / f"{blocks_stem}.png"
    blocks_pdf = output_dir / f"{blocks_stem}.pdf"
    blocks_svg = output_dir / f"{blocks_stem}.svg"
    blocks_fig.savefig(blocks_png, dpi=600, bbox_inches="tight")
    blocks_fig.savefig(blocks_pdf, dpi=600, bbox_inches="tight")
    blocks_fig.savefig(blocks_svg, bbox_inches="tight")

    drops_stem = "clinical_result_rgb_drops_barplot"
    drops_png = output_dir / f"{drops_stem}.png"
    drops_pdf = output_dir / f"{drops_stem}.pdf"
    drops_svg = output_dir / f"{drops_stem}.svg"
    drops_fig.savefig(drops_png, dpi=600, bbox_inches="tight")
    drops_fig.savefig(drops_pdf, dpi=600, bbox_inches="tight")
    drops_fig.savefig(drops_svg, bbox_inches="tight")

    print(
        "Saved: "
        f"{blocks_png.name}, {blocks_pdf.name}, {blocks_svg.name}, "
        f"{drops_png.name}, {drops_pdf.name}, and {drops_svg.name}"
    )


if __name__ == "__main__":
    main()