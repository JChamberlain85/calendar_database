import uuid
import pymysql
import requests
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from icalendar import Calendar

app = Flask(__name__)
app.secret_key = "GDXTj_awXec'EOtJxy4o#`l+@~=%-T" 

# --- CONFIGURATION ---
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Database_Daddys123", # <--- UPDATE THIS
    "db": "calendar_database",
    "port": 3306
}

# --- DATABASE HELPERS ---

def get_mysql_conn(db_name=None):
    return pymysql.connect(
        host=DB_CONFIG["host"], user=DB_CONFIG["user"], password=DB_CONFIG["password"],
        database=db_name, port=DB_CONFIG["port"],
        cursorclass=pymysql.cursors.DictCursor, autocommit=True
    )

def setup_database():
    """Creates the database and UPGRADED tables."""
    print("--- Checking Database ---")
    
    # 1. Create Database if missing
    conn = get_mysql_conn(db_name=None) 
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['db']}")
    finally:
        conn.close()

    # 2. Create Tables with NEW COLUMNS
    conn = get_mysql_conn(db_name=DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            # Users Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                User_ID VARCHAR(36) PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB;
            """)
            
            # Courses
            cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                Course_ID VARCHAR(36) PRIMARY KEY,
                Course_code VARCHAR(255) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                department VARCHAR(255) NULL
            ) ENGINE=InnoDB;
            """)

            # Events (UPGRADED)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                start_dt DATETIME NULL,
                end_dt DATETIME NULL,
                is_all_day TINYINT(1) DEFAULT 0,
                rrule VARCHAR(255) NULL,       -- For Recurring Events (e.g., 'FREQ=WEEKLY')
                description TEXT NULL,         -- New Field
                location VARCHAR(255) NULL,    -- New Field
                color VARCHAR(20) DEFAULT '#039be5', -- New Field
                User_ID VARCHAR(36) NULL,
                Course_ID VARCHAR(36) NULL,
                FOREIGN KEY (User_ID) REFERENCES users(User_ID) ON DELETE SET NULL,
                FOREIGN KEY (Course_ID) REFERENCES courses(Course_ID) ON DELETE SET NULL
            ) ENGINE=InnoDB;
            """)

            # Academic Events
            cur.execute("""
            CREATE TABLE IF NOT EXISTS academic_events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                due_dt DATETIME NULL,
                academic_type VARCHAR(128) NULL,
                FOREIGN KEY (Event_ID) REFERENCES events(Event_ID) ON DELETE CASCADE
            ) ENGINE=InnoDB;
            """)
            
            # Personal Events
            cur.execute("""
            CREATE TABLE IF NOT EXISTS personal_events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                privacy VARCHAR(64) NULL,
                FOREIGN KEY (Event_ID) REFERENCES events(Event_ID) ON DELETE CASCADE
            ) ENGINE=InnoDB;
            """)
            
            print("✅ Tables initialized.")
    finally:
        conn.close()

def gen_id():
    return str(uuid.uuid4())

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html', username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        return render_template('login.html')
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    conn = get_mysql_conn(DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            user = cur.fetchone()
            if user:
                session['user_id'] = user['User_ID']
                session['username'] = user['username']
                return redirect(url_for('index'))
            else:
                flash("Invalid username or password")
                return redirect(url_for('login_page'))
    finally:
        conn.close()

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = get_mysql_conn(DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT User_ID FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                flash("Username already exists")
                return redirect(url_for('login_page'))
            
            # Insert new user
            uid = gen_id()
            cur.execute("INSERT INTO users (User_ID, username, password) VALUES (%s, %s, %s)", 
                        (uid, username, password))
            flash("Account created! Please log in.")
            return redirect(url_for('login_page'))
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- API ROUTES ---

@app.route('/api/events', methods=['GET'])
def get_events():
    if 'user_id' not in session: return jsonify([]), 401
    
    conn = get_mysql_conn(DB_CONFIG["db"])
    events_list = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events WHERE User_ID=%s", (session['user_id'],))
            rows = cur.fetchall()
            for row in rows:
                ev = {
                    'id': row['Event_ID'],
                    'title': row['title'],
                    'color': row['color'],
                    'description': row['description'],
                    'location': row['location']
                }
                
                # Handle Recurring Logic
                if row['rrule']:
                    ev['rrule'] = row['rrule'] 
                    # If using rrule, start_dt usually acts as the start time of the day
                    if row['start_dt']:
                        # For FullCalendar RRule, we often need just the time or a start date
                        ev['duration'] = "01:00" # Default duration if not calc'd
                else:
                    ev['start'] = row['start_dt'].isoformat() if row['start_dt'] else None
                    ev['end'] = row['end_dt'].isoformat() if row['end_dt'] else None
                
                events_list.append(ev)
    finally:
        conn.close()
    return jsonify(events_list)

@app.route('/api/events', methods=['POST'])
def add_event():
    if 'user_id' not in session: return jsonify({"error": "Login required"}), 401
    data = request.json
    conn = get_mysql_conn(DB_CONFIG["db"])
    eid = gen_id()
    
    try:
        with conn.cursor() as cur:
            # Parse simple dates
            start_dt = data.get('start')
            end_dt = data.get('end')
            if start_dt: start_dt = start_dt.replace('T', ' ')
            if end_dt: end_dt = end_dt.replace('T', ' ')

            # Recurrence Logic
            rrule = None
            freq = data.get('recurrence') # 'DAILY', 'WEEKLY', etc.
            if freq and freq != 'NONE':
                # Build a simple RRULE string compatible with FullCalendar
                # Example: "FREQ=WEEKLY;DTSTART=20231010T103000Z"
                # For simplicity here, we just store FREQ.
                # In a real app, you'd calculate proper DTSTART.
                rrule = f"FREQ={freq}"
                # If recurring, we might still want start_dt as the 'first instance' reference

            cur.execute("""
                INSERT INTO events 
                (Event_ID, User_ID, title, start_dt, end_dt, rrule, description, location, color) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (eid, session['user_id'], data['title'], start_dt, end_dt, rrule, 
                  data.get('description'), data.get('location'), data.get('color')))
            
            cur.execute("INSERT INTO personal_events (Event_ID) VALUES (%s)", (eid,))
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    return jsonify({"status": "success", "id": eid})

