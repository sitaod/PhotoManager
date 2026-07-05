"""
Semantic image search backed by SigLIP embeddings and Milvus HNSW.
"""
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from flask import current_app, url_for
from PIL import Image as PILImage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app import db
from app.models import Image, SemanticEmbeddingJob

_MILVUS_ALIAS = "photomanager_semantic"
_MODEL_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()


class SemanticSearchError(RuntimeError):
    """Raised when semantic search cannot run in the current environment."""


class SemanticSearchTransientError(SemanticSearchError):
    """Raised when retrying later is the right behavior."""


def _semantic_log(message: str) -> None:
    print(f"[SemanticSearch] {message}", flush=True)


def _get_config(name: str, default: Any = None) -> Any:
    return current_app.config.get(name, default)


def _import_ml_deps():
    try:
        import torch
        from transformers import AutoModel, AutoProcessor
    except ImportError as exc:
        raise SemanticSearchTransientError(
            "语义搜索需要安装 transformers、torch、sentencepiece 依赖。请先更新依赖并重启应用。"
        ) from exc
    return torch, AutoModel, AutoProcessor


def _import_milvus_deps():
    try:
        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
    except ImportError as exc:
        raise SemanticSearchTransientError(
            "语义搜索需要安装 pymilvus 依赖，并启动 Milvus 服务。请先更新依赖并重启应用。"
        ) from exc
    return Collection, CollectionSchema, DataType, FieldSchema, connections, utility


def _select_device(torch: Any, configured_device: str) -> str:
    if configured_device and configured_device != "auto":
        return configured_device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _to_device(inputs: Dict[str, Any], device: str) -> Dict[str, Any]:
    return {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in inputs.items()
    }


def _get_siglip_bundle() -> Dict[str, Any]:
    torch, AutoModel, AutoProcessor = _import_ml_deps()
    model_name = _get_config("SIGLIP_MODEL_NAME", "google/siglip-base-patch16-224")
    device = _select_device(torch, _get_config("SIGLIP_DEVICE", "auto"))
    cache_key = (model_name, device)

    if cache_key not in _MODEL_CACHE:
        _semantic_log(f"loading SigLIP model={model_name} device={device}")
        try:
            processor = AutoProcessor.from_pretrained(model_name)
            model = AutoModel.from_pretrained(model_name).to(device)
        except Exception as exc:
            raise SemanticSearchTransientError(f"加载 SigLIP 模型失败: {exc}") from exc
        model.eval()
        _MODEL_CACHE[cache_key] = {
            "torch": torch,
            "processor": processor,
            "model": model,
            "device": device,
        }
    return _MODEL_CACHE[cache_key]


def _feature_from_outputs(outputs: Any, attr_name: str) -> Any:
    if hasattr(outputs, attr_name):
        return getattr(outputs, attr_name)
    if isinstance(outputs, dict):
        if attr_name in outputs:
            return outputs[attr_name]
        if "pooler_output" in outputs:
            return outputs["pooler_output"]
        if "last_hidden_state" in outputs:
            return outputs["last_hidden_state"][:, 0]
    if hasattr(outputs, "pooler_output"):
        return outputs.pooler_output
    if hasattr(outputs, "last_hidden_state"):
        return outputs.last_hidden_state[:, 0]
    raise SemanticSearchError("SigLIP 模型输出中没有可用的 embedding。")


def _feature_tensor(outputs: Any, attr_name: str) -> Any:
    if hasattr(outputs, "float"):
        return outputs
    if isinstance(outputs, (tuple, list)) and outputs and hasattr(outputs[0], "float"):
        return outputs[0]
    return _feature_from_outputs(outputs, attr_name)


def _normalize(features: Any, torch: Any) -> Any:
    if not hasattr(features, "float"):
        raise SemanticSearchError(f"SigLIP embedding 不是 Tensor: {type(features).__name__}")
    features = features.float()
    return torch.nn.functional.normalize(features, p=2, dim=-1)


