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
    