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

## Features

### User Authentication
- User registration with email validation
- Password complexity validation (length > 6, at least 2 character types)
- User login (supports username or email)
- Session management with Flask-Login
- User logout

### Image Management
- **Image Upload**: Upload images with unique UUID-based filenames
- **EXIF Extraction**: Automatically extract photo metadata:
  - Shoot time (from EXIF DateTime)
  - GPS location (from EXIF GPS info)
- **Resolution Detection**: Capture image dimensions (format: WxH)
- **Thumbnail Generation**: Auto-generate thumbnails (max 400px)
- **Image Gallery**: Responsive grid display of uploaded images
  - Mobile: 2-3 columns
  - Desktop: 4-6 columns
- **Metadata Display**: Show upload time, shoot time, resolution, location

## Database Schema

### User Table
- `id`: User ID
- `username`: Unique username
- `email`: Unique email address
- `password_hash`: Hashed password
- `register_time`: Registration timestamp

### Image Table
- `id`: Image ID
- `user_id`: Foreign key to User
- `image_path`: Path to original image
- `thumbnail_path`: Path to thumbnail
- `upload_time`: Upload timestamp
- `shoot_time`: Photo shoot time (EXIF)
- `shoot_location`: GPS location (EXIF)
- `resolution`: Image resolution (WxH)

