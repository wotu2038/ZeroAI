"""
知识管理API
支持Community、Episode、关系、实体的查询、删除等操作
"""
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties, serialize_neo4j_value
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识管理"])


# ========== 请求/响应模型 ==========
class KnowledgeListRequest(BaseModel):
    """知识列表查询请求"""
    page: int = 1
    page_size: int = 20
    search: Optional[str] = None  # 搜索关键词
    group_id: Optional[str] = None  # 按文档筛选
    start_date: Optional[str] = None  # 开始日期
    end_date: Optional[str] = None  # 结束日期
    type: Optional[str] = None  # 实体类型（仅用于Entity）


class KnowledgeListResponse(BaseModel):
    """知识列表响应"""
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class DeleteKnowledgeRequest(BaseModel):
    """删除知识请求"""
    uuids: List[str]  # 要删除的UUID列表


# ========== Community管理 ==========
@router.get("/communities", response_model=KnowledgeListResponse)
async def list_communities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """查询Community列表"""
    try:
        skip = (page - 1) * page_size
        
        # 构建查询条件
        where_conditions = []
        params = {"skip": skip, "limit": page_size}
        
        if search:
            where_conditions.append("(c.name CONTAINS $search OR c.summary CONTAINS $search)")
            params["search"] = search
        
        if group_id:
            where_conditions.append("(c.group_id = $group_id OR toString(c.group_id) CONTAINS $group_id)")
            params["group_id"] = group_id
        
        if start_date:
            where_conditions.append("c.created_at >= datetime($start_date)")
            params["start_date"] = start_date
        
        if end_date:
            where_conditions.append("c.created_at <= datetime($end_date)")
            params["end_date"] = end_date
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 查询总数
        count_query = f"""
        MATCH (c:Community)
        WHERE {where_clause}
        RETURN count(c) as total
        """
        count_result = neo4j_client.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0
        
        logger.info(f"Community查询总数: {total}, 条件: {where_clause}, 参数: {params}")
        
        # 查询列表
        list_query = f"""
        MATCH (c:Community)
        WHERE {where_clause}
        OPTIONAL MATCH (c)-[:HAS_MEMBER]->(e:Entity)
        WITH c, count(DISTINCT e) as member_count, collect(DISTINCT e.name)[0..20] as member_names
        RETURN c.uuid as uuid, 
               c.name as name, 
               c.summary as summary,
               c.group_id as group_id,
               c.created_at as created_at,
               member_count,
               member_names,
               properties(c) as properties
        ORDER BY c.created_at DESC
        SKIP $skip
        LIMIT $limit
        """
        
        result = neo4j_client.execute_query(list_query, params)
        
        items = []
        for record in result:
            item = {
                "uuid": record.get("uuid"),
                "name": record.get("name", ""),
                "summary": record.get("summary", ""),
                "group_id": serialize_neo4j_value(record.get("group_id")),
                "created_at": serialize_neo4j_value(record.get("created_at")),
                "member_count": record.get("member_count", 0),
                "member_names": record.get("member_names", []),
                "properties": serialize_neo4j_properties(record.get("properties", {}))
            }
            items.append(item)
        
        return KnowledgeListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"查询Community列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.delete("/communities", response_model=Dict[str, Any])
