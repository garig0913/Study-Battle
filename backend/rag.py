import os
from typing import List, Dict, Optional
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
import logging

logger = logging.getLogger(__name__)


class RAGPipeline:
    
    def __init__(self):
        self.indices: Dict[str, VectorStoreIndex] = {}
        self.chunk_mappings: Dict[str, Dict[str, Dict]] = {}
        self._embedding_model = None
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            try:
                self._embedding_model = OpenAIEmbedding(
                    api_key=openai_key,
                    model="text-embedding-3-small"
                )
                Settings.embed_model = self._embedding_model
                logger.info("Using OpenAI embeddings")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI embeddings: {e}")
                self._embedding_model = None
        else:
            logger.info("No OpenAI API key found, using default embeddings")
    
    def _get_vector_store(self, collection_name: str) -> Optional[MilvusVectorStore]:
        zilliz_uri = os.environ.get("ZILLIZ_URI")
        zilliz_token = os.environ.get("ZILLIZ_TOKEN")
        
        if zilliz_uri and zilliz_token:
            try:
                vector_store = MilvusVectorStore(
                    uri=zilliz_uri,
                    token=zilliz_token,
                    collection_name=collection_name,
                    dim=1536,
                    overwrite=False
                )
                logger.info(f"Connected to Zilliz Cloud: {collection_name}")
                return vector_store
            except Exception as e:
                logger.warning(f"Failed to connect to Zilliz: {e}")
        
        try:
            vector_store = MilvusVectorStore(
                uri="./milvus_data.db",
                collection_name=collection_name,
                dim=1536,
                overwrite=False
            )
            logger.info(f"Using local Milvus Lite: {collection_name}")
            return vector_store
        except Exception as e:
            logger.warning(f"Failed to create local Milvus: {e}")
            return None
    
    async def index_chunks(self, course_id: str, chunks: List[Dict]) -> int:
        if not chunks:
            return 0
        
        documents = []
        self.chunk_mappings[course_id] = {}
        
        for chunk in chunks:
            metadata = {
                "doc_id": chunk["doc_id"],
                "file_name": chunk["file_name"],
                "page_number": chunk["page_number"],
                "chunk_id": chunk["chunk_id"],
                "char_start": chunk["char_start"],
                "char_end": chunk["char_end"],
            }
            
            doc = Document(
                text=chunk["text"],
                metadata=metadata,
                id_=chunk["chunk_id"]
            )
            documents.append(doc)
            
            self.chunk_mappings[course_id][chunk["chunk_id"]] = {
                **metadata,
                "text": chunk["text"]
            }
        
        collection_name = f"study_battle_{course_id[:8]}"
        vector_store = self._get_vector_store(collection_name)
        
        if vector_store:
            try:
                storage_context = StorageContext.from_defaults(vector_store=vector_store)
                index = VectorStoreIndex.from_documents(
                    documents,
                    storage_context=storage_context,
                    show_progress=True
                )
                self.indices[course_id] = index
                logger.info(f"Indexed {len(documents)} chunks for course {course_id}")
                return len(documents)
            except Exception as e:
                logger.error(f"Failed to index with vector store: {e}")
        
        try:
            index = VectorStoreIndex.from_documents(
                documents,
                show_progress=True
            )
            self.indices[course_id] = index
            logger.info(f"Indexed {len(documents)} chunks in memory for course {course_id}")
            return len(documents)
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return 0
    
    async def retrieve(
        self, 
        course_id: str, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict]:
        if course_id not in self.indices:
            logger.warning(f"No index found for course {course_id}")
            if course_id in self.chunk_mappings:
                chunks = list(self.chunk_mappings[course_id].values())[:top_k]
                return chunks
            return []
        
        try:
            index = self.indices[course_id]
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            
            results = []
            for node in nodes:
                chunk_data = {
                    "text": node.text,
                    "score": node.score if hasattr(node, 'score') else 0.0,
                    **node.metadata
                }
                results.append(chunk_data)
            
            return results
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            if course_id in self.chunk_mappings:
                chunks = list(self.chunk_mappings[course_id].values())[:top_k]
                return chunks
            return []
    
    def get_chunk_by_id(self, course_id: str, chunk_id: str) -> Optional[Dict]:
        if course_id in self.chunk_mappings:
            return self.chunk_mappings[course_id].get(chunk_id)
        return None
    
    def get_all_chunks(self, course_id: str) -> List[Dict]:
        if course_id in self.chunk_mappings:
            return list(self.chunk_mappings[course_id].values())
        return []


rag_pipeline = RAGPipeline()
