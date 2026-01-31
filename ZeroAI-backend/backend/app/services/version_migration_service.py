"""
版本管理迁移服务

将旧文档的 group_id 迁移到新的格式（共享基础 group_id）
"""
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from app.core.neo4j_client import neo4j_client
from app.core.utils import serialize_neo4j_properties

logger = logging.getLogger(__name__)


class VersionMigrationService:
    """版本管理迁移服务"""
    
    @staticmethod
    def _extract_base_name(document_name: str) -> str:
        """
        从文档名称中提取基础标识（去除版本号）
        
        Args:
            document_name: 文档名称，例如 "产业项目-项目里程碑管理-软件需求规格说明书-20230731- V1"
        
        Returns:
            基础标识，例如 "产业项目-项目里程碑管理-软件需求规格说明书-20230731"
        """
        # 支持多种版本号格式
        patterns = [
            r'\s*-\s*V\d+$',           # " - V1"
            r'\s*-\s*v\d+$',           # " - v1"
            r'\s*版本\d+$',             # " 版本1"
            r'\s*Version\s*\d+$',      # " Version 1"
            r'\s*version\s*\d+$',      # " version 1"
        ]
        
        base_name = document_name
        for pattern in patterns:
            base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)
        
        return base_name.strip()
    
    @staticmethod
    def _extract_version(document_name: str, group_id: str = None) -> Tuple[str, int]:
        """
        从文档名称或 group_id 中提取版本号
        
        Args:
            document_name: 文档名称
            group_id: group_id（备用）
        
        Returns:
            (version_string, version_number) 例如 ("V1", 1)
        """
        # 优先从文档名称中提取
        version_match = re.search(r'V(\d+)', document_name, re.IGNORECASE)
        if version_match:
            version_num = int(version_match.group(1))
            return f"V{version_num}", version_num
        
        # 如果文档名称中没有，尝试从 group_id 中提取
        if group_id:
            version_match = re.search(r'_V(\d+)_', group_id, re.IGNORECASE)
            if version_match:
                version_num = int(version_match.group(1))
                return f"V{version_num}", version_num
        
        # 如果都找不到，返回默认值
        return "V1", 1
    
    @staticmethod
    def _sanitize_group_id(name: str) -> str:
        """
        清理 group_id，只保留字母数字、破折号和下划线
        （与 WordDocumentService._sanitize_group_id 保持一致）
        """
        import re
        
        # 将中文字符和其他特殊字符替换为下划线
        sanitized = re.sub(r'[^a-zA-Z0-9\-_]', '_', name)
        
        # 将连续的下划线替换为单个下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # 去除开头和结尾的下划线
        sanitized = sanitized.strip('_')
        
        # 如果清理后为空，使用默认值
        if not sanitized:
            sanitized = "document"
        
        # 限制长度
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        return sanitized
    
    @staticmethod
    def _generate_base_group_id(base_name: str, date_str: str = None) -> str:
        """
        生成基础 group_id（所有版本共享）
        
        Args:
            base_name: 基础标识
            date_str: 日期字符串（格式：YYYYMMDD），如果为None则使用最早的创建日期
        
        Returns:
            基础 group_id，例如 "doc_-_-_-20230731_20251225"
        """
        safe_base_name = VersionMigrationService._sanitize_group_id(base_name)
        
        if not date_str:
            # 如果没有提供日期，使用当前日期
            date_str = datetime.now().strftime('%Y%m%d')
        
        return f"doc_{safe_base_name}_{date_str}"
    
    @staticmethod
    def analyze_existing_documents() -> Dict[str, List[Dict[str, Any]]]:
        """
        分析现有文档，识别同一需求的不同版本
        
        Returns:
            {
                "base_group_id": [
                    {
                        "old_group_id": "doc_-_-_-20230731-_V1_20251225",
                        "version": "V1",
                        "version_number": 1,
                        "document_name": "...",
                        "episode_count": 120
                    },
                    ...
                ],
                ...
            }
        """
        # 查询所有文档级 Episode
        query = """
        MATCH (e:Episodic)
        WHERE e.group_id STARTS WITH 'doc_'
          AND e.name CONTAINS '文档概览'
        RETURN DISTINCT e.group_id as group_id, 
               e.name as name,
               e.created_at as created_at
        ORDER BY e.group_id
        """
        
        result = neo4j_client.execute_query(query, {})
        
        # 按基础标识分组
        doc_groups = {}
        
        for record in result:
            old_group_id = record.get('group_id', '')
            name = record.get('name', '')
            created_at = record.get('created_at')
            
            # 从old_group_id中提取基础标识（去除版本号部分）
            # old_group_id格式: "doc_-_-_-20230731-_V1_20251225"
            # 需要提取: "doc_-_-_-20230731_20251225"（去除_V1部分）
            import re
            # 去除版本号部分（_V1, _V2等）
            base_group_id_pattern = re.sub(r'_V\d+_', '_', old_group_id)
            # 如果还是包含版本号，尝试其他模式
            if '_V' in base_group_id_pattern:
                base_group_id_pattern = re.sub(r'_V\d+', '', base_group_id_pattern)
            
            # 提取版本号
            version, version_number = VersionMigrationService._extract_version(name, old_group_id)
            
            # 如果base_group_id_pattern还是包含版本号，从name中提取基础标识
            if '_V' in base_group_id_pattern or not base_group_id_pattern.startswith('doc_'):
                base_name = VersionMigrationService._extract_base_name(name)
                # 使用最早的创建日期作为日期部分
                date_str = None
                if created_at:
                    if hasattr(created_at, 'to_native'):
                        date_obj = created_at.to_native()
                    elif isinstance(created_at, datetime):
                        date_obj = created_at
                    else:
                        try:
                            date_obj = datetime.fromisoformat(str(created_at))
                        except:
                            date_obj = datetime.now()
                    date_str = date_obj.strftime('%Y%m%d')
                base_group_id = VersionMigrationService._generate_base_group_id(base_name, date_str)
            else:
                base_group_id = base_group_id_pattern
            
            # 统计该文档的 Episode 数量
            count_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            RETURN count(e) as count
            """
            count_result = neo4j_client.execute_query(count_query, {"group_id": old_group_id})
            episode_count = count_result[0].get("count", 0) if count_result else 0
            
            if base_group_id not in doc_groups:
                doc_groups[base_group_id] = []
            
            doc_groups[base_group_id].append({
                "old_group_id": old_group_id,
                "version": version,
                "version_number": version_number,
                "document_name": name,
                "created_at": created_at,
                "episode_count": episode_count
            })
        
        # 对每个组内的版本进行排序
        for base_group_id in doc_groups:
            doc_groups[base_group_id].sort(key=lambda x: x["version_number"])
        
        return doc_groups
    
    @staticmethod
    def migrate_document_versions(
        base_group_id: str,
        versions: List[Dict[str, Any]],
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        迁移文档版本到新的 group_id 格式
        
        Args:
            base_group_id: 新的基础 group_id
            versions: 版本列表
            dry_run: 是否为试运行（不实际修改数据）
        
        Returns:
            迁移结果统计
        """
        migration_result = {
            "base_group_id": base_group_id,
            "versions_migrated": [],
            "total_episodes_updated": 0,
            "errors": []
        }
        
        for version_info in versions:
            old_group_id = version_info["old_group_id"]
            version = version_info["version"]
            version_number = version_info["version_number"]
            
            try:
                if dry_run:
                    logger.info(f"[试运行] 准备迁移: {old_group_id} -> {base_group_id} (版本: {version})")
                else:
                    # 更新所有相关 Episode 的 group_id 和版本信息
                    update_query = """
                    MATCH (e:Episodic)
                    WHERE e.group_id = $old_group_id
                    SET e.group_id = $new_group_id,
                        e.version = $version,
                        e.version_number = $version_number
                    RETURN count(e) as updated_count
                    """
                    
                    update_result = neo4j_client.execute_query(update_query, {
                        "old_group_id": old_group_id,
                        "new_group_id": base_group_id,
                        "version": version,
                        "version_number": version_number
                    })
                    
                    updated_count = update_result[0].get("updated_count", 0) if update_result else 0
                    
                    # 更新所有相关 Entity 的 group_id
                    update_entity_query = """
                    MATCH (n:Entity)
                    WHERE n.group_id = $old_group_id
                    SET n.group_id = $new_group_id
                    RETURN count(n) as updated_count
                    """
                    
                    entity_result = neo4j_client.execute_query(update_entity_query, {
                        "old_group_id": old_group_id,
                        "new_group_id": base_group_id
                    })
                    
                    entity_count = entity_result[0].get("updated_count", 0) if entity_result else 0
                    
                    # 更新所有相关关系的 group_id
                    update_rel_query = """
                    MATCH ()-[r:RELATES_TO|MENTIONS]->()
                    WHERE r.group_id = $old_group_id
                    SET r.group_id = $new_group_id
                    RETURN count(r) as updated_count
                    """
                    
                    rel_result = neo4j_client.execute_query(update_rel_query, {
                        "old_group_id": old_group_id,
                        "new_group_id": base_group_id
                    })
                    
                    rel_count = rel_result[0].get("updated_count", 0) if rel_result else 0
                    
                    logger.info(f"迁移完成: {old_group_id} -> {base_group_id}")
                    logger.info(f"  更新 Episode: {updated_count} 个")
                    logger.info(f"  更新 Entity: {entity_count} 个")
                    logger.info(f"  更新关系: {rel_count} 个")
                    
                    migration_result["versions_migrated"].append({
                        "old_group_id": old_group_id,
                        "version": version,
                        "episodes_updated": updated_count,
                        "entities_updated": entity_count,
                        "relationships_updated": rel_count
                    })
                    
                    migration_result["total_episodes_updated"] += updated_count
                    
            except Exception as e:
                error_msg = f"迁移 {old_group_id} 失败: {str(e)}"
                logger.error(error_msg, exc_info=True)
                migration_result["errors"].append({
                    "old_group_id": old_group_id,
                    "error": str(e)
                })
        
        return migration_result
    
    @staticmethod
    def migrate_all_documents(dry_run: bool = True) -> Dict[str, Any]:
        """
        迁移所有文档到新的 group_id 格式
        
        Args:
            dry_run: 是否为试运行
        
        Returns:
            迁移结果统计
        """
        logger.info("开始分析现有文档...")
        doc_groups = VersionMigrationService.analyze_existing_documents()
        
        logger.info(f"识别到 {len(doc_groups)} 个文档组（同一需求的不同版本）")
        
        all_results = {
            "total_groups": len(doc_groups),
            "migrations": [],
            "total_episodes_updated": 0,
            "total_errors": 0
        }
        
        for base_group_id, versions in doc_groups.items():
            logger.info(f"\n处理文档组: {base_group_id}")
            logger.info(f"  包含 {len(versions)} 个版本")
            
            result = VersionMigrationService.migrate_document_versions(
                base_group_id,
                versions,
                dry_run=dry_run
            )
            
            all_results["migrations"].append(result)
            all_results["total_episodes_updated"] += result["total_episodes_updated"]
            all_results["total_errors"] += len(result["errors"])
        
        return all_results

