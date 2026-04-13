from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, timedelta
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'expiry-tracker-secret-key'
DB = 'expiry.db'

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
