from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


NO_GLOVE = "No glove"
GLOVE = "Glove"
CONDITIONS = (NO_GLOVE, GLOVE)

CONDITION_COLORS = {
    NO_GLOVE: "#C55A11",
    GLOVE: "#2F6690",
}

SUBJECT_COLORS = {
    "S1": "#00897B",
    "S2": "#D81B60",
    "S3": "#5E35B1",
}

SUBJECT_LABELS = {
    "S1": "S1  C5 AIS-B",
    "S2": "S2  C4 AIS-D",
    "S3": "S3  C7 AIS-A",
}

WRIST_COLOR = "#B22222"


@dataclass(frozen=True)
class PanelSpec:
    task: str
    tag: str
    metric: str
    row: int
    col: int
    ylabel: str
    yticks: tuple[float, ...]
    ylim: tuple[float, float]
    subjects: tuple[str, ...]
    note: str | None = None
    note_xy: tuple[float, float] | None = None
    note_kwargs: dict | None = None


def build_panel_specs() -> list[PanelSpec]:
    return [
        PanelSpec("Task 1", "standard", "Number of blocks", 0, 0, "Number of blocks", (0, 10, 20, 30), (0, 36), ("S1", "S2", "S3")),
        PanelSpec("Task 1", "standard", "Drops", 0, 1, "Drops", (0, 1, 2, 3), (-0.3, 3.7), ("S1", "S2", "S3")),
        PanelSpec(
            "Task 2",
            "standard",
            "Time (s)",
            0,
            2,
            "Time (s)",
            (0, 10, 20, 30, 40),
            (0, 43),
            ("S1", "S2"),
        ),
        PanelSpec("Task 2", "standard", "Score", 0, 3, "Score", (0, 1, 2, 3, 4, 5), (-0.3, 5.7), ("S1", "S2")),
        PanelSpec("Task 3", "standard", "Time (s)", 0, 4, "Time (s)", (0, 20, 40, 60), (0, 70), ("S1", "S2")),
        PanelSpec("Task 3", "standard", "Score", 0, 5, "Score", (2, 3, 4, 5), (1.5, 5.6), ("S1", "S2")),
        PanelSpec("Task 4", "standard", "Time (s)", 1, 0, "Time (s)", (0, 30, 60, 90), (0, 110), ("S1", "S2")),
        PanelSpec("Task 4", "standard", "Score", 1, 1, "Score", (2, 3, 4, 5), (1.5, 5.6), ("S1", "S2")),
        PanelSpec("Task 5", "time only", "Time (s)", 1, 2, "Time (s)", (0, 5, 10, 15), (0, 18), ("S2", "S3")),
        PanelSpec("Task 6", "time only", "Time (s)", 1, 3, "Time (s)", (0, 5, 10, 15, 20), (0, 25), ("S2", "S3")),
        PanelSpec(
            "Task 7",
            "time only",
            "Time (s)",
            1,
            4,
            "Time (s)",
            (0, 10, 20),
            (0, 28),
            ("S2",),
            note="S3: unable",
            note_xy=(1.5, 2.6),
            note_kwargs={"color": "#777777", "fontstyle": "italic", "fontsize": 8},
        ),
    ]


