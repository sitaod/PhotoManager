"""
Application configuration file
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class"""
    # Application secret key for session encryption
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database configuration
    # MySQL connection format: mysql+pymysql://username:password@host:port/database_name
    # Use environment variables for credentials
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'photomanager')
    
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    # Disable SQLAlchemy event tracking system (save resources)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Return Chinese characters in JSON without escaping to ASCII
    JSON_AS_ASCII = False
    
    # Qwen AI Configuration
    # API Key for Alibaba Cloud DashScope (Tongyi Qianwen)
    QWEN_API_KEY = os.environ.get('API_KEY', '')
    # Base URL for Qwen compatible API
    QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    # Model name for vision-language tasks
    QWEN_MODEL = 'qwen3.6-flash'

    # Semantic image search configuration
    SIGLIP_MODEL_NAME = os.environ.get('SIGLIP_MODEL_NAME', 'google/siglip-base-patch16-224')
    SIGLIP_DEVICE = os.environ.get('SIGLIP_DEVICE', 'auto')
    MILVUS_HOST = os.environ.get('MILVUS_HOST', '127.0.0.1')
    MILVUS_PORT = os.environ.get('MILVUS_PORT', '19530')
    MILVUS_COLLECTION = os.environ.get('MILVUS_COLLECTION', 'photomanager_siglip_images')
    MILVUS_HNSW_M = int(os.environ.get('MILVUS_HNSW_M', '16'))
    MILVUS_HNSW_EF_CONSTRUCTION = int(os.environ.get('MILVUS_HNSW_EF_CONSTRUCTION', '200'))
    MILVUS_HNSW_EF_SEARCH = int(os.environ.get('MILVUS_HNSW_EF_SEARCH', '64'))
    SEMANTIC_CANDIDATE_MULTIPLIER = int(os.environ.get('SEMANTIC_CANDIDATE_MULTIPLIER', '5'))
    SEMANTIC_MAX_TOP_K = int(os.environ.get('SEMANTIC_MAX_TOP_K', '20'))
    SEMANTIC_INDEX_WORKER_ENABLED = os.environ.get('SEMANTIC_INDEX_WORKER_ENABLED', 'true').lower() == 'true'
    SEMANTIC_INDEX_BATCH_SIZE = int(os.environ.get('SEMANTIC_INDEX_BATCH_SIZE', '2'))
    SEMANTIC_INDEX_POLL_SECONDS = int(os.environ.get('SEMANTIC_INDEX_POLL_SECONDS', '10'))
    SEMANTIC_INDEX_MAX_ATTEMPTS = int(os.environ.get('SEMANTIC_INDEX_MAX_ATTEMPTS', '3'))


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
