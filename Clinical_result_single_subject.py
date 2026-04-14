from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


CONTROL = "Control"
EXO_BTN = "Exo+BTN"
EXO_EMG = "Exo+EMG"
CONDITIONS = (CONTROL, EXO_BTN, EXO_EMG)

CONDITION_COLORS = {
    CONTROL: "#C55A11",
    EXO_BTN: "#2F6690",
    EXO_EMG: "#7B1FA2",
}


@dataclass(frozen=True)
class PanelSpec:
    key: str
    row: int
    col: int
    title: str
    ylabel: str
    yticks: tuple[float, ...]
    ylim: tuple[float, float]
    note: str | None = None


def build_panel_specs() -> list[PanelSpec]:
    return [
        PanelSpec("left_bbt_blocks", 0, 0, "BBT", "Number of blocks", (0, 10, 20, 30), (0, 36)),
        PanelSpec("left_bbt_drops", 0, 1, "BBT", "Drops", (0, 1, 2), (-0.3, 2.3)),
        PanelSpec("left_ball_time", 0, 2, "Ball", "Time (s)", (0, 5, 10, 15), (0, 18)),
        PanelSpec("left_cylinder_time", 0, 3, "Cylinder", "Time (s)", (0, 5, 10, 15, 20), (0, 24)),
        PanelSpec("left_cup_time", 0, 4, "Cup", "Time (s)", (0, 10, 20, 30), (0, 30), note="one Exo+EMG trial: unable to open"),
        PanelSpec("right_bbt_blocks", 1, 0, "BBT", "Number of blocks", (0, 10, 20, 30, 40), (0, 42)),
        PanelSpec("right_bbt_drops", 1, 1, "BBT", "Drops", (0, 1, 2), (-0.3, 2.3)),
        PanelSpec("right_bottle_score", 1, 2, "Water Bottle", "Score", (3, 4, 5), (2.5, 5.5)),
        PanelSpec("right_jar_score", 1, 3, "Jar Lids", "Score", (3, 4, 5), (2.5, 5.5)),
        PanelSpec("right_pegs_score", 1, 4, "Pegs", "Score", (3, 4, 5), (2.5, 5.5)),
        PanelSpec("right_bottle_time", 2, 0, "Water Bottle", "Time (s)", (0, 5, 10, 15), (0, 18)),
        PanelSpec("right_bottle_drops", 2, 1, "Water Bottle", "Drops", (0, 1, 2), (-0.3, 2.3)),
        PanelSpec("right_jar_time", 2, 2, "Jar Lids", "Time (s)", (0, 10, 20, 30, 40), (0, 44)),
        PanelSpec("right_jar_drops", 2, 3, "Jar Lids", "Drops", (0, 1, 2), (-0.3, 2.3)),
        PanelSpec("right_pegs_time", 2, 4, "Pegs", "Time (s)", (0, 10, 20, 30, 40), (0, 40)),
        PanelSpec("right_pegs_drops", 2, 5, "Pegs", "Drops", (0, 1, 2), (-0.3, 2.3)),
    ]


