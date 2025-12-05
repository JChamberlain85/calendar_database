import uuid
import requests
import pymysql
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify
from icalendar import Calendar

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Database_Daddys123",
    "db": "calendar_database",
    "port": 3306
}

def get_mysql_conn(db_name=None):
    """
    Creates a connection. 
    If db_name is provided, connects to that specific DB.
    If None, connects to MySQL server generally (for creating DBs).
    """
    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=db_name,
        port=DB_CONFIG["port"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def setup_database():
    """Checks if DB exists, creates it if not, and creates all tables."""
    print("--- 1. Checking Database ---")
    
    # Step A: Create DB if missing
    # Connect WITHOUT a database selected to perform administrative tasks
    conn = get_mysql_conn(db_name=None) 
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['db']}")
            print(f"✅ Database '{DB_CONFIG['db']}' ready.")
    finally:
        conn.close() # Close admin connection

    # Step B: Create Tables
    # Now connect TO the specific database
    conn = get_mysql_conn(db_name=DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            # Users
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                User_ID VARCHAR(36) PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(128) NOT NULL,
                salt VARCHAR(36) NOT NULL,
                is_admin TINYINT(1) DEFAULT 0
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

            # Events
            cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                start_dt DATETIME NULL,
                end_dt DATETIME NULL,
                User_ID VARCHAR(36) NULL,
                Course_ID VARCHAR(36) NULL,
                FOREIGN KEY (User_ID) REFERENCES users(User_ID) ON DELETE SET NULL,
                FOREIGN KEY (Course_ID) REFERENCES courses(Course_ID) ON DELETE SET NULL
            ) ENGINE=InnoDB;
            """)

            # Academic Events (Subtype)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS academic_events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                due_dt DATETIME NULL,
                academic_type VARCHAR(128) NULL,
                FOREIGN KEY (Event_ID) REFERENCES events(Event_ID) ON DELETE CASCADE
            ) ENGINE=InnoDB;
            """)
            
            # Personal Events (Subtype)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS personal_events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                privacy VARCHAR(64) NULL,
                FOREIGN KEY (Event_ID) REFERENCES events(Event_ID) ON DELETE CASCADE
            ) ENGINE=InnoDB;
            """)
            
            print("✅ Tables initialized.")
            
    finally:
        conn.close() # Close setup connection

def gen_id():
    return str(uuid.uuid4())

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/events', methods=['GET'])
def get_events():
    conn = get_mysql_conn(DB_CONFIG["db"])
    events_list = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.Event_ID, e.title, e.start_dt, e.end_dt, ae.due_dt 
                FROM events e 
                LEFT JOIN academic_events ae ON e.Event_ID = ae.Event_ID
            """)
            rows = cur.fetchall()
            for row in rows:
                start = row['start_dt']
                end = row['end_dt']
                if row['due_dt'] and not start:
                    start = row['due_dt']
                
                events_list.append({
                    'id': row['Event_ID'],
                    'title': row['title'],
                    'start': start.isoformat() if start else None,
                    'end': end.isoformat() if end else None,
                    'color': '#d93025' if row['due_dt'] else '#039be5' 
                })
    finally:
        conn.close()
    return jsonify(events_list)

@app.route('/api/events', methods=['POST'])
def add_event():
    data = request.json
    conn = get_mysql_conn(DB_CONFIG["db"])
    eid = gen_id()
    dummy_user = "demo_user"
    
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT IGNORE INTO users (User_ID, username, password_hash, salt) VALUES (%s, 'demo', 'x', 'x')", (dummy_user,))
            
            start_dt = data.get('start').replace('T', ' ').split('+')[0] if data.get('start') else None
            end_dt = data.get('end').replace('T', ' ').split('+')[0] if data.get('end') else None

            cur.execute("INSERT INTO events (Event_ID, User_ID, title, start_dt, end_dt) VALUES (%s, %s, %s, %s, %s)",
                        (eid, dummy_user, data['title'], start_dt, end_dt))
            cur.execute("INSERT INTO personal_events (Event_ID) VALUES (%s)", (eid,))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    return jsonify({"status": "success", "id": eid})

@app.route('/api/events/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    conn = get_mysql_conn(DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE Event_ID=%s", (event_id,))
    finally:
        conn.close()
    return jsonify({"status": "deleted"})

@app.route('/api/import-canvas', methods=['POST'])
def import_canvas():
    data = request.json
    feed_url = data.get('url')
    
    if not feed_url: return jsonify({"error": "No URL"}), 400
    if feed_url.startswith('webcal://'): feed_url = feed_url.replace('webcal://', 'https://', 1)
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
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

                    # 1. Handle Start Time
                    if isinstance(dtstart_raw, datetime): 
                        dtstart = dtstart_raw.replace(tzinfo=None)
                    elif isinstance(dtstart_raw, date): 
                        dtstart = datetime.combine(dtstart_raw, datetime.min.time())
                    else: 
                        continue
                    
                    # 2. Handle End Time (THE FIX IS HERE)
                    dtend = None # <--- Initialize it as None by default
                    
                    if isinstance(dtend_raw, datetime): 
                        dtend = dtend_raw.replace(tzinfo=None)
                    elif isinstance(dtend_raw, date): 
                        dtend = datetime.combine(dtend_raw, datetime.min.time())
                        if dtend > dtstart: dtend = dtend - datetime.timedelta(minutes=1)
                    
                    # 3. Create Strings for MySQL
                    start_str = dtstart.strftime('%Y-%m-%d %H:%M:%S')
                    end_str = dtend.strftime('%Y-%m-%d %H:%M:%S') if dtend else None

                    # 4. Save to DB
                    cur.execute("SELECT Event_ID FROM events WHERE title=%s AND start_dt=%s", (title, start_str))
                    if not cur.fetchone():
                        eid = gen_id()
                        cur.execute("INSERT INTO events (Event_ID, title, start_dt, end_dt, Course_ID) VALUES (%s, %s, %s, %s, %s)", 
                                    (eid, title, start_str, end_str, course_id))
                        cur.execute("INSERT INTO academic_events (Event_ID, due_dt) VALUES (%s, %s)", (eid, start_str))
                        count += 1
    except Exception as e:
        print(f"Error import: {e}") # Print error to terminal for debugging
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    return jsonify({"status": "imported", "count": count})

if __name__ == '__main__':
    try:
        setup_database() # Creates DB and Tables properly
        print("🚀 Starting Server on http://127.0.0.1:5000")
        app.run(debug=True, port=5000)
    except Exception as e:
        print(f"❌ Startup Error: {e}")