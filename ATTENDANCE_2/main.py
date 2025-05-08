from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "secure_random_key"

DB_PATH = "final_attendance.db"
SUMMARY_DB = "overall_summary.db"
TIMETABLE_DB = "timetable.db"

LAB_SUBJECTS = ["CSS LAB", "SEPM LAB", "CCL LAB", "DAV LAB", "ML LAB", "MINI PROJECT"]

def get_db(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con

def init_timetable_db():
    con = get_db(TIMETABLE_DB)
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT,
            position INTEGER,
            subject TEXT
        )
    ''')
    # If empty, insert defaults
    cur.execute("SELECT COUNT(*) FROM timetable")
    if cur.fetchone()[0] == 0:
        defaults = [
            ("Monday",   1, "ML"), ("Monday",   2, "CSS"), ("Monday",   3, "IVP"), ("Monday",   4, "DAV"),
            ("Tuesday",  1, "CSS"),("Tuesday",  2, "IVP"),("Tuesday",  3, "SEPM LAB"),("Tuesday", 4, "CCL LAB"),
            ("Wednesday",1, "SEPM"),("Wednesday",2, "DAV"),("Wednesday",3, "CCL LAB"),
            ("-Wednesday",4, "IVP"),("Wednesday",5, "CSS"),("Wednesday",6,"MINI PROJECT"),
            ("Thursday", 1, "DAV"),("Thursday", 2, "ML"),("Thursday", 3, "DAV LAB"),("Thursday",4,"SEPM"),
            ("Friday",   1, "ML"),("Friday",   2, "SEPM"),("Friday",   3, "CSS LAB"),
            ("Friday",   4, "ML LAB"),("Friday",5,"MINI PROJECT")
        ]
        cur.executemany("INSERT INTO timetable(day,position,subject) VALUES (?,?,?)", defaults)
    con.commit()
    con.close()

def init_db():
    # attendance
    con = get_db(DB_PATH)
    con.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            date TEXT
        )
    ''')
    con.commit()
    con.close()
    # summary
    con = get_db(SUMMARY_DB)
    con.execute('''
        CREATE TABLE IF NOT EXISTS summary (
            date TEXT PRIMARY KEY,
            attended INTEGER,
            total INTEGER,
            percentage REAL
        )
    ''')
    con.commit()
    con.close()
    # timetable
    init_timetable_db()

def load_timetable():
    con = get_db(TIMETABLE_DB)
    cur = con.cursor()
    cur.execute("SELECT day, subject FROM timetable ORDER BY day, position")
    rows = cur.fetchall()
    con.close()
    table = {}
    for r in rows:
        table.setdefault(r["day"], []).append(r["subject"])
    return table

