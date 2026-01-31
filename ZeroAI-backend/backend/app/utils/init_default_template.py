"""
初始化默认模板脚本

在数据库初始化时，如果不存在默认模板，则创建需求文档模板作为默认模板。
"""
import logging
from app.core.mysql_client import SessionLocal
from app.models.template import EntityEdgeTemplate

logger = logging.getLogger(__name__)


def init_default_template():
    """初始化默认模板"""
    db = SessionLocal()
    try:
        # 检查是否已存在默认模板
        existing_default = db.query(EntityEdgeTemplate).filter(
            EntityEdgeTemplate.is_default == True
        ).first()
        
        if existing_default:
            logger.info(f"默认模板已存在: {existing_default.name} (ID: {existing_default.id})")
            return
        
        # 创建默认需求文档模板
        default_template = EntityEdgeTemplate(
            name="需求文档模板",
            description="适用于需求文档，提取需求、功能点、模块",
            category="requirement",
            entity_types={
                "Requirement": {
                    "fields": {
                        "title": {
                            "type": "str",
                            "required": True,
                            "description": "需求名称"
                        },
                        "version": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "版本号"
                        },
                        "description": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "需求描述"
                        },
                        "content": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "需求文档内容"
                        }
                    }
                },
                "Feature": {
                    "fields": {
                        "feature_name": {
                            "type": "str",
                            "required": True,
                            "description": "功能点名称"
                        },
                        "description": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "功能点描述"
                        },
                        "module_name": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "所属模块名称"
                        }
                    }
                },
                "Module": {
                    "fields": {
                        "module_name": {
                            "type": "str",
                            "required": True,
                            "description": "模块名称"
                        },
                        "description": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "模块描述"
                        }
                    }
                }
            },
            edge_types={
                "HAS_FEATURE": {
                    "fields": {
                        "description": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "关系描述"
                        }
                    }
                },
                "BELONGS_TO": {
                    "fields": {
                        "description": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "关系描述"
                        }
                    }
                },
                "HAS_MODULE": {
                    "fields": {
                        "description": {
                            "type": "Optional[str]",
                            "required": False,
                            "description": "关系描述"
                        }
                    }
                }
            },
            edge_type_map={
                "Requirement -> Feature": ["HAS_FEATURE"],
                "Feature -> Module": ["BELONGS_TO"],
                "Requirement -> Module": ["HAS_MODULE"]
            },
            is_default=True,
            is_system=True  # 系统模板，不可删除
        )
        
        db.add(default_template)
        db.commit()
        db.refresh(default_template)
        
        logger.info(f"默认模板创建成功: {default_template.name} (ID: {default_template.id})")
    except Exception as e:
        db.rollback()
        logger.error(f"初始化默认模板失败: {e}", exc_info=True)
    finally:
        db.close()

