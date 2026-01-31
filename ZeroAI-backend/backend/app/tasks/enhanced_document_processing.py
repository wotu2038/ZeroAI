"""
增强版知识库文档处理任务

集成以下新功能：
1. LLM智能分块策略选择
2. 三层质量评估
3. LLM智能文档摘要
4. Episode并发处理
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
from app.core.config import settings
from app.tasks.document_processing import ProgressTask, update_task_progress

# 新增服务
from app.services.smart_chunking_service import SmartChunkingService
from app.services.document_summary_service import DocumentSummaryService
from app.services.extraction_quality_service import ExtractionQualityService
from app.services.quality_gate_service import QualityGateService, QualityStatus, GraphQualityService
from app.services.episode_processor import EpisodeProcessor
from app.services.vector_dual_write_service import VectorDualWriteService
from app.services.auto_community_service import AutoCommunityService
from app.services.cognee_service import CogneeService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=ProgressTask, name="process_document_enhanced_task")
def process_document_enhanced_task(
    self,
    upload_id: int,
    chunk_strategy: str = "auto",  # 新增 "auto" 选项
    max_tokens_per_section: int = 8000,
    analysis_mode: str = "smart_segment",
    provider: str = "deepseek",
    use_thinking: bool = False,
    enable_quality_gate: bool = True,  # 是否启用质量门禁
    enable_concurrent: bool = True      # 是否启用并发处理
):
    """
    增强版知识库文档处理任务
    
    新增功能：
    - 智能分块策略选择 (chunk_strategy="auto")
    - 三层质量评估与门禁
    - LLM智能文档摘要
    - Episode并发处理
    - Milvus向量双写
    - 自动Community构建
    
    流程：
    1. 步骤1: 解析文档 (0-15%)
    2. 步骤2: 智能分块 (15-25%)
    3. 步骤3: LLM生成模板 (25-40%)
    4. 步骤4: 生成智能摘要 (40-50%)
    5. 步骤5: 创建文档级Episode (50-55%)
    6. 步骤6: 处理章节内容到 Milvus (55-75%)
    7. 步骤7: 同步向量到Milvus (75-80%)
    8. 步骤8: 自动构建Community (80-85%)
    9. 步骤9: 质量评估 (85-95%)
    10. 步骤10: 完成处理 (95-100%)
    """
    db = SessionLocal()
    task_id = self.request.id
    
    # 创建事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 初始化服务
    smart_chunking = SmartChunkingService()
    quality_gate = QualityGateService()
    episode_processor = EpisodeProcessor()
    
    retry_count = 0
    current_strategy = chunk_strategy
    task = None  # 初始化 task 变量，避免异常处理中引用未定义变量
    
    try:
        # 更新任务状态
        task = db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if task:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.now()
            db.commit()
        
        # 查询文档
        document = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
        if not document:
            raise Exception(f"文档不存在: upload_id={upload_id}")
        
        # ========== 步骤1: 解析文档 (0-15%) ==========
        self.update_progress(5, "步骤1: 解析文档")
        update_task_progress(db, task_id, 5, "步骤1: 解析文档", 0, 9)
        
        document.status = DocumentStatus.PARSING
        db.commit()
        
        # 路径处理
        if not os.path.isabs(document.file_path):
            file_path_abs = os.path.join("/app", document.file_path)
        else:
            file_path_abs = document.file_path
        
        if not os.path.exists(file_path_abs):
            raise Exception(f"文件不存在: {file_path_abs}")
        
        logger.info(f"开始解析文档: upload_id={upload_id}")
        
        # 解析文档
        document_id_for_content = f"upload_{upload_id}"
        doc_data = WordDocumentService._parse_word_document(file_path_abs, document_id_for_content)
        structured_content = doc_data["structured_content"]
        
        # 保存解析结果文件（供前端预览使用）
        parsed_content_dir = os.path.join("uploads", "parsed_content", document_id_for_content)
        os.makedirs(os.path.join("/app", parsed_content_dir), exist_ok=True)
        
        # 生成 parsed_content (完整Markdown) - 与 kb_document_processing 保持一致
        # 先进行分块以生成 sections
        temp_sections = WordDocumentService._split_by_sections_with_strategy(
            structured_content, strategy="level_1", max_tokens=8000
        )
        
        parsed_content_text = ""
        # 找到第一个一级标题的位置
        first_level1_heading_idx = None
        for idx, item in enumerate(structured_content):
            if item.get("type") == "heading" and item.get("level", 1) == 1:
                first_level1_heading_idx = idx
                break
        
        # 输出第一个一级标题之前的所有内容（封面页、表格等）
        if first_level1_heading_idx is not None and first_level1_heading_idx > 0:
            prefix_content = WordDocumentService._build_content_from_items(
                structured_content[:first_level1_heading_idx],
                doc_data,
                document_id_for_content,
                upload_id
            )
            if prefix_content:
                parsed_content_text += prefix_content + "\n\n"
        elif first_level1_heading_idx is None:
            # 没有一级标题，输出整个文档
            prefix_content = WordDocumentService._build_content_from_items(
                structured_content,
                doc_data,
                document_id_for_content,
                upload_id
            )
            if prefix_content:
                parsed_content_text += prefix_content + "\n\n"
        
        # 按章节输出每个章节的内容
        for section in temp_sections:
            section_content = WordDocumentService._build_section_content(
                section, doc_data, temp_sections.index(section), document_id_for_content, upload_id
            )
            if section_content:
                parsed_content_text += section_content + "\n\n"
        
        parsed_content_path = os.path.join(parsed_content_dir, "parsed_content.md")
        with open(os.path.join("/app", parsed_content_path), 'w', encoding='utf-8') as f:
            f.write(parsed_content_text)
        
        # 生成 summary_content (总结文档)
        summary_content_text = WordDocumentService._build_summary_content(
            doc_data, temp_sections, document_id_for_content, upload_id, document.file_name
        )
        summary_content_path = os.path.join(parsed_content_dir, "summary_content.md")
        with open(os.path.join("/app", summary_content_path), 'w', encoding='utf-8') as f:
            f.write(summary_content_text)
        
        # 保存 structured_content.json
        structured_content_path = os.path.join(parsed_content_dir, "structured_content.json")
        with open(os.path.join("/app", structured_content_path), 'w', encoding='utf-8') as f:
            json.dump(structured_content, f, ensure_ascii=False, indent=2)
        
        # 更新文档记录的路径
        document.parsed_content_path = parsed_content_path
        document.summary_content_path = summary_content_path
        document.structured_content_path = structured_content_path
        db.commit()
        
        self.update_progress(15, "步骤1: 文档解析完成")
        update_task_progress(db, task_id, 15, "步骤1: 文档解析完成", 1, 9)
        
        # ========== 步骤2: 智能分块 (15-25%) ==========
        self.update_progress(18, "步骤2: 智能分块")
        update_task_progress(db, task_id, 18, "步骤2: 智能分块", 1, 9)
        
        document.status = DocumentStatus.CHUNKING
        db.commit()
        
        # 如果策略是 "auto"，使用LLM智能选择
        if current_strategy == "auto":
            logger.info("使用LLM智能选择分块策略")
            strategy_result = loop.run_until_complete(
                smart_chunking.analyze_and_select_strategy(
                    structured_content=structured_content,
                    document_name=document.file_name,
                    metadata=doc_data.get("metadata")
                )
            )
            current_strategy = strategy_result["strategy"]
            logger.info(
                f"LLM选择分块策略: {current_strategy}, "
                f"原因: {strategy_result.get('reason', '')}, "
                f"置信度: {strategy_result.get('confidence', 0):.2f}"
            )
        
        # 执行分块
        sections = WordDocumentService._split_by_sections_with_strategy(
            structured_content,
            strategy=current_strategy,
            max_tokens=max_tokens_per_section
        )
        logger.info(f"分块完成: {len(sections)} 个块, 策略: {current_strategy}")
        
        # 评估分块质量
        chunking_quality = loop.run_until_complete(
            smart_chunking.evaluate_chunking_quality(sections, current_strategy)
        )
        logger.info(f"分块质量评估: 分数={chunking_quality['score']}, 通过={chunking_quality['passed']}")
        
        # 保存分块数据
        chunks_data = []
        for idx, section in enumerate(sections):
            chunk_id = section.get('chunk_id', f"chunk_{idx+1}")
            content = section.get('content', '')
            token_count = len(content) // 4
            
            chunks_data.append({
                "chunk_id": chunk_id,
                "title": section.get('title', f"块 {idx+1}"),
                "level": section.get('level', 1),
                "content": content,
                "start_index": section.get('start_index', 0),
                "end_index": section.get('end_index', 0),
                "token_count": token_count,
                "images": section.get('images', []),
                "tables": section.get('tables', [])
            })
        
        # 保存分块文件
        parsed_content_dir = os.path.join("uploads", "parsed_content", document_id_for_content)
        os.makedirs(os.path.join("/app", parsed_content_dir), exist_ok=True)
        
        chunks_path = os.path.join(parsed_content_dir, "chunks.json")
        with open(os.path.join("/app", chunks_path), 'w', encoding='utf-8') as f:
            json.dump({
                "upload_id": upload_id,
                "document_name": document.file_name,
                "strategy": current_strategy,
                "max_tokens": max_tokens_per_section,
                "total_chunks": len(chunks_data),
                "chunking_quality": chunking_quality,
                "chunks": chunks_data
            }, f, ensure_ascii=False, indent=2)
        
        document.chunks_path = chunks_path
        document.chunk_strategy = current_strategy
        db.commit()
        
        self.update_progress(25, "步骤2: 智能分块完成")
        update_task_progress(db, task_id, 25, "步骤2: 智能分块完成", 2, 9)
        
        # ========== 步骤3: LLM生成模板 (25-40%) ==========
        self.update_progress(30, "步骤3: 生成知识模板")
        update_task_progress(db, task_id, 30, "步骤3: 生成知识模板", 2, 9)
        
        from app.services.template_generation_service import TemplateGenerationService
        from app.models.template import EntityEdgeTemplate
        
        # 生成parsed_content用于模板生成
        parsed_content = "\n\n".join([c["content"] for c in chunks_data])
        
        # 生成模板
        if analysis_mode == "smart_segment":
            template_config = loop.run_until_complete(
                TemplateGenerationService.generate_template_smart_segment(
                    content=parsed_content,
                    document_name=document.file_name,
                    provider=provider
                )
            )
        else:
            template_config = loop.run_until_complete(
                TemplateGenerationService.generate_template_full_chunk(
                    content=parsed_content,
                    document_name=document.file_name
                )
            )
        
        # 验证模板
        from app.services.template_service import TemplateService
        is_valid, errors, warnings = TemplateService.validate_template(
            template_config.get("entity_types", {}),
            template_config.get("edge_types", {}),
            template_config.get("edge_type_map", {})
        )
        
        if not is_valid:
            raise Exception(f"模板验证失败: {', '.join(errors)}")
        
        # 保存模板
        doc_name = document.file_name.rsplit('.', 1)[0]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        template = EntityEdgeTemplate(
            name=f"LLM生成-{doc_name}-{timestamp}",
            description=f"基于文档'{document.file_name}'自动生成的模板",
            category="custom",
            entity_types=template_config.get("entity_types", {}),
            edge_types=template_config.get("edge_types", {}),
            edge_type_map=template_config.get("edge_type_map", {}),
            is_default=False,
            is_system=False,
            is_llm_generated=True,
            source_document_id=upload_id,
            analysis_mode=analysis_mode,
            llm_provider=provider,
            generated_at=datetime.now(),
            usage_count=0
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        document.template_id = template.id
        db.commit()
        
        self.update_progress(40, "步骤3: 模板生成完成")
        update_task_progress(db, task_id, 40, "步骤3: 模板生成完成", 3, 9)
        
        # ========== 步骤4: 生成智能摘要 (40-50%) ==========
        self.update_progress(45, "步骤4: 生成智能文档摘要")
        update_task_progress(db, task_id, 45, "步骤4: 生成智能文档摘要", 3, 9)
        
        # 提取原有概述内容
        original_overview = WordDocumentService._extract_overview_content(structured_content) \
            if hasattr(WordDocumentService, '_extract_overview_content') else None
        
        # 使用LLM生成智能摘要
        document_summary = loop.run_until_complete(
            DocumentSummaryService.generate_summary_with_retry(
                title=doc_name,
                structured_content=structured_content,
                overview_content=original_overview,
                metadata=doc_data.get("metadata", {}),
                max_retries=3,
                provider=provider
            )
        )
        
        logger.info(f"文档智能摘要生成完成，长度: {len(document_summary)}")
        
        # 保存摘要
        summary_path = os.path.join(parsed_content_dir, "smart_summary.md")
        with open(os.path.join("/app", summary_path), 'w', encoding='utf-8') as f:
            f.write(document_summary)
        
        self.update_progress(50, "步骤4: 智能摘要生成完成")
        update_task_progress(db, task_id, 50, "步骤4: 智能摘要生成完成", 4, 9)
        
        # ========== 步骤5: 创建文档级Episode (50-55%) ==========
        self.update_progress(52, "步骤5: 创建文档级Episode")
        update_task_progress(db, task_id, 52, "步骤5: 创建文档级Episode", 4, 9)
        
        # 转换模板配置
        entity_types_dict, edge_types_dict, edge_type_map_dict = TemplateService.convert_to_pydantic(
            template.entity_types,
            template.edge_types,
            template.edge_type_map
        )
        
        # 获取Graphiti实例
        graphiti = get_graphiti_instance(provider)
        
        # 生成group_id
        base_name = WordDocumentService._extract_base_name(document.file_name)
        version, version_number = WordDocumentService._extract_version(document.file_name)
        safe_base_name = WordDocumentService._sanitize_group_id(base_name)
        group_id = f"{safe_base_name}_{upload_id}"
        
        # 准备Episode内容：使用完整文档内容（parsed_content_text）
        # 估算token数量并限制长度（本地大模型最大上下文: 35,488 tokens，实际可用约25,000 tokens）
        def estimate_tokens(text: str) -> int:
            """估算文本的token数（中文通常1 token ≈ 2字符，英文1 token ≈ 4字符）"""
            chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
            other_chars = len(text) - chinese_chars
            return (chinese_chars // 2) + (other_chars // 4)
        
        episode_content = parsed_content_text
        max_episode_tokens = 25000  # 预留空间给prompt和completion
        estimated_tokens = estimate_tokens(episode_content)
        
        if estimated_tokens > max_episode_tokens:
            logger.warning(f"Episode内容过长，估算tokens: {estimated_tokens}，最大允许: {max_episode_tokens}，进行截断")
            # 按比例截断内容
            ratio = max_episode_tokens / estimated_tokens
            target_length = int(len(episode_content) * ratio * 0.9)  # 再留10%余量
            episode_content = episode_content[:target_length]
            # 尝试在句子或段落边界截断
            if '\n\n' in episode_content:
                episode_content = episode_content.rsplit('\n\n', 1)[0]
            elif '\n' in episode_content:
                episode_content = episode_content.rsplit('\n', 1)[0]
            logger.info(f"截断后Episode内容长度: {len(episode_content)} 字符，估算tokens: {estimate_tokens(episode_content)}")
        
        # 创建文档级Episode（使用完整文档内容）
        document_episode = loop.run_until_complete(graphiti.add_episode(
            name=f"{document.file_name}_文档级",
            episode_body=episode_content,  # 使用完整文档内容
            source_description="Word文档（完整内容）",
            reference_time=doc_data["metadata"].get("created") or datetime.now(),
            entity_types=entity_types_dict,
            edge_types=edge_types_dict,
            edge_type_map=edge_type_map_dict,
            group_id=group_id,
            previous_episode_uuids=[]
        ))
        
        document_episode_uuid = document_episode.episode.uuid
        logger.info(f"文档级Episode创建成功: {document_episode_uuid}")
        
        # 更新版本信息
        update_version_query = """
        MATCH (e:Episodic)
        WHERE e.uuid = $episode_uuid
        SET e.version = $version,
            e.version_number = $version_number,
            e.document_name = $document_name,
            e.file_path = $file_path
        RETURN e.uuid as uuid
        """
        neo4j_client.execute_write(update_version_query, {
            "episode_uuid": document_episode_uuid,
            "version": version,
            "version_number": version_number,
            "document_name": document.file_name,
            "file_path": file_path_abs
        })
        
        self.update_progress(55, "步骤5: 文档级Episode创建完成")
        update_task_progress(db, task_id, 55, "步骤5: 文档级Episode创建完成", 5, 9)
        
        # ========== 步骤6: 处理章节内容到 Milvus (55-75%) ==========
        # 注意：不再创建章节、图片、表格 Episode，改为存储到 Milvus
        self.update_progress(60, "步骤6: 处理章节内容到 Milvus")
        update_task_progress(db, task_id, 60, "步骤6: 处理章节内容到 Milvus", 6, 9)
        
        reference_time = doc_data["metadata"].get("created") or datetime.now()
        
        # 存储章节内容到 Milvus
        section_vectors = []
        section_vectors_all = []  # 保存所有章节向量，用于后续 Cognee 构建
        if settings.ENABLE_MILVUS and chunks_data:
            try:
                from app.services.milvus_service import get_milvus_service, VectorType
                
                milvus = get_milvus_service()
                if milvus.is_available():
                    # 获取 embedder（使用已创建的 graphiti 实例）
                    embedder = graphiti.embedder
                    
                    logger.info(f"开始处理 {len(chunks_data)} 个章节到 Milvus")
                    
                    # 批量生成向量并存储
                    for idx, section in enumerate(chunks_data):
                        try:
                            # 生成章节向量
                            section_content = section.get("content", "")
                            if not section_content.strip():
                                continue
                            
                            # 生成 embedding（OpenAIEmbedder 使用 create 方法）
                            try:
                                embedding = loop.run_until_complete(embedder.create(section_content))
                            except AttributeError:
                                # 如果 create 不存在，尝试 embed
                                try:
                                    embedding = loop.run_until_complete(embedder.embed(section_content))
                                except AttributeError:
                                    logger.error(f"Embedder 没有 embed 或 create 方法")
                                    continue
                            
                            # 生成章节 UUID
                            import uuid as uuid_lib
                            section_uuid = str(uuid_lib.uuid4())
                            
                            # 准备向量数据
                            section_vector = {
                                "uuid": section_uuid,
                                "name": section.get("title", f"章节_{idx+1}"),
                                "group_id": group_id,
                                "content": section_content,
                                "embedding": embedding
                            }
                            section_vectors.append(section_vector)
                            section_vectors_all.append(section_vector)  # 同时保存到总列表
                            
                            # 每 10 个章节批量插入一次
                            if len(section_vectors) >= 10:
                                milvus.insert_vectors(VectorType.SECTION, section_vectors)
                                logger.info(f"已插入 {len(section_vectors)} 个章节向量到 Milvus")
                                section_vectors = []  # 清空批量列表，但保留 section_vectors_all
                        
                        except Exception as e:
                            logger.error(f"处理章节 {idx+1} 失败: {e}")
                            continue
                    
                    # 插入剩余的章节向量
                    if section_vectors:
                        milvus.insert_vectors(VectorType.SECTION, section_vectors)
                        logger.info(f"已插入剩余 {len(section_vectors)} 个章节向量到 Milvus")
                    
                    logger.info(f"章节内容存储到 Milvus 完成，共 {len(chunks_data)} 个章节")
                    
                    # 步骤6.5: 使用 Cognee 构建章节知识图谱
                    try:
                        logger.info("开始使用 Cognee 构建章节知识图谱...")
                        logger.info(f"章节数据准备: chunks_data数量={len(chunks_data)}, section_vectors_all数量={len(section_vectors_all)}")
                        
                        # 初始化 CogneeService
                        # 注意：Cognee 模块已在 worker 启动时预加载，所以这里应该很快
                        cognee_service = None
                        try:
                            logger.info("正在初始化 CogneeService...")
                            import time
                            start_time = time.time()
                            
                            # 直接初始化（因为模块已预加载，应该很快）
                            # 如果预加载失败，这里会重新尝试，但应该不会阻塞太久
                            cognee_service = CogneeService()
                            elapsed_time = time.time() - start_time
                            logger.info(f"CogneeService 初始化成功，耗时: {elapsed_time:.2f}秒")
                        except Exception as init_e:
                            elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
                            logger.error(f"CogneeService 初始化失败（耗时: {elapsed_time:.2f}秒）: {init_e}", exc_info=True)
                            cognee_service = None  # 确保设置为 None
                        
                        # 准备章节数据（包含 uuid）
                        # 创建一个映射：章节标题 -> uuid（从 section_vectors_all 中）
                        section_uuid_map = {}
                        for sv in section_vectors_all:
                            section_uuid_map[sv.get("name")] = sv.get("uuid")
                        logger.info(f"章节UUID映射创建完成，共 {len(section_uuid_map)} 个映射")
                        
                        sections_for_cognee = []
                        for idx, chunk in enumerate(chunks_data):
                            section_title = chunk.get("title", f"章节_{idx+1}")
                            section_uuid = section_uuid_map.get(section_title)
                            
                            # 如果没找到，生成一个（应该不会发生，但保险起见）
                            if not section_uuid:
                                import uuid as uuid_lib
                                section_uuid = str(uuid_lib.uuid4())
                                logger.warning(f"章节 '{section_title}' 的 UUID 未找到，生成新 UUID: {section_uuid}")
                            
                            sections_for_cognee.append({
                                "title": section_title,
                                "content": chunk.get("content", ""),
                                "uuid": section_uuid
                            })
                        
                        # 只有在 CogneeService 初始化成功时才继续
                        if cognee_service is None:
                            logger.warning("CogneeService 未初始化，跳过 Cognee 知识图谱构建")
                        elif sections_for_cognee:
                            logger.info(f"准备调用 Cognee，章节数量: {len(sections_for_cognee)}")
                            logger.info(f"Cognee 调用参数: upload_id={upload_id}, document_name={document.file_name if document else 'None'}")
                            try:
                                import time
                                cognee_start_time = time.time()
                                logger.info(f"开始调用 build_section_knowledge_graph，group_id={group_id}, upload_id={upload_id}")
                                
                                cognee_result = loop.run_until_complete(
                                    cognee_service.build_section_knowledge_graph(
                                        sections=sections_for_cognee,
                                        group_id=group_id,
                                        max_concurrent=3,
                                        provider=provider,
                                        upload_id=upload_id,
                                        document_name=document.file_name if document else None
                                    )
                                )
                                
                                cognee_elapsed_time = time.time() - cognee_start_time
                                logger.info(f"Cognee 构建返回结果（耗时: {cognee_elapsed_time:.2f}秒）: {cognee_result}")
                                
                                if cognee_result.get("success"):
                                    logger.info(
                                        f"Cognee 章节知识图谱构建成功: "
                                        f"成功={cognee_result['results']['success']}, "
                                        f"失败={cognee_result['results']['failed']}, "
                                        f"dataset={cognee_result.get('dataset_name', '未知')}, "
                                        f"使用模板={cognee_result.get('template_used', False)}"
                                    )
                                    
                                    # 检查模板是否已保存
                                    if upload_id and document:
                                        from app.models.template import EntityEdgeTemplate
                                        db_check = SessionLocal()
                                        try:
                                            cognee_templates = db_check.query(EntityEdgeTemplate).filter(
                                                EntityEdgeTemplate.source_document_id == upload_id,
                                                EntityEdgeTemplate.analysis_mode.like('cognee_section%')
                                            ).all()
                                            if cognee_templates:
                                                logger.info(f"✅ Cognee 章节级别模板已保存到数据库，共 {len(cognee_templates)} 个模板")
                                                for t in cognee_templates:
                                                    logger.info(f"  - 模板ID: {t.id}, 名称: {t.name}, 实体类型数: {len(t.entity_types) if t.entity_types else 0}")
                                            else:
                                                logger.warning(f"⚠️ 未找到 Cognee 章节级别模板（upload_id={upload_id}），可能未保存")
                                        except Exception as check_e:
                                            logger.error(f"检查 Cognee 模板保存状态失败: {check_e}", exc_info=True)
                                        finally:
                                            db_check.close()
                                else:
                                    logger.warning(
                                        f"Cognee 章节知识图谱构建失败: {cognee_result.get('error', 'Unknown error')}"
                                    )
                            except Exception as inner_e:
                                logger.error(f"Cognee 构建过程中发生异常: {inner_e}", exc_info=True)
                                raise
                        else:
                            logger.warning("没有章节数据，跳过 Cognee 知识图谱构建")
                    except Exception as e:
                        logger.error(f"Cognee 章节知识图谱构建失败: {e}", exc_info=True)
                        logger.error(f"异常详情: {type(e).__name__}: {str(e)}", exc_info=True)
                        # 不中断流程，继续执行
                        logger.info("Cognee 构建失败，但继续执行后续步骤（步骤7：同步向量到Milvus）")
                else:
                    logger.warning("Milvus 不可用，跳过章节内容存储和 Cognee 知识图谱构建")
            except Exception as e:
                logger.error(f"存储章节内容到 Milvus 失败: {e}")
        else:
            logger.info(f"跳过章节、图片、表格 Episode 创建，章节内容将存储到 Milvus（共 {len(chunks_data)} 个章节）")
        
        self.update_progress(75, "步骤6: 章节内容处理完成（Milvus + Cognee）")
        update_task_progress(db, task_id, 75, "步骤6: 章节内容处理完成（Milvus + Cognee）", 6, 9)
        logger.info("=" * 60)
        logger.info("步骤6完成，开始执行步骤7")
        logger.info("=" * 60)
        
        # ========== 步骤7: 同步向量到Milvus (75-80%) ==========
        logger.info("开始执行步骤7: 同步向量到Milvus")
        self.update_progress(77, "步骤7: 同步向量到Milvus")
        update_task_progress(db, task_id, 77, "步骤7: 同步向量到Milvus", 7, 9)
        
        milvus_sync_result = {"success": False, "reason": "disabled"}
        if settings.ENABLE_MILVUS:
            try:
                logger.info("初始化 VectorDualWriteService...")
                dual_write_service = VectorDualWriteService()
                logger.info(f"开始同步向量到Milvus，group_id={group_id}")
                milvus_sync_result = loop.run_until_complete(
                    dual_write_service.batch_sync_from_neo4j(group_id=group_id)
                )
                logger.info(f"✅ Milvus向量同步完成: {milvus_sync_result}")
            except Exception as e:
                logger.warning(f"⚠️ Milvus向量同步失败（不影响主流程）: {e}", exc_info=True)
                milvus_sync_result = {"success": False, "error": str(e)}
        else:
            logger.info("Milvus未启用，跳过向量同步")
        
        logger.info("步骤7执行完成")
        self.update_progress(80, "步骤7: Milvus同步完成")
        update_task_progress(db, task_id, 80, "步骤7: Milvus同步完成", 7, 9)
        logger.info("=" * 60)
        logger.info("步骤7完成，开始执行步骤8")
        logger.info("=" * 60)
        
        # ========== 步骤8: 自动构建Community (80-85%) ==========
        self.update_progress(81, "步骤8: 构建Community")
        update_task_progress(db, task_id, 81, "步骤8: 构建Community", 8, 9)
        
        community_result = {"success": False, "reason": "disabled"}
        if settings.ENABLE_AUTO_COMMUNITY:
            try:
                auto_community_service = AutoCommunityService(provider=provider)
                # 从配置读取超时时间（默认180秒）
                timeout_seconds = getattr(settings, 'COMMUNITY_BUILD_TIMEOUT', 180.0)
                
                # 使用线程池执行异步任务，确保超时能够强制中断阻塞操作
                import concurrent.futures
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                
                # 在新线程中创建新的事件循环并运行异步任务
                def run_async_task():
                    # 在新线程中创建新的事件循环
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            auto_community_service.build_community_for_document(
                                group_id=group_id,
                                document_name=document.file_name,
                                sync_to_milvus=settings.ENABLE_MILVUS
                            )
                        )
                    finally:
                        # 关闭事件循环
                        try:
                            new_loop.close()
                        except Exception:
                            pass  # 忽略关闭时的错误
                
                # 在线程池中运行，并设置超时（线程级别的超时可以中断阻塞操作）
                future = executor.submit(run_async_task)
                try:
                    community_result = future.result(timeout=timeout_seconds)
                    logger.info(f"Community构建完成: {community_result}")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Community构建超时（{timeout_seconds}秒），强制中断")
                    community_result = {"success": False, "reason": "timeout"}
                    # 尝试取消任务（如果可能）
                    future.cancel()
                finally:
                    executor.shutdown(wait=False)  # 不等待，立即关闭
                    
            except Exception as e:
                logger.warning(f"Community构建失败（不影响主流程）: {e}")
                community_result = {"success": False, "error": str(e)}
        else:
            logger.info("自动Community构建未启用，跳过")
        
        self.update_progress(85, "步骤8: Community构建完成")
        update_task_progress(db, task_id, 85, "步骤8: Community构建完成", 8, 9)
        
        # ========== 步骤9: 质量评估 (85-95%) ==========
        if enable_quality_gate:
            self.update_progress(86, "步骤9: 质量评估")
            update_task_progress(db, task_id, 86, "步骤9: 质量评估", 9, 9)
            
            # 获取提取的实体和关系
            entities_query = """
            MATCH (e:Entity)
            WHERE e.group_id = $group_id
            RETURN e.uuid as uuid, e.name as name, labels(e) as labels, e.summary as summary
            """
            entities_result = neo4j_client.execute_query(entities_query, {"group_id": group_id})
            entities = [dict(r) for r in entities_result] if entities_result else []
            
            relationships_query = """
            MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
            WHERE r.group_id = $group_id
            RETURN r.uuid as uuid, r.name as name, a.name as source_name, b.name as target_name
            """
            relationships_result = neo4j_client.execute_query(relationships_query, {"group_id": group_id})
            relationships = [dict(r) for r in relationships_result] if relationships_result else []
            
            # 评估提取质量
            extraction_quality_service = ExtractionQualityService()
            extraction_quality = loop.run_until_complete(
                extraction_quality_service.evaluate_extraction_quality(
                    entities=entities,
                    relationships=relationships,
                    source_content=parsed_content[:10000],
                    document_name=document.file_name,
                    provider=provider
                )
            )
            
            # 评估图结构质量
            graph_quality_service = GraphQualityService()
            graph_quality = graph_quality_service.evaluate(
                entities=entities,
                relationships=relationships,
                communities=[]  # 社区稍后创建
            )
            
            # 综合评估
            quality_result = quality_gate.evaluate(
                chunking_result=chunking_quality,
                extraction_result=extraction_quality,
                graph_result=graph_quality,
                current_retry=retry_count,
                current_strategy=current_strategy
            )
            
            logger.info(
                f"质量评估完成: 状态={quality_result.status.value}, "
                f"总分={quality_result.overall_score:.1f}"
            )
            
            # 保存质量评估结果
            quality_report_path = os.path.join(parsed_content_dir, "quality_report.json")
            with open(os.path.join("/app", quality_report_path), 'w', encoding='utf-8') as f:
                json.dump({
                    "status": quality_result.status.value,
                    "overall_score": quality_result.overall_score,
                    "chunking_score": quality_result.chunking_score,
                    "extraction_score": quality_result.extraction_score,
                    "graph_score": quality_result.graph_score,
                    "issues": quality_result.issues,
                    "suggestions": quality_result.suggestions,
                    "entity_count": len(entities),
                    "relationship_count": len(relationships),
                    "section_count": len(chunks_data) if chunks_data else 0
                }, f, ensure_ascii=False, indent=2)
            
            # 如果需要人工审核
            if quality_result.status == QualityStatus.MANUAL_REVIEW:
                document.status = DocumentStatus.PENDING_REVIEW
                document.quality_score = quality_result.overall_score
                db.commit()
                logger.warning(f"文档需要人工审核: {document.file_name}")
        
        self.update_progress(95, "步骤9: 质量评估完成")
        update_task_progress(db, task_id, 95, "步骤9: 质量评估完成", 9, 9)
        
        # ========== 步骤10: 完成处理 (95-100%) ==========
        self.update_progress(98, "步骤10: 完成处理")
        
        # 更新文档状态
        document.status = DocumentStatus.COMPLETED
        document.document_id = group_id  # 设置 document_id（group_id），供前端使用
        document.completed_at = datetime.now()
        db.commit()
        
        # 更新任务状态
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now()
            task.result = {
                "success": True,
                "group_id": group_id,
                "document_episode_uuid": document_episode_uuid,
                "section_count": len(chunks_data) if chunks_data else 0,
                "entity_count": len(entities) if enable_quality_gate else "未评估",
                "relationship_count": len(relationships) if enable_quality_gate else "未评估",
                "quality_score": quality_result.overall_score if enable_quality_gate else None,
                "milvus_sync": milvus_sync_result,
                "community": community_result
            }
            db.commit()
        
        self.update_progress(100, "处理完成")
        # 步骤10是完成处理，但总步骤数仍然是9（因为步骤10不是实际的处理步骤，只是标记完成）
        update_task_progress(db, task_id, 100, "处理完成", 9, 9)
        
        logger.info(f"文档处理完成: upload_id={upload_id}, group_id={group_id}")
        
        return {
            "success": True,
            "upload_id": upload_id,
            "group_id": group_id,
            "document_episode_uuid": document_episode_uuid,
            "section_count": len(chunks_data) if chunks_data else 0
        }
        
    except Exception as e:
        logger.error(f"文档处理失败: {e}", exc_info=True)
        
        # 更新文档状态
        if document:
            document.status = DocumentStatus.ERROR  # 使用 ERROR 而不是 FAILED
            document.error_message = str(e)
            db.commit()
        
        # 更新任务状态
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
        
        raise
        
    finally:
        db.close()
        # 安全关闭事件循环
        try:
            if loop and not loop.is_closed():
                # 如果循环还在运行，先停止它
                if loop.is_running():
                    loop.stop()
                loop.close()
        except Exception as e:
            logger.warning(f"关闭事件循环时出错: {e}")
        # 关闭 Episode 处理器
        try:
            episode_processor.shutdown()
        except Exception as e:
            logger.warning(f"关闭 Episode 处理器时出错: {e}")

