from qdrant_client import QdrantClient, models

from ..VectorDBInterface import VectorDBInterface
from ..VectoDBEnums import DistanceMethodEnums
from models.db_schemas import RetrievedDataChunk

import logging
from typing import List
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL



class QdrantDBProvider(VectorDBInterface):

    def __init__(self, db_client: str, default_vector_size: int=786, distance_method: str=None, index_threshold: int=100):
        
        self.db_client = db_client
        self.distance_method = None
        self.client = None
        self.default_vector_size = default_vector_size

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT

        self.logger = logging.getLogger('uvicorn.error')


    async def connect(self):
        self.client = QdrantClient(path=self.db_client)
    
    async def disconnect(self):
        self.client = None

    
    async def is_collection_exists(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)
    

    async def list_all_collections(self) -> List:
        return self.client.get_collections()
    

    async def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)
    

    async def delete_collection(self, collection_name: str):
        if await self.is_collection_exists(collection_name):
            self.logger.info(f"Deleting existing Qdrant collection {collection_name}...")
            return self.client.delete_collection(collection_name=collection_name)
        
    async def create_collection(self, collection_name: str, 
                          embedding_size: int, 
                          do_reset: bool = False) -> bool:
        if do_reset:
            _ = await self.delete_collection(collection_name)
        
        if not await self.is_collection_exists(collection_name):
            self.logger.info(f"Creating Qdrant collection {collection_name} with embedding size {embedding_size} and distance method {self.distance_method}...")
            _ = self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=embedding_size, distance=self.distance_method)
            )

            return True
        
        return False
    

    async def insert_one(self, collection_name: str,
                   text: str, 
                   vector: List[float], 
                   metadata: dict = None,
                   record_id: str = None) -> bool:

        if not await self.is_collection_exists(collection_name):
            self.logger.error("Can't insert to non-existing collection!")
            return False
        
        try:
            _ = self.client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=record_id,
                        vector=vector,
                        payload={
                            "text": text,
                            "metadata":metadata
                        }
                    )
                ]
            )
        except Exception as e:
            self.logger.error(f"Error occurred while inserting: {e}")
            return False

        return True
    

    async def insert_many(self, collection_name: str,
                    texts: List[str], 
                    vectors: List[List[float]], 
                    metadatas: List[dict] = None,
                    record_ids: List[str] = None,
                    batch_size: int = 64) -> bool:
        
        if metadatas is None:
            metadatas = [None] * len(texts)

        if record_ids is None:
            record_ids = [str(uuid4()) for _ in range(0, len(texts))]
        else:
            normalized_ids = []
            for record_id in record_ids:
                record_id = str(record_id)
                try:
                    _ = UUID(record_id)
                except :
                    record_id = str(uuid5(NAMESPACE_URL, record_id))
                normalized_ids.append(record_id)
                
            record_ids = normalized_ids

        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_vectors = vectors[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]
            batch_record_ids = record_ids[i:i+batch_size]

            points = [
                models.PointStruct(
                    id=record_id,
                    vector=vector,
                    payload={
                        "text": text,
                        "metadata":metadata
                    }
                )
                for text, vector, metadata, record_id in zip(batch_texts, batch_vectors, batch_metadatas, batch_record_ids)
            ]

            try:
                _ = self.client.upsert(
                    collection_name=collection_name,
                    points=points
                )
            except Exception as e:
                self.logger.error(f"Error occurred while inserting batch: {e}")
                raise e

        return True
    

    async def search_by_vector(self, collection_name: str,
                         query_vector: List[float], 
                         limit: int = 10) -> List[RetrievedDataChunk]:
        if not await self.is_collection_exists(collection_name):
            self.logger.error("Can't search in non-existing collection!")
            return []
        


        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit
        ).points
        
        if not results or len(results) == 0:
            return []
        
        return [
            RetrievedDataChunk(
                text=result.payload["text"],
                score=result.score
            )
            for result in results
        ]


