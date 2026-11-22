import calendar
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import model


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
MONTH_NAMES = list(calendar.month_name)


def render(request: Request, template: str, context: dict, status_code: int = 200):
    return templates.TemplateResponse(
        request, template, context, status_code=status_code
    )


def month_context(year: int, month: int) -> dict:
    return {
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES[month],
        "month_value": f"{year:04d}-{month:02d}",
        "days_in_month": calendar.monthrange(year, month)[1],
    }


def parse_month(month_value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(month_value, "%Y-%m")
    except ValueError:
        return 2025, 12
    return parsed.year, parsed.month


def teacher_required(request: Request) -> bool:
    return request.session.get("role") == "teacher"


def student_required(request: Request) -> bool:
    return request.session.get("role") == "student"


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    role = request.session.get("role")
    if role == "teacher":
        return RedirectResponse("/teacher/dashboard", status_code=303)
    if role == "student":
        return RedirectResponse("/student/dashboard", status_code=303)
    return render(request, "index.html", {})


@router.get("/teacher/login", response_class=HTMLResponse)
def teacher_login_page(request: Request):
    if teacher_required(request):
        return RedirectResponse("/teacher/dashboard", status_code=303)
    return render(request, "login.html", {"portal": "teacher", "error": ""})


@router.post("/teacher/login")
def teacher_login(
    request: Request,
    username: str = Form(),
    password: str = Form(),
):
    teacher = model.authenticate_teacher(username, password)
    if teacher is None:
        return render(
            request,
            "login.html",
            {"portal": "teacher", "error": "Username or password is incorrect."},
            status_code=401,
        )
    request.session.clear()
    request.session.update(
        {"role": "teacher", "user_id": teacher["id"], "name": teacher["name"]}
    )
    return RedirectResponse("/teacher/dashboard", status_code=303)


@router.get("/student/login", response_class=HTMLResponse)
def student_login_page(request: Request):
    if student_required(request):
        return RedirectResponse("/student/dashboard", status_code=303)
    return render(request, "login.html", {"portal": "student", "error": ""})


@router.post("/student/login")
def student_login(
    request: Request,
    roll_no: str = Form(),
    password: str = Form(),
):
    student = model.authenticate_student(roll_no, password)
    if student is None:
        return render(
            request,
            "login.html",
            {"portal": "student", "error": "Roll number or password is incorrect."},
            status_code=401,
        )
    request.session.clear()
    request.session.update(
        {
            "role": "student",
            "user_id": student["id"],
            "name": student["name"],
        }
    )
    return RedirectResponse("/student/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@router.get("/teacher/dashboard", response_class=HTMLResponse)
def teacher_dashboard(
    request: Request,
    month: str = "2025-12",
    saved: str = "",
    attendance_date: str = "",
    weekend: str = "",
    subject: str = "",
):
    if not teacher_required(request):
        return RedirectResponse("/teacher/login", status_code=303)
    subjects = model.get_teacher_subjects(request.session["user_id"])
    if subject and subject not in subjects:
        return RedirectResponse("/teacher/dashboard", status_code=303)
    if not subject:
        return render(
            request,
            "teacher_dashboard.html",
            {
                "subjects": subjects,
                "selected_subject": "",
                "saved": False,
            },
        )

    year, month_number = parse_month(month)
    students = model.get_students()
    month_data = model.get_month_attendance(year, month_number, subject)
    selected_date_value = date(year, month_number, 1)
    while selected_date_value.weekday() >= 5:
        selected_date_value = date.fromordinal(selected_date_value.toordinal() + 1)
    selected_date = selected_date_value.isoformat()
    weekend_warning = weekend == "1"
    try:
        requested_date = date.fromisoformat(attendance_date)
    except ValueError:
        requested_date = None
    if requested_date and requested_date.weekday() >= 5:
        weekend_warning = True
    elif requested_date and (requested_date.year, requested_date.month) == (
        year, month_number
    ):
        selected_date = requested_date.isoformat()
    attendance_for_day = model.get_attendance_for_date(selected_date, subject)
    daily = []
    working_days = []
    for day_number in range(1, calendar.monthrange(year, month_number)[1] + 1):
        current_day = date(year, month_number, day_number)
        current_date = current_day.isoformat()
        is_weekend = current_day.weekday() >= 5
        if is_weekend:
            daily.append(
                {
                    "day": day_number,
                    "present": 0,
                    "absent": 0,
                    "weekend": True,
                }
            )
            continue
        working_days.append(
            {
                "value": current_date,
                "label": current_day.strftime("%a, %b %d"),
            }
        )
        counts = month_data.get(current_date, {"present": 0, "absent": 0})
        daily.append(
            {
                "day": day_number,
                "present": counts["present"],
                "absent": counts["absent"],
                "weekend": False,
            }
        )
    return render(
        request,
        "teacher_dashboard.html",
        {
            **month_context(year, month_number),
            "students": students,
            "attendance_for_day": attendance_for_day,
            "selected_date": selected_date,
            "daily": daily,
            "working_days": working_days,
            "saved": saved == "1",
            "weekend_warning": weekend_warning,
            "student_count": len(students),
            "subjects": subjects,
            "selected_subject": subject,
        },
    )


@router.post("/teacher/attendance")
async def update_attendance(request: Request):
    if not teacher_required(request):
        return RedirectResponse("/teacher/login", status_code=303)
    form = await request.form()
    subject = str(form.get("subject", ""))
    subjects = model.get_teacher_subjects(request.session["user_id"])
    if subject not in subjects:
        return RedirectResponse("/teacher/dashboard", status_code=303)
    month = str(form.get("month", "2025-12"))
    year, month_number = parse_month(month)
    attendance_date = str(form.get("attendance_date", ""))
    try:
        parsed_date = date.fromisoformat(attendance_date)
    except ValueError:
        return RedirectResponse(
            f"/teacher/dashboard?subject={subject}&month={year:04d}-{month_number:02d}",
            status_code=303,
        )
    if (parsed_date.year, parsed_date.month) != (year, month_number):
        return RedirectResponse(
            f"/teacher/dashboard?subject={subject}&month={year:04d}-{month_number:02d}",
            status_code=303,
        )
    if parsed_date.weekday() >= 5:
        return RedirectResponse(
            f"/teacher/dashboard?subject={subject}&month={year:04d}-{month_number:02d}"
            "&weekend=1",
            status_code=303,
        )

    students = model.get_students()
    statuses = {}
    for student in students:
        status = str(form.get(f"status_{student['id']}", "absent"))
        statuses[student["id"]] = status if status in {"present", "absent"} else "absent"
    model.save_attendance(attendance_date, subject, statuses)
    return RedirectResponse(
        f"/teacher/dashboard?subject={subject}&month={year:04d}-{month_number:02d}"
        f"&attendance_date={attendance_date}&saved=1",
        status_code=303,
    )


@router.get("/student/dashboard", response_class=HTMLResponse)
def student_dashboard(
    request: Request, month: str = "2025-12", subject: str = ""
):
    if not student_required(request):
        return RedirectResponse("/student/login", status_code=303)
    subjects = model.get_subjects()
    if subject and subject not in subjects:
        return RedirectResponse("/student/dashboard", status_code=303)
    if not subject:
        student = model.get_student(request.session["user_id"])
        if student is None:
            request.session.clear()
            return RedirectResponse("/student/login", status_code=303)
        return render(
            request,
            "student_dashboard.html",
            {"student": student, "subjects": subjects, "selected_subject": ""},
        )

    year, month_number = parse_month(month)
    student = model.get_student(request.session["user_id"])
    if student is None:
        request.session.clear()
        return RedirectResponse("/student/login", status_code=303)
    attendance = model.get_student_month_attendance(
        student["id"], year, month_number, subject
    )
    days = []
    for day_number in range(1, calendar.monthrange(year, month_number)[1] + 1):
        current_date = date(year, month_number, day_number).isoformat()
        current_day = date(year, month_number, day_number)
        if current_day.weekday() >= 5:
            days.append(
                {"day": day_number, "date": current_date, "status": "weekend"}
            )
            continue
        days.append(
            {
                "day": day_number,
                "date": current_date,
                "status": attendance.get(current_date, "not marked"),
            }
        )
    total_marked = sum(value in {"present", "absent"} for value in attendance.values())
    present_count = sum(value == "present" for value in attendance.values())
    absent_count = sum(value == "absent" for value in attendance.values())
    attendance_rate = round(present_count * 100 / total_marked) if total_marked else 0
    return render(
        request,
        "student_dashboard.html",
        {
            **month_context(year, month_number),
            "student": student,
            "days": days,
            "present_count": present_count,
            "absent_count": absent_count,
            "total_marked": total_marked,
            "attendance_rate": attendance_rate,
            "subjects": subjects,
            "selected_subject": subject,
        },
    )
