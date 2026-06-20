from .ragsys_base import SQLAlchemyBase

from sqlalchemy import Column, Integer, String, DateTime, func, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import Index
import uuid



class CeleryTaskExecution(SQLAlchemyBase):

    __tablename__ = "celery_task_execution"

    execution_id = Column(Integer, primary_key=True, autoincrement=True)

    task_name = Column(String(255), nullable=False)
    task_args_hash = Column(String(255), nullable=False) # hash of the task arguments to identify similar tasks
    celery_task_id = Column(UUID(as_uuid=True), nullable=True)

    status = Column(String(50), nullable=False, default='PENDING')
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    task_args = Column(JSONB, nullable=True)
    result = Column(JSONB, nullable=True)
    

    __table_args__ = (
        Index('idx_task_name_args_hash', 'task_name', 'task_args_hash', unique=True),
        Index('idx_task_execution_status', 'status'),
        Index('idx_task_execution_created_at', 'created_at'),
        Index('idx_celery_task_id', 'celery_task_id'),
    )

    