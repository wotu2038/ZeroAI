"""
文档处理任务（Celery任务）
"""
import os
import json
import logging
from datetime import datetime
from celery import Task
from app.core.celery_app import celery_app
from app.core.mysql_client import SessionLocal
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.models.document_upload import DocumentUpload, DocumentStatus
from app.services.word_document_service import WordDocumentService
from app.core.graphiti_client import get_graphiti_instance
from app.models.graphiti_entities import ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP
from app.core.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


class ProgressTask(Task):
    """支持进度更新的任务基类"""
    def update_progress(self, progress: int, current_step: str, completed_steps: int = None, total_steps: int = None):
        """更新任务进度"""
        if self.request:
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': progress,
                    'current_step': current_step,
                    'completed_steps': completed_steps,
                    'total_steps': total_steps
                }
            )


def update_task_progress(db, task_id: str, progress: int, current_step: str, completed_steps: int = None, total_steps: int = None):
    """更新数据库中的任务进度"""
    try:
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.progress = progress or 0
            # 截断current_step到200字符（数据库字段限制）
            if current_step and len(current_step) > 200:
                task.current_step = current_step[:197] + "..."
            else:
                task.current_step = current_step
            # 确保 completed_steps 和 total_steps 不为 None，如果为 None 则不更新
            if completed_steps is not None:
                task.completed_steps = completed_steps
            if total_steps is not None:
                task.total_steps = total_steps
            db.commit()
    except Exception as e:
        logger.error(f"更新任务进度失败: {e}", exc_info=True)
        db.rollback()


