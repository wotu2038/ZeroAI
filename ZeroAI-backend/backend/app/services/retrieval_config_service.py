"""
检索方案配置服务

管理四种检索方案（A/B/C/D）的配置和参数
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RetrievalSchemeType(Enum):
    """检索方案类型"""
    DEFAULT = "default"      # 方案A: 默认（完整RAG）
    ENHANCED = "enhanced"    # 方案B: 增强（原文截断）
    SMART = "smart"          # 方案C: 智能（分段概括）
    FAST = "fast"            # 方案D: 快速（无重排序）


@dataclass
class SchemeConfig:
    """方案配置"""
    scheme_type: RetrievalSchemeType
    name: str
    description: str
    
    # 检索参数
    top_k: int = 10
    min_score: float = 0.5
    
    # 重排序
    enable_rerank: bool = True
    
    # 方案B特有：截断长度
    truncate_length: int = 500
    
    # 方案C特有：概括长度
    summary_length: int = 200
    
    # 前端展示参数
    adjustable_params: List[str] = field(default_factory=list)


# 方案定义
RETRIEVAL_SCHEMES: Dict[RetrievalSchemeType, SchemeConfig] = {
    RetrievalSchemeType.DEFAULT: SchemeConfig(
        scheme_type=RetrievalSchemeType.DEFAULT,
        name="默认模式",
        description="完整RAG流程，适合大多数场景",
        top_k=10,
        min_score=0.5,
        enable_rerank=True,
        adjustable_params=["top_k"]
    ),
    RetrievalSchemeType.ENHANCED: SchemeConfig(
        scheme_type=RetrievalSchemeType.ENHANCED,
        name="增强模式",
        description="保留更多原文内容，适合需要引用原文的场景",
        top_k=10,
        min_score=0.5,
        enable_rerank=True,
        truncate_length=500,
        adjustable_params=["top_k", "truncate_length"]
    ),
    RetrievalSchemeType.SMART: SchemeConfig(
        scheme_type=RetrievalSchemeType.SMART,
        name="智能模式",
        description="对检索结果进行智能概括，适合信息量大的场景",
        top_k=15,
        min_score=0.5,
        enable_rerank=True,
        summary_length=200,
        adjustable_params=["top_k", "summary_length"]
    ),
    RetrievalSchemeType.FAST: SchemeConfig(
        scheme_type=RetrievalSchemeType.FAST,
        name="快速模式",
        description="跳过重排序，最快速度返回结果",
        top_k=10,
        min_score=0.5,
        enable_rerank=False,
        adjustable_params=["top_k", "min_score"]
    ),
}


class RetrievalConfigService:
    """
    检索方案配置服务
    
    管理检索方案的配置和用户偏好
    """
    
    @staticmethod
    def get_all_schemes() -> List[Dict[str, Any]]:
        """
        获取所有检索方案（用于前端展示）
        
        Returns:
            方案列表
        """
        schemes = []
        for scheme_type, config in RETRIEVAL_SCHEMES.items():
            schemes.append({
                "id": scheme_type.value,
                "name": config.name,
                "description": config.description,
                "params": {
                    "top_k": {
                        "label": "返回数量",
                        "type": "number",
                        "default": config.top_k,
                        "min": 1,
                        "max": 50
                    },
                    "min_score": {
                        "label": "相似度阈值",
                        "type": "number",
                        "default": config.min_score,
                        "min": 0,
                        "max": 1,
                        "step": 0.1,
                        "visible": "min_score" in config.adjustable_params
                    },
                    "truncate_length": {
                        "label": "截断长度",
                        "type": "number",
                        "default": config.truncate_length,
                        "min": 100,
                        "max": 2000,
                        "visible": scheme_type == RetrievalSchemeType.ENHANCED
                    },
                    "summary_length": {
                        "label": "概括长度",
                        "type": "number",
                        "default": config.summary_length,
                        "min": 50,
                        "max": 500,
                        "visible": scheme_type == RetrievalSchemeType.SMART
                    }
                },
                "features": {
                    "rerank": config.enable_rerank,
                    "vector_search": True,
                    "bm25_search": True,
                    "graph_traverse": True
                }
            })
        
        return schemes
    
    @staticmethod
    def get_scheme_config(
        scheme_id: str,
        custom_params: Dict[str, Any] = None
    ) -> SchemeConfig:
        """
        获取方案配置
        
        Args:
            scheme_id: 方案ID (default, enhanced, smart, fast)
            custom_params: 用户自定义参数
            
        Returns:
            方案配置
        """
        try:
            scheme_type = RetrievalSchemeType(scheme_id)
        except ValueError:
            scheme_type = RetrievalSchemeType.DEFAULT
        
        config = RETRIEVAL_SCHEMES[scheme_type]
        
        # 应用自定义参数
        if custom_params:
            if "top_k" in custom_params:
                config.top_k = max(1, min(50, int(custom_params["top_k"])))
            if "min_score" in custom_params:
                config.min_score = max(0, min(1, float(custom_params["min_score"])))
            if "truncate_length" in custom_params and scheme_type == RetrievalSchemeType.ENHANCED:
                config.truncate_length = max(100, min(2000, int(custom_params["truncate_length"])))
            if "summary_length" in custom_params and scheme_type == RetrievalSchemeType.SMART:
                config.summary_length = max(50, min(500, int(custom_params["summary_length"])))
        
        return config
    
    @staticmethod
    def save_user_preference(
        user_id: int,
        scheme_id: str,
        custom_params: Dict[str, Any] = None
    ) -> bool:
        """
        保存用户偏好
        
        Args:
            user_id: 用户ID
            scheme_id: 方案ID
            custom_params: 自定义参数
            
        Returns:
            是否成功
        """
        from app.core.mysql_client import SessionLocal
        from app.models.user import User
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                # 保存到用户配置（假设User模型有preferences字段）
                preferences = user.preferences or {}
                preferences["retrieval_scheme"] = {
                    "scheme_id": scheme_id,
                    "params": custom_params or {}
                }
                user.preferences = preferences
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"保存用户偏好失败: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    @staticmethod
    def get_user_preference(user_id: int) -> Dict[str, Any]:
        """
        获取用户偏好
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户偏好配置
        """
        from app.core.mysql_client import SessionLocal
        from app.models.user import User
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.preferences:
                return user.preferences.get("retrieval_scheme", {
                    "scheme_id": "default",
                    "params": {}
                })
            return {"scheme_id": "default", "params": {}}
        except Exception as e:
            logger.error(f"获取用户偏好失败: {e}")
            return {"scheme_id": "default", "params": {}}
        finally:
            db.close()
    
    @staticmethod
    def get_popup_config() -> Dict[str, Any]:
        """
        获取设置弹窗配置（用于前端）
        
        Returns:
            弹窗配置
        """
        return {
            "title": "检索设置",
            "description": "选择检索方案并调整参数",
            "schemes": RetrievalConfigService.get_all_schemes(),
            "default_scheme": "default",
            "remember_selection": True,
            "advanced_mode": False
        }