async def delete_communities(request: DeleteKnowledgeRequest = Body(...)):
    """批量删除Community"""
    try:
        if not request.uuids:
            raise HTTPException(status_code=400, detail="UUID列表不能为空")
        
        # 删除Community及其关系
        delete_query = """
        MATCH (c:Community)
        WHERE c.uuid IN $uuids
        OPTIONAL MATCH (c)-[r]->()
        DELETE r, c
        RETURN count(c) as deleted_count
        """
        
        result = neo4j_client.execute_write(delete_query, {"uuids": request.uuids})
        deleted_count = result[0]["deleted_count"] if result else 0
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"成功删除 {deleted_count} 个Community"
        }
    except Exception as e:
        logger.error(f"删除Community失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== Episode管理 ==========
@router.get("/episodes", response_model=KnowledgeListResponse)
async def list_episodes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    source_description: Optional[str] = Query(None)
):
    """查询Episode列表"""
    try:
        skip = (page - 1) * page_size
        
        # 构建查询条件
        where_conditions = []
        params = {"skip": skip, "limit": page_size}
        
        if search:
            where_conditions.append("(e.name CONTAINS $search OR e.content CONTAINS $search)")
            params["search"] = search
        
        if group_id:
            where_conditions.append("e.group_id = $group_id")
            params["group_id"] = group_id
        
        if start_date:
            where_conditions.append("e.created_at >= datetime($start_date)")
            params["start_date"] = start_date
        
        if end_date:
            where_conditions.append("e.created_at <= datetime($end_date)")
            params["end_date"] = end_date
        
        if source_description:
            where_conditions.append("e.source_description = $source_description")
            params["source_description"] = source_description
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 查询总数
        count_query = f"""
        MATCH (e:Episodic)
        WHERE {where_clause}
        RETURN count(e) as total
        """
        count_result = neo4j_client.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0
        
        # 查询列表
        list_query = f"""
        MATCH (e:Episodic)
        WHERE {where_clause}
        RETURN e.uuid as uuid,
               e.name as name,
               e.content as content,
               e.source_description as source_description,
               e.group_id as group_id,
               e.created_at as created_at,
               properties(e) as properties
        ORDER BY e.created_at DESC
        SKIP $skip
        LIMIT $limit
        """
        
        result = neo4j_client.execute_query(list_query, params)
        
        items = []
        for record in result:
            content = record.get("content", "")
            content_preview = content[:200] + "..." if len(content) > 200 else content
            
            item = {
                "uuid": record.get("uuid"),
                "name": record.get("name", ""),
                "content": content,
                "content_preview": content_preview,
                "source_description": record.get("source_description", ""),
                "group_id": serialize_neo4j_value(record.get("group_id")),
                "created_at": serialize_neo4j_value(record.get("created_at")),
                "properties": serialize_neo4j_properties(record.get("properties", {}))
            }
            items.append(item)
        
        return KnowledgeListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"查询Episode列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.delete("/episodes", response_model=Dict[str, Any])