@celery_app.task(bind=True, base=ProgressTask, name="process_document_task")
def process_document_task(self, upload_id: int, group_id: str, version: str, version_number: str, provider: str, max_tokens_per_section: int = 8000, use_thinking: bool = False, template_config: dict = None):
    """
    异步处理文档任务（步骤5）
    
    Args:
        self: Celery任务实例
        upload_id: 文档上传ID
        group_id: 文档组ID
        version: 版本号
        version_number: 版本数字
        provider: LLM提供商
        max_tokens_per_section: 每个章节的最大token数
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        # 更新任务状态为运行中
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.now()
            db.commit()
        
        # 查询文档
        document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
        if not document:
            raise Exception(f"文档不存在: upload_id={upload_id}")
        
        # 更新进度：准备阶段（5%）
        self.update_progress(5, "准备阶段：验证文档和读取配置")
        update_task_progress(db, task_id, 5, "准备阶段：验证文档和读取配置", 0, 10)
        
        # 将相对路径转换为绝对路径
        if not os.path.isabs(document.file_path):
            file_path_abs = os.path.join("/app", document.file_path)
        else:
            file_path_abs = document.file_path
        
        if not os.path.exists(file_path_abs):
            raise Exception(f"文件不存在: {file_path_abs}")
        
        # 加载模板配置
        if template_config:
            # 使用模板配置
            from app.services.template_service import TemplateService
            entity_types_dict, edge_types_dict, edge_type_map_dict = TemplateService.convert_to_pydantic(
                template_config["entity_types"],
                template_config["edge_types"],
                template_config["edge_type_map"]
            )
            logger.info(f"使用模板配置: {len(entity_types_dict)} 个实体类型, {len(edge_types_dict)} 个关系类型")
        else:
            # 使用默认配置（向后兼容）
            entity_types_dict = ENTITY_TYPES
            edge_types_dict = EDGE_TYPES
            edge_type_map_dict = EDGE_TYPE_MAP
            logger.info("使用默认配置（硬编码）")
        
        # 更新状态为处理中
        document.status = DocumentStatus.CHUNKING
        db.commit()
        
        # 读取Markdown文件（如果存在）
        parsed_content = None
        summary_content = None
        
        if document.parsed_content_path:
            parsed_content_file_abs = os.path.join("/app", document.parsed_content_path)
            if os.path.exists(parsed_content_file_abs):
                with open(parsed_content_file_abs, 'r', encoding='utf-8') as f:
                    parsed_content = f.read()
                logger.info(f"已读取parsed_content.md文件: {document.parsed_content_path}")
        
        if document.summary_content_path:
            summary_content_file_abs = os.path.join("/app", document.summary_content_path)
            if os.path.exists(summary_content_file_abs):
                with open(summary_content_file_abs, 'r', encoding='utf-8') as f:
                    summary_content = f.read()
                logger.info(f"已读取summary_content.md文件: {document.summary_content_path}")
        
        # 读取chunks.json（如果步骤4已完成）
        chunks_data = None
        if document.chunks_path:
            chunks_file_abs = os.path.join("/app", document.chunks_path)
            if os.path.exists(chunks_file_abs):
                with open(chunks_file_abs, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)
                logger.info(f"已读取chunks.json: {document.chunks_path}, 包含 {len(chunks_data.get('chunks', []))} 个chunks")
        
        # 如果文件不存在，需要重新解析文档
        document_id_for_content = f"upload_{upload_id}"
        doc_data = None
        if parsed_content is None or summary_content is None:
            # 更新进度：解析阶段（15%）
            self.update_progress(15, "解析阶段：解析Word文档")
            update_task_progress(db, task_id, 15, "解析阶段：解析Word文档", 1, 10)
            
            doc_data = WordDocumentService._parse_word_document(file_path_abs, document_id_for_content)
            logger.info(f"文档解析完成: {len(doc_data['structured_content'])} 个元素")
            
            # 重新构建parsed_content和summary_content
            if parsed_content is None:
                parsed_content = ""
                first_level1_heading_idx = None
                for idx, item in enumerate(doc_data.get("structured_content", [])):
                    if item.get("type") == "heading" and item.get("level", 1) == 1:
                        first_level1_heading_idx = idx
                        break
                
                if first_level1_heading_idx is not None and first_level1_heading_idx > 0:
                    prefix_content = WordDocumentService._build_content_from_items(
                        doc_data.get("structured_content", [])[:first_level1_heading_idx],
                        doc_data,
                        document_id_for_content,
                        upload_id
                    )
                    if prefix_content:
                        parsed_content += prefix_content + "\n\n"
                elif first_level1_heading_idx is None:
                    prefix_content = WordDocumentService._build_content_from_items(
                        doc_data.get("structured_content", []),
                        doc_data,
                        document_id_for_content,
                        upload_id
                    )
                    if prefix_content:
                        parsed_content += prefix_content + "\n\n"
                
                # 如果chunks.json不存在，需要重新分块
                if chunks_data is None:
                    sections = WordDocumentService._split_by_sections(
                        doc_data["structured_content"],
                        max_tokens=max_tokens_per_section
                    )
                    logger.info(f"文档分为 {len(sections)} 个章节（重新分块）")
                    
                    for idx, section in enumerate(sections):
                        section_content = WordDocumentService._build_section_content(
                            section, doc_data, idx, document_id_for_content, upload_id
                        )
                        if section_content:
                            parsed_content += section_content + "\n\n"
            
            if summary_content is None:
                if chunks_data is None:
                    sections = WordDocumentService._split_by_sections(
                        doc_data["structured_content"],
                        max_tokens=max_tokens_per_section
                    )
                else:
                    sections = []
                    for chunk in chunks_data.get('chunks', []):
                        sections.append({
                            'title': chunk.get('title', ''),
                            'level': chunk.get('level', 1)
                        })
                
                summary_content = WordDocumentService._build_summary_content(
                    doc_data, sections, document_id_for_content, upload_id, document.file_name
                )
        
        # 如果doc_data不存在，需要解析来获取structured_content（用于图片/表格Episode）
        if doc_data is None:
            doc_data = WordDocumentService._parse_word_document(file_path_abs, document_id_for_content)
            logger.info(f"文档解析完成: {len(doc_data['structured_content'])} 个元素（用于创建图片/表格Episode）")
        
        # 准备章节数据（用于创建章节级Episode）
        section_episodes_data = []
        if chunks_data and chunks_data.get('chunks'):
            logger.info(f"使用chunks.json创建章节级Episode: {len(chunks_data['chunks'])} 个chunks")
            for chunk in chunks_data['chunks']:
                section_episodes_data.append({
                    "chunk_id": chunk.get('chunk_id', ''),
                    "title": chunk.get('title', ''),
                    "level": chunk.get('level', 1),
                    "content": chunk.get('content', ''),
                    "start_index": chunk.get('start_index', 0),
                    "end_index": chunk.get('end_index', 0)
                })
        elif parsed_content:
            # 从parsed_content按章节标题分割
            logger.info("从parsed_content分割章节（chunks.json不存在）")
            lines = parsed_content.split('\n')
            current_section = None
            current_content = []
            
            for line in lines:
                if line.strip().startswith('# ') and not line.strip().startswith('##'):
                    if current_section:
                        section_episodes_data.append({
                            "chunk_id": f"chunk_{len(section_episodes_data) + 1}",
                            "title": current_section,
                            "level": 1,
                            "content": '\n'.join(current_content).strip(),
                            "start_index": 0,
                            "end_index": 0
                        })
                    current_section = line.strip()[2:].strip()
                    current_content = [line]
                else:
                    if current_section:
                        current_content.append(line)
            
            if current_section:
                section_episodes_data.append({
                    "chunk_id": f"chunk_{len(section_episodes_data) + 1}",
                    "title": current_section,
                    "level": 1,
                    "content": '\n'.join(current_content).strip(),
                    "start_index": 0,
                    "end_index": 0
                })
        
        # 计算总步骤数
        total_sections = len(section_episodes_data)
        total_images = len(doc_data.get("images", []))
        total_tables = len(doc_data.get("tables", []))
        total_steps = 1 + total_sections + total_images + total_tables  # 文档级 + 章节 + 图片 + 表格
        
        # 更新任务总步骤数
        if task:
            task.total_steps = total_steps
            db.commit()
        
        # 获取Graphiti实例
        graphiti = get_graphiti_instance(provider)
        
        # 创建文档级Episode（5%）
        self.update_progress(10, "创建文档级Episode")
        update_task_progress(db, task_id, 10, "创建文档级Episode", 1, total_steps)
        
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
            overview_content = '\n'.join(summary_lines[overview_start:overview_end if overview_end else len(summary_lines)])
        else:
            overview_content = summary_content[:1000]
        
        # 估算token数量并限制overview_content长度
        # 本地大模型最大上下文: 35,488 tokens
        # 需要预留空间给prompt和completion，实际可用约25,000 tokens
        def estimate_tokens(text: str) -> int:
            """估算文本的token数（中文通常1 token ≈ 2字符，英文1 token ≈ 4字符）"""
            chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
            other_chars = len(text) - chinese_chars
            return (chinese_chars // 2) + (other_chars // 4)
        
        max_episode_tokens = 25000  # 预留空间给prompt和completion
        estimated_tokens = estimate_tokens(overview_content)
        
        if estimated_tokens > max_episode_tokens:
            logger.warning(f"overview_content过长，估算tokens: {estimated_tokens}，最大允许: {max_episode_tokens}，进行截断")
            # 按比例截断内容
            ratio = max_episode_tokens / estimated_tokens
            target_length = int(len(overview_content) * ratio * 0.9)  # 再留10%余量
            overview_content = overview_content[:target_length]
            # 尝试在句子或段落边界截断
            if '\n\n' in overview_content:
                overview_content = overview_content.rsplit('\n\n', 1)[0]
            elif '\n' in overview_content:
                overview_content = overview_content.rsplit('\n', 1)[0]
            logger.info(f"截断后overview_content长度: {len(overview_content)} 字符，估算tokens: {estimate_tokens(overview_content)}")
        
        # 使用asyncio运行异步函数
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        document_episode = loop.run_until_complete(graphiti.add_episode(
            name=f"{document.file_name}_文档概览",
            episode_body=overview_content,
            source_description="Word文档",
            reference_time=doc_data["metadata"].get("created") or datetime.now(),
            entity_types={
                "Requirement": entity_types_dict.get("Requirement"),
                "Document": entity_types_dict.get("Document"),
            } if entity_types_dict.get("Requirement") and entity_types_dict.get("Document") else None,
            group_id=group_id
        ))
        document_episode_uuid = document_episode.episode.uuid
        logger.info(f"文档级 Episode 创建完成: {document_episode_uuid}")
        
        # 更新文档级Episode的版本信息
        update_version_query = """
        MATCH (e:Episodic)
        WHERE e.uuid = $episode_uuid
        SET e.version = $version,
            e.version_number = $version_number,
            e.document_name = $document_name,
            e.file_path = $file_path,
            e.original_filename = $original_filename
        RETURN e.uuid as uuid
        """
        neo4j_client.execute_write(update_version_query, {
            "episode_uuid": document_episode_uuid,
            "version": version,
            "version_number": version_number,
            "document_name": document.file_name,
            "file_path": file_path_abs,
            "original_filename": os.path.basename(file_path_abs)
        })
        
        # 创建章节级Episode（50%）
        section_episodes = []
        section_episode_map = {}
        
        for idx, section_data in enumerate(section_episodes_data):
            progress = 10 + int((idx + 1) / total_sections * 50)  # 10% - 60%
            current_step = f"创建章节级Episode ({idx+1}/{total_sections}): {section_data['title'][:30]}"
            self.update_progress(progress, current_step)
            update_task_progress(db, task_id, progress, current_step, 1 + idx + 1, total_steps)
            
            section_episode = loop.run_until_complete(graphiti.add_episode(
                name=f"{document.file_name}_章节_{idx+1}_{section_data['title'][:20]}",
                episode_body=section_data["content"],
                source_description="Word文档章节",
                reference_time=doc_data["metadata"].get("created") or datetime.now(),
                entity_types=entity_types_dict,
                edge_types=edge_types_dict,
                edge_type_map=edge_type_map_dict,
                group_id=group_id,
                previous_episode_uuids=[document_episode_uuid]
            ))
            
            neo4j_client.execute_write(update_version_query, {
                "episode_uuid": section_episode.episode.uuid,
                "version": version,
                "version_number": version_number,
                "document_name": document.file_name,
                "file_path": file_path_abs,
                "original_filename": os.path.basename(file_path_abs)
            })
            section_episode_uuid = section_episode.episode.uuid
            section_episodes.append(section_episode_uuid)
            
            chunk_id = section_data.get('chunk_id', f"chunk_{idx+1}")
            section_episode_map[chunk_id] = section_episode_uuid
            
            logger.info(f"章节级 Episode {idx+1} 创建完成: {section_episode_uuid} (chunk_id: {chunk_id})")
        
        # 辅助函数：根据图片/表格在structured_content中的位置，找到对应的chunk_id
        def find_chunk_for_item(item_position, structured_content, chunks_data):
            if not chunks_data or not chunks_data.get('chunks'):
                return None
            for chunk in chunks_data['chunks']:
                start_idx = chunk.get('start_index', 0)
                end_idx = chunk.get('end_index', len(structured_content))
                if start_idx <= item_position < end_idx:
                    return chunk.get('chunk_id')
            if chunks_data['chunks']:
                return chunks_data['chunks'][0].get('chunk_id')
            return None
        
        # 构建图片位置到structured_content索引的映射
        image_position_to_structured_idx = {}
        structured_content = doc_data.get("structured_content", [])
        for idx, item in enumerate(structured_content):
            if item.get("type") in ["paragraph", "heading"]:
                images_in_item = item.get("images", [])
                for img in images_in_item:
                    image_id = img.get("image_id")
                    if image_id:
                        image_position_to_structured_idx[image_id] = idx
        
        # 构建表格位置到structured_content索引的映射
        table_position_to_structured_idx = {}
        for idx, item in enumerate(structured_content):
            if item.get("type") == "table":
                table_id = item.get("table_id")
                if table_id:
                    table_position_to_structured_idx[table_id] = idx
        
        # 创建图片Episode（10%）
        image_episodes = []
        for idx, image in enumerate(doc_data.get("images", [])):
            progress = 60 + int((idx + 1) / max(total_images, 1) * 10)  # 60% - 70%
            current_step = f"创建图片Episode ({idx+1}/{total_images})"
            self.update_progress(progress, current_step)
            update_task_progress(db, task_id, progress, current_step, 1 + total_sections + idx + 1, total_steps)
            
            image_desc = image.get("description", "图片")
            image_id = image.get("image_id", f"image_{idx+1}")
            image_url = f"/api/document-upload/{upload_id}/images/{image_id}"
            
            file_path = image.get("file_path", "")
            relative_path = image.get("relative_path", "")
            file_size = image.get("file_size", 0)
            file_format = image.get("file_format", "未知")
            
            if file_size == 0 or file_format == "未知":
                if file_path:
                    abs_file_path = file_path if os.path.isabs(file_path) else os.path.join("/app", file_path)
                    if os.path.exists(abs_file_path):
                        file_size = os.path.getsize(abs_file_path)
                        if file_format == "未知":
                            ext = os.path.splitext(abs_file_path)[1]
                            file_format = ext[1:].upper() if ext else "UNKNOWN"
            
            image_content = f"""## 图片信息

