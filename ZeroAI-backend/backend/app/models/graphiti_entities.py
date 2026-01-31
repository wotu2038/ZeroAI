"""
Graphiti 自定义实体类型定义

定义用于需求文档提取的自定义实体类型和关系类型。
注意：字段名不能与 EntityNode 的保留字段冲突。
保留字段：uuid, name, group_id, labels, created_at, name_embedding, summary, attributes
"""
from pydantic import BaseModel, Field
from typing import Optional


# ==================== 实体类型定义 ====================

class Requirement(BaseModel):
    """需求实体类型
    
    注意：不能使用 'name' 字段（EntityNode 的保留字段）
    使用 'title' 字段代替
    """
    title: str = Field(..., description="需求名称")
    version: Optional[str] = Field(None, description="版本号")
    description: Optional[str] = Field(None, description="需求描述")
    content: Optional[str] = Field(None, description="需求文档内容")


class Feature(BaseModel):
    """功能点实体类型
    
    注意：不能使用 'name' 字段（EntityNode 的保留字段）
    使用 'feature_name' 字段代替
    """
    feature_name: str = Field(..., description="功能点名称")
    description: Optional[str] = Field(None, description="功能点描述")
    module_name: Optional[str] = Field(None, description="所属模块名称")


class Module(BaseModel):
    """模块实体类型
    
    注意：不能使用 'name' 字段（EntityNode 的保留字段）
    使用 'module_name' 字段代替
    """
    module_name: str = Field(..., description="模块名称")
    description: Optional[str] = Field(None, description="模块描述")


# ==================== 关系类型定义 ====================

class HAS_FEATURE(BaseModel):
    """需求 -> 功能点关系"""
    description: Optional[str] = Field(None, description="关系描述")


class BELONGS_TO(BaseModel):
    """功能点 -> 模块关系"""
    description: Optional[str] = Field(None, description="关系描述")


class HAS_MODULE(BaseModel):
    """需求 -> 模块关系"""
    description: Optional[str] = Field(None, description="关系描述")


# ==================== 轻量化实体类型定义（用于步骤4）====================

class RequirementLightweight(BaseModel):
    """需求实体类型（轻量化版本）
    
    只提取需求名称和版本，不提取详细描述和内容
    """
    title: str = Field(..., description="需求名称")
    version: Optional[str] = Field(None, description="版本号")


class System(BaseModel):
    """系统实体类型（轻量化）
    
    只提取系统名称，不提取详细内容
    """
    system_name: str = Field(..., description="系统名称")


class Person(BaseModel):
    """人员实体类型（轻量化）
    
    只提取人员名称和角色，不提取详细信息
    """
    person_name: str = Field(..., description="人员名称")
    role: Optional[str] = Field(None, description="角色/职位")


# ==================== 轻量化关系类型定义（用于步骤4）====================

class DEPENDS_ON(BaseModel):
    """依赖关系（轻量化）
    
    只提取依赖关系类型，不提取详细描述
    """
    pass  # 轻量化设计，不存储详细内容


class RELATES_TO(BaseModel):
    """关联关系（轻量化）
    
    只提取关联关系类型，不提取详细描述
    """
    pass  # 轻量化设计，不存储详细内容


class IMPLEMENTS(BaseModel):
    """实现关系（轻量化）
    
    只提取实现关系类型，不提取详细描述
    """
    pass  # 轻量化设计，不存储详细内容


# ==================== 轻量化实体类型字典 ====================

LIGHTWEIGHT_ENTITY_TYPES = {
    "Requirement": RequirementLightweight,  # 使用轻量化版本
    "System": System,            # 新增：系统实体
    "Module": Module,            # 保留原有的 Module 类型
    "Person": Person             # 新增：人员实体
}


# ==================== 轻量化关系类型字典 ====================

LIGHTWEIGHT_EDGE_TYPES = {
    "DEPENDS_ON": DEPENDS_ON,    # 新增：依赖关系
    "RELATES_TO": RELATES_TO,    # 新增：关联关系
    "IMPLEMENTS": IMPLEMENTS,    # 新增：实现关系
    "HAS_FEATURE": HAS_FEATURE,  # 保留原有的关系类型
    "BELONGS_TO": BELONGS_TO,
    "HAS_MODULE": HAS_MODULE
}


# ==================== 轻量化关系类型映射 ====================

LIGHTWEIGHT_EDGE_TYPE_MAP = {
    ("Requirement", "Requirement"): ["DEPENDS_ON", "RELATES_TO"],  # 需求之间的依赖和关联
    ("Requirement", "System"): ["IMPLEMENTS"],                      # 需求实现系统
    ("Requirement", "Module"): ["HAS_MODULE"],                      # 需求包含模块
    ("System", "System"): ["DEPENDS_ON", "RELATES_TO"],             # 系统之间的依赖和关联
    ("Module", "Module"): ["DEPENDS_ON", "RELATES_TO"],             # 模块之间的依赖和关联
    ("Person", "Requirement"): ["RELATES_TO"],                      # 人员与需求的关联
    ("Person", "System"): ["RELATES_TO"],                            # 人员与系统的关联
    # 保留原有的映射
    ("Requirement", "Feature"): ["HAS_FEATURE"],
    ("Feature", "Module"): ["BELONGS_TO"]
}


# ==================== 实体类型字典 ====================

ENTITY_TYPES = {
    "Requirement": Requirement,
    "Feature": Feature,
    "Module": Module
}


# ==================== 关系类型字典 ====================

EDGE_TYPES = {
    "HAS_FEATURE": HAS_FEATURE,
    "BELONGS_TO": BELONGS_TO,
    "HAS_MODULE": HAS_MODULE
}


# ==================== 关系类型映射 ====================

EDGE_TYPE_MAP = {
    ("Requirement", "Feature"): ["HAS_FEATURE"],
    ("Feature", "Module"): ["BELONGS_TO"],
    ("Requirement", "Module"): ["HAS_MODULE"]
}

