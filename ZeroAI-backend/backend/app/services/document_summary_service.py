"""
文档智能摘要服务

使用 LLM 生成高质量的文档摘要，用于文档级 Episode
"""
import logging
import json
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class DocumentSummaryService:
    """文档智能摘要服务"""
    
    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
    
    @staticmethod
    async def generate_summary_with_retry(
        title: str,
        structured_content: List[Dict],
        overview_content: str = None,
        metadata: Dict = None,
        max_retries: int = 3,
        provider: str = "local"
    ) -> str:
        """
        生成文档智能摘要（带重试机制）
        
        Args:
            title: 文档标题
            structured_content: 解析后的文档结构
            overview_content: 原有概述内容（如果有）
            metadata: 文档元数据
            max_retries: 最大重试次数
            
        Returns:
            生成的文档摘要
        """
        service = DocumentSummaryService()
        
        for attempt in range(max_retries):
            try:
                # 生成摘要
                summary = await service.generate_smart_summary(
                    title=title,
                    structured_content=structured_content,
                    overview_content=overview_content,
                    metadata=metadata,
                    provider=provider
                )
                
                # 质量检查
                quality = service._check_summary_quality(summary, title)
                
                if quality["passed"]:
                    logger.info(f"文档摘要生成成功，质量分数: {quality['score']}")
                    return summary
                else:
                    logger.warning(
                        f"摘要质量不达标 (分数: {quality['score']}, 问题: {quality['issues']}), "
                        f"重试 {attempt + 1}/{max_retries}"
                    )
                    
            except Exception as e:
                logger.error(f"生成摘要失败 (尝试 {attempt + 1}/{max_retries}): {e}")
        
        # 重试失败，使用回退方案
        logger.warning("LLM摘要生成失败，使用回退方案")
        return service._fallback_summary(
            title=title,
            toc=service._extract_toc(structured_content),
            overview=overview_content,
            metadata=metadata
        )
    
    async def generate_smart_summary(
        self,
        title: str,
        structured_content: List[Dict],
        overview_content: str = None,
        metadata: Dict = None,
        provider: str = "local"
    ) -> str:
        """
        使用 LLM 生成智能文档摘要
        
        摘要包含：
        1. 文档主题与目的
        2. 核心内容概括
        3. 关键实体预告
        4. 文档结构说明
        5. 适用场景
        """
        # 提取文档结构信息
        toc = self._extract_toc(structured_content)
        key_sections = self._extract_key_sections(structured_content)
        
        # 构建 prompt
        prompt = f"""你是一个专业的文档分析专家。请为以下文档生成一份高质量的智能摘要。

## 文档信息
- 标题: {title}
{self._format_metadata(metadata)}

## 目录结构
{toc}

## 关键章节内容预览
{key_sections}

{("## 原有概述" + chr(10) + overview_content + chr(10)) if overview_content else ""}

## 摘要要求
请生成一份结构化的文档摘要，包含以下部分：

### 1. 文档主题与目的（必须）
- 简洁描述这份文档是关于什么的
- 说明文档的核心目的

### 2. 核心内容概括（必须）
- 提取文档的3-5个核心要点
- 每个要点用一句话概括

### 3. 关键实体预告（必须）
- 列出文档中可能出现的重要实体类型
- 例如：需求、功能模块、技术方案、用户角色等

### 4. 文档结构说明（必须）
- 说明文档的组织结构
- 各章节之间的逻辑关系

### 5. 适用场景（可选）
- 这份文档适合在什么场景下参考

## 格式要求
- 使用 Markdown 格式
- 内容要准确、专业、简洁
- 总长度控制在 500-1000 字
- 必须基于文档实际内容，不要臆造

请直接输出摘要内容：
"""
        
        response = await self.llm_client.chat(
            provider=provider,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        return response.strip()
    
    def _extract_toc(self, structured_content: List[Dict]) -> str:
        """提取目录结构"""
        toc_lines = []
        for item in structured_content:
            if item.get("type") == "heading":
                level = item.get("level", 1)
                indent = "  " * (level - 1)
                title = item.get("content", "")[:60]
                toc_lines.append(f"{indent}- {title}")
                
                # 限制目录长度
                if len(toc_lines) >= 30:
                    toc_lines.append("  ...")
                    break
        
        return "\n".join(toc_lines) if toc_lines else "（无标题结构）"
    
    def _extract_key_sections(self, structured_content: List[Dict], max_chars: int = 3000) -> str:
        """提取关键章节内容"""
        sections = []
        current_section = None
        current_content = []
        total_chars = 0
        
        for item in structured_content:
            if item.get("type") == "heading" and item.get("level", 1) <= 2:
                # 保存上一个章节
                if current_section and current_content:
                    content = "\n".join(current_content)[:500]
                    sections.append(f"### {current_section}\n{content}")
                    total_chars += len(content) + len(current_section)
                    
                    if total_chars >= max_chars:
                        break
                
                current_section = item.get("content", "")
                current_content = []
                
            elif item.get("type") == "paragraph" and current_section:
                current_content.append(item.get("content", ""))
        
        # 保存最后一个章节
        if current_section and current_content and total_chars < max_chars:
            content = "\n".join(current_content)[:500]
            sections.append(f"### {current_section}\n{content}")
        
        return "\n\n".join(sections) if sections else "（无章节内容）"
    
    def _format_metadata(self, metadata: Dict) -> str:
        """格式化元数据"""
        if not metadata:
            return ""
        
        lines = []
        if metadata.get("author"):
            lines.append(f"- 作者: {metadata['author']}")
        if metadata.get("created"):
            lines.append(f"- 创建时间: {metadata['created']}")
        if metadata.get("modified"):
            lines.append(f"- 修改时间: {metadata['modified']}")
        
        return "\n".join(lines)
    
    def _check_summary_quality(self, summary: str, title: str) -> Dict[str, Any]:
        """
        轻量级质量检查
        
        检查项：
        1. 长度是否合适 (300-2000字)
        2. 是否包含必要章节
        3. 是否与文档标题相关
        """
        issues = []
        score = 100
        
        # 长度检查
        length = len(summary)
        if length < 200:
            issues.append("摘要过短")
            score -= 30
        elif length > 3000:
            issues.append("摘要过长")
            score -= 10
        
        # 必要章节检查
        required_sections = ["文档主题", "核心内容", "关键实体", "文档结构"]
        for section in required_sections:
            if section not in summary:
                issues.append(f"缺少 {section} 章节")
                score -= 10
        
        # 标题相关性检查（简单的关键词匹配）
        title_keywords = set(title.replace(".", " ").replace("-", " ").split())
        summary_lower = summary.lower()
        matched = sum(1 for kw in title_keywords if kw.lower() in summary_lower)
        if matched < len(title_keywords) * 0.3:
            issues.append("与文档标题相关性不足")
            score -= 15
        
        threshold = getattr(settings, 'SUMMARY_QUALITY_THRESHOLD', 60)
        
        return {
            "score": max(0, score),
            "passed": score >= threshold,
            "issues": issues
        }
    
    @staticmethod
    def _fallback_summary(
        title: str,
        toc: str,
        overview: str = None,
        metadata: Dict = None
    ) -> str:
        """
        回退方案：与当前实现完全一致的格式
        
        当 LLM 生成失败时，使用规则生成的格式
        """
        summary = "## 文档概览\n\n"
        
        # 基本信息
        summary += "### 基本信息\n\n"
        summary += f"- **文档标题**: {title}\n"
        if metadata:
            if metadata.get("author"):
                summary += f"- **作者**: {metadata['author']}\n"
            if metadata.get("created"):
                created = metadata['created']
                if hasattr(created, 'strftime'):
                    created = created.strftime('%Y-%m-%d %H:%M:%S')
                summary += f"- **创建时间**: {created}\n"
            if metadata.get("modified"):
                modified = metadata['modified']
                if hasattr(modified, 'strftime'):
                    modified = modified.strftime('%Y-%m-%d %H:%M:%S')
                summary += f"- **修改时间**: {modified}\n"
        summary += "\n"
        
        # 章节结构
        summary += "### 章节结构\n\n"
        summary += "本文档包含以下主要章节：\n\n"
        summary += toc + "\n\n"
        
        # 功能概述
        if overview:
            summary += "### 功能概述\n\n"
            summary += overview + "\n"
        
        return summary

