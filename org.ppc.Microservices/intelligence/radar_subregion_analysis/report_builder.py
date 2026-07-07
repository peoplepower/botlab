"""
Created on May 4, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

PDF + HTML email summary generator for the radar_subregion_analysis
organization microservice.
"""

import datetime

from . import floorplan_builder, services

HEADING_COLOR = (44, 62, 80)
ACCENT_COLOR = (41, 128, 185)
ALT_ROW_FILL = 230

_UNICODE_TO_LATIN = str.maketrans(
    {
        "–": "-",
        "—": "-",
        "―": "-",
        "‘": "'",
        "’": "'",
        "‚": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "•": "*",
        "…": "...",
        " ": " ",
        "​": "",
        "‑": "-",
        "‐": "-",
        "°": " deg",
    }
)


def _sanitize(text):
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    text = text.translate(_UNICODE_TO_LATIN)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fmt_range(lo, hi):
    if lo is None or hi is None:
        return "-"
    return f"{lo:.2f} – {hi:.2f}"


def _yn(flag):
    if flag is None:
        return "-"
    return "Y" if flag else "N"


def compile_summary(devices_with_config, missing_property_devices):
    """
    Build a small summary structure used on the cover page.

    :param devices_with_config: List of dicts, each:
        {
            "location_id": str,
            "device_id": str,
            "device_type": int,
            "description": str,
            "room": dict,
            "subregions": list[dict],
            "room_defaulted": bool,
        }
    :param missing_property_devices: List of (location_id, device_id, reason) tuples
        for devices we could not pull properties for.
    :return: Summary dict.
    """
    by_type = {}
    by_context = {}
    locations = set()
    total_subregions = 0
    devices_without_subregions = []

    for entry in devices_with_config:
        locations.add(entry["location_id"])
        dt = entry.get("device_type")
        by_type[dt] = by_type.get(dt, 0) + 1

        subs = entry.get("subregions", [])
        if not subs:
            devices_without_subregions.append(entry)
        for sub in subs:
            total_subregions += 1
            ctx = sub.get("context_id", services.CONTEXT_OTHER)
            by_context[ctx] = by_context.get(ctx, 0) + 1

    return {
        "total_locations": len(locations),
        "total_devices": len(devices_with_config),
        "total_subregions": total_subregions,
        "by_device_type": by_type,
        "by_context": by_context,
        "devices_without_subregions": devices_without_subregions,
        "missing_property_devices": list(missing_property_devices),
    }


def behaviors_to_title_map(behaviors):
    """
    Build a {context_id: title} map from a `radar_subregion_behaviors` list.

    :param behaviors: List of behavior dicts (each may carry context_id + title).
    :return: Dict mapping context_id (int) to title (str). Empty if input is invalid.
    """
    titles = {}
    if not isinstance(behaviors, list):
        return titles
    for entry in behaviors:
        if not isinstance(entry, dict):
            continue
        ctx = entry.get("context_id")
        title = entry.get("title")
        if isinstance(title, str) and title and ctx is not None:
            try:
                titles[int(ctx)] = title
            except (TypeError, ValueError):
                continue
    return titles


def context_label(context_id, behavior_titles):
    """
    Resolve a friendly title for a context_id, preferring the behavior map
    over the static fallback in services.CONTEXT_NAMES.
    """
    if behavior_titles and context_id in behavior_titles:
        return behavior_titles[context_id]
    return services.context_name(context_id)


