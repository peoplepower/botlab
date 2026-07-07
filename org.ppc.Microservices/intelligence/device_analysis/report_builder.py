"""
Created on April 6, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Report builder for the device_analysis organization microservice.

Compiles device and parameter statistics, generates PDF reports using fpdf2,
and produces HTML email summaries.
"""

import datetime
import statistics as pystats


def compile_statistics(devices_data, params_data, config):
    """
    Compile statistics from device and parameter data.

    :param devices_data: Device listing data from data request
    :param params_data: Parameter history data from data request
    :param config: Analysis configuration dict
    :return: Statistics dict with device_stats, parameter_stats,
             location_breakdown, and summary
    """
    devices_by_location = devices_data.get("devices_by_location", {})
    total_devices = devices_data.get("total_devices", 0)
    total_locations = devices_data.get("total_locations", 0)

    # Device statistics by type
    by_type = {}
    for location_id, devices in devices_by_location.items():
        for device in devices:
            dt = str(device.get("device_type", "unknown"))
            by_type[dt] = by_type.get(dt, 0) + 1

    # Devices per location distribution
    devices_per_location = {}
    for location_id, devices in devices_by_location.items():
        devices_per_location[location_id] = len(devices)

    device_stats = {
        "by_type": by_type,
        "devices_per_location": devices_per_location,
        "total_devices": total_devices,
        "total_locations": total_locations,
    }

    # Parameter statistics
    parameter_stats = _compile_parameter_stats(params_data, config)

    # Location breakdown
    location_breakdown = _compile_location_breakdown(
        devices_by_location, params_data, config
    )

    summary = {
        "total_devices": total_devices,
        "total_locations": total_locations,
        "device_types_count": len(by_type),
        "parameters_analyzed": len(config.get("parameters", [])),
    }

    return {
        "device_stats": device_stats,
        "parameter_stats": parameter_stats,
        "location_breakdown": location_breakdown,
        "summary": summary,
    }


def _compile_parameter_stats(params_data, config):
    """
    Compile per-parameter statistics across all devices.

    :param params_data: Raw parameter data from data request
    :param config: Analysis configuration
    :return: Dict of {param_name: {min, max, mean, median, stddev, sample_count, unique_values}}
    """
    requested_params = config.get("parameters", [])
    param_values = {p: [] for p in requested_params}

    if isinstance(params_data, dict):
        for device_id, device_params in params_data.items():
            if not isinstance(device_params, dict):
                continue
            for param_name in requested_params:
                readings = device_params.get(param_name, [])
                if isinstance(readings, list):
                    for reading in readings:
                        if isinstance(reading, dict):
                            val = reading.get("value")
                        elif isinstance(reading, (list, tuple)) and len(reading) >= 1:
                            val = reading[0]
                        else:
                            val = reading
                        numeric = _to_numeric(val)
                        if numeric is not None:
                            param_values[param_name].append(numeric)

    result = {}
    for param_name, values in param_values.items():
        if not values:
            result[param_name] = {
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "stddev": None,
                "sample_count": 0,
                "unique_values": 0,
            }
            continue

        result[param_name] = {
            "min": min(values),
            "max": max(values),
            "mean": pystats.mean(values),
            "median": pystats.median(values),
            "stddev": pystats.stdev(values) if len(values) > 1 else 0.0,
            "sample_count": len(values),
            "unique_values": len(set(values)),
        }

    return result


def _compile_location_breakdown(devices_by_location, params_data, config):
    """
    Compile per-location device and parameter summary.

    :param devices_by_location: Dict of {location_id: [device_dicts]}
    :param params_data: Raw parameter data
    :param config: Analysis configuration
    :return: Dict of {location_id: {device_count, by_type, param_highlights}}
    """
    breakdown = {}
    requested_params = config.get("parameters", [])

    for location_id, devices in devices_by_location.items():
        # Count by type
        loc_by_type = {}
        device_ids_in_location = []
        for device in devices:
            dt = str(device.get("device_type", "unknown"))
            loc_by_type[dt] = loc_by_type.get(dt, 0) + 1
            device_ids_in_location.append(device.get("device_id"))

        # Parameter highlights for this location's devices
        param_highlights = {}
        for param_name in requested_params:
            values = []
            if isinstance(params_data, dict):
                for device_id in device_ids_in_location:
                    device_params = params_data.get(device_id, {})
                    if isinstance(device_params, dict):
                        readings = device_params.get(param_name, [])
                        if isinstance(readings, list):
                            for reading in readings:
                                if isinstance(reading, dict):
                                    val = reading.get("value")
                                elif (
                                    isinstance(reading, (list, tuple))
                                    and len(reading) >= 1
                                ):
                                    val = reading[0]
                                else:
                                    val = reading
                                numeric = _to_numeric(val)
                                if numeric is not None:
                                    values.append(numeric)

            if values:
                param_highlights[param_name] = {
                    "mean": round(pystats.mean(values), 2),
                    "sample_count": len(values),
                }

        breakdown[location_id] = {
            "device_count": len(devices),
            "by_type": loc_by_type,
            "param_highlights": param_highlights,
        }

    return breakdown


