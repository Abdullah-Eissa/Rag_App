from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from models.db_schemes import ChatHistory
from models.ChatHistoryModel import ChatHistoryModel
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List
import json


class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{project_id}".strip()
    
    def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return self.vectordb_client.delete_collection(collection_name=collection_name)
    
    def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        vectors = [
            self.embedding_client.embed_text(text=text, 
                                             document_type=DocumentTypeEnum.DOCUMENT.value)
            for text in texts
        ]

        # step3: create collection if not exists
        _ = self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        _ = self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    def search_vector_db_collection(self, project: Project, text: str, limit: int = 10,
                                    threshold: float=0.5):

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: get text embedding vector
        vector = self.embedding_client.embed_text(text=text, 
                                                 document_type=DocumentTypeEnum.QUERY.value)

        if not vector or len(vector) == 0:
            return False

        # step3: do semantic search
        results = self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=vector,
            limit=limit,
            threshold=threshold
        )

        if not results:
            return False

        return results
    
    
    def search_cache_collection(self, project: Project, query: str, limit: int = 1,
                                threshold: float=0.8, cache_do_reset: bool = False):
        
        cache_collection_name = self.create_collection_name(project_id='cache_' + project.project_id)
        
        self.vectordb_client.create_collection(
            collection_name=cache_collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=cache_do_reset
        )
        
        vector = self.embedding_client.embed_text(
            text=query,
            document_type=DocumentTypeEnum.QUERY.value
        )

        if not vector or len(vector) == 0:
            return False
        
        results = self.vectordb_client.search_by_vector(
            collection_name=cache_collection_name,
            vector=vector,
            limit=limit,
            threshold=threshold
        )
        
        if not results:
            return False
        
        
        return results
    
    def answer_rag_question(self, project: Project, query: str, previous_chat_history: List[ChatHistory], limit: int = 10,
                            threshold: float=0.5, cache_do_reset: bool = False):
        
        answer, full_prompt, chat_history = None, None, None
        
        cache_retrieval_result = self.search_cache_collection(
                project=project,
                query=query,
                cache_do_reset=cache_do_reset
            )
        
        if cache_retrieval_result and len(cache_retrieval_result) > 0:
            system_prompt = self.template_parser.get(
                group='rag',
                key='system_prompt',
            )
            
            footer_prompt = self.template_parser.get(
                group='rag', key='footer_prompt',
                vars={'query': query}
            )
            
            chat_history = [
                self.generation_client.construct_prompt(
                    prompt=system_prompt,
                    role=self.generation_client.enums.SYSTEM.value
                )
            ]
            
            full_prompt = '\n\n'.join([footer_prompt])
            
            documents = ''
            answer = cache_retrieval_result[0].metadata.get('response')
        else:
            # step1: retrieve related documents
            retrieved_documents = self.search_vector_db_collection(
                project=project,
                text=query,
                limit=limit,
                threshold=threshold
            )

            if not retrieved_documents or len(retrieved_documents) == 0:
                return None
            
            system_prompt = self.template_parser.get(
                group='rag',
                key='system_prompt',
            )
            
            conversation_history = ChatHistoryModel.get_conversation_history(
                previous_chat_history=previous_chat_history,
                generation_client=self.generation_client
            )
                            
            document_prompts = '\n'.join([
                self.template_parser.get(
                    group='rag',
                    key='document_prompt',
                    vars={
                        'doc_num': idx + 1,
                        'chunk_text': doc.text
                    }
                )
                for idx, doc in enumerate(retrieved_documents)
            ])
            
            documents = [f'Document: {idx+1}\n{doc.text}\n\n' for idx, doc in enumerate(retrieved_documents)]
            
            footer_prompt = self.template_parser.get(
                group='rag', key='footer_prompt',
                vars={'query': query}
            )
            
            chat_history = [
                self.generation_client.construct_prompt(
                    prompt=system_prompt,
                    role=self.generation_client.enums.SYSTEM.value
                )
            ]
            
            chat_history.extend(conversation_history)
            
            full_prompt = '\n\n'.join([document_prompts, footer_prompt])
            
            answer = self.generation_client.generate_text(
                prompt=full_prompt,
                chat_history=chat_history
            )
            
            # if the query vector doesn't exists in the cache, add the vector to the cache with the response
            cache_collection_name = self.create_collection_name(project_id='cache_' + project.project_id)
            
            vector = self.embedding_client.embed_text(
                text=query,
                document_type=DocumentTypeEnum.QUERY.value
            )
            
            self.vectordb_client.insert_one(collection_name=cache_collection_name,
                                            text=query,
                                            vector=vector,
                                            metadata={
                                                'response': answer
                                            })


        return answer, full_prompt, chat_history, documents