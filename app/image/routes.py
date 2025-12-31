"""
Image upload and management routes
"""
import os
import uuid
from pathlib import Path
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from PIL import Image as PILImage
from PIL.ExifTags import TAGS
from app.image import image_bp
from app.models import Image
from app import db


# Base paths (absolute) to avoid issues with non-ASCII filenames and working directory changes
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
ORIGINALS_FOLDER = UPLOAD_FOLDER / 'originals'
THUMBNAILS_FOLDER = UPLOAD_FOLDER / 'thumbnails'

# Create directories if they don't exist
ORIGINALS_FOLDER.mkdir(parents=True, exist_ok=True)
THUMBNAILS_FOLDER.mkdir(parents=True, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_exif_data(image_path):
    """
    Extract EXIF data from image
    Returns: (shoot_time, shoot_location)
    """
    shoot_time = None
    shoot_location = None
    
    try:
        image = PILImage.open(image_path)
        exif_data = image._getexif()
        
        if exif_data is None:
            return None, None
        
        # Parse EXIF tags
        exif_dict = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            exif_dict[tag_name] = value
        
        # Extract shoot time (DateTime tag 306)
        if 'DateTime' in exif_dict:
            try:
                shoot_time = datetime.strptime(exif_dict['DateTime'], '%Y:%m:%d %H:%M:%S')
            except (ValueError, TypeError):
                pass
        
        # Extract GPS info (GPSInfo tag 34853)
        if 'GPSInfo' in exif_dict:
            try:
                gps_data = exif_dict['GPSInfo']
                # Simple latitude/longitude extraction
                if len(gps_data) > 4:
                    # Format: latitude, longitude as string
                    shoot_location = f"GPS: {gps_data}"
            except (ValueError, TypeError, IndexError):
                pass
    
    except Exception as e:
        # Silently handle EXIF parsing errors
        pass
    
    return shoot_time, shoot_location


def get_image_resolution(image_path):
    """
    Get image resolution (width x height)
    Returns: resolution string like "1920x1080"
    """
    try:
        image = PILImage.open(image_path)
        width, height = image.size
        return f"{width}x{height}"
    except Exception as e:
        return None


def generate_thumbnail(source_path, thumb_path, max_size=400):
    """
    Generate thumbnail image
    Scales image to max 400px on longest side while maintaining aspect ratio
    """
    try:
        image = PILImage.open(source_path)
        # Convert to RGB to avoid saving issues for images with alpha channels
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        image.thumbnail((max_size, max_size), PILImage.Resampling.LANCZOS)
        image.save(thumb_path, 'JPEG', quality=85)
        return True
    except Exception as e:
        return False


@image_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload image page and handler"""
    
    if request.method == 'GET':
        return render_template('image/upload.html')
    
    # Handle POST request
    if 'file' not in request.files:
        flash('请选择一个文件', 'danger')
        return render_template('image/upload.html')
    
    file = request.files['file']
    
    if file.filename == '':
        flash('请选择一个文件', 'danger')
        return render_template('image/upload.html')
    
    if not allowed_file(file.filename):
        flash('不支持的文件类型。支持的格式：JPG, PNG, GIF, BMP, WebP', 'danger')
        return render_template('image/upload.html')
    
    try:
        # Generate unique filename using UUID
        if '.' in file.filename:
            file_extension = file.filename.rsplit('.', 1)[1].lower()
        else:
            file_extension = 'jpg'  # fallback for filenames without extension
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Save original image (absolute path to avoid encoding issues)
        original_path = ORIGINALS_FOLDER / unique_filename
        file.save(str(original_path))
        
        # Extract EXIF data
        shoot_time, shoot_location = extract_exif_data(original_path)
        
        # Get image resolution
        resolution = get_image_resolution(original_path)
        
        # Generate thumbnail
        thumb_filename = f"{uuid.uuid4()}.jpg"
        thumb_path = THUMBNAILS_FOLDER / thumb_filename
        generate_thumbnail(str(original_path), str(thumb_path))
        
        # Store relative paths for database
        relative_original = f"uploads/originals/{unique_filename}"
        relative_thumb = f"uploads/thumbnails/{thumb_filename}"
        
        # Create Image record in database
        image = Image(
            user_id=current_user.id,
            image_path=relative_original,
            thumbnail_path=relative_thumb,
            shoot_time=shoot_time,
            shoot_location=shoot_location,
            resolution=resolution
        )
        
        db.session.add(image)
        db.session.commit()
        
        flash('图片上传成功！', 'success')
        return redirect(url_for('image.gallery'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'上传失败：{str(e)}', 'danger')
        return render_template('image/upload.html')


@image_bp.route('/gallery')
@login_required
def gallery():
    """Display user's images"""
    images = Image.query.filter_by(user_id=current_user.id).order_by(Image.upload_time.desc()).all()
    return render_template('image/gallery.html', images=images)