def build_panel_data() -> dict[str, dict[str, list[float]]]:
    return {
        "left_bbt_blocks": {
            CONTROL: [25, 27, 30],
            EXO_BTN: [14, 14, 13],
            EXO_EMG: [5, 5, 5],
        },
        "left_bbt_drops": {
            CONTROL: [1, 1, 1],
            EXO_BTN: [0, 0, 0],
            EXO_EMG: [0, 0, 0],
        },
        "left_ball_time": {
            CONTROL: [8.25, 14.49, 9.71],
            EXO_BTN: [8.34, 10.62, 11.79],
            EXO_EMG: [13, 11, 10],
        },
        "left_cylinder_time": {
            CONTROL: [10.61, 9.52, 10.29],
            EXO_BTN: [15.31, 19.64, 15.19],
            EXO_EMG: [13, 12, 12],
        },
        "left_cup_time": {
            CONTROL: [23.54, 15.67, 8.93],
            EXO_BTN: [19.75, 16.48, 14.89],
            EXO_EMG: [15, 25, 11],
        },
        "right_bbt_blocks": {
            CONTROL: [32, 37.5, 36],
            EXO_BTN: [22, 27, 20],
            EXO_EMG: [14, 16, 30],
        },
        "right_bbt_drops": {
            CONTROL: [0, 0, 0],
            EXO_BTN: [0, 0, 1],
            EXO_EMG: [1, 0, 1],
        },
        "right_bottle_score": {
            CONTROL: [4, 4, 4],
            EXO_BTN: [5, 5, 5],
            EXO_EMG: [4, 5, 4],
        },
        "right_jar_score": {
            CONTROL: [5, 5, 5],
            EXO_BTN: [4, 4, 5],
            EXO_EMG: [4, 5, 4],
        },
        "right_pegs_score": {
            CONTROL: [5, 5, 5],
            EXO_BTN: [5, 5, 5],
            EXO_EMG: [4, 5, 5],
        },
        "right_bottle_time": {
            CONTROL: [10, 8.71, 10.3],
            EXO_BTN: [12.99, 11.92, 7.55],
            EXO_EMG: [14.89, 8.92, 9.83],
        },
        "right_bottle_drops": {
            CONTROL: [0, 0, 0],
            EXO_BTN: [0, 0, 0],
            EXO_EMG: [0, 0, 0],
        },
        "right_jar_time": {
            CONTROL: [18.64, 14.45, 13.12],
            EXO_BTN: [39.6, 26.92, 19.34],
            EXO_EMG: [25.43, 21.03, 21.06],
        },
        "right_jar_drops": {
            CONTROL: [0, 0, 0],
            EXO_BTN: [0, 0, 0],
            EXO_EMG: [0, 0, 1],
        },
        "right_pegs_time": {
            CONTROL: [16.69, 15.7, 16.13],
            EXO_BTN: [30.2, 30.55, 28.29],
            EXO_EMG: [36.84, 30.14, 27.89],
        },
        "right_pegs_drops": {
            CONTROL: [0, 0, 0],
            EXO_BTN: [0, 1, 0],
            EXO_EMG: [0, 0, 1],
        },
    }


def style_axis(ax: plt.Axes, spec: PanelSpec) -> None:
    ax.set_xlim(0.45, 3.55)
    ax.set_ylim(*spec.ylim)
    ax.set_yticks(spec.yticks)
    ax.set_ylabel(spec.ylabel, fontsize=9)
    ax.set_xticks([1, 2, 3], [CONTROL, EXO_BTN, EXO_EMG])
    ax.tick_params(axis="both", labelsize=8, direction="out", length=3)
    ax.grid(axis="y", color="#E6E6E6", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    for tick, label in zip(ax.get_xticklabels(), CONDITIONS):
        tick.set_color(CONDITION_COLORS[label])
        tick.set_fontweight("bold")
        tick.set_fontsize(7.5)


def draw_condition_boxplots(ax: plt.Axes, panel_data: dict[str, list[float]]) -> None:
    for position, condition in enumerate(CONDITIONS, start=1):
        values = np.asarray(panel_data[condition], dtype=float)
        box = ax.boxplot(
            [values],
            positions=[position],
            widths=0.34,
            patch_artist=True,
            manage_ticks=False,
            showfliers=False,
            whis=(0, 100),
            medianprops={"color": "#1F1F1F", "linewidth": 1.2},
            boxprops={"facecolor": CONDITION_COLORS[condition], "edgecolor": CONDITION_COLORS[condition], "linewidth": 1.5, "alpha": 0.72},
            whiskerprops={"color": CONDITION_COLORS[condition], "linewidth": 1.2},
            capprops={"color": CONDITION_COLORS[condition], "linewidth": 1.2},
        )
        for patch in box["boxes"]:
            patch.set_zorder(3)

        mean_value = float(np.mean(values))
        ax.scatter(position, mean_value, s=26, color="white", edgecolors=CONDITION_COLORS[condition], linewidths=0.9, zorder=4)


def annotate_panel(ax: plt.Axes, spec: PanelSpec) -> None:
    ax.set_title(spec.title, fontsize=10, fontweight="bold", color="#141414", pad=12)
    if spec.note:
        ax.text(
            0.5,
            1.02,
            spec.note,
            transform=ax.transAxes,
            ha="center",
            va="bottom",
            fontsize=7,
            color="#666666",
            fontstyle="italic",
        )


def add_group_borders(fig: plt.Figure, axes_map: dict[tuple[int, int], plt.Axes]) -> None:
    groups = [
        [(0, 0), (0, 1)],
        [(0, 2)],
        [(0, 3)],
        [(0, 4)],
        [(1, 0), (1, 1)],
        [(1, 2), (2, 0), (2, 1)],
        [(1, 3), (2, 2), (2, 3)],
        [(1, 4), (2, 4), (2, 5)],
    ]

    for group in groups:
        boxes = [axes_map[key].get_position() for key in group]
        x0 = min(box.x0 for box in boxes) - 0.008
        y0 = min(box.y0 for box in boxes) - 0.012
        x1 = max(box.x1 for box in boxes) + 0.008
        y1 = max(box.y1 for box in boxes) + 0.028
        fig.add_artist(
            Rectangle(
                (x0, y0),
                x1 - x0,
                y1 - y0,
                transform=fig.transFigure,
                fill=False,
                linewidth=0.8,
                edgecolor="#C7C7C7",
                zorder=0,
            )
        )


def draw_legend(ax: plt.Axes) -> None:
    ax.axis("off")
    handles = [Patch(facecolor=CONDITION_COLORS[condition], edgecolor=CONDITION_COLORS[condition], alpha=0.72, label=condition) for condition in CONDITIONS]
    handles.append(Line2D([0], [0], marker="o", linestyle="None", markerfacecolor="white", markeredgecolor="#444444", markersize=6, label="Trial mean"))
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8, handlelength=1.8, borderaxespad=0.0, labelspacing=0.8)
    ax.text(0.0, 0.56, "Left hand\nNLI C4 AIS-D", transform=ax.transAxes, ha="left", va="top", fontsize=9, fontweight="bold", color="#222222")
    ax.text(0.0, 0.33, "Right hand\nNLI C7 AIS-D", transform=ax.transAxes, ha="left", va="top", fontsize=9, fontweight="bold", color="#222222")


