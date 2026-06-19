from celery_app import celery_app, get_setup_utils

from controllers import ProcessController, NLPController
from models import ResponseSignal, ProjectModel, ChunkModel, AssetModel
from models.db_schemas import DataChunk
from models.enums import AssetTypeEnum

import asyncio

import logging



logger = logging.getLogger('celery.task')











@celery_app.task(bind=True, name="tasks.file_processing.process_files",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_files(self, 
                  project_id: str,
                  file_id:int = None,
                  chunk_size: int = 100,
                  chunk_overlap: int = 20,
                  do_reset: int = 0 ):
    
    return asyncio.run(_process_files(self, project_id, 
                                      file_id, chunk_size, 
                                      chunk_overlap, do_reset)) 




async def _process_files(task_instance, 
                         project_id: str,
                         file_id:int = None,
                         chunk_size: int = 100,
                         chunk_overlap: int = 20,
                         do_reset: int = 0 ):

    db_engine, vector_db_client = None, None
    try:

        (db_engine, db_client, generation_client, 
        embedding_client, vector_db_client, template_parser) = await get_setup_utils()




        project_model = await ProjectModel.create_instance(db_client=db_client)
        project = await project_model.get_project_or_create(project_id=project_id)

        nlp_controller = NLPController(
            vector_db_client=vector_db_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser
        )

        asset_model = await AssetModel.create_instance(db_client=db_client)
        project_files_ids = {}

        if file_id is not None:
            asset_record = await asset_model.get_asset_record_by_id(
                asset_project_id=project.project_id, asset_id=file_id
            )

            if asset_record is None:

                task_instance.update_state(
                    state='FAILURE',
                    meta={
                        "signal":ResponseSignal.FILE_WITH_THIS_ID_NOT_FOUND_ERROR.value,
                    }
                )

                raise Exception(f"File with id {file_id} not found in project {project_id}")
                
                
            project_files_ids = {
                asset_record.asset_id : asset_record.asset_name
            }


        else:
            project_assets = await asset_model.get_all_project_assets(asset_project_id=project.project_id, asset_type=AssetTypeEnum.FILE.value)
            
            project_files_ids = {
                asset.asset_id : str(asset.asset_name) for asset in project_assets
                }


        if len(project_files_ids) == 0:
            
            task_instance.update_state(
                state='FAILURE',
                meta={
                    "signal":ResponseSignal.NO_FILES_TO_PROCESS_ERROR.value,
                }
            )

            raise Exception(f"No files to process in project {project_id}")



        process_controller = ProcessController(project_id=project_id)

        
        
        
        chunk_model = await ChunkModel.create_instance(db_client=db_client)

        if do_reset==1:
            # delete the associated collection in the vector database
            collection_name = nlp_controller.create_collection_name(project_id=project.project_id)

            _ = await vector_db_client.delete_collection(collection_name=collection_name)

            # delete the existing chunks in the database for this project
            await chunk_model.delete_chunks_by_project_id(project_id=project.project_id)


        no_records, no_files = 0, 0
        for asset_id, file_id in project_files_ids.items():

            file_content = process_controller.get_file_content(file_id=file_id)
            if file_content is None:
                logger.warning(f"File with id {file_id} not found in project {project_id}, skipping processing for this file.")
                continue

            chunks = process_controller.split_file_content(file_content=file_content, 
                                                        chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            
            if chunks is None or len(chunks) == 0:
                
                logger.error(f"Processing failed for file with id {file_id} in project {project_id}, skipping this file.")
                continue
        
            chunks_records = [
                DataChunk(
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=index,
                    chunk_project_id=project.project_id,
                    chunk_asset_id=asset_id
                ) for index, chunk in enumerate(chunks, start=1)
            ]


            no_records += await chunk_model.insert_many_chunks(chunks=chunks_records)
            no_files += 1




        task_instance.update_state(
            state='SUCCESS',
            meta={
                "signal":ResponseSignal.FILE_PROCESSING_SUCCESS.value,
                "no_files_processed": no_files,
                "no_chunks_created": no_records
            }
        )

        logger.info(f"File processing completed for project {project_id}: {no_files} files processed, {no_records} chunks created.")

        return {
            "signal":ResponseSignal.FILE_PROCESSING_SUCCESS.value,
            "no_files_processed": no_files,
            "no_chunks_created": no_records
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
