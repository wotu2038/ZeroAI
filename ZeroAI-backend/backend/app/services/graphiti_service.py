from typing import List, Dict, Any, Optional
from datetime import datetime
import inspect
from app.core.graphiti_client import get_graphiti_instance
from app.core.utils import serialize_neo4j_value
from app.core.neo4j_client import neo4j_client
from graphiti_core.search.search_config import (
    SearchConfig, EdgeSearchConfig, NodeSearchConfig,
    EpisodeSearchConfig, CommunitySearchConfig,
    EdgeSearchMethod, NodeSearchMethod, EpisodeSearchMethod, CommunitySearchMethod,
    EdgeReranker, NodeReranker, EpisodeReranker, CommunityReranker
)
from graphiti_core.search.search_filters import SearchFilters
import asyncio
import logging

logger = logging.getLogger(__name__)


class GraphitiService:
    """Graphiti服务层，提供知识图谱自动提取和检索功能"""
    
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算文本的 token 数（中文通常 1 token ≈ 2 字符，英文 1 token ≈ 4 字符）"""
        # 简单估算：中文字符按 2 字符/token，英文按 4 字符/token
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        return (chinese_chars // 2) + (other_chars // 4)
    
    @staticmethod
    def _get_max_context_tokens(provider: str) -> int:
        """获取不同 provider 的最大上下文 tokens"""
        # 本地大模型的最大上下文长度是 35,488 tokens
        # 但需要预留空间给 prompt 和 completion，所以实际可用更少
        if provider == "local":
            # 本地大模型：35,488 tokens，预留 10,000 tokens 给 prompt 和 completion
            return 25000  # 保守估计，留出足够空间
        else:
            # 千问等其他模型通常有更大的上下文窗口
            return 80000  # 默认值，可以根据实际情况调整
    
    @staticmethod
    async def add_episode(
        content: str,
        provider: str = "qianwen",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        添加文本片段（Episode），自动提取实体和关系
        
        Args:
            content: 文本内容
            provider: LLM提供商（qianwen或local）
            metadata: 元数据
            
        Returns:
            包含episode信息和提取结果的字典
        """
        try:
            # 检查文本长度
            estimated_tokens = GraphitiService._estimate_tokens(content)
            max_tokens = GraphitiService._get_max_context_tokens(provider)
            
            if estimated_tokens > max_tokens:
                error_msg = (
                    f"文本内容过长，无法处理。\n"
                    f"- 估算 tokens: {estimated_tokens:,}\n"
                    f"- 最大支持 tokens: {max_tokens:,}\n"
                    f"- 超出限制: {estimated_tokens - max_tokens:,} tokens\n"
                    f"- 文本长度: {len(content):,} 字符\n\n"
                    f"建议：\n"
                    f"1. 将文本分割成多个较小的部分，分别提交\n"
                    f"2. 缩短文本内容，只保留关键信息\n"
                    f"3. 对于长文档，建议使用文档上传功能，系统会自动分块处理"
                )
                logger.warning(f"文本长度超限: provider={provider}, tokens={estimated_tokens}, max={max_tokens}")
                raise ValueError(error_msg)
            
            logger.info(f"添加 Episode: provider={provider}, 文本长度={len(content)} 字符, 估算 tokens={estimated_tokens}")
            
            graphiti = get_graphiti_instance(provider)
            
            # 添加episode，Graphiti会自动提取实体和关系
            # Graphiti的add_episode需要: name, episode_body, source_description, reference_time
            episode_name = metadata.get("name", f"episode_{datetime.now().timestamp()}") if metadata else f"episode_{datetime.now().timestamp()}"
            source_description = metadata.get("source_description", "user_input") if metadata else "user_input"
            reference_time = metadata.get("reference_time", datetime.now()) if metadata and "reference_time" in metadata else datetime.now()
            
            # add_episode是异步方法，需要使用await
            episode = await graphiti.add_episode(
                name=episode_name,
                episode_body=content,
                source_description=source_description,
                reference_time=reference_time
            )
            
            # Graphiti会自动将实体和关系存储到Neo4j
            # 获取episode的UUID
            episode_id = str(episode.uuid) if hasattr(episode, 'uuid') else None
            
            # Graphiti的add_episode会返回Episode对象，但节点和边已经存储到Neo4j
            # 我们需要通过查询Neo4j来获取创建的节点和边
            # 查询最近创建的节点（与这个episode相关的）
            from app.core.neo4j_client import neo4j_client
            
            # 查询与episode相关的节点
            query_nodes = """
            MATCH (n)
            WHERE n.episode_uuid = $episode_uuid OR n.created_at IS NOT NULL
            RETURN id(n) as id, labels(n) as labels, properties(n) as properties
            ORDER BY n.created_at DESC
            LIMIT 20
            """
            
            # 查询与episode相关的边
            query_edges = """
            MATCH (a)-[r]->(b)
            WHERE r.episode_uuid = $episode_uuid OR r.created_at IS NOT NULL
            RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
            ORDER BY r.created_at DESC
            LIMIT 20
            """
            
            try:
                node_results = neo4j_client.execute_query(query_nodes, {"episode_uuid": episode_id})
                edge_results = neo4j_client.execute_query(query_edges, {"episode_uuid": episode_id})
                
                nodes = []
                for node_data in node_results:
                    labels = node_data.get("labels", [])
                    props = node_data.get("properties", {})
                    # 序列化属性值
                    serialized_props = {k: serialize_neo4j_value(v) for k, v in props.items() if k not in ["episode_uuid", "created_at"]}
                    nodes.append({
                        "id": str(node_data.get("id", "")),
                        "name": props.get("name", ""),
                        "type": labels[0] if labels else "Entity",
                        "properties": serialized_props
                    })
                
                edges = []
                for edge_data in edge_results:
                    props = edge_data.get("properties", {})
                    # 序列化属性值
                    serialized_props = {k: serialize_neo4j_value(v) for k, v in props.items() if k not in ["episode_uuid", "created_at"]}
                    edges.append({
                        "id": str(edge_data.get("id", "")),
                        "source": str(edge_data.get("source", "")),
                        "target": str(edge_data.get("target", "")),
                        "type": edge_data.get("type", ""),
                        "properties": serialized_props
                    })
            except Exception as e:
                logger.warning(f"Failed to query nodes/edges: {e}")
                nodes = []
                edges = []
            
            return {
                "episode_id": episode_id,
                "nodes": nodes,
                "edges": edges,
                "message": "Episode添加成功，实体和关系已自动提取"
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to add episode: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def retrieve(
        query: str,
        provider: str = "qianwen",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        使用Graphiti进行语义检索（完整流程2实现）
        
        流程：
        1. 用户查询
        2. Graphiti.search(query) - 自动调用 Embedding 生成查询向量
        3. Graphiti 在 Neo4j 中执行向量相似度搜索（vector.similarity.cosine）
        4. Graphiti 使用 Cross-encoder 重排序
        5. 返回排序后的结果
        
        Args:
            query: 查询文本
            provider: LLM提供商
            limit: 返回结果数量限制
            
        Returns:
            检索结果列表（包含 score 相似度分数）
        """
        try:
            graphiti = get_graphiti_instance(provider)
            
            # 步骤2-5: 使用Graphiti的search方法进行语义检索
            # Graphiti会自动：
            # - 调用 Embedding 模型生成查询向量
            # - 在 Neo4j 中执行向量相似度搜索
            # - 使用 Cross-encoder 重排序
            try:
                logger.info(f"开始语义搜索: query='{query}', limit={limit}, provider={provider}")
                results = await graphiti.search(query=query, num_results=limit)
                logger.info(f"语义搜索成功，返回 {len(results) if results else 0} 个结果")
            except Exception as search_error:
                # 如果向量搜索失败（Neo4j不支持向量函数），使用关键词搜索作为备选
                logger.warning(f"Graphiti semantic search failed, using keyword search: {search_error}")
                from app.core.neo4j_client import neo4j_client
                
                # 提取查询中的关键词（中文实体名称）
                import re
                # 提取中文字符作为关键词
                keywords = re.findall(r'[\u4e00-\u9fa5]+', query)
                # 如果没有中文，使用整个查询作为关键词
                if not keywords:
                    keywords = [query]
                
                # 使用关键词搜索节点（支持多个关键词）
                keyword_conditions = " OR ".join([f"n.name CONTAINS '{kw}'" for kw in keywords])
                keyword_query = f"""
                MATCH (n)
                WHERE {keyword_conditions} OR 
                      ANY(key IN keys(n) WHERE toString(n[key]) CONTAINS $query)
                RETURN DISTINCT id(n) as id, labels(n) as labels, properties(n) as properties
                LIMIT $limit
                """
                node_results = neo4j_client.execute_query(keyword_query, {
                    "query": query,
                    "limit": limit
                })
                
                # 使用关键词搜索关系（支持多个关键词，查找包含这些关键词的关系）
                rel_conditions = " OR ".join([
                    f"a.name CONTAINS '{kw}' OR b.name CONTAINS '{kw}'" for kw in keywords
                ])
                rel_keyword_query = f"""
                MATCH (a)-[r]->(b)
                WHERE type(r) CONTAINS $query OR
                      ANY(key IN keys(r) WHERE toString(r[key]) CONTAINS $query) OR
                      ({rel_conditions})
                RETURN DISTINCT id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties, a.name as source_name, b.name as target_name
                LIMIT $limit
                """
                rel_results = neo4j_client.execute_query(rel_keyword_query, {
                    "query": query,
                    "limit": limit
                })
                
                # 格式化结果
                formatted_results = []
                for node_data in node_results:
                    formatted_results.append({
                        "id": str(node_data.get("id", "")),
                        "type": "node",
                        "labels": node_data.get("labels", []),
                        "properties": node_data.get("properties", {}),
                        "score": 0.8  # 关键词匹配的默认分数
                    })
                
                for rel_data in rel_results:
                    formatted_results.append({
                        "id": str(rel_data.get("id", "")),
                        "type": "edge",
                        "source": str(rel_data.get("source", "")),
                        "target": str(rel_data.get("target", "")),
                        "source_name": rel_data.get("source_name", ""),
                        "target_name": rel_data.get("target_name", ""),
                        "rel_type": rel_data.get("type", ""),
                        "properties": rel_data.get("properties", {}),
                        "score": 0.8
                    })
                
                return formatted_results
            
            # 格式化Graphiti的语义搜索结果
            # Graphiti.search() 返回的是 EntityEdge 对象列表（关系/边）
            formatted_results = []
            seen_node_ids = set()  # 用于去重节点
            
            for result in results:
                try:
                    # EntityEdge 对象转换为字典
                    result_dict = {
                        "id": str(getattr(result, 'uuid', getattr(result, 'id', ''))),
                        "type": "edge",  # Graphiti.search() 返回的是边（关系）
                        "rel_type": getattr(result, 'name', getattr(result, 'type', 'RELATES_TO')),
                        "source": str(getattr(result, 'source_node_uuid', getattr(result, 'source', ''))),
                        "target": str(getattr(result, 'target_node_uuid', getattr(result, 'target', ''))),
                        "source_name": getattr(result, 'source_name', ''),
                        "target_name": getattr(result, 'target_name', ''),
                        "properties": getattr(result, 'attributes', getattr(result, 'properties', {})),
                        "score": getattr(result, 'score', 0.0),
                        "fact": getattr(result, 'fact', '')  # Graphiti 的关系事实描述
                    }
                    
                    # 尝试获取源节点和目标节点的完整信息（包括labels和properties）
                    from app.core.neo4j_client import neo4j_client
                    from app.core.utils import serialize_neo4j_properties
                    try:
                        # 查询源节点完整信息
                        source_uuid = result_dict["source"]
                        if source_uuid:
                            source_query = """
                            MATCH (n)
                            WHERE n.uuid = $uuid
                            RETURN n.name as name, labels(n) as labels, properties(n) as properties
                            LIMIT 1
                            """
                            source_result = neo4j_client.execute_query(source_query, {"uuid": source_uuid})
                            if source_result:
                                source_data = source_result[0]
                                result_dict["source_name"] = source_data.get("name", result_dict.get("source_name", ""))
                                result_dict["source_labels"] = source_data.get("labels", [])
                                result_dict["source_properties"] = serialize_neo4j_properties(source_data.get("properties", {}))
                        
                        # 查询目标节点完整信息
                        target_uuid = result_dict["target"]
                        if target_uuid:
                            target_query = """
                            MATCH (n)
                            WHERE n.uuid = $uuid
                            RETURN n.name as name, labels(n) as labels, properties(n) as properties
                            LIMIT 1
                            """
                            target_result = neo4j_client.execute_query(target_query, {"uuid": target_uuid})
                            if target_result:
                                target_data = target_result[0]
                                result_dict["target_name"] = target_data.get("name", result_dict.get("target_name", ""))
                                result_dict["target_labels"] = target_data.get("labels", [])
                                result_dict["target_properties"] = serialize_neo4j_properties(target_data.get("properties", {}))
                    except Exception as e:
                        logger.warning(f"Failed to get node info: {e}")
                    
                    formatted_results.append(result_dict)
                except Exception as e:
                    logger.warning(f"Failed to format result: {e}", exc_info=True)
                    # 尝试基本转换
                    if hasattr(result, 'to_dict'):
                        formatted_results.append(result.to_dict())
                    else:
                        formatted_results.append({
                            "id": str(result) if result else "",
                            "type": "edge",
                            "properties": {},
                            "score": 0.0
                        })
            
            logger.info(f"语义搜索完成，格式化后返回 {len(formatted_results)} 个结果")
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to retrieve: {e}")
            raise
    
    @staticmethod
    async def retrieve_by_group_id(
        query: str,
        group_id: str,
        provider: str = "qianwen",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        使用Graphiti进行语义检索，但只返回指定 group_id 的结果
        
        Args:
            query: 查询文本
            group_id: 文档 group_id（所有版本共享）
            provider: LLM提供商
            limit: 返回结果数量限制
            
        Returns:
            检索结果列表（包含 score 相似度分数），只包含指定 group_id 的结果
        """
        return await GraphitiService.retrieve_by_group_ids(
            query=query,
            group_ids=[group_id],
            provider=provider,
            limit=limit
        )
    
    @staticmethod
    async def retrieve_by_group_ids(
        query: str,
        group_ids: Optional[List[str]] = None,
        provider: str = "qianwen",
        limit: int = 10,
        cross_encoder_mode: str = "default"  # "default", "enhanced", "smart"
    ) -> List[Dict[str, Any]]:
        """
        使用Graphiti的search_()方法进行检索，支持三种交叉编码方案
        
        Args:
            query: 查询文本
            group_ids: 文档 group_id 列表（None 表示全部文档）
            provider: LLM提供商
            limit: 返回结果数量限制
            cross_encoder_mode: 交叉编码方案 ("default", "enhanced", "smart")
            
        Returns:
            检索结果列表（包含 score 相似度分数），按相关性排序
        """
        try:
            from app.core.neo4j_client import neo4j_client
            from app.core.utils import serialize_neo4j_properties
            from graphiti_core.search.search_config import (
                SearchConfig, EdgeSearchConfig, NodeSearchConfig,
                EpisodeSearchConfig, CommunitySearchConfig,
                EdgeSearchMethod, NodeSearchMethod, EpisodeSearchMethod, CommunitySearchMethod,
                EdgeReranker, NodeReranker, EpisodeReranker, CommunityReranker
            )
            from graphiti_core.search.search_filters import SearchFilters
            
            graphiti = get_graphiti_instance(provider)
            scope_desc = f"{len(group_ids)} 个文档" if group_ids else "全部文档"
            
            logger.info(f"开始检索（{scope_desc}）: query='{query}', limit={limit}, provider={provider}, mode={cross_encoder_mode}")
            
            # ========== 方案A：使用Graphiti的默认交叉编码 ==========
            if cross_encoder_mode == "default":
                return await GraphitiService._retrieve_with_scheme_a(graphiti, query, group_ids, limit, provider)
            
            # ========== 方案B和C：手动调用cross_encoder ==========
            elif cross_encoder_mode in ["enhanced", "smart"]:
                return await GraphitiService._retrieve_with_scheme_b_or_c(
                    graphiti, query, group_ids, limit, provider, cross_encoder_mode
                )
            
            else:
                raise ValueError(f"Unsupported cross_encoder_mode: {cross_encoder_mode}")
            
        except Exception as e:
            logger.error(f"Failed to retrieve by group_ids: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def _retrieve_with_scheme_a(
        graphiti,
        query: str,
        group_ids: Optional[List[str]],
        limit: int,
        provider: str
    ) -> List[Dict[str, Any]]:
        """
        方案A：使用Graphiti的默认交叉编码
        """
        from graphiti_core.search.search_config import (
            SearchConfig, EdgeSearchConfig, NodeSearchConfig,
            EpisodeSearchConfig, CommunitySearchConfig,
            EdgeSearchMethod, NodeSearchMethod, EpisodeSearchMethod, CommunitySearchMethod,
            EdgeReranker, NodeReranker, EpisodeReranker, CommunityReranker
        )
        from graphiti_core.search.search_filters import SearchFilters
        from app.core.neo4j_client import neo4j_client
        from app.core.utils import serialize_neo4j_properties
        
        # 创建SearchConfig（使用cross_encoder重排序）
        config = SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[EdgeSearchMethod.cosine_similarity, EdgeSearchMethod.bm25],
                reranker=EdgeReranker.cross_encoder,
                sim_min_score=0.6
            ),
            node_config=NodeSearchConfig(
                search_methods=[NodeSearchMethod.cosine_similarity, NodeSearchMethod.bm25],
                reranker=NodeReranker.cross_encoder,
                sim_min_score=0.6
            ),
            episode_config=EpisodeSearchConfig(
                search_methods=[EpisodeSearchMethod.bm25],
                reranker=EpisodeReranker.cross_encoder,
                sim_min_score=0.6
            ),
            community_config=CommunitySearchConfig(
                search_methods=[CommunitySearchMethod.cosine_similarity, CommunitySearchMethod.bm25],
                reranker=CommunityReranker.cross_encoder,
                sim_min_score=0.6
            ),
            limit=20
        )
        
        # 调用Graphiti的search_()方法
        search_filter = SearchFilters()
        results = await graphiti.search_(
            query=query,
            group_ids=group_ids,
            config=config,
            search_filter=search_filter
        )
        
        # 格式化结果
        formatted_results = []
        seen_uuids = set()
        
        # 格式化Edge结果
        for edge, score in zip(results.edges, results.edge_reranker_scores):
            edge_uuid = str(edge.uuid)
            if edge_uuid in seen_uuids:
                continue
            seen_uuids.add(edge_uuid)
            
            # 调试日志：打印实际的score值
            logger.debug(f"方案A Edge score: type={type(score)}, value={score}, edge={edge.name}")
            if score is None:
                logger.warning(f"方案A Edge reranker_score为None: edge={edge.name}")
            
            formatted_results.append({
                "id": edge_uuid,
                "type": "edge",
                "rel_type": edge.name,
                "source": str(edge.source_node_uuid),
                "target": str(edge.target_node_uuid),
                "source_name": "",  # 需要额外查询
                "target_name": "",  # 需要额外查询
                "properties": serialize_neo4j_properties(edge.attributes),
                "score": float(score) if score is not None else 0.0,
                "fact": edge.fact
            })
        
        # 格式化Entity结果
        for node, score in zip(results.nodes, results.node_reranker_scores):
            node_uuid = str(node.uuid)
            if node_uuid in seen_uuids:
                continue
            seen_uuids.add(node_uuid)
            
            # 调试日志：打印实际的score值（使用INFO级别确保输出）
            logger.info(f"方案A Entity score: type={type(score)}, value={score}, entity={node.name}")
            if score is None:
                logger.warning(f"方案A Entity reranker_score为None: entity={node.name}")
            elif score == 0:
                logger.warning(f"方案A Entity reranker_score为0: entity={node.name}")
            
            formatted_results.append({
                "id": node_uuid,
                "type": "entity",
                "labels": node.labels,
                "properties": serialize_neo4j_properties({
                    "name": node.name,
                    "summary": node.summary,
                    "group_id": node.group_id,
                    **node.attributes
                }),
                "score": float(score) if score is not None else 0.0
            })
        
        # 格式化Episode结果
        for episode, score in zip(results.episodes, results.episode_reranker_scores):
            episode_uuid = str(episode.uuid)
            if episode_uuid in seen_uuids:
                continue
            seen_uuids.add(episode_uuid)
            
            # 调试日志：打印实际的score值（使用INFO级别确保输出）
            logger.info(f"方案A Episode score: type={type(score)}, value={score}, episode={episode.name[:50]}")
            if score is None:
                logger.warning(f"方案A Episode reranker_score为None: episode={episode.name[:50]}")
            elif score == 0:
                logger.warning(f"方案A Episode reranker_score为0: episode={episode.name[:50]}")
            
            formatted_results.append({
                "id": episode_uuid,
                "type": "episode",
                "labels": episode.labels,
                "properties": {
                    "name": episode.name,
                    "content": episode.content,
                    "group_id": episode.group_id,
                    "source_description": episode.source_description
                },
                "score": float(score) if score is not None else 0.0
            })
        
        # 格式化Community结果
        for community, score in zip(results.communities, results.community_reranker_scores):
            community_uuid = str(community.uuid)
            if community_uuid in seen_uuids:
                continue
            seen_uuids.add(community_uuid)
            
            # 调试日志：打印实际的score值（使用INFO级别确保输出）
            logger.info(f"方案A Community score: type={type(score)}, value={score}, community={community.name}")
            if score is None:
                logger.warning(f"方案A Community reranker_score为None: community={community.name}")
            elif score == 0:
                logger.warning(f"方案A Community reranker_score为0: community={community.name}")
            
            formatted_results.append({
                "id": community_uuid,
                "type": "community",
                "labels": community.labels,
                "properties": {
                    "name": community.name,
                    "summary": community.summary,
                    "group_id": community.group_id,
                    "member_count": 0,  # 需要额外查询
                    "member_names": []  # 需要额外查询
                },
                "score": float(score) if score is not None else 0.0
            })
        
        # 批量查询额外信息（Edge的source_name/target_name，Community的member信息）
        await GraphitiService._enrich_results(formatted_results, group_ids)
        
        # 归一化score：找到最大值，将所有score归一化到0-100范围
        scores = [r.get("score", 0.0) for r in formatted_results]
        max_score = max(scores) if scores and max(scores) > 0 else 1.0
        
        if max_score > 0:
            for result in formatted_results:
                original_score = result.get("score", 0.0)
                normalized_score = (original_score / max_score) * 100
                result["score"] = normalized_score
            logger.info(f"方案A score归一化完成: max_score={max_score}, 归一化后范围: 0-100")
        else:
            logger.warning(f"方案A 所有score都为0，跳过归一化")
        
        # 按score排序并限制数量
        formatted_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        formatted_results = formatted_results[:limit]
        
        logger.info(f"方案A检索完成，返回 {len(formatted_results)} 个结果")
        return formatted_results
    
    @staticmethod
    async def _retrieve_with_scheme_b_or_c(
        graphiti,
        query: str,
        group_ids: Optional[List[str]],
        limit: int,
        provider: str,
        mode: str  # "enhanced" or "smart"
    ) -> List[Dict[str, Any]]:
        """
        方案B和C：手动调用cross_encoder，使用更丰富的字段
        """
        from graphiti_core.search.search_config import (
            SearchConfig, EdgeSearchConfig, NodeSearchConfig,
            EpisodeSearchConfig, CommunitySearchConfig,
            EdgeSearchMethod, NodeSearchMethod, EpisodeSearchMethod, CommunitySearchMethod,
            EdgeReranker, NodeReranker, EpisodeReranker, CommunityReranker
        )
        from graphiti_core.search.search_filters import SearchFilters
        from app.core.neo4j_client import neo4j_client
        from app.core.utils import serialize_neo4j_properties
        
        # 创建SearchConfig（使用RRF重排序，不使用cross_encoder）
        config = SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[EdgeSearchMethod.cosine_similarity, EdgeSearchMethod.bm25],
                reranker=EdgeReranker.rrf,  # 使用RRF而不是cross_encoder
                sim_min_score=0.6
            ),
            node_config=NodeSearchConfig(
                search_methods=[NodeSearchMethod.cosine_similarity, NodeSearchMethod.bm25],
                reranker=NodeReranker.rrf,  # 使用RRF而不是cross_encoder
                sim_min_score=0.6
            ),
            episode_config=EpisodeSearchConfig(
                search_methods=[EpisodeSearchMethod.bm25],
                reranker=EpisodeReranker.rrf,  # 使用RRF而不是cross_encoder
                sim_min_score=0.6
            ),
            community_config=CommunitySearchConfig(
                search_methods=[CommunitySearchMethod.cosine_similarity, CommunitySearchMethod.bm25],
                reranker=CommunityReranker.rrf,  # 使用RRF而不是cross_encoder
                sim_min_score=0.6
            ),
            limit=20
        )
        
        # 调用Graphiti的search_()方法（不使用cross_encoder重排序）
        search_filter = SearchFilters()
        results = await graphiti.search_(
            query=query,
            group_ids=group_ids,
            config=config,
            search_filter=search_filter
        )
        
        # 批量查询额外信息（Edge的source_name/target_name，Community的member信息）
        # 先查询这些信息，因为方案B和C需要用到
        node_uuid_to_name = {}
        community_uuid_to_members = {}
        
        # 收集所有需要查询的node_uuid
        node_uuids = set()
        for edge in results.edges:
            node_uuids.add(edge.source_node_uuid)
            node_uuids.add(edge.target_node_uuid)
        
        # 批量查询node名称
        if node_uuids:
            node_query = """
            MATCH (n)
            WHERE n.uuid IN $node_uuids
            RETURN n.uuid as uuid, n.name as name
            """
            node_results = neo4j_client.execute_query(node_query, {"node_uuids": list(node_uuids)})
            for node_result in node_results:
                node_uuid_to_name[str(node_result.get("uuid"))] = node_result.get("name", "")
        
        # 批量查询Community成员信息
        community_uuids = [str(c.uuid) for c in results.communities]
        if community_uuids:
            # 查询member_count和member_names
            for comm_uuid in community_uuids:
                try:
                    member_count_query = """
                    MATCH (c:Community {uuid: $uuid})
                    OPTIONAL MATCH (c)-[:HAS_MEMBER|CONTAINS]->(e1:Entity)
                    OPTIONAL MATCH (e2:Entity)-[:BELONGS_TO]->(c)
                    RETURN count(DISTINCT e1) + count(DISTINCT e2) as member_count
                    """
                    member_result = neo4j_client.execute_query(member_count_query, {"uuid": comm_uuid})
                    member_count = member_result[0].get("member_count", 0) if member_result else 0
                    
                    member_names_query = """
                    MATCH (c:Community {uuid: $uuid})
                    OPTIONAL MATCH (c)-[:HAS_MEMBER|CONTAINS]->(e1:Entity)
                    OPTIONAL MATCH (e2:Entity)-[:BELONGS_TO]->(c)
                    WITH collect(DISTINCT e1) + collect(DISTINCT e2) as all_entities
                    UNWIND all_entities as e
                    WHERE e IS NOT NULL
                    RETURN DISTINCT e.name as name
                    LIMIT 10
                    """
                    member_names_result = neo4j_client.execute_query(member_names_query, {"uuid": comm_uuid})
                    member_names = [m.get("name") for m in member_names_result if m.get("name")]
                    
                    community_uuid_to_members[comm_uuid] = {
                        "member_count": member_count,
                        "member_names": member_names
                    }
                except Exception as e:
                    logger.warning(f"查询Community成员信息失败: {e}")
                    community_uuid_to_members[comm_uuid] = {"member_count": 0, "member_names": []}
        
        # 提取文本用于交叉编码重排序
        edge_passages = []
        edge_objects = []
        entity_passages = []
        entity_objects = []
        episode_passages = []
        episode_objects = []
        community_passages = []
        community_objects = []
        
        # 提取Edge文本
        for edge in results.edges:
            source_name = node_uuid_to_name.get(str(edge.source_node_uuid), "")
            target_name = node_uuid_to_name.get(str(edge.target_node_uuid), "")
            
            relation_desc = f"{source_name} {edge.name} {target_name}" if source_name and target_name else edge.name
            
            if mode == "smart":
                # 方案C：使用LLM概括（仅支持本地大模型）
                from app.utils.text_summarizer import summarize_text
                if len(edge.fact) > 300:
                    # 方案C仅支持本地大模型，如果provider不是local，降级到截断
                    if provider == "local":
                        fact_text = await summarize_text(
                            text=edge.fact,
                            target_length=300,
                            context=query
                        )
                    else:
                        logger.warning(f"方案C需要本地大模型，当前provider={provider}，降级到截断")
                        fact_text = edge.fact[:300] + "..."
                else:
                    fact_text = edge.fact
            else:
                # 方案B：简单截断
                fact_text = edge.fact
                if len(fact_text) > 300:
                    fact_text = fact_text[:300] + "..."
            
            edge_passages.append(f"{relation_desc}\n{fact_text}")
            edge_objects.append(edge)
        
        # 提取Entity文本
        for node in results.nodes:
            if node.summary:
                entity_passages.append(f"{node.name}\n{node.summary}")
            else:
                entity_passages.append(node.name)
            entity_objects.append(node)
        
        # 提取Episode文本
        for episode in results.episodes:
            if mode == "smart":
                # 方案C：使用LLM概括（仅支持本地大模型）
                from app.utils.text_summarizer import summarize_text
                if len(episode.content) > 2000:
                    # 方案C仅支持本地大模型，如果provider不是local，降级到截断
                    if provider == "local":
                        summarized_content = await summarize_text(
                            text=episode.content,
                            target_length=1500,
                            context=query
                        )
                        episode_passages.append(f"{episode.name}\n{summarized_content}")
                    else:
                        logger.warning(f"方案C需要本地大模型，当前provider={provider}，降级到截断")
                        truncated = episode.content[:1500]
                        if '\n\n' in truncated:
                            truncated = truncated.rsplit('\n\n', 1)[0]
                        elif '\n' in truncated:
                            truncated = truncated.rsplit('\n', 1)[0]
                        episode_passages.append(f"{episode.name}\n{truncated}...")
                else:
                    episode_passages.append(f"{episode.name}\n{episode.content}")
            else:
                # 方案B：简单截断
                if len(episode.content) <= 2000:
                    episode_passages.append(f"{episode.name}\n{episode.content}")
                else:
                    truncated = episode.content[:1500]
                    if '\n\n' in truncated:
                        truncated = truncated.rsplit('\n\n', 1)[0]
                    elif '\n' in truncated:
                        truncated = truncated.rsplit('\n', 1)[0]
                    episode_passages.append(f"{episode.name}\n{truncated}...")
            episode_objects.append(episode)
        
        # 提取Community文本
        for community in results.communities:
            comm_uuid = str(community.uuid)
            members_info = community_uuid_to_members.get(comm_uuid, {"member_count": 0, "member_names": []})
            member_names = members_info.get("member_names", [])
            
            text_parts = [community.name]
            if community.summary:
                if mode == "smart":
                    # 方案C：使用LLM概括（仅支持本地大模型）
                    from app.utils.text_summarizer import summarize_text
                    if len(community.summary) > 500:
                        # 方案C仅支持本地大模型，如果provider不是local，降级到截断
                        if provider == "local":
                            summarized_summary = await summarize_text(
                                text=community.summary,
                                target_length=500,
                                context=query
                            )
                            text_parts.append(summarized_summary)
                        else:
                            logger.warning(f"方案C需要本地大模型，当前provider={provider}，降级到截断")
                            text_parts.append(community.summary[:500] + "...")
                    else:
                        text_parts.append(community.summary)
                else:
                    # 方案B：简单截断
                    if len(community.summary) > 500:
                        text_parts.append(community.summary[:500] + "...")
                    else:
                        text_parts.append(community.summary)
            
            if member_names and (not community.summary or len(community.summary) < 100):
                members_text = "、".join(member_names[:5])
                text_parts.append(f"包含实体: {members_text}")
            
            community_passages.append("\n".join(text_parts))
            community_objects.append(community)
        
        # 手动调用cross_encoder.rank()重排序
        # rank()返回 [(passage, score), ...]，已按分数排序
        edge_ranked = await graphiti.cross_encoder.rank(query=query, passages=edge_passages) if edge_passages else []
        entity_ranked = await graphiti.cross_encoder.rank(query=query, passages=entity_passages) if entity_passages else []
        episode_ranked = await graphiti.cross_encoder.rank(query=query, passages=episode_passages) if episode_passages else []
        community_ranked = await graphiti.cross_encoder.rank(query=query, passages=community_passages) if community_passages else []
        
        # 调试日志：打印cross_encoder.rank()返回的score值
        if edge_ranked:
            logger.info(f"方案B/C Edge ranked结果数量: {len(edge_ranked)}, 前3个score: {[s for _, s in edge_ranked[:3]]}")
        if episode_ranked:
            logger.info(f"方案B/C Episode ranked结果数量: {len(episode_ranked)}, 前3个score: {[s for _, s in episode_ranked[:3]]}")
        
        # 创建passage到对象的映射（因为rank()可能重新排序）
        edge_passage_to_obj = {passage: obj for passage, obj in zip(edge_passages, edge_objects)}
        entity_passage_to_obj = {passage: obj for passage, obj in zip(entity_passages, entity_objects)}
        episode_passage_to_obj = {passage: obj for passage, obj in zip(episode_passages, episode_objects)}
        community_passage_to_obj = {passage: obj for passage, obj in zip(community_passages, community_objects)}
        
        # 格式化结果
        formatted_results = []
        seen_uuids = set()
        
        # 格式化Edge结果（按重排序后的顺序）
        for passage, score in edge_ranked:
            edge = edge_passage_to_obj.get(passage)
            if not edge:
                continue
            edge_uuid = str(edge.uuid)
            if edge_uuid in seen_uuids:
                continue
            seen_uuids.add(edge_uuid)
            
            # 调试日志：打印实际的score值（使用INFO级别确保输出）
            logger.info(f"方案B/C Edge score: type={type(score)}, value={score}, edge={edge.name}")
            if score is None or score == 0:
                logger.warning(f"方案B/C Edge score为None或0: edge={edge.name}, score={score}")
            
            source_name = node_uuid_to_name.get(str(edge.source_node_uuid), "")
            target_name = node_uuid_to_name.get(str(edge.target_node_uuid), "")
            
            formatted_results.append({
                "id": edge_uuid,
                "type": "edge",
                "rel_type": edge.name,
                "source": str(edge.source_node_uuid),
                "target": str(edge.target_node_uuid),
                "source_name": source_name,
                "target_name": target_name,
                "properties": serialize_neo4j_properties(edge.attributes),
                "score": float(score) if score is not None else 0.0,
                "fact": edge.fact
            })
        
        # 格式化Entity结果（按重排序后的顺序）
        for passage, score in entity_ranked:
            node = entity_passage_to_obj.get(passage)
            if not node:
                continue
            node_uuid = str(node.uuid)
            if node_uuid in seen_uuids:
                continue
            seen_uuids.add(node_uuid)
            
            formatted_results.append({
                "id": node_uuid,
                "type": "entity",
                "labels": node.labels,
                "properties": serialize_neo4j_properties({
                    "name": node.name,
                    "summary": node.summary,
                    "group_id": node.group_id,
                    **node.attributes
                }),
                "score": float(score)
            })
        
        # 格式化Episode结果（按重排序后的顺序）
        for passage, score in episode_ranked:
            episode = episode_passage_to_obj.get(passage)
            if not episode:
                continue
            episode_uuid = str(episode.uuid)
            if episode_uuid in seen_uuids:
                continue
            seen_uuids.add(episode_uuid)
            
            # 调试日志：打印实际的score值（使用INFO级别确保输出）
            logger.info(f"方案B/C Episode score: type={type(score)}, value={score}, episode={episode.name[:50]}")
            if score is None or score == 0:
                logger.warning(f"方案B/C Episode score为None或0: episode={episode.name[:50]}, score={score}")
            
            formatted_results.append({
                "id": episode_uuid,
                "type": "episode",
                "labels": episode.labels,
                "properties": {
                    "name": episode.name,
                    "content": episode.content,
                    "group_id": episode.group_id,
                    "source_description": episode.source_description
                },
                "score": float(score) if score is not None else 0.0
            })
        
        # 格式化Community结果（按重排序后的顺序）
        for passage, score in community_ranked:
            community = community_passage_to_obj.get(passage)
            if not community:
                continue
            community_uuid = str(community.uuid)
            if community_uuid in seen_uuids:
                continue
            seen_uuids.add(community_uuid)
            
            members_info = community_uuid_to_members.get(community_uuid, {"member_count": 0, "member_names": []})
            
            formatted_results.append({
                "id": community_uuid,
                "type": "community",
                "labels": community.labels,
                "properties": {
                    "name": community.name,
                    "summary": community.summary,
                    "group_id": community.group_id,
                    "member_count": members_info.get("member_count", 0),
                    "member_names": members_info.get("member_names", [])
                },
                "score": float(score)
            })
        
        # 归一化score：找到最大值，将所有score归一化到0-100范围
        scores = [r.get("score", 0.0) for r in formatted_results]
        max_score = max(scores) if scores and max(scores) > 0 else 1.0
        
        if max_score > 0:
            for result in formatted_results:
                original_score = result.get("score", 0.0)
                normalized_score = (original_score / max_score) * 100
                result["score"] = normalized_score
            logger.info(f"方案{mode} score归一化完成: max_score={max_score}, 归一化后范围: 0-100")
        else:
            logger.warning(f"方案{mode} 所有score都为0，跳过归一化")
        
        # 按score排序并限制数量
        formatted_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        formatted_results = formatted_results[:limit]
        
        logger.info(f"方案{mode}检索完成，返回 {len(formatted_results)} 个结果")
        return formatted_results
    
    @staticmethod
    async def _enrich_results(
        formatted_results: List[Dict[str, Any]],
        group_ids: Optional[List[str]]
    ) -> None:
        """
        批量查询额外信息（Edge的source_name/target_name，Community的member信息）
        """
        from app.core.neo4j_client import neo4j_client
        
        # 收集所有需要查询的node_uuid
        node_uuids = set()
        community_uuids = set()
        
        for result in formatted_results:
            if result.get("type") == "edge":
                source = result.get("source", "")
                target = result.get("target", "")
                if source:
                    node_uuids.add(source)
                if target:
                    node_uuids.add(target)
            elif result.get("type") == "community":
                community_uuids.add(result.get("id", ""))
        
        # 批量查询node名称
        node_uuid_to_name = {}
        if node_uuids:
            try:
                node_query = """
                MATCH (n)
                WHERE n.uuid IN $node_uuids
                RETURN n.uuid as uuid, n.name as name
                """
                node_results = neo4j_client.execute_query(node_query, {"node_uuids": list(node_uuids)})
                for node_result in node_results:
                    node_uuid_to_name[str(node_result.get("uuid"))] = node_result.get("name", "")
            except Exception as e:
                logger.warning(f"批量查询node名称失败: {e}")
        
        # 批量查询Community成员信息
        community_uuid_to_members = {}
        if community_uuids:
            for comm_uuid in community_uuids:
                try:
                    member_count_query = """
                    MATCH (c:Community {uuid: $uuid})
                    OPTIONAL MATCH (c)-[:HAS_MEMBER|CONTAINS]->(e1:Entity)
                    OPTIONAL MATCH (e2:Entity)-[:BELONGS_TO]->(c)
                    RETURN count(DISTINCT e1) + count(DISTINCT e2) as member_count
                    """
                    member_result = neo4j_client.execute_query(member_count_query, {"uuid": comm_uuid})
                    member_count = member_result[0].get("member_count", 0) if member_result else 0
                    
                    member_names_query = """
                    MATCH (c:Community {uuid: $uuid})
                    OPTIONAL MATCH (c)-[:HAS_MEMBER|CONTAINS]->(e1:Entity)
                    OPTIONAL MATCH (e2:Entity)-[:BELONGS_TO]->(c)
                    WITH collect(DISTINCT e1) + collect(DISTINCT e2) as all_entities
                    UNWIND all_entities as e
                    WHERE e IS NOT NULL
                    RETURN DISTINCT e.name as name
                    LIMIT 10
                    """
                    member_names_result = neo4j_client.execute_query(member_names_query, {"uuid": comm_uuid})
                    member_names = [m.get("name") for m in member_names_result if m.get("name")]
                    
                    community_uuid_to_members[comm_uuid] = {
                        "member_count": member_count,
                        "member_names": member_names
                    }
                except Exception as e:
                    logger.warning(f"查询Community成员信息失败: {e}")
                    community_uuid_to_members[comm_uuid] = {"member_count": 0, "member_names": []}
        
        # 更新结果
        for result in formatted_results:
            if result.get("type") == "edge":
                source = result.get("source", "")
                target = result.get("target", "")
                result["source_name"] = node_uuid_to_name.get(source, "")
                result["target_name"] = node_uuid_to_name.get(target, "")
            elif result.get("type") == "community":
                comm_uuid = result.get("id", "")
                members_info = community_uuid_to_members.get(comm_uuid, {"member_count": 0, "member_names": []})
                result["properties"]["member_count"] = members_info.get("member_count", 0)
                result["properties"]["member_names"] = members_info.get("member_names", [])
