from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base

class Equipment(Base):
    __tablename__ = "equipment"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # andamios, elevadores, etc.
    description = Column(Text)
    max_height = Column(Float)  # altura máxima en metros
    daily_price = Column(Float, nullable=False)
    weekly_price = Column(Float)
    monthly_price = Column(Float)
    specifications = Column(JSON)  # especificaciones técnicas
    use_cases = Column(JSON)  # casos de uso recomendados
    safety_requirements = Column(Text)
    available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    """
    Modelo para almacenar cada mensaje individual de una conversación.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    # Crea una clave foránea que apunta al ID de la tabla 'conversations'
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    # Define quién envió el mensaje: 'user' o 'agent'
    sender = Column(String(50), nullable=False)
    # El contenido del mensaje
    content = Column(Text, nullable=False)
    # La fecha y hora de creación, gestionada automáticamente por la base de datos
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relación inversa con Conversation
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, sender='{self.sender}', conversation_id={self.conversation_id})>"

class Conversation(Base):
    """
    Modelo para almacenar la información de una conversación.
    """
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=False)  # Telegram user ID
    user_name = Column(String(255))
    company_name = Column(String(255))
    phone = Column(String(50))
    email = Column(String(255))
    project_details = Column(JSON)  # detalles del proyecto
    recommended_equipment = Column(JSON)  # equipos recomendados
    stage = Column(String(50), default="welcome")  # etapa actual
    documents = Column(JSON)  # documentos recibidos
    quotation_sent = Column(Boolean, default=False)
    commercial_notified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Establece una relación "one-to-many".
    # Una conversación tiene muchos mensajes.
    # El 'back_populates' crea una referencia bidireccional, y 'cascade' asegura
    # que si se borra una conversación, también se borren todos sus mensajes asociados.
    messages = relationship(
        "Message", 
        back_populates="conversation", 
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id='{self.user_id}')>"

class Quotation(Base):
    __tablename__ = "quotations"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, nullable=False)
    user_id = Column(String(50), nullable=False)
    equipment_list = Column(JSON)  # lista de equipos cotizados
    rental_duration = Column(Integer)  # duración en días
    total_amount = Column(Float, nullable=False)
    quotation_data = Column(JSON)  # datos completos de la cotización
    created_at = Column(DateTime(timezone=True), server_default=func.now())