**图片ID**: {image_id}
**描述**: {image_desc}
**文件路径**: {file_path}
**相对路径**: {relative_path}
**文件大小**: {file_size} 字节
**文件格式**: {file_format}

### 图片链接
![{image_desc}]({image_url})

### 图片说明
这是一张从Word文档中提取的图片。
"""
            
            image_id_key = image.get("image_id", "")
            structured_idx = image_position_to_structured_idx.get(image_id_key)
            section_episode_uuid_for_image = None
            
            if structured_idx is not None and chunks_data:
                chunk_id = find_chunk_for_item(structured_idx, structured_content, chunks_data)
                if chunk_id and chunk_id in section_episode_map:
                    section_episode_uuid_for_image = section_episode_map[chunk_id]
            
            previous_episode_uuids = [document_episode_uuid]
            if section_episode_uuid_for_image:
                previous_episode_uuids.append(section_episode_uuid_for_image)
            
            image_episode = loop.run_until_complete(graphiti.add_episode(
                name=f"{document.file_name}_图片_{idx+1}_{image.get('image_id', '')}",
                episode_body=image_content,
                source_description="Word文档图片",
                reference_time=doc_data["metadata"].get("created") or datetime.now(),
                entity_types=entity_types_dict,
                edge_types=edge_types_dict,
                edge_type_map=edge_type_map_dict,
                group_id=group_id,
                previous_episode_uuids=previous_episode_uuids
            ))
            
            neo4j_client.execute_write(update_version_query, {
                "episode_uuid": image_episode.episode.uuid,
                "version": version,
                "version_number": version_number,
                "document_name": document.file_name,
                "file_path": file_path_abs,
                "original_filename": os.path.basename(file_path_abs)
            })
            image_episodes.append(image_episode.episode.uuid)
        
        # 创建表格Episode（5%）
        table_episodes = []
        for idx, table_data in enumerate(doc_data.get("tables", [])):
            progress = 70 + int((idx + 1) / max(total_tables, 1) * 5)  # 70% - 75%
            current_step = f"创建表格Episode ({idx+1}/{total_tables})"
            self.update_progress(progress, current_step)
            update_task_progress(db, task_id, progress, current_step, 1 + total_sections + total_images + idx + 1, total_steps)
            
            table_markdown = WordDocumentService._format_table_as_markdown(table_data)
            table_id = table_data.get('table_id', f'table_{idx+1}')
            table_content = f"""## 表格信息

