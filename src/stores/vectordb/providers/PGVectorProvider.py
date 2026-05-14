from ..VectorDBInterface import VectorDBInterface
from ..VectoDBEnums import (DistanceMethodEnums, DistanceMethodEnums, 
                            PgVectorDistanceMethodEnums, PgVectorTableScemaEnums, PgVectorIndexTypeEnums)
from models.db_schemas import RetrievedDataChunk

from typing import List
import logging
from sqlalchemy.sql import text as sql_text
import json



class PGVectorProvider(VectorDBInterface):
    
    def __init__(self, db_client, default_vector_size: int=786, distance_method: str=None):

        self.db_client = db_client
        self.default_vector_size = default_vector_size
        self.distance_method = distance_method

        self.pgvector_table_prefix = PgVectorTableScemaEnums._PREFIX.value

        self.logger = logging.getLogger(__name__)


    async def connect(self):
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text(
                    "CREATE EXTENSION IF NOT EXISTS vector"
                ))
            await session.commit()

    
    async def disconnect(self):
        pass

    
    # that fucnc is to check if the table exists or not (it named collection in qdrant)
    async def is_collection_exists(self, collection_name: str) -> bool:
        record = None

        async with self.db_client() as session:
            async with session.begin():
                list_tb1 = sql_text("SELECT * FROM pg_tables WHERE tablename = :collection_name")
                results = await session.execute(list_tb1, {"collection_name": collection_name})
                record = await results.scalar_one_or_none()

        return record
    

    async def list_all_collections(self) -> List:
        records = []

        async with self.db_client() as session:
            async with session.begin():
                list_tb1 = sql_text("SELECT tablename FROM pg_tables WHERE tablename LIKE :prefix")
                results = await session.execute(list_tb1, {"prefix": f"{self.pgvector_table_prefix}%"})
                records = await results.scalars().all()

        return records


    async def get_collection_info(self, collection_name: str) -> dict:
        record = None

        async with self.db_client() as session:
            async with session.begin():
                table_info_stmt = sql_text("""
                    SELECT schemaname, tablename, tableowner, tablespace, hasindexes
                    FROM pg_tables
                    WHERE tablename = :collection_name
                """) 

                count_sql = sql_text(f"SELECT COUNT(*) FROM :collection_name")

                table_info_result = await session.execute(table_info_stmt, {"collection_name": collection_name})
                count_result = await session.execute(count_sql, {"collection_name": collection_name})

                table_info = table_info_result.fetchone()
                if not table_info:
                    return None
                
                return {
                    "table_info": dict(table_info),
                    "record_count": count_result
                }


    async def delete_collection(self, collection_name: str):
        async with self.db_client() as session:
            async with session.begin():
                self.logger.info(f"Deleting collection (table) {collection_name}...")

                drop_tb1 = sql_text(f"DROP TABLE :collection_name")
                await session.execute(drop_tb1, {"collection_name": collection_name})
                await session.commit()

        return True
    

    async def create_collection(self, collection_name: str, 
                                embedding_size: int, 
                                do_reset: bool = False) -> bool:
        if do_reset:
            _ = await self.delete_collection(collection_name)

        if not await self.is_collection_exists(collection_name):
            self.logger.info(f"Creating collection (table) {collection_name} with embedding size {embedding_size}...")

            async with self.db_client() as session:
                async with session.begin():
                    create_tb1 = sql_text(
                        "CREATE TABLE :collection_name ("
                        f"{PgVectorTableScemaEnums.ID.value} bigserial PRIMARY KEY,"
                        f"{PgVectorTableScemaEnums.TEXT.value} text,"
                        f"{PgVectorTableScemaEnums.VECTOR.value} vector(:embedding_size), "
                        f"{PgVectorTableScemaEnums.METADATA.value} jsonb DEFAULT '{{}}',"
                        f"{PgVectorTableScemaEnums.CHUNK_ID.value} integer,"
                        f"FOREIGN KEY ({PgVectorTableScemaEnums.CHUNK_ID.value}) REFERENCES chunks(chunk_id)"
                        ")"
                    )
                    await session.execute(create_tb1, {"collection_name": collection_name, "embedding_size": embedding_size})
                    await session.commit()

            return True
        
        return False            
    

    async def insert_one(self, collection_name: str, 
                         text: str, 
                         vector: List[float], 
                         metadata: dict = None,
                         record_id: str = None) -> bool:

        if not await self.is_collection_exists(collection_name):
            self.logger.error(f"Collection (table) {collection_name} does not exist. Cannot insert record.")
            return False
        
        if not record_id:
            self.logger.error("Record ID is required for insertion.")
            return False

        async with self.db_client() as session:
            async with session.begin():
                insert_sql = sql_text(
                    "INSERT INTO :collection_name "
                    f"({PgVectorTableScemaEnums.TEXT.value}, {PgVectorTableScemaEnums.VECTOR.value}, {PgVectorTableScemaEnums.METADATA.value}, {PgVectorTableScemaEnums.CHUNK_ID.value})"
                    f"VALUES (:text, :vector, :metadata, :chunk_id)"
                )

                await session.execute(insert_sql, {
                    "collection_name": collection_name,
                    "text": text,
                    "vector": "[" + ",".join([str(x) for x in vector]) + "]",  # postgres should take vector as string in format '[0.1, 0.2, ...]' not as a list and also we did that because we use sql_text
                    "metadata": metadata,
                    "chunk_id": record_id
                })
                await session.commit()

        return True
    


    
    async def insert_many(self, collection_name: str,
                          texts: List[str],
                          vectors: List[List[float]],
                          metadatas: List[dict] = None,
                          record_ids: List[str] = None,
                          batch_size: int = 64) -> bool:


        if not await self.is_collection_exists(collection_name):
            self.logger.error(f"Collection (table) {collection_name} does not exist. Cannot insert records.")
            return False
        
        if len(vectors) != len(record_ids):
            self.logger.error("Length of vectors and record_ids must be the same.")
            return False
        
        if not metadatas:
            metadatas = [None] * len(texts)
        
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i+batch_size]
                    batch_vectors = vectors[i:i+batch_size]
                    batch_metadatas = metadatas[i:i+batch_size] if metadatas else [None] * len(batch_texts)
                    batch_record_ids = record_ids[i:i+batch_size]

                    values = []
                    for _text, _vector, _metadata, _record_id in zip(batch_texts, batch_vectors, batch_metadatas, batch_record_ids):
                        values.append({
                            "text": _text,
                            "vector": "[" + ",".join([str(x) for x in _vector]) + "]",
                            "metadata": _metadata,
                            "chunk_id": _record_id
                        })
                        
                    batch_insert_sql = sql_text(
                        "INSERT INTO {collection_name} "
                        f"({PgVectorTableScemaEnums.TEXT.value}, "
                        f"{PgVectorTableScemaEnums.VECTOR.value}, "
                        f"{PgVectorTableScemaEnums.METADATA.value}, "
                        f"{PgVectorTableScemaEnums.CHUNK_ID.value})"
                        "VALUES (:text, :vector, :metadata, :chunk_id)"
                    ) 

                    await session.execute(batch_insert_sql, values)
                await session.commit()

        return True
    

    async def search_by_vector(self, collection_name: str,
                         query_vector: List[float], 
                         limit: int = 10) -> List[RetrievedDataChunk]:
        
        if not await self.is_collection_exists(collection_name):
            self.logger.error(f"Collection (table) {collection_name} does not exist. Cannot perform search.")
            return []
        

        query_vector = "[" + ",".join([str(x) for x in query_vector]) + "]"

        async with self.db_client() as session:
            async with session.begin():
                search_sql = sql_text(
                    "SELECT "
                    f"{PgVectorTableScemaEnums.TEXT.value} as text, "
                    f"1 - ({PgVectorTableScemaEnums.VECTOR.value} <-> :query_vector) as score, "
                    "FROM :collection_name "
                    "ORDER BY score DESC "
                    "LIMIT :limit"
                )

                results = await session.execute(search_sql, {
                    "collection_name": collection_name,
                    "query_vector": query_vector,
                    "limit": limit
                })

                records = await results.fetchall()

        return [
            RetrievedDataChunk(
                text=record.text,
                score=record.score
            )
            for record in records
        ]
    
    