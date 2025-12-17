# MySQL Abstraction Layer for Musson Group IT's Budget Tracking Application
# Author: Zedaine McDonald
# Date; **

import pymysql
import streamlit as st
from datetime import datetime
import requests
import pandas as pd
import bcrypt
import base64

import pathlib
import tempfile

#Database config section
dbsecrets = st.secrets["MYSQL"]

#ssl authentication files.
ssl_options = {
    "ca": dbsecrets["sslserverca"],
    "cert": dbsecrets["sslclientcert"],
    "key": dbsecrets["sslclientkey"],
    "check_hostname": dbsecrets["sslcheck_hostname"]
}

def write_cert(b64_data, filename):
    """Function to decode base64 and write to a temportaty file"""
    decoded = base64.b64decode(b64_data)
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(decoded)
    f.flush()
    return f.name

# Initial database connection
def get_db():

    home_lib = pathlib.Path.home()
    target_path = home_lib/"private"
    dbsecrets = st.secrets["MYSQL"]
    

    try:
        connection = pymysql.connect(
            host= dbsecrets["host"],
            user= dbsecrets["user"],
            password= dbsecrets["password"],
            database= dbsecrets["database"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            charset="utf8mb4",
        )
        return connection
    except pymysql.Error as e:
        st.error(f"Error connecting to MySQL database: {e}")
        return None


# Users CRUD operations
def get_user_by_email(email: str):
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            SELECT id, name, username, email, hashed_password, role, first_login
            FROM users
            WHERE LOWER(email) = LOWER(%s)
        """, (email,))
        return c.fetchone()


def get_all_users():
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            SELECT id, name, username, email, role, first_login
            FROM users
            ORDER BY name ASC
        """)
        return c.fetchall()


def add_user(name: str, username: str, email: str, hashed_pw:str, role="user"):
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            INSERT INTO users (name, username, email, hashed_password, role, first_login)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, (name, username, email, hashed_pw, role))
    return True


def update_password(email, hashed_pw, first_login: bool = True):
    db = get_db()
    with db.cursor() as c:
        if first_login:
            c.execute("""
                UPDATE users
                SET hashed_password = %s, first_login = True
                WHERE LOWER(email) = LOWER(%s)
            """, (hashed_pw, email))
        else:
            c.execute("""
            UPDATE users
            SET hashed_password = %s, first_login = False
            WHERE LOWER(email) = LOWER(%s)
            """, (hashed_pw,email))
    return True


def reset_user_password(email, hashed_pw):
    """
    Admin resets password -> first_login becomes TRUE.
    """
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            UPDATE users
            SET hashed_password = %s, first_login = TRUE
            WHERE LOWER(email) = LOWER(%s)
        """, (hashed_pw, email))
    return True


def delete_user(email):
    db = get_db()
    with db.cursor() as c:
        c.execute("DELETE FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
    return True




#Login information CRUD
def log_login_activity(email, activity_type, ip_address):
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            INSERT INTO loginlogs (email, activity_type, status, timestamp)
            VALUES (%s, %s, %s, NOW())
        """, (email, activity_type, ip_address))
    return True


def get_login_logs():
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            SELECT email, activity_type, status, timestamp
            FROM loginlogs
            ORDER BY timestamp DESC
        """)
        return c.fetchall()
    



#File Upload CRUD
def add_uploaded_file(file_name, file_type, uploader_email, file_url):
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            INSERT INTO uploadedfiles
            (file_name, file_type, uploader_email, upload_date, file_url)
            VALUES (%s, %s, %s, NOW(), %s)
        """, (file_name, file_type, uploader_email, file_url))
    return True


def delete_uploaded_file(file_name):
    db = get_db()
    with db.cursor() as c:
        c.execute("DELETE FROM uploadedfiles WHERE file_name = %s", (file_name,))
    return True


def get_uploaded_files():
    db = get_db()
    with db.cursor() as c:
        c.execute("""
            SELECT file_name, file_type, uploader_email, upload_date, file_url
            FROM uploadedfiles
            ORDER BY upload_date DESC
        """)
        return c.fetchall()
    



#Budget State Operations
def load_budget_state_monthly(file_name: str):
    #db = get_db()
    #with db.cursor() as c:
    #    c.execute("""
    #        SELECT category, subcategory, month, amount, status_category
    #        FROM budget_state
    #        WHERE file_name = %s
    #    """, (file_name,))
    #    rows = c.fetchall()
    #return rows
    """
    Loads budget-state monthly classification from MySQL.
    Always returns a DataFrame with the required columns.
    Never returns a tuple or list.
    """

    db = get_db()
    with db.cursor() as c:
        c.execute("""
            SELECT category, subcategory, month, amount, status_category
            FROM budget_state
            WHERE file_name = %s
        """, (file_name,))
        rows = c.fetchall()

    # If nothing in DB → return empty DataFrame with required columns
    if not rows:
        return pd.DataFrame(columns=[
            "Category", "Sub-Category", "Month",
            "Amount", "Status Category"
        ])

    # Convert to DataFrame
    df = pd.DataFrame(rows)

    # Normalize column names to match dashboard expectations
    df = df.rename(columns={
        "category": "Category",
        "subcategory": "Sub-Category",
        "month": "Month",
        "amount": "Amount",
        "status_category": "Status Category",
    })

    # Ensure required columns exist
    required = ["Category", "Sub-Category", "Month", "Amount", "Status Category"]
    for col in required:
        if col not in df.columns:
            df[col] = None

    return df[required]

