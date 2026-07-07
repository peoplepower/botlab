"""
Created on March 13, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Matplotlib Chart Generation
============================

Generates statistical plots for the trends report PDF.
All functions return BytesIO PNG buffers suitable for embedding in fpdf2.
"""

import datetime
from io import BytesIO

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless server
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402

from . import services


# Color palette for trend categories
CATEGORY_COLORS = {
    "category.sleep": "#5B5EA6",
    "category.bathroom": "#9B59B6",
    "category.activity": "#2ECC71",
    "category.social": "#F39C12",
    "category.stability": "#E74C3C",
    "category.energy": "#1ABC9C",
    "category.ambient": "#3498DB",
    "category.care": "#E67E22",
    "category.health": "#E91E63",
    "category.summary": "#607D8B",
    "category.other": "#95A5A6",
}

HEALTH_COLORS = {
    "healthy": "#2ECC71",
    "concerning": "#F39C12",
    "critical": "#E74C3C",
}


def generate_category_overview_chart(category_stats, metadata):
    """
    Generate horizontal bar chart of trend counts and location coverage by category.

    :param category_stats: Dict {category: {trend_count, location_count, ...}}
    :param metadata: Trends metadata dict
    :return: BytesIO PNG buffer
    """
    if not category_stats:
        return _empty_chart("No category data available")

    categories = []
    trend_counts = []
    location_counts = []
    colors = []

    for cat, stats in sorted(category_stats.items()):
        label = services.TREND_CATEGORY_LABELS.get(cat, cat)
        categories.append(label)
        trend_counts.append(stats.get("trend_count", 0))
        location_counts.append(stats.get("location_count", 0))
        colors.append(CATEGORY_COLORS.get(cat, "#95A5A6"))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, max(3, len(categories) * 0.4)))

    y_pos = range(len(categories))

    ax1.barh(y_pos, trend_counts, color=colors, height=0.6)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(categories, fontsize=8)
    ax1.set_xlabel("Trend Types", fontsize=9)
    ax1.set_title("Trends by Category", fontsize=10, fontweight="bold")
    ax1.invert_yaxis()

    ax2.barh(y_pos, location_counts, color=colors, height=0.6)
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(categories, fontsize=8)
    ax2.set_xlabel("Locations", fontsize=9)
    ax2.set_title("Location Coverage", fontsize=10, fontweight="bold")
    ax2.invert_yaxis()

    plt.tight_layout()
    return _save_figure(fig)


HEATMAP_ROWS_PER_PAGE = 20


def generate_zscore_heatmap(section2_data, metadata):
    """
    Generate paginated heatmap of average absolute z-scores.

    Rows are locations sorted by their summary trend z-score (highest deviation
    first). Output is paginated so each page contains at most
    ``HEATMAP_ROWS_PER_PAGE`` rows.

    :param section2_data: Dict {location_id: {current_trends: {...}}}
    :param metadata: Trends metadata dict
    :return: List of BytesIO PNG buffers (one per page)
    """
    if not section2_data:
        return [_empty_chart("No location data available")]

    # Collect categories
    all_categories = set()
    for loc_id, loc_data in section2_data.items():
        for trend_id, trend_info in loc_data.get("current_trends", {}).items():
            all_categories.add(trend_info.get("category", "category.other"))

    categories = sorted(all_categories)
    location_ids = list(section2_data.keys())

    if not categories or not location_ids:
        return [_empty_chart("Insufficient data for heatmap")]

    # Compute per-location summary z-score for sorting
    loc_summary = {}
    for loc_id in location_ids:
        current = section2_data[loc_id].get("current_trends", {})
        all_z = [
            abs(t.get("zscore", 0))
            for t in current.values()
            if t.get("zscore") is not None
        ]
        loc_summary[loc_id] = sum(all_z) / len(all_z) if all_z else 0

    # Sort by summary z-score descending (most deviant locations first)
    location_ids.sort(key=lambda lid: loc_summary[lid], reverse=True)

    # Build matrix
    matrix = []
    for loc_id in location_ids:
        row = []
        current = section2_data[loc_id].get("current_trends", {})
        for cat in categories:
            zscores = [
                abs(t.get("zscore", 0))
                for t in current.values()
                if t.get("category") == cat and t.get("zscore") is not None
            ]
            avg_z = sum(zscores) / len(zscores) if zscores else 0
            row.append(avg_z)
        matrix.append(row)

    cat_labels = [services.TREND_CATEGORY_LABELS.get(c, c) for c in categories]
    loc_labels = [f"Location {lid}" for lid in location_ids]
    max_val = max(max(row) for row in matrix) if matrix else 3
    vmax = max(3, max_val)

    # Paginate
    total = len(location_ids)
    pages = []
    for start in range(0, total, HEATMAP_ROWS_PER_PAGE):
        end = min(start + HEATMAP_ROWS_PER_PAGE, total)
        page_matrix = matrix[start:end]
        page_labels = loc_labels[start:end]
        page_num = start // HEATMAP_ROWS_PER_PAGE + 1
        total_pages = (total + HEATMAP_ROWS_PER_PAGE - 1) // HEATMAP_ROWS_PER_PAGE

        row_height = 0.25
        fig_h = max(3, len(page_labels) * row_height + 1.5)
        fig, ax = plt.subplots(figsize=(max(6, len(categories) * 0.9), fig_h))

        im = ax.imshow(page_matrix, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=vmax)
        ax.set_xticks(range(len(cat_labels)))
        ax.set_xticklabels(cat_labels, fontsize=7, rotation=45, ha="right")
        ax.set_yticks(range(len(page_labels)))
        ax.set_yticklabels(page_labels, fontsize=6)

        title = "Z-Score Overview by Location & Category"
        if total_pages > 1:
            title += f" (Page {page_num}/{total_pages})"
        ax.set_title(title, fontsize=10, fontweight="bold")

        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("Avg |Z-Score|", fontsize=8)

        plt.tight_layout()
        pages.append(_save_figure(fig))

    return pages


