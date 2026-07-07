"""
Created on May 4, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Top-down (X-Y) matplotlib renderer for radar room + subregion configurations.

Each call returns a BytesIO PNG buffer suitable for fpdf2's pdf.image().
"""

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from . import services  # noqa: E402


def generate_floorplan(room, subregions, device_label, device_type=None):
    """
    Render a 2D top-down view of one radar device's room and subregions.

    :param room: Dict with x_min_meters, x_max_meters, y_min_meters, y_max_meters,
                 z_min_meters, z_max_meters, mounting_type, sensor_height_m.
    :param subregions: List of subregion dicts (each with name, context_id, x/y bounds).
    :param device_label: Short label drawn into the title.
    :param device_type: Optional integer device type. Pontosense (2007) uses
        an inverted X-axis convention so that the sensor appears at the
        bottom-right corner of the rendered floorplan.
    :return: BytesIO containing a PNG. Caller is responsible for closing it.
    """
    x_min = room.get("x_min_meters", services.DEFAULT_ROOM["x_min_meters"])
    x_max = room.get("x_max_meters", services.DEFAULT_ROOM["x_max_meters"])
    y_min = room.get("y_min_meters", services.DEFAULT_ROOM["y_min_meters"])
    y_max = room.get("y_max_meters", services.DEFAULT_ROOM["y_max_meters"])
    mounting_type = room.get("mounting_type", services.MOUNTING_TYPE_WALL)
    sensor_height = room.get("sensor_height_m", 1.5)
    flip_x = device_type == services.DEVICE_TYPE_PONTOSENSE

    fig, ax = plt.subplots(figsize=(7.5, 5.5))

    # Room rectangle
    ax.add_patch(
        mpatches.Rectangle(
            (x_min, y_min),
            x_max - x_min,
            y_max - y_min,
            fill=False,
            edgecolor="black",
            linewidth=2.0,
        )
    )

    drawn_contexts = set()
    for sub in subregions:
        sx_min = sub.get("x_min_meters")
        sx_max = sub.get("x_max_meters")
        sy_min = sub.get("y_min_meters")
        sy_max = sub.get("y_max_meters")
        if None in (sx_min, sx_max, sy_min, sy_max):
            continue
        context_id = sub.get("context_id", services.CONTEXT_OTHER)
        color = services.context_color(context_id)
        ax.add_patch(
            mpatches.Rectangle(
                (sx_min, sy_min),
                sx_max - sx_min,
                sy_max - sy_min,
                facecolor=color,
                edgecolor=color,
                linewidth=1.0,
                alpha=0.45,
            )
        )
        ax.text(
            (sx_min + sx_max) / 2,
            (sy_min + sy_max) / 2,
            sub.get("name", "") or services.context_name(context_id),
            ha="center",
            va="center",
            fontsize=8,
            color="black",
        )
        drawn_contexts.add(context_id)

    # Sensor marker - origin (0, 0) is where the sensor sits.
    ax.plot(
        0,
        0,
        marker="^",
        color="red",
        markersize=12,
        markeredgecolor="black",
        zorder=5,
    )
    ax.annotate(
        "Sensor",
        xy=(0, 0),
        xytext=(6, 6),
        textcoords="offset points",
        fontsize=8,
        color="red",
    )

    pad_x = max(0.2, (x_max - x_min) * 0.05)
    pad_y = max(0.2, (y_max - y_min) * 0.05)
    if flip_x:
        # Pontosense convention: invert the X axis so the sensor (X = 0)
        # ends up at the bottom-right corner of the rendered floorplan.
        ax.set_xlim(x_max + pad_x, x_min - pad_x)
    else:
        ax.set_xlim(x_min - pad_x, x_max + pad_x)
    ax.set_ylim(y_min - pad_y, y_max + pad_y)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(
        f"{device_label}  -  {services.mounting_type_name(mounting_type)} mount, "
        f"sensor {sensor_height:.2f} m"
    )

    if drawn_contexts:
        legend_handles = [
            mpatches.Patch(
                facecolor=services.context_color(c),
                edgecolor=services.context_color(c),
                alpha=0.45,
                label=services.context_name(c),
            )
            for c in sorted(drawn_contexts)
        ]
        ax.legend(
            handles=legend_handles,
            loc="upper right",
            fontsize=7,
            framealpha=0.9,
        )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
