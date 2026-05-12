from .BaseDataModel import BaseDataModel
from .db_schemas import DataChunk
from .enums import DataBaseEnum

from sqlalchemy.future import select
from sqlalchemy import delete
from bson.objectid import ObjectId
from pymongo import InsertOne


class ChunkModel(BaseDataModel):

    def __init__(self, db_client):
        super().__init__(db_client)

        self.db_client = self.db_client

    @classmethod
    async def create_instance(cls, db_client):
        # we create this method and don't use the __init__ because we need to do async calls and __init__ can't be async
        instance = cls(db_client)
        return instance



    async def create_chunk(self, chunk: DataChunk):
        async with self.db_client() as session:
            async with session.begin():
                session.add(chunk)
            await session.commit()
            await session.refresh(chunk)
        
        return chunk
    

    async def get_chunk(self, chunk_id: str):
        async with self.db_client() as session:
            async with session.begin():
                result = await session.execute(select(DataChunk).where(DataChunk.chunk_id == chunk_id))
                chunk = result.scalar_one_or_none()
        
        return chunk
    

    
    async def insert_many_chunks(self, chunks: list[DataChunk], batch_size: int = 100):

        # Insert chunks in batches to avoid overwhelming the database using the bulk_write method for better performance
        # I can use insert_many but it may cause issues with large datasets, so I will use bulk_write with InsertOne operations for better control and error handling
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    session.add_all(batch)
            await session.commit()

        return len(chunks)
    
    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        async with self.db_client() as session:
            async with session.begin():
                stmt = delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
                results = await session.execute(stmt)
            await session.commit()
        return results.rowcount  # Return the number of deleted records
    

    async def get_project_chunks(self, project_id: ObjectId, page_no: int = 1, page_size: int = 100): # here we do pagination
        async with self.db_client() as session:
            async with session.begin():
                skip = (page_no - 1) * page_size
                stmt = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset(skip).limit(page_size)
                result = await session.execute(stmt)
                chunks = result.scalars().all()
        
        return chunks
    