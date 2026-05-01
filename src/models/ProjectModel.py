from .BaseDataModel import BaseDataModel
from .db_schemas import Project
from .enums import DataBaseEnum

class ProjectModel(BaseDataModel):

    def __init__(self, db_client):
        super().__init__(db_client)

        self.collection = self.db_client[DataBaseEnum.COLLECTION_PROJECT_NAME.value]


    @classmethod
    async def create_instance(cls, db_client):
        # we create this method and don't use the __init__ because we need to do async calls and __init__ can't be async
        instance = cls(db_client)
        await instance.init_collection()
        return instance


    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()

        if DataBaseEnum.COLLECTION_PROJECT_NAME.value not in all_collections:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_PROJECT_NAME.value]

            indices = Project.get_indices()

            for index in indices:
                await self.collection.create_index(
                    index["key"],
                    name=index["name"],
                    unique=index.get("unique")
                )



    async def create_project(self, project: Project):
        
        result = await self.collection.insert_one(project.dict(by_alias=True, exclude_unset=True))
        project._id = result.inserted_id
        
        return project
    

    async def get_project_or_create(self, project_id: str):
        
        record = await self.collection.find_one({"project_id": project_id})

        if record is None:
            project = Project(project_id=project_id)
            project = await self.create_project(project)
            
            return project
        
        return Project(**record)
    

    async def get_all_projects(self, page: int = 1, page_size: int = 10): # we do pagination here to avoid fetching too many records at once
        
        # coount total records
        total_records = await self.collection.count_documents({})
        
        # calculate total pages
        total_pages = total_records // page_size
        if total_records % page_size > 0:
            total_pages += 1

        # fetch records for the requested page
        skip = (page - 1) * page_size
        cursor = self.collection.find().skip(skip).limit(page_size)

        projects = []
        async for record in cursor:
            projects.append(Project(**record))

        return projects, total_pages
    