from typing import List, Optional, Dict, Any
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties
from app.models.schemas import PathSegment, PathResult
import logging

logger = logging.getLogger(__name__)


class PathService:
    """路径查询服务"""
    
    @staticmethod
    def find_entity_by_name(name: str) -> Optional[Dict[str, Any]]:
        """根据名称查找实体"""
        query = """
        MATCH (n)
        WHERE n.name = $name
        RETURN id(n) as id, labels(n) as labels, properties(n) as properties
        LIMIT 1
        """
        result = neo4j_client.execute_query(query, {"name": name})
        if result:
            data = result[0]
            return {
                "id": str(data["id"]),
                "labels": data.get("labels", []),
                "properties": serialize_neo4j_properties(data.get("properties", {}))
            }
        return None
    
    @staticmethod
    def find_paths_between_entities(
        source_name: str,
        target_name: str,
        max_depth: int = 10,
        limit: int = 100
    ) -> List[PathResult]:
        """
        查找两个实体之间的所有路径
        
        Args:
            source_name: 源实体名称
            target_name: 目标实体名称
            max_depth: 最大路径长度
            limit: 返回路径数量限制
            
        Returns:
            路径列表
        """
        # 查找源实体和目标实体
        source_entity = PathService.find_entity_by_name(source_name)
        target_entity = PathService.find_entity_by_name(target_name)
        
        if not source_entity:
            raise ValueError(f"源实体 '{source_name}' 不存在")
        if not target_entity:
            raise ValueError(f"目标实体 '{target_name}' 不存在")
        
        source_id = int(source_entity["id"])
        target_id = int(target_entity["id"])
        
        # Neo4j 不支持 allSimplePaths，使用变通方法：
        # 1. 先查找所有最短路径
        # 2. 然后查找不同长度的路径（逐步增加深度）
        # 注意：必须直接使用 session 来获取 Path 对象，不能通过 execute_query
        all_paths = []
        seen_paths = set()  # 用于去重
        
        # 首先查找所有最短路径（支持双向路径）
        query_shortest = f"""
        MATCH (source), (target)
        WHERE id(source) = $source_id AND id(target) = $target_id
        MATCH path = allShortestPaths((source)-[*1..{max_depth}]-(target))
        RETURN path, length(path) as pathLength
        """
        
        try:
            with neo4j_client.get_session() as session:
                result = session.run(query_shortest, {
                    "source_id": source_id,
                    "target_id": target_id
                })
                for record in result:
                    path = record["path"]  # 这是 Path 对象
                    path_length = record.get("pathLength", 0)
                    
                    # 检查 path 是否为 Path 对象
                    if not hasattr(path, 'nodes'):
                        logger.warning(f"路径对象不是 Path 类型: {type(path)}")
                        continue
                    
                    # 使用路径的节点ID序列作为唯一标识
                    try:
                        path_key = tuple([n.id for n in path.nodes])
                        if path_key not in seen_paths:
                            seen_paths.add(path_key)
                            all_paths.append((path, path_length))
                    except Exception as e:
                        logger.warning(f"处理路径失败: {e}")
                        continue
        except Exception as e:
            logger.warning(f"查找最短路径失败: {e}")
        
        # 如果还需要更多路径，查找不同长度的路径
        if len(all_paths) < limit:
            with neo4j_client.get_session() as session:
                for depth in range(2, max_depth + 1):
                    if len(all_paths) >= limit:
                        break
                    
                    query_depth = f"""
                    MATCH (source), (target)
                    WHERE id(source) = $source_id AND id(target) = $target_id
                    MATCH path = (source)-[*{depth}]-(target)
                    WHERE length(path) = {depth}
                    WITH path, length(path) as pathLength
                    LIMIT $remaining_limit
                    RETURN path, pathLength
                    """
                    
                    try:
                        result = session.run(query_depth, {
                            "source_id": source_id,
                            "target_id": target_id,
                            "remaining_limit": limit - len(all_paths)
                        })
                        for record in result:
                            path = record["path"]  # 这是 Path 对象
                            path_length = record.get("pathLength", 0)
                            
                            # 检查 path 是否为 Path 对象
                            if not hasattr(path, 'nodes'):
                                logger.warning(f"路径对象不是 Path 类型: {type(path)}")
                                continue
                            
                            try:
                                path_key = tuple([n.id for n in path.nodes])
                                if path_key not in seen_paths:
                                    seen_paths.add(path_key)
                                    all_paths.append((path, path_length))
                                    if len(all_paths) >= limit:
                                        break
                            except Exception as e:
                                logger.warning(f"处理路径失败: {e}")
                                continue
                    except Exception as e:
                        logger.warning(f"查找深度 {depth} 的路径失败: {e}")
                        continue
        
        # 按路径长度排序
        all_paths.sort(key=lambda x: x[1])
        results = all_paths[:limit]
        
        paths = []
        path_lengths = []
        
        for idx, (path, path_length) in enumerate(results):
            path_lengths.append(path_length)
            
            # 检查 path 是否为 Path 对象
            if not hasattr(path, 'nodes'):
                logger.error(f"路径对象不是 Path 类型: {type(path)}, 跳过")
                continue
            
            # 提取路径中的节点和关系
            segments = []
            try:
                nodes = list(path.nodes)
                relationships = list(path.relationships)
            except Exception as e:
                logger.error(f"提取路径节点和关系失败: {e}, path类型: {type(path)}")
                continue
            
            for i, rel in enumerate(relationships):
                # 获取关系的起始节点和目标节点
                start_node = nodes[i]
                end_node = nodes[i + 1]
                
                # 获取节点信息
                start_node_id = str(start_node.id)
                start_node_name = dict(start_node).get("name", f"节点{start_node_id}")
                end_node_id = str(end_node.id)
                end_node_name = dict(end_node).get("name", f"节点{end_node_id}")
                
                # 获取关系信息
                rel_id = str(rel.id)
                rel_props = dict(rel)
                # 优先使用 name 属性（如 FOUNDED, WORKS_FOR），如果没有则使用 type 属性（如 RELATES_TO）
                rel_name = rel_props.get("name", "")
                rel_fact = rel_props.get("fact", "")
                
                # 获取关系类型
                try:
                    # Neo4j关系对象有type属性（如 RELATES_TO）
                    if hasattr(rel, 'type'):
                        rel_type = rel.type
                    else:
                        rel_type = "RELATES_TO"
                except:
                    rel_type = "RELATES_TO"
                
                # 如果关系有 name 属性，使用它作为显示类型（更具体）
                if rel_name:
                    rel_type = rel_name
                
                segments.append(PathSegment(
                    source_id=start_node_id,
                    source_name=start_node_name,
                    target_id=end_node_id,
                    target_name=end_node_name,
                    relation_id=rel_id,
                    relation_type=rel_type,
                    relation_name=rel_name if rel_name else None,
                    relation_fact=rel_fact if rel_fact else None
                ))
            
            paths.append(PathResult(
                path_id=f"path_{idx}",
                segments=segments,
                length=path_length,
                is_shortest=False  # 稍后计算
            ))
        
        # 计算最短路径长度并标记
        if path_lengths:
            shortest_length = min(path_lengths)
            for path in paths:
                if path.length == shortest_length:
                    path.is_shortest = True
        
        return paths
    
    @staticmethod
    def find_entity_relationship_chains(
        entity_name: str,
        max_depth: int = 10,
        limit: int = 100
    ) -> List[PathResult]:
        """
        查找某个实体的所有关系链（不指定目标实体）
        
        Args:
            entity_name: 实体名称
            max_depth: 最大路径长度
            limit: 返回路径数量限制
            
        Returns:
            路径列表
        """
        # 查找实体
        entity = PathService.find_entity_by_name(entity_name)
        if not entity:
            raise ValueError(f"实体 '{entity_name}' 不存在")
        
        entity_id = int(entity["id"])
        
        # 查找从该实体出发的所有路径（限制深度）
        # 注意：必须直接使用 session 来获取 Path 对象
        all_paths_raw = []
        seen_paths = set()
        
        with neo4j_client.get_session() as session:
            for depth in range(1, max_depth + 1):
                if len(all_paths_raw) >= limit:
                    break
                
                query = f"""
                MATCH (source)
                WHERE id(source) = $entity_id
                MATCH path = (source)-[*{depth}]->(target)
                WHERE target <> source AND length(path) = {depth}
                WITH path, length(path) as pathLength
                LIMIT $remaining_limit
                RETURN path, pathLength
                """
                
                try:
                    result = session.run(query, {
                        "entity_id": entity_id,
                        "remaining_limit": limit - len(all_paths_raw)
                    })
                    for record in result:
                        path = record["path"]  # 这是 Path 对象
                        path_length = record.get("pathLength", 0)
                        
                        # 检查 path 是否为 Path 对象
                        if not hasattr(path, 'nodes'):
                            logger.warning(f"路径对象不是 Path 类型: {type(path)}")
                            continue
                        
                        try:
                            path_key = tuple([n.id for n in path.nodes])
                            if path_key not in seen_paths:
                                seen_paths.add(path_key)
                                all_paths_raw.append((path, path_length))
                                if len(all_paths_raw) >= limit:
                                    break
                        except Exception as e:
                            logger.warning(f"处理路径失败: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"查找深度 {depth} 的关系链失败: {e}")
                    continue
        
        # 按路径长度排序
        all_paths_raw.sort(key=lambda x: x[1])
        results = all_paths_raw[:limit]
        
        paths = []
        path_lengths = []
        
        for idx, (path, path_length) in enumerate(results):
            path_lengths.append(path_length)
            
            # 检查 path 是否为 Path 对象
            if not hasattr(path, 'nodes'):
                logger.error(f"路径对象不是 Path 类型: {type(path)}, 跳过")
                continue
            
            # 提取路径中的节点和关系
            segments = []
            try:
                nodes = list(path.nodes)
                relationships = list(path.relationships)
            except Exception as e:
                logger.error(f"提取路径节点和关系失败: {e}, path类型: {type(path)}")
                continue
            
            for i, rel in enumerate(relationships):
                start_node = nodes[i]
                end_node = nodes[i + 1]
                
                start_node_id = str(start_node.id)
                start_node_name = dict(start_node).get("name", f"节点{start_node_id}")
                end_node_id = str(end_node.id)
                end_node_name = dict(end_node).get("name", f"节点{end_node_id}")
                
                rel_id = str(rel.id)
                rel_props = dict(rel)
                rel_name = rel_props.get("name", "")
                rel_fact = rel_props.get("fact", "")
                
                # 获取关系类型
                try:
                    if hasattr(rel, 'type'):
                        rel_type = rel.type
                    else:
                        rel_type = "RELATES_TO"
                except:
                    rel_type = "RELATES_TO"
                
                # 如果关系有 name 属性，使用它作为显示类型（更具体）
                if rel_name:
                    rel_type = rel_name
                
                segments.append(PathSegment(
                    source_id=start_node_id,
                    source_name=start_node_name,
                    target_id=end_node_id,
                    target_name=end_node_name,
                    relation_id=rel_id,
                    relation_type=rel_type,
                    relation_name=rel_name if rel_name else None,
                    relation_fact=rel_fact if rel_fact else None
                ))
            
            paths.append(PathResult(
                path_id=f"chain_{idx}",
                segments=segments,
                length=path_length,
                is_shortest=False
            ))
        
        # 计算最短路径长度并标记
        if path_lengths:
            shortest_length = min(path_lengths)
            for path in paths:
                if path.length == shortest_length:
                    path.is_shortest = True
        
        return paths

