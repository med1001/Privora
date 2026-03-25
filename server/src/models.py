from sqlalchemy import Column, Integer, String, DateTime, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from src.db import Base

#Base = declarative_base()

class Message(Base):
    __tablename__ = 'message_history'
    id = Column(Integer, primary_key=True)
    msg_id = Column(String, index=True)
    sender = Column(String)
    sender_display_name = Column(String)
    recipient = Column(String)
    message = Column(String)
    reactions = Column(String, default="{}")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())      

class OfflineMessage(Base):
    __tablename__ = 'offline_messages'
    id = Column(Integer, primary_key=True)
    msg_id = Column(String, index=True)
    sender = Column(String)
    sender_display_name = Column(String)
    recipient = Column(String)
    message = Column(String)
    reactions = Column(String, default="{}")
