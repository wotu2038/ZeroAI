from neo4j import GraphDatabase
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,  # 1小时
            max_connection_pool_size=50,
            connection_acquisition_timeout=60
        )
    
    def close(self):
        self.driver.close()
    
    def get_session(self):
        return self.driver.session()
    
    def _verify_connectivity(self):
        """验证连接是否健康"""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning(f"Neo4j连接验证失败: {e}")
            return False
    
    def execute_query(self, query: str, parameters: dict = None, retry_count: int = 3):
        """执行Cypher查询，带重试机制"""
        last_error = None
        for attempt in range(retry_count):
            try:
                # 如果连接不健康，尝试重新连接
                if attempt > 0:
                    if not self._verify_connectivity():
                        logger.warning(f"Neo4j连接不健康，等待后重试... (尝试 {attempt + 1}/{retry_count})")
                        time.sleep(1)  # 等待1秒后重试
                
                with self.get_session() as session:
                    result = session.run(query, parameters or {})
                    records = [record.data() for record in result]
                    return records
            except Exception as e:
                last_error = e
                logger.warning(f"Neo4j查询失败 (尝试 {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(1)  # 等待后重试
                else:
                    logger.error(f"Neo4j查询最终失败: {e}")
                    raise
    
    def execute_write(self, query: str, parameters: dict = None, retry_count: int = 3):
        """执行写操作，带重试机制"""
        last_error = None
        for attempt in range(retry_count):
            try:
                # 如果连接不健康，尝试重新连接
                if attempt > 0:
                    if not self._verify_connectivity():
                        logger.warning(f"Neo4j连接不健康，等待后重试... (尝试 {attempt + 1}/{retry_count})")
                        time.sleep(1)  # 等待1秒后重试
                
                with self.get_session() as session:
                    result = session.run(query, parameters or {})
                    return result.consume().counters
            except Exception as e:
                last_error = e
                logger.warning(f"Neo4j写操作失败 (尝试 {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(1)  # 等待后重试
                else:
                    logger.error(f"Neo4j写操作最终失败: {e}")
                    raise


# 全局Neo4j客户端实例
neo4j_client = Neo4jClient()

