"""
===========================================================
QRESERVE
Excel Exporter Service (Week 14: Analytics, Reporting & Audit Logs)
===========================================================
Generates downloadable, beautifully styled multi-sheet Excel
workbooks (.xlsx) using openpyxl for admin reporting, audit trails,
and queue analytics.
"""

import io
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from database import PHILIPPINES_TZ, ph_now, QueueRequest, QueueCounter, AuditLog, Student


def _apply_gridlines(ws):
    """Ensure Excel displays grid lines for the worksheet."""
    if ws.views.sheetView:
        ws.views.sheetView[0].showGridLines = True


def _autofit_columns(ws, min_width=12, max_width=45):
    """Automatically adjust column widths to fit content cleanly."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = cell.value
            if val is not None:
                # If merged cell or multiline, handle first line length
                lines = str(val).split("\n")
                first_len = max(len(l) for l in lines) if lines else 0
                if first_len > max_len:
                    max_len = first_len
        # Apply padding and clamp
        adjusted_width = max(max_len + 3, min_width)
        if adjusted_width > max_width:
            adjusted_width = max_width
        ws.column_dimensions[col_letter].width = adjusted_width


def generate_qreserve_excel(report_type="all", filters=None, admin_user="admin"):
    """
    Generate a professional multi-sheet Excel workbook for QRESERVE.

    Parameters:
      - report_type: "all" (Full Suite), "analytics", "requests", "audit"
      - filters: optional dict with 'status', 'counter', 'date_from', 'date_to', 'user_type'
      - admin_user: username of admin requesting export

    Returns:
      io.BytesIO buffer containing the .xlsx file.
    """
    filters = filters or {}
    now = ph_now()
    now_str = now.strftime("%B %d, %Y at %I:%M:%S %p")

    wb = openpyxl.Workbook()
    # Remove default empty sheet later or use it as first sheet
    first_sheet = wb.active

    # --- Palettes & Styles ---
    crimson_header_fill = PatternFill(start_color="8A0D0D", end_color="8A0D0D", fill_type="solid")
    dark_header_fill    = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    sub_header_fill     = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    accent_gold_fill    = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    zebra_even_fill     = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    zebra_odd_fill      = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    status_completed_fill  = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid") # Emerald
    status_processing_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid") # Amber
    status_ready_fill      = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid") # Blue

    font_univ_title = Font(name="Segoe UI", size=14, bold=True, color="8A0D0D")
    font_sys_sub    = Font(name="Segoe UI", size=11, bold=True, color="1E293B")
    font_meta       = Font(name="Segoe UI", size=9.5, italic=True, color="64748B")
    font_tbl_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    font_sub_header = Font(name="Segoe UI", size=10, bold=True, color="1E293B")
    font_bold       = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    font_regular    = Font(name="Segoe UI", size=9.5, color="1E293B")
    font_small      = Font(name="Segoe UI", size=8.5, color="64748B")

    thin_border_side = Side(border_style="thin", color="CBD5E1")
    border_cell = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left   = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right  = Alignment(horizontal="right", vertical="center", wrap_text=True)

    # Fetch Data
    req_query = QueueRequest.query.order_by(QueueRequest.id.desc())
    if filters.get("status") and filters["status"] != "all":
        req_query = req_query.filter(QueueRequest.status == filters["status"])
    if filters.get("counter") and filters["counter"] != "all":
        req_query = req_query.filter(QueueRequest.counter.like(f"%{filters['counter']}%"))
    if filters.get("user_type") == "student":
        req_query = req_query.filter(QueueRequest.student_id.isnot(None))
    elif filters.get("user_type") == "guest":
        req_query = req_query.filter(QueueRequest.student_id.is_(None))

    all_requests = req_query.all()
    all_audit_logs = AuditLog.query.order_by(AuditLog.id.desc()).all()
    all_counters = QueueCounter.query.order_by(QueueCounter.counter_code).all()

    # -------------------------------------------------------------
    # SHEET 1: Executive Summary & Analytics
    # -------------------------------------------------------------
    if report_type in ("all", "analytics"):
        ws_sum = first_sheet
        ws_sum.title = "Analytics & Summary"
        _apply_gridlines(ws_sum)

        # Header Titles
        ws_sum["A1"] = "BULACAN STATE UNIVERSITY — BUSTOS CAMPUS"
        ws_sum["A1"].font = font_univ_title
        ws_sum["A2"] = "QRESERVE QUEUE MANAGEMENT SYSTEM • EXECUTIVE REPORT & ANALYTICS"
        ws_sum["A2"].font = font_sys_sub
        ws_sum["A3"] = f"Report Generated: {now_str} (PST) | Exported By: {admin_user} | Campus: BulSU Bustos"
        ws_sum["A3"].font = font_meta

        # Section 1: KPI Metrics Card Grid
        ws_sum["A5"] = "1. EXECUTIVE KPI PERFORMANCE OVERVIEW"
        ws_sum["A5"].font = font_sub_header

        kpi_headers = ["Metric Indicator", "Total Count / Value", "Proportion / Context", "Operational Notes"]
        for c_idx, h in enumerate(kpi_headers, start=1):
            cell = ws_sum.cell(row=6, column=c_idx, value=h)
            cell.font = font_tbl_header
            cell.fill = crimson_header_fill
            cell.alignment = align_center
            cell.border = border_cell

        # Compute KPIs
        total_reqs = len(all_requests)
        completed_reqs = sum(1 for r in all_requests if r.status == "Completed")
        processing_reqs = sum(1 for r in all_requests if r.status == "Processing")
        ready_reqs = sum(1 for r in all_requests if r.status == "Ready for pickup")
        student_reqs = sum(1 for r in all_requests if r.student_id)
        guest_reqs = total_reqs - student_reqs
        total_revenue = sum(r.total_price for r in all_requests if r.is_paid)

        kpis_data = [
            ("Total Requests Handled", total_reqs, "100%", "All historical queue transactions logged"),
            ("Completed & Released", completed_reqs, f"{(completed_reqs/total_reqs*100):.1f}%" if total_reqs else "0%", "Documents successfully claimed by students/guests"),
            ("Back-Office Processing", processing_reqs, f"{(processing_reqs/total_reqs*100):.1f}%" if total_reqs else "0%", "Academic records undergoing office preparation (3-5 days)"),
            ("Ready for Student Pickup", ready_reqs, f"{(ready_reqs/total_reqs*100):.1f}%" if total_reqs else "0%", "Prepared documents waiting claiming at window"),
            ("Total Service Revenue", f"PHP {total_revenue:,.2f}", "Cashier Paid", "Official document fees collected & confirmed"),
            ("Registered Student Volume", student_reqs, f"{(student_reqs/total_reqs*100):.1f}%" if total_reqs else "0%", "Authenticated BulSU student portal users"),
            ("Guest / External Volume", guest_reqs, f"{(guest_reqs/total_reqs*100):.1f}%" if total_reqs else "0%", "Walk-in guests or parents using guest queue"),
        ]

        for r_idx, (m_label, m_val, m_prop, m_notes) in enumerate(kpis_data, start=7):
            fill = zebra_even_fill if r_idx % 2 == 0 else zebra_odd_fill
            cells = [
                ws_sum.cell(row=r_idx, column=1, value=m_label),
                ws_sum.cell(row=r_idx, column=2, value=m_val),
                ws_sum.cell(row=r_idx, column=3, value=m_prop),
                ws_sum.cell(row=r_idx, column=4, value=m_notes),
            ]
            for c_i, cell in enumerate(cells):
                cell.font = font_bold if c_i in (0, 1) else font_regular
                cell.fill = fill
                cell.border = border_cell
                cell.alignment = align_right if c_i == 1 else (align_center if c_i == 2 else align_left)

        # Section 2: Most Requested Documents & Services
        start_row_s2 = len(kpis_data) + 9
        ws_sum.cell(row=start_row_s2, column=1, value="2. DOCUMENT & SERVICE DEMAND RANKINGS").font = font_sub_header

        doc_headers = ["Rank", "Document / Request Service", "Total Requests", "Share %", "Est. Revenue (PHP)"]
        for c_idx, h in enumerate(doc_headers, start=1):
            cell = ws_sum.cell(row=start_row_s2 + 1, column=c_idx, value=h)
            cell.font = font_tbl_header
            cell.fill = dark_header_fill
            cell.alignment = align_center
            cell.border = border_cell

        doc_counts = defaultdict(lambda: {"count": 0, "revenue": 0})
        for r in all_requests:
            items = r.items or []
            if items:
                for it in items:
                    name = (it.get("name") or "Document").strip()
                    doc_counts[name]["count"] += 1
                    doc_counts[name]["revenue"] += int(it.get("price") or 0)
            elif r.doc_name:
                name = r.doc_name.strip()
                doc_counts[name]["count"] += 1
                doc_counts[name]["revenue"] += (r.total_price or 0)

        sorted_docs = sorted(doc_counts.items(), key=lambda x: x[1]["count"], reverse=True)
        for d_idx, (doc_name, data_dict) in enumerate(sorted_docs, start=1):
            curr_row = start_row_s2 + 1 + d_idx
            fill = zebra_even_fill if curr_row % 2 == 0 else zebra_odd_fill
            pct = f"{(data_dict['count'] / total_reqs * 100):.1f}%" if total_reqs else "0%"
            row_cells = [
                ws_sum.cell(row=curr_row, column=1, value=d_idx),
                ws_sum.cell(row=curr_row, column=2, value=doc_name),
                ws_sum.cell(row=curr_row, column=3, value=data_dict["count"]),
                ws_sum.cell(row=curr_row, column=4, value=pct),
                ws_sum.cell(row=curr_row, column=5, value=f"PHP {data_dict['revenue']:,.2f}"),
            ]
            for c_i, cell in enumerate(row_cells):
                cell.font = font_bold if c_i == 1 else font_regular
                cell.fill = fill
                cell.border = border_cell
                cell.alignment = align_center if c_i in (0, 3) else (align_right if c_i in (2, 4) else align_left)

        # Section 3: Counter Workload Distribution
        start_row_s3 = start_row_s2 + len(sorted_docs) + 4
        ws_sum.cell(row=start_row_s3, column=1, value="3. COUNTER WORKLOAD & STATION DISTRIBUTION").font = font_sub_header

        counter_headers = ["Counter Code", "Station Name", "Currently Serving", "Waiting at Window", "In Back-Office Processing", "Status"]
        for c_idx, h in enumerate(counter_headers, start=1):
            cell = ws_sum.cell(row=start_row_s3 + 1, column=c_idx, value=h)
            cell.font = font_tbl_header
            cell.fill = crimson_header_fill
            cell.alignment = align_center
            cell.border = border_cell

        for c_i, ctr in enumerate(all_counters, start=1):
            curr_row = start_row_s3 + 1 + c_i
            fill = zebra_even_fill if curr_row % 2 == 0 else zebra_odd_fill
            now_serv = f"{ctr.now_serving_prefix}-{ctr.now_serving_number:03d}" if ctr.now_serving_number > 0 else "Idle / Ready"
            c_cells = [
                ws_sum.cell(row=curr_row, column=1, value=ctr.counter_code),
                ws_sum.cell(row=curr_row, column=2, value=ctr.counter_name),
                ws_sum.cell(row=curr_row, column=3, value=now_serv),
                ws_sum.cell(row=curr_row, column=4, value=ctr.waiting_count),
                ws_sum.cell(row=curr_row, column=5, value=ctr.processing_count),
                ws_sum.cell(row=curr_row, column=6, value="Active Station" if ctr.is_active else "Offline"),
            ]
            for idx, cell in enumerate(c_cells):
                cell.font = font_bold if idx in (0, 1) else font_regular
                cell.fill = fill
                cell.border = border_cell
                cell.alignment = align_center if idx in (0, 2, 3, 4, 5) else align_left

        _autofit_columns(ws_sum, min_width=14, max_width=45)

    # -------------------------------------------------------------
    # SHEET 2: Queue Requests & Transaction Records
    # -------------------------------------------------------------
    if report_type in ("all", "requests"):
        ws_req = wb.create_sheet(title="Queue Requests Records") if report_type == "all" else first_sheet
        if report_type != "all":
            ws_req.title = "Queue Requests Records"
        _apply_gridlines(ws_req)

        # Header Titles
        ws_req["A1"] = "BULACAN STATE UNIVERSITY — BUSTOS CAMPUS"
        ws_req["A1"].font = font_univ_title
        ws_req["A2"] = "COMPLETE QUEUE TRANSACTION LOGS & REQUEST STATUS"
        ws_req["A2"].font = font_sys_sub
        ws_req["A3"] = f"Total Records: {len(all_requests)} | Generated: {now_str} (PST) | Admin: {admin_user}"
        ws_req["A3"].font = font_meta

        headers = [
            "ID", "Queue #", "Student / User Name", "User Type", "Student ID / Identifier",
            "Requested Document(s)", "Assigned Counter", "Fee (PHP)", "Payment Status",
            "Date Queued", "Completed Date", "Queue Stage", "Current Status"
        ]

        header_row = 5
        for col_idx, h in enumerate(headers, start=1):
            cell = ws_req.cell(row=header_row, column=col_idx, value=h)
            cell.font = font_tbl_header
            cell.fill = crimson_header_fill
            cell.alignment = align_center
            cell.border = border_cell

        # Freeze header
        ws_req.freeze_panes = "A6"
        # Auto-filter
        ws_req.auto_filter.ref = f"A5:{get_column_letter(len(headers))}{header_row + max(len(all_requests), 1)}"

        for r_idx, req in enumerate(all_requests, start=6):
            fill = zebra_even_fill if r_idx % 2 == 0 else zebra_odd_fill

            # Determine student name and identifier
            if req.student:
                p = req.student.profile
                user_name = p.full_name if (p and p.full_name) else req.student.email.split("@")[0].title()
                user_type = "Student"
                ident = p.student_id if (p and p.student_id) else req.student.email
            else:
                user_name = req.guest_name or "Guest User"
                user_type = "Guest"
                ident = f"Guest Session"

            payment_status = "Paid" if req.is_paid else "Unpaid (Awaiting Cashier)"
            date_queued = req.created_at.strftime("%Y-%m-%d %I:%M %p") if req.created_at else "—"
            date_completed = req.completed_at.strftime("%Y-%m-%d %I:%M %p") if req.completed_at else "—"

            row_data = [
                f"qrs-{req.id}",
                req.queue_number,
                user_name,
                user_type,
                ident,
                req.item_names,
                req.counter,
                float(req.total_price),
                payment_status,
                date_queued,
                date_completed,
                req.queue_step or "Finished",
                req.status
            ]

            for c_idx, val in enumerate(row_data, start=1):
                cell = ws_req.cell(row=r_idx, column=c_idx, value=val)
                cell.font = font_regular
                cell.fill = fill
                cell.border = border_cell

                # Special column stylings
                if c_idx in (1, 2):  # ID, Queue #
                    cell.alignment = align_center
                    cell.font = font_bold
                elif c_idx == 4:     # User Type
                    cell.alignment = align_center
                elif c_idx == 8:     # Fee
                    cell.alignment = align_right
                    cell.number_format = '"PHP "#,##0.00'
                    cell.font = font_bold
                elif c_idx == 9:     # Payment Status
                    cell.alignment = align_center
                    if req.is_paid:
                        cell.fill = status_completed_fill
                elif c_idx in (10, 11): # Dates
                    cell.alignment = align_center
                elif c_idx == 13:    # Status
                    cell.alignment = align_center
                    cell.font = font_bold
                    if req.status == "Completed":
                        cell.fill = status_completed_fill
                    elif req.status == "Processing":
                        cell.fill = status_processing_fill
                    elif req.status == "Ready for pickup":
                        cell.fill = status_ready_fill
                else:
                    cell.alignment = align_left

        _autofit_columns(ws_req, min_width=12, max_width=40)

    # -------------------------------------------------------------
    # SHEET 3: System Audit Logs (Week 14 Requirement)
    # -------------------------------------------------------------
    if report_type in ("all", "audit"):
        ws_audit = wb.create_sheet(title="System Audit Logs") if report_type == "all" else first_sheet
        if report_type != "all":
            ws_audit.title = "System Audit Logs"
        _apply_gridlines(ws_audit)

        ws_audit["A1"] = "BULACAN STATE UNIVERSITY — BUSTOS CAMPUS"
        ws_audit["A1"].font = font_univ_title
        ws_audit["A2"] = "QRESERVE COMPREHENSIVE SECURITY & OPERATIONAL AUDIT TRAIL"
        ws_audit["A2"].font = font_sys_sub
        ws_audit["A3"] = f"Total Audit Events: {len(all_audit_logs)} | Extracted: {now_str} (PST) | Exported By: {admin_user}"
        ws_audit["A3"].font = font_meta

        audit_headers = [
            "Log ID", "Date (PST)", "Time", "Action Event", "Actor Role", "Actor Account / User",
            "Target / Reference", "Description & Operational Details", "IP Address"
        ]

        h_row = 5
        for col_idx, h in enumerate(audit_headers, start=1):
            cell = ws_audit.cell(row=h_row, column=col_idx, value=h)
            cell.font = font_tbl_header
            cell.fill = dark_header_fill
            cell.alignment = align_center
            cell.border = border_cell

        ws_audit.freeze_panes = "A6"
        ws_audit.auto_filter.ref = f"A5:{get_column_letter(len(audit_headers))}{h_row + max(len(all_audit_logs), 1)}"

        for l_idx, log in enumerate(all_audit_logs, start=6):
            fill = zebra_even_fill if l_idx % 2 == 0 else zebra_odd_fill
            date_str = log.created_at.strftime("%Y-%m-%d") if log.created_at else "—"
            time_str = log.created_at.strftime("%I:%M:%S %p") if log.created_at else "—"

            row_data = [
                f"AUD-{log.id:05d}",
                date_str,
                time_str,
                log.action,
                log.actor_type,
                log.actor_name,
                log.target or "—",
                log.details or "—",
                log.ip_address or "127.0.0.1"
            ]

            for c_idx, val in enumerate(row_data, start=1):
                cell = ws_audit.cell(row=l_idx, column=c_idx, value=val)
                cell.font = font_regular
                cell.fill = fill
                cell.border = border_cell

                if c_idx == 1:
                    cell.alignment = align_center
                    cell.font = font_bold
                elif c_idx in (2, 3):
                    cell.alignment = align_center
                elif c_idx == 4:
                    cell.alignment = align_center
                    cell.font = font_bold
                elif c_idx in (5, 9):
                    cell.alignment = align_center
                else:
                    cell.alignment = align_left

        _autofit_columns(ws_audit, min_width=12, max_width=45)

    # -------------------------------------------------------------
    # SHEET 4: Daily Queue Trends (Daily Distribution)
    # -------------------------------------------------------------
    if report_type in ("all", "analytics"):
        ws_trends = wb.create_sheet(title="Daily Queue Trends")
        _apply_gridlines(ws_trends)

        ws_trends["A1"] = "BULACAN STATE UNIVERSITY — BUSTOS CAMPUS"
        ws_trends["A1"].font = font_univ_title
        ws_trends["A2"] = "QRESERVE DAILY QUEUE VOLUME, SERVICE & REVENUE TRENDS"
        ws_trends["A2"].font = font_sys_sub
        ws_trends["A3"] = f"Generated: {now_str} (PST) | System: QRESERVE"
        ws_trends["A3"].font = font_meta

        trend_headers = [
            "Date", "Day of Week", "Total Requests", "Completed", "In Processing",
            "Student Volume", "Guest Volume", "Daily Revenue (PHP)"
        ]

        th_row = 5
        for col_idx, h in enumerate(trend_headers, start=1):
            cell = ws_trends.cell(row=th_row, column=col_idx, value=h)
            cell.font = font_tbl_header
            cell.fill = crimson_header_fill
            cell.alignment = align_center
            cell.border = border_cell

        ws_trends.freeze_panes = "A6"

        daily_data = defaultdict(lambda: {
            "date_obj": None,
            "total": 0,
            "completed": 0,
            "processing": 0,
            "student": 0,
            "guest": 0,
            "revenue": 0
        })

        for r in all_requests:
            if r.created_at:
                d_key = r.created_at.strftime("%Y-%m-%d")
                d_dict = daily_data[d_key]
                d_dict["date_obj"] = r.created_at
                d_dict["total"] += 1
                if r.status == "Completed":
                    d_dict["completed"] += 1
                elif r.status in ("Processing", "Ready for pickup"):
                    d_dict["processing"] += 1
                if r.student_id:
                    d_dict["student"] += 1
                else:
                    d_dict["guest"] += 1
                if r.is_paid:
                    d_dict["revenue"] += r.total_price

        sorted_trend_days = sorted(daily_data.keys(), reverse=True)
        ws_trends.auto_filter.ref = f"A5:{get_column_letter(len(trend_headers))}{th_row + max(len(sorted_trend_days), 1)}"

        for t_idx, d_key in enumerate(sorted_trend_days, start=6):
            fill = zebra_even_fill if t_idx % 2 == 0 else zebra_odd_fill
            info = daily_data[d_key]
            day_name = info["date_obj"].strftime("%A") if info["date_obj"] else "—"

            row_data = [
                d_key,
                day_name,
                info["total"],
                info["completed"],
                info["processing"],
                info["student"],
                info["guest"],
                float(info["revenue"])
            ]

            for c_idx, val in enumerate(row_data, start=1):
                cell = ws_trends.cell(row=t_idx, column=c_idx, value=val)
                cell.font = font_regular
                cell.fill = fill
                cell.border = border_cell

                if c_idx in (1, 2):
                    cell.alignment = align_center
                    cell.font = font_bold if c_idx == 1 else font_regular
                elif c_idx == 8:
                    cell.alignment = align_right
                    cell.number_format = '"PHP "#,##0.00'
                    cell.font = font_bold
                else:
                    cell.alignment = align_right

        _autofit_columns(ws_trends, min_width=14, max_width=30)

    # Save to BytesIO stream
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

