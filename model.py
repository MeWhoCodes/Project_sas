from contextlib import closing
from datetime import date, timedelta
import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "attendance.db"
SUBJECTS = ("MAWD", "OOPS", "DAA")
SAMPLE_TEACHERS = (
    ("Hiramb Mishra", "hiramb", "hirambmishra", ("MAWD",)),
    ("Sarada Samantra", "sarada", "saradasamantra", ("OOPS", "DAA")),
)
SAMPLE_STUDENTS = (
    ("Devansh Sharma", "25imai003", "i"),
    ("Purujit Sharma", "25imds003", "3"),
    ("Kartikey Garg", "25imai005", "p"),
    ("Nehal Yadav", "25imai006", "5"),
    ("Akshata Choudhary", "25imds001", "v"),
    ("Tanishq Kuri", "25imai004", "p"),
    ("Rishab Bhawsingka", "25imai007", "8"),
    ("Aryan Kumawat", "25imds002", "o"),
    ("Zaid Bagwan", "25imai001", "k"),
    ("Priyal Agarwal", "25imai011", "g"),
)
LEGACY_SAMPLE_ROLLS = (
    "2025001",
    "2025002",
    "2025003",
    "2025004",
    "2025005",
    "2025006",
    "2025007",
    "2025008",
)


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}:{digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    salt_hex, digest_hex = stored_hash.split(":", maxsplit=1)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200_000
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _create_attendance_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            subject TEXT NOT NULL REFERENCES subjects(name),
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('present', 'absent')),
            UNIQUE (student_id, subject, attendance_date)
        )
        """
    )


def _seed_demo_attendance(connection: sqlite3.Connection) -> None:
    students = connection.execute(
        "SELECT id, roll_no FROM students WHERE roll_no IN "
        f"({','.join('?' for _ in SAMPLE_STUDENTS)}) ORDER BY roll_no",
        tuple(student[1] for student in SAMPLE_STUDENTS),
    ).fetchall()
    start = date(2025, 12, 1)
    records = []
    for day_offset in range(31):
        current_day = start + timedelta(days=day_offset)
        if current_day.weekday() >= 5:
            continue
        for student_index, student in enumerate(students):
            for subject_index, subject in enumerate(SUBJECTS):
                present = (
                    day_offset * 3 + student_index * 5 + day_offset // 4 + subject_index
                ) % 7 != 0
                records.append(
                    (
                        student["id"],
                        subject,
                        current_day.isoformat(),
                        "present" if present else "absent",
                    )
                )
    connection.executemany(
        """
        INSERT OR IGNORE INTO attendance
            (student_id, subject, attendance_date, status)
        VALUES (?, ?, ?, ?)
        """,
        records,
    )


def initialize_database() -> None:
    with closing(_connect()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS subjects (
                name TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS teacher_subjects (
                teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
                subject TEXT NOT NULL REFERENCES subjects(name),
                PRIMARY KEY (teacher_id, subject)
            );
            """
        )

        teacher_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(teachers)")
        }
        if "name" not in teacher_columns:
            connection.execute(
                "ALTER TABLE teachers ADD COLUMN name TEXT NOT NULL DEFAULT ''"
            )

        connection.executemany(
            "INSERT OR IGNORE INTO subjects (name) VALUES (?)",
            [(subject,) for subject in SUBJECTS],
        )

        # Add the subject key while retaining legacy attendance as MAWD records.
        attendance_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'attendance'"
        ).fetchone()
        if attendance_exists:
            attendance_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(attendance)")
            }
            if "subject" not in attendance_columns:
                connection.execute("ALTER TABLE attendance RENAME TO attendance_legacy")
                _create_attendance_table(connection)
                connection.execute(
                    """
                    INSERT INTO attendance
                        (student_id, subject, attendance_date, status)
                    SELECT student_id, 'MAWD', attendance_date, status
                    FROM attendance_legacy
                    """
                )
                connection.execute("DROP TABLE attendance_legacy")
        else:
            _create_attendance_table(connection)

        legacy_teacher = connection.execute(
            "SELECT password_hash FROM teachers WHERE username = ?", ("teacher",)
        ).fetchone()
        if legacy_teacher and _verify_password("teacher123", legacy_teacher["password_hash"]):
            connection.execute("DELETE FROM teachers WHERE username = ?", ("teacher",))

        for name, username, password, subjects in SAMPLE_TEACHERS:
            teacher = connection.execute(
                "SELECT id, name FROM teachers WHERE username = ?", (username,)
            ).fetchone()
            if teacher is None:
                cursor = connection.execute(
                    "INSERT INTO teachers (username, name, password_hash) "
                    "VALUES (?, ?, ?)",
                    (username, name, _hash_password(password)),
                )
                teacher_id = cursor.lastrowid
            else:
                teacher_id = teacher["id"]
                if not teacher["name"]:
                    connection.execute(
                        "UPDATE teachers SET name = ? WHERE id = ?", (name, teacher_id)
                    )
            connection.executemany(
                "INSERT OR IGNORE INTO teacher_subjects (teacher_id, subject) "
                "VALUES (?, ?)",
                [(teacher_id, subject) for subject in subjects],
            )

        for name, roll_no, suffix in SAMPLE_STUDENTS:
            student = connection.execute(
                "SELECT id FROM students WHERE roll_no = ?", (roll_no,)
            ).fetchone()
            if student is None:
                connection.execute(
                    "INSERT INTO students (roll_no, name, password_hash) "
                    "VALUES (?, ?, ?)",
                    (roll_no, name, _hash_password(roll_no + suffix)),
                )
            else:
                connection.execute(
                    "UPDATE students SET name = ? WHERE roll_no = ?", (name, roll_no)
                )

        for old_roll in LEGACY_SAMPLE_ROLLS:
            connection.execute("DELETE FROM students WHERE roll_no = ?", (old_roll,))

        connection.execute(
            "DELETE FROM attendance "
            "WHERE strftime('%w', attendance_date) IN ('0', '6')"
        )
        _seed_demo_attendance(connection)
        connection.commit()


