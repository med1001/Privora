from sqlalchemy import Column, Integer, String, DateTime, Text, func
from src.db import Base

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


class SupportRequest(Base):
    __tablename__ = "support_requests"

    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False, index=True)
    user_email = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountDeletionRequest(Base):
    __tablename__ = "account_deletion_requests"

    id = Column(Integer, primary_key=True)
    user_email = Column(String, nullable=False, index=True)
    details = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
