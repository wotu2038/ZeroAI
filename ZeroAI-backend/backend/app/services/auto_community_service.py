"""
Community 自动构建服务

在文档处理完成后自动触发 Community 构建
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.core.config import settings
from app.core.graphiti_client import get_graphiti_instance
from app.core.neo4j_client import neo4j_client
from app.services.milvus_service import VectorType, get_milvus_service
from app.services.vector_dual_write_service import VectorDualWriteService

logger = logging.getLogger(__name__)


class AutoCommunityService:
    """
    Community 自动构建服务
    
    在文档处理完成后自动执行 Community 构建，
    无需用户手动触发
    """
    
    def __init__(self, provider: str = "local"):
        self.provider = provider
        self.enabled = getattr(settings, 'ENABLE_AUTO_COMMUNITY', True)
        self.min_entities = getattr(settings, 'COMMUNITY_MIN_ENTITIES', 5)
    
    async def build_community_for_document(
        self,
        group_id: str,
        document_name: str = None,
        sync_to_milvus: bool = True
    ) -> Dict[str, Any]:
        """
        为单个文档构建 Community
        
        Args:
            group_id: 文档的 group_id
            document_name: 文档名称（用于日志）
            sync_to_milvus: 是否同步到 Milvus
            
        Returns:
            构建结果
        """
        if not self.enabled:
            logger.info("Community 自动构建未启用")
            return {"success": False, "reason": "disabled"}
        
        logger.info(f"开始为文档构建 Community: group_id={group_id}")
        
        try:
            # 1. 检查实体数量是否足够
            entity_count = await self._count_entities(group_id)
            if entity_count < self.min_entities:
                logger.info(
                    f"实体数量不足 ({entity_count} < {self.min_entities})，跳过 Community 构建"
                )
                return {
                    "success": True,
                    "skipped": True,
                    "reason": f"entity_count ({entity_count}) < min_entities ({self.min_entities})"
                }
            
            # 2. 获取 Graphiti 实例
            graphiti = get_graphiti_instance(self.provider)
            
            # 3. 执行 Community 构建（带超时控制）
            logger.info(f"调用 Graphiti build_communities: group_ids=[{group_id}]")
            
            # 从配置读取超时时间（默认180秒）
            timeout_seconds = getattr(settings, 'COMMUNITY_BUILD_TIMEOUT', 180.0)
            
            timeout_occurred = False
            try:
                communities_result = await asyncio.wait_for(
                    graphiti.build_communities(group_ids=[group_id]),
                    timeout=timeout_seconds
                )
                community_count = len(communities_result) if communities_result else 0
                logger.info(f"Community 构建完成: 创建了 {community_count} 个社区")
            except asyncio.TimeoutError:
                logger.warning(f"Community 构建超时（{timeout_seconds}秒），返回超时结果")
                communities_result = []
                community_count = 0
                timeout_occurred = True
                # 不抛出异常，返回超时结果，但标记为失败
            
            # 4. 同步到 Milvus（如果启用且未超时）
            if sync_to_milvus and community_count > 0 and not timeout_occurred:
                await self._sync_communities_to_milvus(group_id)
            
            # 如果超时，返回失败结果
            if timeout_occurred:
                return {
                    "success": False,
                    "reason": "timeout",
                    "community_count": 0,
                    "entity_count": entity_count,
                    "group_id": group_id
                }
            
            return {
                "success": True,
                "community_count": community_count,
                "entity_count": entity_count,
                "group_id": group_id
            }
            
        except asyncio.TimeoutError:
            # 如果外层还有超时（双重保护）
            logger.warning(f"Community 构建超时（外层超时）")
            return {
                "success": False,
                "reason": "timeout",
                "group_id": group_id
            }
        except Exception as e:
            logger.error(f"Community 构建失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "group_id": group_id
            }
    
    async def build_cross_document_communities(
        self,
        group_ids: List[str],
        knowledge_base_id: int = None,
        sync_to_milvus: bool = True
    ) -> Dict[str, Any]:
        """
        跨文档构建 Community
        
        将多个文档的实体和关系联合构建社区，
        发现跨文档的知识关联
        
        Args:
            group_ids: 要联合的 group_id 列表
            knowledge_base_id: 知识库 ID
            sync_to_milvus: 是否同步到 Milvus
            
        Returns:
            构建结果
        """
        if not self.enabled:
            return {"success": False, "reason": "disabled"}
        
        if not group_ids:
            return {"success": False, "reason": "no group_ids provided"}
        
        logger.info(f"开始跨文档 Community 构建: {len(group_ids)} 个文档")
        
        try:
            # 1. 统计总实体数
            total_entities = 0
            for gid in group_ids:
                count = await self._count_entities(gid)
                total_entities += count
            
            if total_entities < self.min_entities:
                logger.info(f"总实体数量不足 ({total_entities})，跳过")
                return {"success": True, "skipped": True, "reason": "insufficient entities"}
            
            # 2. 执行跨文档 Community 构建
            graphiti = get_graphiti_instance(self.provider)
            communities_result = await graphiti.build_communities(group_ids=group_ids)
            
            community_count = len(communities_result) if communities_result else 0
            logger.info(f"跨文档 Community 构建完成: {community_count} 个社区")
            
            # 3. 同步到 Milvus
            if sync_to_milvus and community_count > 0:
                for gid in group_ids:
                    await self._sync_communities_to_milvus(gid)
            
            return {
                "success": True,
                "community_count": community_count,
                "document_count": len(group_ids),
                "total_entities": total_entities,
                "knowledge_base_id": knowledge_base_id
            }
            
        except Exception as e:
            logger.error(f"跨文档 Community 构建失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def rebuild_all_communities(
        self,
        knowledge_base_id: int = None
    ) -> Dict[str, Any]:
        """
        重建所有 Community
        
        适用于：
        - 算法更新后需要重新构建
        - 数据修复后需要重建
        
        Args:
            knowledge_base_id: 指定知识库，None 表示全部
            
        Returns:
            重建结果
        """
        logger.info(f"开始重建所有 Community: knowledge_base_id={knowledge_base_id}")
        
        try:
            # 1. 获取所有 group_id
            query = """
            MATCH (e:Episodic)
            WHERE e.group_id IS NOT NULL
            RETURN DISTINCT e.group_id as group_id
            """
            
            results = neo4j_client.execute_query(query, {})
            group_ids = [r.get("group_id") for r in results if r.get("group_id")]
            
            if not group_ids:
                return {"success": True, "message": "no documents to rebuild"}
            
            logger.info(f"找到 {len(group_ids)} 个文档需要重建 Community")
            
            # 2. 删除现有 Community
            await self._delete_all_communities(group_ids)
            
            # 3. 重新构建
            result = await self.build_cross_document_communities(
                group_ids=group_ids,
                knowledge_base_id=knowledge_base_id,
                sync_to_milvus=True
            )
            
            return {
                "success": True,
                "rebuilt_documents": len(group_ids),
                "community_result": result
            }
            
        except Exception as e:
            logger.error(f"重建 Community 失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _count_entities(self, group_id: str) -> int:
        """统计 group_id 下的实体数量"""
        query = """
        MATCH (e:Entity)
        WHERE e.group_id = $group_id
        RETURN count(e) as count
        """
        
        result = neo4j_client.execute_query(query, {"group_id": group_id})
        if result and len(result) > 0:
            return result[0].get("count", 0)
        return 0
    
    async def _sync_communities_to_milvus(self, group_id: str) -> int:
        """同步 Community 到 Milvus"""
        try:
            dual_write = VectorDualWriteService()
            results = await dual_write.batch_sync_from_neo4j(
                group_id=group_id,
                vector_types=[VectorType.COMMUNITY]
            )
            return results.get("communities", 0)
        except Exception as e:
            logger.warning(f"同步 Community 到 Milvus 失败: {e}")
            return 0
    
    async def _delete_all_communities(self, group_ids: List[str]):
        """删除指定 group_ids 的所有 Community"""
        for gid in group_ids:
            query = """
            MATCH (c:Community)
            WHERE c.group_id = $group_id
            DETACH DELETE c
            """
            neo4j_client.execute_write(query, {"group_id": gid})
        
        logger.info(f"已删除 {len(group_ids)} 个文档的 Community")


# 便捷函数
async def auto_build_community(
    group_id: str,
    provider: str = "local"
) -> Dict[str, Any]:
    """
    便捷函数：自动构建单个文档的 Community
    
    在文档处理完成后调用此函数
    """
    service = AutoCommunityService(provider=provider)
    return await service.build_community_for_document(group_id)

