



from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'
DATABASE = 'hospital.db'

# Helper to connect to the DB
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize DB on first run
def initialize_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        specialization TEXT,
        experience INTEGER,
        contact TEXT,
        available_slots INTEGER DEFAULT 0)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS doctor_logins (
        doctor_id INTEGER,
        username TEXT UNIQUE,
        password TEXT,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age INTEGER,
        gender TEXT,
        contact TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS patient_logins (
        patient_id INTEGER,
        username TEXT UNIQUE,
        password TEXT,
        FOREIGN KEY (patient_id) REFERENCES patients(id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS doctor_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER NOT NULL,
        slot_time TEXT NOT NULL,
        is_booked INTEGER DEFAULT 0,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT CHECK(status IN ('Pending', 'Confirmed', 'Completed')) NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patients(id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')

    cursor.execute("INSERT OR IGNORE INTO admin (username, password) VALUES (?, ?)",
                   ('admin', generate_password_hash('admin123')))
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
        username = request.form.get('username')
        password = request.form.get('password')
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

        flash("Invalid credentials.")
        conn.close()
    return render_template('login.html')

@app.route('/doctor/appointments')
def view_appointments():
     if session.get('role') == 'doctor':
         conn = get_db()
         cursor = conn.cursor()
         cursor.execute("SELECT * FROM appointments WHERE doctor_id = ?", (session['user_id'],))
         appointments = cursor.fetchall()
         conn.close()
         return render_template('view_appointments.html', appointments=appointments)
     return redirect('/login')

@app.route('/doctor/add_appointment')
def add_appointment():
    if session.get('role') == 'doctor':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, slot_time, is_booked FROM doctor_slots WHERE doctor_id = ?", (session['user_id'],))
        slots = cursor.fetchall()
        conn.close()
        return render_template('add_appointments.html', slots=slots)
    return redirect('/login')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/doctor')
def doctor_dashboard():
    if session.get('role') == 'doctor':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, slot_time FROM doctor_slots WHERE doctor_id = ?", (session['user_id'],))
        slots = cursor.fetchall()
        conn.close()
        return render_template('doctor_dashboard.html', slots=slots)
    return redirect('/login')

@app.route('/doctor/add_slot', methods=['POST'])
def add_slot():
    if session.get('role') == 'doctor':
        date = request.form.get('date')
        time = request.form.get('time')
        if not date or not time:
            flash("Date and time are required.")
            return redirect('/doctor')  # fallback only if data missing
        slot_time = f"{date} {time}"
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO doctor_slots (doctor_id, slot_time) VALUES (?, ?)",
                           (session['user_id'], slot_time))
            conn.commit()
            flash("Slot added successfully.")
            return redirect('/doctor/add_appointment')
        except:
            flash("Failed to add slot.")
            return redirect('/doctor')
        finally:
            conn.close()
    return redirect('/login')


@app.route('/doctor/delete_slot/<int:slot_id>', methods=['POST'])
def delete_slot(slot_id):
    if session.get('role') == 'doctor':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM doctor_slots WHERE id = ? AND doctor_id = ? AND is_booked = 0",
                       (slot_id, session['user_id']))
        conn.commit()
        flash("Slot deleted.")
        conn.close()
        return redirect('/doctor/add_appointment')
    return redirect('/login')


@app.route('/user')
def user_dashboard():
    if session.get('role') == 'patient':
        return redirect('/user/book')
    return redirect('/login')

@app.route('/user/book')
def book_appointment():
    if session.get('role') == 'patient':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT s.id, d.name, d.specialization, s.slot_time 
                          FROM doctor_slots s 
                          JOIN doctors d ON s.doctor_id = d.id 
                          WHERE s.is_booked = 0''')
        slots = cursor.fetchall()
        
        conn.close()
        flash("Appointment booked successfully.")

        return render_template('book_appointment.html', slots=slots)
    return redirect('/login')

@app.route('/user/book_slot', methods=['POST'])
def book_slot():
    if session.get('role') == 'patient':
        slot_id = request.form.get('slot_id')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT doctor_id, slot_time FROM doctor_slots WHERE id = ? AND is_booked = 0", (slot_id,))
        result = cursor.fetchone()
        if not result:
            flash("Slot not available.")
            conn.close()
            return redirect('/user/book')
        doctor_id, slot_time = result
        cursor.execute("INSERT INTO appointments (patient_id, doctor_id, date, status) VALUES (?, ?, ?, 'Pending')",
                       (session['user_id'], doctor_id, slot_time))
        cursor.execute("UPDATE doctor_slots SET is_booked = 1 WHERE id = ?", (slot_id,))
        conn.commit()
        conn.close()
        flash("Appointment booked.")
        return redirect('/user/book')
    return redirect('/login')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM admin WHERE username = ?", (username,))
        admin = cursor.fetchone()
        conn.close()
        if admin and check_password_hash(admin[1], password):
            session['admin_id'] = admin[0]
            session['role'] = 'admin'
            return redirect('/admin/dashboard')
        flash("Invalid admin credentials.")
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') == 'admin':
        return render_template('admin_dashboard.html')
    return redirect('/admin')

@app.route('/admin/add_doctor_form')
def add_doctor_form():
    if session.get('role') == 'admin':
        return render_template('add_doctor.html')
    return redirect('/admin')

@app.route('/admin/add_doctor', methods=['POST'])
def add_doctor():
    if session.get('role') == 'admin':
        name = request.form.get('name')
        specialization = request.form.get('specialization')
        experience = request.form.get('experience')
        contact = request.form.get('contact')
        username = request.form.get('username')
        password = generate_password_hash(request.form.get('password'))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO doctors (name, specialization, experience, contact) VALUES (?, ?, ?, ?)",
                       (name, specialization, experience, contact))
        doctor_id = cursor.lastrowid
        cursor.execute("INSERT INTO doctor_logins (doctor_id, username, password) VALUES (?, ?, ?)",
                       (doctor_id, username, password))
        conn.commit()
        conn.close()
        flash("Doctor added successfully.")
        return redirect('/admin/dashboard')
    return redirect('/admin')

@app.route('/admin/add_patient_form')
def add_patient_form():
    if session.get('role') == 'admin':
        return render_template('add_patient.html')
    return redirect('/admin')

@app.route('/admin/add_patient', methods=['POST'])
def add_patient():
    if session.get('role') == 'admin':
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        contact = request.form.get('contact')
        username = request.form.get('username')
        password = generate_password_hash(request.form.get('password'))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO patients (name, age, gender, contact) VALUES (?, ?, ?, ?)",
                       (name, age, gender, contact))
        patient_id = cursor.lastrowid
        cursor.execute("INSERT INTO patient_logins (patient_id, username, password) VALUES (?, ?, ?)",
                       (patient_id, username, password))
        conn.commit()
        conn.close()
        flash("Patient added successfully.")
        return redirect('/admin/dashboard')
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)
