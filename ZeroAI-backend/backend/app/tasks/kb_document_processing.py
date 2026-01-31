"""
知识库文档处理任务（整合步骤2-5）
"""
import os
import json
import logging
import asyncio
from datetime import datetime
from celery import Task
from app.core.celery_app import celery_app
from app.core.mysql_client import SessionLocal
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.models.document_upload import DocumentUpload, DocumentStatus
from app.services.word_document_service import WordDocumentService
from app.core.graphiti_client import get_graphiti_instance
from app.core.neo4j_client import neo4j_client
from app.tasks.document_processing import ProgressTask, update_task_progress

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=ProgressTask, name="process_knowledge_base_document_task")
def process_knowledge_base_document_task(
    self,
    upload_id: int,
    chunk_strategy: str = "level_1",
    max_tokens_per_section: int = 8000,
    analysis_mode: str = "smart_segment",
    provider: str = "deepseek",
    use_thinking: bool = False
):
    """
    知识库文档处理任务（整合步骤2-5）
    
    流程：
    1. 步骤2: 解析文档 (0-20%)
    2. 步骤3: 分块 (20-40%)
    3. 步骤4: LLM生成模板 (40-60%)
    4. 步骤5: 处理文档并保存到Neo4j (60-100%)
    
    Args:
        self: Celery任务实例
        upload_id: 文档上传ID
        chunk_strategy: 分块策略
        max_tokens_per_section: 每个章节的最大token数
        analysis_mode: 模板生成方案（smart_segment/full_chunk）
        provider: LLM提供商
        use_thinking: 是否启用Thinking模式
    """
    db = SessionLocal()
    task_id = self.request.id
    task = None  # 初始化 task 变量，避免异常处理中引用未定义变量
    
    # 创建事件循环（整个任务中只创建一个，避免事件循环冲突）
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
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
        
        # ========== 步骤2: 解析文档 (0-20%) ==========
        self.update_progress(5, "步骤2: 开始解析文档")
        update_task_progress(db, task_id, 5, "步骤2: 开始解析文档", 0, 5)
        
        document.status = DocumentStatus.PARSING
        db.commit()
        
        # 将相对路径转换为绝对路径
        if not os.path.isabs(document.file_path):
            file_path_abs = os.path.join("/app", document.file_path)
        else:
            file_path_abs = document.file_path
        
        if not os.path.exists(file_path_abs):
            raise Exception(f"文件不存在: {file_path_abs}")
        
        logger.info(f"开始解析文档: upload_id={upload_id}, file_path={file_path_abs}")
        
        # 解析文档（使用upload_id作为document_id，用于保存图片和OLE对象）
        document_id_for_content = f"upload_{upload_id}"
        doc_data = WordDocumentService._parse_word_document(file_path_abs, document_id_for_content)
        logger.info(f"文档解析完成: {len(doc_data['structured_content'])} 个元素")
        
        # 按章节分块（用于生成parsed_content）
        sections = WordDocumentService._split_by_sections(
            doc_data["structured_content"],
            max_tokens=max_tokens_per_section
        )
        logger.info(f"文档分为 {len(sections)} 个章节")
        
        # 生成parsed_content（1:1对应原始文档）
        parsed_content = ""
        
        # 找到第一个一级标题的位置
        first_level1_heading_idx = None
        for idx, item in enumerate(doc_data.get("structured_content", [])):
            if item.get("type") == "heading" and item.get("level", 1) == 1:
                first_level1_heading_idx = idx
                break
        
        # 输出第一个一级标题之前的所有内容（封面页、表格等）
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
            # 没有一级标题，输出整个文档
            prefix_content = WordDocumentService._build_content_from_items(
                doc_data.get("structured_content", []),
                doc_data,
                document_id_for_content,
                upload_id
            )
            if prefix_content:
                parsed_content += prefix_content + "\n\n"
        
        # 按章节输出每个章节的内容
        for section in sections:
            section_content = WordDocumentService._build_section_content(
                section, doc_data, sections.index(section), document_id_for_content, upload_id
            )
            if section_content:
                parsed_content += section_content + "\n\n"
        
        # 生成summary_content（总结文档）
        summary_content = WordDocumentService._build_summary_content(
            doc_data, sections, document_id_for_content, upload_id, document.file_name
        )
        
        # 保存解析结果
        parsed_content_dir = os.path.join("uploads", "parsed_content", document_id_for_content)
        os.makedirs(parsed_content_dir, exist_ok=True)
        
        # 保存parsed_content.md
        parsed_content_path = os.path.join(parsed_content_dir, "parsed_content.md")
        with open(os.path.join("/app", parsed_content_path), 'w', encoding='utf-8') as f:
            f.write(parsed_content)
        
        # 保存summary_content.md
        summary_content_path = os.path.join(parsed_content_dir, "summary_content.md")
        with open(os.path.join("/app", summary_content_path), 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        # 保存structured_content.json
        structured_content_path = os.path.join(parsed_content_dir, "structured_content.json")
        with open(os.path.join("/app", structured_content_path), 'w', encoding='utf-8') as f:
            json.dump(doc_data['structured_content'], f, ensure_ascii=False, indent=2)
        
        # 更新文档记录
        document.parsed_content_path = parsed_content_path
        document.summary_content_path = summary_content_path
        document.structured_content_path = structured_content_path
        document.status = DocumentStatus.PARSED
        db.commit()
        
        self.update_progress(20, "步骤2: 文档解析完成")
        update_task_progress(db, task_id, 20, "步骤2: 文档解析完成", 1, 5)
        
        # ========== 步骤3: 分块 (20-40%) ==========
        self.update_progress(25, "步骤3: 开始分块")
        update_task_progress(db, task_id, 25, "步骤3: 开始分块", 1, 5)
        
        document.status = DocumentStatus.CHUNKING
        db.commit()
        
        # 根据策略分块
        valid_strategies = ["level_1", "level_2", "level_3", "level_4", "level_5", "fixed_token", "no_split"]
        if chunk_strategy not in valid_strategies:
            raise Exception(f"无效的分块策略: {chunk_strategy}")
        
        logger.info(f"开始分块: strategy={chunk_strategy}, max_tokens={max_tokens_per_section}")
        
        sections = WordDocumentService._split_by_sections_with_strategy(
            doc_data["structured_content"],
            strategy=chunk_strategy,
            max_tokens=max_tokens_per_section
        )
        logger.info(f"分块完成: {len(sections)} 个块")
        
        # 构建chunks数据
        chunks_data = []
        total_tokens = 0
        for idx, section in enumerate(sections):
            chunk_id = section.get('chunk_id', f"chunk_{idx+1}")
            content = section.get('content', '')
            # 简单估算token数（1 token ≈ 4字符）
            token_count = len(content) // 4
            total_tokens += token_count
            
            chunks_data.append({
                "chunk_id": chunk_id,
                "title": section.get('title', f"块 {idx+1}"),
                "level": section.get('level', 1),
                "content": content,
                "start_index": section.get('start_index', 0),
                "end_index": section.get('end_index', 0),
                "token_count": token_count
            })
        
        # 保存chunks.json
        chunks_path = os.path.join(parsed_content_dir, "chunks.json")
        chunks_file_data = {
            "upload_id": upload_id,
            "document_name": document.file_name,
            "strategy": chunk_strategy,
            "max_tokens": max_tokens_per_section,
            "created_at": datetime.now().isoformat(),
            "total_chunks": len(chunks_data),
            "total_tokens": total_tokens,
            "chunks": chunks_data
        }
        
        with open(os.path.join("/app", chunks_path), 'w', encoding='utf-8') as f:
            json.dump(chunks_file_data, f, ensure_ascii=False, indent=2)
        
        # 更新文档记录
        document.chunks_path = chunks_path
        document.chunk_strategy = chunk_strategy
        document.max_tokens_per_section = max_tokens_per_section
        document.status = DocumentStatus.CHUNKED
        db.commit()
        
        self.update_progress(40, "步骤3: 分块完成")
        update_task_progress(db, task_id, 40, "步骤3: 分块完成", 2, 5)
        
        # ========== 步骤4: LLM生成模板 (40-60%) ==========
        self.update_progress(45, "步骤4: 开始生成模板")
        update_task_progress(db, task_id, 45, "步骤4: 开始生成模板", 2, 5)
        
        logger.info(f"开始生成模板: analysis_mode={analysis_mode}")
        
        # 直接调用模板生成服务（同步执行）
        try:
            from app.services.template_generation_service import TemplateGenerationService
            from app.models.template import EntityEdgeTemplate
            
            # 读取parsed_content用于模板生成
            parsed_content_file_abs = os.path.join("/app", document.parsed_content_path)
            with open(parsed_content_file_abs, 'r', encoding='utf-8') as f:
                parsed_content = f.read()
            
            # 根据分析模式生成模板（使用统一的事件循环）
            if analysis_mode == "smart_segment":
                template_config = loop.run_until_complete(TemplateGenerationService.generate_template_smart_segment(
                    content=parsed_content,
                    document_name=document.file_name,
                    provider=provider
                ))
            else:  # full_chunk
                template_config = loop.run_until_complete(TemplateGenerationService.generate_template_full_chunk(
                    content=parsed_content,
                    document_name=document.file_name
                ))
            
            # 验证模板配置
            from app.services.template_service import TemplateService
            is_valid, errors, warnings = TemplateService.validate_template(
                template_config.get("entity_types", {}),
                template_config.get("edge_types", {}),
                template_config.get("edge_type_map", {})
            )
            
            if not is_valid:
                raise Exception(f"模板验证失败: {', '.join(errors)}")
            
            # 生成模板名称和描述
            doc_name = document.file_name.rsplit('.', 1)[0] if '.' in document.file_name else document.file_name
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            template_name = f"LLM生成-{doc_name}-{timestamp}"
            description = f"基于文档'{document.file_name}'自动生成的模板（{'智能分段' if analysis_mode == 'smart_segment' else '全文分块'}分析）"
            
            # 保存模板到数据库
            template = EntityEdgeTemplate(
                name=template_name,
                description=description,
                category="custom",
                entity_types=template_config.get("entity_types", {}),
                edge_types=template_config.get("edge_types", {}),
                edge_type_map=template_config.get("edge_type_map", {}),
                is_default=False,
                is_system=False,
                is_llm_generated=True,
                source_document_id=upload_id,
                analysis_mode=analysis_mode,
                llm_provider="local",
                generated_at=datetime.now(),
                usage_count=0
            )
            
            db.add(template)
            db.commit()
            db.refresh(template)
            
            # 更新文档记录
            document.template_id = template.id
            document.analysis_mode = analysis_mode
            db.commit()
            
            logger.info(f"模板生成成功: template_id={template.id}")
            
        except Exception as e:
            logger.error(f"模板生成失败: {e}", exc_info=True)
            raise Exception(f"模板生成失败: {str(e)}")
        
        self.update_progress(60, "步骤4: 模板生成完成")
        update_task_progress(db, task_id, 60, "步骤4: 模板生成完成", 3, 5)
        
        # ========== 步骤5: 处理文档并保存到Neo4j (60-100%) ==========
        self.update_progress(65, "步骤5: 开始处理文档")
        update_task_progress(db, task_id, 65, "步骤5: 开始处理文档", 3, 5)
        
        # 加载模板配置
        from app.services.template_service import TemplateService
        template_config = {
            "entity_types": template.entity_types,
            "edge_types": template.edge_types,
            "edge_type_map": template.edge_type_map
        }
        
        entity_types_dict, edge_types_dict, edge_type_map_dict = TemplateService.convert_to_pydantic(
            template_config["entity_types"],
            template_config["edge_types"],
            template_config["edge_type_map"]
        )
        
        logger.info(f"使用模板配置: {len(entity_types_dict)} 个实体类型, {len(edge_types_dict)} 个关系类型")
        
        # 获取Graphiti实例
        graphiti = get_graphiti_instance(provider)
        
        # 提取基础标识和版本号
        base_name = WordDocumentService._extract_base_name(document.file_name)
        version, version_number = WordDocumentService._extract_version(document.file_name)
        safe_base_name = WordDocumentService._sanitize_group_id(base_name)
        group_id = f"{safe_base_name}_{upload_id}"
        
        # 读取summary_content用于文档级Episode（从文件读取，因为之前已保存）
        summary_content_file_abs = os.path.join("/app", document.summary_content_path)
        with open(summary_content_file_abs, 'r', encoding='utf-8') as f:
            summary_content = f.read()
        
        # 读取chunks用于章节级Episode
        section_episodes_data = []
        for chunk in chunks_data:
            section_episodes_data.append({
                "chunk_id": chunk["chunk_id"],
                "title": chunk["title"],
                "level": chunk["level"],
                "content": chunk["content"],
                "start_index": chunk["start_index"],
                "end_index": chunk["end_index"]
            })
        
        # 计算总步骤数
        total_sections = len(section_episodes_data)
        total_images = len(doc_data.get("images", []))
        total_tables = len(doc_data.get("tables", []))
        total_steps = 1 + total_sections + total_images + total_tables
        
        # 更新任务总步骤数
        if task:
            task.total_steps = total_steps
            db.commit()
        
        # 创建文档级Episode
        self.update_progress(70, "创建文档级Episode")
        update_task_progress(db, task_id, 70, "创建文档级Episode", 1, total_steps)
        
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
        
        # 创建文档级Episode（使用统一的事件循环）
        document_episode = loop.run_until_complete(graphiti.add_episode(
            name=f"{document.file_name}_文档级",
            episode_body=overview_content,
            source_description="Word文档",
            reference_time=doc_data["metadata"].get("created") or datetime.now(),
            entity_types=entity_types_dict,
            edge_types=edge_types_dict,
            edge_type_map=edge_type_map_dict,
            group_id=group_id,
            previous_episode_uuids=[]
        ))
        
        document_episode_uuid = document_episode.episode.uuid
        
        # 更新版本信息
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
        
        # 创建章节级Episode
        section_episodes = []
        for idx, section_data in enumerate(section_episodes_data):
            progress = 70 + int((idx + 1) / total_sections * 20)
            step_desc = f"创建章节Episode ({idx+1}/{total_sections})"
            self.update_progress(progress, step_desc)
            update_task_progress(db, task_id, progress, step_desc, idx + 2, total_steps)
            
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
            
            # 更新版本信息
            neo4j_client.execute_write(update_version_query, {
                "episode_uuid": section_episode.episode.uuid,
                "version": version,
                "version_number": version_number,
                "document_name": document.file_name,
                "file_path": file_path_abs,
                "original_filename": os.path.basename(file_path_abs)
            })
            
            section_episodes.append(section_episode.episode.uuid)
        
        # 构建section_episode_map（用于关联图片/表格到章节）
        section_episode_map = {}
        for idx, section_data in enumerate(section_episodes_data):
            chunk_id = section_data.get('chunk_id', f"chunk_{idx+1}")
            if idx < len(section_episodes):
                section_episode_map[chunk_id] = section_episodes[idx]
        
        # 辅助函数：根据图片/表格在structured_content中的位置，找到对应的chunk_id
        def find_chunk_for_item(item_position, structured_content, chunks_data_list):
            if not chunks_data_list:
                return None
            for chunk in chunks_data_list:
                start_idx = chunk.get('start_index', 0)
                end_idx = chunk.get('end_index', len(structured_content))
                if start_idx <= item_position < end_idx:
                    return chunk.get('chunk_id')
            if chunks_data_list:
                return chunks_data_list[0].get('chunk_id')
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
        
        # 创建图片Episode
        image_episodes = []
        for idx, image in enumerate(doc_data.get("images", [])):
            progress = 90 + int((idx + 1) / max(total_images, 1) * 5)  # 90% - 95%
            step_desc = f"创建图片Episode ({idx+1}/{total_images})"
            self.update_progress(progress, step_desc)
            update_task_progress(db, task_id, progress, step_desc, 1 + total_sections + idx + 1, total_steps)
            
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
        
        # 创建表格Episode
        table_episodes = []
        for idx, table_data in enumerate(doc_data.get("tables", [])):
            progress = 95 + int((idx + 1) / max(total_tables, 1) * 5)  # 95% - 100%
            step_desc = f"创建表格Episode ({idx+1}/{total_tables})"
            self.update_progress(progress, step_desc)
            update_task_progress(db, task_id, progress, step_desc, 1 + total_sections + total_images + idx + 1, total_steps)
            
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
        
        # 更新文档记录
        document.document_id = group_id
        document.status = DocumentStatus.COMPLETED
        db.commit()
        
        # 更新知识库文档数量
        if document.knowledge_base_id:
            from app.models.knowledge_base import KnowledgeBase
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == document.knowledge_base_id).first()
            if kb:
                kb.document_count = db.query(DocumentUpload).filter(
                    DocumentUpload.knowledge_base_id == kb.id,
                    DocumentUpload.status == DocumentStatus.COMPLETED
                ).count()
                kb.last_updated_at = datetime.now()
                db.commit()
        
        self.update_progress(100, "文档处理完成")
        update_task_progress(db, task_id, 100, "文档处理完成", total_steps, total_steps)
        
        logger.info(f"知识库文档处理完成: upload_id={upload_id}, group_id={group_id}")
        
        return {
            "upload_id": upload_id,
            "group_id": group_id,
            "template_id": document.template_id,
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"知识库文档处理失败: {e}", exc_info=True)
        
        # 更新文档状态为错误
        try:
            document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
            if document:
                document.status = DocumentStatus.ERROR
                document.error_message = str(e)
                db.commit()
        except:
            pass
        
        # 更新任务状态
        if task:
            task.status = TaskStatus.FAILED.value
            # 截断错误信息到200字符（数据库字段限制）
            # 先拼接完整字符串，再截断，确保总长度不超过200字符
            full_error_msg = f"处理失败: {str(e)}"
            if len(full_error_msg) > 200:
                task.current_step = full_error_msg[:197] + "..."
            else:
                task.current_step = full_error_msg
            task.completed_at = datetime.now()
            db.commit()
        
        raise
    finally:
        # 确保事件循环被关闭
        try:
            loop.close()
        except:
            pass

