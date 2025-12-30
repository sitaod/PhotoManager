# Photo Manager

A B/S architecture photo management system built with Flask and MySQL.

## Project Structure

```
PhotoManager/
├── app/
│   ├── __init__.py              # Flask application factory
│   ├── models.py                # Database models
│   ├── main_routes.py           # Main page routes
│   ├── auth/                    # Authentication blueprint
│   │   ├── __init__.py
│   │   └── routes.py            # Registration, login, logout logic
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html            # Base template
│   │   ├── index.html           # Home page
│   │   └── auth/
│   │       ├── login.html       # Login page
│   │       └── register.html    # Registration page
│   └── static/                  # Static assets
│       ├── css/
│       └── js/
├── config.py                    # Configuration file
├── run.py                       # Application entry point
├── init_db.py                   # Database initialization script
├── requirements.txt             # Python dependencies
└── README.md                    # Project documentation
```

## Tech Stack

- **Backend**: Python 3.x + Flask 3.0
- **Database**: MySQL 8.0 + SQLAlchemy ORM
- **Frontend**: HTML5 + Bootstrap 5 + Vue.js (CDN)
- **Authentication**: Flask-Login

## Setup & Installation

### 1. Create Virtual Environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Database

Make sure MySQL is running and update `config.py` with your database credentials:

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://username:password@host:port/database_name'
```

### 4. Initialize Database

```bash
python init_db.py
```

This will create all necessary tables in the database.

### 5. Run Application

```bash
python run.py
```

The application will be available at `http://localhost:5000`

