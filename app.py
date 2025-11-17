import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

# -------------------------------------------------
# KONFIGURACIJA
# -------------------------------------------------
app = Flask(__name__)

# DATABASE_URL bo nastavljen v oblaku (PostgreSQL).
# Lokalno, če ni nastavljena, uporabimo SQLite datoteko.
db_url = os.getenv("DATABASE_URL", "sqlite:///tasks.db")

# Nekateri providerji uporabljajo "postgres://", SQLAlchemy hoče "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# -------------------------------------------------
# MODEL: naloga
# -------------------------------------------------
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)        # naslov naloge
    task_type = db.Column(db.String(50), nullable=False)     # npr. "naloga", "kolokvij", "kviz"
    subject = db.Column(db.String(100), nullable=False)      # predmet (Matematika, Fizika ...)
    due_date = db.Column(db.Date, nullable=False)            # rok (datum)
    description = db.Column(db.Text)                         # opis, link na ucilnice
    is_done = db.Column(db.Boolean, default=False)           # ali je opravljena

    def is_overdue(self):
        return (not self.is_done) and self.due_date < datetime.today().date()

    def is_soon(self):
        # "kmalu" = danes ali jutri
        today = datetime.today().date()
        delta = (self.due_date - today).days
        return (not self.is_done) and (0 <= delta <= 1)


# -------------------------------------------------
# INITIALIZACIJA BAZE
# -------------------------------------------------
with app.app_context():
    db.create_all()


# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.route("/")
def index():
    show_done = request.args.get("show_done", "0") == "1"

    query = Task.query.order_by(Task.due_date.asc())
    if not show_done:
        query = query.filter(Task.is_done.is_(False))

    tasks = query.all()
    return render_template("index.html", tasks=tasks, show_done=show_done)


@app.route("/add", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        title = request.form["title"].strip()
        task_type = request.form["task_type"].strip()
        subject = request.form["subject"].strip()
        due_date_str = request.form["due_date"]
        description = request.form.get("description", "").strip()

        # HTML <input type="date"> vrne "YYYY-MM-DD"
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()

        task = Task(
            title=title,
            task_type=task_type,
            subject=subject,
            due_date=due_date,
            description=description,
        )
        db.session.add(task)
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("add_task.html")


@app.route("/done/<int:task_id>")
def mark_done(task_id):
    task = Task.query.get_or_404(task_id)
    task.is_done = True
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/undo/<int:task_id>")
def mark_undone(task_id):
    task = Task.query.get_or_404(task_id)
    task.is_done = False
    db.session.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Lokalni development server
    app.run(debug=True)
