"""
版本比较服务

实现文档版本的差异分析和比较功能
"""
import logging
from typing import Dict, List, Any, Optional, Set
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties

logger = logging.getLogger(__name__)


class VersionComparisonService:
    """版本比较服务"""
    
    @staticmethod
    def get_document_versions(base_document_id: str) -> List[Dict[str, Any]]:
        """
        获取同一需求的所有版本
        
        Args:
            base_document_id: 基础文档ID（group_id）
        
        Returns:
            版本列表，按版本号排序
        """
        query = """
        MATCH (e:Episodic)
        WHERE e.group_id = $base_document_id
          AND e.name CONTAINS '文档概览'
        RETURN DISTINCT e.version as version,
               e.version_number as version_number,
               e.created_at as created_at,
               e.document_name as document_name,
               e.uuid as episode_uuid,
               properties(e) as properties
        ORDER BY e.version_number ASC
        """
        
        result = neo4j_client.execute_query(query, {"base_document_id": base_document_id})
        
        versions = []
        for record in result:
            versions.append({
                "version": record.get("version"),
                "version_number": record.get("version_number"),
                "created_at": record.get("created_at").isoformat() if record.get("created_at") and hasattr(record.get("created_at"), "isoformat") else str(record.get("created_at", "")),
                "document_name": record.get("document_name"),
                "episode_uuid": record.get("episode_uuid"),
                "properties": serialize_neo4j_properties(record.get("properties", {}))
            })
        
        # 统计每个版本的Episode、Entity和Relationship数量
        for version_info in versions:
            version = version_info["version"]
            
            # 统计Episode
            episode_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $base_document_id
              AND e.version = $version
            RETURN count(e) as episode_count
            """
            episode_result = neo4j_client.execute_query(episode_query, {
                "base_document_id": base_document_id,
                "version": version
            })
            version_info["statistics"] = {
                "total_episodes": episode_result[0].get("episode_count", 0) if episode_result else 0
            }
            
            # 统计Entity（通过MENTIONS关系关联）
            entity_query = """
            MATCH (e:Episodic)-[:MENTIONS]->(n:Entity)
            WHERE e.group_id = $base_document_id
              AND e.version = $version
            RETURN count(DISTINCT n) as entity_count
            """
            entity_result = neo4j_client.execute_query(entity_query, {
                "base_document_id": base_document_id,
                "version": version
            })
            version_info["statistics"]["total_entities"] = entity_result[0].get("entity_count", 0) if entity_result else 0
            
            # 统计Relationship（通过MENTIONS关系关联）
            rel_query = """
            MATCH (e:Episodic)-[:MENTIONS]->(a)-[r:RELATES_TO|MENTIONS]->(b)
            WHERE e.group_id = $base_document_id
              AND e.version = $version
            RETURN count(DISTINCT r) as relationship_count
            """
            rel_result = neo4j_client.execute_query(rel_query, {
                "base_document_id": base_document_id,
                "version": version
            })
            version_info["statistics"]["total_relationships"] = rel_result[0].get("relationship_count", 0) if rel_result else 0
        
        return versions
    
    @staticmethod
    def compare_versions(
        base_document_id: str,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        比较两个版本的差异
        
        Args:
            base_document_id: 基础文档ID（group_id）
            version1: 第一个版本号（如 "V1"）
            version2: 第二个版本号（如 "V3"）
        
        Returns:
            版本比较结果，包含实体和关系的变化
        """
        # 获取两个版本的所有实体
        v1_entities = VersionComparisonService._get_version_entities(base_document_id, version1)
        v2_entities = VersionComparisonService._get_version_entities(base_document_id, version2)
        
        # 获取两个版本的所有关系
        v1_relationships = VersionComparisonService._get_version_relationships(base_document_id, version1)
        v2_relationships = VersionComparisonService._get_version_relationships(base_document_id, version2)
        
        # 比较实体
        entity_changes = VersionComparisonService._compare_entities(v1_entities, v2_entities)
        
        # 比较关系
        relationship_changes = VersionComparisonService._compare_relationships(v1_relationships, v2_relationships)
        
        # 计算相似度
        similarity_score = VersionComparisonService._calculate_similarity(
            len(v1_entities), len(v2_entities),
            len(v1_relationships), len(v2_relationships),
            entity_changes, relationship_changes
        )
        
        # 获取版本信息
        versions = VersionComparisonService.get_document_versions(base_document_id)
        v1_info = next((v for v in versions if v["version"] == version1), None)
        v2_info = next((v for v in versions if v["version"] == version2), None)
        
        return {
            "base_document_id": base_document_id,
            "version1": {
                "version": version1,
                "version_number": v1_info["version_number"] if v1_info else None,
                "created_at": v1_info["created_at"] if v1_info else None,
                "entity_count": len(v1_entities),
                "relationship_count": len(v1_relationships),
                "statistics": v1_info["statistics"] if v1_info else {}
            },
            "version2": {
                "version": version2,
                "version_number": v2_info["version_number"] if v2_info else None,
                "created_at": v2_info["created_at"] if v2_info else None,
                "entity_count": len(v2_entities),
                "relationship_count": len(v2_relationships),
                "statistics": v2_info["statistics"] if v2_info else {}
            },
            "entity_changes": entity_changes,
            "relationship_changes": relationship_changes,
            "similarity_score": similarity_score
        }
    
    @staticmethod
    def _get_version_entities(base_document_id: str, version: str) -> List[Dict[str, Any]]:
        """获取指定版本的所有实体（通过MENTIONS关系关联）"""
        query = """
        MATCH (e:Episodic)-[:MENTIONS]->(n:Entity)
        WHERE e.group_id = $base_document_id
          AND e.version = $version
        RETURN DISTINCT n.uuid as uuid,
               n.name as name,
               labels(n) as labels,
               properties(n) as properties
        """
        
        result = neo4j_client.execute_query(query, {
            "base_document_id": base_document_id,
            "version": version
        })
        
        entities = []
        for record in result:
            entities.append({
                "uuid": record.get("uuid"),
                "name": record.get("name"),
                "type": record.get("labels", ["Entity"])[0] if record.get("labels") else "Entity",
                "properties": serialize_neo4j_properties(record.get("properties", {}))
            })
        
        return entities
    
    @staticmethod
    def _get_version_relationships(base_document_id: str, version: str) -> List[Dict[str, Any]]:
        """获取指定版本的所有关系（通过MENTIONS关系关联）"""
        query = """
        MATCH (e:Episodic)-[:MENTIONS]->(a)-[r:RELATES_TO|MENTIONS]->(b)
        WHERE e.group_id = $base_document_id
          AND e.version = $version
        RETURN DISTINCT r.uuid as uuid,
               r.name as name,
               type(r) as type,
               r.fact as fact,
               id(startNode(r)) as source_id,
               id(endNode(r)) as target_id,
               a.name as source_name,
               b.name as target_name,
               properties(r) as properties
        """
        
        result = neo4j_client.execute_query(query, {
            "base_document_id": base_document_id,
            "version": version
        })
        
        relationships = []
        for record in result:
            relationships.append({
                "uuid": record.get("uuid"),
                "name": record.get("name"),
                "type": record.get("type", "RELATES_TO"),
                "fact": record.get("fact"),
                "source_id": str(record.get("source_id", "")),
                "target_id": str(record.get("target_id", "")),
                "source_name": record.get("source_name", ""),
                "target_name": record.get("target_name", ""),
                "properties": serialize_neo4j_properties(record.get("properties", {}))
            })
        
        return relationships
    
    @staticmethod
    def _compare_entities(
        v1_entities: List[Dict[str, Any]],
        v2_entities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """比较两个版本的实体（使用名称作为唯一标识）"""
        # 使用名称作为唯一标识（因为不同版本的实体可能有不同的UUID）
        # 创建名称到实体的映射
        v1_entity_map = {}
        for e in v1_entities:
            name = e.get("name", "")
            if name:
                # 如果名称已存在，保留第一个
                if name not in v1_entity_map:
                    v1_entity_map[name] = e
        
        v2_entity_map = {}
        for e in v2_entities:
            name = e.get("name", "")
            if name:
                if name not in v2_entity_map:
                    v2_entity_map[name] = e
        
        v1_names = set(v1_entity_map.keys())
        v2_names = set(v2_entity_map.keys())
        
        # 新增的实体（在V2中但不在V1中）
        added_names = v2_names - v1_names
        added = [v2_entity_map[name] for name in added_names]
        
        # 删除的实体（在V1中但不在V2中）
        removed_names = v1_names - v2_names
        removed = [v1_entity_map[name] for name in removed_names]
        
        # 未变更的实体（在两个版本中都存在）
        unchanged_names = v1_names & v2_names
        unchanged = [v1_entity_map[name] for name in unchanged_names]
        
        # 修改的实体（属性发生变化，但名称相同）
        modified = []
        for name in unchanged_names:
            v1_entity = v1_entity_map[name]
            v2_entity = v2_entity_map[name]
            
            # 检查属性是否变化（名称相同，但其他属性可能不同）
            if v1_entity.get("properties") != v2_entity.get("properties"):
                modified.append({
                    "name": name,
                    "v1": v1_entity,
                    "v2": v2_entity
                })
        
        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged
        }
    
    @staticmethod
    def _compare_relationships(
        v1_relationships: List[Dict[str, Any]],
        v2_relationships: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """比较两个版本的关系（使用fact和节点名称作为唯一标识）"""
        # 使用fact和源/目标节点名称作为唯一标识
        def get_rel_key(rel):
            fact = rel.get("fact", "")
            source_name = rel.get("source_name", "")
            target_name = rel.get("target_name", "")
            return (fact, source_name, target_name)
        
        v1_rel_map = {}
        for r in v1_relationships:
            key = get_rel_key(r)
            if key not in v1_rel_map:
                v1_rel_map[key] = r
        
        v2_rel_map = {}
        for r in v2_relationships:
            key = get_rel_key(r)
            if key not in v2_rel_map:
                v2_rel_map[key] = r
        
        v1_keys = set(v1_rel_map.keys())
        v2_keys = set(v2_rel_map.keys())
        
        # 新增的关系
        added_keys = v2_keys - v1_keys
        added = [v2_rel_map[key] for key in added_keys]
        
        # 删除的关系
        removed_keys = v1_keys - v2_keys
        removed = [v1_rel_map[key] for key in removed_keys]
        
        # 未变更的关系
        unchanged_keys = v1_keys & v2_keys
        unchanged = [v1_rel_map[key] for key in unchanged_keys]
        
        # 修改的关系（fact相同，但属性可能不同）
        modified = []
        for key in unchanged_keys:
            v1_rel = v1_rel_map[key]
            v2_rel = v2_rel_map[key]
            
            # 检查关系属性是否变化
            if v1_rel.get("properties") != v2_rel.get("properties"):
                modified.append({
                    "key": key,
                    "v1": v1_rel,
                    "v2": v2_rel
                })
        
        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged
        }
    
    @staticmethod
    def _calculate_similarity(
        v1_entity_count: int,
        v2_entity_count: int,
        v1_rel_count: int,
        v2_rel_count: int,
        entity_changes: Dict[str, List],
        relationship_changes: Dict[str, List]
    ) -> float:
        """计算两个版本的相似度（0-1之间）"""
        # 计算实体相似度
        total_entities = max(v1_entity_count, v2_entity_count)
        if total_entities == 0:
            entity_similarity = 1.0
        else:
            unchanged_entities = len(entity_changes.get("unchanged", []))
            entity_similarity = unchanged_entities / total_entities
        
        # 计算关系相似度
        total_relationships = max(v1_rel_count, v2_rel_count)
        if total_relationships == 0:
            rel_similarity = 1.0
        else:
            unchanged_rels = len(relationship_changes.get("unchanged", []))
            rel_similarity = unchanged_rels / total_relationships
        
        # 综合相似度（实体和关系的加权平均）
        # 如果实体和关系数量都为0，返回1.0
        if total_entities == 0 and total_relationships == 0:
            return 1.0
        
        # 根据实体和关系的数量进行加权
        total_items = total_entities + total_relationships
        if total_items == 0:
            return 1.0
        
        similarity = (entity_similarity * total_entities + rel_similarity * total_relationships) / total_items
        
        return round(similarity, 4)