def _to_numeric(val):
    """
    Convert a value to float if possible.
    :param val: Any value
    :return: float or None
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    return None


def generate_pdf(report, analysis_name, timestamp_ms):
    """
    Generate a PDF report using fpdf2.

    :param report: Complete report dict with stats and llm_results
    :param analysis_name: Name of the analysis
    :param timestamp_ms: Current timestamp in milliseconds
    :return: PDF as bytes
    """
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    HEADING_COLOR = (44, 62, 80)
    ACCENT_COLOR = (41, 128, 185)
    ALT_ROW_FILL = 230

    _UNICODE_TO_LATIN = str.maketrans(
        {
            "\u2013": "-",
            "\u2014": "-",
            "\u2015": "-",
            "\u2018": "'",
            "\u2019": "'",
            "\u201a": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u201e": '"',
            "\u2022": "*",
            "\u2026": "...",
            "\u00a0": " ",
            "\u200b": "",
            "\u2011": "-",
            "\u2010": "-",
        }
    )

    def sanitize(text):
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        text = text.translate(_UNICODE_TO_LATIN)
        return text.encode("latin-1", errors="replace").decode("latin-1")

    class AnalysisPDF(FPDF):
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

    pdf = AnalysisPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(f"{analysis_name} - Device Analysis Report")
    pdf.set_author("CareDaily")
    pdf.add_page()

    def section_heading(title):
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(*HEADING_COLOR)
        pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
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

    headings_style = FontFace(
        emphasis="BOLD",
        color=255,
        fill_color=ACCENT_COLOR,
    )

    stats = report.get("stats", {})
    device_stats = stats.get("device_stats", {})
    parameter_stats = stats.get("parameter_stats", {})
    location_breakdown = stats.get("location_breakdown", {})
    summary = stats.get("summary", {})
    llm_results = report.get("llm_results", {})

    # ==================================================================
    # TITLE
    # ==================================================================
    report_date = datetime.datetime.fromtimestamp(timestamp_ms / 1000).strftime(
        "%B %d, %Y"
    )

    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(*ACCENT_COLOR)
    pdf.cell(
        0,
        14,
        sanitize(analysis_name),
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.set_text_color(100)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(
        0,
        7,
        sanitize(f"Device Analysis Report - {report_date}"),
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    pdf.set_text_color(0)
    pdf.ln(6)

    # Quick stats
    pdf.set_font("helvetica", "", 10)
    with pdf.table(
        col_widths=(2, 1),
        borders_layout="SINGLE_TOP_LINE",
        first_row_as_headings=False,
        line_height=6,
        padding=2,
    ) as table:
        row = table.row()
        row.cell("Total Devices", style=FontFace(emphasis="BOLD"))
        row.cell(str(summary.get("total_devices", 0)))
        row = table.row()
        row.cell("Total Locations", style=FontFace(emphasis="BOLD"))
        row.cell(str(summary.get("total_locations", 0)))
        row = table.row()
        row.cell("Device Types Analyzed", style=FontFace(emphasis="BOLD"))
        row.cell(str(summary.get("device_types_count", 0)))
        row = table.row()
        row.cell("Parameters Analyzed", style=FontFace(emphasis="BOLD"))
        row.cell(str(summary.get("parameters_analyzed", 0)))
    pdf.ln(5)

    # ==================================================================
    # SECTION 1: FLEET OVERVIEW
    # ==================================================================
    section_heading("Section 1: Fleet Overview")

    overview_text = llm_results.get("task_device_overview", {}).get("overview_text", "")
    if overview_text:
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 5, sanitize(overview_text))
        pdf.ln(5)

    # Device type table
    by_type = device_stats.get("by_type", {})
    if by_type:
        pdf.set_font("helvetica", "", 10)
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
                row.cell(str(dt), style=style)
                row.cell(str(count), style=style)
        pdf.ln(5)

    # ==================================================================
    # SECTION 2: PARAMETER ANALYSIS
    # ==================================================================
    if parameter_stats:
        pdf.add_page()
        section_heading("Section 2: Parameter Analysis")

        insights_text = llm_results.get("task_parameter_insights", {}).get(
            "insights_text", ""
        )
        if insights_text:
            pdf.set_font("helvetica", "", 10)
            pdf.multi_cell(0, 5, sanitize(insights_text))
            pdf.ln(5)

        pdf.set_font("helvetica", "", 10)
        with pdf.table(
            col_widths=(2, 1, 1, 1, 1, 1, 1),
            headings_style=headings_style,
            line_height=6,
            padding=2,
        ) as table:
            header = table.row()
            header.cell("Parameter")
            header.cell("Min")
            header.cell("Max")
            header.cell("Mean")
            header.cell("Median")
            header.cell("Std Dev")
            header.cell("Samples")
            for idx, (param_name, pstats) in enumerate(parameter_stats.items()):
                style = FontFace(fill_color=ALT_ROW_FILL) if idx % 2 == 1 else None
                row = table.row()
                row.cell(sanitize(param_name), style=style)
                row.cell(_fmt_num(pstats.get("min")), style=style)
                row.cell(_fmt_num(pstats.get("max")), style=style)
                row.cell(_fmt_num(pstats.get("mean")), style=style)
                row.cell(_fmt_num(pstats.get("median")), style=style)
                row.cell(_fmt_num(pstats.get("stddev")), style=style)
                row.cell(str(pstats.get("sample_count", 0)), style=style)
        pdf.ln(5)

    # ==================================================================
    # SECTION 3: LOCATION BREAKDOWN
    # ==================================================================
    if location_breakdown:
        pdf.add_page()
        section_heading("Section 3: Device Breakdown by Location")

        pdf.set_font("helvetica", "", 10)
        with pdf.table(
            col_widths=(2, 1, 2, 2),
            headings_style=headings_style,
            line_height=6,
            padding=2,
        ) as table:
            header = table.row()
            header.cell("Location ID")
            header.cell("Devices")
            header.cell("Device Types")
            header.cell("Parameter Highlights")
            for idx, (location_id, loc_data) in enumerate(
                sorted(
                    location_breakdown.items(),
                    key=lambda x: -x[1].get("device_count", 0),
                )
            ):
                style = FontFace(fill_color=ALT_ROW_FILL) if idx % 2 == 1 else None
                row = table.row()
                row.cell(sanitize(str(location_id)), style=style)
                row.cell(str(loc_data.get("device_count", 0)), style=style)

                # Format device types
                type_parts = [
                    f"{dt}: {ct}" for dt, ct in loc_data.get("by_type", {}).items()
                ]
                row.cell(sanitize(", ".join(type_parts)), style=style)

                # Format parameter highlights
                highlights = loc_data.get("param_highlights", {})
                highlight_parts = [
                    f"{p}: mean={h.get('mean', 'N/A')} (n={h.get('sample_count', 0)})"
                    for p, h in highlights.items()
                ]
                row.cell(
                    sanitize(", ".join(highlight_parts) if highlight_parts else "N/A"),
                    style=style,
                )
        pdf.ln(5)

    # ==================================================================
    # SECTION 4: RECOMMENDATIONS
    # ==================================================================
    recs_text = llm_results.get("task_recommendations", {}).get(
        "recommendations_text", ""
    )
    if recs_text:
        if pdf.get_y() > 200:
            pdf.add_page()
        section_heading("Section 4: Recommendations")
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 5, sanitize(recs_text))
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
        sanitize(
            "This report is HIPAA compliant. No personally identifiable "
            "information (PII) is included. Locations are referenced by ID only."
        ),
    )

    return pdf.output()


def generate_html_summary(report, analysis_name):
    """
    Generate an HTML email summary with key highlights.

    :param report: Complete report dict
    :param analysis_name: Name of the analysis
    :return: HTML string
    """
    stats = report.get("stats", {})
    summary = stats.get("summary", {})
    device_stats = stats.get("device_stats", {})
    llm_results = report.get("llm_results", {})

    overview_text = llm_results.get("task_device_overview", {}).get("overview_text", "")
    recs_text = llm_results.get("task_recommendations", {}).get(
        "recommendations_text", ""
    )

    by_type_rows = ""
    for dt, count in sorted(
        device_stats.get("by_type", {}).items(), key=lambda x: -x[1]
    ):
        by_type_rows += f"<tr><td>{dt}</td><td>{count}</td></tr>"

    html = f"""<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
