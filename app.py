from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mail import Mail, Message
from datetime import date
import sqlite3

app = Flask(__name__)
app.secret_key = 'expiry-tracker-secret-key'
DB = 'expiry.db'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'akramamjadali7@gmail.com'
app.config['MAIL_PASSWORD'] = 'soyj gyhv uylj npke'
app.config['MAIL_DEFAULT_SENDER'] = 'akramamjadali7@gmail.com'

mail = Mail(app)

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            expiry_date TEXT NOT NULL,
            added_date TEXT NOT NULL
        )
    ''')
    conn.commit()
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

@app.route('/')
def dashboard():
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY expiry_date ASC').fetchall()
    conn.close()
    products_with_status = []
    total = len(products)
    safe = near = expired = 0
    for p in products:
        status = get_status(p['expiry_date'])
        days = get_days_left(p['expiry_date'])
        products_with_status.append(dict(p) | {'status': status, 'days_left': days})
        if status == 'Safe': safe += 1
        elif status == 'Near Expiry': near += 1
        else: expired += 1
    return render_template('dashboard.html',
        products=products_with_status,
        total=total, safe=safe, near=near, expired=expired)

@app.route('/send-alerts')
def send_alerts():
    conn = get_db()
    products = conn.execute('SELECT * FROM products').fetchall()
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
        flash(f'Alert email sent! ({len(expired)} expired, {len(near_expiry)} near expiry)', 'success')
    else:
        flash('Failed to send email. Please check your email settings.', 'error')
    return redirect(url_for('dashboard'))

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category'].strip()
        quantity = request.form['quantity']
        expiry_date = request.form['expiry_date']
        if not name or not category or not quantity or not expiry_date:
            flash('All fields are required.', 'error')
            return redirect(url_for('add_product'))
        conn = get_db()
        conn.execute(
            'INSERT INTO products (name, category, quantity, expiry_date, added_date) VALUES (?, ?, ?, ?, ?)',
            (name, category, int(quantity), expiry_date, date.today().isoformat())
        )
        conn.commit()
        conn.close()
        flash(f'"{name}" added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_product.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    if not product:
        conn.close()
        flash('Product not found.', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category'].strip()
        quantity = request.form['quantity']
        expiry_date = request.form['expiry_date']
        conn.execute(
            'UPDATE products SET name=?, category=?, quantity=?, expiry_date=? WHERE id=?',
            (name, category, int(quantity), expiry_date, id)
        )
        conn.commit()
        conn.close()
        flash(f'"{name}" updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_product(id):
    conn = get_db()
    product = conn.execute('SELECT name FROM products WHERE id = ?', (id,)).fetchone()
    if product:
        conn.execute('DELETE FROM products WHERE id = ?', (id,))
        conn.commit()
        flash(f'"{product["name"]}" deleted.', 'success')
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

init_db()