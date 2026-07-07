"""
Created on May 5, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Organization Resident Report Microservice
=========================================

Aggregates the per-location ``resident_report`` state (written by
``intelligence.reports.location_reports_resident_microservice``) across all
child locations and produces a single PDF report that is emailed to the
organization's resident-report notification categories.

Pipeline (mirrors ``trends_report``):
1. Datastream ``resident_report_run_test`` triggers a data request for the
   ``resident_report`` state across all locations.
2. ``async_data_request_ready`` builds a deterministic skeleton.
3. A timer bridges the async response back to a sync context where, when
   permitted, a single LLM call fills the executive-summary text.
4. ``_finalize_report`` renders the PDF with fpdf2 + matplotlib and emails
   it to the configured notification categories.

The optional ``disable_llm`` flag in the datastream payload skips the LLM
call entirely and emits a deterministic PDF.
"""

import re

import properties  # type: ignore
import utilities.utilities as utilities  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore

from . import report_builder, services


class OrganizationResidentReportMicroservice(Intelligence):
    """
    Organization-level microservice that aggregates each location's
    ``resident_report`` state into a single PDF and emails it to the
    organization's resident-report notification categories.

    Trigger: Manual only via the ``resident_report_run_test`` datastream
    message with payload ``{"test_case": "generate_report",
    "disable_llm": false}``.
    """

    def __init__(self, botengine, parent):
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        pass

    def destroy(self, botengine):
        pass

    def new_version(self, botengine):
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">new_version()"
        )

    # ==========================================================================
    # Datastream Message Handlers
    # ==========================================================================
    def datastream_updated(self, botengine, address, content):
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def resident_report_run_test(self, botengine, content):
        """Manual trigger to generate the resident report."""
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">resident_report_run_test()")
        test_case = (content or {}).get("test_case", "unknown")
        if test_case == "generate_report":
            self._request_resident_data(
                botengine,
                disable_llm=(content or {}).get("disable_llm", False),
            )
        logger.info("<resident_report_run_test()")

    # ==========================================================================
    # Timer Handler
    # ==========================================================================
    def timer_fired(self, botengine, argument):
        """
        Bridges the async data-request response back to a sync context
        where timers/state mutations are safe.
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        if not isinstance(argument, dict):
            return

        if argument.get("type") != "data_request_timeout":
            return

        retry_count = argument.get("retry_count", 0)
        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)

        if state is not None and state.get("ready_for_processing"):
            logger.info(
                "|timer_fired() Report skeleton ready, starting pipeline"
            )
            state["ready_for_processing"] = False
            botengine.save_variable(
                services.STATE_VAR_REPORT_IN_PROGRESS, state, overwrite=True
            )
            report = state["report"]
            if state.get("disable_llm") or not report.get("enhancement_tasks"):
                self._finalize_report(botengine, report, state["start_time"])
            else:
                self._process_executive_summary_task(
                    botengine, report["enhancement_tasks"][0]
                )
            return

        if retry_count >= services.MAX_DATA_REQUEST_RETRIES:
            logger.warning(
                f"|timer_fired() Max retries ({services.MAX_DATA_REQUEST_RETRIES}) "
                "exceeded. Giving up."
            )
            return

        logger.warning(
            f"|timer_fired() Data request timeout, retry "
            f"{retry_count + 1}/{services.MAX_DATA_REQUEST_RETRIES}"
        )
        self.start_timer_s(
            botengine,
            services.DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": "data_request_timeout",
                "retry_count": retry_count + 1,
            },
            reference="data_request_timeout_resident_report",
        )

    # ==========================================================================
    # Data Request Handlers
    # ==========================================================================
    def async_data_request_ready(self, botengine, reference, content):
        """
        Async context: no timers, no state mutations.
        Builds the report skeleton from the data-request payload and stashes
        it for the timer bridge to consume.
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">async_data_request_ready() reference={reference}")

        if reference == services.DATA_REQUEST_REFERENCE_RESIDENT:
            self._process_resident_data(botengine, content)

        logger.info("<async_data_request_ready()")

    # ==========================================================================
    # LLM Response Handler
    # ==========================================================================
    def llm_response(self, botengine, response, reference, argument):
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">llm_response() reference={reference}")

        Intelligence.llm_response(self, botengine, response, reference, argument)

        if reference == services.LLM_REFERENCE_RESIDENT_REPORT:
            self._handle_executive_summary_response(
                botengine, response, argument
            )

        logger.info("<llm_response()")

    # ==========================================================================
    # Pipeline Methods
    # ==========================================================================
    def _request_resident_data(self, botengine, disable_llm=False):
        """
        Request the ``resident_report`` state across all locations.

        :param disable_llm: When True, skip the executive-summary LLM call
            and produce a deterministic PDF.
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">_request_resident_data() disable_llm={disable_llm}")

        llm_allowed = properties.get_property(
            botengine, "LLM_FEATURES_ALLOWED", False
        )
        if not llm_allowed:
            disable_llm = True
        self.disable_llm = disable_llm

        existing = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        if existing is not None:
            logger.warning(
                "|_request_resident_data() Report already in progress, skipping"
            )
            return

        cutoff_ms = botengine.get_timestamp() - utilities.ONE_WEEK_MS

        botengine.request_data(
            type=botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES,
            reference=services.DATA_REQUEST_REFERENCE_RESIDENT,
            oldest_timestamp_ms=cutoff_ms,
            newest_timestamp_ms=botengine.get_timestamp(),
            names=[services.STATE_RESIDENT_REPORT],
        )

        self.start_timer_s(
            botengine,
            services.DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": "data_request_timeout",
                "retry_count": 0,
            },
            reference="data_request_timeout_resident_report",
        )
        logger.info("<_request_resident_data()")

    def _process_resident_data(self, botengine, content):
        """
        Build the deterministic skeleton from the data-request payload and
        persist it under ``STATE_VAR_REPORT_IN_PROGRESS``.
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_process_resident_data()")

        latest = report_builder.latest_report_per_location(content)
        if not latest:
            logger.warning(
                "|_process_resident_data() No resident_report data across "
                "locations. Skipping."
            )
            logger.info("<_process_resident_data()")
            return

        try:
            organization_name = botengine.get_organization_name() or ""
        except Exception:
            organization_name = ""

        disable_llm = getattr(self, "disable_llm", False)
        report = report_builder.build_report_skeleton(
            latest,
            organization_name=organization_name,
            timestamp_ms=botengine.get_timestamp(),
            disable_llm=disable_llm,
        )

        botengine.save_variable(
            services.STATE_VAR_REPORT_IN_PROGRESS,
            {
                "report": report,
                "tasks_remaining": len(report["enhancement_tasks"]),
                "tasks_completed": 0,
                "start_time": botengine.get_timestamp(),
                "ready_for_processing": True,
                "disable_llm": disable_llm,
            },
            overwrite=True,
        )

        logger.info(
            f"|_process_resident_data() Skeleton saved with "
            f"{len(report['section2_residents'])} residents and "
            f"{len(report['enhancement_tasks'])} enhancement tasks"
        )
        logger.info("<_process_resident_data()")

    # ==========================================================================
    # LLM Pipeline (single executive-summary task)
    # ==========================================================================
    def _process_executive_summary_task(self, botengine, task):
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_process_executive_summary_task()")

        messages, max_tokens = report_builder.build_executive_summary_messages(
            task["data"]
        )
        if not messages:
            logger.warning(
                "|_process_executive_summary_task() Empty messages, "
                "finalizing without LLM"
            )
            state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
            if state:
                self._finalize_report(
                    botengine, state["report"], state["start_time"]
                )
            return

        self.llm_chat(
            botengine,
            reference=services.LLM_REFERENCE_RESIDENT_REPORT,
            argument={
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "fields_to_fill": task["fields_to_fill"],
            },
            messages=messages,
            model=services.LLM_MODEL,
            max_tokens=max_tokens,
            temperature=services.LLM_TEMPERATURE,
        )
        logger.info("<_process_executive_summary_task()")

    def _handle_executive_summary_response(self, botengine, response, argument):
        """
        Apply the LLM-generated executive summary text and finalize.
        Errors do not block PDF emission; we fall through to finalize.
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_handle_executive_summary_response()")

        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        if not state:
            logger.error(
                "|_handle_executive_summary_response() No report in progress"
            )
            return

        report = state["report"]
        try:
            try:
                content = response["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError, AttributeError):
                content = ""
                if response is not None:
                    fallback = response.get("content", "") if isinstance(
                        response, dict
                    ) else ""
                    if isinstance(fallback, str):
                        content = fallback.strip()
                logger.warning(
                    "|_handle_executive_summary_response() Fallback content "
                    f"extraction, length={len(content)}"
                )

            enhanced = self._parse_llm_text_response(
                content, argument.get("fields_to_fill", [])
            )
            report_builder.apply_llm_enhancement(
                report, argument.get("task_id"), enhanced
            )
        except Exception as e:
            import traceback
            logger.error(
                "|_handle_executive_summary_response() Error processing "
                f"response: {e}"
            )
            logger.error(traceback.format_exc())

        self._finalize_report(botengine, report, state["start_time"])
        logger.info("<_handle_executive_summary_response()")

    @staticmethod
    def _parse_llm_text_response(content, expected_fields):
        """Parse ``field_name: value`` lines from the LLM response."""
        result = {}
        for field in expected_fields or []:
            pattern = rf"{field}:\s*(.+?)(?=\n\w+:|$)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                result[field] = match.group(1).strip()
            elif len(expected_fields) == 1:
                result[field] = content.strip()
            else:
                result[field] = ""
        return result

    def _finalize_report(self, botengine, report, start_time):
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_finalize_report()")

        self._generate_and_email_pdf(botengine, report)

        botengine.save_variable(
            services.STATE_VAR_REPORT_IN_PROGRESS, None, overwrite=True
        )

        duration_ms = botengine.get_timestamp() - start_time
        logger.info(f"|_finalize_report() Report completed in {duration_ms}ms")
        logger.info("<_finalize_report()")

    # ==========================================================================
    # PDF Generation
    # ==========================================================================
    def _generate_and_email_pdf(self, botengine, report):
        """
        Render the resident-report PDF (title + executive overview + roster
        table + per-resident detail pages) and email it to the organization's
        resident-report notification categories.
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_generate_and_email_pdf()")

        try:
            import base64
            import datetime
            from io import BytesIO

            from fpdf import FPDF
            from fpdf.fonts import FontFace

            HEADING_COLOR = (44, 62, 80)
            ACCENT_COLOR = (41, 128, 185)
            CONCERNING_FILL = (255, 243, 224)  # Light orange
            CRITICAL_FILL = (255, 224, 224)    # Light red

            _UNICODE_TO_LATIN = str.maketrans({
                "–": "-", "—": "-", "―": "-",
                "‘": "'", "’": "'", "‚": "'",
                "“": '"', "”": '"', "„": '"',
                "•": "*", "…": "...",
                " ": " ", "​": "",
                "‐": "-", "‑": "-",
            })

            def sanitize(text):
                if not isinstance(text, str):
                    text = str(text) if text is not None else ""
                text = text.translate(_UNICODE_TO_LATIN)
                return text.encode("latin-1", errors="replace").decode("latin-1")

            _format_score = OrganizationResidentReportMicroservice._format_score

            class ResidentPDF(FPDF):
                def footer(self):
                    self.set_y(-15)
                    self.set_font("helvetica", "I", 8)
                    self.set_text_color(150)
                    self.cell(
                        0, 10, f"Page {self.page_no()}/{{nb}}",
                        align="C",
                    )

            pdf = ResidentPDF()
            pdf.alias_nb_pages()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_title("Resident Report - Organization")
            pdf.set_author("CareDaily")
            pdf.add_page()

            def section_heading(title):
                pdf.set_font("helvetica", "B", 13)
                pdf.set_text_color(*HEADING_COLOR)
                pdf.cell(0, 9, sanitize(title),
                         new_x="LMARGIN", new_y="NEXT")
                pdf.set_draw_color(*ACCENT_COLOR)
                pdf.set_line_width(0.5)
                pdf.line(
                    pdf.l_margin, pdf.get_y(),
                    pdf.l_margin + pdf.epw, pdf.get_y(),
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

            section1 = report.get("section1_overview", {})
            metadata = report.get("metadata") or section1.get("stats", {})
            residents = report.get("section2_residents", [])
            org_name = report.get("organization_name") or ""

            # ── TITLE PAGE ───────────────────────────────────────────────
            pdf.set_font("helvetica", "B", 20)
            pdf.set_text_color(*ACCENT_COLOR)
            pdf.cell(
                0, 14, "Resident Report",
                new_x="LMARGIN", new_y="NEXT", align="C",
            )
            pdf.set_text_color(100)
            pdf.set_font("helvetica", "", 11)
            report_date = datetime.datetime.fromtimestamp(
                report.get("timestamp_ms", 0) / 1000
            ).strftime("%B %d, %Y")
            subtitle = (
                f"{org_name} - {report_date}" if org_name
                else f"Organization Report - {report_date}"
            )
            pdf.cell(
                0, 7, sanitize(subtitle),
                new_x="LMARGIN", new_y="NEXT", align="C",
            )
            pdf.set_text_color(0)
            pdf.ln(6)

            # ── SECTION 1: EXECUTIVE OVERVIEW ────────────────────────────
            overview_text = section1.get("overview_text", "")
            if overview_text:
                section_heading("Executive Overview")
                pdf.set_font("helvetica", "", 10)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.epw, 5, sanitize(overview_text))
                pdf.ln(5)

            section_heading("Population Statistics")
            pdf.set_font("helvetica", "", 10)
            with pdf.table(
                col_widths=(2, 1),
                borders_layout="SINGLE_TOP_LINE",
                first_row_as_headings=False,
                line_height=6,
                padding=2,
            ) as table:
                rows = [
                    ("Total Residents Reported", metadata.get("total_residents", 0)),
                    ("Residents With Falls Today", metadata.get("with_falls", 0)),
                    ("Total Falls Detected", metadata.get("total_falls", 0)),
                    ("Residents With Critical Events",
                     metadata.get("with_critical_events", 0)),
                    ("Total Critical Events (24h)",
                     metadata.get("total_critical_events", 0)),
                    ("Residents With Wellness < 50",
                     metadata.get("with_low_wellness", 0)),
                    ("Average Wellness Score",
                     metadata.get("avg_wellness_score") if metadata.get("avg_wellness_score") is not None else "--"),
                    ("Residents With Journal", metadata.get("with_journal", 0)),
                    ("Total Night Bathroom Visits",
                     metadata.get("night_bathroom_total", 0)),
                ]
                for label, value in rows:
                    row = table.row()
                    row.cell(sanitize(label), style=FontFace(emphasis="BOLD"))
                    row.cell(sanitize(value))
            pdf.ln(5)

            # ── SECTION 2: RESIDENT ROSTER ───────────────────────────────
            if residents:
                section_heading("Resident Roster")
                pdf.set_font("helvetica", "", 9)
                with pdf.table(
                    col_widths=(3, 1, 1, 5),
                    headings_style=headings_style,
                    line_height=5,
                    padding=1,
                ) as table:
                    header = table.row()
                    header.cell("Location")
                    header.cell("Wellness")
                    header.cell("Falls")
                    header.cell("Status")
                    for resident in residents:
                        wellness = (resident.get("wellness_data") or {}).get("score")
                        falls = len(resident.get("falls_data") or [])
                        journal = resident.get("journal_summary") or ""
                        bathroom = (resident.get("bathroom_data") or {}).get(
                            "description", ""
                        )
                        daily_summary = (resident.get("daily_report") or {}).get(
                            "summary", ""
                        )
                        narrative_count = len(resident.get("narratives") or [])
                        status = journal or daily_summary or bathroom or "-"
                        if narrative_count:
                            status = "[{} critical event(s)] ".format(
                                narrative_count
                            ) + status
                        if falls > 0 or narrative_count:
                            cell_style = FontFace(fill_color=CRITICAL_FILL)
                        elif (wellness is not None
                              and wellness < services.WELLNESS_SCORE_CONCERNING):
                            cell_style = FontFace(fill_color=CONCERNING_FILL)
                        else:
                            cell_style = None
                        row = table.row()
                        row.cell(
                            sanitize(resident.get("location_name") or "-"),
                            style=cell_style,
                        )
                        row.cell(
                            sanitize(_format_score(wellness)),
                            style=cell_style,
                        )
                        row.cell(sanitize(falls), style=cell_style)
                        row.cell(sanitize(status[:120]), style=cell_style)
                pdf.ln(5)

            # ── SECTION 3: PER-RESIDENT DETAIL PAGES ─────────────────────
            for resident in residents:
                pdf.add_page()
                self._render_resident_detail_page(
                    pdf, resident,
                    section_heading=section_heading,
                    sanitize=sanitize,
                    headings_style=headings_style,
                    accent_color=ACCENT_COLOR,
                    bytesio_factory=BytesIO,
                    logger=logger,
                )

            # ── EMAIL ────────────────────────────────────────────────────
            pdf_bytes = pdf.output()
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            attachments = []
            botengine.add_email_attachment(
                destination_attachment_array=attachments,
                filename="Resident_Report_Organization.pdf",
                content=pdf_base64,
                content_type="application/pdf",
                content_id="resident_org_pdf",
            )

            categories = properties.get_property(
                botengine,
                services.NOTIFICATION_CATEGORIES_PROPERTY,
                complain_if_missing=False,
            )
            if not categories:
                categories = [
                    utilities.ORGANIZATION_USER_NOTIFICATION_CATEGORY_REPORTS
                ]

            email_html = self._build_email_html(report)

            botengine.email_admins(
                email_subject=_(  # noqa: F821 # type: ignore
                    "Resident Report - Organization"
                ),
                email_content=email_html,
                email_html=True,
                email_attachments=attachments,
                brand=properties.get_property(
                    botengine, "ORGANIZATION_BRAND",
                    complain_if_missing=False,
                ),
                categories=categories,
            )
            logger.info(
                "|_generate_and_email_pdf() PDF generated and emailed"
            )

        except ImportError as e:
            logger.warning(
                f"|_generate_and_email_pdf() Missing dependency, "
                f"skipping PDF generation: {e}"
            )
        except Exception as e:
            import traceback
            logger.error(
                "|_generate_and_email_pdf() Error generating PDF: "
                f"{e} trace={traceback.format_exc()}"
            )

        logger.info("<_generate_and_email_pdf()")

    @staticmethod
    def _render_resident_detail_page(pdf, resident, *, section_heading,
                                     sanitize, headings_style, accent_color,
                                     bytesio_factory, logger):
        """Render one resident's detailed page on the open PDF document."""
        _format_score = OrganizationResidentReportMicroservice._format_score
        section_heading(resident.get("location_name") or "Resident")

        if resident.get("report_date"):
            pdf.set_font("helvetica", "I", 9)
            pdf.set_text_color(120)
            pdf.cell(0, 5, sanitize(resident["report_date"]),
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0)
            pdf.ln(2)

        daily_summary = (resident.get("daily_report") or {}).get("summary")
        if daily_summary:
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(0, 6, "Daily Summary",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "", 9)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(pdf.epw, 5, sanitize(daily_summary))
            pdf.ln(2)

        wellness = resident.get("wellness_data") or {}
        if wellness.get("score") is not None or wellness.get("categories"):
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(
                0, 6,
                sanitize(
                    f"Wellness Score: {_format_score(wellness.get('score'))}"
                ),
                new_x="LMARGIN", new_y="NEXT",
            )
            pdf.ln(1)
            categories = wellness.get("categories") or {}
            pdf.set_font("helvetica", "", 9)
            with pdf.table(
                col_widths=(2, 1, 1),
                headings_style=headings_style,
                line_height=5,
                padding=1,
            ) as table:
                header = table.row()
                header.cell("Category")
                header.cell("Score")
                header.cell("Delta")
                for key, label in services.SCORE_CATEGORIES:
                    cat = categories.get(key) or {}
                    value = cat.get("value")
                    delta = cat.get("delta")
                    row = table.row()
                    row.cell(sanitize(label))
                    row.cell(sanitize(_format_score(value)))
                    row.cell(sanitize(_format_score(delta)))
            pdf.ln(3)

        falls = resident.get("falls_data") or []
        if falls:
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(*accent_color)
            pdf.cell(0, 6, "Falls Today",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0)
            pdf.set_font("helvetica", "", 9)
            for fall in falls:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.epw, 5, sanitize(
                    f"- {fall.get('description', 'Fall detected')}"
                ))
            pdf.ln(2)

        narratives = resident.get("narratives") or []
        if narratives:
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(*accent_color)
            pdf.cell(0, 6, "Critical Events (Last 24 Hours)",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0)
            pdf.set_font("helvetica", "", 9)
            for narrative in narratives:
                title = narrative.get("title") or "Critical event"
                description = narrative.get("description") or ""
                line = f"- {title}"
                if description:
                    line += f": {description}"
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.epw, 5, sanitize(line))
            pdf.ln(2)

        bathroom = resident.get("bathroom_data") or {}
        if bathroom.get("description"):
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(0, 6, "Bathroom",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "", 9)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(pdf.epw, 5, sanitize(bathroom["description"]))
            pdf.ln(2)

        if resident.get("journal_summary"):
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(0, 6, "Journal",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "", 9)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(pdf.epw, 5, sanitize(resident["journal_summary"]))
            pdf.ln(2)

        score_history = resident.get("score_history") or []
        if score_history:
            try:
                buf = OrganizationResidentReportMicroservice._render_score_history_chart(
                    score_history, bytesio_factory=bytesio_factory,
                )
                if buf is not None:
                    pdf.set_font("helvetica", "B", 11)
                    pdf.cell(0, 6, "Score History",
                             new_x="LMARGIN", new_y="NEXT")
                    pdf.image(buf, x=pdf.l_margin, w=pdf.epw)
                    buf.close()
                    pdf.ln(3)
            except Exception as e:
                if logger:
                    logger.warning(
                        f"|_render_resident_detail_page() chart error: {e}"
                    )

    @staticmethod
    def _format_score(value):
        """Render numeric scores cleanly: ``2.6666...`` -> ``3``, None -> ``--``."""
        if value is None:
            return "--"
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, float)):
            return str(int(round(value)))
        return str(value)

    @staticmethod
    def _render_score_history_chart(score_history, *, bytesio_factory):
        """
        Render a small line chart of recent wellness scores into a PNG buffer.

        ``score_history`` is the dict produced by
        ``location_reports_resident_microservice._get_score_history`` and has
        the shape ``{"dates": [...], "summary": [{"date":..., "value":...}],
        "sleep": [...], ...}``. We plot the ``summary`` (wellness) series in
        chronological order; each series is newest-first.

        :return: BytesIO buffer or ``None`` if there is nothing to plot.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return None

        if not isinstance(score_history, dict):
            return None
        series = score_history.get("summary") or []
        if not series:
            return None

        labels = []
        values = []
        for entry in reversed(series):  # oldest -> newest for the x-axis
            if not isinstance(entry, dict):
                continue
            value = entry.get("value")
            if not isinstance(value, (int, float)):
                continue
            labels.append(entry.get("date") or "")
            values.append(value)
        if not values:
            return None

        buf = bytesio_factory()
        fig, ax = plt.subplots(figsize=(6, 1.8))
        ax.plot(range(len(values)), values, marker="o", linewidth=1.2,
                color="#2980b9")
        ax.set_ylim(0, 100)
        ax.set_ylabel("Wellness")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        buf.seek(0)
        return buf

    @staticmethod
    def _build_email_html(report):
        """
        Build the HTML body for the resident-report email.

        Includes a header, the executive overview (when present), a
        population statistics table, and a roster table with severity row
        highlighting matching the PDF.

        :param report: Completed report dict (sections + metadata)
        :return: HTML string
        """
        import datetime
        import html

        section1 = report.get("section1_overview") or {}
        metadata = report.get("metadata") or section1.get("stats", {}) or {}
        residents = report.get("section2_residents") or []
        org_name = report.get("organization_name") or ""
        report_date = datetime.datetime.fromtimestamp(
            (report.get("timestamp_ms") or 0) / 1000
        ).strftime("%B %d, %Y")

        def esc(value):
            if value is None:
                return ""
            return html.escape(str(value))

        sections = []

        # Header
        title = _("Resident Report - Organization")  # noqa: F821 # type: ignore
        sections.append(
            '<h2 style="color:#1a1a2e;margin:0 0 4px 0;">{}</h2>'.format(
                esc(title)
            )
        )
        subtitle = "{} &mdash; {}".format(esc(org_name), esc(report_date)) \
            if org_name else esc(report_date)
        sections.append(
            '<p style="color:#666;margin:0 0 24px 0;">{}</p>'.format(subtitle)
        )

        # Executive overview (LLM)
        overview_text = section1.get("overview_text") or ""
        if overview_text:
            sections.append(
                '<div style="background:#f0f4ff;border-radius:8px;'
                'padding:16px;margin:0 0 16px 0;">'
                '<h3 style="margin:0 0 8px 0;color:#1a1a2e;">{}</h3>'
                '<p style="color:#444;line-height:1.5;margin:0;">{}</p>'
                '</div>'.format(
                    esc(_("Executive Overview")),  # noqa: F821 # type: ignore
                    esc(overview_text),
                )
            )

        # Population statistics table
        stat_rows = [
            (_("Total Residents Reported"),  # noqa: F821 # type: ignore
             metadata.get("total_residents", 0)),
            (_("Residents With Falls Today"),  # noqa: F821 # type: ignore
             metadata.get("with_falls", 0)),
            (_("Total Falls Detected"),  # noqa: F821 # type: ignore
             metadata.get("total_falls", 0)),
            (_("Residents With Critical Events"),  # noqa: F821 # type: ignore
             metadata.get("with_critical_events", 0)),
            (_("Total Critical Events (Last 24h)"),  # noqa: F821 # type: ignore
             metadata.get("total_critical_events", 0)),
            (_("Residents With Wellness Below {}").format(  # noqa: F821 # type: ignore
                services.WELLNESS_SCORE_CONCERNING),
             metadata.get("with_low_wellness", 0)),
            (_("Average Wellness Score"),  # noqa: F821 # type: ignore
             metadata.get("avg_wellness_score") if
             metadata.get("avg_wellness_score") is not None else "--"),
            (_("Residents With Journal"),  # noqa: F821 # type: ignore
             metadata.get("with_journal", 0)),
            (_("Total Night Bathroom Visits"),  # noqa: F821 # type: ignore
             metadata.get("night_bathroom_total", 0)),
        ]
        stat_html = (
            '<h3 style="color:#1a1a2e;margin:24px 0 8px 0;">{}</h3>'
            '<table style="border-collapse:collapse;width:100%;'
            'margin:0 0 24px 0;">'
        ).format(esc(_("Population Statistics")))  # noqa: F821 # type: ignore
        for label, value in stat_rows:
            stat_html += (
                '<tr>'
                '<td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;'
                'color:#444;">{}</td>'
                '<td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;'
                'color:#1a1a2e;font-weight:600;text-align:right;">{}</td>'
                '</tr>'.format(esc(label), esc(value))
            )
        stat_html += '</table>'
        sections.append(stat_html)

        # Resident roster table
        if residents:
            fmt = OrganizationResidentReportMicroservice._format_score
            roster_html = (
                '<h3 style="color:#1a1a2e;margin:0 0 8px 0;">{}</h3>'
                '<table style="border-collapse:collapse;width:100%;'
                'font-size:13px;">'
                '<thead>'
                '<tr style="background:#2980b9;color:#fff;">'
                '<th style="padding:8px;text-align:left;">{}</th>'
                '<th style="padding:8px;text-align:right;">{}</th>'
                '<th style="padding:8px;text-align:right;">{}</th>'
                '<th style="padding:8px;text-align:left;">{}</th>'
                '</tr></thead><tbody>'
            ).format(
                esc(_("Resident Roster")),  # noqa: F821 # type: ignore
                esc(_("Location")),  # noqa: F821 # type: ignore
                esc(_("Wellness")),  # noqa: F821 # type: ignore
                esc(_("Falls")),  # noqa: F821 # type: ignore
                esc(_("Status")),  # noqa: F821 # type: ignore
            )
            for resident in residents:
                wellness = (resident.get("wellness_data") or {}).get("score")
                falls = len(resident.get("falls_data") or [])
                journal = resident.get("journal_summary") or ""
                bathroom = (resident.get("bathroom_data") or {}).get(
                    "description", ""
                )
                daily_summary = (resident.get("daily_report") or {}).get(
                    "summary", ""
                )
                narrative_count = len(resident.get("narratives") or [])
                status = journal or daily_summary or bathroom or "-"
                if narrative_count:
                    status = _(  # noqa: F821 # type: ignore
                        "[{} critical event(s)] "
                    ).format(narrative_count) + status
                if falls > 0 or narrative_count:
                    row_bg = "#FFE0E0"  # critical
                elif (wellness is not None
                      and wellness < services.WELLNESS_SCORE_CONCERNING):
                    row_bg = "#FFF3E0"  # concerning
                else:
                    row_bg = "#FFFFFF"
                roster_html += (
                    '<tr style="background:{};">'
                    '<td style="padding:6px 8px;border-bottom:1px solid '
                    '#e5e7eb;">{}</td>'
                    '<td style="padding:6px 8px;border-bottom:1px solid '
                    '#e5e7eb;text-align:right;">{}</td>'
                    '<td style="padding:6px 8px;border-bottom:1px solid '
                    '#e5e7eb;text-align:right;">{}</td>'
                    '<td style="padding:6px 8px;border-bottom:1px solid '
                    '#e5e7eb;color:#444;">{}</td>'
                    '</tr>'
                ).format(
                    row_bg,
                    esc(resident.get("location_name") or "-"),
                    esc(fmt(wellness)),
                    esc(falls),
                    esc(status[:200]),
                )
            roster_html += '</tbody></table>'
            sections.append(roster_html)

        # Footer attachment note
        sections.append(
            '<p style="color:#888;font-size:12px;margin:24px 0 0 0;">{}</p>'
            .format(esc(_(  # noqa: F821 # type: ignore
                "The full PDF report with per-resident detail pages is "
                "attached."
            )))
        )

        return (
            '<div style="font-family:Arial,Helvetica,sans-serif;'
            'color:#1a1a2e;max-width:760px;">'
            + "".join(sections)
            + '</div>'
        )