def _encode_text(query: str) -> List[float]:
    bundle = _get_siglip_bundle()
    torch = bundle["torch"]
    processor = bundle["processor"]
    model = bundle["model"]
    device = bundle["device"]

    inputs = processor(text=[query], padding="max_length", truncation=True, return_tensors="pt")
    inputs = _to_device(inputs, device)
    with torch.no_grad():
        if hasattr(model, "get_text_features"):
            features = _feature_tensor(model.get_text_features(**inputs), "text_embeds")
        else:
            features = _feature_tensor(model(**inputs), "text_embeds")
        features = _normalize(features, torch)
    return features[0].detach().cpu().numpy().astype("float32").tolist()


def _load_image(image_path: Path) -> Any:
    if not image_path.exists():
        raise SemanticSearchError(f"图片文件不存在: {image_path}")
    with PILImage.open(image_path) as image:
        return image.convert("RGB")


def _encode_image(image_path: Path) -> List[float]:
    bundle = _get_siglip_bundle()
    torch = bundle["torch"]
    processor = bundle["processor"]
    model = bundle["model"]
    device = bundle["device"]

    image = _load_image(image_path)
    inputs = processor(images=image, return_tensors="pt")
    inputs = _to_device(inputs, device)
    with torch.no_grad():
        if hasattr(model, "get_image_features"):
            features = _feature_tensor(model.get_image_features(**inputs), "image_embeds")
        else:
            features = _feature_tensor(model(**inputs), "image_embeds")
        features = _normalize(features, torch)
    return features[0].detach().cpu().numpy().astype("float32").tolist()


def _milvus_collection_name() -> str:
    return _get_config("MILVUS_COLLECTION", "photomanager_siglip_images")


def _connect_milvus() -> None:
    _, _, _, _, connections, _ = _import_milvus_deps()
    host = _get_config("MILVUS_HOST", "127.0.0.1")
    port = str(_get_config("MILVUS_PORT", "19530"))
    try:
        connections.connect(alias=_MILVUS_ALIAS, host=host, port=port)
    except Exception as exc:
        raise SemanticSearchTransientError(f"连接 Milvus 失败: {host}:{port} ({exc})") from exc


