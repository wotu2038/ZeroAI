"""
初始化 Cognee Neo4j 配置

在服务启动时设置所有 Neo4j 环境变量，确保在导入 Cognee 之前环境变量已经设置好。
这是解决 Cognee 无法创建 Neo4j 节点的关键。
"""
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def init_cognee_neo4j_config():
    """
    初始化 Cognee Neo4j 环境变量
    
    必须在导入 Cognee 之前调用此函数。
    参考 test_cognee_full_flow.py 的成功经验。
    
    Returns:
        bool: 是否成功设置
    """
    try:
        # 设置 Neo4j 图数据库环境变量（在导入 Cognee 之前）
        # 根据 Cognee 官方文档，这些环境变量必须在导入前设置
        # 注意：使用自托管 Neo4j 时，需要禁用多用户访问控制（ENABLE_BACKEND_ACCESS_CONTROL=false）
        os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
        os.environ["GRAPH_DATABASE_PROVIDER"] = "neo4j"
        os.environ["GRAPH_DATABASE_URL"] = settings.NEO4J_URI
        os.environ["GRAPH_DATABASE_NAME"] = "neo4j"
        os.environ["GRAPH_DATABASE_USERNAME"] = settings.NEO4J_USER
        os.environ["GRAPH_DATABASE_PASSWORD"] = settings.NEO4J_PASSWORD
        # 同时设置 NEO4J_* 环境变量（Cognee 可能也需要这些）
        os.environ["NEO4J_URI"] = settings.NEO4J_URI
        os.environ["NEO4J_USERNAME"] = settings.NEO4J_USER
        os.environ["NEO4J_PASSWORD"] = settings.NEO4J_PASSWORD
        # 设置 COGNEE_* 环境变量（Cognee 可能也需要这些）
        os.environ["COGNEE_GRAPH_DB_PROVIDER"] = "neo4j"
        os.environ["COGNEE_GRAPH_DB_NAME"] = "neo4j"
        
        logger.info(
            f"✅ Neo4j 环境变量已设置: "
            f"GRAPH_DATABASE_PROVIDER={os.environ.get('GRAPH_DATABASE_PROVIDER')}, "
            f"GRAPH_DATABASE_URL={os.environ.get('GRAPH_DATABASE_URL')}, "
            f"NEO4J_USERNAME={os.environ.get('NEO4J_USERNAME')}"
        )
        
        return True
    except Exception as e:
        logger.error(f"❌ Neo4j 环境变量设置失败: {e}", exc_info=True)
        return False

