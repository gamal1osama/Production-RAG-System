from .BaseController import BaseController
from .ProjectController import ProjectController
from models import ProcessingEnums

import os

from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


class ProcessController(BaseController):

    def __init__(self, project_id: str):
        super().__init__()

        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id)

    def get_file_extension(self, file_id: str) -> str:
        return os.path.splitext(file_id)[-1]
    
    def get_file_loader(self, file_id: str):

        file_ext = self.get_file_extension(file_id)
        file_path = os.path.join(self.project_path, file_id)

        if file_ext == ProcessingEnums.TXT.value:
            return TextLoader(file_path=file_path, encoding='utf-8') # we use utf-8 encoding because if the file contain arabic caracters
        
        elif file_ext == ProcessingEnums.PDF.value:
            return PyMuPDFLoader(file_path=file_path)
        
        return None
    
    def get_file_content(self, file_id: str) -> str:
        loader = self.get_file_loader(file_id)

        return loader.load()
    
    def split_file_content(self, file_content: list,
                           chunk_size: int = 100, chunk_overlap: int = 20):
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        file_content_text = [content.page_content for content in file_content]
        file_content_metadata = [content.metadata for content in file_content]

        chunks = text_splitter.create_documents(file_content_text, metadatas=file_content_metadata)

        return chunks