@app.route("/")
def index():
    timetable = load_timetable()
    weekday = datetime.today().strftime('%A')
    today = str(date.today())
    subjects_today = timetable.get(weekday, [])

    # marked subjects
    con = get_db(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT subject FROM attendance WHERE date=?", (today,))
    marked = [r["subject"] for r in cur.fetchall()]
    con.close()

    total = sum(2 if s in LAB_SUBJECTS else 1 for s in subjects_today)
    attended = sum(2 if s in LAB_SUBJECTS else 1 for s in set(marked))
    percent = round(attended/total*100,2) if total else 0

    # history
    con = get_db(SUMMARY_DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM summary ORDER BY date DESC")
    history = cur.fetchall()
    cur.execute("SELECT AVG(percentage) FROM summary")
    avg = cur.fetchone()[0]
    overall = round(avg,2) if avg else 0
    con.close()

    return render_template("index.html",
        timetable=timetable, today=weekday,
        marked=marked, total=total, attended=attended, percent_today=percent,
        overall_percent=overall, history=history
    )

@app.route("/mark", methods=["POST"])
def mark():
    subject = request.form["subject"]
    today = str(date.today())
    con = get_db(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT 1 FROM attendance WHERE subject=? AND date=?", (subject,today))
    if not cur.fetchone():
        count = 2 if subject in LAB_SUBJECTS else 1
        for _ in range(count):
            cur.execute("INSERT INTO attendance(subject,date) VALUES(?,?)",(subject,today))
        flash(f"{subject} marked.")
    else:
        flash(f"{subject} already marked.")
    con.commit(); con.close()
    return redirect(url_for("index"))

@app.route("/save_day", methods=["POST"])
def save_day():
    today = str(date.today()); weekday = datetime.today().strftime('%A')
    subjects = load_timetable().get(weekday, [])
    con = get_db(DB_PATH); cur = con.cursor()
    cur.execute("SELECT subject FROM attendance WHERE date=?", (today,))
    marked = [r["subject"] for r in cur.fetchall()]
    total = sum(2 if s in LAB_SUBJECTS else 1 for s in subjects)
    attended = sum(2 if s in LAB_SUBJECTS else 1 for s in set(marked))
    percent = round(attended/total*100,2) if total else 0
    con.close()

    con = get_db(SUMMARY_DB); cur = con.cursor()
    try:
        cur.execute("INSERT INTO summary(date,attended,total,percentage) VALUES(?,?,?,?)",
                    (today,attended,total,percent))
        flash("Day summary saved.")
    except sqlite3.IntegrityError:
        flash("Summary already exists.")
    con.commit(); con.close()
    return redirect(url_for("index"))

@app.route("/reset", methods=["POST"])
def reset():
    con = get_db(DB_PATH); con.execute("DELETE FROM attendance"); con.commit(); con.close()
    flash("Today's attendance reset.")
    return redirect(url_for("index"))

@app.route("/reset_summary", methods=["POST"])
def reset_summary():
    con = get_db(SUMMARY_DB); con.execute("DELETE FROM summary"); con.commit(); con.close()
    flash("Summary history reset.")
    return redirect(url_for("index"))

@app.route("/attended")
def attended():
    con = get_db(DB_PATH); cur = con.cursor()
    cur.execute("SELECT subject,date FROM attendance ORDER BY date DESC")
    records = cur.fetchall(); con.close()
    return render_template("attended.html", records=records)

@app.route("/summary")
def summary():
    con = get_db(SUMMARY_DB); cur = con.cursor()
    cur.execute("SELECT * FROM summary ORDER BY date DESC")
    rows = cur.fetchall()
    cur.execute("SELECT AVG(percentage) FROM summary")
    avg = cur.fetchone()[0]
    overall = round(avg,2) if avg else 0
    con.close()
    return render_template("summary.html", summary=rows, overall=overall)

# --- Admin routes ---

@app.route("/admin")
def admin():
    con = get_db(TIMETABLE_DB); cur = con.cursor()
    cur.execute("SELECT * FROM timetable ORDER BY day, position")
    entries = cur.fetchall(); con.close()
    return render_template("admin.html", entries=entries)

@app.route("/admin/add", methods=["POST"])
def admin_add():
    day = request.form["day"]
    position = int(request.form["position"])
    subject = request.form["subject"]
    con = get_db(TIMETABLE_DB)
    con.execute("INSERT INTO timetable(day,position,subject) VALUES(?,?,?)",
                (day,position,subject))
    con.commit(); con.close()
    flash("Entry added.")
    return redirect(url_for("admin"))

@app.route("/admin/edit/<int:id>", methods=["POST"])
def admin_edit(id):
    day = request.form["day"]
    position = int(request.form["position"])
    subject = request.form["subject"]
    con = get_db(TIMETABLE_DB)
    con.execute("UPDATE timetable SET day=?,position=?,subject=? WHERE id=?",
                (day,position,subject,id))
    con.commit(); con.close()
    flash("Entry updated.")
    return redirect(url_for("admin"))

@app.route("/admin/delete/<int:id>", methods=["POST"])
def admin_delete(id):
    con = get_db(TIMETABLE_DB)
    con.execute("DELETE FROM timetable WHERE id=?", (id,))
    con.commit(); con.close()
    flash("Entry deleted.")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
@app.route("/admin/edit/<int:id>", methods=["POST"])
def admin_edit(id):
    day = request.form["day"]
    position = int(request.form["position"])
    subject = request.form["subject"]
    con = get_db(TIMETABLE_DB)
    con.execute("UPDATE timetable SET day=?, position=?, subject=? WHERE id=?",
                (day, position, subject, id))
    con.commit()
    con.close()
    flash("Entry updated.")
    return redirect(url_for("admin"))

@app.route("/admin/delete/<int:id>", methods=["POST"])
def admin_delete(id):
    con = get_db(TIMETABLE_DB)
    con.execute("DELETE FROM timetable WHERE id=?", (id,))
    con.commit()
    con.close()
    flash("Entry deleted.")
    return redirect(url_for("admin"))
