from sqlalchemy import Column, Integer, String, DateTime, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from db import Base

#Base = declarative_base()

class Message(Base):
    __tablename__ = 'message_history'
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    sender_display_name = Column(String)  # <-- new column for sender's display name
    recipient = Column(String)
    message = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class OfflineMessage(Base):
    __tablename__ = 'offline_messages'
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    sender_display_name = Column(String)  # <-- new column here too
    recipient = Column(String)
    message = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