def build_panel_data() -> dict[tuple[str, str], dict[str, dict[str, list[float]]]]:
    return {
        ("Task 1", "Number of blocks"): {
            NO_GLOVE: {"S1": [8, 13, 14], "S2": [25, 27, 30], "S3": [7, 4, 6]},
            GLOVE: {"S1": [10, 10, 11], "S2": [14, 14, 13], "S3": [10, 9, 12]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": True, "S3": False}, GLOVE: {"S1": False, "S2": False, "S3": False}},
        },
        ("Task 1", "Drops"): {
            NO_GLOVE: {"S1": [1, 1, 1], "S2": [1, 1, 1], "S3": [2, 0, 2]},
            GLOVE: {"S1": [0, 2, 0], "S2": [0, 0, 0], "S3": [0, 0, 0]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": True, "S3": False}, GLOVE: {"S1": False, "S2": False, "S3": False}},
        },
        ("Task 2", "Time (s)"): {
            NO_GLOVE: {"S1": [24.55, np.nan, np.nan], "S2": [14.42, 15.92, 11.33]},
            GLOVE: {"S1": [29.5, 17.0, 30.0], "S2": [17.0, 15.06, 34.46]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": False}, GLOVE: {"S1": False, "S2": False}},
        },
        ("Task 2", "Score"): {
            NO_GLOVE: {"S1": [0, 0, 0], "S2": [3, 3, 3]},
            GLOVE: {"S1": [1, 1, 1], "S2": [4, 4, 4]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": False}, GLOVE: {"S1": False, "S2": False}},
        },
        ("Task 3", "Time (s)"): {
            NO_GLOVE: {"S1": [31.04, 20.02, 16.88], "S2": [20.65, 22.86, 18.47]},
            GLOVE: {"S1": [56.61, 50.59, 43.96], "S2": [40.16, 36.57, 35.34]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": False}, GLOVE: {"S1": False, "S2": False}},
        },
        ("Task 3", "Score"): {
            NO_GLOVE: {"S1": [3, 3, 3], "S2": [4, 3, 3]},
            GLOVE: {"S1": [3, 3, 3], "S2": [4, 4, 4]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": False}, GLOVE: {"S1": False, "S2": False}},
        },
        ("Task 4", "Time (s)"): {
            NO_GLOVE: {"S1": [42.84, 33.52, 31.28], "S2": [53.60, 32.63, 29.77]},
            GLOVE: {"S1": [88.78, 70.97, 79.02], "S2": [93.60, 79.51, 54.83]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": False}, GLOVE: {"S1": False, "S2": False}},
        },
        ("Task 4", "Score"): {
            NO_GLOVE: {"S1": [4, 4, 4], "S2": [3, 5, 5]},
            GLOVE: {"S1": [4, 5, 4], "S2": [4, 4, 5]},
            "wrist": {NO_GLOVE: {"S1": False, "S2": False}, GLOVE: {"S1": False, "S2": False}},
        },
        ("Task 5", "Time (s)"): {
            NO_GLOVE: {"S2": [8.25, 14.49, 9.71], "S3": [9.96, 8.00, 7.09]},
            GLOVE: {"S2": [8.34, 10.62, 11.79], "S3": [12.79, 11.94, 9.19]},
            "wrist": {NO_GLOVE: {"S2": False, "S3": False}, GLOVE: {"S2": False, "S3": False}},
        },
        ("Task 6", "Time (s)"): {
            NO_GLOVE: {"S2": [10.61, 9.52, 10.29], "S3": [6.23, 6.53, 8.86]},
            GLOVE: {"S2": [15.31, 19.64, 15.19], "S3": [10.96, 9.79, 9.30]},
            "wrist": {NO_GLOVE: {"S2": True, "S3": False}, GLOVE: {"S2": False, "S3": False}},
        },
        ("Task 7", "Time (s)"): {
            NO_GLOVE: {"S2": [23.54, 15.67, 8.93]},
            GLOVE: {"S2": [19.75, 16.48, 14.89]},
            "wrist": {NO_GLOVE: {"S2": False}, GLOVE: {"S2": False}},
        },
    }


def clean_values(values: list[float]) -> list[float]:
    array = np.asarray(values, dtype=float)
    return array[~np.isnan(array)].tolist()


def subjects_with_wrist_compensation(panel_data: dict[tuple[str, str], dict[str, dict[str, list[float]]]]) -> set[str]:
    subjects: set[str] = set()
    for panel in panel_data.values():
        wrist_data = panel["wrist"]
        for condition in CONDITIONS:
            for subject, used_wrist in wrist_data[condition].items():
                if used_wrist:
                    subjects.add(subject)
    return subjects


def subject_offsets(subjects: tuple[str, ...]) -> dict[str, float]:
    if len(subjects) == 1:
        offsets = [0.0]
    else:
        offsets = np.linspace(-0.22, 0.22, len(subjects))
    return dict(zip(subjects, offsets, strict=True))


def style_axis(ax: plt.Axes, spec: PanelSpec) -> None:
    ax.set_xlim(0.45, 2.55)
    ax.set_ylim(*spec.ylim)
    ax.set_yticks(spec.yticks)
    ax.set_ylabel(spec.ylabel, fontsize=9)
    ax.set_xticks([1, 2], [NO_GLOVE, GLOVE])
    ax.tick_params(axis="both", labelsize=8, direction="out", length=3)
    ax.grid(axis="y", color="#E6E6E6", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    for tick, label in zip(ax.get_xticklabels(), (NO_GLOVE, GLOVE), strict=True):
        tick.set_color(CONDITION_COLORS[label])
        tick.set_fontweight("bold")


def draw_subject_boxplots(ax: plt.Axes, spec: PanelSpec, panel_data: dict[str, dict[str, list[float]]]) -> None:
    offsets = subject_offsets(spec.subjects)
    group_means: dict[str, list[float]] = {NO_GLOVE: [], GLOVE: []}

    for subject in spec.subjects:
        subject_color = SUBJECT_COLORS[subject]
        for center, condition in zip((1, 2), CONDITIONS, strict=True):
            values = clean_values(panel_data[condition].get(subject, []))
            if not values:
                continue

            position = center + offsets[subject]
            wrist_flag = panel_data["wrist"][condition].get(subject, False)
            edge_color = WRIST_COLOR if wrist_flag else subject_color

            box = ax.boxplot(
                [values],
                positions=[position],
                widths=0.18,
                patch_artist=True,
                manage_ticks=False,
                showfliers=False,
                whis=(0, 100),
                medianprops={"color": "#1F1F1F", "linewidth": 1.2},
                boxprops={"facecolor": subject_color, "edgecolor": edge_color, "linewidth": 1.5, "alpha": 0.72},
                whiskerprops={"color": edge_color, "linewidth": 1.2},
                capprops={"color": edge_color, "linewidth": 1.2},
            )
            for patch in box["boxes"]:
                patch.set_zorder(3)

            mean_value = float(np.mean(values))
            group_means[condition].append(mean_value)
            ax.scatter(position, mean_value, s=18, color="white", edgecolors=edge_color, linewidths=0.8, zorder=4)

    for center, condition in zip((1, 2), CONDITIONS, strict=True):
        if not group_means[condition]:
            continue
        mean_line = float(np.mean(group_means[condition]))
        ax.plot(
            [center - 0.34, center + 0.34],
            [mean_line, mean_line],
            color=CONDITION_COLORS[condition],
            linewidth=2.2,
            solid_capstyle="round",
            zorder=2,
        )


def add_panel_annotations(ax: plt.Axes, spec: PanelSpec) -> None:
    ax.set_title(spec.task, fontsize=10, fontweight="bold", color="#141414", pad=14)
    if spec.note and spec.note_xy:
        note_kwargs = {"fontsize": 8, "color": "#555555"}
        if spec.note_kwargs:
            note_kwargs.update(spec.note_kwargs)
        ax.text(spec.note_xy[0], spec.note_xy[1], spec.note, ha="center", va="bottom", **note_kwargs)


def add_group_borders(fig: plt.Figure, axes_map: dict[tuple[int, int], plt.Axes]) -> None:
    groups = [
        [(0, 0), (0, 1)],
        [(0, 2), (0, 3)],
        [(0, 4), (0, 5)],
        [(1, 0), (1, 1)],
        [(1, 2)],
        [(1, 3)],
        [(1, 4)],
    ]

    for group in groups:
        boxes = [axes_map[key].get_position() for key in group]
        x0 = min(box.x0 for box in boxes) - 0.008
        y0 = min(box.y0 for box in boxes) - 0.01
        x1 = max(box.x1 for box in boxes) + 0.008
        y1 = max(box.y1 for box in boxes) + 0.03
        rect = Rectangle(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            transform=fig.transFigure,
            fill=False,
            linewidth=0.8,
            edgecolor="#C7C7C7",
            zorder=0,
        )
        fig.add_artist(rect)


def draw_legend(ax: plt.Axes, wrist_subjects: set[str]) -> None:
    ax.axis("off")
    handles = []
    for subject in ("S1", "S2", "S3"):
        edgecolor = WRIST_COLOR if subject in wrist_subjects else SUBJECT_COLORS[subject]
        linewidth = 1.8 if subject in wrist_subjects else 1.0
        label = SUBJECT_LABELS[subject]
        if subject in wrist_subjects:
            label = f"{label} (tenodesis)"
        handles.append(
            Patch(
                facecolor=SUBJECT_COLORS[subject],
                edgecolor=edgecolor,
                linewidth=linewidth,
                alpha=0.72,
                label=label,
            )
        )
    handles.extend(
        [
        Line2D([0], [0], color=CONDITION_COLORS[NO_GLOVE], linewidth=2.2, label="No glove mean"),
        Line2D([0], [0], color=CONDITION_COLORS[GLOVE], linewidth=2.2, label="Glove mean"),
        ]
    )

    ax.legend(
        handles=handles,
        loc="upper left",
        frameon=False,
        fontsize=7.5,
        handlelength=1.8,
        labelspacing=0.7,
        borderaxespad=0.0,
    )
    ax.text(
        0.0,
        0.18,
        "S3 could not complete Task 7.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7.2,
        color="#666666",
        fontstyle="italic",
    )


def create_figure() -> plt.Figure:
    panel_specs = build_panel_specs()
    panel_data = build_panel_data()
    wrist_subjects = subjects_with_wrist_compensation(panel_data)

    fig = plt.figure(figsize=(15.5, 7.6), facecolor="white")
    grid = GridSpec(
        2,
        6,
        figure=fig,
        width_ratios=[1, 1, 1, 1, 1, 1],
        wspace=0.62,
        hspace=0.5,
        left=0.06,
        right=0.97,
        top=0.92,
        bottom=0.08,
    )

    axes_map: dict[tuple[int, int], plt.Axes] = {}
    for spec in panel_specs:
        ax = fig.add_subplot(grid[spec.row, spec.col])
        style_axis(ax, spec)
        draw_subject_boxplots(ax, spec, panel_data[(spec.task, spec.metric)])
        add_panel_annotations(ax, spec)
        axes_map[(spec.row, spec.col)] = ax

    legend_ax = fig.add_subplot(grid[1, 5])
    draw_legend(legend_ax, wrist_subjects)
    add_group_borders(fig, axes_map)
    return fig


def main() -> None:
    fig = create_figure()
    output_dir = Path(__file__).resolve().parent
    pdf_path = output_dir / "rehab_glove_results_boxplots.pdf"
    png_path = output_dir / "rehab_glove_results_boxplots.png"
    svg_path = output_dir / "rehab_glove_results_boxplots.svg"
    fig.savefig(pdf_path, dpi=600, bbox_inches="tight")
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    print(f"Saved: {pdf_path.name}, {png_path.name}, and {svg_path.name}")


if __name__ == "__main__":
    main()