def generate_pdf(
    devices_with_config, summary, analysis_name, timestamp_ms, behaviors=None
):
    """
    Generate the radar subregion analysis PDF.

    :param devices_with_config: List of per-device config dicts (see compile_summary).
    :param summary: Summary dict from compile_summary().
    :param analysis_name: Display name for the report.
    :param timestamp_ms: Current timestamp in milliseconds.
    :param behaviors: Optional list from the `radar_subregion_behaviors` location
        state. If provided, the title for each context_id is taken from this list
        rather than the static services.CONTEXT_NAMES map.
    :return: PDF as bytes.
    """
    behavior_titles = behaviors_to_title_map(behaviors)
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    class RadarSubregionPDF(FPDF):
        def footer(self):
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.set_text_color(150)
            self.cell(
                0,
                10,
                f"Page {self.page_no()}/{{nb}}",
                align="C",
            )

    pdf = RadarSubregionPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(f"{analysis_name} - Radar Subregion Analysis")
    pdf.set_author("CareDaily")

    headings_style = FontFace(
        emphasis="BOLD",
        color=255,
        fill_color=ACCENT_COLOR,
    )

    def section_heading(title):
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(*HEADING_COLOR)
        pdf.cell(0, 9, _sanitize(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*ACCENT_COLOR)
        pdf.set_line_width(0.5)
        pdf.line(
            pdf.l_margin,
            pdf.get_y(),
            pdf.l_margin + pdf.epw,
            pdf.get_y(),
        )
        pdf.ln(3)
        pdf.set_text_color(0)
        pdf.set_draw_color(0)
        pdf.set_line_width(0.2)

    # ==================================================================
    # COVER PAGE
    # ==================================================================
    pdf.add_page()
    report_date = datetime.datetime.fromtimestamp(timestamp_ms / 1000).strftime(
        "%B %d, %Y"
    )

    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(*ACCENT_COLOR)
    pdf.cell(
        0,
        14,
        _sanitize(analysis_name),
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.set_text_color(100)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(
        0,
        7,
        _sanitize(f"Radar Subregion Analysis - {report_date}"),
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.set_text_color(0)
    pdf.ln(6)

    pdf.set_font("helvetica", "", 10)
    with pdf.table(
        col_widths=(2, 1),
        borders_layout="SINGLE_TOP_LINE",
        first_row_as_headings=False,
        line_height=6,
        padding=2,
    ) as table:
        for label, value in (
            ("Locations with Radar", summary.get("total_locations", 0)),
            ("Radar Devices", summary.get("total_devices", 0)),
            ("Subregions Configured", summary.get("total_subregions", 0)),
            (
                "Devices Without Subregions",
                len(summary.get("devices_without_subregions", [])),
            ),
            (
                "Devices Missing Radar State",
                len(summary.get("missing_property_devices", [])),
            ),
        ):
            row = table.row()
            row.cell(label, style=FontFace(emphasis="BOLD"))
            row.cell(str(value))
    pdf.ln(5)

    # Device type breakdown
    by_type = summary.get("by_device_type", {})
    if by_type:
        section_heading("Devices by Type")
        with pdf.table(
            col_widths=(2, 1),
            headings_style=headings_style,
            line_height=6,
            padding=2,
        ) as table:
            header = table.row()
            header.cell("Device Type")
            header.cell("Count")
            for idx, (dt, count) in enumerate(
                sorted(by_type.items(), key=lambda x: -x[1])
            ):
                style = FontFace(fill_color=ALT_ROW_FILL) if idx % 2 == 1 else None
                row = table.row()
                row.cell(_sanitize(services.device_type_name(dt)), style=style)
                row.cell(str(count), style=style)
        pdf.ln(5)

    # Context breakdown
    by_context = summary.get("by_context", {})
    if by_context:
        section_heading("Subregions by Context")
        with pdf.table(
            col_widths=(2, 1),
            headings_style=headings_style,
            line_height=6,
            padding=2,
        ) as table:
            header = table.row()
            header.cell("Context")
            header.cell("Count")
            for idx, (ctx, count) in enumerate(
                sorted(by_context.items(), key=lambda x: -x[1])
            ):
                style = FontFace(fill_color=ALT_ROW_FILL) if idx % 2 == 1 else None
                row = table.row()
                row.cell(_sanitize(context_label(ctx, behavior_titles)), style=style)
                row.cell(str(count), style=style)
        pdf.ln(5)

    # ==================================================================
    # PER-DEVICE PAGES
    # ==================================================================
    sorted_entries = sorted(
        devices_with_config,
        key=lambda e: (str(e.get("location_id")), str(e.get("device_id"))),
    )
    for entry in sorted_entries:
        _render_device_page(
            pdf, entry, section_heading, headings_style, behavior_titles
        )

    # ==================================================================
    # ERRORS APPENDIX
    # ==================================================================
    errors = summary.get("missing_property_devices", [])
    if errors:
        pdf.add_page()
        section_heading("Devices Missing Radar State")
        pdf.set_font("helvetica", "", 10)
        with pdf.table(
            col_widths=(1, 1, 2),
            headings_style=headings_style,
            line_height=6,
            padding=2,
        ) as table:
            header = table.row()
            header.cell("Location ID")
            header.cell("Device ID")
            header.cell("Reason")
            for idx, (loc_id, dev_id, reason) in enumerate(errors):
                style = FontFace(fill_color=ALT_ROW_FILL) if idx % 2 == 1 else None
                row = table.row()
                row.cell(_sanitize(str(loc_id)), style=style)
                row.cell(_sanitize(str(dev_id)), style=style)
                row.cell(_sanitize(str(reason)), style=style)
        pdf.ln(5)

    # ==================================================================
    # FOOTER NOTE
    # ==================================================================
    pdf.ln(5)
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(150)
    pdf.multi_cell(
        0,
        4,
        _sanitize(
            "This report is HIPAA compliant. No personally identifiable "
            "information (PII) is included. Locations and devices are "
            "referenced by ID only."
        ),
    )

    return pdf.output()


def _render_device_page(pdf, entry, section_heading, headings_style, behavior_titles):
    """Render one device's floorplan + subregion table on a fresh PDF page."""
    from fpdf.fonts import FontFace

    pdf.add_page()

    location_id = entry.get("location_id", "")
    device_id = entry.get("device_id", "")
    device_type = entry.get("device_type")
    description = entry.get("description", "") or ""
    room = entry.get("room", {})
    subregions = entry.get("subregions", [])
    room_defaulted = entry.get("room_defaulted", False)

    heading = (
        f"Location {location_id} - {services.device_type_name(device_type)} "
        f"({description})"
        if description
        else f"Location {location_id} - {services.device_type_name(device_type)}"
    )
    section_heading(heading)

    pdf.set_font("helvetica", "", 9)
    pdf.cell(
        0,
        5,
        _sanitize(f"Device ID: {device_id}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    if room_defaulted:
        pdf.set_text_color(150)
        pdf.cell(
            0,
            5,
            _sanitize("(Room boundaries defaulted - device has not published a room)"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(0)
    pdf.ln(2)

    device_label = (
        description
        if description
        else f"{services.device_type_name(device_type)} {device_id}"
    )

    buf = None
    try:
        buf = floorplan_builder.generate_floorplan(
            room, subregions, device_label, device_type=device_type
        )
        pdf.image(buf, w=180)
    finally:
        if buf is not None:
            buf.close()
    pdf.ln(3)

    if not subregions:
        pdf.set_font("helvetica", "I", 9)
        pdf.set_text_color(120)
        pdf.cell(
            0,
            6,
            _sanitize("No subregions configured on this device."),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(0)
        return

    pdf.set_font("helvetica", "", 9)
    with pdf.table(
        col_widths=(3, 2, 2, 2, 2, 1, 1, 1, 1),
        headings_style=headings_style,
        line_height=5,
        padding=1.5,
    ) as table:
        header = table.row()
        for label in (
            "Name",
            "Context",
            "X (m)",
            "Y (m)",
            "Z (m)",
            "Falls",
            "Presence",
            "Door",
            "AI",
        ):
            header.cell(label)
        for idx, sub in enumerate(
            sorted(
                subregions,
                key=lambda s: (s.get("context_id", 99), s.get("name", "") or ""),
            )
        ):
            style = FontFace(fill_color=ALT_ROW_FILL) if idx % 2 == 1 else None
            row = table.row()
            ctx_id = sub.get("context_id")
            row.cell(
                _sanitize(
                    sub.get("name", "") or context_label(ctx_id, behavior_titles)
                ),
                style=style,
            )
            row.cell(
                _sanitize(context_label(ctx_id, behavior_titles)),
                style=style,
            )
            row.cell(
                _sanitize(_fmt_range(sub.get("x_min_meters"), sub.get("x_max_meters"))),
                style=style,
            )
            row.cell(
                _sanitize(_fmt_range(sub.get("y_min_meters"), sub.get("y_max_meters"))),
                style=style,
            )
            row.cell(
                _sanitize(_fmt_range(sub.get("z_min_meters"), sub.get("z_max_meters"))),
                style=style,
            )
            row.cell(_yn(sub.get("detect_falls")), style=style)
            row.cell(_yn(sub.get("detect_presence")), style=style)
            row.cell(_yn(sub.get("is_door")), style=style)
            row.cell(_yn(sub.get("ai")), style=style)
    pdf.ln(3)


def generate_html_summary(summary, analysis_name):
    """
    Generate an HTML email summary describing what's in the attached PDF.

    :param summary: Summary dict from compile_summary().
    :param analysis_name: Display name for the report.
    :return: HTML string.
    """
    by_type_rows = ""
    for dt, count in sorted(
        summary.get("by_device_type", {}).items(), key=lambda x: -x[1]
    ):
        by_type_rows += (
            f"<tr><td>{services.device_type_name(dt)}</td><td>{count}</td></tr>"
        )

    by_context_rows = ""
    for ctx, count in sorted(
        summary.get("by_context", {}).items(), key=lambda x: -x[1]
    ):
        by_context_rows += (
            f"<tr><td>{services.context_name(ctx)}</td><td>{count}</td></tr>"
        )

    html = f"""<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
<h2 style="color: #2980b9;">{analysis_name} - Radar Subregion Analysis</h2>

<table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
<tr><td style="padding: 4px 8px;"><strong>Locations with Radar</strong></td>
    <td style="padding: 4px 8px;">{summary.get("total_locations", 0)}</td></tr>
<tr><td style="padding: 4px 8px;"><strong>Radar Devices</strong></td>
    <td style="padding: 4px 8px;">{summary.get("total_devices", 0)}</td></tr>
<tr><td style="padding: 4px 8px;"><strong>Subregions Configured</strong></td>
    <td style="padding: 4px 8px;">{summary.get("total_subregions", 0)}</td></tr>
<tr><td style="padding: 4px 8px;"><strong>Devices Without Subregions</strong></td>
    <td style="padding: 4px 8px;">{len(summary.get("devices_without_subregions", []))}</td></tr>
</table>"""

    if by_type_rows:
        html += f"""
<h3 style="color: #2c3e50;">Devices by Type</h3>
<table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
<tr style="background-color: #2980b9; color: white;">
    <th style="padding: 6px 8px; text-align: left;">Device Type</th>
    <th style="padding: 6px 8px; text-align: left;">Count</th></tr>
{by_type_rows}
</table>"""

    if by_context_rows:
        html += f"""
<h3 style="color: #2c3e50;">Subregions by Context</h3>
<table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
<tr style="background-color: #2980b9; color: white;">
    <th style="padding: 6px 8px; text-align: left;">Context</th>
    <th style="padding: 6px 8px; text-align: left;">Count</th></tr>
{by_context_rows}
</table>"""

    html += """
<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
<p style="font-size: 11px; color: #999;">
This report is HIPAA compliant. No personally identifiable information (PII) is included.
See the attached PDF for per-device floorplans and subregion details.</p>
</body>
</html>"""

    return html