async def delete_episodes(request: DeleteKnowledgeRequest = Body(...)):
    """批量删除Episode"""
    try:
        if not request.uuids:
            raise HTTPException(status_code=400, detail="UUID列表不能为空")
        
        # 删除Episode及其关系
        delete_query = """
        MATCH (e:Episodic)
        WHERE e.uuid IN $uuids
        OPTIONAL MATCH (e)-[r]-()
        DELETE r, e
        RETURN count(e) as deleted_count
        """
        
        result = neo4j_client.execute_write(delete_query, {"uuids": request.uuids})
        deleted_count = result[0]["deleted_count"] if result else 0
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"成功删除 {deleted_count} 个Episode"
        }
    except Exception as e:
        logger.error(f"删除Episode失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== 关系管理 ==========
@router.get("/edges", response_model=KnowledgeListResponse)
async def list_edges(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    rel_type: Optional[str] = Query(None)
):
    """查询关系列表"""
    try:
        skip = (page - 1) * page_size
        
        # 构建查询条件
        where_conditions = []
        params = {"skip": skip, "limit": page_size}
        
        if search:
            where_conditions.append("(r.name CONTAINS $search OR r.fact CONTAINS $search)")
            params["search"] = search
        
        if group_id:
            where_conditions.append("r.group_id = $group_id")
            params["group_id"] = group_id
        
        if start_date:
            where_conditions.append("r.created_at >= datetime($start_date)")
            params["start_date"] = start_date
        
        if end_date:
            where_conditions.append("r.created_at <= datetime($end_date)")
            params["end_date"] = end_date
        
        if rel_type:
            where_conditions.append("type(r) = $rel_type")
            params["rel_type"] = rel_type
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 查询总数
        count_query = f"""
        MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
        WHERE {where_clause}
        RETURN count(r) as total
        """
        count_result = neo4j_client.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0
        
        # 查询列表
        list_query = f"""
        MATCH (a)-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->(b)
        WHERE {where_clause}
        RETURN r.uuid as uuid,
               type(r) as rel_type,
               r.name as name,
               r.fact as fact,
               r.group_id as group_id,
               r.created_at as created_at,
               id(a) as source_id,
               id(b) as target_id,
               labels(a) as source_labels,
               labels(b) as target_labels,
               a.name as source_name,
               b.name as target_name,
               properties(r) as properties
        ORDER BY r.created_at DESC
        SKIP $skip
        LIMIT $limit
        """
        
        result = neo4j_client.execute_query(list_query, params)
        
        items = []
        for record in result:
            item = {
                "uuid": record.get("uuid"),
                "rel_type": record.get("rel_type", ""),
                "name": record.get("name", ""),
                "fact": record.get("fact", ""),
                "group_id": serialize_neo4j_value(record.get("group_id")),
                "created_at": serialize_neo4j_value(record.get("created_at")),
                "source_id": str(record.get("source_id", "")),
                "target_id": str(record.get("target_id", "")),
                "source_labels": record.get("source_labels", []),
                "target_labels": record.get("target_labels", []),
                "source_name": record.get("source_name", ""),
                "target_name": record.get("target_name", ""),
                "properties": serialize_neo4j_properties(record.get("properties", {}))
            }
            items.append(item)
        
        return KnowledgeListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"查询关系列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.delete("/edges", response_model=Dict[str, Any])
async def delete_edges(request: DeleteKnowledgeRequest = Body(...)):
    """批量删除关系"""
    try:
        if not request.uuids:
            raise HTTPException(status_code=400, detail="UUID列表不能为空")
        
        # 删除关系
        delete_query = """
        MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
        WHERE r.uuid IN $uuids
        DELETE r
        RETURN count(r) as deleted_count
        """
        
        result = neo4j_client.execute_write(delete_query, {"uuids": request.uuids})
        deleted_count = result[0]["deleted_count"] if result else 0
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"成功删除 {deleted_count} 个关系"
        }
    except Exception as e:
        logger.error(f"删除关系失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== 实体管理 ==========
@router.get("/entities", response_model=KnowledgeListResponse)
async def list_entities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    type: Optional[str] = Query(None)
):
    """查询实体列表"""
    try:
        skip = (page - 1) * page_size
        
        # 构建查询条件
        where_conditions = []
        params = {"skip": skip, "limit": page_size}
        
        if search:
            where_conditions.append("(n.name CONTAINS $search OR n.summary CONTAINS $search)")
            params["search"] = search
        
        if group_id:
            where_conditions.append("n.group_id = $group_id")
            params["group_id"] = group_id
        
        if start_date:
            where_conditions.append("n.created_at >= datetime($start_date)")
            params["start_date"] = start_date
        
        if end_date:
            where_conditions.append("n.created_at <= datetime($end_date)")
            params["end_date"] = end_date
        
        if type:
            where_conditions.append("$type IN labels(n)")
            params["type"] = type
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 查询总数
        count_query = f"""
        MATCH (n:Entity)
        WHERE {where_clause}
        RETURN count(n) as total
        """
        count_result = neo4j_client.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0
        
        # 查询列表
        list_query = f"""
        MATCH (n:Entity)
        WHERE {where_clause}
        RETURN n.uuid as uuid,
               labels(n) as labels,
               n.name as name,
               n.summary as summary,
               n.group_id as group_id,
               n.created_at as created_at,
               properties(n) as properties
        ORDER BY n.created_at DESC
        SKIP $skip
        LIMIT $limit
        """
        
        result = neo4j_client.execute_query(list_query, params)
        
        items = []
        for record in result:
            item = {
                "uuid": record.get("uuid"),
                "labels": record.get("labels", []),
                "name": record.get("name", ""),
                "summary": record.get("summary", ""),
                "group_id": serialize_neo4j_value(record.get("group_id")),
                "created_at": serialize_neo4j_value(record.get("created_at")),
                "properties": serialize_neo4j_properties(record.get("properties", {}))
            }
            items.append(item)
        
        return KnowledgeListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"查询实体列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.delete("/entities", response_model=Dict[str, Any])
