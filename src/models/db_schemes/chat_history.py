from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid import ObjectId
from typing import List

class ChatHistory(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    chat_project_id: ObjectId
    query: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [
                    ("chat_project_id", 1)
                ],
                "name": "chat_project_id_index_1",
                "unique": False
            }
        ]