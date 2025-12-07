# calendar_database

A comprehensive calendar application built with **Python (Flask)** and **MySQL**. This application allows students to manage personal events, recurring schedules, and automatically sync their assignments from **Canvas LMS** using calendar feeds.

---

## Installation Manual

### Step 1: Install Python Libraries
Download ``requirements.txt``, ``main.py``, and ``Templates`` into your project folder. Open your terminal (Command Prompt or PowerShell) in the project folder and run the following command to install the required dependencies:

``pip install -r requirements.txt``

### Step 2: Configure the Database
The application needs to know your specific MySQL database password to modify the database.

1.  Open **main.py** in a text editor (Notepad, VS Code, etc.).
2.  Locate the `DB_CONFIG` section near the top of the file.
3.  Update the fields to match your MySQL Database.

# Change config file to match your database
``DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Database_Daddys123", 
    "db": "calendar_database",
    "port": 3306
}``


## User Guide

Step 1: Start your MySQL database and run main.py 

Step 2: Access the Website by copying and pasting the link the terminal gives you after running the main file

Step 3: Register account and log in

Step 4: Add events by clicking on dates, import canvas assignments by copying the link given after clicking the "Calendar Feed" button on the right side of your canvas calendar and copy/paste that link in the "Import Canvas" Section of the calendar website