<h2 style="color: #2980b9;">{analysis_name} - Device Analysis Report</h2>

<table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
<tr><td style="padding: 4px 8px;"><strong>Total Devices</strong></td>
    <td style="padding: 4px 8px;">{summary.get("total_devices", 0)}</td></tr>
<tr><td style="padding: 4px 8px;"><strong>Total Locations</strong></td>
    <td style="padding: 4px 8px;">{summary.get("total_locations", 0)}</td></tr>
<tr><td style="padding: 4px 8px;"><strong>Device Types</strong></td>
    <td style="padding: 4px 8px;">{summary.get("device_types_count", 0)}</td></tr>
<tr><td style="padding: 4px 8px;"><strong>Parameters Analyzed</strong></td>
    <td style="padding: 4px 8px;">{summary.get("parameters_analyzed", 0)}</td></tr>
</table>"""

    if overview_text:
        html += f"""
<h3 style="color: #2c3e50;">Fleet Overview</h3>
<p>{overview_text}</p>"""

    if by_type_rows:
        html += f"""
<h3 style="color: #2c3e50;">Devices by Type</h3>
<table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
<tr style="background-color: #2980b9; color: white;">
    <th style="padding: 6px 8px; text-align: left;">Device Type</th>
    <th style="padding: 6px 8px; text-align: left;">Count</th></tr>
{by_type_rows}
</table>"""

    if recs_text:
        html += f"""
<h3 style="color: #2c3e50;">Recommendations</h3>
<p>{recs_text}</p>"""

    html += """
<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
<p style="font-size: 11px; color: #999;">
This report is HIPAA compliant. No personally identifiable information (PII) is included.
Please see the attached PDF for the full analysis.</p>
</body>
</html>"""

    return html


def _fmt_num(val):
    """Format a numeric value for display."""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return f"{val:.2f}"
    return str(val)
