from .BaseController import BaseController
from stores.llm.LLMEnums import DocumentTypeEnums
from models.db_schemas import Project, DataChunk
from typing import List
import asyncio
from cohere.errors import TooManyRequestsError
import json




class NLPController(BaseController):

    def __init__(self, vector_db_client, generation_client, embedding_client, template_parser):
        super().__init__()

        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    
    def create_collection_name(self, project_id: str) -> str:
        return f"collection_{self.vector_db_client.default_vector_size}_{project_id}".strip()
    

    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vector_db_client.delete_collection(collection_name=collection_name)
        

    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vector_db_client.get_collection_info(collection_name=collection_name)

        return json.loads( # that usually solves the issue of non-serializable objects in the response (we actually get the error when we try to return the collection_info object in the response, so we convert it to json string and then parse it back to dict
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
        

    async def index_into_db(self, project: Project, chunks: List[DataChunk], do_reset: bool = False, chunks_ids: List[str] = None) -> bool:
        
        # step 1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)


        # step 2: manage items
        texts = [chunk.chunk_text for chunk in chunks]
        metadatas = [chunk.chunk_metadata for chunk in chunks]

        while True:
            try:
                vectors = self.embedding_client.embed_text(text=texts, document_type=DocumentTypeEnums.DOCUMENT.value)
                break
            except TooManyRequestsError:
                await asyncio.sleep(60)


        # step 3: create collection if not exists
        _ = await self.vector_db_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset
        )

        # step 4: insert items into collection
        _ = await self.vector_db_client.insert_many(
            collection_name=collection_name,
            texts=texts, 
            vectors=vectors, 
            metadatas=metadatas,
            record_ids=chunks_ids
        )


        return True
    

    
    async def search_vector_db_collection(self,
                                          project: Project,
                                          text: str,
                                          limit: int = 10):

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)
        query_vector = None

        # step2: get the text embedding vector
        while True:
            try:
                query_vectors = self.embedding_client.embed_text(text=text, document_type=DocumentTypeEnums.QUERY.value)
                break
            except TooManyRequestsError:
                await asyncio.sleep(60)
        
        if isinstance(query_vectors, list) and len(query_vectors) > 0:
            query_vector = query_vectors[0]
    
        if not query_vector:
            return None

        # step3: do semantic search
        search_results = await self.vector_db_client.search_by_vector(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
        if not search_results:
            return None


        return search_results


    async def answer_rag_query(self, project: Project, query: str, limit: int = 10):

        answer, full_prompt, chat_history = None, None, None
        
        # step1: retrieve related chunks from vector db
        retrieved_chunks = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit
        )

        if not retrieved_chunks:
            return answer, full_prompt, chat_history


        # step2: construct prompt for generation client (LLM)
        system_prompt = self.template_parser.get_prompts(group="rag", key="system_prompt")

        document_prompts = "\n".join([
            self.template_parser.get_prompts(
                group="rag",
                key="document_prompt",
                vars={
                    "doc_number": idx,
                    "doc_content": self.generation_client.process_text(chunk.text)
                }
            )
            for idx, chunk in enumerate(retrieved_chunks, 1)
        ])

        footer_prompt = self.template_parser.get_prompts(
            group="rag",
            key="footer_prompt",
            vars={
                "query": query
            }
        )


        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt, 
                role=self.generation_client.enums.SYSTEM.value
            )
        ]

        full_prompt = "\n\n".join([
            document_prompts,
            footer_prompt
        ])

        # step3: call generation client (LLM) to get the answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history
    