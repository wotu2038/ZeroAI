from fastapi import APIRouter, HTTPException
from app.models.schemas import ImportDataRequest, ImportResult
from app.services.entity_service import EntityService
from app.services.relationship_service import RelationshipService
from app.models.schemas import EntityCreate, RelationshipCreate
import csv
import json
import io
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=ImportResult)
async def import_data(request: ImportDataRequest):
    """导入数据（CSV或JSON格式）"""
    entities_created = 0
    relationships_created = 0
    errors = []
    
    try:
        if request.format == "csv":
            result = await _import_csv(request.data)
        elif request.format == "json":
            result = await _import_json(request.data)
        else:
            raise ValueError(f"不支持的数据格式: {request.format}")
        
        entities_created = result["entities_created"]
        relationships_created = result["relationships_created"]
        errors = result["errors"]
        
        return ImportResult(
            success=True,
            entities_created=entities_created,
            relationships_created=relationships_created,
            errors=errors
        )
    except Exception as e:
        logger.error(f"Import data error: {e}")
        return ImportResult(
            success=False,
            entities_created=entities_created,
            relationships_created=relationships_created,
            errors=[str(e)]
        )


async def _import_csv(data: str) -> dict:
    """导入CSV数据"""
    entities_created = 0
    relationships_created = 0
    errors = []
    
    try:
        reader = csv.DictReader(io.StringIO(data))
        
        for row in reader:
            # CSV格式：type, name, properties (JSON字符串), source, target, rel_type, rel_properties (JSON字符串)
            # 支持两种模式：实体模式或关系模式
            
            if "name" in row and row["name"]:
                # 实体模式
                try:
                    entity_type = row.get("type", "Concept")
                    name = row["name"]
                    properties = {}
                    
                    if "properties" in row and row["properties"]:
                        try:
                            properties = json.loads(row["properties"])
                        except:
                            pass
                    
                    entity = EntityCreate(
                        name=name,
                        type=entity_type,
                        properties=properties
                    )
                    EntityService.create_entity(entity)
                    entities_created += 1
                except Exception as e:
                    errors.append(f"导入实体失败 {row.get('name', '')}: {str(e)}")
            
            if "source" in row and "target" in row and row["source"] and row["target"]:
                # 关系模式
                try:
                    source = row["source"]
                    target = row["target"]
                    rel_type = row.get("rel_type", "RELATED_TO")
                    rel_properties = {}
                    
                    if "rel_properties" in row and row["rel_properties"]:
                        try:
                            rel_properties = json.loads(row["rel_properties"])
                        except:
                            pass
                    
                    relationship = RelationshipCreate(
                        source=source,
                        target=target,
                        type=rel_type,
                        properties=rel_properties
                    )
                    RelationshipService.create_relationship(relationship)
                    relationships_created += 1
                except Exception as e:
                    errors.append(f"导入关系失败 {row.get('source', '')}->{row.get('target', '')}: {str(e)}")
        
        return {
            "entities_created": entities_created,
            "relationships_created": relationships_created,
            "errors": errors
        }
    except Exception as e:
        raise ValueError(f"CSV解析失败: {str(e)}")


async def _import_json(data: str) -> dict:
    """导入JSON数据"""
    entities_created = 0
    relationships_created = 0
    errors = []
    
    try:
        json_data = json.loads(data)
        
        # 支持两种JSON格式：
        # 1. {"entities": [...], "relationships": [...]}
        # 2. [{"type": "entity/relationship", ...}]
        
        if isinstance(json_data, dict):
            # 格式1
            entities_data = json_data.get("entities", [])
            relationships_data = json_data.get("relationships", [])
        elif isinstance(json_data, list):
            # 格式2
            entities_data = [item for item in json_data if item.get("type") == "entity"]
            relationships_data = [item for item in json_data if item.get("type") == "relationship"]
        else:
            raise ValueError("JSON格式不正确")
        
        # 导入实体
        for entity_data in entities_data:
            try:
                entity = EntityCreate(
                    name=entity_data.get("name", ""),
                    type=entity_data.get("type", "Concept"),
                    properties=entity_data.get("properties", {})
                )
                EntityService.create_entity(entity)
                entities_created += 1
            except Exception as e:
                errors.append(f"导入实体失败 {entity_data.get('name', '')}: {str(e)}")
        
        # 导入关系
        for rel_data in relationships_data:
            try:
                relationship = RelationshipCreate(
                    source=rel_data.get("source", ""),
                    target=rel_data.get("target", ""),
                    type=rel_data.get("type", "RELATED_TO"),
                    properties=rel_data.get("properties", {})
                )
                RelationshipService.create_relationship(relationship)
                relationships_created += 1
            except Exception as e:
                errors.append(f"导入关系失败 {rel_data.get('source', '')}->{rel_data.get('target', '')}: {str(e)}")
        
        return {
            "entities_created": entities_created,
            "relationships_created": relationships_created,
            "errors": errors
        }
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败: {str(e)}")

