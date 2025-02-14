import streamlit as st
import sqlite3
import datetime
import bcrypt
import pandas as pd
import re
from transformers import pipeline
from pytz import timezone

# ===========================
# Configuration & Initialization
# ===========================
st.set_page_config(page_title="AI Healthcare Assistant", page_icon="💬", layout="wide")

# ===========================
# Database Setup
# ===========================
@st.cache_resource(show_spinner=False)
def get_db_connection():
    conn = sqlite3.connect("healthcare.db", check_same_thread=False)
    cur = conn.cursor()
    
    # Create tables
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    username TEXT UNIQUE, 
                    password BLOB, 
                    email TEXT)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    patient_name TEXT, 
                    doctor_name TEXT, 
                    appointment_datetime TEXT)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    patient_name TEXT, 
                    medication TEXT, 
                    reminder_time TEXT,
                    sent INTEGER DEFAULT 0)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    full_name TEXT,
                    age INTEGER,
                    medical_history TEXT,
                    allergies TEXT,
                    medications TEXT,
                    blood_type TEXT,
                    height INTEGER,
                    weight INTEGER,
                    profile_picture BLOB)''')
    
    conn.commit()
    return conn, cur

conn, cur = get_db_connection()

# ===========================
# Core Functions
# ===========================
def signup(username, password, email):
    if not re.match(r"^[A-Za-z0-9_]{3,20}$", username):
        return "❌ Invalid username (3-20 chars, alphanumeric)"
    
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cur.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                    (username, hashed, email))
        conn.commit()
        return "✅ Signup successful!"
    except sqlite3.IntegrityError:
        return "❌ Username already exists!"
    except Exception as e:
        return f"❌ Signup error: {e}"

def login(username, password):
    try:
        cur.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = cur.fetchone()
        if result:
            stored_hashed_pw = result[0]  # Ensure this is stored as bytes
            if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_pw):
                return "✅ Login successful!"
        return "❌ Invalid credentials"
    except Exception as e:
        return f"❌ Login error: {e}"


@st.cache_resource(show_spinner=False)
def load_chatbot():
    return pipeline("text-generation", model="distilgpt2", device=-1)

chatbot = load_chatbot()

def healthcare_chatbot(user_input):
    disclaimer = "⚠️ This is not medical advice."
    try:
        # Generate response from the chatbot
        response = chatbot(user_input, max_length=200, temperature=0.7)[0]['generated_text']
        return f"{response}\n\n⚠️ {disclaimer}"
    except Exception as e:
        return f"Error: {str(e)}"

# ===========================
# Appointment Functions
# ===========================
def book_appointment(patient_name, doctor_name, appointment_datetime):
    try:
        if appointment_datetime.tzinfo is None:
            appointment_datetime = timezone('Asia/Kolkata').localize(appointment_datetime)
        
        utc_time = appointment_datetime.astimezone(timezone('UTC'))
        
        cur.execute("""INSERT INTO appointments 
                    (patient_name, doctor_name, appointment_datetime)
                    VALUES (?, ?, ?)""",
                    (patient_name, doctor_name, utc_time.isoformat()))
        conn.commit()
        return "✅ Appointment booked!"
    except Exception as e:
        return f"❌ Error: {e}"

def delete_appointment(appointment_id):
    try:
        cur.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
        conn.commit()
        return "✅ Appointment deleted!"
    except Exception as e:
        return f"❌ Error: {e}"

# ===========================
# Medicine Reminder Functions
# ===========================
def set_medicine_reminder(patient_name, medication, reminder_time):
    try:
        india_time = reminder_time.astimezone(timezone('Asia/Kolkata'))  # Convert to India Standard Time (IST)
        cur.execute("""INSERT INTO reminders 
                    (patient_name, medication, reminder_time) 
                    VALUES (?, ?, ?)""",
                    (patient_name, medication, india_time.isoformat()))
        conn.commit()
        return "✅ Medicine reminder set!"
    except Exception as e:
        return f"❌ Error: {e}"

def delete_medicine_reminder(reminder_id):
    try:
        cur.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        return "✅ Medicine reminder deleted!"
    except Exception as e:
        return f"❌ Error: {e}"

# ===========================
# User Interface
# ===========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# Authentication Sidebar
with st.sidebar:
    st.title("🔐 Authentication")
    auth_mode = st.radio("Choose", ["Login", "Signup"])
    
    if auth_mode == "Signup":
        with st.form("signup"):
            email = st.text_input("Email")
            username = st.text_input("Username (3-20 chars, a-z, 0-9, _)")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign Up"):
                if all([email, username, password]):
                    msg = signup(username, password, email)
                    if "✅" in msg:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                    st.success(msg)
    else:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log In"):
                if username and password:
                    msg = login(username, password)
                    if "✅" in msg:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                    st.success(msg)

def get_profile_picture(username):
    cur.execute("SELECT profile_picture FROM profiles WHERE username = ?", (username,))
    result = cur.fetchone()
    if result and result[0]:  # If picture exists
        return result[0]  # Binary data
    return None

# Display Profile Picture
image_data = get_profile_picture(st.session_state.username)
if image_data:
    st.image(image_data, caption="Profile Picture", use_column_width=True)


# Main App Interface
if st.session_state.logged_in:
    tabs = st.tabs(["💬 Chat", "📅 Appointments", "💊 Medicine Reminder", "👤 Profile"])

    with tabs[0]:  # Chat Tab
        st.header("AI Healthcare Assistant")

        prompt = st.chat_input("Your message...")
        if prompt:
            with st.spinner("Generating response..."):
                response = healthcare_chatbot(prompt)
            st.session_state.messages.append(f"**You:** {prompt}")
            st.session_state.messages.append(f"**AI:** {response}")

        for msg in st.session_state.messages:
            st.markdown(msg)
    
    with tabs[1]:  # Appointments
        st.header("Manage Appointments")
        
        # Appointment booking form
        with st.form("appointment"):
            doctors = ["Dr. Smith (Cardiology)", "Dr. Jones (Pediatrics)"]
            doc = st.selectbox("Doctor", doctors)
            date = st.date_input("Select a date", min_value=datetime.datetime.now().date())
            time = st.time_input("Select a time", value=datetime.datetime.now().time())

            # Combine date and time into a single datetime object
            dt = datetime.datetime.combine(date, time)

            tz = st.selectbox("Timezone", ["Asia/Kolkata"])
            
            if st.form_submit_button("Book Appointment"):
                tz_obj = timezone(tz)
                localized_dt = tz_obj.localize(dt)
                msg = book_appointment(st.session_state.username, doc, localized_dt)
                st.success(msg)

        # Display upcoming appointments
        cur.execute("""SELECT id, doctor_name, datetime(appointment_datetime) 
                     FROM appointments WHERE patient_name = ?
                     ORDER BY datetime(appointment_datetime)""",
                     (st.session_state.username,))
        appointments = cur.fetchall()
        if appointments:
            st.subheader("Upcoming Appointments")
            # Convert the string datetime to datetime object
            appointments = [(appointment_id, doctor, datetime.datetime.fromisoformat(appointment)) 
                            for appointment_id, doctor, appointment in appointments]
            df = pd.DataFrame(appointments, columns=["Appointment ID", "Doctor", "Date/Time (UTC)"])
            st.dataframe(df.style.format({"Date/Time (UTC)": lambda x: x.strftime('%Y-%m-%d %H:%M')}))
            
            # Delete appointment functionality
            appointment_id_to_delete = st.number_input("Enter Appointment ID to delete", min_value=1, step=1)
            if st.button("Delete Appointment"):
                if appointment_id_to_delete:
                    msg = delete_appointment(appointment_id_to_delete)
                    st.success(msg)
        
    with tabs[2]:  # Medicine Reminder Tab
        st.header("Medicine Reminder")
        
        # Show reminders
        cur.execute("""SELECT id, medication, reminder_time FROM reminders WHERE patient_name = ? ORDER BY reminder_time""",
                     (st.session_state.username,))
        reminders = cur.fetchall()
        if reminders:
            st.subheader("Your Medicine Reminders")
            reminders = [(reminder_id, medication, datetime.datetime.fromisoformat(reminder_time)) 
                         for reminder_id, medication, reminder_time in reminders]
            df = pd.DataFrame(reminders, columns=["Reminder ID", "Medication", "Reminder Time (IST)"])
            st.dataframe(df.style.format({"Reminder Time (IST)": lambda x: x.strftime('%Y-%m-%d %H:%M')}))
        
        # Delete reminder functionality
        reminder_id_to_delete = st.number_input("Enter Reminder ID to delete", min_value=1, step=1)
        if st.button("Delete Medicine Reminder"):
            if reminder_id_to_delete:
                msg = delete_medicine_reminder(reminder_id_to_delete)
                st.success(msg)
        
        # Reminder form
        with st.form("reminder_form"):
            medication = st.text_input("Medication Name")
            reminder_time = st.time_input("Reminder Time", value=datetime.datetime.now().time())

            if st.form_submit_button("Set Reminder"):
                reminder_datetime = datetime.datetime.combine(datetime.date.today(), reminder_time)
                msg = set_medicine_reminder(st.session_state.username, medication, reminder_datetime)
                st.success(msg)
    
    with tabs[3]:  # Profile Section
        st.header("Medical Profile")
        
        # Profile Picture Upload
        uploaded_file = st.file_uploader("Upload Profile Picture", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)
            profile_picture = uploaded_file.read()
            # Save to database
            cur.execute("INSERT OR REPLACE INTO profiles (username, profile_picture) VALUES (?, ?)",
                        (st.session_state.username, profile_picture))
            conn.commit()
        
        # Profile Information Form
        with st.form("profile_form"):
            full_name = st.text_input("Full Name")
            age = st.number_input("Age", min_value=1, max_value=120, step=1)
            medical_history = st.text_area("Medical History")
            allergies = st.text_area("Allergies")
            medications = st.text_area("Current Medications")
            blood_type = st.text_input("Blood Type")
            height = st.number_input("Height (cm)", min_value=50, max_value=300, step=1)
            weight = st.number_input("Weight (kg)", min_value=1, max_value=300, step=1)

            if st.form_submit_button("Save Profile"):
                try:
                    cur.execute("""
                        INSERT OR REPLACE INTO profiles 
                        (username, full_name, age, medical_history, allergies, medications, blood_type, height, weight)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, 
                    (st.session_state.username, full_name, age, medical_history, allergies, medications, blood_type, height, weight))
                    conn.commit()
                    st.success("Profile Updated Successfully!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
else:
    st.warning("⚠️ Please do log in to continue with the app.")