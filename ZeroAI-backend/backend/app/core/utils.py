"""通用工具函数"""
from datetime import datetime


def serialize_neo4j_value(value):
    """序列化 Neo4j 值（包括 DateTime 等特殊类型）"""
    if value is None:
        return None
    # 处理 Neo4j DateTime 类型
    if hasattr(value, 'iso_format'):
        # Neo4j DateTime 对象
        return value.iso_format()
    elif hasattr(value, 'to_native'):
        # Neo4j 时间类型，转换为 Python datetime
        return value.to_native().isoformat()
    elif isinstance(value, datetime):
        # Python datetime
        return value.isoformat()
    elif isinstance(value, (list, tuple)):
        # 递归处理列表
        return [serialize_neo4j_value(item) for item in value]
    elif isinstance(value, dict):
        # 递归处理字典
        return {k: serialize_neo4j_value(v) for k, v in value.items()}
    else:
        return value


def serialize_neo4j_properties(properties: dict) -> dict:
    """序列化 Neo4j 属性字典"""
    if not properties:
        return {}
    return {k: serialize_neo4j_value(v) for k, v in properties.items()}

