"""
Image upload and management routes
"""
import os
import uuid
from pathlib import Path
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from PIL import Image as PILImage
from PIL.ExifTags import TAGS
from app.image import image_bp
from app.models import Image, Tag
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


def generate_automatic_tags(image_obj):
    """
    Generate automatic tags based on image metadata
    Creates tags for: year, resolution classification
    """
    tags_to_create = []
    
    try:
        # Generate year tag from shoot_time or current year
        if image_obj.shoot_time:
            year_tag = f"{image_obj.shoot_time.year}年"
        else:
            year_tag = f"{datetime.now().year}年"
        
        # Check if year tag already exists for this image
        year_tag_exists = Tag.query.filter_by(image_id=image_obj.id, tag_content=year_tag).first()
        if not year_tag_exists:
            tags_to_create.append(Tag(image_id=image_obj.id, tag_content=year_tag))
        
        # Generate resolution classification tag
        if image_obj.resolution:
            try:
                width, height = map(int, image_obj.resolution.split('x'))
                # Classification: 4K -> 3840x2160, 高清 -> 1920x1080+, 标清 -> others
                if width >= 3840 and height >= 2160:
                    resolution_tag = "4K"
                elif width >= 1920 and height >= 1080:
                    resolution_tag = "高清"
                else:
                    resolution_tag = "标清"
                
                # Check if resolution tag already exists
                res_tag_exists = Tag.query.filter_by(image_id=image_obj.id, tag_content=resolution_tag).first()
                if not res_tag_exists:
                    tags_to_create.append(Tag(image_id=image_obj.id, tag_content=resolution_tag))
            except (ValueError, TypeError):
                # If resolution parsing fails, skip this tag
                pass
        
        # Bulk insert all tags
        if tags_to_create:
            db.session.bulk_save_objects(tags_to_create)
            db.session.commit()
        
        return True
    
    except Exception as e:
        # Log error but don't fail the upload
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
        
        # Generate automatic tags after image is saved
        generate_automatic_tags(image)
        
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


@image_bp.route('/detail/<int:image_id>')
@login_required
def detail(image_id):
    """Display image detail page"""
    image = Image.query.get_or_404(image_id)
    
    # Verify ownership
    if image.user_id != current_user.id:
        flash('无权访问此图片', 'danger')
        return redirect(url_for('image.gallery'))
    
    return render_template('image/detail.html', image=image)


