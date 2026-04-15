from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


CONTROL = "Control"
EXO_EMG = "Exo+EMG"
CONDITIONS = (CONTROL, EXO_EMG)

LEFT_HAND = "Left hand"
RIGHT_HAND = "Right hand"

CONDITION_COLORS = {
    CONTROL: "#C55A11",
    EXO_EMG: "#7B1FA2",
}

HAND_COLORS = {
    LEFT_HAND: "#00897B",
    RIGHT_HAND: "#D81B60",
}

FONT_FAMILY = "DejaVu Sans"
AXIS_GRID_COLOR = "#E6E6E6"
AXIS_SPINE_COLOR = "#CFCFCF"
TEXT_COLOR = "#222222"


@dataclass(frozen=True)
class PanelSpec:
    key: str
    row: int
    col: int
    title: str
    ylabel: str
    yticks: tuple[float, ...]
    ylim: tuple[float, float]
    hands: tuple[str, ...]
    note: str | None = None


def build_panel_specs() -> list[PanelSpec]:
    return [
        PanelSpec("bbt_blocks", 0, 0, "BBT", "Number of blocks", (0, 10, 20, 30, 40), (0, 42), (LEFT_HAND, RIGHT_HAND)),
        PanelSpec("bbt_drops", 0, 1, "BBT", "Drops", (0, 1, 2), (-0.3, 2.3), (LEFT_HAND, RIGHT_HAND)),
        PanelSpec("ball_time", 0, 2, "Ball", "Time (s)", (0, 5, 10, 15), (0, 18), (LEFT_HAND,)),
        PanelSpec("cylinder_time", 0, 3, "Cylinder", "Time (s)", (0, 5, 10, 15, 20), (0, 24), (LEFT_HAND,)),
        PanelSpec("cup_time", 0, 4, "Cup", "Time (s)", (0, 10, 20, 30), (0, 30), (LEFT_HAND,), note="One Exo+EMG trial: unable to open"),
        PanelSpec("bottle_score", 1, 0, "Water Bottle", "Score", (3, 4, 5), (2.5, 5.5), (RIGHT_HAND,)),
        PanelSpec("jar_score", 1, 1, "Jar Lids", "Score", (3, 4, 5), (2.5, 5.5), (RIGHT_HAND,)),
        PanelSpec("pegs_score", 1, 2, "Pegs", "Score", (3, 4, 5), (2.5, 5.5), (RIGHT_HAND,)),
        PanelSpec("bottle_time", 1, 3, "Water Bottle", "Time (s)", (0, 5, 10, 15), (0, 18), (RIGHT_HAND,)),
        PanelSpec("bottle_drops", 1, 4, "Water Bottle", "Drops", (0, 1, 2), (-0.3, 2.3), (RIGHT_HAND,)),
        PanelSpec("jar_time", 2, 0, "Jar Lids", "Time (s)", (0, 10, 20, 30, 40), (0, 44), (RIGHT_HAND,)),
        PanelSpec("jar_drops", 2, 1, "Jar Lids", "Drops", (0, 1, 2), (-0.3, 2.3), (RIGHT_HAND,)),
        PanelSpec("pegs_time", 2, 2, "Pegs", "Time (s)", (0, 10, 20, 30, 40), (0, 40), (RIGHT_HAND,)),
        PanelSpec("pegs_drops", 2, 3, "Pegs", "Drops", (0, 1, 2), (-0.3, 2.3), (RIGHT_HAND,)),
    ]


