import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Database
    DATABASE_URL = "postgresql://neondb_owner:npg_Uduk4FqGZbn1@ep-cold-snow-adtfewzz-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    
    # Gemini API
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # Resend API
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    
    # Business Config
    COMPANY_NAME = "EquiposUp"
    COMPANY_EMAIL = "comercial@equiposup.com"
    COMPANY_WEBSITE = "https://equiposup.com/"
    
    # LLM Config - MODELO ACTUALIZADO
    MODEL_NAME = "gemini-1.5-flash"  # Cambiar de "gemini-pro" a "gemini-1.5-flash"
    MAX_TOKENS = 1000
    TEMPERATURE = 0.7

config = Config()