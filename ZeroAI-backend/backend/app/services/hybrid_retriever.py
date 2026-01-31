"""
混合检索服务

融合 Milvus 向量检索 + Neo4j BM25 + 图遍历，实现高质量召回
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from app.services.milvus_service import (
    MilvusService, 
    VectorType, 
    VectorSearchResult,
    get_milvus_service
)
from app.core.neo4j_client import neo4j_client
from app.core.config import settings
from app.services.cognee_service import CogneeService

logger = logging.getLogger(__name__)


class RetrievalScheme(Enum):
    """检索方案"""
    DEFAULT = "default"          # 方案A: 默认（完整RAG）
    ENHANCED = "enhanced"        # 方案B: 增强（原文截断）
    SMART = "smart"              # 方案C: 智能（分段概括）
    FAST = "fast"                # 方案D: 快速（无重排序）


@dataclass
class RetrievalResult:
    """检索结果"""
    uuid: str
    name: str
    content: str
    score: float
    source_type: str  # entity, edge, episode, community
    group_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class HybridRetrievalConfig:
    """混合检索配置"""
    # 各通道权重
    milvus_weight: float = 0.3
    bm25_weight: float = 0.25
    graph_weight: float = 0.25
    cognee_weight: float = 0.2  # Cognee 章节知识图谱检索权重
    
    # 各通道返回数量
    milvus_top_k: int = 20
    bm25_top_k: int = 20
    graph_hop: int = 2
    cognee_top_k: int = 20  # Cognee 检索返回数量
    
    # 最终返回数量
    final_top_k: int = 10
    
    # 过滤阈值
    min_score: float = 0.5
    
    # 是否启用重排序
    enable_rerank: bool = True
    
    # 是否启用 Cognee 检索
    enable_cognee: bool = True
    
    # 检索方案
    scheme: RetrievalScheme = RetrievalScheme.DEFAULT


class HybridRetriever:
    """
    混合检索器
    
    融合四个检索通道：
    1. Milvus 向量检索（语义相似度）
    2. Neo4j BM25 全文检索（关键词匹配）
    3. Neo4j 图遍历（关系扩展）
    4. Cognee 章节知识图谱检索（章节级知识图谱）
    """
    
    def __init__(
        self, 
        milvus_service: MilvusService = None,
        embedder = None,
        reranker = None,
        cognee_service: CogneeService = None
    ):
        self.milvus = milvus_service or get_milvus_service()
        self.embedder = embedder
        self.reranker = reranker
        self.cognee_service = cognee_service or CogneeService()
        
    async def retrieve(
        self,
        query: str,
        group_ids: Optional[List[str]] = None,
        config: HybridRetrievalConfig = None
    ) -> List[RetrievalResult]:
        """
        执行混合检索
        
        Args:
            query: 查询文本
            group_ids: 要检索的 group_id 列表
            config: 检索配置
            
        Returns:
            检索结果列表（已排序）
        """
        config = config or HybridRetrievalConfig()
        
        logger.info(f"开始混合检索: query='{query[:50]}...', scheme={config.scheme.value}")
        
        # 1. 生成查询向量
        query_embedding = await self._get_query_embedding(query)
        
        # 2. 并行执行四个检索通道
        milvus_results = await self._milvus_search(
            query_embedding=query_embedding,
            group_ids=group_ids,
            top_k=config.milvus_top_k,
            min_score=config.min_score
        ) if self.milvus.is_available() else []
        
        bm25_results = await self._bm25_search(
            query=query,
            group_ids=group_ids,
            top_k=config.bm25_top_k
        )
        
        graph_results = await self._graph_traverse(
            seed_uuids=[r.uuid for r in milvus_results[:5] + bm25_results[:5]],
            group_ids=group_ids,
            max_hop=config.graph_hop
        )
        
        # Cognee 章节知识图谱检索
        cognee_results = []
        if config.enable_cognee:
            try:
                cognee_results = await self._cognee_search(
                    query=query,
                    group_ids=group_ids,
                    top_k=config.cognee_top_k
                )
            except Exception as e:
                logger.warning(f"Cognee 检索失败: {e}")
                cognee_results = []
        
        logger.info(
            f"检索通道结果: Milvus={len(milvus_results)}, "
            f"BM25={len(bm25_results)}, Graph={len(graph_results)}, "
            f"Cognee={len(cognee_results)}"
        )
        
        # 3. 合并结果（RRF 融合）
        merged_results = self._rrf_merge(
            milvus_results=milvus_results,
            bm25_results=bm25_results,
            graph_results=graph_results,
            cognee_results=cognee_results,
            weights={
                "milvus": config.milvus_weight,
                "bm25": config.bm25_weight,
                "graph": config.graph_weight,
                "cognee": config.cognee_weight
            }
        )
        
        # 4. 重排序（如果启用）
        if config.enable_rerank and config.scheme != RetrievalScheme.FAST:
            merged_results = await self._rerank(
                query=query,
                results=merged_results,
                top_k=config.final_top_k
            )
        else:
            # 快速模式：直接截取
            merged_results = merged_results[:config.final_top_k]
        
        # 5. 归一化分数到 0-100 范围（前端期望百分比格式）
        if merged_results:
            scores = [r.score for r in merged_results if r.score > 0]
            if scores:
                max_score = max(scores)
                if max_score > 0:
                    for result in merged_results:
                        # 将分数归一化到 0-100 范围
                        result.score = (result.score / max_score) * 100
                    logger.info(f"分数归一化完成: max_score={max_score}, 归一化后范围: 0-100")
                else:
                    logger.warning("所有分数都为0，跳过归一化")
        
        logger.info(f"最终返回 {len(merged_results)} 个结果")
        return merged_results
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """获取查询向量"""
        if self.embedder:
            # OpenAIEmbedder 使用 create 方法
            try:
                return await self.embedder.create(query)
            except AttributeError:
                # 如果 create 不存在，尝试 embed
                try:
                    return await self.embedder.embed(query)
                except AttributeError:
                    logger.error(f"Embedder 没有 embed 或 create 方法")
                    return []
        
        # 如果没有 embedder，尝试使用 Graphiti 的 embedder
        try:
            from app.core.graphiti_client import get_graphiti_instance
            graphiti = get_graphiti_instance("local")
            if graphiti.embedder:
                return await graphiti.embedder.create(query)
            else:
                logger.warning("Graphiti embedder 不可用")
                return []
        except Exception as e:
            logger.error(f"获取查询向量失败: {e}")
            return []
    
    async def _milvus_search(
        self,
        query_embedding: List[float],
        group_ids: Optional[List[str]],
        top_k: int,
        min_score: float
    ) -> List[RetrievalResult]:
        """Milvus 向量检索"""
        if not query_embedding:
            return []
        
        results = []
        
        # 搜索所有向量类型
        for vector_type in [VectorType.ENTITY, VectorType.EDGE, VectorType.EPISODE, VectorType.DOCUMENT_SUMMARY, VectorType.COMMUNITY, VectorType.SECTION, VectorType.IMAGE, VectorType.TABLE, VectorType.COGNEE_ENTITY, VectorType.COGNEE_EDGE]:
            search_results = self.milvus.search_vectors(
                vector_type=vector_type,
                query_embedding=query_embedding,
                top_k=top_k,
                group_ids=group_ids,
                min_score=min_score
            )
            
            for sr in search_results:
                results.append(RetrievalResult(
                    uuid=sr.uuid,
                    name=sr.name,
                    content=sr.content or sr.name,
                    score=sr.score,
                    source_type=sr.vector_type.value,
                    group_id=sr.group_id,
                    metadata={"source": "milvus"}
                ))
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    async def _bm25_search(
        self,
        query: str,
        group_ids: Optional[List[str]],
        top_k: int
    ) -> List[RetrievalResult]:
        """Neo4j BM25 全文检索"""
        results = []
        
        # 构建 group_id 过滤条件
        group_filter = ""
        params = {"query": query, "limit": top_k}
        if group_ids:
            group_filter = "AND e.group_id IN $group_ids"
            params["group_ids"] = group_ids
        
        # 搜索 Episode
        episode_query = f"""
        CALL db.index.fulltext.queryNodes('episode_content', $query)
        YIELD node, score
        WHERE node:Episodic {group_filter.replace('e.', 'node.')}
        RETURN node.uuid as uuid, node.name as name, node.content as content,
               score, 'episode' as source_type, node.group_id as group_id
        LIMIT $limit
        """
        
        try:
            episode_results = neo4j_client.execute_query(episode_query, params)
            for r in episode_results or []:
                results.append(RetrievalResult(
                    uuid=r.get("uuid", ""),
                    name=r.get("name", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0),
                    source_type="episode",
                    group_id=r.get("group_id"),
                    metadata={"source": "bm25"}
                ))
        except Exception as e:
            logger.warning(f"Episode BM25 搜索失败: {e}")
        
        # 搜索 Entity
        entity_query = f"""
        CALL db.index.fulltext.queryNodes('node_name_and_summary', $query)
        YIELD node, score
        WHERE node:Entity {group_filter.replace('e.', 'node.')}
        RETURN node.uuid as uuid, node.name as name, node.summary as content,
               score, 'entity' as source_type, node.group_id as group_id
        LIMIT $limit
        """
        
        try:
            entity_results = neo4j_client.execute_query(entity_query, params)
            for r in entity_results or []:
                results.append(RetrievalResult(
                    uuid=r.get("uuid", ""),
                    name=r.get("name", ""),
                    content=r.get("content", r.get("name", "")),
                    score=r.get("score", 0),
                    source_type="entity",
                    group_id=r.get("group_id"),
                    metadata={"source": "bm25"}
                ))
        except Exception as e:
            logger.warning(f"Entity BM25 搜索失败: {e}")
        
        # 搜索 Edge
        edge_query = f"""
        CALL db.index.fulltext.queryRelationships('edge_name_and_fact', $query)
        YIELD relationship, score
        WHERE relationship.group_id IN $group_ids OR $group_ids IS NULL
        RETURN relationship.uuid as uuid, relationship.name as name, 
               relationship.fact as content, score, 'edge' as source_type,
               relationship.group_id as group_id
        LIMIT $limit
        """
        
        try:
            if group_ids:
                params["group_ids"] = group_ids
            else:
                params["group_ids"] = None
            edge_results = neo4j_client.execute_query(edge_query, params)
            for r in edge_results or []:
                results.append(RetrievalResult(
                    uuid=r.get("uuid", ""),
                    name=r.get("name", ""),
                    content=r.get("content", r.get("name", "")),
                    score=r.get("score", 0),
                    source_type="edge",
                    group_id=r.get("group_id"),
                    metadata={"source": "bm25"}
                ))
        except Exception as e:
            logger.warning(f"Edge BM25 搜索失败: {e}")
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    async def _graph_traverse(
        self,
        seed_uuids: List[str],
        group_ids: Optional[List[str]],
        max_hop: int
    ) -> List[RetrievalResult]:
        """
        Neo4j 图遍历扩展
        
        按照优化方案：使用简单的1-hop查询，查找Entity的邻居节点
        """
        if not seed_uuids:
            return []
        
        results = []
        
        # 按照优化方案的简单1-hop查询（第590-596行）
        # 查询这些Entity的1-hop邻居
        expand_query = """
        MATCH (e:Entity)-[r:RELATES_TO]-(neighbor:Entity)
        WHERE e.uuid IN $uuids AND ($group_ids IS NULL OR neighbor.group_id IN $group_ids)
        RETURN DISTINCT neighbor.uuid as uuid, neighbor.name as name,
               neighbor.summary as content, 0.5 as score, 'entity' as source_type,
               neighbor.group_id as group_id
        LIMIT 50
        """
        
        params = {
            "uuids": seed_uuids[:10],  # 限制种子数量
            "group_ids": group_ids
        }
        
        try:
            traverse_results = neo4j_client.execute_query(expand_query, params)
            for r in traverse_results or []:
                results.append(RetrievalResult(
                    uuid=r.get("uuid", ""),
                    name=r.get("name", ""),
                    content=r.get("content", r.get("name", "")),
                    score=r.get("score", 0.5),  # 扩展结果降权
                    source_type="entity",
                    group_id=r.get("group_id"),
                    metadata={"source": "graph"}
                ))
        except Exception as e:
            logger.warning(f"图遍历失败: {e}")
        
        return results
    
    async def _cognee_search(
        self,
        query: str,
        group_ids: Optional[List[str]],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Cognee 章节知识图谱检索（按需创建）
        
        两阶段检索策略的核心：
        - 第一次查询慢（需要构建知识图谱）
        - 之后查询快（复用已有知识图谱）
        
        从 Cognee 构建的章节级知识图谱中检索相关内容
        """
        results = []
        
        try:
            # 如果指定了 group_ids，为每个 group_id 确保知识图谱存在
            if group_ids:
                for group_id in group_ids:
                    # ========== 按需创建：确保知识图谱存在 ==========
                    ensure_result = await self.cognee_service.ensure_cognee_kg(
                        group_id=group_id,
                        provider="local"  # 使用默认 provider
                    )
                    
                    if ensure_result.get("created"):
                        logger.info(
                            f"✅ Cognee 知识图谱已按需创建: group_id={group_id}, "
                            f"构建耗时={ensure_result.get('build_time', 0):.2f}秒"
                        )
                    elif ensure_result.get("exists"):
                        logger.debug(
                            f"✅ Cognee 知识图谱已存在: group_id={group_id}, "
                            f"检查耗时={ensure_result.get('check_time', 0):.2f}秒"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Cognee 知识图谱创建失败: group_id={group_id}, "
                            f"错误={ensure_result.get('error', 'unknown')}"
                        )
                        # 即使创建失败，也尝试搜索（可能部分数据已存在）
                    
                    # 执行搜索
                    cognee_results = await self.cognee_service.search_sections(
                        query=query,
                        group_id=group_id,
                        top_k=top_k
                    )
                    
                    for r in cognee_results:
                        # 转换 Cognee 结果格式为 RetrievalResult
                        results.append(RetrievalResult(
                            uuid=r.get("metadata", {}).get("section_uuid", f"cognee_{group_id}_{len(results)}"),
                            name=r.get("metadata", {}).get("title", "章节内容"),
                            content=r.get("content", ""),
                            score=r.get("score", 0.0),
                            source_type="section",  # 标记为章节类型
                            group_id=group_id,
                            metadata={
                                "source": "cognee",
                                "section_uuid": r.get("metadata", {}).get("section_uuid"),
                                "title": r.get("metadata", {}).get("title"),
                                "kg_created": ensure_result.get("created", False),
                                "kg_exists": ensure_result.get("exists", False)
                            }
                        ))
            else:
                # 如果没有指定 group_ids，搜索所有 dataset（不进行按需创建）
                cognee_results = await self.cognee_service.search_sections(
                    query=query,
                    group_id=None,
                    top_k=top_k
                )
                
                for r in cognee_results:
                    # 从 metadata 中提取 group_id
                    metadata = r.get("metadata", {})
                    group_id = metadata.get("group_id")
                    
                    results.append(RetrievalResult(
                        uuid=metadata.get("section_uuid", f"cognee_{len(results)}"),
                        name=metadata.get("title", "章节内容"),
                        content=r.get("content", ""),
                        score=r.get("score", 0.0),
                        source_type="section",
                        group_id=group_id,
                        metadata={
                            "source": "cognee",
                            "section_uuid": metadata.get("section_uuid"),
                            "title": metadata.get("title")
                        }
                    ))
            
            # 按分数排序
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Cognee 检索失败: {e}", exc_info=True)
            return []
    
    def _rrf_merge(
        self,
        milvus_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
        graph_results: List[RetrievalResult],
        cognee_results: List[RetrievalResult] = None,
        weights: Dict[str, float] = None,
        k: int = 60
    ) -> List[RetrievalResult]:
        """
        RRF (Reciprocal Rank Fusion) 合并
        
        RRF_score = sum(weight * 1 / (k + rank))
        """
        if weights is None:
            weights = {}
        if cognee_results is None:
            cognee_results = []
        
        # 按 UUID 合并分数
        uuid_scores: Dict[str, Tuple[float, RetrievalResult]] = {}
        
        def add_results(results: List[RetrievalResult], source: str, weight: float):
            for rank, result in enumerate(results):
                rrf_score = weight * (1 / (k + rank + 1))
                
                if result.uuid in uuid_scores:
                    current_score, current_result = uuid_scores[result.uuid]
                    uuid_scores[result.uuid] = (current_score + rrf_score, current_result)
                else:
                    uuid_scores[result.uuid] = (rrf_score, result)
        
        add_results(milvus_results, "milvus", weights.get("milvus", 0.3))
        add_results(bm25_results, "bm25", weights.get("bm25", 0.25))
        add_results(graph_results, "graph", weights.get("graph", 0.25))
        add_results(cognee_results, "cognee", weights.get("cognee", 0.2))
        
        # 排序
        sorted_results = sorted(
            uuid_scores.values(),
            key=lambda x: x[0],
            reverse=True
        )
        
        # 更新分数并返回
        merged = []
        for score, result in sorted_results:
            result.score = score
            merged.append(result)
        
        return merged
    
    async def _rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        使用 Cross-encoder 重排序
        
        注意：rank()方法返回 [(passage, score), ...]，已按分数排序
        """
        if not results:
            return []
        
        if self.reranker:
            try:
                # 准备重排序输入
                passages = [r.content for r in results]
                
                # 调用 reranker.rank()（不是rerank）
                # rank()返回 [(passage, score), ...]，已按分数排序
                ranked_results = await self.reranker.rank(
                    query=query,
                    passages=passages
                )
                
                # 创建passage到分数的映射
                passage_to_score = {passage: score for passage, score in ranked_results}
                
                # 更新分数并保持原始顺序（用于后续重新排序）
                for result in results:
                    if result.content in passage_to_score:
                        result.score = passage_to_score[result.content]
                
                # 按照rank()返回的顺序重新排序（rank()已经按分数排序）
                # 创建passage到原始结果的映射
                passage_to_result = {r.content: r for r in results}
                
                # 按照rank()返回的顺序构建新的结果列表
                reranked = []
                for passage, score in ranked_results:
                    if passage in passage_to_result:
                        result = passage_to_result[passage]
                        result.score = score
                        reranked.append(result)
                
                # 添加未在ranked_results中的结果（如果有）
                ranked_passages = {passage for passage, _ in ranked_results}
                for result in results:
                    if result.content not in ranked_passages:
                        reranked.append(result)
                
                results = reranked
                
            except Exception as e:
                logger.warning(f"重排序失败，使用原始排序: {e}")
        
        return results[:top_k]


# 便捷函数
async def hybrid_retrieve(
    query: str,
    group_ids: Optional[List[str]] = None,
    scheme: str = "default",
    top_k: int = 10
) -> List[RetrievalResult]:
    """
    便捷的混合检索函数
    
    Args:
        query: 查询文本
        group_ids: 要检索的 group_id 列表
        scheme: 检索方案 (default, enhanced, smart, fast)
        top_k: 返回数量
        
    Returns:
        检索结果列表
    """
    retriever = HybridRetriever()
    
    config = HybridRetrievalConfig(
        scheme=RetrievalScheme(scheme),
        final_top_k=top_k,
        enable_rerank=(scheme != "fast")
    )
    
    return await retriever.retrieve(
        query=query,
        group_ids=group_ids,
        config=config
    )