def build_panel_data() -> dict[str, dict[str, list[float]]]:
    return {
        "bbt_blocks": {
            CONTROL: {LEFT_HAND: [25, 27, 30], RIGHT_HAND: [32, 37.5, 36]},
            EXO_EMG: {LEFT_HAND: [5, 5, 5], RIGHT_HAND: [14, 16, 30]},
        },
        "bbt_drops": {
            CONTROL: {LEFT_HAND: [1, 1, 1], RIGHT_HAND: [0, 0, 0]},
            EXO_EMG: {LEFT_HAND: [0, 0, 0], RIGHT_HAND: [1, 0, 1]},
        },
        "ball_time": {
            CONTROL: {LEFT_HAND: [8.25, 14.49, 9.71]},
            EXO_EMG: {LEFT_HAND: [13, 11, 10]},
        },
        "cylinder_time": {
            CONTROL: {LEFT_HAND: [10.61, 9.52, 10.29]},
            EXO_EMG: {LEFT_HAND: [13, 12, 12]},
        },
        "cup_time": {
            CONTROL: {LEFT_HAND: [23.54, 15.67, 8.93]},
            EXO_EMG: {LEFT_HAND: [15, 25, 11]},
        },
        "bottle_score": {
            CONTROL: {RIGHT_HAND: [4, 4, 4]},
            EXO_EMG: {RIGHT_HAND: [4, 5, 4]},
        },
        "jar_score": {
            CONTROL: {RIGHT_HAND: [5, 5, 5]},
            EXO_EMG: {RIGHT_HAND: [4, 5, 4]},
        },
        "pegs_score": {
            CONTROL: {RIGHT_HAND: [5, 5, 5]},
            EXO_EMG: {RIGHT_HAND: [4, 5, 5]},
        },
        "bottle_time": {
            CONTROL: {RIGHT_HAND: [10, 8.71, 10.3]},
            EXO_EMG: {RIGHT_HAND: [14.89, 8.92, 9.83]},
        },
        "bottle_drops": {
            CONTROL: {RIGHT_HAND: [0, 0, 0]},
            EXO_EMG: {RIGHT_HAND: [0, 0, 0]},
        },
        "jar_time": {
            CONTROL: {RIGHT_HAND: [18.64, 14.45, 13.12]},
            EXO_EMG: {RIGHT_HAND: [25.43, 21.03, 21.06]},
        },
        "jar_drops": {
            CONTROL: {RIGHT_HAND: [0, 0, 0]},
            EXO_EMG: {RIGHT_HAND: [0, 0, 1]},
        },
        "pegs_time": {
            CONTROL: {RIGHT_HAND: [16.69, 15.7, 16.13]},
            EXO_EMG: {RIGHT_HAND: [36.84, 30.14, 27.89]},
        },
        "pegs_drops": {
            CONTROL: {RIGHT_HAND: [0, 0, 0]},
            EXO_EMG: {RIGHT_HAND: [0, 0, 1]},
        },
    }


def clean_values(values: list[float]) -> list[float]:
    array = np.asarray(values, dtype=float)
    return array[~np.isnan(array)].tolist()


def hand_offsets(hands: tuple[str, ...]) -> dict[str, float]:
    if len(hands) == 1:
        return {hands[0]: 0.0}
    offsets = np.linspace(-0.18, 0.18, len(hands))
    return dict(zip(hands, offsets, strict=True))


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


def style_axis(ax: plt.Axes, spec: PanelSpec) -> None:
    ax.set_xlim(0.45, 2.55)
    ax.set_ylim(*spec.ylim)
    ax.set_yticks(spec.yticks)
    ax.set_ylabel(spec.ylabel, fontsize=9)
    ax.set_xticks([1, 2], [CONTROL, EXO_EMG])
    ax.tick_params(axis="both", labelsize=8, direction="out", length=3)
    ax.grid(axis="y", color=AXIS_GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS_SPINE_COLOR)
    ax.spines["bottom"].set_color(AXIS_SPINE_COLOR)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    for tick, label in zip(ax.get_xticklabels(), CONDITIONS, strict=True):
        tick.set_color(CONDITION_COLORS[label])
        tick.set_fontweight("bold")
        tick.set_fontsize(8)


def draw_condition_bars(ax: plt.Axes, spec: PanelSpec, panel_data: dict[str, dict[str, list[float]]]) -> None:
    offsets = hand_offsets(spec.hands)
    bar_width = 0.28 if len(spec.hands) > 1 else 0.36
    condition_means: dict[str, list[float]] = {CONTROL: [], EXO_EMG: []}

    for hand in spec.hands:
        hand_color = HAND_COLORS[hand]
        for center, condition in zip((1, 2), CONDITIONS, strict=True):
            values = clean_values(panel_data[condition].get(hand, []))
            if not values:
                continue

            position = center + offsets[hand]
            mean_value = float(np.mean(values))
            std_value = float(np.std(values, ddof=0))

            ax.bar(
                position,
                mean_value,
                width=bar_width,
                color=hand_color,
                edgecolor=hand_color,
                alpha=0.84,
                linewidth=0.9,
                zorder=3,
            )
            ax.errorbar(position, mean_value, yerr=std_value, fmt="none", ecolor="#4D4D4D", elinewidth=0.8, capsize=2.3, zorder=4)

            jitter = np.linspace(-0.06, 0.06, len(values))
            ax.scatter(
                np.full(len(values), position) + jitter,
                values,
                s=16,
                facecolors="white",
                edgecolors=hand_color,
                linewidths=0.8,
                zorder=5,
            )
            condition_means[condition].append(mean_value)

    for center, condition in zip((1, 2), CONDITIONS, strict=True):
        if not condition_means[condition]:
            continue
        line_value = float(np.mean(condition_means[condition]))
        ax.plot(
            [center - 0.34, center + 0.34],
            [line_value, line_value],
            color=CONDITION_COLORS[condition],
            linewidth=2.1,
            solid_capstyle="round",
            zorder=2,
        )


