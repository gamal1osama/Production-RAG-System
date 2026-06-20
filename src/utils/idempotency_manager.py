import hashlib
import json
from datetime import datetime
from models.db_schemas.ragsys.schemas.celery_task_execution import CeleryTaskExecution

from sqlalchemy import select




class IdempotencyManager:

    def __init__(self, db_client, db_engine):
        
        self.db_client = db_client
        self.db_engine = db_engine

    
    def create_args_hash(self, task_name, task_args):
        
        combined_data = {
            **task_args,
            "task_name": task_name,
        }

        json_string = json.dumps(combined_data, sort_keys=True, default=str)

        hash_object = hashlib.sha256(json_string.encode())
        return hash_object.hexdigest()





    async def create_task_record(self, task_name: str, task_args: dict, celery_task_id: str=None):
        
        args_hash = self.create_args_hash(task_name, task_args)
        current_time = datetime.utcnow()

        new_task_record = CeleryTaskExecution(
            celery_task_id=celery_task_id,
            task_name=task_name,
            task_args_hash=args_hash,
            status="PENDING",
            created_at=current_time,
        )

        session = self.db_client()
        try:
            session.add(new_task_record)
            await session.commit()
            await session.refresh(new_task_record)
            return new_task_record
        finally:
            await session.close()


    async def update_task_status(self, execution_id: int, status: str, result: dict = None):
        
        session = self.db_client()
        try:
            task_record = await session.get(CeleryTaskExecution, execution_id)

            if task_record:
                task_record.status = status
                
                if result:
                    task_record.result = result
                
                if status in ["SUCCESS", "FAILURE"]:
                    task_record.finished_at = datetime.utcnow()

                await session.commit()
                await session.refresh(task_record)
        finally:
            await session.close()




    
    async def get_existing_task(self, task_name: str, task_args: dict, celery_task_id: str) -> CeleryTaskExecution:
        
        args_hash = self.create_args_hash(task_name, task_args)

        session = self.db_client()
        try:
            stmt = select(CeleryTaskExecution).where(
                CeleryTaskExecution.celery_task_id == celery_task_id,
                CeleryTaskExecution.task_name == task_name,
                CeleryTaskExecution.task_args_hash == args_hash
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        finally:
            await session.close()

    async def should_execute_task(self, task_name: str, task_args: dict, celery_task_id: str, 
                                  task_time_limit: int = 600) -> tuple[bool, CeleryTaskExecution]:
        
        existing_task = await self.get_existing_task(task_name, task_args, celery_task_id)

        if not existing_task:
            return True, None
        
        if existing_task.status == "SUCCESS":
            return False, existing_task

        if existing_task.status in ["PENDING", "STARTED", "RETRY"]:
            if existing_task.created_at:
                time_since_creation = (datetime.utcnow() - existing_task.created_at).total_seconds()
                time_gap = 60
                if time_since_creation > task_time_limit + time_gap:
                    return True, existing_task
            return False, existing_task

        return True, existing_task
        