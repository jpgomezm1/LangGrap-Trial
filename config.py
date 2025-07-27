from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Settings(BaseSettings):
    """Configuración de la aplicación usando Pydantic Settings"""
    
    # Configuración de Telegram
    TELEGRAM_TOKEN: str = Field(..., description="Token del bot de Telegram")
    
    # Configuración de Google AI
    GOOGLE_API_KEY: str = Field(..., description="API Key de Google Generative AI")
    MODEL_NAME: str = Field(default="gemini-1.5-flash", description="Nombre del modelo de Gemini")
    TEMPERATURE: float = Field(default=0.7, description="Temperatura del modelo")
    MAX_TOKENS: int = Field(default=1000, description="Máximo número de tokens")
    
    # Configuración de base de datos
    # --- MODIFICAR ESTA LÍNEA ---
    DATABASE_URL: str = Field(default=os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_Uduk4FqGZbn1@ep-cold-snow-adtfewzz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"), description="URL de la base de datos")
    
    # Configuración de la empresa
    COMPANY_NAME: str = Field(default="EquiposUp", description="Nombre de la empresa")
    COMPANY_EMAIL: str = Field(default="ventas@equiposup.com", description="Email de la empresa")
    COMPANY_PHONE: str = Field(default="+57 300 123 4567", description="Teléfono de la empresa")
    
    # --- AÑADIR ESTA LÍNEA ---
    COMPANY_DOMAIN: str = Field(default="updates.stayirrelevant.com", description="Dominio de la empresa para enviar correos")
    
    # Configuración de email (Resend) - opcional
    RESEND_API_KEY: Optional[str] = Field(default=None, description="API Key de Resend para emails")
    
    # Configuración de logging
    LOG_LEVEL: str = Field(default="INFO", description="Nivel de logging")
    LOG_FILE: Optional[str] = Field(default=None, description="Archivo de logging")
    
    # Configuración de desarrollo
    DEBUG: bool = Field(default=False, description="Modo debug")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignora campos extra del .env
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> any:
            if field_name == 'DEBUG':
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
    
    return True

# Validar configuración al importar
validate_config()