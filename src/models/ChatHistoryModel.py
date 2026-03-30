from .BaseDataModel import BaseDataModel
from .db_schemes import ChatHistory
from .enums.DataBaseEnum import DataBaseEnum
from bson.objectid import ObjectId

class ChatHistoryModel(BaseDataModel):
    
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_CHAT_HISTORY_NAME.value]
        
    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        await instance.init_collection()
        return instance
    
    async def init_collection(self):
        
        all_collections = await self.db_client.list_collection_names()
        
        if DataBaseEnum.COLLECTION_CHAT_HISTORY_NAME.value not in all_collections:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_CHAT_HISTORY_NAME.value]
            
            indexes = ChatHistory.get_indexes()
            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    name=index["name"],
                    unique=index["unique"]
                )
                
    async def insert_chat_history(self, chat_history: ChatHistory):
        result = await self.collection.insert_one(chat_history.dict(by_alias=True, exclude_unset=True))
        chat_history.id = result.inserted_id
        
        return chat_history
    
    async def get_chat_history(self, project_id: ObjectId):
        records = await self.collection.find({
            "chat_project_id": project_id
        }).to_list(length=None)
        
        return [
            ChatHistory(**record)
            for record in records
        ]
        
    
    async def clear_chat_history(self, project_id: ObjectId):
        result = await self.collection.delete_many({
            'chat_project_id': project_id
        })
        
        return result.deleted_count