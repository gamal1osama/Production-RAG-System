from celery_app import celery_app, get_setup_utils

from models import ProjectModel, ChunkModel, ResponseSignal
from controllers import NLPController

import asyncio
import logging
from tqdm import tqdm
        









logger = logging.getLogger('celery.task')




@celery_app.task(bind=True, name="tasks.data_indexing.index_data",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60})
def index_data(self, project_id: str, do_reset: int = 0):

    return asyncio.run(_index_data(self, project_id, do_reset))




async def _index_data(task_instance, project_id: str, do_reset: int = 0):


    db_engine, vector_db_client = None, None
    try:

        (db_engine, db_client, generation_client, 
        embedding_client, vector_db_client, template_parser) = await get_setup_utils()


        logger.info(f"Starting data indexing for project {project_id}")


        project_model = await ProjectModel.create_instance(db_client=db_client)
        project = await project_model.get_project_or_create(project_id=project_id)


        if not project:
            task_instance.update_state(
                state='FAILURE', 
                meta={
                    "signal": ResponseSignal.PROJECT_NOT_FOUND.value
                }
            )

            raise Exception(f"Project with id {project_id} not found")


    
        nlp_controller = NLPController(
            vector_db_client=vector_db_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser
        )



        chunk_model = await ChunkModel.create_instance(db_client=db_client)


        # create collection if not exists
        collection_name = nlp_controller.create_collection_name(project_id=project.project_id)

        _ = await vector_db_client.create_collection(collection_name=collection_name, 
                                                                embedding_size=embedding_client.embedding_size, 
                                                                do_reset=do_reset)
        
        # setup batching
        total_chunks_count = await chunk_model.get_total_chunks_count(project_id=project.project_id)
        pbar = tqdm(total=total_chunks_count, desc="Indexing chunks into vector DB", position=0)


        has_records, page_no, inserted_items_cnt, idx = True, 1, 0, 0
        while has_records:
            page_chunks = await chunk_model.get_project_chunks(
                project_id=project.project_id, 
                page_no=page_no, 
                page_size=100
            )

            if len(page_chunks):
                page_no += 1
            else:
                has_records = False
                break

            chunks_ids = [ c.chunk_id for c in page_chunks ]
            idx += len(page_chunks)

            is_inserted = await nlp_controller.index_into_db(
                project=project,
                chunks=page_chunks,
                chunks_ids=chunks_ids
            )
            if not is_inserted:
                task_instance.update_state(
                    state='FAILURE',
                    meta={
                        "signal": ResponseSignal.INSERTING_CHUNKS_INTO_DB_FAILED.value,
                    }
                )

                raise Exception(f"Failed to insert chunks into vector DB | Project ID: {project_id}")

            
            pbar.update(len(page_chunks))
            inserted_items_cnt += len(page_chunks)
        
       

        task_instance.update_state(
            state='SUCCESS',
            meta={
                "signal": ResponseSignal.INSERTING_CHUNKS_INTO_DB_SUCCESS.value,
                "total_chunks_indexed": inserted_items_cnt
            }
        )

        return {
            "signal": ResponseSignal.INSERTING_CHUNKS_INTO_DB_SUCCESS.value,
            "total_chunks_indexed": inserted_items_cnt
        }



    except Exception as e:

        logger.error(f"Task failed for project {project_id}: {str(e)}")

        raise

    finally:
        try:    
            if db_engine:
                await db_engine.dispose()
            if vector_db_client:
                await vector_db_client.disconnect()
        except Exception as e:
            logger.error(f"Error during cleanup for project {project_id}: {str(e)}")
