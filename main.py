import uuid
import pymysql
import requests
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from icalendar import Calendar

app = Flask(__name__)
app.secret_key = "GDXTj_awXec'EOtJxy4o#`l+@~=%-T" 

# Config, update for your server
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Database_Daddys123", 
    "db": "calendar_database",
    "port": 3306
}

#Connect mysql server
def get_mysql_conn(db_name=None):
    return pymysql.connect(
        host=DB_CONFIG["host"], user=DB_CONFIG["user"], password=DB_CONFIG["password"],
        database=db_name, port=DB_CONFIG["port"],
        cursorclass=pymysql.cursors.DictCursor, autocommit=True
    )

def setup_database():
    #Create Database if missing
    conn = get_mysql_conn(db_name=None) 
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['db']}")
    finally:
        conn.close()

    # Create new tables
    conn = get_mysql_conn(db_name=DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            # Users table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                User_ID VARCHAR(36) PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB;
            """)

            # Academic Events table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS academic_events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                start_dt DATETIME NULL,
                end_dt DATETIME NULL,
                is_all_day TINYINT(1) DEFAULT 0,
                rrule VARCHAR(255) NULL,       
                description TEXT NULL,        
                location VARCHAR(255) NULL,   
                color VARCHAR(20) DEFAULT '#039be5', 
                User_ID VARCHAR(36) NULL,
                FOREIGN KEY (User_ID) REFERENCES users(User_ID) ON DELETE SET NULL
            ) ENGINE=InnoDB;
            """)

            # Personal Events table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS personal_events (
                Event_ID VARCHAR(36) PRIMARY KEY,
                privacy VARCHAR(64) NULL,
                FOREIGN KEY (Event_ID) REFERENCES academic_events(Event_ID) ON DELETE CASCADE
            ) ENGINE=InnoDB;
            """)
            
    finally:
        conn.close()

def gen_id():
    return str(uuid.uuid4())

#Force login
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html', username=session.get('username'))

#login prompt
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
                return redirect(url_for('index')) #user confirmed 
            else:
                flash("Invalid username or password")
                return redirect(url_for('login_page')) #user denied
    finally:
        conn.close()

#new user register
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = get_mysql_conn(DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT User_ID FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                flash("Username already exists") #duplicate user check
                return redirect(url_for('login_page'))
            
            # Insert new user
            uid = gen_id()
            cur.execute("INSERT INTO users (User_ID, username, password) VALUES (%s, %s, %s)", 
                        (uid, username, password))
            flash("Account created! Please log in.")
            return redirect(url_for('login_page'))
    finally:
        conn.close()

#sign out
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

#Academic Event pull
@app.route('/api/academic_events', methods=['GET'])
def get_events():
    if 'user_id' not in session: return jsonify([]), 401
    
    conn = get_mysql_conn(DB_CONFIG["db"])
    events_list = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM academic_events WHERE User_ID=%s", (session['user_id'],))
            rows = cur.fetchall()
            for row in rows:
                ev = {
                    'id': row['Event_ID'],
                    'title': row['title'],
                    'color': row['color'],
                    'description': row['description'],
                    'location': row['location']
                }
                
                # FIX: Always set start and end if they exist
                if row['start_dt']:
                    ev['start'] = row['start_dt'].isoformat()
                if row['end_dt']:
                    ev['end'] = row['end_dt'].isoformat()
                
                if row['rrule']:
                    ev['rrule'] = row['rrule'] 
                    ev['duration'] = "01:00" 
                
                events_list.append(ev)
    finally:
        conn.close()
    return jsonify(events_list)

@app.route('/api/academic_events', methods=['POST'])
def add_event():
    if 'user_id' not in session: return jsonify({"error": "Login required"}), 401
    data = request.json
    conn = get_mysql_conn(DB_CONFIG["db"])
    eid = gen_id()
    
    try:
        with conn.cursor() as cur:
            # simple dates
            start_dt = data.get('start')
            end_dt = data.get('end')
            if start_dt: start_dt = start_dt.replace('T', ' ')
            if end_dt: end_dt = end_dt.replace('T', ' ')

            # recurring dates
            rrule = None
            freq = data.get('recurrence')
            if freq and freq != 'NONE':
                rrule = f"FREQ={freq}"
                
            #insert into events tables
            cur.execute("""
                INSERT INTO academic_events 
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

#Delete events

@app.route('/api/academic_events/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    if 'user_id' not in session: return jsonify({"error": "Login required"}), 401
    conn = get_mysql_conn(DB_CONFIG["db"])
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM academic_events WHERE Event_ID=%s AND User_ID=%s", (event_id, session['user_id']))
    finally:
        conn.close()
    return jsonify({"status": "deleted"})

#import canvas events
@app.route('/api/import-canvas', methods=['POST'])
def import_canvas():
    if 'user_id' not in session: return jsonify({"error": "Login required"}), 401

    data = request.json
    feed_url = data.get('url')
    if not feed_url: return jsonify({"error": "No URL"}), 400
    if feed_url.startswith('webcal://'): feed_url = feed_url.replace('webcal://', 'https://', 1) #hopefully works now
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    conn = get_mysql_conn(DB_CONFIG["db"])
    count = 0
    try:
        resp = requests.get(feed_url, headers=headers, timeout=15)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.content)
        
        with conn.cursor() as cur:
            for component in cal.walk():
                if component.name == "VEVENT": #filter useful information
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

                    # block duplicate canvas events
                    cur.execute("SELECT Event_ID FROM academic_events WHERE title=%s AND start_dt=%s AND User_ID=%s", (title, start_str, session['user_id']))
                    if not cur.fetchone():
                        eid = gen_id()
                        cur.execute("""
                            INSERT INTO academic_events (Event_ID, title, start_dt, end_dt,  User_ID, color) 
                            VALUES (%s, %s, %s, %s, %s, '#d93025')
                        """, (eid, title, start_str, end_str, session['user_id']))
                        count += 1
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    return jsonify({"status": "imported", "count": count})

if __name__ == '__main__':
    setup_database()
    print("Server Running")
    app.run(debug=True, port=5000)