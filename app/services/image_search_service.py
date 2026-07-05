"""
Shared image search helpers for the web UI and agent tools.
"""
from datetime import datetime
from typing import Any, Dict, List

from flask import url_for
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from app.models import Image, Tag


def search_images_for_user(user_id: int, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Search the current user's images by location, tags, and year."""
    query = Image.query.filter(Image.user_id == user_id)

    location = str(params.get('location', '') or '').strip()
    if location:
        query = query.filter(Image.shoot_location.ilike(f"%{location}%"))

    tags: List[str] = params.get('tags') or []
    cleaned_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    if cleaned_tags:
        tag_filters = [Tag.tag_content.ilike(f"%{tag}%") for tag in cleaned_tags]
        query = query.join(Tag).filter(or_(*tag_filters)).distinct()

    year_raw = str(params.get('year', '') or '').strip()
    if year_raw:
        try:
            year_int = int(year_raw)
            start_dt = datetime(year_int, 1, 1)
            end_dt = datetime(year_int + 1, 1, 1)
            year_tag = f"{year_int}年"
            query = query.filter(
                or_(
                    and_(Image.shoot_time >= start_dt, Image.shoot_time < end_dt),
                    Image.tags.any(Tag.tag_content == year_tag),
                )
            )
        except ValueError:
            pass

    images = (
        query.options(joinedload(Image.tags))
        .order_by(Image.upload_time.desc())
        .all()
    )

    return [
        {
            'id': image.id,
            'thumbnail_url': url_for('static', filename=image.thumbnail_path, _external=False),
            'tags': [tag.tag_content for tag in image.tags],
            'shoot_location': image.shoot_location,
            'shoot_time': image.shoot_time.isoformat() if image.shoot_time else None,
        }
        for image in images
    ]
