from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    GraphData, GraphNode, GraphEdge, GraphQuery,
    PathQueryRequest, PathQueryResponse
)
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties
from app.services.graphiti_service import GraphitiService
from app.services.path_service import PathService

router = APIRouter()


@router.get("/data", response_model=GraphData)
async def get_graph_data(limit: int = 100):
    """获取图数据（用于可视化）"""
    query = """
    MATCH (n)
    OPTIONAL MATCH (n)-[r]->(m)
    WITH n, r, m
    LIMIT $limit
    RETURN collect(DISTINCT {
        id: id(n),
        labels: labels(n),
        properties: properties(n)
    }) as nodes,
    collect(DISTINCT {
        id: id(r),
        source: id(startNode(r)),
        target: id(endNode(r)),
        type: type(r),
        properties: properties(r)
    }) as edges
    """
    
    result = neo4j_client.execute_query(query, {"limit": limit})
    
    if not result:
        return GraphData(nodes=[], edges=[])
    
    data = result[0]
    
    # 处理节点
    nodes_dict = {}
    for node_data in data.get("nodes", []):
        if node_data.get("id") is not None:
            node_id = str(node_data["id"])
            nodes_dict[node_id] = GraphNode(
                id=node_id,
                labels=node_data.get("labels", []),
                properties=serialize_neo4j_properties(node_data.get("properties", {}))
            )
    
    # 处理边
    edges = []
    for edge_data in data.get("edges", []):
        if edge_data.get("id") is not None and edge_data.get("source") is not None:
            edges.append(GraphEdge(
                id=str(edge_data["id"]),
                source=str(edge_data["source"]),
                target=str(edge_data["target"]),
                type=edge_data.get("type", ""),
                properties=serialize_neo4j_properties(edge_data.get("properties", {}))
            ))
    
    return GraphData(nodes=list(nodes_dict.values()), edges=edges)


@router.post("/query", response_model=dict)
async def execute_graph_query(query: GraphQuery):
    """执行Cypher查询"""
    try:
        result = neo4j_client.execute_query(query.query)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查询执行失败: {str(e)}")


@router.get("/stats", response_model=dict)
async def get_graph_stats():
    """获取图统计信息"""
    node_count_query = "MATCH (n) RETURN count(n) as count"
    rel_count_query = "MATCH ()-[r]->() RETURN count(r) as count"
    
    node_result = neo4j_client.execute_query(node_count_query)
    rel_result = neo4j_client.execute_query(rel_count_query)
    
    node_count = node_result[0]["count"] if node_result else 0
    rel_count = rel_result[0]["count"] if rel_result else 0
    
    # 获取实体类型统计
    type_query = """
    MATCH (n)
    WHERE labels(n) <> []
    RETURN labels(n)[0] as type, count(n) as count
    ORDER BY count DESC
    """
    type_result = neo4j_client.execute_query(type_query)
    entity_types = {item["type"]: item["count"] for item in type_result}
    
    # 获取关系类型统计
    rel_type_query = """
    MATCH ()-[r]->()
    RETURN type(r) as type, count(r) as count
    ORDER BY count DESC
    """
    rel_type_result = neo4j_client.execute_query(rel_type_query)
    relationship_types = {item["type"]: item["count"] for item in rel_type_result}
    
    return {
        "node_count": node_count,
        "relationship_count": rel_count,
        "entity_types": entity_types,
        "relationship_types": relationship_types
    }


@router.post("/retrieve", response_model=dict)
async def retrieve_graph(
    query: str = Query(..., description="检索查询文本"),
    provider: str = Query("qianwen", description="LLM提供商"),
    limit: int = Query(10, ge=1, le=100, description="返回结果数量")
):
    """使用Graphiti进行语义检索"""
    try:
        results = await GraphitiService.retrieve(
            query=query,
            provider=provider,
            limit=limit
        )
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


@router.post("/retrieve-body", response_model=dict)
async def retrieve_graph_body(request: dict):
    """使用Graphiti进行语义检索（POST body方式）"""
    try:
        query = request.get("query", "")
        provider = request.get("provider", "qianwen")
        limit = request.get("limit", 10)
        
        if not query:
            raise HTTPException(status_code=400, detail="查询文本不能为空")
        
        results = await GraphitiService.retrieve(
            query=query,
            provider=provider,
            limit=limit
        )
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


@router.post("/find-paths", response_model=PathQueryResponse)
async def find_paths(request: PathQueryRequest):
    """
    查找关系路径
    
    支持两种模式：
    1. 两个实体之间：提供 source 和 target
    2. 单个实体的所有关系链：只提供 source，不提供 target
    """
    try:
        if request.target:
            # 模式1：查找两个实体之间的路径
            paths = PathService.find_paths_between_entities(
                source_name=request.source,
                target_name=request.target,
                max_depth=request.max_depth,
                limit=request.limit
            )
            target = request.target
        else:
            # 模式2：查找单个实体的所有关系链
            paths = PathService.find_entity_relationship_chains(
                entity_name=request.source,
                max_depth=request.max_depth,
                limit=request.limit
            )
            target = None
        
        # 计算最短路径长度
        shortest_length = None
        if paths:
            shortest_paths = [p for p in paths if p.is_shortest]
            if shortest_paths:
                shortest_length = shortest_paths[0].length
        
        return PathQueryResponse(
            source=request.source,
            target=target,
            paths=paths,
            total_paths=len(paths),
            shortest_length=shortest_length
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"查找路径失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查找路径失败: {str(e)}")