def annotate_panel(ax: plt.Axes, spec: PanelSpec) -> None:
    ax.set_title(spec.title, fontsize=10, fontweight="bold", color="#141414", pad=12)
    if len(spec.hands) == 1:
        ax.text(
            0.98,
            0.98,
            spec.hands[0],
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7.2,
            color="#666666",
        )
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


def draw_legend(ax: plt.Axes) -> None:
    ax.axis("off")
    handles = [
        Patch(facecolor=HAND_COLORS[LEFT_HAND], edgecolor=HAND_COLORS[LEFT_HAND], alpha=0.84, label=LEFT_HAND),
        Patch(facecolor=HAND_COLORS[RIGHT_HAND], edgecolor=HAND_COLORS[RIGHT_HAND], alpha=0.84, label=RIGHT_HAND),
        Line2D([0], [0], color=CONDITION_COLORS[CONTROL], linewidth=2.1, label="Control mean"),
        Line2D([0], [0], color=CONDITION_COLORS[EXO_EMG], linewidth=2.1, label="Exo+EMG mean"),
        Line2D([0], [0], marker="o", linestyle="None", markerfacecolor="white", markeredgecolor="#444444", markersize=5.5, label="Trial value"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8, handlelength=1.8, borderaxespad=0.0, labelspacing=0.8)
    ax.text(0.0, 0.56, "Left hand\nNLI C4 AIS-D", transform=ax.transAxes, ha="left", va="top", fontsize=9, fontweight="bold", color=TEXT_COLOR)
    ax.text(0.0, 0.34, "Right hand\nNLI C7 AIS-D", transform=ax.transAxes, ha="left", va="top", fontsize=9, fontweight="bold", color=TEXT_COLOR)


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
        "Exo+BTN values removed from all panels.\nCup: one Exo+EMG trial was noted as\n'unable to open' in the source table.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color="#666666",
        fontstyle="italic",
    )


def create_figure() -> plt.Figure:
    apply_theme()

    panel_specs = build_panel_specs()
    panel_data = build_panel_data()

    fig = plt.figure(figsize=(15.8, 9.2), facecolor="white")
    grid = GridSpec(
        3,
        6,
        figure=fig,
        width_ratios=[1, 1, 1, 1, 1, 1],
        wspace=0.68,
        hspace=0.62,
        left=0.055,
        right=0.97,
        top=0.91,
        bottom=0.07,
    )

    fig.suptitle("Clinical Results: Single Subject (Barplots)", fontsize=14.5, fontweight="bold", y=0.968)
    fig.text(0.055, 0.93, "Control vs Exo+EMG", fontsize=10.2, fontweight="bold", color=TEXT_COLOR)
    fig.text(0.055, 0.905, "BBT panels include both hands; remaining panels show hand-specific tasks.", fontsize=8.8, color="#555555")

    axes_map: dict[tuple[int, int], plt.Axes] = {}
    for spec in panel_specs:
        ax = fig.add_subplot(grid[spec.row, spec.col])
        style_axis(ax, spec)
        draw_condition_bars(ax, spec, panel_data[spec.key])
        annotate_panel(ax, spec)
        axes_map[(spec.row, spec.col)] = ax

    legend_ax = fig.add_subplot(grid[0, 5])
    draw_legend(legend_ax)

    note_ax = fig.add_subplot(grid[1, 5])
    draw_note_panel(note_ax)

    blank_ax = fig.add_subplot(grid[2, 5])
    blank_ax.axis("off")

    return fig


def main() -> None:
    fig = create_figure()
    output_dir = Path(__file__).resolve().parent
    stem = "single_subject_clinical_results_barplots"
    pdf_path = output_dir / f"{stem}.pdf"
    png_path = output_dir / f"{stem}.png"
    svg_path = output_dir / f"{stem}.svg"
    fig.savefig(pdf_path, dpi=600, bbox_inches="tight")
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    print(f"Saved: {pdf_path.name}, {png_path.name}, and {svg_path.name}")


if __name__ == "__main__":
    main()