def _get_collection(dim: Optional[int] = None) -> Any:
    Collection, CollectionSchema, DataType, FieldSchema, _, utility = _import_milvus_deps()
    _connect_milvus()
    name = _milvus_collection_name()

    if utility.has_collection(name, using=_MILVUS_ALIAS):
        collection = Collection(name=name, using=_MILVUS_ALIAS)
        collection.load()
        return collection

    if dim is None:
        raise SemanticSearchError("创建 Milvus collection 需要传入 embedding 维度。")

    fields = [
        FieldSchema(name="image_id", dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="user_id", dtype=DataType.INT64),
        FieldSchema(name="image_path", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="thumbnail_path", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields=fields, description="PhotoManager SigLIP image embeddings")
    collection = Collection(name=name, schema=schema, using=_MILVUS_ALIAS)
    collection.create_index(
        field_name="embedding",
        index_params={
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {
                "M": int(_get_config("MILVUS_HNSW_M", 16)),
                "efConstruction": int(_get_config("MILVUS_HNSW_EF_CONSTRUCTION", 200)),
            },
        },
    )
    collection.load()
    _semantic_log(f"created Milvus collection={name} dim={dim} index=HNSW")
    return collection


def _get_existing_collection() -> Optional[Any]:
    Collection, _, _, _, _, utility = _import_milvus_deps()
    _connect_milvus()
    name = _milvus_collection_name()
    if not utility.has_collection(name, using=_MILVUS_ALIAS):
        return None
    collection = Collection(name=name, using=_MILVUS_ALIAS)
    collection.load()
    return collection


def _image_full_path(image: Image) -> Path:
    return Path(current_app.static_folder) / image.image_path


def _delete_from_collection(collection: Any, image_id: int) -> None:
    collection.delete(expr=f"image_id == {int(image_id)}")
    collection.flush()


def _index_image(image: Image) -> None:
    embedding = _encode_image(_image_full_path(image))
    collection = _get_collection(dim=len(embedding))
    _delete_from_collection(collection, int(image.id))
    collection.insert(
        [
            [int(image.id)],
            [int(image.user_id)],
            [image.image_path],
            [image.thumbnail_path],
            [embedding],
        ]
    )
    collection.flush()
    collection.load()
    _semantic_log(f"indexed image_id={image.id} user_id={image.user_id}")


def _ensure_queue_table() -> None:
    db.create_all()


def enqueue_image_for_embedding(image_id: int) -> None:
    """Add an image to the semantic embedding queue."""
    try:
        existing = SemanticEmbeddingJob.query.filter_by(image_id=int(image_id)).first()
        if existing:
            if existing.status == "done":
                existing.status = "pending"
                existing.attempts = 0
                existing.last_error = None
                existing.updated_at = datetime.now()
            db.session.commit()
            return

        db.session.add(SemanticEmbeddingJob(image_id=int(image_id), status="pending"))
        db.session.commit()
        _semantic_log(f"queued image_id={image_id} for embedding")
    except SQLAlchemyError:
        db.session.rollback()
        _ensure_queue_table()
        existing = SemanticEmbeddingJob.query.filter_by(image_id=int(image_id)).first()
        if not existing:
            db.session.add(SemanticEmbeddingJob(image_id=int(image_id), status="pending"))
        db.session.commit()
        _semantic_log(f"queued image_id={image_id} for embedding after creating queue table")


def enqueue_missing_semantic_embeddings() -> int:
    """Queue existing images that do not have a semantic embedding job yet."""
    reset_count = SemanticEmbeddingJob.query.filter_by(status="processing").update({"status": "pending"})
    compatibility_reset_count = 0
    for error_marker in ("BaseModelOutputWithPooling", "__version_info__"):
        compatibility_reset_count += (
            SemanticEmbeddingJob.query.filter(
                SemanticEmbeddingJob.status == "failed",
                SemanticEmbeddingJob.last_error.contains(error_marker),
            )
            .update(
                {"status": "pending", "attempts": 0, "last_error": None},
                synchronize_session=False,
            )
        )
    if reset_count or compatibility_reset_count:
        db.session.commit()
        if reset_count:
            _semantic_log(f"reset {reset_count} stale processing embedding jobs")
        if compatibility_reset_count:
            _semantic_log(f"reset {compatibility_reset_count} failed embedding jobs after compatibility fixes")

    existing_job_image_ids = {
        int(row.image_id)
        for row in SemanticEmbeddingJob.query.with_entities(SemanticEmbeddingJob.image_id).all()
    }
    images = Image.query.with_entities(Image.id).all()
    missing_ids = [int(image.id) for image in images if int(image.id) not in existing_job_image_ids]
    for image_id in missing_ids:
        db.session.add(SemanticEmbeddingJob(image_id=image_id, status="pending"))
    if missing_ids:
        db.session.commit()
        _semantic_log(f"queued {len(missing_ids)} existing images for semantic embedding")
    return len(missing_ids)


def process_pending_embedding_jobs(batch_size: Optional[int] = None) -> int:
    """Process a batch of queued semantic embedding jobs."""
    batch_size = batch_size or int(_get_config("SEMANTIC_INDEX_BATCH_SIZE", 2))
    max_attempts = int(_get_config("SEMANTIC_INDEX_MAX_ATTEMPTS", 3))
    jobs = (
        SemanticEmbeddingJob.query.filter(
            SemanticEmbeddingJob.status.in_(["pending", "failed"]),
            SemanticEmbeddingJob.attempts < max_attempts,
        )
        .order_by(SemanticEmbeddingJob.created_at.asc())
        .limit(batch_size)
        .all()
    )

    processed = 0
    for job in jobs:
        image = Image.query.get(job.image_id)
        if image is None:
            db.session.delete(job)
            db.session.commit()
            continue

        job.status = "processing"
        job.updated_at = datetime.now()
        db.session.commit()

        try:
            _index_image(image)
            job.status = "done"
            job.last_error = None
            job.updated_at = datetime.now()
            db.session.commit()
            processed += 1
        except SemanticSearchTransientError as exc:
            db.session.rollback()
            job = SemanticEmbeddingJob.query.get(job.id)
            if job is not None:
                job.status = "pending"
                job.last_error = str(exc)[:2000]
                job.updated_at = datetime.now()
                db.session.commit()
            raise
        except Exception as exc:
            db.session.rollback()
            job = SemanticEmbeddingJob.query.get(job.id)
            if job is None:
                continue
            job.attempts += 1
            job.status = "failed"
            job.last_error = str(exc)[:2000]
            job.updated_at = datetime.now()
            db.session.commit()
            _semantic_log(f"embedding job failed image_id={image.id}: {exc}")
    return processed


def delete_semantic_embedding(image_id: int) -> None:
    """Remove an image from the semantic queue and Milvus index."""
    try:
        job = SemanticEmbeddingJob.query.filter_by(image_id=int(image_id)).first()
        if job:
            db.session.delete(job)
            db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        _semantic_log(f"failed to delete queue job for image_id={image_id}: {exc}")

    try:
        collection = _get_existing_collection()
        if collection is not None:
            _delete_from_collection(collection, int(image_id))
            _semantic_log(f"deleted image_id={image_id} from Milvus")
    except Exception as exc:
        _semantic_log(f"failed to delete image_id={image_id} from Milvus: {exc}")


def _semantic_worker_loop(app: Any) -> None:
    _semantic_log("background embedding worker started")
    did_bootstrap = False
    poll_seconds = int(app.config.get("SEMANTIC_INDEX_POLL_SECONDS", 10))

    while True:
        with app.app_context():
            try:
                _ensure_queue_table()
                if not did_bootstrap:
                    enqueue_missing_semantic_embeddings()
                    did_bootstrap = True
                processed = process_pending_embedding_jobs()
                if processed:
                    _semantic_log(f"worker processed {processed} embedding jobs")
            except Exception as exc:
                _semantic_log(f"worker paused after error: {exc}")
        time.sleep(poll_seconds)


def start_semantic_index_worker(app: Any) -> None:
    """Start the background semantic embedding worker once per process."""
    if not app.config.get("SEMANTIC_INDEX_WORKER_ENABLED", True):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    global _WORKER_STARTED
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return
        thread = threading.Thread(
            target=_semantic_worker_loop,
            args=(app,),
            name="SemanticEmbeddingWorker",
            daemon=True,
        )
        thread.start()
        _WORKER_STARTED = True


def _ann_candidates(collection: Any, user_id: int, text_embedding: List[float], limit: int) -> List[Dict[str, Any]]:
    results = collection.search(
        data=[text_embedding],
        anns_field="embedding",
        param={
            "metric_type": "COSINE",
            "params": {"ef": int(_get_config("MILVUS_HNSW_EF_SEARCH", 64))},
        },
        limit=limit,
        expr=f"user_id == {int(user_id)}",
        output_fields=["image_path", "thumbnail_path"],
    )
    candidates = []
    for hit in results[0]:
        candidates.append(
            {
                "image_id": int(hit.id),
                "ann_score": float(hit.distance),
            }
        )
    return candidates


def _rerank_with_siglip(query: str, images: Sequence[Image]) -> Dict[int, float]:
    if not images:
        return {}

    bundle = _get_siglip_bundle()
    torch = bundle["torch"]
    processor = bundle["processor"]
    model = bundle["model"]
    device = bundle["device"]

    pil_images = []
    valid_images = []
    for image in images:
        try:
            pil_images.append(_load_image(_image_full_path(image)))
            valid_images.append(image)
        except Exception as exc:
            _semantic_log(f"skip rerank image_id={image.id}: {exc}")

    if not valid_images:
        return {}

    inputs = processor(text=[query], images=pil_images, padding="max_length", truncation=True, return_tensors="pt")
    inputs = _to_device(inputs, device)
    with torch.no_grad():
        outputs = model(**inputs)
        if hasattr(outputs, "logits_per_image"):
            scores = torch.sigmoid(outputs.logits_per_image[:, 0]).detach().cpu().tolist()
        else:
            text_embedding = _encode_text(query)
            scores = []
            for image in valid_images:
                image_embedding = _encode_image(_image_full_path(image))
                score = sum(left * right for left, right in zip(text_embedding, image_embedding))
                scores.append(float(score))

    return {int(image.id): float(score) for image, score in zip(valid_images, scores)}


def semantic_search_images_for_user(user_id: int, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search current user's images semantically and return top-k with scores.

    Pipeline:
    SigLIP image/text embeddings -> Milvus HNSW ANN -> top 5*k candidates ->
    SigLIP image-text matching rerank -> top-k.
    """
    query = str(query or "").strip()
    if not query:
        return []

    image_count = Image.query.filter(Image.user_id == user_id).count()
    if image_count == 0:
        _semantic_log(f"user_id={user_id} has no images; skip semantic search")
        return []

    top_k = max(1, min(int(top_k or 5), int(_get_config("SEMANTIC_MAX_TOP_K", 20))))
    candidate_limit = top_k * int(_get_config("SEMANTIC_CANDIDATE_MULTIPLIER", 5))
    _semantic_log(f"user_id={user_id} semantic query='{query}' top_k={top_k} candidates={candidate_limit}")

    collection = _get_existing_collection()
    if collection is None:
        _semantic_log("semantic collection does not exist yet; background index is not ready")
        return []

    text_embedding = _encode_text(query)
    candidates = _ann_candidates(collection, user_id, text_embedding, candidate_limit)
    if not candidates:
        return []

    image_ids = [candidate["image_id"] for candidate in candidates]
    image_map = {
        int(image.id): image
        for image in Image.query.options(joinedload(Image.tags))
        .filter(Image.user_id == user_id, Image.id.in_(image_ids))
        .all()
    }
    ordered_images = [image_map[image_id] for image_id in image_ids if image_id in image_map]
    rerank_scores = _rerank_with_siglip(query, ordered_images)
    ann_scores = {candidate["image_id"]: candidate["ann_score"] for candidate in candidates}

    scored_images = []
    for image in ordered_images:
        image_id = int(image.id)
        score = float(rerank_scores.get(image_id, ann_scores.get(image_id, 0.0)))
        scored_images.append((image, score))

    scored_images.sort(key=lambda item: item[1], reverse=True)
    if not scored_images:
        return []

    score_max = scored_images[0][1]
    score_threshold = score_max / 5.0
    scored_images = [
        (image, score)
        for image, score in scored_images
        if score > score_threshold
    ][:top_k]
    _semantic_log(
        f"semantic score filter max={score_max:.6f} threshold={score_threshold:.6f} kept={len(scored_images)}"
    )

    results = []
    for image, score in scored_images:
        image_id = int(image.id)
        results.append(
            {
                "id": image_id,
                "score": round(float(score), 6),
                "ann_score": round(float(ann_scores.get(image_id, 0.0)), 6),
                "thumbnail_url": url_for("static", filename=image.thumbnail_path, _external=False),
                "image_url": url_for("static", filename=image.image_path, _external=False),
                "tags": [tag.tag_content for tag in image.tags],
                "shoot_location": image.shoot_location,
                "shoot_time": image.shoot_time.isoformat() if image.shoot_time else None,
            }
        )
    return results
