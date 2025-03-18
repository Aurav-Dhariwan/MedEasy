from flask import Flask, request, jsonify, render_template
import sqlite3
import traceback
from workflow import chat_agent

app = Flask(__name__)

# Database connection
def get_db_connection():
    conn = sqlite3.connect('healthcare_bot.db')
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

# Initialize the database
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        appointment_date TEXT NOT NULL,
        appointment_time TEXT NOT NULL,
        department TEXT NOT NULL,
        status TEXT DEFAULT 'Scheduled'
    )
    ''')
    conn.commit()
    conn.close()

# Homepage with chatbot and appointments table
@app.route('/')
def index():
    conn = get_db_connection()
    appointments = conn.execute('SELECT * FROM appointments').fetchall()
    conn.close()
    return render_template('chat.html', appointments=appointments)

# Route to fetch table rows for AJAX updates
@app.route('/appointments')
def view_appointments():
    conn = get_db_connection()
    appointments = conn.execute('SELECT * FROM appointments').fetchall()
    conn.close()
    return render_template('_appointments_table.html', appointments=appointments)

# Chat endpoint
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    try:
        print(f"Received message: {message}")
        response = chat_agent.invoke(message)
        print(f"Chatbot Response: {response}")
        return jsonify({
            "response": response,
            "state": {"last_message": message},
            "continue_chat": True
        })
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({
            "response": "I apologize, but I couldn't process your request at this time. Please try again.",
            "state": {},
            "continue_chat": True
        })

# Book an appointment
@app.route('/book', methods=['POST'])
def book_appointment():
    data = request.json
    patient_name = data.get('patient_name')
    appointment_date = data.get('appointment_date')
    appointment_time = data.get('appointment_time')
    department = data.get('department', 'General')  # Default to 'General'

    conn = get_db_connection()
    cursor = conn.cursor()
    # Check for conflicts
    cursor.execute('''
    SELECT * FROM appointments 
    WHERE appointment_date = ? AND appointment_time = ?
    ''', (appointment_date, appointment_time))
    if cursor.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Time slot is already booked."})
    
    cursor.execute('''
    INSERT INTO appointments (patient_name, appointment_date, appointment_time, department)
    VALUES (?, ?, ?, ?)
    ''', (patient_name, appointment_date, appointment_time, department))
    appointment_id = cursor.lastrowid  # Get the ID of the newly inserted appointment
    conn.commit()
    conn.close()
    return jsonify({
        "status": "success",
        "message": "Appointment booked successfully!",
        "appointment_id": appointment_id
    })

# Cancel an appointment
@app.route('/cancel/<int:appointment_id>', methods=['GET'])
def cancel_appointment(appointment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM appointments WHERE id = ?', (appointment_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Appointment ID not found."})
    cursor.execute('UPDATE appointments SET status = "Cancelled" WHERE id = ?', (appointment_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Appointment cancelled successfully!"})

# Reschedule an appointment
@app.route('/reschedule/<int:appointment_id>', methods=['POST'])
def reschedule_appointment(appointment_id):
    data = request.json
    new_date = data.get('new_date')
    new_time = data.get('new_time')

    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if appointment exists
    cursor.execute('SELECT * FROM appointments WHERE id = ?', (appointment_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Appointment ID not found."})
    # Check for conflicts
    cursor.execute('''
    SELECT * FROM appointments 
    WHERE appointment_date = ? AND appointment_time = ?
    ''', (new_date, new_time))
    if cursor.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "New time slot is already booked."})
    
    cursor.execute('''
    UPDATE appointments 
    SET appointment_date = ?, appointment_time = ?, status = "Rescheduled" 
    WHERE id = ?
    ''', (new_date, new_time, appointment_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Appointment rescheduled successfully!"})

if __name__ == '__main__':
    init_db()  # Initialize database on startup
    app.run(debug=True)