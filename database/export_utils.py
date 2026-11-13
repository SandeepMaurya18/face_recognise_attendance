import io
from typing import Optional
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from database.models import get_attendance_logs


def get_filtered_dataframe(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    user_id: Optional[str] = None,
    punch_type: Optional[str] = None
) -> pd.DataFrame:
    """Fetch attendance records into a clean pandas DataFrame."""
    logs, _ = get_attendance_logs(
        start_date=start_date,
        end_date=end_date,
        department=department,
        user_id=user_id,
        punch_type=punch_type,
        limit=10000,
        offset=0
    )

    if not logs:
        return pd.DataFrame(columns=[
            "Record ID", "User ID", "Full Name", "Department", "Date",
            "Time", "Punch Type", "Status", "Confidence", "Notes"
        ])

    data = []
    for log in logs:
        data.append({
            "Record ID": log["id"],
            "User ID": log["user_id"],
            "Full Name": log["name"],
            "Department": log["department"],
            "Date": log["date"],
            "Time": log["time"],
            "Punch Type": log["punch_type"],
            "Status": log["status"],
            "Confidence": f"{round(log['confidence'] * 100, 1)}%",
            "Notes": log.get("notes") or ""
        })

    return pd.DataFrame(data)


def export_to_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    user_id: Optional[str] = None,
    punch_type: Optional[str] = None
) -> io.BytesIO:
    """Generate attendance CSV stream."""
    df = get_filtered_dataframe(start_date, end_date, department, user_id, punch_type)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)
    return buffer


def export_to_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    user_id: Optional[str] = None,
    punch_type: Optional[str] = None
) -> io.BytesIO:
    """Generate a styled Excel workbook."""
    df = get_filtered_dataframe(start_date, end_date, department, user_id, punch_type)
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance Log")
        workbook = writer.book
        worksheet = writer.sheets["Attendance Log"]

        # Styling
        header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        regular_font = Font(name="Calibri", size=10)
        thin_border = Border(
            left=Side(style="thin", color="E5E7EB"),
            right=Side(style="thin", color="E5E7EB"),
            top=Side(style="thin", color="E5E7EB"),
            bottom=Side(style="thin", color="E5E7EB")
        )

        for col_num, col_name in enumerate(df.columns, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, min_col=1, max_col=len(df.columns)):
            for cell in row:
                cell.font = regular_font
                cell.border = thin_border
                if cell.column in (1, 2, 5, 6, 7, 8, 9):
                    cell.alignment = Alignment(horizontal="center")

        # Auto-adjust column widths
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer.seek(0)
    return buffer
