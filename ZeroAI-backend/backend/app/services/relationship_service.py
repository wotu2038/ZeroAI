from typing import List, Optional, Dict, Any
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties
from app.models.schemas import Relationship, RelationshipCreate, RelationshipUpdate
from app.services.entity_service import EntityService
import logging

logger = logging.getLogger(__name__)


class RelationshipService:
    # 预定义的关系类型
    RELATIONSHIP_TYPES = [
        "KNOWS",        # 认识
        "WORKS_FOR",    # 工作于
        "LOCATED_IN",   # 位于
        "RELATED_TO",   # 相关
        "OWNS",         # 拥有
        "CREATED",      # 创建
        "PART_OF",      # 属于
        "INFLUENCES",   # 影响
        "COLLABORATES_WITH", # 合作
        "MANAGES",      # 管理
        "FOUNDED",      # 创立
        "DEVELOPS"      # 开发
    ]
    
    @staticmethod
    def create_relationship(rel: RelationshipCreate) -> Relationship:
        """创建关系"""
        # 获取源实体和目标实体
        source_entity = EntityService.get_entity_by_name(rel.source)
        if not source_entity:
            # 尝试通过ID查找
            try:
                source_entity = EntityService.get_entity(rel.source)
            except:
                pass
            if not source_entity:
                raise ValueError(f"源实体 '{rel.source}' 不存在")
        
        target_entity = EntityService.get_entity_by_name(rel.target)
        if not target_entity:
            try:
                target_entity = EntityService.get_entity(rel.target)
            except:
                pass
            if not target_entity:
                raise ValueError(f"目标实体 '{rel.target}' 不存在")
        
        # 检查关系是否已存在
        check_query = """
        MATCH (a)-[r]->(b)
        WHERE id(a) = $source_id AND id(b) = $target_id AND type(r) = $rel_type
        RETURN r LIMIT 1
        """
        existing = neo4j_client.execute_query(
            check_query,
            {
                "source_id": int(source_entity.id),
                "target_id": int(target_entity.id),
                "rel_type": rel.type
            }
        )
        
        if existing:
            raise ValueError(f"关系已存在")
        
        # 创建关系
        create_query = f"""
        MATCH (a), (b)
        WHERE id(a) = $source_id AND id(b) = $target_id
        CREATE (a)-[r:{rel.type} $properties]->(b)
        SET r.id = id(r)
        RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
        """
        
        result = neo4j_client.execute_write(
            create_query,
            {
                "source_id": int(source_entity.id),
                "target_id": int(target_entity.id),
                "properties": rel.properties
            }
        )
        
        if not result:
            raise ValueError("创建关系失败")
        
        data = result[0]
        props = {k: v for k, v in data["properties"].items() if k != "id"}
        return Relationship(
            id=str(data["id"]),
            source=str(data["source"]),
            target=str(data["target"]),
            type=data["type"],
            properties=serialize_neo4j_properties(props)
        )
    
    @staticmethod
    def get_relationship(rel_id: str) -> Optional[Relationship]:
        """获取关系"""
        query = """
        MATCH (a)-[r]->(b)
        WHERE id(r) = $id
        RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
        """
        
        result = neo4j_client.execute_query(query, {"id": int(rel_id)})
        
        if not result:
            return None
        
        data = result[0]
        props = {k: v for k, v in data["properties"].items() if k != "id"}
        
        return Relationship(
            id=str(data["id"]),
            source=str(data["source"]),
            target=str(data["target"]),
            type=data["type"],
            properties=serialize_neo4j_properties(props)
        )
    
    @staticmethod
    def list_relationships(
        rel_type: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Relationship]:
        """列出关系"""
        if rel_type:
            query = f"""
            MATCH (a)-[r:{rel_type}]->(b)
            RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
            SKIP $skip
            LIMIT $limit
            """
        else:
            query = """
            MATCH (a)-[r]->(b)
            RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
            SKIP $skip
            LIMIT $limit
            """
        
        result = neo4j_client.execute_query(query, {"limit": limit, "skip": skip})
        
        relationships = []
        for data in result:
            props = {k: v for k, v in data["properties"].items() if k != "id"}
            relationships.append(Relationship(
                id=str(data["id"]),
                source=str(data["source"]),
                target=str(data["target"]),
                type=data["type"],
                properties=serialize_neo4j_properties(props)
            ))
        
        return relationships
    
    @staticmethod
    def update_relationship(rel_id: str, update: RelationshipUpdate) -> Optional[Relationship]:
        """更新关系"""
        updates = []
        params = {"id": int(rel_id)}
        
        if update.type:
            # Neo4j不支持直接修改关系类型，需要删除后重建
            # 这里简化处理，只更新属性
            pass
        
        if update.properties:
            for key, value in update.properties.items():
                updates.append(f"r.{key} = $prop_{key}")
                params[f"prop_{key}"] = value
        
        if not updates:
            return RelationshipService.get_relationship(rel_id)
        
        query = f"""
        MATCH (a)-[r]->(b)
        WHERE id(r) = $id
        SET {', '.join(updates)}
        RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
        """
        
        result = neo4j_client.execute_write(query, params)
        
        if not result:
            return None
        
        data = result[0]
        props = {k: v for k, v in data["properties"].items() if k != "id"}
        
        return Relationship(
            id=str(data["id"]),
            source=str(data["source"]),
            target=str(data["target"]),
            type=data["type"],
            properties=serialize_neo4j_properties(props)
        )
    
    @staticmethod
    def delete_relationship(rel_id: str) -> bool:
        """删除关系"""
        query = """
        MATCH (a)-[r]->(b)
        WHERE id(r) = $id
        DELETE r
        RETURN count(r) as deleted
        """
        
        result = neo4j_client.execute_write(query, {"id": int(rel_id)})
        
        if result and result[0].get("deleted", 0) > 0:
            return True
        return False
    
    @staticmethod
    def get_entity_relationships(entity_id: str) -> List[Relationship]:
        """获取实体的所有关系"""
        query = """
        MATCH (a)-[r]->(b)
        WHERE id(a) = $id OR id(b) = $id
        RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
        """
        
        result = neo4j_client.execute_query(query, {"id": int(entity_id)})
        
        relationships = []
        for data in result:
            props = {k: v for k, v in data["properties"].items() if k != "id"}
            relationships.append(Relationship(
                id=str(data["id"]),
                source=str(data["source"]),
                target=str(data["target"]),
                type=data["type"],
                properties=serialize_neo4j_properties(props)
            ))
        
        return relationships

