from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import date
import psycopg2
import psycopg2.extras
import os
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
from PIL import Image
import re

app = Flask(__name__)
app.secret_key = 'expiry-tracker-secret-key-2024'

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://expiry_tracker_db2_user:ileMauyebfZmWTKAlaWvvWfKl4QRLGQh@dpg-d925utbtqb8s73euvtl0-a.oregon-postgres.render.com/expiry_tracker_db2')

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'akramamjadali7@gmail.com'
app.config['MAIL_PASSWORD'] = 'soyj gyhv uylj npke'
app.config['MAIL_DEFAULT_SENDER'] = 'akramamjadali7@gmail.com'

mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access the Expiry Tracker.'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

USERS = {
    'admin': {'id': '1', 'password': 'admin123'},
    'manager': {'id': '2', 'password': 'manager123'},
}

@login_manager.user_loader
def load_user(user_id):
    for username, data in USERS.items():
        if data['id'] == user_id:
            return User(user_id, username)
    return None

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            expiry_date TEXT NOT NULL,
            added_date TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notification_history (
            id SERIAL PRIMARY KEY,
            sent_at TEXT NOT NULL,
            expired_count INTEGER NOT NULL,
            near_expiry_count INTEGER NOT NULL,
            total_products INTEGER NOT NULL
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def get_status(expiry_date_str):
    today = date.today()
    expiry = date.fromisoformat(expiry_date_str)
    diff = (expiry - today).days
    if diff < 0:
        return 'Expired'
    elif diff <= 7:
        return 'Near Expiry'
    else:
        return 'Safe'

def get_days_left(expiry_date_str):
    today = date.today()
    expiry = date.fromisoformat(expiry_date_str)
    return (expiry - today).days

def send_alert_email(near_expiry_products, expired_products):
    try:
        msg = Message(
            subject='Expiry Tracker Alert — Products Need Attention',
            recipients=['Mohammed2.Amjadali@live.uwe.ac.uk']
        )
        body = "Hello,\n\nThis is an automated alert from your Expiry Tracker system.\n\n"
        if expired_products:
            body += "EXPIRED PRODUCTS (remove immediately):\n"
            body += "-" * 40 + "\n"
            for p in expired_products:
                body += f"  - {p['name']} ({p['category']}) | Qty: {p['quantity']} | Expired: {p['expiry_date']}\n"
            body += "\n"
        if near_expiry_products:
            body += "NEAR EXPIRY PRODUCTS (within 7 days):\n"
            body += "-" * 40 + "\n"
            for p in near_expiry_products:
                days = get_days_left(p['expiry_date'])
                body += f"  - {p['name']} ({p['category']}) | Qty: {p['quantity']} | Expires in {days} day(s) on {p['expiry_date']}\n"
            body += "\n"
        body += "Please log in to your Expiry Tracker to take action.\n"
        body += "https://expiry-tracker-q5w6.onrender.com\n\n"
        body += "— Expiry Tracker System"
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if username in USERS and USERS[username]['password'] == password:
            user = User(USERS[username]['id'], username)
            login_user(user)
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM products ORDER BY expiry_date ASC')
    products = cur.fetchall()
    cur.close()
    conn.close()
    products_with_status = []
    total = len(products)
    safe = near = expired = 0
    for p in products:
        status = get_status(p['expiry_date'])
        days = get_days_left(p['expiry_date'])
        product_dict = dict(p)
        product_dict['status'] = status
        product_dict['days_left'] = days
        products_with_status.append(product_dict)
        if status == 'Safe': safe += 1
        elif status == 'Near Expiry': near += 1
        else: expired += 1
    return render_template('dashboard.html',
        products=products_with_status,
        total=total, safe=safe, near=near, expired=expired)

@app.route('/send-alerts')
@login_required
def send_alerts():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM products')
    products = cur.fetchall()
    cur.close()
    conn.close()
    near_expiry = []
    expired = []
    for p in products:
        status = get_status(p['expiry_date'])
        if status == 'Near Expiry':
            near_expiry.append(dict(p))
        elif status == 'Expired':
            expired.append(dict(p))
    if not near_expiry and not expired:
        flash('No near-expiry or expired products found. No email sent.', 'success')
        return redirect(url_for('dashboard'))
    success = send_alert_email(near_expiry, expired)
    if success:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO notification_history (sent_at, expired_count, near_expiry_count, total_products) VALUES (%s, %s, %s, %s)',
            (date.today().isoformat(), len(expired), len(near_expiry), len(products))
        )
        conn.commit()
        cur.close()
        conn.close()
        flash(f'Alert email sent! ({len(expired)} expired, {len(near_expiry)} near expiry)', 'success')
    else:
        flash('Failed to send email. Please check your email settings.', 'error')
    return redirect(url_for('dashboard'))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    prefill_date = request.args.get('date', '')
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category'].strip()
        quantity = request.form['quantity']
        expiry_date = request.form['expiry_date']
        if not name or not category or not quantity or not expiry_date:
            flash('All fields are required.', 'error')
            return redirect(url_for('add_product'))
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO products (name, category, quantity, expiry_date, added_date) VALUES (%s, %s, %s, %s, %s)',
            (name, category, int(quantity), expiry_date, date.today().isoformat())
        )
        conn.commit()
        cur.close()
        conn.close()
        flash(f'"{name}" added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_product.html', prefill_date=prefill_date)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM products WHERE id = %s', (id,))
    product = cur.fetchone()
    if not product:
        cur.close()
        conn.close()
        flash('Product not found.', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category'].strip()
        quantity = request.form['quantity']
        expiry_date = request.form['expiry_date']
        cur.execute(
            'UPDATE products SET name=%s, category=%s, quantity=%s, expiry_date=%s WHERE id=%s',
            (name, category, int(quantity), expiry_date, id)
        )
        conn.commit()
        cur.close()
        conn.close()
        flash(f'"{name}" updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    cur.close()
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT name FROM products WHERE id = %s', (id,))
    product = cur.fetchone()
    if product:
        cur.execute('DELETE FROM products WHERE id = %s', (id,))
        conn.commit()
        flash(f'"{product["name"]}" deleted.', 'success')
    cur.close()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/notifications')
@login_required
def notifications():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM notification_history ORDER BY sent_at DESC')
    history = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('notifications.html', history=history)

@app.route('/reports')
@login_required
def reports():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM products ORDER BY expiry_date ASC')
    products = cur.fetchall()
    cur.close()
    conn.close()
    products_with_status = []
    safe = near = expired = 0
    category_counts = {}
    for p in products:
        status = get_status(p['expiry_date'])
        days = get_days_left(p['expiry_date'])
        product_dict = dict(p)
        product_dict['status'] = status
        product_dict['days_left'] = days
        products_with_status.append(product_dict)
        if status == 'Safe': safe += 1
        elif status == 'Near Expiry': near += 1
        else: expired += 1
        cat = p['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1
    return render_template('reports.html',
        products=products_with_status,
        safe=safe, near=near, expired=expired,
        total=len(products),
        category_counts=category_counts)

@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_product():
    detected_date = None
    error = None
    if request.method == 'POST':
        if 'image' not in request.files:
            error = 'No image uploaded.'
        else:
            file = request.files['image']
            if file.filename == '':
                error = 'No image selected.'
            else:
                try:
                    img = Image.open(file.stream)
                    text = pytesseract.image_to_string(img)
                    text_upper = text.upper()

                    MONTHS = {
                        "JAN":"01","FEB":"02","MAR":"03","APR":"04",
                        "MAY":"05","JUN":"06","JUL":"07","AUG":"08",
                        "SEP":"09","OCT":"10","NOV":"11","DEC":"12"
                    }

                    # Format 1: DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
                    m = re.search(r'\b(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})\b', text)
                    if m:
                        detected_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

                    # Format 2: YYYY/MM/DD or YYYY-MM-DD
                    if not detected_date:
                        m = re.search(r'\b(\d{4})[/\-\.](\d{2})[/\-\.](\d{2})\b', text)
                        if m:
                            detected_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

                    # Format 3: DD/MM/YY or DD-MM-YY
                    if not detected_date:
                        m = re.search(r'\b(\d{2})[/\-\.](\d{2})[/\-\.](\d{2})\b', text)
                        if m:
                            detected_date = f"20{m.group(3)}-{m.group(2)}-{m.group(1)}"

                    # Format 4: MM/YYYY or MM-YYYY (e.g. 06/2026)
                    if not detected_date:
                        m = re.search(r'\b(\d{2})[/\-](\d{4})\b', text)
                        if m:
                            detected_date = f"{m.group(2)}-{m.group(1)}-01"

                    # Format 5: MMM DD YYYY or MMM DD YY (e.g. JUN 28 2026 or JUN 28 26)
                    if not detected_date:
                        m = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})\s+(\d{2,4})', text_upper)
                        if m:
                            month = MONTHS[m.group(1)]
                            day = m.group(2).zfill(2)
                            year = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
                            detected_date = f"{year}-{month}-{day}"

                    # Format 6: DD MMM YYYY or DD MMM YY (e.g. 28 JUN 2026)
                    if not detected_date:
                        m = re.search(r'(\d{1,2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{2,4})', text_upper)
                        if m:
                            month = MONTHS[m.group(2)]
                            day = m.group(1).zfill(2)
                            year = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
                            detected_date = f"{year}-{month}-{day}"

                    # Format 7: MMM YYYY (e.g. JUN 2026)
                    if not detected_date:
                        m = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{4})', text_upper)
                        if m:
                            month = MONTHS[m.group(1)]
                            year = m.group(2)
                            detected_date = f"{year}-{month}-01"

                    # Format 8: YYYY MM DD (e.g. 2026 06 28)
                    if not detected_date:
                        m = re.search(r'\b(\d{4})\s+(\d{2})\s+(\d{2})\b', text)
                        if m:
                            detected_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

                    if not detected_date:
                        error = 'No expiry date found in image. Please enter the date manually.'

                except Exception as e:
                    error = f'Error processing image: {str(e)}'
    return render_template('scan.html', detected_date=detected_date, error=error)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')

init_db()
