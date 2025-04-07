# app.py
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'hospital.db'

def get_db():
    return sqlite3.connect(DATABASE)

def initialize_db():
    if not os.path.exists(DATABASE):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            experience INTEGER NOT NULL,
            contact TEXT,
            available_slots INTEGER NOT NULL)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            contact TEXT)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS doctor_logins (
            doctor_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS patient_logins (
            patient_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS medical_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            description TEXT,
            file BLOB,
            upload_date TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT CHECK(status IN ('Pending', 'Confirmed', 'Completed')) NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')

        default_admin = ('admin', generate_password_hash('admin123'))
        cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)", default_admin)

        conn.commit()
        conn.close()

initialize_db()

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, specialization, experience FROM doctors")
    doctors = cursor.fetchall()
    conn.close()
    return render_template('index.html', doctors=doctors)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT doctor_id, password FROM doctor_logins WHERE username = ?", (username,))
        doc = cursor.fetchone()
        if doc and check_password_hash(doc[1], password):
            session['user_id'] = doc[0]
            session['username'] = username
            session['role'] = 'doctor'
            return redirect('/doctor')

        cursor.execute("SELECT patient_id, password FROM patient_logins WHERE username = ?", (username,))
        pat = cursor.fetchone()
        if pat and check_password_hash(pat[1], password):
            session['user_id'] = pat[0]
            session['username'] = username
            session['role'] = 'patient'
            return redirect('/user')

        conn.close()
        flash("Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/doctor', methods=['GET', 'POST'])
def doctor_dashboard():
    if 'role' in session and session['role'] == 'doctor':
        return render_template('doctor_dashboard.html')
    return redirect('/login')

@app.route('/doctor/view_patient', methods=['POST'])
def view_patient():
    patient_id = request.form['patient_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE id = ? OR name = ?", (patient_id, patient_id))
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        flash("Patient not found.")
        return redirect('/doctor')
    cursor.execute("SELECT id, description, upload_date FROM medical_records WHERE patient_id = ?", (patient[0],))
    records = cursor.fetchall()
    conn.close()
    return render_template('view_medical_history.html', patient=patient, records=records)

@app.route('/doctor/appointments')
def view_appointments():
    if 'role' in session and session['role'] == 'doctor':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM appointments WHERE doctor_id = ?", (session['user_id'],))
        appointments = cursor.fetchall()
        conn.close()
        return render_template('view_appointments.html', appointments=appointments)
    return redirect('/login')

@app.route('/user')
def user_dashboard():
    if 'role' in session and session['role'] == 'patient':
        return render_template('user_dashboard.html')
    return redirect('/login')

@app.route('/user/book', methods=['GET', 'POST'])
def book_appointment():
    conn = get_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        date = request.form['date']
        cursor.execute("INSERT INTO appointments (patient_id, doctor_id, date, status) VALUES (?, ?, ?, 'Pending')",
                       (session['user_id'], doctor_id, date))
        cursor.execute("UPDATE doctors SET available_slots = available_slots - 1 WHERE id = ?", (doctor_id,))
        conn.commit()
        conn.close()
        flash("Appointment booked successfully.")
        return redirect('/user')
    else:
        cursor.execute("SELECT id, name, specialization, available_slots FROM doctors WHERE available_slots > 0")
        doctors = cursor.fetchall()
        conn.close()
        return render_template('book_appointment.html', doctors=doctors)

@app.route('/user/history')
def user_history():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medical_records WHERE patient_id = ?", (session['user_id'],))
    records = cursor.fetchall()
    conn.close()
    return render_template('view_medical_history.html', records=records)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM admin WHERE username = ?", (username,))
        admin = cursor.fetchone()
        conn.close()
        if admin and check_password_hash(admin[1], password):
            session['admin'] = True
            return redirect('/admin/dashboard')
        else:
            flash("Invalid admin credentials")
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' in session:
        return render_template('admin_dashboard.html')
    return redirect('/admin')

@app.route('/admin/add_doctor_form')
def add_doctor_form():
    if 'admin' in session:
        return render_template('add_doctor.html')
    return redirect('/admin')

@app.route('/admin/add_patient_form')
def add_patient_form():
    if 'admin' in session:
        return render_template('add_patient.html')
    return redirect('/admin')

@app.route('/admin/add_doctor', methods=['POST'])
def add_doctor():
    if 'admin' in session:
        data = request.form
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO doctors (name, specialization, experience, contact, available_slots)
                    VALUES (?, ?, ?, ?, ?)
                """, (data['name'], data['specialization'], data['experience'], data['contact'], data['slots']))
                doctor_id = cursor.lastrowid
                password_hash = generate_password_hash(data['password'])
                cursor.execute("""
                    INSERT INTO doctor_logins (doctor_id, username, password)
                    VALUES (?, ?, ?)
                """, (doctor_id, data['username'], password_hash))
                flash("Doctor added successfully")
        except sqlite3.IntegrityError:
            flash("Username already exists or data invalid.")
        return redirect('/admin/dashboard')
    return redirect('/admin')

@app.route('/admin/add_patient', methods=['POST'])
def add_patient():
    if 'admin' in session:
        data = request.form
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO patients (name, age, gender, contact)
                    VALUES (?, ?, ?, ?)
                """, (data['name'], data['age'], data['gender'], data['contact']))
                patient_id = cursor.lastrowid
                password_hash = generate_password_hash(data['password'])
                cursor.execute("""
                    INSERT INTO patient_logins (patient_id, username, password)
                    VALUES (?, ?, ?)
                """, (patient_id, data['username'], password_hash))
                flash("Patient added successfully")
        except sqlite3.IntegrityError:
            flash("Username already exists or data invalid.")
        return redirect('/admin/dashboard')
    return redirect('/admin')

@app.route('/admin/view_doctors')
def view_doctors():
    if 'admin' in session:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, l.username FROM doctors d
            JOIN doctor_logins l ON d.id = l.doctor_id
        """)
        doctors = cursor.fetchall()
        conn.close()
        return render_template('view_doctors.html', doctors=doctors)
    return redirect('/admin')

@app.route('/admin/view_patients')
def view_patients():
    if 'admin' in session:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, l.username FROM patients p
            JOIN patient_logins l ON p.id = l.patient_id
        """)
        patients = cursor.fetchall()
        conn.close()
        return render_template('view_patients.html', patients=patients)
    return redirect('/admin')

@app.route('/admin/change_password', methods=['POST'])
def change_admin_password():
    if 'admin' in session:
        new_password = generate_password_hash(request.form['new_password'])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE admin SET password = ? WHERE username = 'admin'", (new_password,))
        conn.commit()
        conn.close()
        flash("Password updated.")
    return redirect('/admin/dashboard')

if __name__ == '__main__':
    app.run(debug=True, threaded=False)
