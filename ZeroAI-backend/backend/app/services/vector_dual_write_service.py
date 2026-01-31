"""
向量双写服务

在写入 Neo4j 的同时，将向量同步到 Milvus
确保两个存储的数据一致性
"""
import logging
from typing import Dict, List, Any, Optional
from app.services.milvus_service import (
    MilvusService, 
    VectorType, 
    get_milvus_service
)
from app.core.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


class VectorDualWriteService:
    """
    向量双写服务
    
    负责将 Graphiti 生成的向量同时写入 Neo4j 和 Milvus
    """
    
    def __init__(self, milvus_service: MilvusService = None):
        self.milvus = milvus_service or get_milvus_service()
    
    async def sync_entity_to_milvus(
        self,
        entity_uuid: str,
        name: str,
        group_id: str,
        summary: str,
        embedding: List[float]
    ) -> bool:
        """
        同步实体向量到 Milvus
        
        Args:
            entity_uuid: 实体 UUID
            name: 实体名称
            group_id: 分组 ID
            summary: 实体摘要
            embedding: 向量
            
        Returns:
            是否成功
        """
        if not self.milvus.is_available():
            logger.debug("Milvus 不可用，跳过实体向量同步")
            return False
        
        try:
            # 先删除旧的（如果存在）
            self.milvus.delete_by_uuid(VectorType.ENTITY, entity_uuid)
            
            # 插入新的
            result = self.milvus.insert_vectors(
                vector_type=VectorType.ENTITY,
                vectors=[{
                    "uuid": entity_uuid,
                    "name": name,
                    "group_id": group_id,
                    "content": summary or name,
                    "embedding": embedding
                }]
            )
            
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"同步实体向量到 Milvus 失败: {e}")
            return False
    
    async def sync_edge_to_milvus(
        self,
        edge_uuid: str,
        name: str,
        group_id: str,
        fact: str,
        embedding: List[float]
    ) -> bool:
        """
        同步关系向量到 Milvus
        """
        if not self.milvus.is_available():
            return False
        
        try:
            self.milvus.delete_by_uuid(VectorType.EDGE, edge_uuid)
            
            result = self.milvus.insert_vectors(
                vector_type=VectorType.EDGE,
                vectors=[{
                    "uuid": edge_uuid,
                    "name": name,
                    "group_id": group_id,
                    "content": fact or name,
                    "embedding": embedding
                }]
            )
            
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"同步关系向量到 Milvus 失败: {e}")
            return False
    
    async def sync_episode_to_milvus(
        self,
        episode_uuid: str,
        name: str,
        group_id: str,
        content: str,
        embedding: List[float]
    ) -> bool:
        """
        同步文档摘要向量到 Milvus（原 Episode，已重命名为 DOCUMENT_SUMMARY）
        
        注意：此方法用于同步文档摘要，不是 Graphiti Episode
        """
        if not self.milvus.is_available():
            return False
        
        try:
            self.milvus.delete_by_uuid(VectorType.DOCUMENT_SUMMARY, episode_uuid)
            
            result = self.milvus.insert_vectors(
                vector_type=VectorType.DOCUMENT_SUMMARY,
                vectors=[{
                    "uuid": episode_uuid,
                    "name": name,
                    "group_id": group_id,
                    "content": content[:65535] if content else name,
                    "embedding": embedding
                }]
            )
            
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"同步文档摘要向量到 Milvus 失败: {e}")
            return False
    
    async def sync_community_to_milvus(
        self,
        community_uuid: str,
        name: str,
        group_id: str,
        summary: str,
        embedding: List[float]
    ) -> bool:
        """
        同步社区向量到 Milvus
        """
        if not self.milvus.is_available():
            return False
        
        try:
            self.milvus.delete_by_uuid(VectorType.COMMUNITY, community_uuid)
            
            result = self.milvus.insert_vectors(
                vector_type=VectorType.COMMUNITY,
                vectors=[{
                    "uuid": community_uuid,
                    "name": name,
                    "group_id": group_id,
                    "content": summary or name,
                    "embedding": embedding
                }]
            )
            
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"同步社区向量到 Milvus 失败: {e}")
            return False
    
    async def batch_sync_from_neo4j(
        self,
        group_id: str,
        vector_types: List[VectorType] = None
    ) -> Dict[str, int]:
        """
        从 Neo4j 批量同步向量到 Milvus
        
        用于初始迁移或数据修复
        
        Args:
            group_id: 要同步的 group_id
            vector_types: 要同步的向量类型，默认全部
            
        Returns:
            各类型同步的数量
        """
        if not self.milvus.is_available():
            return {}
        
        vector_types = vector_types or [VectorType.ENTITY, VectorType.EDGE, VectorType.DOCUMENT_SUMMARY, VectorType.COMMUNITY]
        results = {}
        
        # 同步实体
        if VectorType.ENTITY in vector_types:
            count = await self._sync_entities_from_neo4j(group_id)
            results["entities"] = count
        
        # 同步关系
        if VectorType.EDGE in vector_types:
            count = await self._sync_edges_from_neo4j(group_id)
            results["edges"] = count
        
        # 同步文档摘要（原 Episode）
        if VectorType.DOCUMENT_SUMMARY in vector_types:
            count = await self._sync_episodes_from_neo4j(group_id)
            results["document_summaries"] = count
        
        # 同步社区
        if VectorType.COMMUNITY in vector_types:
            count = await self._sync_communities_from_neo4j(group_id)
            results["communities"] = count
        
        logger.info(f"批量同步完成: group_id={group_id}, results={results}")
        return results
    
    async def _sync_entities_from_neo4j(self, group_id: str) -> int:
        """从 Neo4j 同步实体"""
        query = """
        MATCH (e:Entity)
        WHERE e.group_id = $group_id AND e.name_embedding IS NOT NULL
        RETURN e.uuid as uuid, e.name as name, e.group_id as group_id, 
               e.summary as summary, e.name_embedding as embedding
        """
        
        results = neo4j_client.execute_query(query, {"group_id": group_id})
        if not results:
            return 0
        
        vectors = []
        for r in results:
            embedding = r.get("embedding")
            if embedding and len(embedding) > 0:
                vectors.append({
                    "uuid": r.get("uuid", ""),
                    "name": r.get("name", ""),
                    "group_id": r.get("group_id", ""),
                    "content": r.get("summary", r.get("name", "")),
                    "embedding": list(embedding)
                })
        
        if vectors:
            self.milvus.delete_by_group_id(VectorType.ENTITY, group_id)
            self.milvus.insert_vectors(VectorType.ENTITY, vectors)
        
        return len(vectors)
    
    async def _sync_edges_from_neo4j(self, group_id: str) -> int:
        """从 Neo4j 同步关系"""
        query = """
        MATCH ()-[r:RELATES_TO]->()
        WHERE r.group_id = $group_id AND r.fact_embedding IS NOT NULL
        RETURN r.uuid as uuid, r.name as name, r.group_id as group_id,
               r.fact as fact, r.fact_embedding as embedding
        """
        
        results = neo4j_client.execute_query(query, {"group_id": group_id})
        if not results:
            return 0
        
        vectors = []
        for r in results:
            embedding = r.get("embedding")
            if embedding and len(embedding) > 0:
                vectors.append({
                    "uuid": r.get("uuid", ""),
                    "name": r.get("name", ""),
                    "group_id": r.get("group_id", ""),
                    "content": r.get("fact", r.get("name", "")),
                    "embedding": list(embedding)
                })
        
        if vectors:
            self.milvus.delete_by_group_id(VectorType.EDGE, group_id)
            self.milvus.insert_vectors(VectorType.EDGE, vectors)
        
        return len(vectors)
    
    async def _sync_episodes_from_neo4j(self, group_id: str) -> int:
        """
        从 Neo4j 同步文档摘要向量（原 Episode，已重命名为 DOCUMENT_SUMMARY）
        
        注意：此方法从 Neo4j 的 Episodic 节点读取数据，但存储到 Milvus 的 DOCUMENT_SUMMARY collection
        用于文档摘要的向量化存储，不是 Graphiti Episode 的向量化
        """
        query = """
        MATCH (e:Episodic)
        WHERE e.group_id = $group_id
        RETURN e.uuid as uuid, e.name as name, e.group_id as group_id,
               e.content as content, e.embedding as embedding
        """
        
        results = neo4j_client.execute_query(query, {"group_id": group_id})
        if not results:
            return 0
        
        # 获取embedder用于生成embedding
        from app.core.graphiti_client import get_graphiti_instance
        graphiti = get_graphiti_instance("local")  # 使用默认provider
        embedder = graphiti.embedder
        
        vectors = []
        for r in results:
            uuid = r.get("uuid", "")
            name = r.get("name", "")
            content = r.get("content", name)
            embedding = r.get("embedding")
            
            # 如果Neo4j中没有embedding，则生成新的
            if not embedding or len(embedding) == 0:
                try:
                    # 使用content生成embedding（优先使用完整content，如果太长则截断）
                    # 注意：embedder.embed 可能需要使用 embedder.create 或 embedder.embed_batch
                    content_for_embedding = content if content else name
                    # 检查embedder的方法名
                    if hasattr(embedder, 'create'):
                        # OpenAIEmbedder 使用 create 方法
                        embedding = await embedder.create(content_for_embedding)
                    elif hasattr(embedder, 'embed'):
                        # 其他embedder可能使用embed方法
                        embedding = await embedder.embed(content_for_embedding)
                    else:
                        # 尝试直接调用
                        embedding = await embedder(content_for_embedding)
                    logger.debug(f"为Episode {uuid} 生成新embedding，内容长度: {len(content_for_embedding)}")
                except Exception as e:
                    logger.warning(f"为Episode {uuid} 生成embedding失败: {e}")
                    continue
            
            if embedding and len(embedding) > 0:
                vectors.append({
                    "uuid": uuid,
                    "name": name,
                    "group_id": r.get("group_id", ""),
                    "content": content[:65535] if content else name,  # Milvus VARCHAR限制
                    "embedding": list(embedding) if not isinstance(embedding, list) else embedding
                })
        
        if vectors:
            self.milvus.delete_by_group_id(VectorType.DOCUMENT_SUMMARY, group_id)
            self.milvus.insert_vectors(VectorType.DOCUMENT_SUMMARY, vectors)
            logger.info(f"成功同步 {len(vectors)} 个文档摘要向量到Milvus")
        
        return len(vectors)
    
    async def _sync_communities_from_neo4j(self, group_id: str) -> int:
        """
        从 Neo4j 同步社区
        
        如果Community节点有name_embedding则直接使用，
        如果没有则使用name或summary生成embedding
        """
        query = """
        MATCH (c:Community)
        WHERE c.group_id = $group_id
        RETURN c.uuid as uuid, c.name as name, c.group_id as group_id,
               c.summary as summary, c.name_embedding as embedding
        """
        
        results = neo4j_client.execute_query(query, {"group_id": group_id})
        if not results:
            return 0
        
        # 获取embedder用于生成embedding
        from app.core.graphiti_client import get_graphiti_instance
        graphiti = get_graphiti_instance("local")  # 使用默认provider
        embedder = graphiti.embedder
        
        vectors = []
        for r in results:
            uuid = r.get("uuid", "")
            name = r.get("name", "")
            summary = r.get("summary", name)
            embedding = r.get("embedding")
            
            # 如果Neo4j中没有embedding，则生成新的
            if not embedding or len(embedding) == 0:
                try:
                    # 使用name或summary生成embedding
                    text_for_embedding = name if name else summary
                    embedding = await embedder.embed(text_for_embedding)
                    logger.debug(f"为Community {uuid} 生成新embedding")
                except Exception as e:
                    logger.warning(f"为Community {uuid} 生成embedding失败: {e}")
                    continue
            
            if embedding and len(embedding) > 0:
                vectors.append({
                    "uuid": uuid,
                    "name": name,
                    "group_id": r.get("group_id", ""),
                    "content": summary or name,
                    "embedding": list(embedding) if not isinstance(embedding, list) else embedding
                })
        
        if vectors:
            self.milvus.delete_by_group_id(VectorType.COMMUNITY, group_id)
            self.milvus.insert_vectors(VectorType.COMMUNITY, vectors)
            logger.info(f"成功同步 {len(vectors)} 个Community到Milvus")
        
        return len(vectors)
    
    async def delete_group_vectors(self, group_id: str) -> bool:
        """
        删除指定 group_id 的所有向量
        
        在删除文档时调用，保持数据一致性
        """
        if not self.milvus.is_available():
            return True  # Milvus 不可用时不影响主流程
        
        try:
            for vector_type in VectorType:
                self.milvus.delete_by_group_id(vector_type, group_id)
            
            logger.info(f"成功删除 group_id={group_id} 的所有向量")
            return True
            
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False

