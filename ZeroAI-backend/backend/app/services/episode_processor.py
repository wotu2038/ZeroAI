"""
Episode 并发处理器

支持并发创建章节 Episode，提升处理效率
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from app.core.config import settings

logger = logging.getLogger(__name__)


class EpisodeProcessor:
    """
    Episode 并发处理器
    
    支持并发创建章节级 Episode，同时保持与文档级 Episode 的正确关联
    """
    
    # 默认最大并发数（可通过 .env 配置）
    DEFAULT_MAX_CONCURRENT = 5
    
    def __init__(self, max_concurrent: int = None):
        """
        初始化处理器
        
        Args:
            max_concurrent: 最大并发数，默认从配置读取
        """
        self.max_concurrent = max_concurrent or getattr(
            settings, 
            'EPISODE_MAX_CONCURRENT', 
            self.DEFAULT_MAX_CONCURRENT
        )
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent)
        
        logger.info(f"EpisodeProcessor 初始化: max_concurrent={self.max_concurrent}")
    
    async def process_sections_concurrently(
        self,
        graphiti,
        sections: List[Dict],
        document_episode_uuid: str,
        entity_types: Dict,
        edge_types: Dict,
        edge_type_map: Dict,
        group_id: str,
        document_name: str,
        reference_time: datetime,
        progress_callback: callable = None
    ) -> List[str]:
        """
        并发处理章节 Episode
        
        所有章节 Episode 的 previous_episode_uuids 只包含文档级 Episode，
        这样可以安全地并发创建。
        
        Args:
            graphiti: Graphiti 实例
            sections: 章节列表，每个包含 title, content, images, tables 等
            document_episode_uuid: 文档级 Episode 的 UUID
            entity_types: 实体类型定义
            edge_types: 边类型定义
            edge_type_map: 边类型映射
            group_id: 文档分组 ID
            document_name: 文档名称
            reference_time: 参考时间
            progress_callback: 进度回调函数 (current, total, section_title)
            
        Returns:
            创建成功的 Episode UUID 列表
        """
        if not sections:
            logger.warning("没有章节需要处理")
            return []
        
        total = len(sections)
        logger.info(f"开始并发处理 {total} 个章节 Episode (并发数: {self.max_concurrent})")
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_single_section(idx: int, section: Dict) -> Optional[str]:
            """处理单个章节"""
            async with semaphore:
                try:
                    section_title = section.get("title", f"章节{idx+1}")[:30]
                    section_content = section.get("content", "")
                    
                    # 构建章节内容（包含图片和表格的引用）
                    content_with_refs = self._build_section_content_with_refs(
                        section_content=section_content,
                        images=section.get("images", []),
                        tables=section.get("tables", [])
                    )
                    
                    if not content_with_refs.strip():
                        logger.warning(f"章节 '{section_title}' 内容为空，跳过")
                        return None
                    
                    # 创建 Episode
                    episode = await graphiti.add_episode(
                        name=f"{document_name}_章节_{section_title}",
                        episode_body=content_with_refs,
                        source_description=f"Word文档章节: {section_title}",
                        reference_time=reference_time,
                        entity_types=entity_types,
                        edge_types=edge_types,
                        edge_type_map=edge_type_map,
                        group_id=group_id,
                        previous_episode_uuids=[document_episode_uuid]  # 只包含文档级
                    )
                    
                    episode_uuid = episode.episode.uuid
                    logger.info(f"章节 Episode 创建成功: {section_title} -> {episode_uuid}")
                    
                    # 进度回调
                    if progress_callback:
                        progress_callback(idx + 1, total, section_title)
                    
                    return episode_uuid
                    
                except Exception as e:
                    logger.error(f"创建章节 Episode 失败: {section.get('title', 'unknown')}, error: {e}")
                    return None
        
        # 并发执行所有章节
        tasks = [
            process_single_section(idx, section)
            for idx, section in enumerate(sections)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 过滤成功的结果
        successful_uuids = [uuid for uuid in results if uuid is not None]
        
        logger.info(
            f"并发处理完成: 成功 {len(successful_uuids)}/{total} 个章节"
        )
        
        return successful_uuids
    
    def _build_section_content_with_refs(
        self,
        section_content: str,
        images: List[Dict],
        tables: List[Dict]
    ) -> str:
        """
        构建包含图片和表格引用的章节内容
        
        图片和表格仍然作为独立 Episode 创建，
        但在章节内容中保留引用信息
        """
        content = section_content
        
        # 添加图片引用
        if images:
            content += "\n\n【本章节包含的图片】\n"
            for idx, img in enumerate(images, 1):
                img_desc = img.get("description") or img.get("alt_text") or f"图片{idx}"
                content += f"- 图{idx}: {img_desc}\n"
        
        # 添加表格引用
        if tables:
            content += "\n\n【本章节包含的表格】\n"
            for idx, table in enumerate(tables, 1):
                table_summary = self._summarize_table(table)
                content += f"- 表{idx}: {table_summary}\n"
        
        return content
    
    def _summarize_table(self, table: Dict) -> str:
        """生成表格摘要"""
        # 尝试获取表格的标题或第一行
        if isinstance(table, dict):
            if table.get("title"):
                return table["title"][:50]
            if table.get("headers"):
                return f"包含列: {', '.join(table['headers'][:5])}"
            if table.get("content"):
                # 如果是文本内容，取前50字符
                return table["content"][:50] + "..."
        
        return "数据表格"
    
    async def process_images_concurrently(
        self,
        graphiti,
        images: List[Dict],
        document_episode_uuid: str,
        entity_types: Dict,
        edge_types: Dict,
        edge_type_map: Dict,
        group_id: str,
        document_name: str,
        reference_time: datetime
    ) -> List[str]:
        """
        并发处理图片 Episode
        
        Args:
            graphiti: Graphiti 实例
            images: 图片列表
            其他参数同 process_sections_concurrently
            
        Returns:
            创建成功的 Episode UUID 列表
        """
        if not images:
            return []
        
        logger.info(f"开始并发处理 {len(images)} 个图片 Episode")
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_single_image(idx: int, image: Dict) -> Optional[str]:
            async with semaphore:
                try:
                    # 构建图片描述
                    image_content = self._build_image_content(image, idx)
                    
                    if not image_content.strip():
                        return None
                    
                    episode = await graphiti.add_episode(
                        name=f"{document_name}_图片_{idx+1}",
                        episode_body=image_content,
                        source_description="Word文档图片",
                        reference_time=reference_time,
                        entity_types=entity_types,
                        edge_types=edge_types,
                        edge_type_map=edge_type_map,
                        group_id=group_id,
                        previous_episode_uuids=[document_episode_uuid]
                    )
                    
                    return episode.episode.uuid
                    
                except Exception as e:
                    logger.error(f"创建图片 Episode 失败: 图片{idx+1}, error: {e}")
                    return None
        
        tasks = [
            process_single_image(idx, image)
            for idx, image in enumerate(images)
        ]
        
        results = await asyncio.gather(*tasks)
        return [uuid for uuid in results if uuid is not None]
    
    def _build_image_content(self, image: Dict, idx: int) -> str:
        """构建图片 Episode 内容"""
        content = f"## 图片 {idx + 1}\n\n"
        
        # 图片描述
        description = image.get("description") or image.get("alt_text") or ""
        if description:
            content += f"**描述**: {description}\n\n"
        
        # 图片上下文
        context = image.get("context") or image.get("section_title") or ""
        if context:
            content += f"**所在章节**: {context}\n\n"
        
        # OCR 文本（如果有）
        ocr_text = image.get("ocr_text") or image.get("extracted_text") or ""
        if ocr_text:
            content += f"**图中文字**: {ocr_text}\n\n"
        
        return content
    
    async def process_tables_concurrently(
        self,
        graphiti,
        tables: List[Dict],
        document_episode_uuid: str,
        entity_types: Dict,
        edge_types: Dict,
        edge_type_map: Dict,
        group_id: str,
        document_name: str,
        reference_time: datetime
    ) -> List[str]:
        """
        并发处理表格 Episode
        
        Args:
            graphiti: Graphiti 实例
            tables: 表格列表
            其他参数同 process_sections_concurrently
            
        Returns:
            创建成功的 Episode UUID 列表
        """
        if not tables:
            return []
        
        logger.info(f"开始并发处理 {len(tables)} 个表格 Episode")
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_single_table(idx: int, table: Dict) -> Optional[str]:
            async with semaphore:
                try:
                    # 构建表格内容
                    table_content = self._build_table_content(table, idx)
                    
                    if not table_content.strip():
                        return None
                    
                    episode = await graphiti.add_episode(
                        name=f"{document_name}_表格_{idx+1}",
                        episode_body=table_content,
                        source_description="Word文档表格",
                        reference_time=reference_time,
                        entity_types=entity_types,
                        edge_types=edge_types,
                        edge_type_map=edge_type_map,
                        group_id=group_id,
                        previous_episode_uuids=[document_episode_uuid]
                    )
                    
                    return episode.episode.uuid
                    
                except Exception as e:
                    logger.error(f"创建表格 Episode 失败: 表格{idx+1}, error: {e}")
                    return None
        
        tasks = [
            process_single_table(idx, table)
            for idx, table in enumerate(tables)
        ]
        
        results = await asyncio.gather(*tasks)
        return [uuid for uuid in results if uuid is not None]
    
    def _build_table_content(self, table: Dict, idx: int) -> str:
        """构建表格 Episode 内容"""
        content = f"## 表格 {idx + 1}\n\n"
        
        # 表格标题
        title = table.get("title") or ""
        if title:
            content += f"**标题**: {title}\n\n"
        
        # 表格上下文
        context = table.get("context") or table.get("section_title") or ""
        if context:
            content += f"**所在章节**: {context}\n\n"
        
        # 表格内容
        if table.get("markdown"):
            content += table["markdown"] + "\n\n"
        elif table.get("content"):
            content += table["content"] + "\n\n"
        elif table.get("rows"):
            # 尝试转换为 Markdown 表格
            content += self._rows_to_markdown(table["rows"], table.get("headers", []))
        
        return content
    
    def _rows_to_markdown(self, rows: List[List], headers: List = None) -> str:
        """将表格行转换为 Markdown 格式"""
        if not rows:
            return ""
        
        lines = []
        
        # 表头
        if headers:
            lines.append("| " + " | ".join(str(h) for h in headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
        elif rows:
            # 使用第一行作为表头
            lines.append("| " + " | ".join(str(c) for c in rows[0]) + " |")
            lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
            rows = rows[1:]
        
        # 数据行
        for row in rows[:20]:  # 限制行数
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        
        if len(rows) > 20:
            lines.append(f"... (共 {len(rows)} 行)")
        
        return "\n".join(lines) + "\n"
    
    def shutdown(self):
        """关闭处理器"""
        self.executor.shutdown(wait=True)
        logger.info("EpisodeProcessor 已关闭")