def authenticate_teacher(username: str, password: str) -> sqlite3.Row | None:
    with closing(_connect()) as connection:
        teacher = connection.execute(
            "SELECT id, username, name, password_hash FROM teachers WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    if teacher and _verify_password(password, teacher["password_hash"]):
        return teacher
    return None


def authenticate_student(roll_no: str, password: str) -> sqlite3.Row | None:
    with closing(_connect()) as connection:
        student = connection.execute(
            "SELECT id, roll_no, name, password_hash FROM students WHERE roll_no = ?",
            (roll_no.strip().lower(),),
        ).fetchone()
    if student and _verify_password(password, student["password_hash"]):
        return student
    return None


def get_subjects() -> list[str]:
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT name FROM subjects ORDER BY name").fetchall()
    order = {subject: index for index, subject in enumerate(SUBJECTS)}
    return sorted((row["name"] for row in rows), key=order.get)


def get_teacher_subjects(teacher_id: int) -> list[str]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT subject FROM teacher_subjects WHERE teacher_id = ?",
            (teacher_id,),
        ).fetchall()
    order = {subject: index for index, subject in enumerate(SUBJECTS)}
    return sorted((row["subject"] for row in rows), key=order.get)


def get_students() -> list[sqlite3.Row]:
    with closing(_connect()) as connection:
        return connection.execute(
            "SELECT id, roll_no, name FROM students ORDER BY roll_no"
        ).fetchall()


def get_student(student_id: int) -> sqlite3.Row | None:
    with closing(_connect()) as connection:
        return connection.execute(
            "SELECT id, roll_no, name FROM students WHERE id = ?", (student_id,)
        ).fetchone()


def get_attendance_for_date(attendance_date: str, subject: str) -> dict[int, str]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT student_id, status FROM attendance
            WHERE attendance_date = ? AND subject = ?
            """,
            (attendance_date, subject),
        ).fetchall()
    return {row["student_id"]: row["status"] for row in rows}


def save_attendance(
    attendance_date: str, subject: str, statuses: dict[int, str]
) -> None:
    parsed_date = date.fromisoformat(attendance_date)
    if parsed_date.weekday() >= 5:
        raise ValueError("Attendance cannot be marked on Saturday or Sunday.")
    with closing(_connect()) as connection:
        connection.executemany(
            """
            INSERT INTO attendance (student_id, subject, attendance_date, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id, subject, attendance_date)
            DO UPDATE SET status = excluded.status
            """,
            [
                (student_id, subject, attendance_date, status)
                for student_id, status in statuses.items()
            ],
        )
        connection.commit()


def get_month_attendance(
    year: int, month: int, subject: str
) -> dict[str, dict[str, int]]:
    month_prefix = f"{year:04d}-{month:02d}-"
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT attendance_date, status, COUNT(*) AS count
            FROM attendance
            WHERE attendance_date LIKE ? AND subject = ?
                AND strftime('%w', attendance_date) NOT IN ('0', '6')
            GROUP BY attendance_date, status
            ORDER BY attendance_date
            """,
            (f"{month_prefix}%", subject),
        ).fetchall()
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        result.setdefault(row["attendance_date"], {"present": 0, "absent": 0})
        result[row["attendance_date"]][row["status"]] = row["count"]
    return result


def get_student_month_attendance(
    student_id: int, year: int, month: int, subject: str
) -> dict[str, str]:
    month_prefix = f"{year:04d}-{month:02d}-"
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT attendance_date, status FROM attendance
            WHERE student_id = ? AND attendance_date LIKE ? AND subject = ?
                AND strftime('%w', attendance_date) NOT IN ('0', '6')
            ORDER BY attendance_date
            """,
            (student_id, f"{month_prefix}%", subject),
        ).fetchall()
    return {row["attendance_date"]: row["status"] for row in rows}