def save_budget_state_monthly(file_name, df_melted, user_email):
    """
    Saves budget-state monthly classification using MySQL UPSERT.
    Only inserts new rows or updates existing ones.
    """
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = df_melted.to_dict(orient="records")

    with db.cursor() as c:
        for r in rows:
            c.execute("""
                INSERT INTO budget_state
                (file_name, category, subcategory, month, amount, status_category, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)

                ON DUPLICATE KEY UPDATE
                    amount = VALUES(amount),
                    status_category = VALUES(status_category),
                    updated_by = VALUES(updated_by),
                    updated_at = VALUES(updated_at)
            """, (
                file_name,
                r["Category"],
                r["Sub-Category"],
                r["Month"],
                r["Amount"],
                r["Status Category"],
                user_email,
                now
            ))

    return True





#Generic Helpers
def run_query(sql: str, params=None):
    """Run a SELECT and return all rows as list(dict)."""
    db = get_db()
    with db.cursor() as c:
        c.execute(sql, params or ())
        return c.fetchall()


def run_execute(sql: str, params=None):
    """Run INSERT/UPDATE/DELETE."""
    db = get_db()
    with db.cursor() as c:
        c.execute(sql, params or ())
    return True

#Non-SQL, IP get
def get_ip():
    try:
        response = requests.get("https://api.ipify.org?format=text")
        return response.text
    except:
        return "Unavailable"
    
def seed_admin_user():
    """
    Generates a default admin user with user defined credentials
    """
    x = run_query(sql = "select count(*) from users")
    try:

        #Check if any user exists
        if x[0].get("count(*)") < 1:

            #Inserting user details
            name = st.secrets['admin']['name']
            email = st.secrets['admin']['email']
            username = st.secrets['admin']['username']
            password = str(st.secrets['admin']['password'])
            role = st.secrets['admin']['role']

            #Hashing password
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            encoded = base64.b64encode(hashed).decode()

            #Inserting user
            add_user(name, username, email, encoded, role)
            print ("No users found, admin user seeded")
        else:
            pass

    except Exception as e:
        st.error(f"Error seeding user {e}")

def set_active_budget(file_name:str):
    """ 
    Sets the active budget file.

    If a table is empty, insert a new row.
    If there is already a selected budget update the table
    If multiple rows exist (this shouldn't happen) the entire table is cleared.
    """
    db = get_db()
    with db.cursor() as c:
        #clearing table
        c.execute("Select id from active_budget limit 2")
        rows = c.fetchall()

        if len(rows) == 0:  #If there is no selected budget file.
            c.execute("Insert into active_budget (file_name) values (%s)",(file_name,))

        elif len(rows) == 1:    #If one row exists
            active_id = rows[0]["id"]
            c.execute("update active_budget set file_name = %s, updated_at = NOW(), where id = %s",
                      (file_name, active_id, ))
            
        else:   #if multiple rows exits (safety cleanu[])
            c.execute("delete from active_budget")
            c.execute("Insert into active_budget (file_name, updated_at) values (%s,NOW())", (file_name,))
        
    db.commit()
    return True

def clear_active_budget():
    """
    clears active budget setting
    """
    db = get_db()
    
    with db.cursor() as c:
        c.execute("delete from active_budget")
    
    return True

def get_active_budget() -> str:
    """
    returns active budget file_name or "None" if none is set
    """
    db = get_db()

    with db.cursor() as c:
        c.execute("select file_name FROM active_budget limit 1")
        row = c.fetchone()

    if not row:
        return "None"
    
    return row["file_name"]

def get_active_budget_metadata() -> dict:
    """
    Returns full metadata from uploadedfiles for the active budget.
    (file_url, file_type, timestamp, uploader_email, etc.)
    """
    active_file = get_active_budget()

    db = get_db()
    with db.cursor() as c:
        c.execute("""
            SELECT *
            FROM uploadedfiles
            WHERE file_name = %s
            LIMIT 1
        """, (active_file,))
        row = c.fetchone()

    if not row:
        raise ValueError(f"❌ Active budget '{active_file}' not found in uploadedfiles table.")

    return row