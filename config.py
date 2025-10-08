import os
from datetime import timedelta

# Configuración base
class Config:
    # Clave secreta para sesiones y tokens
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-cambiar-en-produccion-2024'
    
    # Configuración de directorios
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    SALES_DIR = os.path.join(BASE_DIR, 'sales_data')
    COMMENTS_DIR = os.path.join(BASE_DIR, 'comments')
    PHOTOS_DIR = os.path.join(BASE_DIR, 'static', 'fotos')
    TUTORIALS_DIR = os.path.join(BASE_DIR, 'static', 'tutoriales')
    
    # Configuración de archivos
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'mp4', 'txt', 'html'}
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
    
    # Configuración de aplicación
    SESSION_TIMEOUT = timedelta(hours=2)
    ITEMS_PER_PAGE = 20
    
    # Configuración de códigos
    SALES_CODE_PREFIX = 'BI'
    SALES_CODE_LENGTH = 8  # BINNNNCC
    
    # Contraseña para sección de informaciones
    INFO_PASSWORD = 'boa2024'  # Cambiar en producción
    
    # Configuración de CSV
    CSV_DELIMITER = ';'
    CSV_ENCODING = 'utf-8'

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # En producción, usar variables de entorno
    SECRET_KEY = os.environ.get('SECRET_KEY', 'production-secret-key-change-me')
    INFO_PASSWORD = os.environ.get('INFO_PASSWORD', 'boa2024')

class TestingConfig(Config):
    TESTING = True
    DEBUG = True

# Configuración por defecto
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Obtener configuración basada en entorno"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])

# Funciones de utilidad (sin dependencias de app.py)
def ensure_directories(config_obj):
    """Asegurar que todos los directorios necesarios existan"""
    directories = [
        config_obj.DATA_DIR,
        config_obj.SALES_DIR,
        config_obj.COMMENTS_DIR,
        config_obj.PHOTOS_DIR,
        config_obj.TUTORIALS_DIR
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Directorio verificado: {directory}")

def allowed_file(filename, config_obj):
    """Verificar si la extensión del archivo está permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config_obj.ALLOWED_EXTENSIONS

def validate_sales_code(code, config_obj):
    """Validar formato de código de ventas"""
    if not code.startswith(config_obj.SALES_CODE_PREFIX):
        return False
    if len(code) != config_obj.SALES_CODE_LENGTH:
        return False
    # Verificar que los caracteres después de BI sean válidos
    suffix = code[2:]
    if not suffix[:4].isdigit():  # NNNN deben ser dígitos
        return False
    if not suffix[4:].isalpha():  # CC deben ser letras
        return False
    return True

def validate_factory_code(code, config_obj):
    """Validar formato de código de fábrica"""
    return 3 <= len(code) <= 8 and code.isalnum()