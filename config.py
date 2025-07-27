from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Settings(BaseSettings):
    """Configuración de la aplicación usando Pydantic Settings optimizada para reducir uso de tokens"""
    
    # Configuración de Telegram
    TELEGRAM_TOKEN: str = Field(..., description="Token del bot de Telegram")
    
    # Configuración de Google AI optimizada
    GOOGLE_API_KEY: str = Field(..., description="API Key de Google Generative AI")
    MODEL_NAME: str = Field(default="gemini-1.5-flash", description="Nombre del modelo de Gemini")
    TEMPERATURE: float = Field(default=0.3, description="Temperatura del modelo - reducida para consistencia")
    MAX_TOKENS: int = Field(default=300, description="Máximo número de tokens - reducido para ahorrar cuota")
    
    # Configuración de rate limiting para evitar exceder cuota
    REQUEST_DELAY: float = Field(default=0.8, description="Delay entre requests en segundos")
    MAX_RETRIES: int = Field(default=3, description="Máximo número de reintentos")
    RETRY_DELAY: int = Field(default=60, description="Delay base para reintentos en segundos")
    
    # Configuración de base de datos
    DATABASE_URL: str = Field(default=os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_Uduk4FqGZbn1@ep-cold-snow-adtfewzz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"), description="URL de la base de datos")
    
    # Configuración de la empresa
    COMPANY_NAME: str = Field(default="EquiposUp", description="Nombre de la empresa")
    COMPANY_EMAIL: str = Field(default="ventas@equiposup.com", description="Email de la empresa")
    COMPANY_PHONE: str = Field(default="+57 300 123 4567", description="Teléfono de la empresa")
    
    # Configuración del dominio
    COMPANY_DOMAIN: str = Field(default="updates.stayirrelevant.com", description="Dominio de la empresa para enviar correos")
    
    # Configuración de email (Resend) - opcional
    RESEND_API_KEY: Optional[str] = Field(default=None, description="API Key de Resend para emails")
    
    # Configuración de logging
    LOG_LEVEL: str = Field(default="INFO", description="Nivel de logging")
    LOG_FILE: Optional[str] = Field(default=None, description="Archivo de logging")
    
    # Configuración de desarrollo
    DEBUG: bool = Field(default=False, description="Modo debug")
    
    # Nuevas configuraciones para optimización
    USE_CACHE: bool = Field(default=True, description="Usar cache para conversaciones")
    SIMPLE_EXTRACTION: bool = Field(default=True, description="Usar extracción simple sin LLM cuando sea posible")
    QUOTA_SAFETY: bool = Field(default=True, description="Activar medidas de seguridad para la cuota")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignora campos extra del .env
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> any:
            if field_name in ['DEBUG', 'USE_CACHE', 'SIMPLE_EXTRACTION', 'QUOTA_SAFETY']:
                return raw_val.lower() in ('true', '1', 'yes', 'on')
            return raw_val

# Instancia global de configuración
config = Settings()

# Validación de configuración crítica
def validate_config():
    """Valida que todas las configuraciones críticas estén presentes"""
    critical_fields = ['TELEGRAM_TOKEN', 'GOOGLE_API_KEY']
    
    missing_fields = []
    for field in critical_fields:
        if not getattr(config, field, None):
            missing_fields.append(field)
    
    if missing_fields:
        raise ValueError(f"Faltan las siguientes variables de entorno críticas: {', '.join(missing_fields)}")
    
    # Mostrar confirmación de configuración cargada
    print(f"✅ Configuración validada correctamente")
    print(f"📱 Telegram Token: {'*' * 20}...{config.TELEGRAM_TOKEN[-4:]}")
    print(f"🤖 Google API Key: {'*' * 20}...{config.GOOGLE_API_KEY[-4:]}")
    if config.RESEND_API_KEY:
        print(f"📧 Resend API Key: {'*' * 20}...{config.RESEND_API_KEY[-4:]}")
    print(f"🏢 Empresa: {config.COMPANY_NAME}")
    print(f"🌐 Dominio: {config.COMPANY_DOMAIN}")
    print(f"🤖 Modelo: {config.MODEL_NAME}")
    print(f"⚡ Max tokens: {config.MAX_TOKENS} (optimizado)")
    print(f"🛡️ Rate limiting: {config.REQUEST_DELAY}s delay")
    print(f"🔄 Quota safety: {'Activado' if config.QUOTA_SAFETY else 'Desactivado'}")
    
    return True

# Validar configuración al importar
validate_config()