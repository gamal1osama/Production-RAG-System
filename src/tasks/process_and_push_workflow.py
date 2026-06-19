from celery import chain

from celery_app import celery_app

from tasks.file_processing import process_files
from tasks.data_indexing import _index_data

import asyncio

import logging



logger = logging.getLogger('celery.task')






@celery_app.task(bind=True, name="tasks.process_and_push_workflow.push_after_process",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60})
def push_after_process(self, prev_task_result):
    
    project_id = prev_task_result.get("project_id")
    do_reset = prev_task_result.get("do_reset")

    task_results = asyncio.run(_index_data(self, project_id, do_reset))

    return {
        "task_results": task_results,

        "project_id": project_id,  # to use them in the next task in the workflow 
        "do_reset": do_reset
    }



@celery_app.task(bind=True, name="tasks.process_and_push_workflow.process_and_push_workflow",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_and_push_workflow(self, 
                              project_id: str,
                              file_id:int = None,
                              chunk_size: int = 100,
                              chunk_overlap: int = 20,
                              do_reset: int = 0 ):
    
    
    workflow = chain(
        process_files.s(project_id, file_id, chunk_size, chunk_overlap, do_reset),
        push_after_process.s()
    )

    result = workflow.apply_async()

    return {
        "workflow_id": result.id,
        "message": "Workflow started.",
        "tasks": ["tasks.file_processing.process_files", "tasks.data_indexing.index_data"],
    }
