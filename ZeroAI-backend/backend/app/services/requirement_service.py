from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import uuid
import logging
from app.core.graphiti_client import get_graphiti_instance
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_value
from app.models.schemas import (
    Requirement, RequirementCreate, RequirementUpdate,
    Feature, Module, SimilarRequirementResult, SimilarRequirementResponse
)
from app.models.graphiti_entities import (
    ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP
)

logger = logging.getLogger(__name__)


class RequirementService:
    """需求助手服务层，提供需求文档管理、相似度查询、文档生成功能
    
    使用 Graphiti 自定义实体类型进行提取，不保留自定义 Prompt 提取逻辑
    """
    
    @staticmethod
    async def create_requirement(
        requirement_data: RequirementCreate,
        provider: str = "qianwen"
    ) -> Requirement:
        """
        创建需求文档（使用 Graphiti 自定义实体类型）
        
        流程：
        1. 使用 Graphiti 自定义实体类型提取实体和关系
        2. 手动补充元数据（版本号、创建时间等）
        3. 查询提取的实体和关系，统计数量
        4. 创建 Requirement 节点（用于需求管理）
        """
        try:
            requirement_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            logger.info("=" * 80)
            logger.info(f"【需求创建开始】需求ID: {requirement_id}, 名称: {requirement_data.name}, Provider: {provider}")
            logger.info(f"需求内容长度: {len(requirement_data.content)} 字符")
            
            # Step 1: 使用 Graphiti 自定义实体类型提取
            logger.info("-" * 80)
            logger.info("【Step 1】开始使用 Graphiti 自定义实体类型提取需求")
            logger.info(f"传入参数: entity_types={list(ENTITY_TYPES.keys())}, edge_types={list(EDGE_TYPES.keys())}, group_id={requirement_id}")
            episode_uuid = None
            episode_result = None
            
            try:
                logger.info(f"【Step 1.1】开始获取 Graphiti 实例，Provider: {provider}")
                graphiti = get_graphiti_instance(provider)
                logger.info(f"【Step 1.2】Graphiti 实例获取成功，类型: {type(graphiti)}")
                logger.info(f"【Step 1.3】开始调用 add_episode，文档长度: {len(requirement_data.content)} 字符")
                
                episode_result = await graphiti.add_episode(
                    name=requirement_data.name,
                    episode_body=requirement_data.content,  # 整个文档
                    source_description="需求文档",
                    reference_time=datetime.now(),
                    entity_types=ENTITY_TYPES,  # 传入自定义实体类型
                    edge_types=EDGE_TYPES,  # 传入自定义关系类型
                    edge_type_map=EDGE_TYPE_MAP,  # 传入关系类型映射
                    group_id=requirement_id  # 使用 group_id 关联所有提取的实体
                )
                
                logger.info(f"【Step 1.4】Graphiti add_episode 调用完成，返回结果类型: {type(episode_result)}")
                logger.info(f"【Step 1.5】episode_result 对象属性: {[attr for attr in dir(episode_result) if not attr.startswith('_')]}")
                
                # AddEpisodeResults 的结构是: {episode: Episode, nodes: [], edges: [], ...}
                # 需要从 episode_result.episode.uuid 获取
                logger.info(f"【Step 1.6】开始解析 episode_result，检查 episode 属性")
                if hasattr(episode_result, 'episode') and episode_result.episode:
                    logger.info(f"【Step 1.7】episode_result.episode 存在，类型: {type(episode_result.episode)}")
                    if hasattr(episode_result.episode, 'uuid'):
                        episode_uuid = str(episode_result.episode.uuid)
                        logger.info(f"【Step 1.8】从 episode_result.episode.uuid 获取成功: {episode_uuid}")
                    else:
                        logger.warning(f"【Step 1.8】episode_result.episode 没有 uuid 属性，属性列表: {[attr for attr in dir(episode_result.episode) if not attr.startswith('_')]}")
                        episode_uuid = None
                else:
                    logger.warning(f"【Step 1.7】episode_result 没有 episode 属性或 episode 为空")
                    logger.warning(f"episode_result 是否有 episode 属性: {hasattr(episode_result, 'episode')}")
                    if hasattr(episode_result, 'episode'):
                        logger.warning(f"episode_result.episode 的值: {episode_result.episode}")
                    episode_uuid = None
                
                logger.info(f"【Step 1.9】Graphiti 提取完成，episode_uuid: {episode_uuid}")
                
            except Exception as e:
                logger.error("=" * 80)
                logger.error(f"【Step 1 异常】Graphiti 提取失败: {e}", exc_info=True)
                logger.error(f"异常类型: {type(e).__name__}")
                logger.error(f"异常详情: {str(e)}")
                # Graphiti 提取失败，使用基本信息创建需求节点
                logger.warning("【Step 1 异常处理】Graphiti 提取失败，将使用基本信息创建需求节点")
            
            # Step 2: 查询 Graphiti 提取的实体和关系（统计数量）
            logger.info("-" * 80)
            logger.info("【Step 2】开始查询 Graphiti 提取的实体和关系（统计数量）")
            features_count = 0
            modules_count = 0
            
            if episode_uuid:
                logger.info(f"【Step 2.1】episode_uuid 存在: {episode_uuid}，开始查询 Feature 和 Module")
                try:
                    # 先查询所有 Feature 节点，看看是否有数据
                    logger.info(f"【Step 2.2】查询数据库中所有 Feature 节点总数（调试用）")
                    debug_feature_query = """
                    MATCH (f:Feature)
                    RETURN count(f) as total_count
                    """
                    debug_result = neo4j_client.execute_query(debug_feature_query, {})
                    total_features = debug_result[0].get('total_count', 0) if debug_result else 0
                    logger.info(f"【Step 2.2】数据库中所有 Feature 节点总数: {total_features}")
                    
                    # 查询提取的 Feature 实体数量
                    logger.info(f"【Step 2.3】查询 Feature 实体，episode_uuid: {episode_uuid}, group_id: {requirement_id}")
                    feature_query = """
                    MATCH (f:Feature)
                    WHERE f.episode_uuid = $episode_uuid OR f.group_id = $group_id
                    RETURN count(f) as count
                    """
                    feature_result = neo4j_client.execute_query(
                        feature_query,
                        {"episode_uuid": episode_uuid, "group_id": requirement_id}
                    )
                    if feature_result:
                        features_count = feature_result[0].get("count", 0)
                        logger.info(f"【Step 2.4】Feature 查询结果: {feature_result}, 数量: {features_count}")
                    else:
                        logger.warning(f"【Step 2.4】Feature 查询结果为空")
                    
                    # 查询提取的 Module 实体数量
                    logger.info(f"【Step 2.5】查询 Module 实体，episode_uuid: {episode_uuid}, group_id: {requirement_id}")
                    module_query = """
                    MATCH (m:Module)
                    WHERE m.episode_uuid = $episode_uuid OR m.group_id = $group_id
                    RETURN count(m) as count
                    """
                    module_result = neo4j_client.execute_query(
                        module_query,
                        {"episode_uuid": episode_uuid, "group_id": requirement_id}
                    )
                    if module_result:
                        modules_count = module_result[0].get("count", 0)
                        logger.info(f"【Step 2.6】Module 查询结果: {module_result}, 数量: {modules_count}")
                    else:
                        logger.warning(f"【Step 2.6】Module 查询结果为空")
                    
                    logger.info(f"【Step 2.7】Graphiti 提取统计完成: Feature={features_count}, Module={modules_count}")
                except Exception as e:
                    logger.error(f"【Step 2 异常】查询 Graphiti 提取结果失败: {e}", exc_info=True)
            else:
                logger.warning("【Step 2.1】episode_uuid 为空，跳过 Graphiti 提取结果查询")
            
            # Step 3: 手动补充元数据，创建 Requirement 节点（用于需求管理）
            logger.info("-" * 80)
            logger.info("【Step 3】开始创建 Requirement 节点（用于需求管理）")
            
            # 注意：Neo4j 不支持 Map 类型作为属性值，需要将 metadata 转换为 JSON 字符串
            import json as json_lib
            # 确保 metadata 不是空字典，如果是空字典或 None，则设为 None
            metadata_dict = requirement_data.metadata if requirement_data.metadata and len(requirement_data.metadata) > 0 else None
            metadata_str = json_lib.dumps(metadata_dict, ensure_ascii=False) if metadata_dict else None
            
            # 构建需求节点数据（手动补充元数据）
            requirement_node = {
                "id": requirement_id,
                "name": requirement_data.name,  # 使用用户输入的名称
                "description": requirement_data.description or (requirement_data.content[:200] if requirement_data.content else ""),
                "version": requirement_data.version,  # 手动补充版本号
                "content": requirement_data.content,
                "created_at": now,  # 手动补充创建时间
                "updated_at": now,
                "episode_uuid": episode_uuid if episode_uuid else None
            }
            
            # 只有当 metadata 不为空时才添加
            if metadata_str:
                requirement_node["metadata"] = metadata_str
            
            # 调试：打印 requirement_node 的内容，检查是否有 Map 类型
            logger.info(f"准备创建需求节点，requirement_node keys: {list(requirement_node.keys())}")
            for key, value in requirement_node.items():
                if isinstance(value, dict):
                    logger.error(f"发现 Map 类型属性: {key} = {value}")
                    raise ValueError(f"属性 {key} 不能是 Map 类型，必须是基本类型或数组")
            
            # 创建需求节点
            # 构建动态查询，根据是否有 metadata 来决定
            if metadata_str:
                create_requirement_query = """
                CREATE (r:Requirement {
                    id: $id,
                    name: $name,
                    description: $description,
                    version: $version,
                    content: $content,
                    created_at: $created_at,
                    updated_at: $updated_at,
                    episode_uuid: $episode_uuid,
                    metadata: $metadata
                })
                RETURN id(r) as id, r.name as name, r.description as description,
                       r.version as version, r.content as content,
                       r.created_at as created_at, r.updated_at as updated_at,
                       r.metadata as metadata
                """
            else:
                create_requirement_query = """
                CREATE (r:Requirement {
                    id: $id,
                    name: $name,
                    description: $description,
                    version: $version,
                    content: $content,
                    created_at: $created_at,
                    updated_at: $updated_at,
                    episode_uuid: $episode_uuid
                })
                RETURN id(r) as id, r.name as name, r.description as description,
                       r.version as version, r.content as content,
                       r.created_at as created_at, r.updated_at as updated_at
                """
            
            result = neo4j_client.execute_query(
                create_requirement_query,
                requirement_node
            )
            
            if not result:
                raise Exception("创建需求节点失败")
            
            logger.info("=" * 80)
            logger.info(f"【需求创建完成】需求ID: {requirement_id}, 功能点数量: {features_count}, 模块数量: {modules_count}")
            logger.info("=" * 80)
            
            # 返回需求对象
            # 解析 metadata（如果是 JSON 字符串）
            metadata = {}
            if metadata_str:
                try:
                    metadata = json_lib.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
                except json_lib.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata JSON: {metadata_str}")
                    metadata = {}
            
            return Requirement(
                id=requirement_id,
                name=requirement_node["name"],
                content=requirement_node["content"],
                version=requirement_node.get("version"),
                description=requirement_node.get("description"),
                metadata=metadata,
                created_at=requirement_node["created_at"],
                updated_at=requirement_node["updated_at"],
                features_count=features_count,
                modules_count=modules_count
            )
            
        except Exception as e:
            logger.error(f"创建需求失败: {e}", exc_info=True)
            raise
    
    @staticmethod
    def get_requirement(requirement_id: str) -> Optional[Requirement]:
        """获取需求详情"""
        try:
            query = """
            MATCH (r:Requirement {id: $id})
            OPTIONAL MATCH (r)-[:HAS_FEATURE]->(f:Feature)
            OPTIONAL MATCH (r)-[:HAS_MODULE]->(m:Module)
            RETURN r, count(DISTINCT f) as features_count, count(DISTINCT m) as modules_count
            """
            
            result = neo4j_client.execute_query(query, {"id": requirement_id})
            
            if not result:
                return None
            
            r_data = result[0]["r"]
            # 解析 metadata（如果是 JSON 字符串）
            metadata = {}
            metadata_str = r_data.get("metadata")
            if metadata_str:
                try:
                    import json as json_lib
                    metadata = json_lib.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
                except:
                    metadata = {}
            
            # 转换 DateTime 对象为字符串
            created_at = serialize_neo4j_value(r_data.get("created_at"))
            updated_at = serialize_neo4j_value(r_data.get("updated_at"))
            
            return Requirement(
                id=str(r_data.get("id", requirement_id)),
                name=r_data.get("name", ""),
                content=r_data.get("content", ""),
                version=r_data.get("version"),
                description=r_data.get("description"),
                metadata=metadata,
                created_at=created_at,
                updated_at=updated_at,
                features_count=result[0].get("features_count", 0),
                modules_count=result[0].get("modules_count", 0)
            )
        except Exception as e:
            logger.error(f"获取需求失败: {e}", exc_info=True)
            return None
    
    @staticmethod
    def list_requirements(limit: int = 50, offset: int = 0) -> List[Requirement]:
        """获取需求列表"""
        try:
            query = """
            MATCH (r:Requirement)
            OPTIONAL MATCH (r)-[:HAS_FEATURE]->(f:Feature)
            OPTIONAL MATCH (r)-[:HAS_MODULE]->(m:Module)
            RETURN r, count(DISTINCT f) as features_count, count(DISTINCT m) as modules_count
            ORDER BY r.created_at DESC
            SKIP $offset
            LIMIT $limit
            """
            
            results = neo4j_client.execute_query(query, {"limit": limit, "offset": offset})
            
            requirements = []
            for record in results:
                r_data = record["r"]
                # 解析 metadata（如果是 JSON 字符串）
                metadata = {}
                metadata_str = r_data.get("metadata")
                if metadata_str:
                    try:
                        import json as json_lib
                        metadata = json_lib.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
                    except:
                        metadata = {}
                
                # 转换 DateTime 对象为字符串
                created_at = serialize_neo4j_value(r_data.get("created_at"))
                updated_at = serialize_neo4j_value(r_data.get("updated_at"))
                
                requirements.append(Requirement(
                    id=str(r_data.get("id", "")),
                    name=r_data.get("name", ""),
                    content=r_data.get("content", ""),
                    version=r_data.get("version"),
                    description=r_data.get("description"),
                    metadata=metadata,
                    created_at=created_at,
                    updated_at=updated_at,
                    features_count=record.get("features_count", 0),
                    modules_count=record.get("modules_count", 0)
                ))
            
            return requirements
        except Exception as e:
            logger.error(f"获取需求列表失败: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def find_similar_requirements(
        requirement_id: Optional[str] = None,
        query_text: Optional[str] = None,
        limit: int = 10,
        include_features: bool = True,
        include_modules: bool = True,
        provider: str = "qianwen"
    ) -> SimilarRequirementResponse:
        """
        查找相似需求（组合方案）
        
        1. 语义相似度搜索（使用 Graphiti）
        2. 功能点重合度查询
        3. 模块重合度查询
        4. 组合和排序结果
        """
        try:
            query_requirement = None
            
            # 如果提供了 requirement_id，先获取该需求
            if requirement_id:
                query_requirement = RequirementService.get_requirement(requirement_id)
                if not query_requirement:
                    raise ValueError(f"需求不存在: {requirement_id}")
                query_text = query_text or f"{query_requirement.name} {query_requirement.description}"
            
            if not query_text:
                raise ValueError("必须提供 requirement_id 或 query_text")
            
            # Step 1: 语义相似度搜索（使用 Graphiti）
            logger.info(f"开始语义相似度搜索: query_text='{query_text[:100]}'")
            graphiti = get_graphiti_instance(provider)
            
            semantic_results = []
            try:
                search_results = await graphiti.search(query=query_text, num_results=limit * 2)
                
                # 将 Graphiti 搜索结果转换为需求ID列表
                for result in search_results:
                    # Graphiti 返回的是 EntityEdge，我们需要找到关联的 Requirement
                    # 通过 episode_uuid 关联
                    episode_uuid = getattr(result, 'episode_uuid', None)
                    if episode_uuid:
                        # 查询该 episode 关联的需求
                        find_req_query = """
                        MATCH (r:Requirement {episode_uuid: $episode_uuid})
                        RETURN r.id as id
                        LIMIT 1
                        """
                        req_result = neo4j_client.execute_query(
                            find_req_query,
                            {"episode_uuid": str(episode_uuid)}
                        )
                        if req_result:
                            semantic_results.append({
                                "requirement_id": req_result[0]["id"],
                                "semantic_score": getattr(result, 'score', 0.0)
                            })
            except Exception as e:
                logger.warning(f"Graphiti 语义搜索失败: {e}")
            
            # Step 2: 功能点重合度查询（如果提供了 requirement_id）
            feature_results = []
            if requirement_id and include_features:
                logger.info("开始功能点重合度查询")
                feature_overlap_query = """
                MATCH (r1:Requirement {id: $req_id})-[:HAS_FEATURE]->(f:Feature)
                MATCH (r2:Requirement)-[:HAS_FEATURE]->(f)
                WHERE r2.id <> $req_id
                RETURN r2.id as id, count(f) as overlap_count,
                       collect(f.name) as common_features
                ORDER BY overlap_count DESC
                LIMIT $limit
                """
                feature_results = neo4j_client.execute_query(
                    feature_overlap_query,
                    {"req_id": requirement_id, "limit": limit * 2}
                )
            
            # Step 3: 模块重合度查询（如果提供了 requirement_id）
            module_results = []
            if requirement_id and include_modules:
                logger.info("开始模块重合度查询")
                module_overlap_query = """
                MATCH (r1:Requirement {id: $req_id})-[:HAS_MODULE]->(m:Module)
                MATCH (r2:Requirement)-[:HAS_MODULE]->(m)
                WHERE r2.id <> $req_id
                RETURN r2.id as id, count(DISTINCT m) as module_overlap,
                       collect(m.name) as common_modules
                ORDER BY module_overlap DESC
                LIMIT $limit
                """
                module_results = neo4j_client.execute_query(
                    module_overlap_query,
                    {"req_id": requirement_id, "limit": limit * 2}
                )
            
            # Step 4: 合并和排序结果
            results_map = {}  # requirement_id -> SimilarRequirementResult
            
            # 添加语义搜索结果
            for sem_result in semantic_results:
                req_id = sem_result["requirement_id"]
                if req_id not in results_map:
                    req = RequirementService.get_requirement(req_id)
                    if req:
                        results_map[req_id] = {
                            "requirement": req,
                            "semantic_score": sem_result["semantic_score"],
                            "feature_overlap_count": 0,
                            "module_overlap_count": 0,
                            "common_features": [],
                            "common_modules": []
                        }
            
            # 添加功能点重合结果
            for feat_result in feature_results:
                req_id = feat_result["id"]
                if req_id not in results_map:
                    req = RequirementService.get_requirement(req_id)
                    if req:
                        results_map[req_id] = {
                            "requirement": req,
                            "semantic_score": 0.0,
                            "feature_overlap_count": 0,
                            "module_overlap_count": 0,
                            "common_features": [],
                            "common_modules": []
                        }
                
                results_map[req_id]["feature_overlap_count"] = feat_result["overlap_count"]
                results_map[req_id]["common_features"] = feat_result.get("common_features", [])
                
                # 计算功能点重合比例
                if query_requirement:
                    total_features = query_requirement.features_count
                    if total_features > 0:
                        results_map[req_id]["feature_overlap_ratio"] = feat_result["overlap_count"] / total_features
                    else:
                        results_map[req_id]["feature_overlap_ratio"] = 0.0
            
            # 添加模块重合结果
            for mod_result in module_results:
                req_id = mod_result["id"]
                if req_id not in results_map:
                    req = RequirementService.get_requirement(req_id)
                    if req:
                        results_map[req_id] = {
                            "requirement": req,
                            "semantic_score": 0.0,
                            "feature_overlap_count": 0,
                            "module_overlap_count": 0,
                            "common_features": [],
                            "common_modules": []
                        }
                
                results_map[req_id]["module_overlap_count"] = mod_result["module_overlap"]
                results_map[req_id]["common_modules"] = mod_result.get("common_modules", [])
                
                # 计算模块重合比例
                if query_requirement:
                    total_modules = query_requirement.modules_count
                    if total_modules > 0:
                        results_map[req_id]["module_overlap_ratio"] = mod_result["module_overlap"] / total_modules
                    else:
                        results_map[req_id]["module_overlap_ratio"] = 0.0
            
            # 计算综合相似度分数并排序
            similar_results = []
            for req_id, data in results_map.items():
                # 综合相似度 = 语义相似度 * 0.5 + 功能点重合比例 * 0.3 + 模块重合比例 * 0.2
                semantic_score = data.get("semantic_score", 0.0)
                feature_ratio = data.get("feature_overlap_ratio", 0.0)
                module_ratio = data.get("module_overlap_ratio", 0.0)
                
                similarity_score = (
                    semantic_score * 0.5 +
                    feature_ratio * 0.3 +
                    module_ratio * 0.2
                )
                
                similar_results.append(SimilarRequirementResult(
                    requirement=data["requirement"],
                    similarity_score=similarity_score,
                    semantic_score=semantic_score if semantic_score > 0 else None,
                    feature_overlap_count=data.get("feature_overlap_count") if data.get("feature_overlap_count", 0) > 0 else None,
                    feature_overlap_ratio=data.get("feature_overlap_ratio") if data.get("feature_overlap_ratio", 0) > 0 else None,
                    module_overlap_count=data.get("module_overlap_count") if data.get("module_overlap_count", 0) > 0 else None,
                    module_overlap_ratio=data.get("module_overlap_ratio") if data.get("module_overlap_ratio", 0) > 0 else None,
                    common_features=data.get("common_features") if data.get("common_features") else None,
                    common_modules=data.get("common_modules") if data.get("common_modules") else None
                ))
            
            # 按相似度分数排序
            similar_results.sort(key=lambda x: x.similarity_score, reverse=True)
            similar_results = similar_results[:limit]
            
            logger.info(f"相似需求查询完成，返回 {len(similar_results)} 个结果")
            
            return SimilarRequirementResponse(
                query_requirement=query_requirement,
                results=similar_results,
                total=len(similar_results)
            )
            
        except Exception as e:
            logger.error(f"查找相似需求失败: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def generate_requirement_document(
        new_requirement_id: str,
        similar_requirement_ids: List[str],
        format: str = "markdown",
        provider: str = "qianwen"
    ) -> Dict[str, Any]:
        """
        生成需求文档
        
        结合新需求 + 相似历史需求，生成新文档
        """
        try:
            # 获取新需求
            new_req = RequirementService.get_requirement(new_requirement_id)
            if not new_req:
                raise ValueError(f"需求不存在: {new_requirement_id}")
            
            # 获取相似历史需求
            similar_reqs = []
            for req_id in similar_requirement_ids:
                req = RequirementService.get_requirement(req_id)
                if req:
                    similar_reqs.append(req)
            
            # 构建生成 Prompt
            generation_prompt = f"""你是一个专业的需求文档编写专家。请根据以下信息生成一份完整的需求规格说明书。

**新需求信息**：
- 需求名称：{new_req.name}
- 需求描述：{new_req.description or new_req.content[:500]}
- 版本号：{new_req.version or "v1.0"}

**相似历史需求**（供参考）：
{chr(10).join([f"- {req.name} (版本: {req.version or 'N/A'}) - {req.description or req.content[:200]}" for req in similar_reqs[:5]])}

**生成要求**：
1. 参考历史需求的文档结构和格式
2. 结合新需求的特点，生成完整的需求文档
3. 包含以下章节：
   - 文档信息（版本号、编写日期等）
   - 项目概述（背景、定位、技术架构）
   - 系统架构
   - 功能需求详细说明（按模块组织）
   - 数据模型
   - 非功能性需求
4. 保持专业、清晰、完整的风格
5. 使用 Markdown 格式

请生成完整的需求文档。"""
            
            # 调用 LLM 生成文档
            llm_client = get_llm_client(provider)
            generated_content = await llm_client.generate(
                provider=provider,
                prompt=generation_prompt,
                temperature=0.7,
                max_tokens=8000
            )
            
            # 保存生成的文档
            document_id = str(uuid.uuid4())
            document_name = f"{new_req.name}_生成文档_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 根据格式处理文档
            if format == "markdown":
                # Markdown 格式直接返回内容
                return {
                    "document_id": document_id,
                    "document_name": document_name,
                    "format": format,
                    "content": generated_content,
                    "file_path": None,
                    "download_url": None
                }
            elif format == "word":
                # TODO: 实现 Word 格式转换
                # 可以使用 python-docx 库
                return {
                    "document_id": document_id,
                    "document_name": document_name,
                    "format": format,
                    "content": generated_content,
                    "file_path": None,
                    "download_url": None,
                    "message": "Word 格式转换功能待实现"
                }
            elif format == "pdf":
                # TODO: 实现 PDF 格式转换
                # 可以使用 markdown2pdf 或 weasyprint
                return {
                    "document_id": document_id,
                    "document_name": document_name,
                    "format": format,
                    "content": generated_content,
                    "file_path": None,
                    "download_url": None,
                    "message": "PDF 格式转换功能待实现"
                }
            else:
                raise ValueError(f"不支持的文档格式: {format}")
                
        except Exception as e:
            logger.error(f"生成需求文档失败: {e}", exc_info=True)
            raise

