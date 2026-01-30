from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bootstrap import Bootstrap

app = Flask(__name__)
app.secret_key = 'secret'
Bootstrap(app)

# In-memory data
users = [{'username': 'user1', 'password': 'password', 'balance': 100}]
products = [{'id': 1, 'name': 'Product A', 'price': 20},
            {'id': 2, 'name': 'Product B', 'price': 15}]
transactions = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = next((u for u in users if u['username'] == username and u['password'] == password), None)
        if user:
            session['user'] = user
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    
    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        product = next((p for p in products if p['id'] == product_id), None)
        
        if product and user['balance'] >= product['price']:
            user['balance'] -= product['price']
            transactions.append(f"{user['username']} bought {product['name']} for ${product['price']}")
            flash('Purchase successful!', 'success')
        else:
            flash('Insufficient balance', 'danger')
    
    return render_template('dashboard.html', user=user, products=products, transactions=transactions)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