@image_bp.route('/api/tag/add', methods=['POST'])
@login_required
def add_tag():
    """Add a tag to image"""
    data = request.get_json()
    image_id = data.get('image_id')
    tag_content = data.get('tag_content', '').strip()
    
    if not image_id or not tag_content:
        return jsonify({'success': False, 'error': '参数不完整'}), 400
    
    # Verify image ownership
    image = Image.query.get_or_404(image_id)
    if image.user_id != current_user.id:
        return jsonify({'success': False, 'error': '无权操作'}), 403
    
    # Check if tag already exists
    existing_tag = Tag.query.filter_by(image_id=image_id, tag_content=tag_content).first()
    if existing_tag:
        return jsonify({'success': False, 'error': '标签已存在'}), 400
    
    try:
        tag = Tag(image_id=image_id, tag_content=tag_content)
        db.session.add(tag)
        db.session.commit()
        return jsonify({
            'success': True,
            'tag_id': tag.id,
            'tag_content': tag.tag_content,
            'message': '标签添加成功'
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': '添加失败'}), 500


@image_bp.route('/api/tag/remove/<int:tag_id>', methods=['DELETE', 'POST'])
@login_required
def remove_tag(tag_id):
    """Remove a tag from image"""
    tag = Tag.query.get_or_404(tag_id)
    image = tag.image
    
    # Verify ownership
    if image.user_id != current_user.id:
        return jsonify({'success': False, 'error': '无权操作'}), 403
    
    try:
        db.session.delete(tag)
        db.session.commit()
        return jsonify({'success': True, 'message': '标签删除成功'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': '删除失败'}), 500


@image_bp.route('/api/<int:image_id>/edit', methods=['POST'])
@login_required
def edit_image(image_id):
    """Edit image (rotation)"""
    image = Image.query.get_or_404(image_id)
    
    # Verify ownership
    if image.user_id != current_user.id:
        return jsonify({'success': False, 'error': '无权操作'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据无效'}), 400
    
    edit_type = data.get('edit_type')
    
    if not edit_type or edit_type not in ['rotate_90', 'rotate_180', 'rotate_270']:
        return jsonify({'success': False, 'error': '不支持的编辑类型'}), 400
    
    try:
        # Load original image
        image_full_path = Path(current_app.static_folder) / image.image_path
        pil_image = PILImage.open(image_full_path)
        
        # Apply rotation
        rotation_angles = {
            'rotate_90': 270,      # PIL rotates counter-clockwise
            'rotate_180': 180,
            'rotate_270': 90
        }
        angle = rotation_angles[edit_type]
        rotated_image = pil_image.rotate(angle, expand=True)
        
        # Save rotated image back to original path
        if rotated_image.mode in ('RGBA', 'P'):
            rotated_image = rotated_image.convert('RGB')
        rotated_image.save(str(image_full_path), quality=95)
        
        # Regenerate thumbnail
        thumb_full_path = Path(current_app.static_folder) / image.thumbnail_path
        generate_thumbnail(str(image_full_path), str(thumb_full_path))
        
        # Update resolution if image was rotated 90 or 270 degrees
        if edit_type in ['rotate_90', 'rotate_270']:
            new_width, new_height = rotated_image.size
            image.resolution = f"{new_width}x{new_height}"
            db.session.commit()
        
        return jsonify({'success': True, 'message': '编辑成功'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@image_bp.route('/api/<int:image_id>/delete', methods=['DELETE', 'POST'])
@login_required
def delete_image(image_id):
    """Delete image and associated files"""
    image = Image.query.get_or_404(image_id)
    
    # Verify ownership
    if image.user_id != current_user.id:
        return jsonify({'success': False, 'error': '无权操作'}), 403
    
    try:
        # Delete image files
        original_path = Path(current_app.static_folder) / image.image_path
        thumb_path = Path(current_app.static_folder) / image.thumbnail_path
        
        if original_path.exists():
            original_path.unlink()
        if thumb_path.exists():
            thumb_path.unlink()
        
        # Delete database record (cascade will delete related tags)
        db.session.delete(image)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '删除成功'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@image_bp.route('/search')
def search():
    """Search page"""
    return render_template('image/search.html')


@image_bp.route('/search_results')
@login_required
def search_results():
    """Search results page"""
    tag = request.args.get('tag', '').strip()
    date_start = request.args.get('date_start', '')
    date_end = request.args.get('date_end', '')
    
    # Build base query for current user's images
    query = Image.query.filter_by(user_id=current_user.id)
    
    # Filter by tag if provided
    if tag:
        query = query.join(Tag).filter(Tag.tag_content.ilike(f"%{tag}%")).distinct()
    
    # Filter by date range if provided
    if date_start:
        try:
            start_date = datetime.strptime(date_start, '%Y-%m-%d').date()
            query = query.filter(Image.shoot_time >= start_date)
        except ValueError:
            pass
    
    if date_end:
        try:
            end_date = datetime.strptime(date_end, '%Y-%m-%d').date()
            # Add 1 day to include images shot on end_date
            from datetime import timedelta
            end_date = end_date + timedelta(days=1)
            query = query.filter(Image.shoot_time < end_date)
        except ValueError:
            pass
    
    # Order by upload time descending
    images = query.order_by(Image.upload_time.desc()).all()
    
    return render_template('image/search_results.html', images=images, tag=tag, date_start=date_start, date_end=date_end)