**表格序号**: {idx+1}
**表格ID**: {table_id}
**行数**: {len(table_data.get('rows', []))}
**列数**: {len(table_data.get('headers', []))}

### 表格内容

{table_markdown}

### 表格说明
这是从Word文档中提取的表格数据，使用标准Markdown表格格式，包含结构化的信息。
"""
            
            structured_idx = table_position_to_structured_idx.get(table_id)
            section_episode_uuid_for_table = None
            
            if structured_idx is not None and chunks_data:
                chunk_id = find_chunk_for_item(structured_idx, structured_content, chunks_data)
                if chunk_id and chunk_id in section_episode_map:
                    section_episode_uuid_for_table = section_episode_map[chunk_id]
            
            previous_episode_uuids = [document_episode_uuid]
            if section_episode_uuid_for_table:
                previous_episode_uuids.append(section_episode_uuid_for_table)
            
            table_episode = loop.run_until_complete(graphiti.add_episode(
                name=f"{document.file_name}_表格_{idx+1}_{table_id}",
                episode_body=table_content,
                source_description="Word文档表格",
                reference_time=doc_data["metadata"].get("created") or datetime.now(),
                entity_types=entity_types_dict,
                edge_types=edge_types_dict,
                edge_type_map=edge_type_map_dict,
                group_id=group_id,
                previous_episode_uuids=previous_episode_uuids
            ))
            
            neo4j_client.execute_write(update_version_query, {
                "episode_uuid": table_episode.episode.uuid,
                "version": version,
                "version_number": version_number,
                "document_name": document.file_name,
                "file_path": file_path_abs,
                "original_filename": os.path.basename(file_path_abs)
            })
            table_episodes.append(table_episode.episode.uuid)
        
        # 更新文档状态和document_id
        document.status = DocumentStatus.COMPLETED
        document.document_id = group_id
        db.commit()
        
        # 更新任务状态为完成
        result = {
            "upload_id": upload_id,
            "document_id": group_id,
            "document_name": document.file_name,
            "version": version,
            "version_number": version_number,
            "episodes": {
                "document": document_episode_uuid,
                "sections": section_episodes,
                "images": image_episodes,
                "tables": table_episodes
            },
            "statistics": {
                "total_episodes": 1 + len(section_episodes) + len(image_episodes) + len(table_episodes),
                "total_sections": len(section_episodes),
                "total_images": len(image_episodes),
                "total_tables": len(table_episodes)
            }
        }
        
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.current_step = "处理完成"
            task.completed_steps = total_steps
            task.result = result
            task.completed_at = datetime.now()
            db.commit()
        
        logger.info(f"文档处理完成: upload_id={upload_id}, group_id={group_id}")
        
        loop.close()
        return result
        
    except Exception as e:
        logger.error(f"处理文档失败: {e}", exc_info=True)
        
        # 更新文档状态为错误
        try:
            document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
            if document:
                document.status = DocumentStatus.ERROR
                document.error_message = str(e)
                db.commit()
        except:
            pass
        
        # 更新任务状态为失败
        try:
            task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_message = str(e)
                task.completed_at = datetime.now()
                db.commit()
        except:
            pass
        
        raise
    
    finally:
        db.close()

