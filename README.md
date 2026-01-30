# E-commerce Platform

A lightweight Flask-based e-commerce web application with user authentication, product catalog, shopping cart functionality, and transaction history tracking.

## 🎯 Features

- **User Authentication**: Secure login/logout system with session management
- **Product Catalog**: Browse available products with pricing information
- **Purchase System**: Buy products with real-time balance updates
- **Transaction History**: Track all purchase activities
- **Balance Management**: Monitor account balance and spending
- **Responsive UI**: Bootstrap-powered responsive design for all devices
- **Flash Messaging**: Real-time feedback for user actions (success/error notifications)

## 🛠️ Technologies Used

**Backend:**
- Python 3.x
- Flask (Web Framework)
- Flask-Bootstrap (UI Framework Integration)
- Session-based Authentication

**Frontend:**
- HTML5/Jinja2 Templates
- Bootstrap 4.0.0
- CSS3

## 📋 Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ecommerce-platform.git
   cd ecommerce-platform
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install flask flask-bootstrap
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   - Open your browser and navigate to `http://127.0.0.1:5000`
   - Default credentials: `username: user1`, `password: password`

## 📁 Project Structure

```
ecommerce-platform/
│
├── app.py                     # Main application file with routes and logic
│
├── templates/
│   ├── base.html             # Base template with navbar and layout
│   ├── index.html            # Landing/home page
│   ├── login.html            # Login form
│   └── dashboard.html        # User dashboard with products and transactions
│
└── README.md                 # Project documentation
```

## 🌐 Application Routes

### Public Routes
- `GET /` - Home page
- `GET /login` - Login page
- `POST /login` - Process login credentials

### Protected Routes (Requires Authentication)
- `GET /dashboard` - User dashboard with products and balance
- `POST /dashboard` - Process product purchases
- `GET /logout` - Logout and clear session

## 💻 Usage

### Default User Credentials
```
Username: user1
Password: password
Starting Balance: $100
```

### Available Products
- **Product A**: $20
- **Product B**: $15

### Making a Purchase

1. Log in with the default credentials
2. View your current balance on the dashboard
3. Browse available products in the product table
4. Click the "Buy" button next to any product
5. The system will:
   - Check if you have sufficient balance
   - Deduct the product price from your balance
   - Add the transaction to your history
   - Display a success or error message

## 🔐 Security Features

- Session-based authentication
- Password verification before granting access
- Protected routes requiring login
- Flash messages for user feedback
- Balance validation before purchases

## 📊 Data Models

### User Model
```python
{
    'username': str,    # Unique username
    'password': str,    # User password (plain text - for demo only)
    'balance': float    # Account balance
}
```

### Product Model
```python
{
    'id': int,         # Unique product identifier
    'name': str,       # Product name
    'price': float     # Product price
}
```

### Transaction Model
```python
"username bought product_name for $price"  # Transaction string
```

## 🎨 User Interface

### Pages

1. **Home Page** (`/`)
   - Welcome message
   - Login link

2. **Login Page** (`/login`)
   - Username input field
   - Password input field
   - Login button
   - Error messages for invalid credentials

3. **Dashboard** (`/dashboard`)
   - User welcome message
   - Current balance display
   - Product table with:
     - Product name
     - Product price
     - Buy button
   - Transaction history list

## 🚀 Future Enhancements

- [ ] User registration functionality
- [ ] Database integration (SQLite/PostgreSQL)
- [ ] Password hashing and encryption
- [ ] Shopping cart with multiple items
- [ ] Product categories and search
- [ ] Admin panel for product management
- [ ] Payment gateway integration
- [ ] Order management system
- [ ] User profile editing
- [ ] Product images and detailed descriptions
- [ ] Wishlist functionality
- [ ] Product reviews and ratings

## 🛠️ Development

To run in development mode:

```bash
export FLASK_ENV=development  # On Windows: set FLASK_ENV=development
python app.py
```

## 📝 License

This project is created for educational purposes.

