# Student Attendance System

A small teacher/student attendance portal built with FastAPI, Jinja templates, SQLite, HTML, CSS, and vanilla JavaScript.

## Run locally

From this folder, install dependencies and start the development server:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). 
## Demo teacher accounts

- Hiramb Mishra: username `hiramb`, password `hirambmishra` (MAWD)
- Sarada Samantra: username `sarada`, password `saradasamantra` (OOPS and DAA)

## Demo student accounts

Each student password is their roll number followed by one random character:

| Student | Roll number | Password |
|---|---|---|
| Devansh Sharma | `25imai003` | `25imai003i` |
| Purujit Sharma | `25imds003` | `25imds0033` |
| Kartikey Garg | `25imai005` | `25imai005p` |
| Nehal Yadav | `25imai006` | `25imai0065` |
| Akshata Choudhary | `25imds001` | `25imds001v` |
| Tanishq Kuri | `25imai004` | `25imai004p` |
| Rishab Bhawsingka | `25imai007` | `25imai0078` |
| Aryan Kumawat | `25imds002` | `25imds002o` |
| Zaid Bagwan | `25imai001` | `25imai001k` |
| Priyal Agarwal | `25imai011` | `25imai011g` |

Students first choose a subject, then view its month-by-month calendar and attendance rate. Teachers see only their assigned subjects; they can mark attendance for each date and view that subject's daily chart.

Attendance is available on weekdays only. Saturdays and Sundays are shown as weekends on student calendars and are not included in attendance totals. Weekend attendance records already in the database are removed when the app starts.
