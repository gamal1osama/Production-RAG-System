from .BaseDataModel import BaseDataModel
from .db_schemas import DataChunk
from .enums import DataBaseEnum
from bson.objectid import ObjectId
from pymongo import InsertOne


class ChunkModel(BaseDataModel):

    def __init__(self, db_client):
        super().__init__(db_client)

        self.collection = self.db_client.get_collection(DataBaseEnum.COLLECTION_CHUNK_NAME.value)


    @classmethod
    async def create_instance(cls, db_client):
        # we create this method and don't use the __init__ because we need to do async calls and __init__ can't be async
        instance = cls(db_client)
        await instance.init_collection()
        return instance


    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()

        if DataBaseEnum.COLLECTION_CHUNK_NAME.value not in all_collections:
            self.collection = self.db_client.get_collection(DataBaseEnum.COLLECTION_CHUNK_NAME.value)

            indices = DataChunk.get_indices()

            for index in indices:
                await self.collection.create_index(
                    index["key"],
                    name=index["name"],
                    unique=index["unique"]
                )
        
    
    async def create_chunk(self, chunk: DataChunk):
        result = await self.collection.insert_one(chunk.dict(by_alias=True, exclude_unset=True))
        chunk.id = result.inserted_id
        return chunk
    

    async def get_chunk(self, chunk_id: str):
        result = await self.collection.find_one({"_id": ObjectId(chunk_id)})

        if result is None:
            return None
        
        return DataChunk(**result)
    
    async def insert_many_chunks(self, chunks: list[DataChunk], batch_size: int = 100):

        # Insert chunks in batches to avoid overwhelming the database using the bulk_write method for better performance
        # I can use insert_many but it may cause issues with large datasets, so I will use bulk_write with InsertOne operations for better control and error handling
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            operations = [InsertOne(chunk.dict(by_alias=True, exclude_unset=True)) for chunk in batch]
            await self.collection.bulk_write(operations)

        return len(chunks)
    
    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        result = await self.collection.delete_many({"chunk_project_id": project_id})
        return result.deleted_count
    

    async def get_project_chunks(self, project_id: ObjectId, page_no: int = 1, page_size: int = 100): # here we do pagination
        skip = (page_no - 1) * page_size
        cursor = self.collection.find(
            {
                "chunk_project_id": project_id
            }
        ).skip(skip).limit(page_size)

        records = await cursor.to_list(length=page_size)

        return [DataChunk(**record) for record in records]
    