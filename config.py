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
    QWEN_MODEL = 'qwen-vl-max'


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
