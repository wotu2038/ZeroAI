"""
组合管理服务

实现组合（Composite）的创建、查询、更新、删除功能
组合用于将多个GroupID关联在一起，形成项目、功能等业务概念
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties

logger = logging.getLogger(__name__)


class CompositeService:
    """组合管理服务"""
    
    @staticmethod
    def create_composite(
        name: str,
        composite_type: str,
        description: Optional[str] = None,
        group_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        创建组合
        
        Args:
            name: 组合名称
            composite_type: 组合类型（project, feature, document, custom）
            description: 描述信息
            group_ids: 关联的GroupID列表
        
        Returns:
            创建的组合信息
        """
        composite_uuid = str(uuid.uuid4())
        now = datetime.now()
        
        # 创建组合节点
        create_query = """
        CREATE (c:CompositeGroup {
            uuid: $uuid,
            name: $name,
            type: $type,
            description: $description,
            created_at: $created_at,
            updated_at: $updated_at
        })
        RETURN c.uuid as uuid, c.name as name, c.type as type,
               c.description as description, c.created_at as created_at
        """
        
        result = neo4j_client.execute_write(create_query, {
            "uuid": composite_uuid,
            "name": name,
            "type": composite_type,
            "description": description or "",
            "created_at": now,
            "updated_at": now
        })
        
        if not result:
            raise Exception("创建组合失败")
        
        # 创建与GroupID的关联关系
        if group_ids:
            CompositeService._link_group_ids(composite_uuid, group_ids)
        
        return {
            "uuid": composite_uuid,
            "name": name,
            "type": composite_type,
            "description": description,
            "group_ids": group_ids or [],
            "created_at": now.isoformat() if hasattr(now, 'isoformat') else str(now)
        }
    
    @staticmethod
    def _link_group_ids(composite_uuid: str, group_ids: List[str]):
        """创建组合与GroupID的关联关系"""
        for index, group_id in enumerate(group_ids):
            link_query = """
            MATCH (c:CompositeGroup {uuid: $composite_uuid})
            MERGE (dg:DocumentGroup {group_id: $group_id})
            ON CREATE SET dg.group_id = $group_id, dg.created_at = $created_at
            MERGE (c)-[r:CONTAINS]->(dg)
            ON CREATE SET r.created_at = $created_at, r.order = $order
            ON MATCH SET r.updated_at = $created_at
            RETURN r
            """
            
            neo4j_client.execute_write(link_query, {
                "composite_uuid": composite_uuid,
                "group_id": group_id,
                "created_at": datetime.now(),
                "order": index
            })
    
    @staticmethod
    def get_composite(composite_uuid: str) -> Optional[Dict[str, Any]]:
        """获取组合详情"""
        query = """
        MATCH (c:CompositeGroup {uuid: $uuid})
        OPTIONAL MATCH (c)-[:CONTAINS]->(dg:DocumentGroup)
        RETURN c.uuid as uuid, c.name as name, c.type as type,
               c.description as description, c.created_at as created_at,
               c.updated_at as updated_at,
               collect(DISTINCT dg.group_id) as group_ids
        """
        
        result = neo4j_client.execute_query(query, {"uuid": composite_uuid})
        
        if not result:
            return None
        
        data = result[0]
        return {
            "uuid": data.get("uuid"),
            "name": data.get("name"),
            "type": data.get("type"),
            "description": data.get("description"),
            "group_ids": data.get("group_ids", []),
            "created_at": data.get("created_at").isoformat() if data.get("created_at") and hasattr(data.get("created_at"), "isoformat") else str(data.get("created_at", "")),
            "updated_at": data.get("updated_at").isoformat() if data.get("updated_at") and hasattr(data.get("updated_at"), "isoformat") else str(data.get("updated_at", ""))
        }
    
    @staticmethod
    def list_composites(composite_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取组合列表"""
        if composite_type:
            query = """
            MATCH (c:CompositeGroup {type: $type})
            OPTIONAL MATCH (c)-[:CONTAINS]->(dg:DocumentGroup)
            RETURN c.uuid as uuid, c.name as name, c.type as type,
                   c.description as description, c.created_at as created_at,
                   c.updated_at as updated_at,
                   collect(DISTINCT dg.group_id) as group_ids
            ORDER BY c.created_at DESC
            """
            params = {"type": composite_type}
        else:
            query = """
            MATCH (c:CompositeGroup)
            OPTIONAL MATCH (c)-[:CONTAINS]->(dg:DocumentGroup)
            RETURN c.uuid as uuid, c.name as name, c.type as type,
                   c.description as description, c.created_at as created_at,
                   c.updated_at as updated_at,
                   collect(DISTINCT dg.group_id) as group_ids
            ORDER BY c.created_at DESC
            """
            params = {}
        
        result = neo4j_client.execute_query(query, params)
        
        composites = []
        for data in result:
            composites.append({
                "uuid": data.get("uuid"),
                "name": data.get("name"),
                "type": data.get("type"),
                "description": data.get("description"),
                "group_ids": data.get("group_ids", []),
                "created_at": data.get("created_at").isoformat() if data.get("created_at") and hasattr(data.get("created_at"), "isoformat") else str(data.get("created_at", "")),
                "updated_at": data.get("updated_at").isoformat() if data.get("updated_at") and hasattr(data.get("updated_at"), "isoformat") else str(data.get("updated_at", ""))
            })
        
        return composites
    
    @staticmethod
    def update_composite(
        composite_uuid: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        group_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """更新组合"""
        # 更新基本信息
        update_fields = []
        params = {"uuid": composite_uuid, "updated_at": datetime.now()}
        
        if name:
            update_fields.append("c.name = $name")
            params["name"] = name
        
        if description is not None:
            update_fields.append("c.description = $description")
            params["description"] = description
        
        if update_fields:
            update_query = f"""
            MATCH (c:CompositeGroup {{uuid: $uuid}})
            SET {', '.join(update_fields)}, c.updated_at = $updated_at
            RETURN c
            """
            neo4j_client.execute_write(update_query, params)
        
        # 更新GroupID关联
        if group_ids is not None:
            # 删除旧关联
            delete_query = """
            MATCH (c:CompositeGroup {uuid: $uuid})-[r:CONTAINS]->(dg:DocumentGroup)
            DELETE r
            """
            neo4j_client.execute_write(delete_query, {"uuid": composite_uuid})
            
            # 创建新关联
            CompositeService._link_group_ids(composite_uuid, group_ids)
        
        # 返回更新后的组合信息
        return CompositeService.get_composite(composite_uuid)
    
    @staticmethod
    def delete_composite(composite_uuid: str) -> bool:
        """删除组合"""
        # 删除关联关系
        delete_relations_query = """
        MATCH (c:CompositeGroup {uuid: $uuid})-[r:CONTAINS]->(dg:DocumentGroup)
        DELETE r
        """
        neo4j_client.execute_write(delete_relations_query, {"uuid": composite_uuid})
        
        # 删除组合节点
        delete_query = """
        MATCH (c:CompositeGroup {uuid: $uuid})
        DELETE c
        RETURN c
        """
        result = neo4j_client.execute_write(delete_query, {"uuid": composite_uuid})
        
        return len(result) > 0
    
    @staticmethod
    def get_composite_graph(composite_uuid: str, limit: int = 2000) -> Dict[str, Any]:
        """
        获取组合的图谱数据（合并所有关联GroupID的数据）
        
        Args:
            composite_uuid: 组合UUID
            limit: 返回节点数量限制
        
        Returns:
            包含nodes和edges的字典，每个节点/关系都标记了source_group_id
        """
        # 获取组合关联的GroupID列表
        composite = CompositeService.get_composite(composite_uuid)
        if not composite:
            raise ValueError(f"组合不存在: {composite_uuid}")
        
        group_ids = composite.get("group_ids", [])
        if not group_ids:
            return {"nodes": [], "edges": [], "composite": composite}
        
        # 查询每个GroupID的图谱数据
        all_nodes = []
        all_edges = []
        node_id_map = {}  # 用于去重和映射
        
        for group_id in group_ids:
            # 查询该GroupID的所有节点和关系
            query = """
            // 第一步：找到该文档的所有Episode
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            WITH collect(e) as episodes, collect(e.uuid) as episode_uuids
            
            // 第二步：查询这些Episode相关的实体（通过group_id）
            MATCH (n:Entity)
            WHERE n.group_id = $group_id
            WITH collect(DISTINCT n) as entities, episodes, episode_uuids
            
            // 第三步：合并Episode节点和Entity节点
            WITH entities + episodes as all_nodes, episode_uuids
            
            // 第四步：查询这些节点之间的关系
            MATCH (a)-[r:RELATES_TO|MENTIONS]->(b)
            WHERE (r.group_id = $group_id OR r.episode_uuid IN episode_uuids)
              AND a IN all_nodes 
              AND b IN all_nodes
            
            WITH all_nodes, collect(DISTINCT r) as relations
            
            RETURN 
              [node IN all_nodes | {
                id: id(node),
                labels: labels(node),
                properties: properties(node),
                content: node.content
              }] as nodes,
              [rel IN relations | {
                id: id(rel),
                source: id(startNode(rel)),
                target: id(endNode(rel)),
                type: type(rel),
                properties: properties(rel)
              }] as edges
            """
            
            result = neo4j_client.execute_query(query, {"group_id": group_id, "limit": limit})
            
            if result:
                data = result[0]
                
                # 处理节点，标记来源
                for node_data in data.get("nodes", []):
                    if node_data.get("id") is not None:
                        node_id = str(node_data["id"])
                        props = node_data.get("properties", {})
                        
                        # 使用节点ID作为唯一标识，如果已存在则合并来源信息
                        if node_id in node_id_map:
                            # 节点已存在，添加来源信息
                            existing_node = node_id_map[node_id]
                            if group_id not in existing_node.get("source_group_ids", []):
                                existing_node["source_group_ids"].append(group_id)
                        else:
                            # 新节点
                            node = {
                                "id": node_id,
                                "labels": node_data.get("labels", []),
                                "name": props.get("name", ""),
                                "type": node_data.get("labels", ["Entity"])[0] if node_data.get("labels") else "Entity",
                                "properties": serialize_neo4j_properties(props),
                                "content": node_data.get("content"),
                                "source_group_id": group_id,  # 主要来源
                                "source_group_ids": [group_id]  # 所有来源列表
                            }
                            node_id_map[node_id] = node
                            all_nodes.append(node)
                
                # 处理边，标记来源
                for edge_data in data.get("edges", []):
                    if edge_data.get("id") is not None and edge_data.get("source") is not None:
                        source_id = str(edge_data["source"])
                        target_id = str(edge_data["target"])
                        
                        # 确保source和target节点都存在
                        if source_id in node_id_map and target_id in node_id_map:
                            edge = {
                                "id": str(edge_data["id"]),
                                "source": source_id,
                                "target": target_id,
                                "type": edge_data.get("type", ""),
                                "properties": serialize_neo4j_properties(edge_data.get("properties", {})),
                                "source_group_id": group_id  # 标记来源
                            }
                            all_edges.append(edge)
        
        return {
            "nodes": all_nodes,
            "edges": all_edges,
            "composite": composite,
            "statistics": {
                "total_nodes": len(all_nodes),
                "total_edges": len(all_edges),
                "group_ids": group_ids,
                "by_group_id": {
                    group_id: {
                        "nodes": len([n for n in all_nodes if group_id in n.get("source_group_ids", [])]),
                        "edges": len([e for e in all_edges if e.get("source_group_id") == group_id])
                    }
                    for group_id in group_ids
                }
            }
        }

