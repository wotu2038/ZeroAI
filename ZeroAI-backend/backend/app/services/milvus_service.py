"""
Milvus 向量存储服务

管理知识图谱和文档的向量存储：

【Graphiti知识图谱相关】
- graphiti_entity_vectors: Graphiti实体向量
- graphiti_edge_vectors: Graphiti关系向量
- graphiti_episode_vectors: Graphiti Episode向量
- graphiti_community_vectors: Graphiti社区向量

【文档相关内容（非知识图谱）】
- document_summary_vectors: 文档摘要向量（从summary_content_path读取）
- document_section_vectors: 文档章节向量（文档分块的章节内容）
- document_image_vectors: 文档图片向量（OCR文字）
- document_table_vectors: 文档表格向量（结构化文本）

【Cognee知识图谱相关】
- Cognee_entity_vectors: Cognee生成的KnowledgeNode向量
- Cognee_edge_vectors: Cognee生成的关系向量
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from app.core.config import settings

logger = logging.getLogger(__name__)

# Milvus 客户端（延迟导入）
_milvus_client = None


class VectorType(Enum):
    """向量类型"""
    ENTITY = "entity"
    EDGE = "edge"
    EPISODE = "episode"  # Graphiti Episode向量（文档级别的事件元数据+章节标题）
    DOCUMENT_SUMMARY = "document_summary"  # 文档摘要向量（从summary_content_path读取的完整摘要）
    COMMUNITY = "community"
    SECTION = "section"  # 新增：章节向量类型
    IMAGE = "image"      # 新增：图片向量类型
    TABLE = "table"      # 新增：表格向量类型
    COGNEE_ENTITY = "cognee_entity"  # Cognee生成的KnowledgeNode向量
    COGNEE_EDGE = "cognee_edge"      # Cognee生成的关系向量


@dataclass
class VectorSearchResult:
    """向量搜索结果"""
    id: str
    uuid: str
    name: str
    score: float
    vector_type: VectorType
    group_id: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict] = None


# Collection 配置
COLLECTION_CONFIGS = {
    VectorType.ENTITY: {
        "name": "graphiti_entity_vectors",
        "description": "Graphiti Entity向量存储",
        "dimension": 1024,  # BGE-large-zh 向量维度
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.EDGE: {
        "name": "graphiti_edge_vectors",
        "description": "Graphiti Edge向量存储",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.EPISODE: {
        "name": "graphiti_episode_vectors",
        "description": "Graphiti Episode向量存储（文档级别的事件元数据+章节标题）",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.DOCUMENT_SUMMARY: {
        "name": "document_summary_vectors",
        "description": "文档摘要向量存储（从summary_content_path读取的完整摘要）",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.COMMUNITY: {
        "name": "graphiti_community_vectors",
        "description": "Graphiti Community向量存储",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 512
    },
    VectorType.SECTION: {
        "name": "document_section_vectors",
        "description": "文档章节向量存储（文档分块的章节内容）",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.IMAGE: {
        "name": "document_image_vectors",
        "description": "文档图片向量存储（OCR文字）",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.TABLE: {
        "name": "document_table_vectors",
        "description": "文档表格向量存储（结构化文本）",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.COGNEE_ENTITY: {
        "name": "Cognee_entity_vector_storage",
        "description": "Cognee生成的KnowledgeNode向量存储（Rule、Constraint、Flow等）",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    },
    VectorType.COGNEE_EDGE: {
        "name": "Cognee_edge_vector_storage",
        "description": "Cognee生成的关系向量存储",
        "dimension": 1024,
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "nlist": 1024
    }
}


class MilvusService:
    """Milvus 向量存储服务"""
    
    def __init__(self):
        self.enabled = getattr(settings, 'ENABLE_MILVUS', False)
        self.host = getattr(settings, 'MILVUS_HOST', '')
        self.port = getattr(settings, 'MILVUS_PORT', 19530)
        self.username = getattr(settings, 'MILVUS_USERNAME', '')
        self.password = getattr(settings, 'MILVUS_PASSWORD', '')
        
        self._client = None
        self._connected = False
        
        if self.enabled and self.host:
            self._connect()
    
    def _connect(self) -> bool:
        """连接到 Milvus"""
        if self._connected:
            return True
        
        try:
            from pymilvus import connections, utility
            
            connection_params = {
                "host": self.host,
                "port": self.port
            }
            
            if self.username and self.password:
                connection_params["user"] = self.username
                connection_params["password"] = self.password
            
            connections.connect(alias="default", **connection_params)
            self._connected = True
            logger.info(f"成功连接到 Milvus: {self.host}:{self.port}")
            
            return True
            
        except Exception as e:
            logger.error(f"连接 Milvus 失败: {e}")
            self._connected = False
            return False
    
    def is_available(self) -> bool:
        """检查 Milvus 是否可用"""
        if not self.enabled:
            return False
        
        try:
            if not self._connected:
                self._connect()
            
            if not self._connected:
                return False
            
            # 使用 list_collections 验证连接是否有效
            from pymilvus import utility
            utility.list_collections()
            return True
            
        except Exception as e:
            logger.warning(f"Milvus 不可用: {e}")
            self._connected = False
            return False
    
    def ensure_collections(self) -> bool:
        """确保所有 Collection 存在"""
        if not self.is_available():
            return False
        
        try:
            from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
            
            for vector_type, config in COLLECTION_CONFIGS.items():
                collection_name = config["name"]
                
                # 检查是否存在
                if utility.has_collection(collection_name):
                    logger.info(f"Collection 已存在: {collection_name}")
                    continue
                
                # 创建 Schema
                fields = [
                    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema(name="uuid", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=512),
                    FieldSchema(name="group_id", dtype=DataType.VARCHAR, max_length=128),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=config["dimension"])
                ]
                
                schema = CollectionSchema(
                    fields=fields,
                    description=config["description"]
                )
                
                # 创建 Collection
                collection = Collection(name=collection_name, schema=schema)
                
                # 创建索引
                index_params = {
                    "index_type": config["index_type"],
                    "metric_type": config["metric_type"],
                    "params": {"nlist": config["nlist"]}
                }
                collection.create_index(field_name="embedding", index_params=index_params)
                
                logger.info(f"成功创建 Collection: {collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"创建 Collection 失败: {e}")
            return False
    
    def insert_vectors(
        self,
        vector_type: VectorType,
        vectors: List[Dict[str, Any]]
    ) -> List[int]:
        """
        批量插入向量
        
        Args:
            vector_type: 向量类型
            vectors: 向量数据列表，每个包含 uuid, name, group_id, content, embedding
            
        Returns:
            插入的 ID 列表
        """
        if not self.is_available():
            logger.warning("Milvus 不可用，跳过向量插入")
            return []
        
        try:
            from pymilvus import Collection
            
            config = COLLECTION_CONFIGS[vector_type]
            collection = Collection(config["name"])
            collection.load()
            
            # 准备数据（确保 name 字段不超过 512 字符）
            # 先截断每个向量的 name 字段
            for i, v in enumerate(vectors):
                name = v.get("name", "")
                if not isinstance(name, str):
                    name = str(name) if name else ""
                    v["name"] = name
                
                if len(name) > 512:
                    original_len = len(name)
                    v["name"] = name[:512]
                    logger.warning(f"向量 {i}: 截断 name 字段: 原始长度 {original_len}, 截断后长度 {len(v['name'])}")
                    logger.warning(f"向量 {i}: name 前100字符: {name[:100]}")
            
            # 构建数据列表，再次确保截断
            names_list = []
            for v in vectors:
                name = v.get("name", "")
                if not isinstance(name, str):
                    name = str(name) if name else ""
                truncated_name = name[:512] if len(name) > 512 else name
                if len(truncated_name) > 512:
                    logger.error(f"严重错误：截断后 name 仍然超过 512 字符！长度: {len(truncated_name)}")
                    truncated_name = truncated_name[:512]
                names_list.append(truncated_name)
            
            data = [
                [v.get("uuid", "") for v in vectors],
                names_list,  # 使用预处理后的 names_list
                [v.get("group_id", "") for v in vectors],
                [v.get("content", "")[:65535] for v in vectors],
                [v.get("embedding", []) for v in vectors]
            ]
            
            # 最终验证：检查 names_list 中是否有超过 512 字符的
            max_name_len = max([len(n) for n in names_list]) if names_list else 0
            if max_name_len > 512:
                logger.error(f"最终验证失败：names_list 中最大长度 {max_name_len} 仍然超过 512！")
                for i, name in enumerate(names_list):
                    if len(name) > 512:
                        logger.error(f"  向量 {i}: 长度 {len(name)}, 内容: {name[:100]}...")
                        # 强制截断
                        names_list[i] = name[:512]
            else:
                logger.info(f"最终验证通过：names_list 中最大长度 {max_name_len}")
            
            # 最后一次确保所有 name 都不超过 512（使用字节长度，因为 Milvus VARCHAR 是按字节计算的）
            for i in range(len(names_list)):
                name = names_list[i]
                # 先按字符截断到 512
                if len(name) > 512:
                    name = name[:512]
                # 再按字节截断（UTF-8 编码，中文字符可能占 3 字节）
                name_bytes = name.encode('utf-8')
                if len(name_bytes) > 512:
                    # 如果字节长度超过 512，需要截断字节
                    name_bytes = name_bytes[:512]
                    # 尝试解码，如果截断导致不完整字符，去掉最后一个不完整字符
                    try:
                        name = name_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        # 如果解码失败，去掉最后一个字节再试
                        name_bytes = name_bytes[:-1]
                        try:
                            name = name_bytes.decode('utf-8')
                        except UnicodeDecodeError:
                            # 如果还是失败，继续去掉
                            name_bytes = name_bytes[:-1]
                            name = name_bytes.decode('utf-8', errors='ignore')
                    logger.warning(f"向量 {i}: name 字节长度超过 512，已截断为 {len(name_bytes)} 字节 ({len(name)} 字符)")
                names_list[i] = name
            
            # 更新 data 列表中的 names_list
            data[1] = names_list
            
            # 最终验证：检查所有 name 的字节长度
            max_bytes = max([len(n.encode('utf-8')) for n in names_list]) if names_list else 0
            if max_bytes > 512:
                logger.error(f"最终字节验证失败：最大字节长度 {max_bytes} 仍然超过 512！")
            else:
                logger.info(f"最终字节验证通过：最大字节长度 {max_bytes}")
            
            # 插入数据
            result = collection.insert(data)
            
            logger.info(f"成功插入 {len(vectors)} 个向量到 {config['name']}")
            return result.primary_keys
            
        except Exception as e:
            logger.error(f"插入向量失败: {e}")
            return []
    
    def search_vectors(
        self,
        vector_type: VectorType,
        query_embedding: List[float],
        top_k: int = 10,
        group_ids: Optional[List[str]] = None,
        min_score: float = 0.5
    ) -> List[VectorSearchResult]:
        """
        搜索相似向量
        
        Args:
            vector_type: 向量类型
            query_embedding: 查询向量
            top_k: 返回数量
            group_ids: 过滤的 group_id 列表
            min_score: 最小相似度阈值
            
        Returns:
            搜索结果列表
        """
        if not self.is_available():
            logger.warning("Milvus 不可用，返回空结果")
            return []
        
        try:
            from pymilvus import Collection
            
            config = COLLECTION_CONFIGS[vector_type]
            collection = Collection(config["name"])
            collection.load()
            
            # 构建过滤表达式
            expr = None
            if group_ids:
                group_ids_str = ", ".join([f'"{gid}"' for gid in group_ids])
                expr = f"group_id in [{group_ids_str}]"
            
            # 搜索参数
            search_params = {
                "metric_type": config["metric_type"],
                "params": {"nprobe": 10}
            }
            
            # 执行搜索
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["uuid", "name", "group_id", "content"]
            )
            
            # 处理结果
            search_results = []
            for hit in results[0]:
                score = hit.score
                
                # 过滤低分结果
                if score < min_score:
                    continue
                
                search_results.append(VectorSearchResult(
                    id=str(hit.id),
                    uuid=hit.entity.get("uuid", ""),
                    name=hit.entity.get("name", ""),
                    score=score,
                    vector_type=vector_type,
                    group_id=hit.entity.get("group_id"),
                    content=hit.entity.get("content")
                ))
            
            logger.info(f"搜索到 {len(search_results)} 个结果 (type={vector_type.value})")
            return search_results
            
        except Exception as e:
            logger.error(f"搜索向量失败: {e}")
            return []
    
    def delete_by_group_id(
        self,
        vector_type: VectorType,
        group_id: str
    ) -> bool:
        """
        删除指定 group_id 的所有向量
        
        Args:
            vector_type: 向量类型
            group_id: 要删除的 group_id
            
        Returns:
            是否成功
        """
        if not self.is_available():
            return False
        
        try:
            from pymilvus import Collection
            
            config = COLLECTION_CONFIGS[vector_type]
            collection = Collection(config["name"])
            
            expr = f'group_id == "{group_id}"'
            collection.delete(expr)
            
            logger.info(f"成功删除 group_id={group_id} 的向量 (type={vector_type.value})")
            return True
            
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False
    
    def delete_by_uuid(
        self,
        vector_type: VectorType,
        uuid: str
    ) -> bool:
        """
        删除指定 UUID 的向量
        
        Args:
            vector_type: 向量类型
            uuid: 要删除的 UUID
            
        Returns:
            是否成功
        """
        if not self.is_available():
            return False
        
        try:
            from pymilvus import Collection
            
            config = COLLECTION_CONFIGS[vector_type]
            collection = Collection(config["name"])
            
            expr = f'uuid == "{uuid}"'
            collection.delete(expr)
            
            logger.info(f"成功删除 uuid={uuid} 的向量 (type={vector_type.value})")
            return True
            
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False
    
    def get_collection_stats(self, vector_type: VectorType) -> Dict[str, Any]:
        """获取 Collection 统计信息"""
        if not self.is_available():
            return {"available": False}
        
        try:
            from pymilvus import Collection
            
            config = COLLECTION_CONFIGS[vector_type]
            collection = Collection(config["name"])
            
            return {
                "available": True,
                "name": config["name"],
                "num_entities": collection.num_entities,
                "dimension": config["dimension"]
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"available": False, "error": str(e)}
    
    def close(self):
        """关闭连接"""
        if self._connected:
            try:
                from pymilvus import connections
                connections.disconnect("default")
                self._connected = False
                logger.info("Milvus 连接已关闭")
            except Exception as e:
                logger.warning(f"关闭 Milvus 连接失败: {e}")


# 全局实例
_milvus_service: Optional[MilvusService] = None


def get_milvus_service() -> MilvusService:
    """获取 Milvus 服务实例（单例）"""
    global _milvus_service
    if _milvus_service is None:
        _milvus_service = MilvusService()
    return _milvus_service

