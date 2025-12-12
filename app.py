import os
import string
import secrets
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

#Create Flask app
app = Flask(__name__)
app.secret_key = "final_4320"

#Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "reservations.db")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

#Seat pricing matrix (12 rows x 4 seats)
def get_cost_matrix():
    return [[100, 75, 50, 100] for row in range(12)]

#Check if seat numbers are valid
def valid_seat(row_1, col_1):
    return 1 <= row_1 <= 12 and 1 <= col_1 <= 4

#Create a random eTicket number
def make_eticket_number():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))

#Reservation table model
class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    passengerName = db.Column(db.Text, nullable=False)
    seatRow = db.Column(db.Integer, nullable=False)
    seatColumn = db.Column(db.Integer, nullable=False)
    eTicketNumber = db.Column(db.Text, nullable=False)
    created = db.Column(db.DateTime, nullable=False)

#Admin table model
class Admin(db.Model):
    __tablename__ = "admins"

    username = db.Column(db.Text, primary_key=True)
    password = db.Column(db.Text, nullable=False)

#Check if a seat is already taken
def seat_is_taken(row_1, col_1):
    return Reservation.query.filter_by(
        seatRow=row_1,
        seatColumn=col_1
    ).first() is not None

#Build seating chart from database
def build_seating_chart():
    chart = []
    for r in range(1, 13):
        row_cells = []
        for c in range(1, 5):
            res = Reservation.query.filter_by(seatRow=r, seatColumn=c).first()
            if res:
                row_cells.append({"taken": True, "code": res.eTicketNumber})
            else:
                row_cells.append({"taken": False, "code": ""})
        chart.append(row_cells)
    return chart

#Calculate total sales for all reservations
def total_sales():
    prices = get_cost_matrix()
    total = 0
    for res in Reservation.query.all():
        total += prices[res.seatRow - 1][res.seatColumn - 1]
    return total

#Check if admin is logged in
def is_admin_logged_in():
    return session.get("admin_logged_in") is True

#Main menu page
@app.route("/")
def menu():
    return render_template("menu.html")

#Reserve seat page
@app.route("/reserve", methods=["GET", "POST"])
def reserve():
    prices = get_cost_matrix()

    if request.method == "POST":
        passengerName = (request.form.get("passengerName") or "").strip()

        try:
            seatRow = int(request.form.get("seatRow") or "0")
            seatColumn = int(request.form.get("seatColumn") or "0")
        except ValueError:
            seatRow, seatColumn = 0, 0

        if not passengerName:
            flash("Passenger name is required.")
            return redirect(url_for("reserve"))

        if not valid_seat(seatRow, seatColumn):
            flash("Invalid seat selection.")
            return redirect(url_for("reserve"))

        if seat_is_taken(seatRow, seatColumn):
            flash("Seat already reserved.")
            return redirect(url_for("reserve"))

        eTicketNumber = make_eticket_number()
        while Reservation.query.filter_by(eTicketNumber=eTicketNumber).first():
            eTicketNumber = make_eticket_number()

        reservation = Reservation(
            passengerName=passengerName,
            seatRow=seatRow,
            seatColumn=seatColumn,
            eTicketNumber=eTicketNumber,
            created=datetime.now()
        )

        db.session.add(reservation)
        db.session.commit()

        flash("Reservation successful. eTicket: " + eTicketNumber)
        return redirect(url_for("reserve"))

    return render_template(
        "reserve.html",
        chart=build_seating_chart(),
        prices=prices
    )

#Admin login page
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        admin = Admin.query.filter_by(username=username).first()
        if not admin or admin.password != password:
            flash("Invalid admin login.")
            return redirect(url_for("admin_login"))

        session["admin_logged_in"] = True
        return redirect(url_for("admin_portal"))

    return render_template("admin_login.html")

#Admin dashboard
@app.route("/admin")
def admin_portal():
    if not is_admin_logged_in():
        return redirect(url_for("admin_login"))

    reservations = Reservation.query.order_by(
        Reservation.seatRow,
        Reservation.seatColumn
    ).all()

    return render_template(
        "admin.html",
        chart=build_seating_chart(),
        prices=get_cost_matrix(),
        sales=total_sales(),
        reservations=reservations
    )

#Delete reservation
@app.route("/admin/delete/<int:rid>", methods=["POST"])
def admin_delete(rid):
    if not is_admin_logged_in():
        return redirect(url_for("admin_login"))

    res = Reservation.query.get(rid)
    if res:
        db.session.delete(res)
        db.session.commit()
        flash("Reservation deleted.")

    return redirect(url_for("admin_portal"))

#Admin logout
@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("menu"))

#Start the app
if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("reservations.db not found")
    app.run(debug=True)