async def delete_entities(request: DeleteKnowledgeRequest = Body(...)):
    """批量删除实体"""
    try:
        if not request.uuids:
            raise HTTPException(status_code=400, detail="UUID列表不能为空")
        
        # 删除实体及其关系
        delete_query = """
        MATCH (n:Entity)
        WHERE n.uuid IN $uuids
        OPTIONAL MATCH (n)-[r]-()
        DELETE r, n
        RETURN count(n) as deleted_count
        """
        
        result = neo4j_client.execute_write(delete_query, {"uuids": request.uuids})
        deleted_count = result[0]["deleted_count"] if result else 0
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"成功删除 {deleted_count} 个实体"
        }
    except Exception as e:
        logger.error(f"删除实体失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== Group管理 ==========
@router.get("/groups", response_model=KnowledgeListResponse)
async def list_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    """查询Group列表（从MySQL获取）"""
    try:
        from app.core.mysql_client import SessionLocal
        from app.models.document_upload import DocumentUpload
        
        skip = (page - 1) * page_size
        db = SessionLocal()
        
        try:
            # 构建查询
            query = db.query(DocumentUpload).filter(
                DocumentUpload.document_id.isnot(None),
                DocumentUpload.document_id != ""
            )
            
            if search:
                query = query.filter(
                    (DocumentUpload.document_id.contains(search)) |
                    (DocumentUpload.file_name.contains(search))
                )
            
            # 查询所有符合条件的文档（不分页，用于过滤有Neo4j数据的）
            all_documents = query.order_by(DocumentUpload.upload_time.desc()).all()
            
            # 获取每个Group的统计信息（从Neo4j），并过滤掉没有Neo4j数据的Group
            all_items = []
            for doc in all_documents:
                group_id = doc.document_id
                
                # 查询Neo4j统计信息（分别查询，避免WITH链式查询失败）
                episode_query = """
                MATCH (e:Episodic)
                WHERE e.group_id = $group_id
                RETURN count(e) as count
                """
                episode_result = neo4j_client.execute_query(episode_query, {"group_id": group_id})
                episode_count = episode_result[0]["count"] if episode_result and episode_result[0] else 0
                
                entity_query = """
                MATCH (n:Entity)
                WHERE n.group_id = $group_id
                RETURN count(n) as count
                """
                entity_result = neo4j_client.execute_query(entity_query, {"group_id": group_id})
                entity_count = entity_result[0]["count"] if entity_result and entity_result[0] else 0
                
                edge_query = """
                MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
                WHERE r.group_id = $group_id
                RETURN count(r) as count
                """
                edge_result = neo4j_client.execute_query(edge_query, {"group_id": group_id})
                edge_count = edge_result[0]["count"] if edge_result and edge_result[0] else 0
                
                community_query = """
                MATCH (c:Community)
                WHERE (c.group_id = $group_id OR 
                       (c.group_id IS NOT NULL AND 
                        (toString(c.group_id) CONTAINS $group_id OR 
                         $group_id IN c.group_id)))
                RETURN count(c) as count
                """
                community_result = neo4j_client.execute_query(community_query, {"group_id": group_id})
                community_count = community_result[0]["count"] if community_result and community_result[0] else 0
                
                # 使用统计结果
                stats = {
                    "episode_count": episode_count,
                    "entity_count": entity_count,
                    "edge_count": edge_count,
                    "community_count": community_count
                }
                
                
                # 只添加有Neo4j数据的Group（至少有一个统计信息不为0）
                if episode_count > 0 or entity_count > 0 or edge_count > 0 or community_count > 0:
                    all_items.append({
                        "group_id": group_id,
                        "file_name": doc.file_name,
                        "upload_time": serialize_neo4j_value(doc.upload_time),
                        "status": doc.status,
                        "episode_count": episode_count,
                        "entity_count": entity_count,
                        "edge_count": edge_count,
                        "community_count": community_count
                    })
            
            # 计算总数（过滤后的数量）
            total = len(all_items)
            
            # 分页处理
            items = all_items[skip:skip + page_size]
            
            return KnowledgeListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"查询Group列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/groups/{group_id}/detail", response_model=Dict[str, Any])