def generate_individual_overview_charts(health_distribution, wellness_history):
    """
    Generate side-by-side pie chart (health distribution) and wellness score
    timeline for a single location.

    :param health_distribution: Dict {healthy, concerning, critical}
    :param wellness_history: List of {day_ms, value} dicts
    :return: BytesIO PNG buffer
    """
    has_pie = any(v > 0 for v in health_distribution.values())
    has_timeline = bool(wellness_history)

    if not has_pie and not has_timeline:
        return _empty_chart("No individual overview data available")

    fig, (ax_pie, ax_timeline) = plt.subplots(1, 2, figsize=(9, 3.5))

    # Left: Pie chart of health distribution
    if has_pie:
        labels = []
        sizes = []
        colors = []
        for level in ("healthy", "concerning", "critical"):
            count = health_distribution.get(level, 0)
            if count > 0:
                labels.append(f"{level.capitalize()} ({count})")
                sizes.append(count)
                colors.append(HEALTH_COLORS[level])

        ax_pie.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.0f%%",
            startangle=90,
            textprops={"fontsize": 8},
        )
        ax_pie.set_title("Trend Health", fontsize=10, fontweight="bold")
    else:
        ax_pie.text(
            0.5, 0.5, "No health data",
            ha="center", va="center", fontsize=10, color="#999999",
        )
        ax_pie.axis("off")

    # Right: Wellness score timeline
    if has_timeline:
        dates = []
        values = []
        for point in wellness_history:
            if point.get("value") is not None:
                try:
                    dt = datetime.datetime.fromtimestamp(int(point["day_ms"]) / 1000)
                    dates.append(dt)
                    values.append(point["value"])
                except (ValueError, TypeError, OSError):
                    continue

        if dates and values:
            ax_timeline.plot(
                dates, values,
                color="#2980B9", linewidth=2, marker="o", markersize=4,
            )
            ax_timeline.fill_between(dates, values, alpha=0.1, color="#2980B9")
            ax_timeline.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax_timeline.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax_timeline.tick_params(axis="x", labelsize=7, rotation=30)
            ax_timeline.tick_params(axis="y", labelsize=7)
            ax_timeline.set_ylabel("Score", fontsize=8)
            ax_timeline.grid(axis="y", alpha=0.3)
        ax_timeline.set_title("Wellness Score", fontsize=10, fontweight="bold")
    else:
        ax_timeline.text(
            0.5, 0.5, "No wellness data",
            ha="center", va="center", fontsize=10, color="#999999",
        )
        ax_timeline.axis("off")

    plt.tight_layout()
    return _save_figure(fig)


def generate_category_health_chart(category_health):
    """
    Generate stacked bar chart of healthy/concerning/critical counts per category.

    :param category_health: Dict {category: {healthy, concerning, critical}}
    :return: BytesIO PNG buffer
    """
    if not category_health:
        return _empty_chart("No category health data available")

    categories = sorted(category_health.keys())
    labels = [services.TREND_CATEGORY_LABELS.get(c, c) for c in categories]
    healthy = [category_health[c].get("healthy", 0) for c in categories]
    concerning = [category_health[c].get("concerning", 0) for c in categories]
    critical = [category_health[c].get("critical", 0) for c in categories]

    fig, ax = plt.subplots(figsize=(max(6, len(categories) * 0.8), 4))
    x = range(len(categories))
    width = 0.6

    ax.bar(x, healthy, width, label="Healthy", color=HEALTH_COLORS["healthy"])
    ax.bar(x, concerning, width, bottom=healthy, label="Concerning", color=HEALTH_COLORS["concerning"])
    bottom_critical = [h + c for h, c in zip(healthy, concerning)]
    ax.bar(x, critical, width, bottom=bottom_critical, label="Critical", color=HEALTH_COLORS["critical"])

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=45, ha="right")
    ax.set_ylabel("Trend-Location Readings", fontsize=9)
    ax.set_title("Category Health Distribution", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8)

    plt.tight_layout()
    return _save_figure(fig)


def _save_figure(fig):
    """
    Save matplotlib figure to BytesIO buffer and close it.

    :param fig: matplotlib Figure
    :return: BytesIO PNG buffer
    """
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf


def _empty_chart(message):
    """
    Generate a simple chart with a centered message for empty data cases.

    :param message: Text to display
    :return: BytesIO PNG buffer
    """
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=10, color="#999999")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return _save_figure(fig)
