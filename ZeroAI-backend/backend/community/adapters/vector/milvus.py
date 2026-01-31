"""
Milvus Adapter for Cognee

This adapter allows Cognee to use Milvus as a vector database.
"""
import asyncio
from typing import List, Optional, Any
from pymilvus import connections, Collection, utility, FieldSchema, CollectionSchema, DataType
from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.databases.vector.embeddings.EmbeddingEngine import EmbeddingEngine
from cognee.infrastructure.databases.vector.vector_db_interface import VectorDBInterface
from cognee.infrastructure.databases.vector.models.ScoredResult import ScoredResult
import logging

logger = logging.getLogger(__name__)


class IndexSchema(DataPoint):
    """
    Represents a schema for an index data point containing an ID and text.
    
    Attributes:
    - id: A string representing the unique identifier for the data point.
    - text: A string representing the content of the data point.
    - metadata: A dictionary with default index fields for the schema, currently configured
      to include 'text'.
    """
    id: str
    text: str
    metadata: dict = {"index_fields": ["text"]}


class MilvusAdapter(VectorDBInterface):
    """Milvus adapter for Cognee vector database"""
    
    name = "Milvus"
    
    def __init__(
        self,
        url: Optional[str],
        api_key: Optional[str],
        embedding_engine: EmbeddingEngine,
        database_name: Optional[str] = None,
    ):
        self.url = url or "http://localhost:19530"
        self.api_key = api_key
        self.embedding_engine = embedding_engine
        self.database_name = database_name  # Milvus 中 database_name 用于多租户，可选
        self.VECTOR_DB_LOCK = asyncio.Lock()
        self._connected = False
        
        # 解析 URL 获取 host 和 port
        if self.url.startswith("http://"):
            url_parts = self.url.replace("http://", "").split(":")
            self.host = url_parts[0]
            self.port = int(url_parts[1]) if len(url_parts) > 1 else 19530
        else:
            self.host = self.url.split(":")[0]
            self.port = int(self.url.split(":")[1]) if ":" in self.url else 19530
        
        # 解析认证信息（如果 api_key 是 username:password 格式）
        self.username = None
        self.password = None
        if self.api_key and ":" in self.api_key:
            self.username, self.password = self.api_key.split(":", 1)
    
    async def _ensure_connection(self):
        """确保 Milvus 连接已建立"""
        alias = "cognee_milvus"
        try:
            # 检查连接是否已存在
            if connections.has_connection(alias):
                self._connected = True
                return
        except:
            pass
        
        if not self._connected:
            try:
                connection_params = {
                    "host": self.host,
                    "port": self.port
                }
                
                if self.username and self.password:
                    connection_params["user"] = self.username
                    connection_params["password"] = self.password
                
                # 如果连接已存在，先断开
                try:
                    if connections.has_connection(alias):
                        connections.disconnect(alias)
                except:
                    pass
                
                connections.connect(alias=alias, **connection_params)
                self._connected = True
                logger.info(f"成功连接到 Milvus: {self.host}:{self.port}")
            except Exception as e:
                logger.error(f"连接 Milvus 失败: {e}")
                raise
    
    async def has_collection(self, collection_name: str) -> bool:
        """检查 collection 是否存在"""
        await self._ensure_connection()
        
        # 确保连接存在
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        # utility 函数需要使用连接别名
        return utility.has_collection(collection_name, using=alias)
    
    async def create_collection(
        self,
        collection_name: str,
        payload_schema: Optional[Any] = None,
    ):
        """创建 collection"""
        print(f"[DEBUG MilvusAdapter] create_collection called with collection_name: {collection_name}")
        logger.info(f"[MilvusAdapter] create_collection called with collection_name: {collection_name}")
        await self._ensure_connection()
        
        if await self.has_collection(collection_name):
            print(f"[DEBUG MilvusAdapter] Collection {collection_name} 已存在")
            logger.info(f"Collection {collection_name} 已存在")
            return
        
        # 获取 embedding 维度
        dim = 1024  # 默认维度，可以从 embedding_engine 获取
        if hasattr(self.embedding_engine, 'dimensions'):
            dim = self.embedding_engine.dimensions
        
        # 定义 schema
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="metadata", dtype=DataType.JSON),
        ]
        
        schema = CollectionSchema(fields=fields, description=f"Cognee collection: {collection_name}")
        
        # 确保连接存在
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        # Collection 需要使用连接别名
        collection = Collection(name=collection_name, schema=schema, using=alias)
        
        # 创建索引
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        
        logger.info(f"成功创建 Collection: {collection_name}")
    
    async def create_data_points(self, collection_name: str, data_points: List[DataPoint]):
        """插入数据点"""
        print(f"[DEBUG MilvusAdapter] create_data_points called with collection_name: {collection_name}")
        logger.info(f"[MilvusAdapter] create_data_points called with collection_name: {collection_name}")
        await self._ensure_connection()
        
        # 确保 collection 存在
        if not await self.has_collection(collection_name):
            print(f"[DEBUG MilvusAdapter] Creating new collection: {collection_name}")
            logger.info(f"[MilvusAdapter] Creating new collection: {collection_name}")
            await self.create_collection(collection_name)
        else:
            print(f"[DEBUG MilvusAdapter] Collection {collection_name} already exists")
            logger.info(f"[MilvusAdapter] Collection {collection_name} already exists")
        
        # 使用连接别名
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        collection = Collection(collection_name, using=alias)
        
        # 准备数据（过滤掉无效的数据点）
        valid_data_points = []
        ids = []
        texts = []
        metadatas = []
        
        for data_point in data_points:
            # 使用 DataPoint.get_embeddable_data() 获取可嵌入的文本（参考 LanceDBAdapter）
            embeddable_text = DataPoint.get_embeddable_data(data_point)
            
            # 检查文本是否有效（不能为空或None）
            if not embeddable_text or not str(embeddable_text).strip():
                logger.warning(f"数据点 {data_point.id} 的文本为空，跳过")
                continue
            
            valid_data_points.append(data_point)
            ids.append(str(data_point.id))
            texts.append(str(embeddable_text))
            metadatas.append(data_point.metadata if hasattr(data_point, 'metadata') else {})
        
        if not valid_data_points:
            logger.warning(f"没有有效的数据点可以插入到 {collection_name}")
            return
        
        # 生成向量（批量生成）
        try:
            vectors = await self.embedding_engine.embed_text(texts)
            
            # 验证向量是否有效
            if not vectors or len(vectors) != len(texts):
                logger.error(f"向量生成失败：期望 {len(texts)} 个向量，实际得到 {len(vectors) if vectors else 0} 个")
                raise Exception(f"向量生成失败：向量数量不匹配")
            
            # 检查每个向量是否有效（不能为 None 或空）
            valid_indices = []
            valid_ids = []
            valid_texts = []
            valid_vectors = []
            valid_metadatas = []
            
            for i, vector in enumerate(vectors):
                if vector is None or (isinstance(vector, list) and len(vector) == 0):
                    logger.warning(f"数据点 {ids[i]} 的向量为 None 或空，跳过")
                    continue
                
                # 确保向量是列表格式
                if not isinstance(vector, list):
                    vector = list(vector)
                
                valid_indices.append(i)
                valid_ids.append(ids[i])
                valid_texts.append(texts[i])
                valid_vectors.append(vector)
                valid_metadatas.append(metadatas[i])
            
            if not valid_vectors:
                logger.warning(f"没有有效的向量可以插入到 {collection_name}")
                return
            
            # 插入数据
            data = [valid_ids, valid_texts, valid_vectors, valid_metadatas]
            collection.insert(data)
            collection.flush()
            
            logger.info(f"成功插入 {len(valid_vectors)} 个数据点到 {collection_name}（跳过了 {len(data_points) - len(valid_vectors)} 个无效数据点）")
            
        except Exception as e:
            logger.error(f"生成向量或插入数据失败: {e}", exc_info=True)
            raise
    
    async def retrieve(self, collection_name: str, data_point_ids: list[str]):
        """根据 ID 检索数据点"""
        await self._ensure_connection()
        
        if not await self.has_collection(collection_name):
            raise Exception(f"Collection {collection_name} 不存在")
        
        # 确保连接存在
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        collection = Collection(collection_name, using=alias)
        collection.load()
        
        # 查询数据
        results = collection.query(
            expr=f'id in {data_point_ids}',
            output_fields=["id", "text", "metadata"]
        )
        
        return results
    
    async def search(
        self,
        collection_name: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        limit: Optional[int] = 15,
        with_vector: bool = False,
    ):
        """搜索数据"""
        await self._ensure_connection()
        
        # 确保连接存在
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        # 如果 collection 不存在，返回空结果（Cognee 可能会查询不存在的 collection）
        if not await self.has_collection(collection_name):
            logger.warning(f"Collection {collection_name} 不存在，返回空结果")
            return []
        
        collection = Collection(collection_name, using=alias)
        collection.load()
        
        # 如果没有提供向量，从文本生成
        if query_vector is None:
            if query_text is None:
                raise Exception("必须提供 query_text 或 query_vector")
            query_vector = (await self.embedding_engine.embed_text([query_text]))[0]
        
        # 搜索参数
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10}
        }
        
        # 执行搜索
        results = collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=limit or 10,
            output_fields=["id", "text", "metadata"]
        )
        
        # 转换结果格式
        scored_results = []
        for hits in results:
            for hit in hits:
                # ScoredResult 需要 payload 字段，包含 text 和 metadata
                payload = {
                    "text": hit.entity.get("text", ""),
                    "metadata": hit.entity.get("metadata", {})
                }
                scored_results.append(ScoredResult(
                    id=hit.id,
                    score=hit.score,
                    payload=payload
                ))
        
        return scored_results
    
    async def embed_data(self, data: list[str]) -> list[list[float]]:
        """嵌入文本数据"""
        return await self.embedding_engine.embed_text(data)
    
    async def create_vector_index(self, index_name: str, index_property_name: str):
        """创建向量索引（Cognee 会先调用这个方法）"""
        collection_name = f"{index_name}_{index_property_name}"
        print(f"[DEBUG MilvusAdapter] create_vector_index called with index_name: {index_name}, index_property_name: {index_property_name}, collection_name: {collection_name}")
        logger.info(f"[MilvusAdapter] create_vector_index called with collection_name: {collection_name}")
        # 创建 collection（如果不存在）
        if not await self.has_collection(collection_name):
            await self.create_collection(collection_name)
    
    async def batch_search(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_vectors: Optional[List[List[float]]] = None,
        limit: Optional[int] = 15,
        with_vector: bool = False,
    ):
        """批量搜索"""
        await self._ensure_connection()
        
        # 确保连接存在
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        # 如果 collection 不存在，返回空结果
        if not await self.has_collection(collection_name):
            logger.warning(f"Collection {collection_name} 不存在，返回空结果")
            return []
        
        collection = Collection(collection_name, using=alias)
        collection.load()
        
        # 如果没有提供向量，从文本生成
        if query_vectors is None:
            if query_texts is None:
                raise Exception("必须提供 query_texts 或 query_vectors")
            query_vectors = await self.embedding_engine.embed_text(query_texts)
        
        # 搜索参数
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10}
        }
        
        # 执行批量搜索
        results = collection.search(
            data=query_vectors,
            anns_field="vector",
            param=search_params,
            limit=limit or 10,
            output_fields=["id", "text", "metadata"]
        )
        
        # 转换结果格式
        all_scored_results = []
        for hits in results:
            scored_results = []
            for hit in hits:
                # ScoredResult 需要 payload 字段，包含 text 和 metadata
                payload = {
                    "text": hit.entity.get("text", ""),
                    "metadata": hit.entity.get("metadata", {})
                }
                scored_results.append(ScoredResult(
                    id=hit.id,
                    score=hit.score,
                    payload=payload
                ))
            all_scored_results.append(scored_results)
        
        return all_scored_results
    
    async def delete_data_points(self, collection_name: str, data_point_ids: list[str]):
        """删除数据点"""
        await self._ensure_connection()
        
        if not await self.has_collection(collection_name):
            raise Exception(f"Collection {collection_name} 不存在")
        
        # 确保连接存在
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        collection = Collection(collection_name, using=alias)
        collection.load()
        
        # 删除数据
        collection.delete(expr=f'id in {data_point_ids}')
        collection.flush()
        
        logger.info(f"成功删除 {len(data_point_ids)} 个数据点")
    
    async def index_data_points(self, index_name: str, index_property_name: str, data_points: List[DataPoint]):
        """索引数据点（Cognee 使用这个方法，它会调用 create_data_points）"""
        collection_name = f"{index_name}_{index_property_name}"
        print(f"[DEBUG MilvusAdapter] index_data_points called with index_name: {index_name}, index_property_name: {index_property_name}, collection_name: {collection_name}, data_points count: {len(data_points)}")
        logger.info(f"[MilvusAdapter] index_data_points called with collection_name: {collection_name}")
        
        # 参考 LanceDBAdapter：创建 IndexSchema 数据点，提取正确的文本字段
        indexed_data_points = []
        for data_point in data_points:
            # 从 metadata["index_fields"][0] 获取字段名，然后使用 getattr 获取值
            field_name = data_point.metadata.get("index_fields", [index_property_name])[0]
            text_value = getattr(data_point, field_name, None)
            if text_value is None:
                # 如果没有找到字段，尝试使用 get_embeddable_data
                text_value = DataPoint.get_embeddable_data(data_point) or str(data_point)
            
            indexed_data_points.append(
                IndexSchema(
                    id=str(data_point.id),
                    text=str(text_value) if text_value else "",
                )
            )
        
        # 调用 create_data_points
        return await self.create_data_points(collection_name, indexed_data_points)
    
    async def create_dataset(self, dataset_name: str):
        """创建数据集（Cognee 可能使用这个方法）"""
        print(f"[DEBUG MilvusAdapter] create_dataset called with dataset_name: {dataset_name}")
        logger.info(f"[MilvusAdapter] create_dataset called with dataset_name: {dataset_name}")
        # 对于 Milvus，dataset 可能对应 collection，但通常不需要特殊处理
        pass
    
    async def prune(self, collection_name: str):
        """清理 collection（可选操作）"""
        print(f"[DEBUG MilvusAdapter] prune called with collection_name: {collection_name}")
        logger.info(f"[MilvusAdapter] prune called with collection_name: {collection_name}")
        await self._ensure_connection()
        
        # 确保连接存在
        alias = "cognee_milvus"
        if not connections.has_connection(alias):
            await self._ensure_connection()
        
        if await self.has_collection(collection_name):
            # 可以选择删除整个 collection 或只清理数据
            # 这里我们选择删除整个 collection
            utility.drop_collection(collection_name, using=alias)
            logger.info(f"成功删除 Collection: {collection_name}")


# Register function for Cognee
def register():
    """Register Milvus adapter with Cognee"""
    from cognee.infrastructure.databases.vector import use_vector_adapter
    use_vector_adapter("milvus", MilvusAdapter)
    logger.info("Milvus adapter registered with Cognee")


# Auto-register when module is imported (like cognee_community_vector_adapter_milvus)
register()

