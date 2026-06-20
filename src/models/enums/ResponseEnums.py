from enum import Enum


class ResponseSignal(Enum):

    # the following signals are enums valus you should use .value when calling to get the string value of the signal
    FILE_VALIDATION_SUCCESS = "file_validation_success"

    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDS_LIMIT = "file_size_exceeds_limit"
    
    FILE_UPLOADED_SUCCESSFULLY = "file_uploaded_successfully"
    FILE_UPLOADED_FAILED = "file_uploaded_failed"

    FILE_PROCESSING_FAILED = "file_processing_failed"
    FILE_PROCESSING_SUCCESS = "file_processing_success"
    
    NO_FILES_TO_PROCESS_ERROR = "no_files_to_process_error"

    FILE_WITH_THIS_ID_NOT_FOUND_ERROR = "file_with_this_id_not_found_error"

    PROJECT_NOT_FOUND = "project_not_found"

    INSERTING_CHUNKS_INTO_DB_FAILED = "inserting_chunks_into_db_failed"
    INSERTING_CHUNKS_INTO_DB_SUCCESS = "inserting_chunks_into_db_success"

    GETTING_VECTOR_DB_COLLECTION_INFO_SUCCESS = "getting_vector_db_collection_info_success"

    SEARCHING_VECTOR_DB_COLLECTION_FAILED = "searching_vector_db_collection_failed"
    SEARCHING_VECTOR_DB_COLLECTION_SUCCESS = "searching_vector_db_collection_success"

    ANSWERING_RAG_QUERY_FAILED = "answering_rag_query_failed"
    ANSWERING_RAG_QUERY_SUCCESS = "answering_rag_query_success"
    
    FILE_PROCESSING_STARTED = "file_processing_started"
    DATA_PUSHING_STARTED = "data_pushing_started"
    PROCESS_AND_PUSH_WORKFLOW_STARTED = "process_and_push_workflow_started"
    