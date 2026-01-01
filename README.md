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

### Tag System
- **Automatic Tag Generation**: Tags created on image upload:
  - Year tag: Based on shoot time or current year (e.g., "2024年", "2025年")
  - Resolution tag: Classification ("4K", "高清", "标清")
- **Manual Tag Management**:
  - Add custom tags to images
  - Remove tags from images
- **Tag-based Search**: Find images by tag content (supports fuzzy matching)

### Image Detail & Editing
- **Image Detail Page**: View full-size image with all metadata and tags
- **Image Rotation**: Rotate images 90°, 180°, 270° (clockwise/counterclockwise)
- **Image Deletion**: Delete images with automatic cleanup of files and related tags

### Advanced Search
- **Search by Tag**: Filter images by tag keywords
- **Search by Date Range**: Filter images by shoot time range
- **Combined Search**: Use tag and date filters together for precise results
- **Search Results**: Display matching images with thumbnails and metadata

## Database Schema

### User Table
- `id`: User ID (BIGINT, PK, auto-increment)
- `username`: Unique username (VARCHAR 50)
- `email`: Unique email address (VARCHAR 100)
- `password_hash`: Hashed password (VARCHAR 255)
- `register_time`: Registration timestamp (DATETIME)

### Image Table
- `id`: Image ID (BIGINT, PK, auto-increment)
- `user_id`: Foreign key to User (BIGINT, FK with CASCADE)
- `image_path`: Path to original image (VARCHAR 512)
- `thumbnail_path`: Path to thumbnail (VARCHAR 512)
- `upload_time`: Upload timestamp (DATETIME)
- `shoot_time`: Photo shoot time from EXIF (DATETIME, nullable)
- `shoot_location`: GPS location from EXIF (VARCHAR 200, nullable)
- `resolution`: Image resolution in WxH format (VARCHAR 50, nullable)

### Tag Table
- `id`: Tag ID (BIGINT, PK, auto-increment)
- `image_id`: Foreign key to Image (BIGINT, FK with CASCADE)
- `tag_content`: Tag content (VARCHAR 50, indexed)

## API Endpoints

### Tag Management
- `POST /api/tag/add`: Add a tag to image
  - Parameters: `image_id`, `tag_content`
  - Returns: JSON with success status and tag details
  
- `DELETE /api/tag/remove/<tag_id>`: Remove a tag
  - Returns: JSON with success status

### Image Editing
- `POST /api/image/<image_id>/edit`: Edit image (rotation)
  - Parameters: `edit_type` (rotate_90, rotate_180, rotate_270)
  - Returns: JSON with success status

- `DELETE /api/image/<image_id>/delete`: Delete image and files
  - Returns: JSON with success status

## Routes

- `GET /`: Home page
- `GET /auth/register`: Registration page
- `POST /auth/register`: Submit registration
- `GET /auth/login`: Login page
- `POST /auth/login`: Submit login
- `GET /auth/logout`: Logout
- `GET /image/upload`: Upload image page
- `POST /image/upload`: Submit image upload
- `GET /image/gallery`: View user's image gallery
- `GET /image/detail/<image_id>`: View image details
- `GET /image/search`: Search page
- `GET /image/search_results`: Display search results

## Usage Examples

### Register and Login
1. Visit `http://localhost:5000/auth/register`
2. Create account with username, email, and strong password
3. Login at `http://localhost:5000/auth/login`

### Upload and Manage Images
1. Click "上传" (Upload) in navbar
2. Select an image file
3. System automatically:
   - Extracts EXIF metadata
   - Generates thumbnail
   - Creates year and resolution tags
4. View image in gallery with all tags
5. Click on image to view details and manage tags

### Search Images
1. Click "搜索" (Search) in navbar
2. Enter tag keyword (e.g., "高清", "2024年")
3. Optionally set date range
4. System returns matching images