def draw_note_panel(ax: plt.Axes) -> None:
    ax.axis("off")
    ax.text(
        0.0,
        0.9,
        "Single-subject clinical dataset\nwith 3 repeated trials per condition.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color="#444444",
    )
    ax.text(
        0.0,
        0.55,
        "Cup: one Exo+EMG trial was noted as\n'unable to open' in the source table.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color="#666666",
        fontstyle="italic",
    )


def create_figure() -> plt.Figure:
    panel_specs = build_panel_specs()
    panel_data = build_panel_data()

    fig = plt.figure(figsize=(16.0, 10.2), facecolor="white")
    grid = GridSpec(
        3,
        6,
        figure=fig,
        width_ratios=[1, 1, 1, 1, 1, 1],
        wspace=0.65,
        hspace=0.72,
        left=0.055,
        right=0.97,
        top=0.93,
        bottom=0.07,
    )

    fig.suptitle("Clinical Results: Single Subject", fontsize=15, fontweight="bold", y=0.972)
    fig.text(0.055, 0.94, "Left Hand | NLI C4 AIS-D", fontsize=10.5, fontweight="bold", color="#1F1F1F")
    fig.text(0.055, 0.62, "Right Hand | NLI C7 AIS-D", fontsize=10.5, fontweight="bold", color="#1F1F1F")

    axes_map: dict[tuple[int, int], plt.Axes] = {}
    for spec in panel_specs:
        ax = fig.add_subplot(grid[spec.row, spec.col])
        style_axis(ax, spec)
        draw_condition_boxplots(ax, panel_data[spec.key])
        annotate_panel(ax, spec)
        axes_map[(spec.row, spec.col)] = ax

    legend_ax = fig.add_subplot(grid[0, 5])
    draw_legend(legend_ax)

    note_ax = fig.add_subplot(grid[1, 5])
    draw_note_panel(note_ax)

    blank_ax = fig.add_subplot(grid[2, 5])
    blank_ax.axis("off")

    add_group_borders(fig, axes_map)
    return fig


def main() -> None:
    fig = create_figure()
    output_dir = Path(__file__).resolve().parent
    stem = "single_subject_clinical_results"
    pdf_path = output_dir / f"{stem}.pdf"
    png_path = output_dir / f"{stem}.png"
    svg_path = output_dir / f"{stem}.svg"
    fig.savefig(pdf_path, dpi=600, bbox_inches="tight")
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    print(f"Saved: {pdf_path.name}, {png_path.name}, and {svg_path.name}")


if __name__ == "__main__":
    main()