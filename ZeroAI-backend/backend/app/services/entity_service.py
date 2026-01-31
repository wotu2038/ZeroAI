from typing import List, Optional, Dict, Any
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties
from app.models.schemas import Entity, EntityCreate, EntityUpdate
import logging

logger = logging.getLogger(__name__)


class EntityService:
    # 预定义的实体类型
    ENTITY_TYPES = [
        "Person",      # 人物
        "Organization", # 组织
        "Location",    # 地点
        "Concept",     # 概念
        "Event",       # 事件
        "Product",     # 产品
        "Technology",  # 技术
        "Document"     # 文档
    ]
    
    @staticmethod
    def create_entity(entity: EntityCreate) -> Entity:
        """创建实体"""
        # 检查实体是否已存在
        check_query = """
        MATCH (e {name: $name})
        RETURN e LIMIT 1
        """
        existing = neo4j_client.execute_query(check_query, {"name": entity.name})
        
        if existing:
            raise ValueError(f"实体 '{entity.name}' 已存在")
        
        # 创建实体
        create_query = f"""
        CREATE (e:{entity.type} $properties)
        SET e.name = $name
        RETURN id(e) as id, e.name as name, labels(e) as labels, properties(e) as properties
        """
        
        properties = entity.properties.copy()
        properties["name"] = entity.name
        
        result = neo4j_client.execute_write(
            create_query,
            {"name": entity.name, "properties": properties}
        )
        
        if not result:
            raise ValueError("创建实体失败")
        
        data = result[0]
        entity_type = data["labels"][0] if data["labels"] else entity.type
        props = {k: v for k, v in data["properties"].items() if k != "name"}
        return Entity(
            id=str(data["id"]),
            name=data["name"],
            type=entity_type,
            properties=serialize_neo4j_properties(props)
        )
    
    @staticmethod
    def get_entity(entity_id: str) -> Optional[Entity]:
        """获取实体"""
        query = """
        MATCH (e)
        WHERE id(e) = $id
        RETURN e.id as id, labels(e) as labels, e.name as name, properties(e) as properties
        """
        
        result = neo4j_client.execute_query(query, {"id": int(entity_id)})
        
        if not result:
            return None
        
        data = result[0]
        entity_type = data["labels"][0] if data["labels"] else "Entity"
        props = {k: v for k, v in data["properties"].items() if k != "name"}
        
        return Entity(
            id=str(data["id"]),
            name=data["name"],
            type=entity_type,
            properties=serialize_neo4j_properties(props)
        )
    
    @staticmethod
    def get_entity_by_name(name: str) -> Optional[Entity]:
        """根据名称获取实体"""
        query = """
        MATCH (e {name: $name})
        RETURN id(e) as id, labels(e) as labels, e.name as name, properties(e) as properties
        LIMIT 1
        """
        
        result = neo4j_client.execute_query(query, {"name": name})
        
        if not result:
            return None
        
        data = result[0]
        entity_type = data["labels"][0] if data["labels"] else "Entity"
        props = {k: v for k, v in data["properties"].items() if k != "name"}
        
        return Entity(
            id=str(data["id"]),
            name=data["name"],
            type=entity_type,
            properties=serialize_neo4j_properties(props)
        )
    
    @staticmethod
    def list_entities(
        entity_type: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Entity]:
        """列出实体"""
        if entity_type:
            query = f"""
            MATCH (e:{entity_type})
            RETURN id(e) as id, labels(e) as labels, e.name as name, properties(e) as properties
            ORDER BY e.name
            SKIP $skip
            LIMIT $limit
            """
        else:
            query = """
            MATCH (e)
            WHERE e.name IS NOT NULL
            RETURN id(e) as id, labels(e) as labels, e.name as name, properties(e) as properties
            ORDER BY e.name
            SKIP $skip
            LIMIT $limit
            """
        
        result = neo4j_client.execute_query(query, {"limit": limit, "skip": skip})
        
        entities = []
        for data in result:
            entity_type = data["labels"][0] if data["labels"] else "Entity"
            props = {k: v for k, v in data["properties"].items() if k != "name"}
            
            entities.append(Entity(
                id=str(data["id"]),
                name=data["name"],
                type=entity_type,
                properties=serialize_neo4j_properties(props)
            ))
        
        return entities
    
    @staticmethod
    def update_entity(entity_id: str, update: EntityUpdate) -> Optional[Entity]:
        """更新实体"""
        updates = []
        params = {"id": int(entity_id)}
        
        if update.name:
            updates.append("e.name = $name")
            params["name"] = update.name
        
        if update.type:
            # 先删除旧标签，再添加新标签
            query_remove = f"""
            MATCH (e)
            WHERE id(e) = $id
            REMOVE e:{update.type}
            """
            # 这里简化处理，实际应该获取旧标签
            updates.append(f"SET e:{update.type}")
        
        if update.properties:
            for key, value in update.properties.items():
                updates.append(f"e.{key} = $prop_{key}")
                params[f"prop_{key}"] = value
        
        if not updates:
            return EntityService.get_entity(entity_id)
        
        query = f"""
        MATCH (e)
        WHERE id(e) = $id
        SET {', '.join(updates)}
        RETURN id(e) as id, labels(e) as labels, e.name as name, properties(e) as properties
        """
        
        result = neo4j_client.execute_write(query, params)
        
        if not result:
            return None
        
        data = result[0]
        entity_type = data["labels"][0] if data["labels"] else "Entity"
        props = {k: v for k, v in data["properties"].items() if k != "name"}
        
        return Entity(
            id=str(data["id"]),
            name=data["name"],
            type=entity_type,
            properties=serialize_neo4j_properties(props)
        )
    
    @staticmethod
    def delete_entity(entity_id: str) -> bool:
        """删除实体"""
        query = """
        MATCH (e)
        WHERE id(e) = $id
        DETACH DELETE e
        RETURN count(e) as deleted
        """
        
        result = neo4j_client.execute_write(query, {"id": int(entity_id)})
        
        if result and result[0].get("deleted", 0) > 0:
            return True
        return False
    
    @staticmethod
    def search_entities(keyword: str, limit: int = 20) -> List[Entity]:
        """搜索实体"""
        query = """
        MATCH (e)
        WHERE e.name CONTAINS $keyword
        RETURN id(e) as id, labels(e) as labels, e.name as name, properties(e) as properties
        ORDER BY e.name
        LIMIT $limit
        """
        
        result = neo4j_client.execute_query(query, {"keyword": keyword, "limit": limit})
        
        entities = []
        for data in result:
            entity_type = data["labels"][0] if data["labels"] else "Entity"
            props = {k: v for k, v in data["properties"].items() if k != "name"}
            
            entities.append(Entity(
                id=str(data["id"]),
                name=data["name"],
                type=entity_type,
                properties=serialize_neo4j_properties(props)
            ))
        
        return entities

