"""
智能对话服务

实现文档入库流程和检索生成流程的分步执行
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.core.graphiti_client import get_graphiti_instance
from app.core.neo4j_client import neo4j_client
from app.core.embedding_client import embedding_client
from app.core.llm_client import LLMClient
# Mem0 延迟导入，只在步骤6需要时导入
# from app.core.mem0_client import get_mem0_client
from app.services.milvus_service import get_milvus_service, VectorType
from app.services.cognee_service import get_cognee, CogneeService
from app.services.graphiti_service import GraphitiService
from app.core.mysql_client import SessionLocal
from app.models.document_upload import DocumentUpload
from app.models.graphiti_entities import (
    LIGHTWEIGHT_ENTITY_TYPES,
    LIGHTWEIGHT_EDGE_TYPES,
    LIGHTWEIGHT_EDGE_TYPE_MAP
)
from app.core.utils import serialize_neo4j_properties
from app.services.template_service import TemplateService
from app.services.template_generation_service import TemplateGenerationService
from app.models.template import EntityEdgeTemplate
from app.core.config import settings
from typing import Type
from pydantic import BaseModel
import os
import json

logger = logging.getLogger(__name__)


def _validate_provider_config(provider: str) -> tuple[bool, str]:
    """
    验证 provider 配置是否完整
    
    Args:
        provider: LLM提供商名称
        
    Returns:
        (是否有效, 错误信息或成功信息)
    """
    if provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            return False, "DeepSeek API key 未配置，请在 .env 文件中设置 DEEPSEEK_API_KEY"
        if not settings.DEEPSEEK_API_BASE:
            return False, "DeepSeek API base 未配置，请在 .env 文件中设置 DEEPSEEK_API_BASE"
        if not settings.DEEPSEEK_MODEL:
            return False, "DeepSeek model 未配置，请在 .env 文件中设置 DEEPSEEK_MODEL"
        return True, f"DeepSeek 配置完整: {settings.DEEPSEEK_MODEL} @ {settings.DEEPSEEK_API_BASE}"
    
    elif provider == "qwen" or provider == "qianwen":
        if not settings.QWEN_API_KEY:
            return False, "Qwen API key 未配置，请在 .env 文件中设置 QWEN_API_KEY"
        if not settings.QWEN_API_BASE:
            return False, "Qwen API base 未配置，请在 .env 文件中设置 QWEN_API_BASE"
        if not settings.QWEN_MODEL:
            return False, "Qwen model 未配置，请在 .env 文件中设置 QWEN_MODEL"
        return True, f"Qwen 配置完整: {settings.QWEN_MODEL} @ {settings.QWEN_API_BASE}"
    
    elif provider == "kimi":
        if not settings.KIMI_API_KEY:
            return False, "Kimi API key 未配置，请在 .env 文件中设置 KIMI_API_KEY"
        if not settings.KIMI_API_BASE:
            return False, "Kimi API base 未配置，请在 .env 文件中设置 KIMI_API_BASE"
        if not settings.KIMI_MODEL:
            return False, "Kimi model 未配置，请在 .env 文件中设置 KIMI_MODEL"
        return True, f"Kimi 配置完整: {settings.KIMI_MODEL} @ {settings.KIMI_API_BASE}"
    
    else:
        return False, f"不支持的 provider: {provider}，仅支持 deepseek/qwen/kimi"


class IntelligentChatService:
    """智能对话服务"""
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.milvus = get_milvus_service()
    
    # ==================== 文档入库流程 ====================
    
    async def _save_graphiti_template_to_db(
        self,
        template_config: Dict[str, Any],
        upload_id: int,
        document_name: str,
        template_mode: str,  # "llm_generate" 或 "json_config"
        provider: str = "deepseek"
    ) -> Optional[int]:
        """
        保存 Graphiti 模板到数据库
        
        Args:
            template_config: 模板配置（entity_types, edge_types, edge_type_map）
            upload_id: 文档上传ID
            document_name: 文档名称
            template_mode: 模板模式（llm_generate 或 json_config）
            provider: LLM 提供商
            
        Returns:
            模板ID（如果保存成功），否则返回 None
        """
        try:
            # 1. 验证模板配置
            is_valid, errors, warnings = TemplateService.validate_template(
                template_config.get("entity_types", {}),
                template_config.get("edge_types", {}),
                template_config.get("edge_type_map", {})
            )
            
            if not is_valid:
                logger.warning(f"Graphiti 模板验证失败，不保存: {', '.join(errors)}")
                return None
            
            logger.info(
                f"Graphiti 模板验证通过: "
                f"实体类型数={len(template_config.get('entity_types', {}))}, "
                f"关系类型数={len(template_config.get('edge_types', {}))}"
            )
            
            # 2. 生成模板名称
            doc_name = document_name.rsplit('.', 1)[0] if '.' in document_name else document_name
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            mode_label = "LLM自动生成" if template_mode == "llm_generate" else "JSON手动配置"
            template_name = f"Graphiti-文档级-{mode_label}-{doc_name}-{timestamp}"
            
            # 3. 生成模板描述
            description = f"基于文档'{document_name}'的Graphiti文档级模板（{mode_label}）"
            
            # 4. 创建模板记录
            db = SessionLocal()
            try:
                template = EntityEdgeTemplate(
                    name=template_name,
                    description=description,
                    category="custom",
                    entity_types=template_config.get("entity_types", {}),
                    edge_types=template_config.get("edge_types", {}),
                    edge_type_map=template_config.get("edge_type_map", {}),
                    is_default=False,
                    is_system=False,
                    is_llm_generated=(template_mode == "llm_generate"),
                    source_document_id=upload_id,
                    analysis_mode="graphiti_document",
                    llm_provider=provider,
                    generated_at=datetime.now(),
                    usage_count=0
                )
                
                db.add(template)
                db.commit()
                db.refresh(template)
                
                logger.info(
                    f"Graphiti 模板已保存到数据库: "
                    f"template_id={template.id}, "
                    f"name={template_name}, "
                    f"mode={template_mode}, "
                    f"实体类型数={len(template_config.get('entity_types', {}))}, "
                    f"关系类型数={len(template_config.get('edge_types', {}))}"
                )
                
                return template.id
            except Exception as e:
                db.rollback()
                logger.error(f"保存 Graphiti 模板到数据库失败: {e}", exc_info=True)
                return None
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"保存 Graphiti 模板到数据库时发生异常: {e}", exc_info=True)
            return None
    
    def _parse_entity_types_from_json(
        self,
        template_config: Dict[str, Any]
    ) -> Dict[str, Type[BaseModel]]:
        """
        从 JSON 配置解析实体类型为 Pydantic 模型
        
        Args:
            template_config: 模板配置
            
        Returns:
            实体类型字典 {"EntityName": PydanticModel, ...}
        """
        entity_types_config = template_config.get("entity_types", {})
        edge_types_config = template_config.get("edge_types", {})
        edge_type_map_config = template_config.get("edge_type_map", {})
        
        entity_types_dict, _, _ = TemplateService.convert_to_pydantic(
            entity_types_config,
            edge_types_config,
            edge_type_map_config
        )
        
        return entity_types_dict
    
    def _parse_edge_types_from_json(
        self,
        template_config: Dict[str, Any]
    ) -> Dict[str, Type[BaseModel]]:
        """
        从 JSON 配置解析关系类型为 Pydantic 模型
        
        Args:
            template_config: 模板配置
            
        Returns:
            关系类型字典 {"EdgeName": PydanticModel, ...}
        """
        entity_types_config = template_config.get("entity_types", {})
        edge_types_config = template_config.get("edge_types", {})
        edge_type_map_config = template_config.get("edge_type_map", {})
        
        _, edge_types_dict, _ = TemplateService.convert_to_pydantic(
            entity_types_config,
            edge_types_config,
            edge_type_map_config
        )
        
        return edge_types_dict
    
    def _parse_edge_type_map_from_json(
        self,
        template_config: Dict[str, Any]
    ) -> Dict[tuple, List[str]]:
        """
        从 JSON 配置解析关系类型映射
        
        Args:
            template_config: 模板配置
            
        Returns:
            关系类型映射字典 {("SourceEntity", "TargetEntity"): ["EdgeName1", ...]}
        """
        entity_types_config = template_config.get("entity_types", {})
        edge_types_config = template_config.get("edge_types", {})
        edge_type_map_config = template_config.get("edge_type_map", {})
        
        _, _, edge_type_map_dict = TemplateService.convert_to_pydantic(
            entity_types_config,
            edge_types_config,
            edge_type_map_config
        )
        
        return edge_type_map_dict
    
    async def step1_graphiti_episode(
        self,
        upload_id: int,
        # 必选参数：用户必须选择一种模式（必须在有默认值的参数之前）
        template_mode: str,  # "llm_generate" 或 "json_config"（必选，无默认值）
        provider: str = "deepseek",
        template_config_json: Optional[Dict[str, Any]] = None  # JSON配置（json_config 模式时必填）
    ) -> Dict[str, Any]:
        """
        步骤1: Graphiti文档级处理（轻量化设计）
        
        根据实施方案，创建轻量级的 Episode：
        - 只存储"业务事件信息"，不存正文、表格、图片
        - 用于时间线和依赖关系推理
        - 轻量化，便于快速建图
        
        Episode Content 字段：
        - episode_id: UUID
        - doc_id: 文档ID
        - type: NEW / CHANGE / DEPRECATE / DEPENDENCY
        - title: 文档标题
        - version: 文档版本号
        - created_at: 创建时间
        - related_docs: 关联文档ID列表
        - system: 所属系统/模块（可选）
        - summary: 1-2句话摘要（可选）
        - author: 创建人（可选）
        - status: ACTIVE / OBSOLETE / ARCHIVED（可选）
        
        Args:
            upload_id: 文档上传ID
            provider: LLM 提供商
            template_mode: 模板模式（"llm_generate" 或 "json_config"）
            template_config_json: JSON配置（json_config 模式时必填）
        """
        # 验证 provider 配置
        config_valid, config_msg = _validate_provider_config(provider)
        if not config_valid:
            logger.error(f"Provider 配置验证失败: {config_msg}")
            raise ValueError(config_msg)
        logger.info(f"Provider 配置验证通过: {config_msg}")
        
        # 验证 template_mode 参数
        if template_mode not in ["llm_generate", "json_config"]:
            raise ValueError(
                f"不支持的 template_mode: {template_mode}，只支持 'llm_generate' 或 'json_config'"
            )
        import uuid as uuid_lib
        from app.services.word_document_service import WordDocumentService
        
        db = SessionLocal()
        try:
            # 获取文档
            document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
            if not document:
                raise ValueError(f"文档不存在: upload_id={upload_id}")
            
            # 生成或获取 group_id（统一使用标准生成规则）
            if document.document_id:
                group_id = document.document_id
                logger.info(f"使用已有的 group_id: {group_id}")
            else:
                # 使用标准规则生成 group_id
                base_name = WordDocumentService._extract_base_name(document.file_name)
                safe_base_name = WordDocumentService._sanitize_group_id(base_name)
                date_str = datetime.now().strftime('%Y%m%d')
                group_id = f"doc_{safe_base_name}_{date_str}"
                
                # 保存到数据库
                document.document_id = group_id
                db.commit()
                logger.info(f"自动生成并保存 group_id: {group_id}")
            
            # ========== 1. 提取文档元数据 ==========
            logger.info(f"开始提取文档元数据: upload_id={upload_id}, group_id={group_id}")
            
            # 提取文档版本信息
            base_name = WordDocumentService._extract_base_name(document.file_name)
            version, version_number = WordDocumentService._extract_version(document.file_name)
            
            # 提取文档类型（NEW / CHANGE）
            episode_type = "NEW"
            related_docs = []
            if version and version != "v1.0":
                episode_type = "CHANGE"
                # TODO: 查找前一个版本（后续实现）
                # previous_version = find_previous_version(document)
                # if previous_version:
                #     related_docs = [previous_version.doc_id]
            
            # 提取系统/模块信息（从文件名或元数据中提取）
            system = None
            # 尝试从文件名中提取系统名（例如："订单系统_需求文档.docx" -> "订单系统"）
            if "_" in base_name:
                parts = base_name.split("_")
                if len(parts) > 1:
                    system = parts[0]
            
            # ========== 2. 提取文档摘要（1-2句话）==========
            summary = None
            if document.summary_content_path and os.path.exists(document.summary_content_path):
                try:
                    with open(document.summary_content_path, 'r', encoding='utf-8') as f:
                        summary_content = f.read()
                    
                    # 提取"文档概览"部分的第一段作为摘要
                    summary_lines = summary_content.split('\n')
                    overview_start = None
                    overview_end = None
                    
                    for idx, line in enumerate(summary_lines):
                        if line.strip() == "## 文档概览":
                            overview_start = idx + 1
                        elif overview_start is not None and line.startswith("## ") and line.strip() != "## 文档概览":
                            overview_end = idx
                            break
                    
                    if overview_start is not None:
                        overview_content = '\n'.join(
                            summary_lines[overview_start:overview_end if overview_end else len(summary_lines)]
                        )
                        # 提取第一段（1-2句话）
                        paragraphs = [p.strip() for p in overview_content.split('\n\n') if p.strip()]
                        if paragraphs:
                            # 取第一段，限制在200字符以内
                            summary = paragraphs[0][:200]
                            # 如果超过200字符，截取到最后一个句号
                            if len(paragraphs[0]) > 200:
                                last_period = summary.rfind('。')
                                if last_period > 100:  # 确保至少100字符
                                    summary = summary[:last_period + 1]
                    
                    # 如果没有找到"文档概览"，使用摘要的前200字符
                    if not summary and summary_content:
                        summary = summary_content[:200]
                        last_period = summary.rfind('。')
                        if last_period > 100:
                            summary = summary[:last_period + 1]
                
                except Exception as e:
                    logger.warning(f"提取文档摘要失败: {e}")
            
            # ========== 2.5 处理模板配置（根据 template_mode）==========
            logger.info(f"开始处理模板配置: template_mode={template_mode}")
            entity_types = None
            edge_types = None
            edge_type_map = None
            template_id = None
            
            # 读取完整摘要内容（用于 LLM 生成模板）
            full_summary_content = None
            if document.summary_content_path and os.path.exists(document.summary_content_path):
                try:
                    with open(document.summary_content_path, 'r', encoding='utf-8') as f:
                        full_summary_content = f.read()
                except Exception as e:
                    logger.warning(f"读取完整摘要内容失败: {e}")
            
            if template_mode == "json_config":
                # JSON 配置模式
                if not template_config_json:
                    raise ValueError("json_config 模式必须提供 template_config_json 参数")
                
                # 验证 JSON 配置
                is_valid, errors, warnings = TemplateService.validate_template(
                    template_config_json.get("entity_types", {}),
                    template_config_json.get("edge_types", {}),
                    template_config_json.get("edge_type_map", {})
                )
                if not is_valid:
                    raise ValueError(f"JSON 配置验证失败: {', '.join(errors)}")
                
                # 解析实体和关系类型
                entity_types = self._parse_entity_types_from_json(template_config_json)
                edge_types = self._parse_edge_types_from_json(template_config_json)
                edge_type_map = self._parse_edge_type_map_from_json(template_config_json)
                
                logger.info(
                    f"JSON 配置解析成功: "
                    f"实体类型数={len(entity_types)}, "
                    f"关系类型数={len(edge_types)}, "
                    f"关系映射数={len(edge_type_map)}"
                )
                
                # 保存 JSON 配置模板到数据库
                template_id = await self._save_graphiti_template_to_db(
                    template_config=template_config_json,
                    upload_id=upload_id,
                    document_name=document.file_name,
                    template_mode="json_config",
                    provider=provider
                )
                if template_id:
                    logger.info(f"Graphiti JSON配置模板已保存: template_id={template_id}")
                    
            elif template_mode == "llm_generate":
                # LLM 生成模板模式
                # 使用 summary_content 作为输入（更完整的信息）
                if not full_summary_content:
                    raise ValueError("LLM生成模式需要文档摘要，请先完成文档解析")
                
                logger.info(f"使用 LLM 生成模板，输入内容长度: {len(full_summary_content)} 字符")
                
                # 生成模板
                template_config = await TemplateGenerationService.generate_template_smart_segment(
                    content=full_summary_content,
                    document_name=document.file_name,
                    provider=provider
                )
                
                # 解析实体和关系类型
                entity_types = self._parse_entity_types_from_json(template_config)
                edge_types = self._parse_edge_types_from_json(template_config)
                edge_type_map = self._parse_edge_type_map_from_json(template_config)
                
                logger.info(
                    f"LLM 模板生成成功: "
                    f"实体类型数={len(entity_types)}, "
                    f"关系类型数={len(edge_types)}, "
                    f"关系映射数={len(edge_type_map)}"
                )
                
                # 保存 LLM 生成模板到数据库
                template_id = await self._save_graphiti_template_to_db(
                    template_config=template_config,
                    upload_id=upload_id,
                    document_name=document.file_name,
                    template_mode="llm_generate",
                    provider=provider
                )
                if template_id:
                    logger.info(f"Graphiti LLM生成模板已保存: template_id={template_id}")
            
            # 验证：确保模板配置已成功解析
            if not entity_types or not edge_types:
                raise ValueError(f"模板配置解析失败: template_mode={template_mode}")
            
            # ========== 3. 构建轻量化的 Episode Content ==========
            episode_id = str(uuid_lib.uuid4())
            doc_id = f"DOC_{upload_id}"
            
            episode_content = {
                # 必须字段
                "episode_id": episode_id,
                "doc_id": doc_id,
                "type": episode_type,
                "title": base_name or document.file_name.rsplit('.', 1)[0],
                "version": version or "v1.0",
                "created_at": document.upload_time.isoformat() if document.upload_time else datetime.now().isoformat(),
                "related_docs": related_docs,
                
                # 可选字段
                "system": system,
                "summary": summary,  # 1-2句话摘要，仅用于快速理解
                "author": None,  # TODO: 从文档元数据或用户信息中提取
                "status": "ACTIVE"
            }
            
            # 轻量化验证：确保不包含正文、表格、图片
            content_str = json.dumps(episode_content, ensure_ascii=False)
            assert len(content_str) < 2000, "Episode Content 应该轻量化，不超过2000字符"
            assert "tables" not in content_str.lower(), "Episode Content 不应包含表格数据"
            assert "images" not in content_str.lower() or "image" not in content_str.lower(), "Episode Content 不应包含图片数据"
            
            # 注意：不再验证轻量化要求，因为用户可能使用自定义模板
            logger.info("Episode Content 构建完成")
            
            logger.info(
                f"Episode Content 构建完成: "
                f"episode_id={episode_id}, doc_id={doc_id}, type={episode_type}, "
                f"version={version}, summary_length={len(summary) if summary else 0}"
            )
            
            # ========== 3.5 提取章节标题列表（用于增强 episode_body）==========
            section_titles = []
            if document.chunks_path and os.path.exists(document.chunks_path):
                try:
                    with open(document.chunks_path, 'r', encoding='utf-8') as f:
                        chunks_data = json.load(f)
                        chunks = chunks_data.get("chunks", [])
                        
                        # 按层级分类
                        level_1_titles = [chunk.get("title", "") for chunk in chunks if chunk.get("level") == 1]
                        level_2_titles = [chunk.get("title", "") for chunk in chunks if chunk.get("level") == 2]
                        
                        # 过滤空标题
                        level_1_titles = [t for t in level_1_titles if t and t.strip()]
                        level_2_titles = [t for t in level_2_titles if t and t.strip()]
                        
                        # 优先使用一级标题，不足则补充二级标题
                        max_section_titles = 20
                        if len(level_1_titles) >= 5:
                            section_titles = level_1_titles[:max_section_titles]
                        else:
                            # 一级标题不足，补充二级标题
                            section_titles = level_1_titles + level_2_titles[:max_section_titles - len(level_1_titles)]
                        
                        logger.info(
                            f"提取章节标题: 一级={len(level_1_titles)}, 二级={len(level_2_titles)}, "
                            f"最终={len(section_titles)}"
                        )
                except Exception as e:
                    logger.warning(f"读取章节标题失败: {e}")
            
            # ========== 4. 使用 Graphiti 创建 Episode ==========
            logger.info(f"开始创建 Graphiti Episode: group_id={group_id}")
            graphiti = get_graphiti_instance(provider)
            
            # 将 Episode Content 转换为可读的文本格式作为 episode_body
            # Graphiti 的 add_episode 会使用 LLM 提取实体和关系
            # 我们传入结构化的元数据文本和章节标题列表，让 LLM 能够理解并提取关键信息
            episode_body_parts = [
                f"文档ID: {doc_id}",
                f"文档标题: {episode_content['title']}",
                f"文档类型: {episode_type}",
                f"版本号: {episode_content['version']}",
                f"创建时间: {episode_content['created_at']}",
            ]
            
            if system:
                episode_body_parts.append(f"所属系统: {system}")
            
            if summary:
                episode_body_parts.append(f"文档摘要: {summary}")
            
            if related_docs:
                episode_body_parts.append(f"关联文档: {', '.join(related_docs)}")
            
            # 添加章节标题列表（增强 LLM 提取实体和关系的能力）
            if section_titles:
                episode_body_parts.append("\n主要章节：")
                for idx, title in enumerate(section_titles, 1):
                    episode_body_parts.append(f"{idx}. {title}")
            
            # 构建轻量化的 episode_body（包含元数据和章节标题列表，不包含正文）
            episode_body = "\n".join(episode_body_parts)
            
            # 验证轻量化：确保不超过1000字符（因为添加了章节标题列表）
            if len(episode_body) > 1000:
                logger.warning(f"Episode body 超过1000字符，已截断: {len(episode_body)}")
                episode_body = episode_body[:1000]
            
            logger.info(f"Episode body 长度: {len(episode_body)} 字符（轻量化设计，包含 {len(section_titles)} 个章节标题）")
            
            # ========== 4.1 使用配置的实体和关系类型 ==========
            logger.info(
                f"使用模板配置的实体和关系类型: "
                f"template_mode={template_mode}, "
                f"实体类型数={len(entity_types)}, "
                f"关系类型数={len(edge_types)}, "
                f"关系映射数={len(edge_type_map) if edge_type_map else 0}"
            )
            
            episode_result = await graphiti.add_episode(
                name=f"{episode_content['title']}_文档级",
                episode_body=episode_body,  # 轻量化的元数据，不是完整文档内容
                source_description="需求文档（轻量化Episode）",
                reference_time=datetime.fromisoformat(episode_content["created_at"].replace('Z', '+00:00')) if 'T' in episode_content["created_at"] else datetime.now(),
                group_id=group_id,
                # 传入模板配置的实体和关系类型
                entity_types=entity_types,
                edge_types=edge_types,
                edge_type_map=edge_type_map
            )
            
            episode_uuid = episode_result.episode.uuid
            
            # 更新 Neo4j 中的 Episode 节点，添加额外的元数据属性
            logger.info(f"更新 Episode 节点元数据: episode_uuid={episode_uuid}")
            update_episode_query = """
            MATCH (e:Episodic)
            WHERE e.uuid = $episode_uuid
            SET e.episode_id = $episode_id,
                e.doc_id = $doc_id,
                e.episode_type = $episode_type,
                e.version = $version,
                e.system = $system,
                e.status = $status,
                e.related_docs = $related_docs
            RETURN e.uuid as uuid
            """
            
            try:
                neo4j_client.execute_query(update_episode_query, {
                    "episode_uuid": episode_uuid,
                    "episode_id": episode_id,
                    "doc_id": doc_id,
                    "episode_type": episode_type,
                    "version": version or "v1.0",
                    "system": system or "",
                    "status": "ACTIVE",
                    "related_docs": json.dumps(related_docs) if related_docs else "[]"
                })
                logger.info(f"Episode 节点元数据更新成功")
            except Exception as e:
                logger.warning(f"更新 Episode 节点元数据失败: {e}，继续执行")
            
            # 等待一下，确保Graphiti已经将数据写入Neo4j
            await asyncio.sleep(2)
            
            # ========== 4.5 建立与 Cognee TextSummary 的引用关系 ==========
            logger.info(f"尝试建立与 Cognee TextSummary 的引用关系: episode_uuid={episode_uuid}, group_id={group_id}")
            text_summary_reference = {
                "established": False,
                "text_summary_id": None,
                "text_summary_uuid": None,
                "text_summary_text": None,
                "error": None
            }
            
            try:
                # 查找 Cognee TextSummary 节点
                # 问题：Cognee 创建的节点（TextSummary、TextDocument、DocumentChunk）都没有 group_id 或 dataset_name 属性
                # 解决方案：直接查找所有有内容的 TextSummary，按创建时间排序，选择最新的
                # 这是一个简化的方案，因为无法通过 group_id 精确匹配
                find_text_summary_query = """
                MATCH (ts:TextSummary)
                WHERE '__Node__' IN labels(ts)
                  AND ts.text IS NOT NULL
                  AND ts.text <> ''
                RETURN id(ts) as text_summary_id, ts.text as text_summary_text, ts.id as text_summary_uuid, ts.created_at as created_at
                ORDER BY ts.created_at DESC
                LIMIT 1
                """
                
                logger.info(f"查找 Cognee TextSummary（简化方案：选择最新的有内容的 TextSummary）")
                
                text_summary_results = neo4j_client.execute_query(find_text_summary_query, {
                    "group_id": group_id
                })
                
                if text_summary_results and len(text_summary_results) > 0:
                    text_summary_id = text_summary_results[0].get("text_summary_id")
                    text_summary_uuid = text_summary_results[0].get("text_summary_uuid")
                    text_summary_text = text_summary_results[0].get("text_summary_text", "")
                    
                    logger.info(f"找到 Cognee TextSummary 节点: text_summary_id={text_summary_id}, text_summary_uuid={text_summary_uuid}, text_length={len(text_summary_text) if text_summary_text else 0}")
                    
                    # 建立引用关系：(DocumentEpisode)-[:SUMMARIZED_FROM]->(TextSummary)
                    create_reference_query = """
                    MATCH (e:Episodic {uuid: $episode_uuid})
                    MATCH (ts:TextSummary)
                    WHERE id(ts) = $text_summary_id
                    MERGE (e)-[r:SUMMARIZED_FROM]->(ts)
                    SET r.created_at = timestamp()
                    RETURN id(r) as relation_id
                    """
                    
                    reference_result = neo4j_client.execute_query(create_reference_query, {
                        "episode_uuid": episode_uuid,
                        "text_summary_id": text_summary_id
                    })
                    
                    if reference_result:
                        text_summary_reference["established"] = True
                        text_summary_reference["text_summary_id"] = text_summary_id
                        text_summary_reference["text_summary_uuid"] = text_summary_uuid
                        text_summary_reference["text_summary_text"] = text_summary_text[:200] if text_summary_text else None  # 只返回前200字符
                        logger.info(f"✅ 成功建立引用关系: (DocumentEpisode)-[:SUMMARIZED_FROM]->(TextSummary)")
                    else:
                        text_summary_reference["error"] = "建立引用关系失败"
                        logger.warning(f"⚠️ 建立引用关系失败，但继续执行")
                else:
                    text_summary_reference["error"] = f"未找到 Cognee TextSummary 节点（group_id={group_id}）。这可能是因为 Cognee 尚未处理该文档，或者 TextSummary 尚未生成。"
                    logger.info(text_summary_reference["error"])
            except Exception as e:
                text_summary_reference["error"] = str(e)
                logger.warning(f"建立引用关系时出错: {e}，继续执行", exc_info=True)
            
            # ========== 5. 查询创建的Entity和Edge ==========
            logger.info(f"查询创建的 Entity 和 Edge: group_id={group_id}")
            entity_query = """
            MATCH (n:Entity)
            WHERE n.group_id = $group_id
            RETURN id(n) as id, labels(n) as labels, properties(n) as properties
            LIMIT 1000
            """
            
            edge_query = """
            MATCH (a:Entity)-[r]->(b:Entity)
            WHERE r.group_id = $group_id 
              AND (r.episodes IS NULL OR $episode_uuid IN r.episodes)
            RETURN id(r) as id, id(a) as source, id(b) as target, type(r) as type, properties(r) as properties
            LIMIT 1000
            """
            
            entity_results = neo4j_client.execute_query(entity_query, {
                "group_id": group_id
            })
            
            edge_results = neo4j_client.execute_query(edge_query, {
                "group_id": group_id,
                "episode_uuid": episode_uuid
            })
            
            # 处理Entity
            entities = []
            entity_type_counts = {}  # 统计各类型实体数量
            for entity_data in entity_results:
                props = entity_data.get("properties", {})
                labels = entity_data.get("labels", [])
                
                # 统计实体类型
                for label in labels:
                    if label != "Entity":  # 排除基础标签
                        entity_type_counts[label] = entity_type_counts.get(label, 0) + 1
                
                entities.append({
                    "id": str(entity_data.get("id", "")),
                    "labels": labels,
                    "properties": serialize_neo4j_properties(props)
                })
            
            # 处理Edge
            edges = []
            edge_type_counts = {}  # 统计各类型关系数量
            for edge_data in edge_results:
                edge_type = edge_data.get("type", "RELATES_TO")
                edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
                
                edges.append({
                    "id": str(edge_data.get("id", "")),
                    "source": str(edge_data.get("source", "")),
                    "target": str(edge_data.get("target", "")),
                    "type": edge_type,
                    "properties": serialize_neo4j_properties(edge_data.get("properties", {}))
                })
            
            # ========== 6. 依赖关系推理（可选）==========
            # 根据提取的实体和关系，推理文档之间的依赖关系
            dependency_analysis = None
            try:
                dependency_analysis = await self._analyze_dependencies(
                    group_id=group_id,
                    entities=entities,
                    edges=edges,
                    episode_content=episode_content
                )
                logger.info(f"依赖关系分析完成: {dependency_analysis}")
            except Exception as e:
                logger.warning(f"依赖关系分析失败: {e}，继续执行")
            
            # group_id 已经在前面生成并保存，这里不需要再次保存
            
            logger.info(
                f"Graphiti Episode 创建完成: "
                f"episode_uuid={episode_uuid}, group_id={group_id}, "
                f"entity_count={len(entities)}, edge_count={len(edges)}, "
                f"entity_types={entity_type_counts}, edge_types={edge_type_counts}"
            )
            
            # ========== 7. 保存向量到Milvus（步骤2：Graphiti构建后立即保存）==========
            vectors_saved = {
                "episode": 0,
                "entity": 0,
                "edge": 0,
                "community": 0
            }
            
            if self.milvus.is_available():
                logger.info(f"开始保存Graphiti向量到Milvus: group_id={group_id}")
                try:
                    # 7.1 保存Episode向量
                    episode_embedding = None
                    episode_content_text = episode_body  # 使用轻量化的episode_body
                    
                    # 尝试从Neo4j读取Graphiti生成的向量
                    episode_vector_query = """
                    MATCH (e:Episodic)
                    WHERE e.uuid = $episode_uuid
                    RETURN e.embedding as embedding, e.name as name, e.episode_body as episode_body
                    """
                    episode_vector_result = neo4j_client.execute_query(episode_vector_query, {
                        "episode_uuid": episode_uuid
                    })
                    
                    if episode_vector_result and episode_vector_result[0].get("embedding"):
                        episode_embedding = episode_vector_result[0].get("embedding")
                        logger.info(f"从Neo4j读取Episode向量: episode_uuid={episode_uuid}")
                    else:
                        # 如果没有向量，生成新的向量
                        episode_embedding = await embedding_client.get_embedding(episode_content_text)
                        logger.info(f"生成新的Episode向量: episode_uuid={episode_uuid}")
                    
                    if episode_embedding:
                        result = self.milvus.insert_vectors(
                            VectorType.EPISODE,
                            [{
                                "uuid": episode_uuid,
                                "name": f"{episode_content['title']}_文档级",
                                "group_id": group_id,
                                "content": episode_content_text[:1000],  # 限制长度
                                "embedding": episode_embedding
                            }]
                        )
                        vectors_saved["episode"] = len(result)
                        logger.info(f"Episode向量保存完成: {len(result)} 个向量")
                    
                    # 7.2 保存Entity向量
                    entity_vectors = []
                    for entity_data in entity_results:
                        props = entity_data.get("properties", {})
                        entity_uuid = props.get("uuid")
                        entity_name = props.get("name", "")
                        entity_summary = props.get("summary", "")
                        
                        if not entity_uuid:
                            continue
                        
                        # 尝试从Neo4j读取Graphiti生成的向量
                        entity_embedding = props.get("name_embedding")
                        
                        if not entity_embedding:
                            # 如果没有向量，生成新的向量（使用name或summary）
                            entity_text = entity_summary if entity_summary else entity_name
                            entity_embedding = await embedding_client.get_embedding(entity_text)
                        
                        if entity_embedding:
                            entity_vectors.append({
                                "uuid": entity_uuid,
                                "name": entity_name,
                                "group_id": group_id,
                                "content": entity_summary[:1000] if entity_summary else entity_name[:1000],
                                "embedding": entity_embedding
                            })
                    
                    if entity_vectors:
                        # 批量插入Entity向量（每批50个）
                        batch_size = 50
                        for i in range(0, len(entity_vectors), batch_size):
                            batch = entity_vectors[i:i + batch_size]
                            result = self.milvus.insert_vectors(VectorType.ENTITY, batch)
                            vectors_saved["entity"] += len(result)
                        logger.info(f"Entity向量保存完成: {vectors_saved['entity']} 个向量")
                    
                    # 7.3 保存Edge向量
                    edge_vectors = []
                    for edge_data in edge_results:
                        props = edge_data.get("properties", {})
                        edge_uuid = props.get("uuid")
                        edge_name = props.get("name", "")
                        edge_fact = props.get("fact", "")
                        
                        if not edge_uuid:
                            continue
                        
                        # 尝试从Neo4j读取Graphiti生成的向量
                        edge_embedding = props.get("fact_embedding")
                        
                        if not edge_embedding:
                            # 如果没有向量，生成新的向量（使用fact或name）
                            edge_text = edge_fact if edge_fact else edge_name
                            edge_embedding = await embedding_client.get_embedding(edge_text)
                        
                        if edge_embedding:
                            edge_vectors.append({
                                "uuid": edge_uuid,
                                "name": edge_name or edge_fact[:100],
                                "group_id": group_id,
                                "content": edge_fact[:1000] if edge_fact else edge_name[:1000],
                                "embedding": edge_embedding
                            })
                    
                    if edge_vectors:
                        # 批量插入Edge向量（每批50个）
                        batch_size = 50
                        for i in range(0, len(edge_vectors), batch_size):
                            batch = edge_vectors[i:i + batch_size]
                            result = self.milvus.insert_vectors(VectorType.EDGE, batch)
                            vectors_saved["edge"] += len(result)
                        logger.info(f"Edge向量保存完成: {vectors_saved['edge']} 个向量")
                    
                    # 7.4 保存Community向量（如果有）
                    community_query = """
                    MATCH (c:Community)
                    WHERE c.group_id = $group_id
                    RETURN c.uuid as uuid, c.name as name, c.summary as summary, c.name_embedding as embedding
                    LIMIT 100
                    """
                    community_results = neo4j_client.execute_query(community_query, {
                        "group_id": group_id
                    })
                    
                    community_vectors = []
                    for comm_data in community_results:
                        comm_uuid = comm_data.get("uuid")
                        comm_name = comm_data.get("name", "")
                        comm_summary = comm_data.get("summary", "")
                        comm_embedding = comm_data.get("embedding")
                        
                        if not comm_uuid:
                            continue
                        
                        if not comm_embedding:
                            # 如果没有向量，生成新的向量
                            comm_text = comm_summary if comm_summary else comm_name
                            comm_embedding = await embedding_client.get_embedding(comm_text)
                        
                        if comm_embedding:
                            community_vectors.append({
                                "uuid": comm_uuid,
                                "name": comm_name,
                                "group_id": group_id,
                                "content": comm_summary[:1000] if comm_summary else comm_name[:1000],
                                "embedding": comm_embedding
                            })
                    
                    if community_vectors:
                        result = self.milvus.insert_vectors(VectorType.COMMUNITY, community_vectors)
                        vectors_saved["community"] = len(result)
                        logger.info(f"Community向量保存完成: {len(result)} 个向量")
                    
                    logger.info(
                        f"Graphiti向量保存到Milvus完成: "
                        f"episode={vectors_saved['episode']}, "
                        f"entity={vectors_saved['entity']}, "
                        f"edge={vectors_saved['edge']}, "
                        f"community={vectors_saved['community']}"
                    )
                except Exception as e:
                    logger.error(f"保存Graphiti向量到Milvus失败: {e}", exc_info=True)
                    # 不抛出异常，允许继续执行
            else:
                logger.warning("Milvus不可用，跳过向量保存")
            
            return {
                "success": True,
                "episode_uuid": episode_uuid,
                "episode_id": episode_id,
                "doc_id": doc_id,
                "group_id": group_id,
                "episode_type": episode_type,
                "version": version or "v1.0",
                "template_id": template_id,  # 保存的模板ID（如果成功保存）
                "template_mode": template_mode,  # 使用的模板模式
                "entity_count": len(entities),
                "edge_count": len(edges),
                "entity_type_counts": entity_type_counts,  # 各类型实体数量统计
                "edge_type_counts": edge_type_counts,      # 各类型关系数量统计
                "vectors_saved": vectors_saved,  # 向量保存统计
                "entities": entities[:50],  # 限制返回数量
                "edges": edges[:50],
                "episode_content": episode_content,  # 返回轻量化的 Episode Content
                "dependency_analysis": dependency_analysis,  # 依赖关系分析结果
                "text_summary_reference": text_summary_reference  # Cognee TextSummary 引用关系信息
            }
            
        except ValueError as e:
            logger.error(f"参数错误: {e}")
            raise
        except Exception as e:
            logger.error(f"Graphiti Episode 创建失败: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    async def _analyze_dependencies(
        self,
        group_id: str,
        entities: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        episode_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析文档之间的依赖关系（轻量化推理）
        
        根据提取的实体和关系，推理文档之间的依赖关系：
        1. 查找 DEPENDS_ON 关系
        2. 查找 RELATES_TO 关系
        3. 根据实体类型（System, Module）推理依赖
        
        Args:
            group_id: 文档组ID
            entities: 提取的实体列表
            edges: 提取的关系列表
            episode_content: Episode 内容（包含 related_docs）
            
        Returns:
            依赖关系分析结果
        """
        from app.core.neo4j_client import neo4j_client
        
        try:
            # 1. 查找直接的 DEPENDS_ON 关系
            depends_on_query = """
            MATCH (a:Entity)-[r:DEPENDS_ON]->(b:Entity)
            WHERE r.group_id = $group_id
            RETURN a.name as source_name, b.name as target_name, 
                   labels(a) as source_labels, labels(b) as target_labels
            LIMIT 50
            """
            
            depends_on_results = neo4j_client.execute_query(depends_on_query, {
                "group_id": group_id
            })
            
            # 2. 查找 RELATES_TO 关系（可能表示依赖）
            relates_to_query = """
            MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
            WHERE r.group_id = $group_id
            RETURN a.name as source_name, b.name as target_name,
                   labels(a) as source_labels, labels(b) as target_labels
            LIMIT 50
            """
            
            relates_to_results = neo4j_client.execute_query(relates_to_query, {
                "group_id": group_id
            })
            
            # 3. 查找跨文档的依赖关系（如果 related_docs 不为空）
            cross_doc_dependencies = []
            if episode_content.get("related_docs"):
                # 查找与其他文档的关联
                for related_doc_id in episode_content["related_docs"]:
                    cross_doc_query = """
                    MATCH (e1:Episodic)-[:MENTIONS]->(ent1:Entity)
                    WHERE e1.doc_id = $doc_id
                    WITH ent1
                    MATCH (e2:Episodic)-[:MENTIONS]->(ent2:Entity)
                    WHERE e2.doc_id = $related_doc_id
                      AND (ent1)-[:DEPENDS_ON|RELATES_TO]->(ent2)
                    RETURN ent1.name as source_name, ent2.name as target_name,
                           e1.doc_id as source_doc, e2.doc_id as target_doc
                    LIMIT 10
                    """
                    
                    cross_results = neo4j_client.execute_query(cross_doc_query, {
                        "doc_id": episode_content["doc_id"],
                        "related_doc_id": related_doc_id
                    })
                    cross_doc_dependencies.extend(cross_results)
            
            # 4. 统计依赖关系
            dependency_stats = {
                "direct_dependencies": len(depends_on_results),
                "related_entities": len(relates_to_results),
                "cross_doc_dependencies": len(cross_doc_dependencies),
                "total_dependencies": len(depends_on_results) + len(relates_to_results) + len(cross_doc_dependencies)
            }
            
            return {
                "stats": dependency_stats,
                "depends_on": [
                    {
                        "source": r.get("source_name", ""),
                        "target": r.get("target_name", ""),
                        "source_type": r.get("source_labels", [])[0] if r.get("source_labels") else "Unknown",
                        "target_type": r.get("target_labels", [])[0] if r.get("target_labels") else "Unknown"
                    }
                    for r in depends_on_results[:20]  # 限制返回数量
                ],
                "relates_to": [
                    {
                        "source": r.get("source_name", ""),
                        "target": r.get("target_name", ""),
                        "source_type": r.get("source_labels", [])[0] if r.get("source_labels") else "Unknown",
                        "target_type": r.get("target_labels", [])[0] if r.get("target_labels") else "Unknown"
                    }
                    for r in relates_to_results[:20]  # 限制返回数量
                ],
                "cross_doc": cross_doc_dependencies[:10]  # 限制返回数量
            }
            
        except Exception as e:
            logger.error(f"依赖关系分析失败: {e}", exc_info=True)
            return {
                "error": str(e),
                "stats": {
                    "direct_dependencies": 0,
                    "related_entities": 0,
                    "cross_doc_dependencies": 0,
                    "total_dependencies": 0
                }
            }
    
    async def step2_cognee_build(
        self,
        upload_id: int,
        group_id: Optional[str] = None,
        provider: str = "deepseek",
        # 模板配置（cognify阶段）
        cognify_template_mode: str = "llm_generate",
        cognify_template_config_json: Optional[Dict[str, Any]] = None,
        # 模板配置（memify阶段）
        memify_template_mode: str = "default",
        memify_template_config_json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        步骤2: Cognee章节级处理
        
        构建章节级知识图谱
        """
        # 验证 provider 配置
        config_valid, config_msg = _validate_provider_config(provider)
        if not config_valid:
            logger.error(f"Provider 配置验证失败: {config_msg}")
            raise ValueError(config_msg)
        logger.info(f"Provider 配置验证通过: {config_msg}")
        
        from app.services.word_document_service import WordDocumentService
        
        db = SessionLocal()
        try:
            # 获取文档
            document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
            if not document:
                raise ValueError(f"文档不存在: upload_id={upload_id}")
            
            # 生成或获取 group_id（统一使用标准生成规则）
            if group_id:
                # 如果传入了 group_id，使用传入的（但需要验证格式）
                import re
                if not re.match(r'^[a-zA-Z0-9\-_]+$', group_id):
                    raise ValueError(f"Group ID 格式不正确，只能包含字母、数字、破折号(-)和下划线(_): {group_id}")
                # 如果文档已有 document_id 且与传入的不同，使用文档的（确保一致性）
                if document.document_id and document.document_id != group_id:
                    logger.warning(f"文档已有 document_id ({document.document_id})，但传入了不同的 group_id ({group_id})，使用文档的 document_id")
                    group_id = document.document_id
                elif not document.document_id:
                    # 如果文档没有 document_id，保存传入的 group_id
                    document.document_id = group_id
                    db.commit()
                    logger.info(f"保存传入的 group_id 到数据库: {group_id}")
            elif document.document_id:
                # 如果文档已有 document_id，使用文档的
                group_id = document.document_id
                logger.info(f"使用文档已有的 group_id: {group_id}")
            else:
                # 使用标准规则生成 group_id
                base_name = WordDocumentService._extract_base_name(document.file_name)
                safe_base_name = WordDocumentService._sanitize_group_id(base_name)
                date_str = datetime.now().strftime('%Y%m%d')
                group_id = f"doc_{safe_base_name}_{date_str}"
                
                # 保存到数据库
                document.document_id = group_id
                db.commit()
                logger.info(f"自动生成并保存 group_id: {group_id}")
            
            # 读取分块内容
            if not document.chunks_path or not os.path.exists(document.chunks_path):
                raise ValueError("文档尚未分块，请先完成文档分块")
            
            with open(document.chunks_path, 'r', encoding='utf-8') as f:
                chunks_data = json.load(f)
            
            # 获取Cognee实例并初始化
            cognee_service = CogneeService()
            await cognee_service.initialize()
            
            # 不再使用固定的 dataset_name，因为每次处理都生成新的
            
            # 准备章节数据
            chunks = chunks_data.get("chunks", [])
            sections = []
            for idx, chunk in enumerate(chunks):
                sections.append({
                    "title": chunk.get("title", f"章节_{idx+1}"),
                    "content": chunk.get("content", ""),
                    "uuid": chunk.get("uuid", f"{group_id}_chunk_{idx+1}")
                })
            
            # 构建章节级知识图谱
            build_result = await cognee_service.build_section_knowledge_graph(
                sections=sections,
                group_id=group_id,
                provider=provider,
                upload_id=upload_id,  # 传递upload_id以便保存模板
                document_name=document.file_name,  # 传递document_name以便保存模板
                cognify_template_mode=cognify_template_mode,
                cognify_template_config_json=cognify_template_config_json,
                memify_template_mode=memify_template_mode,
                memify_template_config_json=memify_template_config_json
            )
            
            # 获取dataset_name（如果build_result中有）
            dataset_name = build_result.get("dataset_name") if isinstance(build_result, dict) else None
            
            # 等待一下，确保节点已完全提交到Neo4j
            # 同时验证节点是否已创建
            import asyncio
            from app.core.neo4j_client import neo4j_client as check_neo4j
            
            max_wait = 10  # 最多等待10秒
            wait_interval = 1  # 每秒检查一次
            waited = 0
            
            while waited < max_wait:
                check_query = """
                MATCH (n)
                WHERE '__Node__' IN labels(n)
                   AND ('Entity' IN labels(n)
                   OR 'DocumentChunk' IN labels(n)
                   OR 'TextDocument' IN labels(n)
                   OR 'EntityType' IN labels(n)
                   OR 'TextSummary' IN labels(n)
                   OR 'KnowledgeNode' IN labels(n))
                RETURN count(n) as node_count
                """
                check_result = check_neo4j.execute_query(check_query)
                node_count = check_result[0]["node_count"] if check_result else 0
                
                if node_count > 0:
                    logger.info(f"检测到 {node_count} 个节点已创建，继续执行向量保存")
                    break
                
                await asyncio.sleep(wait_interval)
                waited += wait_interval
                logger.info(f"等待节点创建... ({waited}/{max_wait}秒)")
            
            if waited >= max_wait:
                logger.warning(f"等待超时，可能节点尚未创建，但继续执行向量保存")
            
            # ========== 保存 Cognee 生成的向量到 Milvus ==========
            logger.info(f"开始保存 Cognee 生成的向量到 Milvus: group_id={group_id}")
            vectors_saved = {
                "cognee_entity": 0,
                "cognee_edge": 0
            }
            
            # 检查 Milvus 是否可用
            if self.milvus.is_available():
                try:
                    # 确保 Cognee 向量集合存在
                    from app.services.milvus_service import VectorType
                    logger.info("确保 Cognee 向量集合存在...")
                    self.milvus.ensure_collections()
                    logger.info("✅ Cognee 向量集合已确保存在")
                    # 1. 查询 Cognee 生成的 KnowledgeNode（Rule、Constraint、Flow等）
                    # Cognee 创建的节点没有 dataset_name/dataset_id 属性，使用标签查询
                    knowledge_node_query = """
                    MATCH (n)
                    WHERE '__Node__' IN labels(n)
                       AND ('Entity' IN labels(n)
                       OR 'DocumentChunk' IN labels(n)
                       OR 'TextDocument' IN labels(n)
                       OR 'EntityType' IN labels(n)
                       OR 'TextSummary' IN labels(n)
                       OR 'KnowledgeNode' IN labels(n))
                    RETURN 
                        id(n) as id,
                        COALESCE(n.name, n.text, n.id, toString(id(n))) as name,
                        properties(n) as properties,
                        COALESCE(n.summary, n.name, n.text, toString(id(n))) as summary,
                        labels(n) as labels
                    """
                    
                    knowledge_nodes = neo4j_client.execute_query(knowledge_node_query)
                    
                    logger.info(f"查询到 {len(knowledge_nodes)} 个 Cognee 节点")
                    
                    # 2. 保存 KnowledgeNode 向量
                    entity_vectors = []
                    for node in knowledge_nodes:
                        node_id = node.get("id", "")
                        node_name = node.get("name", "")
                        node_summary = node.get("summary", node_name)
                        node_properties = node.get("properties", {})
                        labels = node.get("labels", [])
                        
                        # 构建用于向量化的文本（name + summary + properties）
                        vector_text = node_name
                        if node_summary and node_summary != node_name:
                            vector_text += f" {node_summary}"
                        if node_properties:
                            # 将 properties 字典转换为文本
                            props_text = ", ".join([f"{k}: {v}" for k, v in node_properties.items() if v])
                            if props_text:
                                vector_text += f" {props_text}"
                        
                        if vector_text and vector_text.strip():
                            try:
                                embedding = await embedding_client.get_embedding(vector_text)
                                if embedding:
                                    # 将 metadata 信息合并到 content 中（JSON格式）
                                    content_data = {
                                        "text": vector_text[:500],
                                        "node_id": str(node_id),
                                        "labels": labels,
                                        "properties": node_properties,
                                        "summary": node_summary
                                    }
                                    # 确保 name 字段不超过 512 字符（强制截断）
                                    safe_name = str(node_name)[:512] if node_name else ""
                                    if len(str(node_name)) > 512:
                                        logger.warning(f"节点 {node_id} 的 name 字段过长 ({len(str(node_name))} 字符)，已截断为 512 字符")
                                    
                                    entity_vectors.append({
                                        "uuid": f"{group_id}_cognee_{node_id}",
                                        "name": safe_name,  # 确保 name 不超过 512 字符
                                        "group_id": group_id,
                                        "content": json.dumps(content_data, ensure_ascii=False)[:65535],
                                        "embedding": embedding
                                    })
                            except Exception as e:
                                logger.warning(f"KnowledgeNode {node_id} 向量生成失败: {e}")
                                continue
                    
                    # 批量插入 Entity 向量
                    if entity_vectors:
                        batch_size = 50
                        for i in range(0, len(entity_vectors), batch_size):
                            batch = entity_vectors[i:i + batch_size]
                            result = self.milvus.insert_vectors(VectorType.COGNEE_ENTITY, batch)
                            vectors_saved["cognee_entity"] += len(result)
                        logger.info(f"Cognee Entity向量保存完成: {vectors_saved['cognee_entity']} 个向量")
                    
                    # 3. 查询 Cognee 生成的关系
                    # Cognee 创建的节点没有 dataset_name/dataset_id 属性，使用标签查询
                    relation_query = """
                    MATCH (a)-[r]->(b)
                    WHERE '__Node__' IN labels(a)
                       AND '__Node__' IN labels(b)
                       AND ('Entity' IN labels(a) OR 'DocumentChunk' IN labels(a) OR 'TextDocument' IN labels(a) OR 'EntityType' IN labels(a) OR 'TextSummary' IN labels(a) OR 'KnowledgeNode' IN labels(a))
                       AND ('Entity' IN labels(b) OR 'DocumentChunk' IN labels(b) OR 'TextDocument' IN labels(b) OR 'EntityType' IN labels(b) OR 'TextSummary' IN labels(b) OR 'KnowledgeNode' IN labels(b))
                    RETURN 
                        id(a) as source_id,
                        COALESCE(a.name, a.text, a.id, toString(id(a))) as source_name,
                        type(r) as relation_type,
                        id(b) as target_id,
                        COALESCE(b.name, b.text, b.id, toString(id(b))) as target_name,
                        properties(r) as relation_properties
                    """
                    
                    relations = neo4j_client.execute_query(relation_query)
                    
                    logger.info(f"查询到 {len(relations)} 个关系")
                    
                    # 4. 保存关系向量
                    edge_vectors = []
                    for rel in relations:
                        source_name = rel.get("source_name", "")
                        target_name = rel.get("target_name", "")
                        relation_type = rel.get("relation_type", "")
                        relation_properties = rel.get("relation_properties", {})
                        
                        # 构建用于向量化的文本（关系类型 + 源实体 + 目标实体）
                        vector_text = f"{relation_type}: {source_name} -> {target_name}"
                        if relation_properties:
                            props_text = ", ".join([f"{k}: {v}" for k, v in relation_properties.items() if v])
                            if props_text:
                                vector_text += f" ({props_text})"
                        
                        if vector_text and vector_text.strip():
                            try:
                                embedding = await embedding_client.get_embedding(vector_text)
                                if embedding:
                                    # 将 metadata 信息合并到 content 中（JSON格式）
                                    content_data = {
                                        "text": vector_text[:500],
                                        "source_id": str(rel.get("source_id", "")),
                                        "target_id": str(rel.get("target_id", "")),
                                        "relation_type": relation_type,
                                        "source_name": source_name,
                                        "target_name": target_name,
                                        "properties": relation_properties
                                    }
                                    # 确保 name 字段不超过 512 字符（强制截断）
                                    safe_name = str(vector_text)[:512] if vector_text else ""
                                    if len(str(vector_text)) > 512:
                                        logger.warning(f"关系向量 name 字段过长 ({len(str(vector_text))} 字符)，已截断为 512 字符")
                                    
                                    edge_vectors.append({
                                        "uuid": f"{group_id}_cognee_edge_{rel.get('source_id')}_{rel.get('target_id')}_{relation_type}",
                                        "name": safe_name,  # 确保 name 不超过 512 字符
                                        "group_id": group_id,
                                        "content": json.dumps(content_data, ensure_ascii=False)[:65535],
                                        "embedding": embedding
                                    })
                            except Exception as e:
                                logger.warning(f"关系向量生成失败: {e}")
                                continue
                    
                    # 批量插入 Edge 向量
                    if edge_vectors:
                        batch_size = 50
                        for i in range(0, len(edge_vectors), batch_size):
                            batch = edge_vectors[i:i + batch_size]
                            result = self.milvus.insert_vectors(VectorType.COGNEE_EDGE, batch)
                            vectors_saved["cognee_edge"] += len(result)
                        logger.info(f"Cognee Edge向量保存完成: {vectors_saved['cognee_edge']} 个向量")
                    
                except Exception as e:
                    logger.error(f"保存 Cognee 向量到 Milvus 失败: {e}", exc_info=True)
            else:
                logger.warning("Milvus 不可用，跳过 Cognee 向量保存")
            
            # 查询节点和关系数量
            # Cognee创建的节点没有dataset_name/dataset_id/group_id属性，需要使用标签查询
            # 由于Cognee的节点可能属于多个dataset，我们查询所有Cognee节点
            query = """
            MATCH (n)
            WHERE '__Node__' IN labels(n)
               AND ('Entity' IN labels(n)
               OR 'DocumentChunk' IN labels(n)
               OR 'TextDocument' IN labels(n)
               OR 'EntityType' IN labels(n)
               OR 'TextSummary' IN labels(n)
               OR 'KnowledgeNode' IN labels(n))
            WITH count(n) as node_count
            MATCH (a)-[r]->(b)
            WHERE '__Node__' IN labels(a)
               AND '__Node__' IN labels(b)
               AND ('Entity' IN labels(a) OR 'DocumentChunk' IN labels(a) OR 'TextDocument' IN labels(a) OR 'EntityType' IN labels(a) OR 'TextSummary' IN labels(a) OR 'KnowledgeNode' IN labels(a))
               AND ('Entity' IN labels(b) OR 'DocumentChunk' IN labels(b) OR 'TextDocument' IN labels(b) OR 'EntityType' IN labels(b) OR 'TextSummary' IN labels(b) OR 'KnowledgeNode' IN labels(b))
            RETURN node_count, count(r) as relationship_count
            """
            
            result = neo4j_client.execute_query(query)
            
            node_count = result[0].get("node_count", 0) if result else 0
            relationship_count = result[0].get("relationship_count", 0) if result else 0
            
            return {
                "group_id": group_id,  # 返回生成的或使用的 group_id
                "node_count": node_count,
                "relationship_count": relationship_count,
                "vectors_saved": vectors_saved,
                "dataset_name": dataset_name  # Cognee的dataset_name
            }
            
        finally:
            db.close()
    
    async def step3_milvus_vectorize(
        self,
        upload_id: int,
        group_id: str
    ) -> Dict[str, Any]:
        """
        步骤3: Milvus向量化处理（优化版）
        
        根据实施方案，实现以下功能：
        1. 文档摘要向量化（DOCUMENT_SUMMARY）
        2. 章节向量化（SECTION）- 核心功能，用于快速召回
        3. 图片向量化（IMAGE）- 可选
        4. 表格向量化（TABLE）- 可选
        
        注意：
        - 流程/规则向量化已在步骤2中完成（保存到Cognee_entity_vectors），此处不再重复
        - Requirement向量化已在步骤2中完成（保存到graphiti_entity_vectors），此处不再重复
        
        优化点：
        - 添加完善的元数据（doc_id, section_index, section_level等）
        - 批量插入优化
        - 错误处理和日志完善
        """
        db = SessionLocal()
        try:
            # 获取文档
            document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
            if not document:
                raise ValueError(f"文档不存在: upload_id={upload_id}")
            
            # 检查 Milvus 是否可用
            if not self.milvus.is_available():
                raise ValueError("Milvus 不可用，请检查配置")
            
            # 读取解析后的内容
            parsed_content_path = document.parsed_content_path
            if not parsed_content_path or not os.path.exists(parsed_content_path):
                raise ValueError("文档尚未解析，请先完成文档解析")
            
            # 读取分块内容
            chunks = []
            chunks_data = None
            if document.chunks_path and os.path.exists(document.chunks_path):
                with open(document.chunks_path, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)
                    chunks = chunks_data.get("chunks", [])
            
            if not chunks:
                logger.warning(f"文档 {upload_id} 没有分块数据，跳过章节向量化")
            
            vectors_inserted = {
                "summary": 0,
                "chunks": 0,
                "images": 0,
                "tables": 0
            }
            
            doc_id = f"DOC_{upload_id}"
            
            # ========== 1. 文档摘要向量化 ==========
            logger.info(f"开始处理文档摘要向量化: upload_id={upload_id}")
            if document.summary_content_path and os.path.exists(document.summary_content_path):
                try:
                    with open(document.summary_content_path, 'r', encoding='utf-8') as f:
                        summary = f.read()
                    
                    if summary and summary.strip():
                        embedding = await embedding_client.get_embedding(summary)
                        if embedding:
                            result = self.milvus.insert_vectors(
                                VectorType.DOCUMENT_SUMMARY,
                                [{
                                    "uuid": f"{group_id}_summary",
                                    "name": f"{document.file_name}_摘要",
                                    "group_id": group_id,
                                    "content": summary[:500],  # 限制长度
                                    "embedding": embedding
                                }]
                            )
                            vectors_inserted["summary"] = len(result)
                            logger.info(f"文档摘要向量化完成: {len(result)} 个向量")
                except Exception as e:
                    logger.error(f"文档摘要向量化失败: {e}", exc_info=True)
            
            # ========== 2. 章节（Chunks）向量化 - 核心功能 ==========
            logger.info(f"开始处理章节向量化: {len(chunks)} 个章节")
            if chunks:
                try:
                    chunk_vectors = []
                    batch_size = 10  # 批量插入大小
                    
                    for idx, chunk in enumerate(chunks):
                        chunk_content = chunk.get("content", "")
                        chunk_title = chunk.get("title", f"章节_{idx+1}")
                        chunk_uuid = chunk.get("uuid") or chunk.get("chunk_id") or f"{group_id}_chunk_{idx+1}"
                        
                        if not chunk_content or not chunk_content.strip():
                            logger.warning(f"章节 {idx+1} 内容为空，跳过")
                            continue
                        
                        try:
                            # 生成向量
                            embedding = await embedding_client.get_embedding(chunk_content)
                            if not embedding:
                                logger.warning(f"章节 {idx+1} 向量生成失败，跳过")
                                continue
                            
                            # 构建向量数据（添加完善的元数据）
                            # 注意：MilvusService 当前只支持固定字段，元数据存储在 content 的 JSON 中
                            # 为了保持兼容性，content 字段存储 JSON，包含文本和元数据
                            content_data = {
                                "text": chunk_content[:1500],  # 实际文本内容（限制1500字符，为JSON格式留空间）
                                "doc_id": doc_id,
                                "section_index": idx,
                                "section_level": chunk.get("level", 1),
                                "section_start_index": chunk.get("start_index", 0),
                                "section_end_index": chunk.get("end_index", 0),
                                "token_count": chunk.get("token_count", 0),
                                "title": chunk_title
                            }
                            content_json = json.dumps(content_data, ensure_ascii=False)
                            
                            # 确保不超过 Milvus VARCHAR 字段的最大长度（65535）
                            if len(content_json) > 65535:
                                # 如果超过，只保留文本内容
                                content_json = chunk_content[:65530]
                                logger.warning(f"章节 {idx+1} 内容过长，已截断元数据")
                            
                            chunk_vector = {
                                "uuid": chunk_uuid,
                                "name": chunk_title,
                                "group_id": group_id,
                                "content": content_json,
                                "embedding": embedding
                            }
                            
                            chunk_vectors.append(chunk_vector)
                            
                            # 批量插入（每 batch_size 个插入一次）
                            if len(chunk_vectors) >= batch_size:
                                result = self.milvus.insert_vectors(VectorType.SECTION, chunk_vectors)
                                vectors_inserted["chunks"] += len(result)
                                logger.info(f"批量插入章节向量: {len(result)} 个（累计: {vectors_inserted['chunks']}）")
                                chunk_vectors = []  # 清空批量列表
                        
                        except Exception as e:
                            logger.error(f"处理章节 {idx+1} 失败: {e}", exc_info=True)
                            continue
                    
                    # 插入剩余的章节向量
                    if chunk_vectors:
                        result = self.milvus.insert_vectors(VectorType.SECTION, chunk_vectors)
                        vectors_inserted["chunks"] += len(result)
                        logger.info(f"插入剩余章节向量: {len(result)} 个（累计: {vectors_inserted['chunks']}）")
                    
                    logger.info(f"章节向量化完成: 共 {vectors_inserted['chunks']} 个向量")
                
                except Exception as e:
                    logger.error(f"章节向量化失败: {e}", exc_info=True)
            
            # ========== 3. 图片向量化（根据实施方案步骤6）==========
            logger.info(f"开始处理图片向量化: group_id={group_id}")
            try:
                # 从 structured_content.json 中读取图片数据
                images = []
                if document.structured_content_path and os.path.exists(document.structured_content_path):
                    with open(document.structured_content_path, 'r', encoding='utf-8') as f:
                        structured_content = json.load(f)
                    
                    # 从 structured_content 中提取图片
                    for item in structured_content:
                        if item.get("type") == "image" or item.get("type") == "image_only":
                            if item.get("images"):
                                images.extend(item.get("images", []))
                            elif item.get("type") == "image":
                                # 单个图片项
                                images.append(item)
                
                # 如果没有从 structured_content 中找到，尝试从 parsed_content 中提取
                if not images and document.parsed_content_path and os.path.exists(document.parsed_content_path):
                    # 尝试从解析后的文档中提取图片信息（备用方案）
                    logger.debug("尝试从 parsed_content 中提取图片信息")
                
                logger.info(f"读取到 {len(images)} 张图片")
                
                image_vectors = []
                for idx, img in enumerate(images):
                    image_path = img.get("file_path", "") or img.get("relative_path", "")
                    image_id = img.get("image_id", f"image_{idx+1}")
                    image_title = img.get("description", img.get("title", f"图片_{idx+1}"))
                    
                    # 方案2：使用 OCR 提取图片文字（如果图片路径存在）
                    image_text = ""
                    if image_path:
                        # 构建绝对路径
                        abs_image_path = image_path if os.path.isabs(image_path) else os.path.join("/app", image_path)
                        
                        if os.path.exists(abs_image_path):
                            try:
                                # 尝试使用 OCR 提取文字
                                image_text = await self._extract_image_text(abs_image_path)
                                if not image_text:
                                    # 如果没有 OCR 文字，使用图片描述
                                    image_text = img.get("description", "") or img.get("title", "")
                            except Exception as e:
                                logger.warning(f"图片 OCR 失败: {abs_image_path}, 错误: {e}，使用描述文本")
                                image_text = img.get("description", "") or img.get("title", "")
                        else:
                            logger.warning(f"图片文件不存在: {abs_image_path}，使用描述文本")
                            image_text = img.get("description", "") or img.get("title", "")
                    else:
                        # 如果没有图片路径，使用描述文本
                        image_text = img.get("description", "") or img.get("title", "")
                    
                    if image_text and image_text.strip():
                        try:
                            embedding = await embedding_client.get_embedding(image_text)
                            if embedding:
                                # 构建图片向量数据
                                image_metadata = {
                                    "image_path": image_path,
                                    "image_id": image_id,
                                    "description": img.get("description", ""),
                                    "file_format": img.get("file_format", ""),
                                    "file_size": img.get("file_size", 0),
                                    "doc_id": doc_id
                                }
                                
                                image_vectors.append({
                                    "uuid": img.get("uuid", f"{group_id}_image_{idx+1}"),
                                    "name": image_title,
                                    "group_id": group_id,
                                    "content": image_text[:2000],  # 限制长度
                                    "embedding": embedding,
                                    "metadata": image_metadata  # 存储图片元数据
                                })
                        except Exception as e:
                            logger.error(f"图片 {idx+1} 向量化失败: {e}", exc_info=True)
                            continue
                
                if image_vectors:
                    result = self.milvus.insert_vectors(VectorType.IMAGE, image_vectors)
                    vectors_inserted["images"] = len(result)
                    logger.info(f"图片向量化完成: {len(result)} 个向量")
                else:
                    logger.info("没有有效的图片向量")
                    
            except Exception as e:
                logger.error(f"图片向量化失败: {e}", exc_info=True)
            
            # ========== 4. 表格向量化（根据实施方案步骤6）==========
            logger.info(f"开始处理表格向量化: group_id={group_id}")
            try:
                # 从 structured_content.json 中读取表格数据
                tables = []
                if document.structured_content_path and os.path.exists(document.structured_content_path):
                    with open(document.structured_content_path, 'r', encoding='utf-8') as f:
                        structured_content = json.load(f)
                    
                    # 从 structured_content 中提取表格
                    for item in structured_content:
                        if item.get("type") == "table":
                            table_data = item.get("data", {})
                            if table_data:
                                tables.append(table_data)
                
                logger.info(f"读取到 {len(tables)} 个表格")
                
                table_vectors = []
                for idx, tbl in enumerate(tables):
                    table_id = tbl.get("table_id", f"table_{idx+1}")
                    table_title = tbl.get("title", f"表格_{idx+1}")
                    
                    # 方案2：将表格转换为结构化文本
                    table_text = self._format_table_as_text(tbl)
                    
                    if table_text and table_text.strip():
                        try:
                            embedding = await embedding_client.get_embedding(table_text)
                            if embedding:
                                # 构建表格向量数据
                                table_metadata = {
                                    "table_id": table_id,
                                    "table_data": tbl,  # 保留原始表格数据
                                    "headers": tbl.get("headers", []),
                                    "row_count": len(tbl.get("rows", [])),
                                    "doc_id": doc_id
                                }
                                
                                table_vectors.append({
                                    "uuid": tbl.get("uuid", f"{group_id}_table_{idx+1}"),
                                    "name": table_title,
                                    "group_id": group_id,
                                    "content": table_text[:2000],  # 限制长度
                                    "embedding": embedding,
                                    "metadata": table_metadata  # 存储表格元数据
                                })
                        except Exception as e:
                            logger.error(f"表格 {idx+1} 向量化失败: {e}", exc_info=True)
                            continue
                
                if table_vectors:
                    result = self.milvus.insert_vectors(VectorType.TABLE, table_vectors)
                    vectors_inserted["tables"] = len(result)
                    logger.info(f"表格向量化完成: {len(result)} 个向量")
                else:
                    logger.info("没有有效的表格向量")
                    
            except Exception as e:
                logger.error(f"表格向量化失败: {e}", exc_info=True)
            
            total_count = sum(vectors_inserted.values())
            
            logger.info(
                f"Milvus 向量化处理完成: upload_id={upload_id}, group_id={group_id}, "
                f"总计={total_count} 个向量 "
                f"(摘要={vectors_inserted['summary']}, "
                f"章节={vectors_inserted['chunks']}, "
                f"图片={vectors_inserted['images']}, "
                f"表格={vectors_inserted['tables']})"
            )
            
            return {
                "success": True,
                "upload_id": upload_id,
                "group_id": group_id,
                "doc_id": doc_id,
                "summary_vector_count": vectors_inserted["summary"],
                "chunk_vector_count": vectors_inserted["chunks"],
                "image_vector_count": vectors_inserted["images"],
                "table_vector_count": vectors_inserted["tables"],
                "total_vector_count": total_count
            }
            
        except ValueError as e:
            logger.error(f"参数错误: {e}")
            raise
        except Exception as e:
            logger.error(f"Milvus 向量化处理失败: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    # ==================== 检索生成流程 ====================
    
    async def step4_milvus_recall(
        self,
        query: str,
        top_k: int = 50,
        group_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        步骤4: Milvus快速召回
        
        向量相似性检索，返回Top K相似结果
        """
        # 获取查询向量
        query_embedding = await embedding_client.get_embedding(query)
        if not query_embedding:
            return {
                "total_count": 0,
                "results": [],
                "requirement_count": 0,
                "rule_count": 0,
                "flow_count": 0
            }
        
        # 搜索所有向量类型
        # 包括：Entity（实体）、Episode（文档级）、Section（章节）、Edge（关系）、Community（社区）
        all_results = []
        
        # 搜索所有向量类型
        vector_types_to_search = [
            VectorType.ENTITY,      # Graphiti实体 + Cognee规则/流程
            VectorType.EPISODE,    # Graphiti Episode（文档级别的事件元数据+章节标题）
            VectorType.DOCUMENT_SUMMARY,     # 文档摘要
            VectorType.SECTION,     # 文档章节（chunks）
            VectorType.EDGE,        # Graphiti关系
            VectorType.COMMUNITY,   # Graphiti社区
            VectorType.IMAGE,       # 图片（新增）
            VectorType.TABLE        # 表格（新增）
        ]
        
        for vector_type in vector_types_to_search:
            results = self.milvus.search_vectors(
                vector_type=vector_type,
                query_embedding=query_embedding,
                top_k=top_k,  # 每个类型取top_k，最后合并后再取top_k
                group_ids=group_ids,
                min_score=0.3  # 降低阈值以获取更多结果
            )
            
            for sr in results:
                all_results.append({
                    "uuid": sr.uuid,
                    "name": sr.name,
                    "content": sr.content or sr.name,
                    "score": float(sr.score),
                    "type": sr.vector_type.value,  # entity/episode/section/edge/community
                    "group_id": sr.group_id,
                    "metadata": sr.metadata or {}
                })
        
        # 按分数排序
        all_results.sort(key=lambda x: x["score"], reverse=True)
        all_results = all_results[:top_k]  # 最终取Top K
        
        # 批量判断来源（优化性能）
        self._batch_determine_sources(all_results, group_ids)
        
        # 按来源分类统计
        graphiti_results = [r for r in all_results if r.get("source") == "graphiti"]
        cognee_results = [r for r in all_results if r.get("source") == "cognee"]
        milvus_results = [r for r in all_results if r.get("source") == "milvus"]
        
        # 统计各类型数量（支持中英文关键词匹配）
        # Requirement: 检查name/content中是否包含"需求"或"requirement"
        requirement_count = sum(1 for r in all_results 
            if ("需求" in r.get("name", "") or "需求" in r.get("content", "") or 
                "requirement" in r.get("name", "").lower() or "requirement" in r.get("content", "").lower() or
                r.get("type") == "requirement"))
        
        # Rule: 检查name/content中是否包含"规则"或"rule"，或type为rule
        rule_count = sum(1 for r in all_results 
            if ("规则" in r.get("name", "") or "规则" in r.get("content", "") or
                "rule" in r.get("name", "").lower() or "rule" in r.get("content", "").lower() or
                r.get("type") == "rule"))
        
        # Flow: 检查name/content中是否包含"流程"或"flow"，或type为flow
        flow_count = sum(1 for r in all_results 
            if ("流程" in r.get("name", "") or "流程" in r.get("content", "") or
                "flow" in r.get("name", "").lower() or "flow" in r.get("content", "").lower() or
                r.get("type") == "flow"))
        
        # 统计各向量类型数量
        entity_count = sum(1 for r in all_results if r.get("type") == "entity")
        episode_count = sum(1 for r in all_results if r.get("type") == "episode")
        section_count = sum(1 for r in all_results if r.get("type") == "section")
        edge_count = sum(1 for r in all_results if r.get("type") == "edge")
        community_count = sum(1 for r in all_results if r.get("type") == "community")
        image_count = sum(1 for r in all_results if r.get("type") == "image")
        table_count = sum(1 for r in all_results if r.get("type") == "table")
        
        return {
            "total_count": len(all_results),
            "results": all_results,
            # 按来源分类的结果
            "graphiti_results": graphiti_results,
            "cognee_results": cognee_results,
            "milvus_results": milvus_results,
            # 来源统计
            "graphiti_count": len(graphiti_results),
            "cognee_count": len(cognee_results),
            "milvus_count": len(milvus_results),
            # 业务类型统计
            "requirement_count": requirement_count,
            "rule_count": rule_count,
            "flow_count": flow_count,
            # 向量类型统计
            "entity_count": entity_count,
            "episode_count": episode_count,
            "section_count": section_count,
            "edge_count": edge_count,
            "community_count": community_count,
            "image_count": image_count,      # 新增
            "table_count": table_count       # 新增
        }
    
    async def _extract_image_text(self, image_path: str) -> str:
        """
        提取图片中的文字（OCR）
        
        方案2：使用 OCR 提取图片文字
        如果 OCR 不可用，返回空字符串
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            提取的文字内容
        """
        try:
            # 尝试使用 pytesseract 进行 OCR
            try:
                from PIL import Image
                import pytesseract
                
                # 检查图片文件是否存在
                if not os.path.exists(image_path):
                    logger.warning(f"图片文件不存在: {image_path}")
                    return ""
                
                # 打开图片
                image = Image.open(image_path)
                
                # 使用 OCR 提取文字（支持中文）
                # 注意：需要安装 tesseract 和中文语言包
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                
                if text and text.strip():
                    logger.debug(f"图片 OCR 成功: {image_path}, 提取文字长度: {len(text)}")
                    return text.strip()
                else:
                    logger.debug(f"图片 OCR 未提取到文字: {image_path}")
                    return ""
                    
            except ImportError:
                logger.warning("pytesseract 未安装，跳过 OCR，使用图片描述")
                return ""
            except Exception as e:
                logger.warning(f"图片 OCR 失败: {image_path}, 错误: {e}")
                return ""
                
        except Exception as e:
            logger.error(f"提取图片文字失败: {e}", exc_info=True)
            return ""
    
    def _format_table_as_text(self, table_data: dict) -> str:
        """
        将表格数据转换为结构化文本
        
        方案2：表格结构化文本 + 向量化
        
        Args:
            table_data: 表格数据字典
            
        Returns:
            结构化文本
        """
        try:
            text_parts = []
            
            # 表格标题
            title = table_data.get("title", "")
            if title:
                text_parts.append(f"表格标题：{title}")
            
            # 表头
            headers = table_data.get("headers", [])
            if headers:
                text_parts.append(f"表头：{', '.join(str(h) for h in headers)}")
            
            # 数据行
            rows = table_data.get("rows", [])
            if rows:
                text_parts.append("数据：")
                for idx, row in enumerate(rows[:50], 1):  # 限制最多50行
                    row_text = ', '.join(str(cell) for cell in row if cell)
                    text_parts.append(f"  行{idx}: {row_text}")
                
                if len(rows) > 50:
                    text_parts.append(f"  ...（共 {len(rows)} 行，仅显示前50行）")
            
            result = "\n".join(text_parts)
            
            # 限制总长度（为向量化留空间）
            if len(result) > 2000:
                result = result[:2000] + "..."
            
            return result
            
        except Exception as e:
            logger.error(f"格式化表格文本失败: {e}", exc_info=True)
            return table_data.get("title", "表格") or "表格"
    
    def _batch_determine_sources(self, results: List[Dict[str, Any]], group_ids: Optional[List[str]]) -> None:
        """
        批量判断结果的来源（优化性能）
        
        避免对每个结果单独查询Neo4j，而是批量查询
        """
        # 先快速判断：Section直接归为Milvus，Episode/Edge/Community归为Graphiti
        for result in results:
            result_type = result.get("type", "")
            
            if result_type == "section":
                result["source"] = "milvus"
            elif result_type in ["episode", "edge", "community"]:
                result["source"] = "graphiti"
            else:
                # Entity类型需要进一步判断，先标记为待判断
                result["source"] = None
        
        # 收集需要判断的Entity的uuid和group_id
        entity_uuids_to_check = []
        entity_group_ids = set()
        
        for result in results:
            if result.get("source") is None:  # 待判断的Entity
                uuid = result.get("uuid", "")
                group_id = result.get("group_id", "")
                if uuid and group_id:
                    entity_uuids_to_check.append({
                        "uuid": uuid,
                        "group_id": group_id,
                        "result": result
                    })
                    entity_group_ids.add(group_id)
        
        # 如果没有需要判断的Entity，直接返回
        if not entity_uuids_to_check:
            # 将所有None设置为graphiti（默认）
            for result in results:
                if result.get("source") is None:
                    result["source"] = "graphiti"
            return
        
        # 批量查询Cognee节点（一次性查询所有group_id）
        try:
            # 使用 group_id 列表查询所有相关的节点
            # 批量查询：查找所有可能是Cognee节点的Entity
            cognee_query = """
            MATCH (n)
            WHERE (n.uuid IN $uuids OR n.id IN $uuids)
              AND '__Node__' IN labels(n)
              AND (
                n.group_id IN $group_ids
                OR any(gid IN $group_ids WHERE n.dataset_name CONTAINS gid)
                OR any(gid IN $group_ids WHERE n.dataset_id CONTAINS gid)
              )
            RETURN n.uuid as uuid, n.id as id, n.dataset_name as dataset_name
            """
            
            uuids = [item["uuid"] for item in entity_uuids_to_check]
            cognee_results = neo4j_client.execute_query(cognee_query, {
                "uuids": uuids,
                "group_ids": entity_group_ids
            })
            
            # 构建Cognee节点集合
            cognee_uuids = set()
            for cognee_result in cognee_results:
                uuid = cognee_result.get("uuid") or cognee_result.get("id")
                if uuid:
                    cognee_uuids.add(str(uuid))
            
            # 判断每个Entity的来源
            for item in entity_uuids_to_check:
                result = item["result"]
                uuid = item["uuid"]
                
                # 检查metadata
                metadata = result.get("metadata", {})
                if metadata.get("source") == "cognee":
                    result["source"] = "cognee"
                    continue
                
                # 检查是否在Cognee节点集合中
                if uuid in cognee_uuids:
                    result["source"] = "cognee"
                else:
                    # 检查关键词（快速判断）
                    name = result.get("name", "").lower()
                    content = result.get("content", "").lower()
                    cognee_keywords = ["规则", "流程", "约束", "rule", "flow", "constraint"]
                    
                    # 如果包含关键词，可能是Cognee，但为了性能，默认归为Graphiti
                    # 只有在Neo4j中确认是Cognee节点时才标记为Cognee
                    result["source"] = "graphiti"
        
        except Exception as e:
            logger.warning(f"批量判断来源失败: {e}，默认归为Graphiti")
            # 出错时默认归为Graphiti
            for result in results:
                if result.get("source") is None:
                    result["source"] = "graphiti"
    
    def _determine_result_source(self, search_result, vector_type: VectorType, group_ids: Optional[List[str]]) -> str:
        """
        判断召回结果的来源
        
        Returns:
            "graphiti": Graphiti创建的知识图谱（Entity, Episode, Edge, Community）
            "cognee": Cognee创建的章节级知识图谱（Rule, Flow, Constraint等）
            "milvus": Milvus直接存储的向量（Section章节向量）
        """
        # Section向量直接来自Milvus存储的chunks
        if vector_type == VectorType.SECTION:
            return "milvus"
        
        # Document Summary向量来自文档摘要（非Graphiti）
        if vector_type == VectorType.DOCUMENT_SUMMARY:
            return "document"
        
        # Episode、Edge、Community通常来自Graphiti
        if vector_type in [VectorType.EPISODE, VectorType.EDGE, VectorType.COMMUNITY]:
            return "graphiti"
        
        # Entity类型需要判断：可能是Graphiti Entity或Cognee节点
        if vector_type == VectorType.ENTITY:
            uuid = search_result.uuid
            group_id = search_result.group_id
            
            # 如果uuid包含特定模式，可能是Cognee节点
            # Cognee节点的uuid通常包含rule/flow等标识，或者通过metadata判断
            metadata = search_result.metadata or {}
            
            # 检查metadata中是否有Cognee标识
            if metadata.get("source") == "cognee":
                return "cognee"
            
            # 检查name或content中是否包含Cognee特有的关键词
            name = search_result.name or ""
            content = search_result.content or ""
            
            # Cognee通常处理规则、流程、约束等
            cognee_keywords = ["规则", "流程", "约束", "rule", "flow", "constraint"]
            if any(keyword in name.lower() or keyword in content.lower() for keyword in cognee_keywords):
                # 进一步通过Neo4j确认
                try:
                    # 使用 group_id 查询所有相关的节点
                    cognee_query = """
                    MATCH (n)
                    WHERE (n.uuid = $uuid OR n.id = $uuid)
                      AND '__Node__' IN labels(n)
                      AND (
                          n.group_id = $group_id
                          OR (n.dataset_name IS NOT NULL AND n.dataset_name CONTAINS $group_id)
                          OR (n.dataset_id IS NOT NULL AND n.dataset_id CONTAINS $group_id)
                      )
                    RETURN n
                    LIMIT 1
                    """
                    
                    cognee_result = neo4j_client.execute_query(cognee_query, {
                        "uuid": uuid,
                        "group_id": group_id
                    })
                    
                    if cognee_result:
                        return "cognee"
                except Exception as e:
                    logger.debug(f"查询Cognee节点失败: {e}")
            
            # 默认归为Graphiti
            return "graphiti"
        
        # 默认归为Graphiti
        return "graphiti"
    
    async def step5_neo4j_refine(
        self,
        query: str,
        recall_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        步骤5: Neo4j精筛
        
        使用Graphiti和Cognee联合查询，精筛Milvus召回结果
        """
        if not recall_results:
            return {
                "original_count": 0,
                "refined_count": 0,
                "refined_results": []
            }
        
        refined_results = []
        
        for result in recall_results:
            uuid = result.get("uuid", "")
            group_id = result.get("group_id", "")
            content = result.get("content", "")
            
            # 查询Graphiti Entity的详细信息
            graphiti_query = """
            MATCH (n:Entity)
            WHERE n.uuid = $uuid OR n.group_id = $group_id
            OPTIONAL MATCH (n)-[r:RELATES_TO]->(related:Entity)
            WHERE r.group_id = $group_id
            RETURN n, collect(DISTINCT related) as related_entities
            LIMIT 1
            """
            
            graphiti_result = neo4j_client.execute_query(graphiti_query, {
                "uuid": uuid,
                "group_id": group_id
            })
            
            # 查询Cognee节点的详细信息
            cognee_query = """
            MATCH (n)
            WHERE (n.id = $uuid OR n.name = $name OR n.content CONTAINS $content)
              AND '__Node__' IN labels(n)
              AND (
                n.group_id = $group_id
                OR (n.dataset_name IS NOT NULL AND n.dataset_name CONTAINS $group_id)
                OR (n.dataset_id IS NOT NULL AND n.dataset_id CONTAINS $group_id)
              )
            OPTIONAL MATCH (n)-[r]->(related)
            WHERE '__Node__' IN labels(related)
              AND (
                related.group_id = $group_id
                OR (related.dataset_name IS NOT NULL AND related.dataset_name CONTAINS $group_id)
                OR (related.dataset_id IS NOT NULL AND related.dataset_id CONTAINS $group_id)
              )
            RETURN n, collect(DISTINCT related) as related_nodes
            LIMIT 1
            """
            
            # 使用 group_id 查询所有相关的节点
            cognee_result = neo4j_client.execute_query(cognee_query, {
                "uuid": uuid,
                "name": result.get("name", ""),
                "content": content[:100],
                "group_id": group_id
            })
            
            # 构建精筛结果
            refined_item = {
                **result,
                "filter_reason": None,
                "graph_path": None
            }
            
            # 如果找到Graphiti或Cognee的关联，标记为同系统/同业务能力
            if graphiti_result or cognee_result:
                refined_item["filter_reason"] = "图关联匹配"
                refined_results.append(refined_item)
        
        # 统计
        same_system_count = sum(1 for r in refined_results if r.get("filter_reason") == "图关联匹配")
        same_capability_count = same_system_count  # 简化处理
        conflict_rule_count = 0  # 需要更复杂的逻辑来检测冲突
        
        return {
            "original_count": len(recall_results),
            "refined_count": len(refined_results),
            "refined_results": refined_results,
            "same_system_count": same_system_count,
            "same_capability_count": same_capability_count,
            "conflict_rule_count": conflict_rule_count
        }
    
    async def step6_mem0_inject(
        self,
        query: str,
        refined_results: List[Dict[str, Any]],
        user_id: str,
        session_id: Optional[str] = None,
        provider: str = "deepseek"
    ) -> Dict[str, Any]:
        """
        步骤6: Mem0记忆注入
        
        检索用户偏好、会话上下文、反馈记忆，注入到检索结果
        
        Args:
            query: 查询文本
            refined_results: 精细处理后的检索结果
            user_id: 用户ID
            session_id: 会话ID（可选）
            provider: LLM提供商（默认 "deepseek"）
        """
        try:
            # 延迟导入mem0，只在需要时才导入
            from app.core.mem0_client import get_mem0_client
            mem0 = get_mem0_client(provider=provider)
            
            # 检索记忆
            memories = mem0.search(query, limit=5)
            
            # 注入记忆到结果
            injected_results = []
            for result in refined_results:
                injected_item = {
                    **result,
                    "memory_injection": None,
                    "preference_match": 0.0
                }
                
                # 检查是否有匹配的记忆
                for memory in memories:
                    if memory.get("content") and query.lower() in memory.get("content", "").lower():
                        injected_item["memory_injection"] = memory.get("content", "")
                        injected_item["preference_match"] = 0.8  # 简化处理
                        break
                
                injected_results.append(injected_item)
            
            # 统计记忆类型
            user_preference_count = sum(1 for m in memories if m.get("type") == "user_preference")
            session_context_count = sum(1 for m in memories if m.get("type") == "session_context")
            feedback_count = sum(1 for m in memories if m.get("type") == "feedback")
            
            return {
                "injected_count": len(injected_results),
                "injected_results": injected_results,
                "memories": memories,
                "user_preference_count": user_preference_count,
                "session_context_count": session_context_count,
                "feedback_count": feedback_count
            }
            
        except ImportError as e:
            logger.warning(f"Mem0模块未安装，跳过记忆注入: {e}")
            # 如果Mem0未安装，返回原始结果
            return {
                "injected_count": len(refined_results),
                "injected_results": refined_results,
                "memories": [],
                "user_preference_count": 0,
                "session_context_count": 0,
                "feedback_count": 0,
                "warning": "Mem0模块未安装，已跳过记忆注入"
            }
        except Exception as e:
            logger.error(f"Mem0记忆注入失败: {e}", exc_info=True)
            # 如果Mem0失败，返回原始结果
            return {
                "injected_count": len(refined_results),
                "injected_results": refined_results,
                "memories": [],
                "user_preference_count": 0,
                "session_context_count": 0,
                "feedback_count": 0,
                "error": f"Mem0记忆注入失败: {str(e)}"
            }
    
    async def mem0_chat(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        provider: str = "deepseek"
    ) -> Dict[str, Any]:
        """
        Mem0 独立问答接口
        
        用于验证 Mem0 的上下文管理能力：
        1. 检索 Mem0 记忆（展示检索到的记忆）
        2. 使用 LLM 生成回答（结合记忆和对话历史）
        3. 保存对话到 Mem0
        4. 返回回答、检索到的记忆、对话历史
        
        Args:
            query: 用户问题
            user_id: 用户ID（必需）
            session_id: 会话ID（可选，用于会话级上下文）
            conversation_history: 对话历史（可选，格式：[{"role": "user", "content": "..."}, ...]）
            provider: LLM提供商（默认 "deepseek"）
            
        Returns:
            包含以下字段的字典：
            - answer: 生成的回答
            - memories: 检索到的记忆列表
            - memory_count: 记忆数量
            - conversation_history: 更新后的对话历史
        """
        try:
            # 延迟导入mem0，只在需要时才导入
            from app.core.mem0_client import get_mem0_client
            mem0 = get_mem0_client(provider=provider)
            
            # 1. 检索 Mem0 记忆
            logger.info(f"检索 Mem0 记忆: query='{query[:50]}...', user_id={user_id}")
            memories_result = mem0.search(query=query, user_id=user_id, limit=5)
            
            # 处理返回格式（Mem0 返回 {"results": [...]} 或直接返回列表）
            memories = []
            if isinstance(memories_result, dict) and "results" in memories_result:
                memories = memories_result["results"]
            elif isinstance(memories_result, list):
                memories = memories_result
            else:
                logger.warning(f"Mem0 search 返回格式异常: {type(memories_result)}")
                memories = []
            
            logger.info(f"检索到 {len(memories)} 条相关记忆")
            
            # 2. 构建记忆上下文
            memory_context = ""
            if memories:
                memory_context = "相关记忆：\n"
                for i, mem in enumerate(memories, 1):
                    # Mem0 返回格式可能是 {"memory": "...", "metadata": {...}, "score": ...}
                    memory_text = mem.get("memory", "") or mem.get("content", "") or str(mem)
                    score = mem.get("score", 0.0)
                    memory_context += f"{i}. {memory_text}"
                    if score:
                        memory_context += f" (相关性: {score:.2f})"
                    memory_context += "\n"
            
            # 3. 构建对话历史上下文
            history_context = ""
            if conversation_history:
                history_context = "对话历史：\n"
                for msg in conversation_history[-5:]:  # 只取最近5轮对话
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        history_context += f"用户: {content}\n"
                    elif role == "assistant":
                        history_context += f"助手: {content}\n"
            
            # 4. 构建消息列表
            system_prompt = """你是一个智能助手，能够基于用户的记忆和对话历史来回答问题。
请根据以下信息回答用户的问题：
1. 如果提供了相关记忆，请优先考虑这些记忆信息
2. 如果提供了对话历史，请保持对话的连贯性
3. 回答要准确、友好、有帮助"""
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # 构建用户消息内容（包含记忆、对话历史和当前问题）
            user_content_parts = []
            
            if memory_context:
                user_content_parts.append(memory_context)
            if history_context:
                user_content_parts.append(history_context)
            
            user_content_parts.append(f"用户问题：{query}")
            
            # 将所有内容合并为一个用户消息
            user_content = "\n\n".join(user_content_parts)
            messages.append({"role": "user", "content": user_content})
            
            # 6. 调用 LLM 生成回答
            logger.info(f"调用 LLM 生成回答: provider={provider}")
            answer = await self.llm_client.chat(
                provider=provider,
                messages=messages
            )
            
            logger.info(f"LLM 生成回答完成，长度: {len(answer)}")
            
            # 7. 保存对话到 Mem0
            try:
                mem0_messages = [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": answer}
                ]
                mem0.add(mem0_messages, user_id=user_id)
                logger.info(f"对话已保存到 Mem0: user_id={user_id}, session_id={session_id}")
            except Exception as e:
                logger.error(f"保存对话到 Mem0 失败: {e}", exc_info=True)
                # 不影响返回结果，只记录错误
            
            # 8. 更新对话历史
            updated_history = conversation_history.copy() if conversation_history else []
            updated_history.append({"role": "user", "content": query})
            updated_history.append({"role": "assistant", "content": answer})
            
            # 9. 格式化返回的记忆信息
            formatted_memories = []
            for mem in memories:
                formatted_mem = {
                    "memory": mem.get("memory", "") or mem.get("content", "") or str(mem),
                    "score": mem.get("score", 0.0),
                    "metadata": mem.get("metadata", {})
                }
                formatted_memories.append(formatted_mem)
            
            return {
                "answer": answer,
                "memories": formatted_memories,
                "memory_count": len(formatted_memories),
                "conversation_history": updated_history,
                "has_memory": len(formatted_memories) > 0
            }
            
        except ImportError as e:
            logger.warning(f"Mem0模块未安装: {e}")
            # 如果Mem0未安装，仍然可以生成回答（但不使用记忆）
            answer = await self.llm_client.chat(
                provider=provider,
                messages=[{"role": "user", "content": query}]
            )
            updated_history = conversation_history.copy() if conversation_history else []
            updated_history.append({"role": "user", "content": query})
            updated_history.append({"role": "assistant", "content": answer})
            
            return {
                "answer": answer,
                "memories": [],
                "memory_count": 0,
                "conversation_history": updated_history,
                "has_memory": False,
                "warning": "Mem0模块未安装，已跳过记忆功能"
            }
        except Exception as e:
            logger.error(f"Mem0 问答失败: {e}", exc_info=True)
            raise
    
    async def step7_llm_generate(
        self,
        query: str,
        retrieval_results: List[Dict[str, Any]] = None,
        injected_results: List[Dict[str, Any]] = None,
        provider: str = "deepseek",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        步骤7: LLM生成
        
        基于智能检索结果和Mem0上下文，生成回答
        
        Args:
            query: 用户问题
            retrieval_results: 智能检索结果（可选）
            injected_results: Mem0注入结果（可选）
            provider: LLM提供商
            user_id: 用户ID（用于Mem0记忆保存）
            session_id: 会话ID（用于Mem0记忆保存）
        """
        retrieval_results = retrieval_results or []
        injected_results = injected_results or []
        
        # 如果injected_results为空，自动从Mem0检索相关记忆
        if not injected_results and user_id and user_id != "anonymous":
            try:
                from app.core.mem0_client import get_mem0_client
                mem0 = get_mem0_client(provider=provider)
                
                logger.info(f"自动从Mem0检索相关记忆: user_id={user_id}, query='{query[:50]}...'")
                memories_result = mem0.search(query=query, user_id=user_id, limit=5)
                
                # 处理返回格式
                memories = []
                if isinstance(memories_result, dict) and "results" in memories_result:
                    memories = memories_result["results"]
                elif isinstance(memories_result, list):
                    memories = memories_result
                
                # 转换为injected_results格式
                if memories:
                    for mem in memories:
                        memory_text = mem.get("memory", "") or mem.get("content", "") or str(mem)
                        injected_results.append({
                            "name": "历史对话",
                            "content": memory_text,
                            "score": mem.get("score", 0.0),
                            "metadata": mem.get("metadata", {})
                        })
                    logger.info(f"从Mem0检索到 {len(injected_results)} 条相关记忆")
                else:
                    logger.info(f"Mem0未检索到相关记忆")
                    
            except ImportError as e:
                logger.warning(f"Mem0模块未安装，跳过自动检索: {e}")
            except Exception as e:
                logger.error(f"自动从Mem0检索记忆失败: {e}", exc_info=True)
                # 不影响主流程，继续执行
        
        # 构建智能检索上下文（按相似度排序，取Top 20）
        retrieval_context_parts = []
        if retrieval_results:
            # 按score降序排序
            sorted_results = sorted(retrieval_results, key=lambda x: x.get('score', 0), reverse=True)
            top_results = sorted_results[:20]  # 取Top 20
            
            for idx, r in enumerate(top_results, 1):
                source = r.get('source', 'unknown')
                source_channel = r.get('source_channel', 'unknown')
                name = r.get('name', '')
                content = r.get('content', '')
                score = r.get('score', 0)
                
                # 格式化内容（限制长度）
                content_preview = content[:300] if len(content) > 300 else content
                
                retrieval_context_parts.append(
                    f"{idx}. 【{source}/{source_channel}】{name}\n"
                    f"   相似度: {score:.2%}\n"
                    f"   内容: {content_preview}"
                )
        
        retrieval_context = "\n\n".join(retrieval_context_parts) if retrieval_context_parts else "（未检索到相关知识）"
        
        # 构建Mem0上下文
        mem0_context_parts = []
        if injected_results:
            for idx, r in enumerate(injected_results[:10], 1):  # 限制Mem0上下文长度
                name = r.get('name', '')
                content = r.get('content', '')
                mem0_context_parts.append(
                    f"{idx}. {name}: {content[:200]}"
                )
        
        mem0_context = "\n".join(mem0_context_parts) if mem0_context_parts else "（无历史对话上下文）"
        
        logger.info(f"开始LLM生成: 检索结果数={len(retrieval_results)}, Mem0上下文数={len(injected_results)}")
        
        # 构建完整的Prompt模板
        main_prompt = f"""你是一个智能助手，基于以下检索到的知识库内容和历史对话上下文，回答用户的问题。

【检索到的相关知识】
{retrieval_context}

【历史对话上下文】
{mem0_context}

【用户问题】
{query}

请基于以上信息，给出准确、详细的回答。要求：
1. 优先使用检索到的相关知识来回答问题
2. 结合历史对话上下文，保持回答的连贯性
3. 如果检索结果中没有相关信息，请明确说明
4. 回答要结构清晰、逻辑严谨
"""
        
        # 生成回答
        logger.info("正在调用LLM生成主要回答...")
        import time
        llm_start_time = time.time()
        generated_answer = await self.llm_client.chat(
            provider=provider,
            messages=[{"role": "user", "content": main_prompt}]
        )
        llm_time = time.time() - llm_start_time
        logger.info(f"LLM主要回答生成完成，耗时: {llm_time:.2f}秒")
        
        # 生成对比分析（可选，基于检索结果）- 简化处理，减少LLM调用
        comparison_analysis = None
        if retrieval_results and len(retrieval_results) > 0:
            logger.info("正在生成对比分析...")
            try:
                # 获取前3条检索结果的格式化文本
                top3_context = "\n\n".join(retrieval_context_parts[:3]) if len(retrieval_context_parts) >= 3 else "\n\n".join(retrieval_context_parts)
                comparison_prompt = f"""基于以下检索结果，简要分析用户问题与知识库内容的关联（100字以内）：

用户问题：{query}

检索到的相关内容（前3条）：
{top3_context}

请简要分析关联性。
"""
                comparison_start = time.time()
                comparison_analysis = await self.llm_client.chat(
                    provider=provider,
                    messages=[{"role": "user", "content": comparison_prompt}]
                )
                logger.info(f"对比分析生成完成，耗时: {time.time() - comparison_start:.2f}秒")
            except Exception as e:
                logger.warning(f"生成对比分析失败: {e}")
        
        # 生成复用建议（基于检索结果）- 简化处理
        reuse_suggestions = []
        if retrieval_results and len(retrieval_results) > 0:
            logger.info("正在生成复用建议...")
            try:
                # 获取前3条检索结果的格式化文本
                top3_context = "\n\n".join(retrieval_context_parts[:3]) if len(retrieval_context_parts) >= 3 else "\n\n".join(retrieval_context_parts)
                reuse_prompt = f"""基于以下检索结果，提供可以复用的组件或建议（最多3条，每条一句话）：

用户问题：{query}

检索到的相关内容（前3条）：
{top3_context}

请列出可以复用的组件或建议。
"""
                reuse_start = time.time()
                reuse_suggestions_text = await self.llm_client.chat(
                    provider=provider,
                    messages=[{"role": "user", "content": reuse_prompt}]
                )
                logger.info(f"复用建议生成完成，耗时: {time.time() - reuse_start:.2f}秒")
                
                # 解析复用建议
                reuse_suggestions = [
                    {
                        "type": "复用建议",
                        "title": item.strip().replace('- ', '').replace('* ', '').replace('1. ', '').replace('2. ', '').replace('3. ', ''),
                        "content": item.strip(),
                        "source": "LLM生成"
                    }
                    for item in reuse_suggestions_text.split("\n")
                    if item.strip() and len(item.strip()) > 10
                ][:3]  # 最多3条
            except Exception as e:
                logger.warning(f"生成复用建议失败: {e}")
        
        # 生成风险提示 - 简化处理
        risk_warnings = []
        logger.info("正在生成风险提示...")
        try:
            # 获取前3条检索结果的格式化文本
            top3_context = "\n\n".join(retrieval_context_parts[:3]) if len(retrieval_context_parts) >= 3 else "\n\n".join(retrieval_context_parts)
            risk_prompt = f"""基于以下信息，识别潜在风险或注意事项（最多3条，每条一句话）：

用户问题：{query}

检索到的相关内容（前3条）：
{top3_context}

请列出潜在的风险和注意事项。
"""
            risk_start = time.time()
            risk_warnings_text = await self.llm_client.chat(
                provider=provider,
                messages=[{"role": "user", "content": risk_prompt}]
            )
            logger.info(f"风险提示生成完成，耗时: {time.time() - risk_start:.2f}秒")
            
            # 解析风险提示
            risk_warnings = [
                {
                    "title": "风险提示",
                    "content": item.strip().replace('- ', '').replace('* ', '').replace('1. ', '').replace('2. ', '').replace('3. ', '')
                }
                for item in risk_warnings_text.split("\n")
                if item.strip() and len(item.strip()) > 10
            ][:3]  # 最多3条
        except Exception as e:
            logger.warning(f"生成风险提示失败: {e}")
        
        total_time = time.time() - llm_start_time
        logger.info(f"LLM生成全部完成，总耗时: {total_time:.2f}秒")
        
        # 保存对话到 Mem0（如果提供了 user_id）
        mem0_saved = False
        if user_id and user_id != "anonymous":
            try:
                from app.core.mem0_client import get_mem0_client
                mem0 = get_mem0_client(provider=provider)
                
                mem0_messages = [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": generated_answer}
                ]
                
                logger.info(f"开始保存对话到 Mem0: user_id={user_id}, provider={provider}, query长度={len(query)}, answer长度={len(generated_answer)}")
                
                # 尝试保存，如果返回空结果，尝试使用infer=False强制保存
                result = mem0.add(mem0_messages, user_id=user_id)
                
                # 检查保存结果
                if result and isinstance(result, dict):
                    results = result.get('results', [])
                    if results and len(results) > 0:
                        mem0_saved = True
                        logger.info(f"对话已保存到 Mem0: user_id={user_id}, session_id={session_id}, provider={provider}, 保存了{len(results)}条记忆")
                    else:
                        # 如果返回空结果，尝试使用infer=False强制保存
                        logger.warning(f"Mem0保存返回空结果，尝试使用infer=False强制保存: user_id={user_id}, result={result}")
                        try:
                            result_force = mem0.add(mem0_messages, user_id=user_id, infer=False)
                            if result_force and isinstance(result_force, dict):
                                results_force = result_force.get('results', [])
                                if results_force and len(results_force) > 0:
                                    mem0_saved = True
                                    logger.info(f"使用infer=False强制保存成功: user_id={user_id}, 保存了{len(results_force)}条记忆")
                                else:
                                    logger.warning(f"即使使用infer=False，Mem0仍然返回空结果: user_id={user_id}, result={result_force}")
                        except Exception as e:
                            logger.error(f"使用infer=False强制保存失败: {e}", exc_info=True)
                else:
                    logger.warning(f"Mem0保存返回异常格式: user_id={user_id}, result={result}")
                    
            except ImportError as e:
                logger.warning(f"Mem0模块未安装，跳过记忆保存: {e}")
            except Exception as e:
                logger.error(f"保存对话到 Mem0 失败: {e}", exc_info=True)
                # 不影响返回结果，只记录错误
        else:
            logger.debug(f"未提供有效的 user_id，跳过 Mem0 记忆保存")
        
        return {
            "generated_document": generated_answer,  # 主要回答
            "comparison_analysis": comparison_analysis,
            "reuse_suggestions": reuse_suggestions,
            "risk_warnings": risk_warnings,
            "retrieval_count": len(retrieval_results),
            "mem0_count": len(injected_results),
            "mem0_saved": mem0_saved  # 是否成功保存到Mem0
        }
    
    # ==================== 智能检索（两阶段检索）====================
    
    async def smart_retrieval(
        self,
        query: str,
        top_k: int = 50,
        top3: bool = True,
        group_ids: Optional[List[str]] = None,
        enable_refine: bool = True,
        enable_bm25: bool = True,
        enable_graph_traverse: bool = True
    ) -> Dict[str, Any]:
        """
        智能检索：两阶段检索策略
        
        阶段1：Milvus快速召回（文档级别）
        - 只使用Document相关的四个向量类型
        - 按文档聚合结果
        - 选择Top3文档
        
        阶段2：精细处理（文档级别）
        - 对Top3文档，使用Graphiti和Cognee知识图谱
        - 使用Milvus和Neo4j进行深度检索
        
        Args:
            query: 查询文本
            top_k: 阶段1的Top K（默认50）
            top3: 是否选择Top3文档（默认True）
            group_ids: 检索范围（可选）
            enable_refine: 是否启用阶段2精细处理（默认True）
            enable_bm25: 是否启用BM25检索（默认True）
            enable_graph_traverse: 是否启用图遍历（默认True）
            
        Returns:
            两阶段检索结果
        """
        import time
        start_time = time.time()
        
        logger.info(f"开始智能检索: query='{query[:50]}...', top_k={top_k}, top3={top3}")
        
        # ========== 阶段1：Milvus快速召回（文档级别）==========
        stage1_start = time.time()
        
        # 1. 生成查询向量
        query_embedding = await embedding_client.get_embedding(query)
        if not query_embedding:
            return {
                "success": False,
                "error": "查询向量生成失败",
                "stage1": {"total_documents": 0, "top3_documents": []},
                "stage2": {"refined_results": [], "total_count": 0}
            }
        
        # 2. 只搜索Document相关的四个向量类型
        document_vector_types = [
            VectorType.SECTION,           # document_section_vectors
            VectorType.DOCUMENT_SUMMARY,  # document_summary_vectors
            VectorType.IMAGE,             # document_image_vectors
            VectorType.TABLE              # document_table_vectors
        ]
        
        all_results = []
        for vector_type in document_vector_types:
            results = self.milvus.search_vectors(
                vector_type=vector_type,
                query_embedding=query_embedding,
                top_k=top_k,
                group_ids=group_ids,
                min_score=0.3
            )
            
            for sr in results:
                all_results.append({
                    "uuid": sr.uuid,
                    "name": sr.name,
                    "content": sr.content or sr.name,
                    "score": float(sr.score),
                    "type": sr.vector_type.value,
                    "group_id": sr.group_id,
                    "metadata": sr.metadata or {}
                })
        
        # 3. 按文档（group_id）聚合结果
        doc_results = {}
        for result in all_results:
            group_id = result.get("group_id")
            if not group_id:
                continue
            
            if group_id not in doc_results:
                doc_results[group_id] = {
                    "scores": [],
                    "vectors": {
                        "section": 0,
                        "document_summary": 0,
                        "image": 0,
                        "table": 0
                    },
                    "results": []
                }
            
            doc_results[group_id]["scores"].append(result["score"])
            doc_results[group_id]["vectors"][result["type"]] += 1
            doc_results[group_id]["results"].append(result)
        
        # 4. 计算每个文档的综合分数（使用最高分）
        doc_scores = []
        for group_id, data in doc_results.items():
            max_score = max(data["scores"]) if data["scores"] else 0.0
            avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0.0
            
            # 获取文档名称（从第一个结果中获取）
            doc_name = data["results"][0].get("name", group_id) if data["results"] else group_id
            
            doc_scores.append({
                "group_id": group_id,
                "document_name": doc_name,
                "score": max_score,  # 使用最高分作为综合分数
                "avg_score": avg_score,
                "max_score": max_score,
                "matched_vectors": data["vectors"],
                "vector_count": sum(data["vectors"].values()),
                "results": data["results"]
            })
        
        # 5. 按综合分数排序，选择Top3文档
        doc_scores.sort(key=lambda x: x["score"], reverse=True)
        top3_documents = doc_scores[:3] if top3 else doc_scores
        
        stage1_time = time.time() - stage1_start
        logger.info(f"阶段1完成: 匹配到 {len(doc_results)} 个文档，选择 {len(top3_documents)} 个文档，耗时 {stage1_time:.2f}秒")
        
        # ========== 阶段2：精细处理（文档级别）==========
        stage2_start = time.time()
        refined_results = []
        
        if enable_refine and top3_documents:
            for doc in top3_documents:
                group_id = doc["group_id"]
                logger.info(f"开始精细处理文档: group_id={group_id}")
                
                doc_refined_results = []
                
                # 并行执行Graphiti、Cognee和Milvus检索以提高性能
                import asyncio
                
                async def graphiti_search():
                    """Graphiti语义搜索"""
                    try:
                        # 使用 deepseek 作为默认 provider（因为 Kimi 在 Graphiti 中已验证可用）
                        # 如果 deepseek 不可用，可以尝试 kimi
                        selected_provider = "deepseek"
                        if not settings.DEEPSEEK_API_KEY:
                            if settings.KIMI_API_KEY:
                                selected_provider = "kimi"
                            elif settings.QWEN_API_KEY:
                                selected_provider = "qwen"
                            else:
                                logger.warning("没有可用的 LLM provider，跳过 Graphiti 语义搜索")
                                return []
                        
                        graphiti_results = await GraphitiService.retrieve_by_group_ids(
                            query=query,
                            group_ids=[group_id],
                            provider=selected_provider,
                            limit=50,
                            cross_encoder_mode="default"
                        )
                        results = []
                        for gr in graphiti_results:
                            results.append({
                                "uuid": gr.get("uuid", ""),
                                "name": gr.get("name", ""),
                                "content": gr.get("content", gr.get("name", "")),
                                "score": gr.get("score", 0.0),
                                "type": gr.get("type", "graphiti_entity"),
                                "source": "graphiti",
                                "source_channel": "graphiti_search",
                                "group_id": group_id,
                                "metadata": gr.get("metadata", {})
                            })
                        logger.info(f"文档 {group_id} Graphiti语义搜索完成，查询到 {len(results)} 个结果")
                        return results
                    except Exception as e:
                        logger.error(f"Graphiti语义搜索失败: {e}", exc_info=True)
                        return []
                
                async def cognee_search():
                    """Cognee语义搜索"""
                    try:
                        cognee_service = CogneeService()
                        kg_exists = await cognee_service.check_cognee_kg_exists(group_id=group_id)
                        
                        if not kg_exists:
                            logger.info(f"⚠️ Cognee 知识图谱不存在 (group_id={group_id})，跳过Cognee检索")
                            return []
                        
                        logger.debug(f"✅ Cognee 知识图谱已存在 (group_id={group_id})，执行Cognee检索")
                        cognee_results = await cognee_service.search_sections(
                            query=query,
                            group_id=group_id,
                            top_k=50
                        )
                        
                        results = []
                        for cr in cognee_results:
                            results.append({
                                "uuid": cr.get("metadata", {}).get("id", ""),
                                "name": cr.get("metadata", {}).get("name", cr.get("content", "")[:50]),
                                "content": cr.get("content", ""),
                                "score": cr.get("score", 0.0),
                                "type": "cognee_section",
                                "source": "cognee",
                                "source_channel": "cognee_search",
                                "group_id": group_id,
                                "metadata": cr.get("metadata", {})
                            })
                        logger.info(f"文档 {group_id} Cognee语义搜索完成，查询到 {len(results)} 个结果")
                        return results
                    except Exception as e:
                        logger.error(f"Cognee语义搜索失败: {e}", exc_info=True)
                        return []
                
                async def milvus_search():
                    """Milvus深度检索（并行查询所有向量类型）"""
                    try:
                        all_vector_types = [
                            VectorType.ENTITY,
                            VectorType.EDGE,
                            VectorType.EPISODE,
                            VectorType.COMMUNITY,
                            VectorType.SECTION,
                            VectorType.DOCUMENT_SUMMARY,
                            VectorType.IMAGE,
                            VectorType.TABLE,
                            VectorType.COGNEE_ENTITY,
                            VectorType.COGNEE_EDGE
                        ]
                        
                        # 并行执行所有向量类型的查询
                        async def search_vector_type(vt):
                            try:
                                milvus_results = self.milvus.search_vectors(
                                    vector_type=vt,
                                    query_embedding=query_embedding,
                                    top_k=20,
                                    group_ids=[group_id],
                                    min_score=0.3
                                )
                                
                                if vt in [VectorType.ENTITY, VectorType.EDGE, VectorType.EPISODE, VectorType.COMMUNITY]:
                                    source = "graphiti"
                                elif vt in [VectorType.COGNEE_ENTITY, VectorType.COGNEE_EDGE]:
                                    source = "cognee"
                                else:
                                    source = "document"
                                
                                results = []
                                for sr in milvus_results:
                                    results.append({
                                        "uuid": sr.uuid,
                                        "name": sr.name,
                                        "content": sr.content or sr.name,
                                        "score": float(sr.score),
                                        "type": sr.vector_type.value,
                                        "source": source,
                                        "source_channel": "milvus",
                                        "group_id": group_id,
                                        "metadata": sr.metadata or {}
                                    })
                                return results
                            except Exception as e:
                                logger.warning(f"Milvus {vt.value} 查询失败: {e}")
                                return []
                        
                        # 并行执行所有向量类型查询
                        milvus_tasks = [search_vector_type(vt) for vt in all_vector_types]
                        milvus_results_list = await asyncio.gather(*milvus_tasks, return_exceptions=True)
                        
                        # 合并结果
                        results = []
                        for r in milvus_results_list:
                            if isinstance(r, list):
                                results.extend(r)
                            elif isinstance(r, Exception):
                                logger.warning(f"Milvus查询异常: {r}")
                        
                        logger.info(f"文档 {group_id} Milvus深度检索完成，查询到 {len(results)} 个结果")
                        return results
                    except Exception as e:
                        logger.error(f"Milvus深度检索失败: {e}", exc_info=True)
                        return []
                
                # 并行执行Graphiti、Cognee和Milvus检索
                graphiti_results, cognee_results, milvus_results = await asyncio.gather(
                    graphiti_search(),
                    cognee_search(),
                    milvus_search(),
                    return_exceptions=True
                )
                
                # 合并结果
                if isinstance(graphiti_results, list):
                    doc_refined_results.extend(graphiti_results)
                if isinstance(cognee_results, list):
                    doc_refined_results.extend(cognee_results)
                if isinstance(milvus_results, list):
                    doc_refined_results.extend(milvus_results)
                
                # 4. 使用Neo4j进行关系扩展（可选）
                if enable_graph_traverse:
                    try:
                        # 获取该文档的所有Entity UUID
                        # 从Graphiti、Milvus等结果中提取Entity类型的UUID
                        # type可能是: "entity", "graphiti_entity", "cognee_entity", "graphiti_edge"等
                        entity_uuids = []
                        for r in doc_refined_results:
                            r_type = r.get("type", "").lower()
                            r_uuid = r.get("uuid", "")
                            # 提取Entity类型的UUID（排除edge、episode、community等）
                            if r_uuid and ("entity" in r_type or r_type == "cognee_node"):
                                entity_uuids.append(r_uuid)
                        
                        logger.info(f"文档 {group_id} 提取到 {len(entity_uuids)} 个Entity UUID用于图遍历: {entity_uuids[:5] if entity_uuids else '无'}")
                        
                        if entity_uuids:
                            # 图遍历扩展（1-hop）
                            # 分别查询Graphiti Entity和Cognee KnowledgeNode的关系
                            
                            # 1. 查询Graphiti Entity之间的关系
                            graphiti_query = """
                            MATCH (e:Entity)-[r:RELATES_TO]-(neighbor:Entity)
                            WHERE e.uuid IN $entity_uuids
                              AND neighbor.group_id = $group_id
                              AND NOT ('KnowledgeNode' IN labels(e))
                              AND NOT ('KnowledgeNode' IN labels(neighbor))
                            RETURN DISTINCT
                              id(neighbor) as id,
                              labels(neighbor) as labels,
                              properties(neighbor) as properties,
                              neighbor.uuid as uuid,
                              neighbor.name as name,
                              'graphiti' as source_type
                            LIMIT 50
                            """
                            
                            # 2. 查询Cognee KnowledgeNode之间的关系
                            # Cognee节点使用__Node__标签，可能有KnowledgeNode、Entity等标签
                            # 关系类型可能是RELATED_TO、CONTAINS_KNOWLEDGE等
                            # Cognee节点的uuid可能存储在uuid、id等属性中
                            cognee_query = """
                            MATCH (n)-[r]-(related)
                            WHERE (
                              n.uuid IN $entity_uuids 
                              OR n.id IN $entity_uuids
                              OR toString(n.id) IN $entity_uuids
                            )
                              AND (
                                ('KnowledgeNode' IN labels(n) OR '__Node__' IN labels(n) OR 'Entity' IN labels(n))
                                OR (n.dataset_name IS NOT NULL AND n.dataset_name CONTAINS $group_id)
                                OR (n.dataset_id IS NOT NULL AND n.dataset_id CONTAINS $group_id)
                              )
                              AND (
                                ('KnowledgeNode' IN labels(related) OR '__Node__' IN labels(related) OR 'Entity' IN labels(related))
                                OR (related.dataset_name IS NOT NULL AND related.dataset_name CONTAINS $group_id)
                                OR (related.dataset_id IS NOT NULL AND related.dataset_id CONTAINS $group_id)
                              )
                              AND n <> related
                            RETURN DISTINCT
                              id(related) as id,
                              labels(related) as labels,
                              properties(related) as properties,
                              COALESCE(related.uuid, related.id, toString(id(related))) as uuid,
                              COALESCE(related.name, related.text, related.id, toString(id(related))) as name,
                              'cognee' as source_type
                            LIMIT 50
                            """
                            
                            graph_results = []
                            
                            # 执行Graphiti查询
                            try:
                                graphiti_results = neo4j_client.execute_query(graphiti_query, {
                                    "entity_uuids": entity_uuids[:10],
                                    "group_id": group_id
                                })
                                if graphiti_results:
                                    graph_results.extend(graphiti_results)
                                    logger.info(f"文档 {group_id} Graphiti Neo4j图遍历查询返回 {len(graphiti_results)} 个结果")
                            except Exception as e:
                                logger.warning(f"Graphiti Neo4j查询失败: {e}")
                            
                            # 执行Cognee查询
                            try:
                                logger.info(f"文档 {group_id} 开始执行Cognee Neo4j查询，使用 {len(entity_uuids[:10])} 个UUID")
                                cognee_results = neo4j_client.execute_query(cognee_query, {
                                    "entity_uuids": entity_uuids[:10],
                                    "group_id": group_id
                                })
                                logger.info(f"文档 {group_id} Cognee Neo4j查询执行完成，返回 {len(cognee_results) if cognee_results else 0} 个结果")
                                if cognee_results:
                                    graph_results.extend(cognee_results)
                                    logger.info(f"文档 {group_id} Cognee Neo4j图遍历查询返回 {len(cognee_results)} 个结果，已添加到graph_results")
                                else:
                                    logger.warning(f"文档 {group_id} Cognee Neo4j查询返回空结果，可能原因：1) 节点不存在 2) 没有关系 3) dataset_name不匹配")
                            except Exception as e:
                                logger.error(f"Cognee Neo4j查询失败: {e}", exc_info=True)
                            
                            logger.info(f"文档 {group_id} Neo4j图遍历查询总共返回 {len(graph_results)} 个结果")
                            
                            neo4j_result_count = 0
                            cognee_neo4j_count = 0
                            graphiti_neo4j_count = 0
                            
                            for gr in graph_results:
                                if not gr:
                                    continue
                                
                                # 判断节点是Graphiti还是Cognee
                                node_labels = gr.get("labels", [])
                                node_props = gr.get("properties", {})
                                source_type = gr.get("source_type", "")
                                
                                # 优先使用查询返回的source_type
                                if source_type == "cognee":
                                    source = "cognee"
                                    cognee_neo4j_count += 1
                                elif source_type == "graphiti":
                                    source = "graphiti"
                                    graphiti_neo4j_count += 1
                                # 如果节点有Entity标签且没有KnowledgeNode标签，属于Graphiti
                                elif "Entity" in node_labels and "KnowledgeNode" not in node_labels:
                                    source = "graphiti"
                                    graphiti_neo4j_count += 1
                                # 如果节点有KnowledgeNode标签或dataset_name，属于Cognee
                                elif "KnowledgeNode" in node_labels or node_props.get("dataset_name") or node_props.get("dataset_id"):
                                    source = "cognee"
                                    cognee_neo4j_count += 1
                                else:
                                    # 默认根据group_id判断
                                    source = "graphiti"
                                    graphiti_neo4j_count += 1
                                
                                doc_refined_results.append({
                                    "uuid": gr.get("uuid", ""),
                                    "name": gr.get("name", ""),
                                    "content": gr.get("name", ""),  # 添加content字段
                                    "type": "graph_related",
                                    "source": source,
                                    "source_channel": "neo4j",
                                    "group_id": group_id,
                                    "score": 0.5,  # 图遍历结果降权
                                    "metadata": {
                                        "labels": node_labels,
                                        "properties": node_props
                                    }
                                })
                                neo4j_result_count += 1
                            
                            logger.info(f"文档 {group_id} Neo4j结果分类: Graphiti={graphiti_neo4j_count}, Cognee={cognee_neo4j_count}, 总计={neo4j_result_count}")
                            
                            logger.info(f"文档 {group_id} 图遍历扩展完成，找到 {len(graph_results) if graph_results else 0} 个相关节点，已添加 {neo4j_result_count} 个到结果")
                        else:
                            logger.warning(f"文档 {group_id} 没有Entity UUID可用于图遍历，跳过Neo4j扩展")
                    except Exception as e:
                        logger.error(f"图遍历扩展失败: {e}", exc_info=True)
                
                # 5. 去重和排序
                # 使用uuid去重（但保留不同source和source_channel的结果）
                seen_uuids = set()
                unique_results = []
                neo4j_count_before_dedup = len([r for r in doc_refined_results if r.get("source_channel") == "neo4j"])
                cognee_neo4j_before = len([r for r in doc_refined_results if r.get("source_channel") == "neo4j" and r.get("source") == "cognee"])
                graphiti_neo4j_before = len([r for r in doc_refined_results if r.get("source_channel") == "neo4j" and r.get("source") == "graphiti"])
                
                for r in doc_refined_results:
                    uuid_key = r.get("uuid", "")
                    source_channel = r.get("source_channel", "")
                    source = r.get("source", "")
                    
                    # 对于Neo4j结果，使用uuid+source+source_channel作为唯一键，避免被其他结果去重
                    # 这样可以区分Graphiti和Cognee的Neo4j结果
                    if source_channel == "neo4j":
                        dedup_key = f"{uuid_key}::{source}::neo4j"
                    else:
                        dedup_key = uuid_key
                    
                    if uuid_key and dedup_key not in seen_uuids:
                        seen_uuids.add(dedup_key)
                        unique_results.append(r)
                
                neo4j_count_after_dedup = len([r for r in unique_results if r.get("source_channel") == "neo4j"])
                cognee_neo4j_after = len([r for r in unique_results if r.get("source_channel") == "neo4j" and r.get("source") == "cognee"])
                graphiti_neo4j_after = len([r for r in unique_results if r.get("source_channel") == "neo4j" and r.get("source") == "graphiti"])
                logger.info(f"文档 {group_id} 去重前Neo4j结果: 总计={neo4j_count_before_dedup} (Graphiti={graphiti_neo4j_before}, Cognee={cognee_neo4j_before}), 去重后: 总计={neo4j_count_after_dedup} (Graphiti={graphiti_neo4j_after}, Cognee={cognee_neo4j_after})")
                
                # 按分数排序
                unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                refined_results.extend(unique_results)
                
                logger.info(f"文档 {group_id} 精细处理完成: {len(unique_results)} 个结果")
        
        stage2_time = time.time() - stage2_start
        total_time = time.time() - start_time
        
        logger.info(f"智能检索完成: 阶段1={stage1_time:.2f}秒, 阶段2={stage2_time:.2f}秒, 总计={total_time:.2f}秒")
        
        return {
            "success": True,
            "query": query,
            "stage1": {
                "total_documents": len(doc_results),
                "top3_documents": top3_documents,
                "execution_time": stage1_time
            },
            "stage2": {
                "refined_results": refined_results,
                "total_count": len(refined_results),
                "execution_time": stage2_time
            },
            "execution_time": {
                "stage1": stage1_time,
                "stage2": stage2_time,
                "total": total_time
            }
        }