# ... (Delete and Import routes remain the same as previous step, just ensure they filter by User_ID) ...
# I will include them for completeness:

@app.route('/api/events/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    if 'user_id' not in session: return jsonify({"error": "Login required"}), 401
    conn = get_mysql_conn(DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE Event_ID=%s AND User_ID=%s", (event_id, session['user_id']))
    finally:
        conn.close()
    return jsonify({"status": "deleted"})

@app.route('/api/import-canvas', methods=['POST'])
def import_canvas():
    if 'user_id' not in session: return jsonify({"error": "Login required"}), 401
    data = request.json
    feed_url = data.get('url')
    if not feed_url: return jsonify({"error": "No URL"}), 400
    if feed_url.startswith('webcal://'): feed_url = feed_url.replace('webcal://', 'https://', 1)
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    conn = get_mysql_conn(DB_CONFIG["db"])
    count = 0
    try:
        resp = requests.get(feed_url, headers=headers, timeout=15)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.content)
        
        with conn.cursor() as cur:
            course_id = "canvas_import_bucket"
            cur.execute("INSERT IGNORE INTO courses (Course_ID, Course_code, title) VALUES (%s, 'CANVAS', 'Imported')", (course_id,))
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    title = str(component.get('summary'))
                    dtstart_raw = component.get('dtstart').dt
                    dtend_raw = component.get('dtend').dt if component.get('dtend') else None

                    if isinstance(dtstart_raw, datetime): dtstart = dtstart_raw.replace(tzinfo=None)
                    elif isinstance(dtstart_raw, date): dtstart = datetime.combine(dtstart_raw, datetime.min.time())
                    else: continue
                    
                    dtend = None
                    if isinstance(dtend_raw, datetime): dtend = dtend_raw.replace(tzinfo=None)
                    elif isinstance(dtend_raw, date): 
                        dtend = datetime.combine(dtend_raw, datetime.min.time())
                        if dtend > dtstart: dtend = dtend - timedelta(minutes=1)
                    
                    start_str = dtstart.strftime('%Y-%m-%d %H:%M:%S')
                    end_str = dtend.strftime('%Y-%m-%d %H:%M:%S') if dtend else None

                    # Only checking for duplicate title+time for THIS user
                    cur.execute("SELECT Event_ID FROM events WHERE title=%s AND start_dt=%s AND User_ID=%s", (title, start_str, session['user_id']))
                    if not cur.fetchone():
                        eid = gen_id()
                        cur.execute("""
                            INSERT INTO events (Event_ID, title, start_dt, end_dt, Course_ID, User_ID, color) 
                            VALUES (%s, %s, %s, %s, %s, %s, '#d93025')
                        """, (eid, title, start_str, end_str, course_id, session['user_id']))
                        count += 1
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    return jsonify({"status": "imported", "count": count})

if __name__ == '__main__':
    setup_database()
    print("🚀 Server Running!")
    app.run(debug=True, port=5000)