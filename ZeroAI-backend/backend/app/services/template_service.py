"""
模板服务
"""
from typing import Dict, Any, Tuple, List, Type
from pydantic import BaseModel, Field, create_model
import logging

logger = logging.getLogger(__name__)


class TemplateService:
    """模板服务"""
    
    # EntityNode 保留字段
    ENTITY_RESERVED_FIELDS = {
        "uuid", "name", "group_id", "labels", 
        "created_at", "name_embedding", "summary", "attributes"
    }
    
    # EdgeNode 保留字段
    EDGE_RESERVED_FIELDS = {
        "uuid", "source_node_uuid", "target_node_uuid", 
        "name", "fact", "attributes"
    }
    
    @staticmethod
    def validate_template(
        entity_types: Dict[str, Any],
        edge_types: Dict[str, Any],
        edge_type_map: Dict[str, Any]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        校验模板格式
        
        Args:
            entity_types: 实体类型定义
            edge_types: 关系类型定义
            edge_type_map: 关系类型映射
        
        Returns:
            (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # 1. 校验实体类型
        if not entity_types:
            errors.append("实体类型定义不能为空")
        else:
            if not isinstance(entity_types, dict):
                errors.append("实体类型定义必须是字典格式")
            else:
                for entity_name, entity_config in entity_types.items():
                    # 校验实体名称
                    if not entity_name or not isinstance(entity_name, str):
                        errors.append(f"实体类型名称无效: {entity_name}")
                        continue
                    
                    # 校验字段定义
                    if not isinstance(entity_config, dict):
                        errors.append(f"实体类型 '{entity_name}' 的配置必须是字典格式")
                        continue
                    
                    if "fields" not in entity_config:
                        errors.append(f"实体类型 '{entity_name}' 缺少 'fields' 定义")
                        continue
                    
                    fields = entity_config["fields"]
                    if not isinstance(fields, dict):
                        errors.append(f"实体类型 '{entity_name}' 的 'fields' 必须是字典")
                        continue
                    
                    # 检查保留字段冲突
                    for field_name in fields.keys():
                        if field_name in TemplateService.ENTITY_RESERVED_FIELDS:
                            errors.append(
                                f"实体类型 '{entity_name}' 的字段 '{field_name}' 与保留字段冲突。"
                                f"保留字段: {', '.join(TemplateService.ENTITY_RESERVED_FIELDS)}"
                            )
                    
                    # 校验字段定义格式
                    for field_name, field_config in fields.items():
                        if not isinstance(field_config, dict):
                            errors.append(f"实体类型 '{entity_name}' 的字段 '{field_name}' 的配置必须是字典格式")
                            continue
                        
                        if "type" not in field_config:
                            errors.append(f"实体类型 '{entity_name}' 的字段 '{field_name}' 缺少 'type' 定义")
        
        # 2. 校验关系类型
        if not edge_types:
            errors.append("关系类型定义不能为空")
        else:
            if not isinstance(edge_types, dict):
                errors.append("关系类型定义必须是字典格式")
            else:
                for edge_name, edge_config in edge_types.items():
                    # 校验关系名称
                    if not edge_name or not isinstance(edge_name, str):
                        errors.append(f"关系类型名称无效: {edge_name}")
                        continue
                    
                    # 校验字段定义
                    if not isinstance(edge_config, dict):
                        errors.append(f"关系类型 '{edge_name}' 的配置必须是字典格式")
                        continue
                    
                    if "fields" not in edge_config:
                        errors.append(f"关系类型 '{edge_name}' 缺少 'fields' 定义")
                        continue
                    
                    fields = edge_config["fields"]
                    if not isinstance(fields, dict):
                        errors.append(f"关系类型 '{edge_name}' 的 'fields' 必须是字典")
                        continue
                    
                    # 检查保留字段冲突
                    for field_name in fields.keys():
                        if field_name in TemplateService.EDGE_RESERVED_FIELDS:
                            errors.append(
                                f"关系类型 '{edge_name}' 的字段 '{field_name}' 与保留字段冲突。"
                                f"保留字段: {', '.join(TemplateService.EDGE_RESERVED_FIELDS)}"
                            )
                    
                    # 校验字段定义格式
                    for field_name, field_config in fields.items():
                        if not isinstance(field_config, dict):
                            errors.append(f"关系类型 '{edge_name}' 的字段 '{field_name}' 的配置必须是字典格式")
                            continue
                        
                        if "type" not in field_config:
                            errors.append(f"关系类型 '{edge_name}' 的字段 '{field_name}' 缺少 'type' 定义")
        
        # 3. 校验关系映射
        if not edge_type_map:
            warnings.append("关系类型映射为空，可能无法建立实体间的关系")
        else:
            if not isinstance(edge_type_map, dict):
                errors.append("关系类型映射必须是字典格式")
            else:
                for mapping_key, edge_names in edge_type_map.items():
                    # 校验映射格式: "SourceEntity -> TargetEntity"
                    if not isinstance(mapping_key, str) or " -> " not in mapping_key:
                        errors.append(f"关系映射格式错误: {mapping_key}，应为 'SourceEntity -> TargetEntity'")
                        continue
                    
                    source_entity, target_entity = mapping_key.split(" -> ", 1)
                    
                    # 检查源实体是否存在
                    if entity_types and source_entity not in entity_types:
                        warnings.append(f"关系映射中的源实体 '{source_entity}' 未在实体类型中定义")
                    
                    # 检查目标实体是否存在
                    if entity_types and target_entity not in entity_types:
                        warnings.append(f"关系映射中的目标实体 '{target_entity}' 未在实体类型中定义")
                    
                    # 检查关系类型是否存在
                    if not isinstance(edge_names, list):
                        errors.append(f"关系映射 '{mapping_key}' 的值必须是列表")
                        continue
                    
                    for edge_name in edge_names:
                        if edge_types and edge_name not in edge_types:
                            warnings.append(f"关系映射 '{mapping_key}' 中的关系类型 '{edge_name}' 未在关系类型中定义")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @staticmethod
    def _parse_type(type_str: str) -> Type:
        """
        解析类型字符串为Python类型
        
        Args:
            type_str: 类型字符串，如 "str", "Optional[str]", "int", "bool"
        
        Returns:
            Python类型
        """
        from typing import Optional
        
        type_str = type_str.strip()
        
        # 处理 Optional 类型
        if type_str.startswith("Optional[") and type_str.endswith("]"):
            inner_type_str = type_str[9:-1].strip()
            inner_type = TemplateService._parse_type(inner_type_str)
            return Optional[inner_type]
        
        # 基本类型映射
        type_mapping = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "dict": dict,
            "list": list,
        }
        
        return type_mapping.get(type_str, str)
    
    @staticmethod
    def convert_to_pydantic(
        entity_types_config: Dict[str, Any],
        edge_types_config: Dict[str, Any],
        edge_type_map_config: Dict[str, Any]
    ) -> Tuple[Dict[str, Type[BaseModel]], Dict[str, Type[BaseModel]], Dict[Tuple[str, str], List[str]]]:
        """
        将JSON配置转换为Pydantic模型
        
        Args:
            entity_types_config: 实体类型配置
            edge_types_config: 关系类型配置
            edge_type_map_config: 关系类型映射配置
        
        Returns:
            (entity_types_dict, edge_types_dict, edge_type_map_dict)
            entity_types_dict: {"EntityName": PydanticModel, ...}
            edge_types_dict: {"EdgeName": PydanticModel, ...}
            edge_type_map_dict: {("SourceEntity", "TargetEntity"): ["EdgeName1", ...]}
        """
        entity_types_dict = {}
        edge_types_dict = {}
        edge_type_map_dict = {}
        
        # 转换实体类型
        for entity_name, entity_config in entity_types_config.items():
            if "fields" not in entity_config:
                logger.warning(f"实体类型 '{entity_name}' 缺少 'fields' 定义，跳过")
                continue
            
            fields = entity_config["fields"]
            field_definitions = {}
            
            for field_name, field_config in fields.items():
                field_type_str = field_config.get("type", "str")
                field_description = field_config.get("description", "")
                field_required = field_config.get("required", False)
                
                field_type = TemplateService._parse_type(field_type_str)
                
                if field_required:
                    field_definitions[field_name] = (field_type, Field(..., description=field_description))
                else:
                    from typing import Optional
                    optional_type = Optional[field_type] if not str(field_type).startswith("typing.Optional") else field_type
                    field_definitions[field_name] = (optional_type, Field(None, description=field_description))
            
            # 动态创建Pydantic模型
            try:
                entity_model = create_model(entity_name, **field_definitions)
                entity_types_dict[entity_name] = entity_model
            except Exception as e:
                logger.error(f"创建实体类型模型 '{entity_name}' 失败: {e}")
        
        # 转换关系类型
        for edge_name, edge_config in edge_types_config.items():
            if "fields" not in edge_config:
                logger.warning(f"关系类型 '{edge_name}' 缺少 'fields' 定义，跳过")
                continue
            
            fields = edge_config["fields"]
            field_definitions = {}
            
            for field_name, field_config in fields.items():
                field_type_str = field_config.get("type", "str")
                field_description = field_config.get("description", "")
                field_required = field_config.get("required", False)
                
                field_type = TemplateService._parse_type(field_type_str)
                
                if field_required:
                    field_definitions[field_name] = (field_type, Field(..., description=field_description))
                else:
                    from typing import Optional
                    optional_type = Optional[field_type] if not str(field_type).startswith("typing.Optional") else field_type
                    field_definitions[field_name] = (optional_type, Field(None, description=field_description))
            
            # 动态创建Pydantic模型
            try:
                edge_model = create_model(edge_name, **field_definitions)
                edge_types_dict[edge_name] = edge_model
            except Exception as e:
                logger.error(f"创建关系类型模型 '{edge_name}' 失败: {e}")
        
        # 转换关系映射
        for mapping_key, edge_names in edge_type_map_config.items():
            if " -> " not in mapping_key:
                logger.warning(f"关系映射格式错误: {mapping_key}，跳过")
                continue
            
            source_entity, target_entity = mapping_key.split(" -> ", 1)
            edge_type_map_dict[(source_entity.strip(), target_entity.strip())] = edge_names
        
        return entity_types_dict, edge_types_dict, edge_type_map_dict