async def get_group_detail(group_id: str):
    """获取Group详情（包含该Group下的所有数据概览）"""
    try:
        from app.core.mysql_client import SessionLocal
        from app.models.document_upload import DocumentUpload
        
        db = SessionLocal()
        try:
            # 从MySQL获取文档信息
            document = db.query(DocumentUpload).filter(
                DocumentUpload.document_id == group_id
            ).first()
            
            document_info = None
            if document:
                document_info = {
                    "id": document.id,
                    "file_name": document.file_name,
                    "file_size": document.file_size,
                    "upload_time": serialize_neo4j_value(document.upload_time),
                    "status": document.status
                }
            
            # 从Neo4j获取统计信息
            stats_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            WITH count(e) as episode_count, collect(e.uuid)[0..10] as episode_uuids
            
            MATCH (n:Entity)
            WHERE n.group_id = $group_id
            WITH episode_count, episode_uuids, count(n) as entity_count, collect(n.uuid)[0..10] as entity_uuids
            
            MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
            WHERE r.group_id = $group_id
            WITH episode_count, episode_uuids, entity_count, entity_uuids, count(r) as edge_count, collect(r.uuid)[0..10] as edge_uuids
            
            MATCH (c:Community)
            WHERE (c.group_id = $group_id OR 
                   (c.group_id IS NOT NULL AND 
                    (toString(c.group_id) CONTAINS $group_id OR 
                     $group_id IN c.group_id)))
            WITH episode_count, episode_uuids, entity_count, entity_uuids, edge_count, edge_uuids, count(c) as community_count, collect(c.uuid)[0..10] as community_uuids
            
            RETURN episode_count, episode_uuids, entity_count, entity_uuids, edge_count, edge_uuids, community_count, community_uuids
            """
            
            stats_result = neo4j_client.execute_query(stats_query, {"group_id": group_id})
            stats = stats_result[0] if stats_result else {
                "episode_count": 0,
                "episode_uuids": [],
                "entity_count": 0,
                "entity_uuids": [],
                "edge_count": 0,
                "edge_uuids": [],
                "community_count": 0,
                "community_uuids": []
            }
            
            return {
                "group_id": group_id,
                "document_info": document_info,
                "statistics": {
                    "episode_count": stats.get("episode_count", 0),
                    "entity_count": stats.get("entity_count", 0),
                    "edge_count": stats.get("edge_count", 0),
                    "community_count": stats.get("community_count", 0)
                },
                "sample_uuids": {
                    "episodes": stats.get("episode_uuids", []),
                    "entities": stats.get("entity_uuids", []),
                    "edges": stats.get("edge_uuids", []),
                    "communities": stats.get("community_uuids", [])
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"获取Group详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.delete("/groups/{group_id}", response_model=Dict[str, Any])
async def delete_group(group_id: str):
    """删除Group（删除该Group下的所有数据）"""
    try:
        from app.core.mysql_client import SessionLocal
        from app.models.document_upload import DocumentUpload
        
        db = SessionLocal()
        try:
            # 检查MySQL中是否有对应的文档记录
            document = db.query(DocumentUpload).filter(
                DocumentUpload.document_id == group_id
            ).first()
            
            # 删除Neo4j中该Group下的所有数据
            # 先统计数量，再执行删除
            
            # 1. 统计并删除关系
            count_edges_query = """
            MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
            WHERE r.group_id = $group_id
            RETURN count(r) as count
            """
            count_result = neo4j_client.execute_query(count_edges_query, {"group_id": group_id})
            deleted_edges = count_result[0]["count"] if count_result else 0
            
            delete_edges_query = """
            MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
            WHERE r.group_id = $group_id
            DELETE r
            """
            neo4j_client.execute_write(delete_edges_query, {"group_id": group_id})
            
            # 2. 统计并删除Entity
            count_entities_query = """
            MATCH (n:Entity)
            WHERE n.group_id = $group_id
            RETURN count(n) as count
            """
            count_result = neo4j_client.execute_query(count_entities_query, {"group_id": group_id})
            deleted_entities = count_result[0]["count"] if count_result else 0
            
            delete_entities_query = """
            MATCH (n:Entity)
            WHERE n.group_id = $group_id
            DELETE n
            """
            neo4j_client.execute_write(delete_entities_query, {"group_id": group_id})
            
            # 3. 统计并删除Episode
            count_episodes_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            RETURN count(e) as count
            """
            count_result = neo4j_client.execute_query(count_episodes_query, {"group_id": group_id})
            deleted_episodes = count_result[0]["count"] if count_result else 0
            
            delete_episodes_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            DELETE e
            """
            neo4j_client.execute_write(delete_episodes_query, {"group_id": group_id})
            
            # 4. 统计并删除Community（如果group_id匹配）
            count_communities_query = """
            MATCH (c:Community)
            WHERE (c.group_id = $group_id OR 
                   (c.group_id IS NOT NULL AND 
                    (toString(c.group_id) CONTAINS $group_id OR 
                     $group_id IN c.group_id)))
            RETURN count(c) as count
            """
            count_result = neo4j_client.execute_query(count_communities_query, {"group_id": group_id})
            deleted_communities = count_result[0]["count"] if count_result else 0
            
            delete_communities_query = """
            MATCH (c:Community)
            WHERE (c.group_id = $group_id OR 
                   (c.group_id IS NOT NULL AND 
                    (toString(c.group_id) CONTAINS $group_id OR 
                     $group_id IN c.group_id)))
            DELETE c
            """
            neo4j_client.execute_write(delete_communities_query, {"group_id": group_id})
            
            # 5. 清空DocumentUpload记录中的document_id字段（保留记录，但清空Group ID关联）
            # 这样文档仍会出现在"文档管理"列表中，但不会出现在"知识管理"的Group列表中
            # （因为document_id已被清空，且Neo4j数据已删除）
            if document:
                try:
                    document.document_id = None
                    db.commit()
                    logger.info(f"已删除Neo4j数据，并清空DocumentUpload的document_id字段: {group_id}")
                except Exception as mysql_error:
                    db.rollback()
                    logger.warning(f"清空document_id字段失败: {mysql_error}，但Neo4j数据已删除")
            
            return {
                "success": True,
                "group_id": group_id,
                "deleted_counts": {
                    "episodes": deleted_episodes,
                    "entities": deleted_entities,
                    "edges": deleted_edges,
                    "communities": deleted_communities
                },
                "message": f"成功删除Group {group_id} 下的所有数据"
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"删除Group失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== 获取所有文档列表（用于综合管理） ==========
@router.get("/documents", response_model=List[Dict[str, str]])
async def list_documents():
    """获取所有文档的Group ID列表"""
    try:
        query = """
        MATCH (n)
        WHERE n.group_id IS NOT NULL
        WITH DISTINCT n.group_id as group_id
        ORDER BY group_id
        RETURN group_id
        """
        
        result = neo4j_client.execute_query(query)
        
        documents = []
        for record in result:
            group_id = serialize_neo4j_value(record.get("group_id"))
            if group_id:
                documents.append({"group_id": group_id})
        
        return documents
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

