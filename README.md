# calendar_database

A comprehensive calendar application built with **Python (Flask)** and **MySQL**. This application allows students to manage personal events, recurring schedules, and automatically sync their assignments from **Canvas LMS** using calendar feeds.

---

## 🚀 Installation Guide

### Step 1: Install Python Libraries
Open your terminal (Command Prompt or PowerShell) in the project folder and run the following command to install the required dependencies:

pip install flask pymysql requests icalendar

### Step 2: Configure the Database
The application needs to know your specific MySQL password to create the database.

1.  Open **main.py** in a text editor (Notepad, VS Code, etc.).
2.  Locate the `DB_CONFIG` section near the top of the file.
3.  Update the **password** field to match your MySQL root password.

# Change config file to match your database
``DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "password",  
    "db": "project3",
    "port": 3306
}``

## User Guide

Step 1: Start MySQL and run main.py 

Step 2: Access the Website by copying and pasting the link the terminal gives you after running the main file

Step 3: Register account and log in

### Step 4: Add events by clicking on dates, import canvas assignments by copying the link given after clicking the "Calendar Feed" button on the right side of your canvas calendar and copy/paste that link in the "Import Canvas" Section of the calendar website
