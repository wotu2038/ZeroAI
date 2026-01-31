"""
智能分块服务

使用 LLM 自动分析文档结构，选择最佳分块策略
"""
import logging
import json
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


# 支持的分块策略
CHUNKING_STRATEGIES = {
    "level_1": {
        "name": "按一级标题分块",
        "description": "适用于结构清晰、一级标题明确的文档",
        "typical_sections": "3-10个章节"
    },
    "level_2": {
        "name": "按二级标题分块",
        "description": "适用于一级标题下内容过长的文档",
        "typical_sections": "10-30个章节"
    },
    "level_3": {
        "name": "按三级标题分块",
        "description": "适用于详细结构的技术文档",
        "typical_sections": "30-100个章节"
    },
    "fixed_token": {
        "name": "按固定Token分块",
        "description": "适用于无明确标题结构的文档",
        "typical_sections": "根据文档长度动态决定"
    },
    "no_split": {
        "name": "不分块",
        "description": "适用于短文档或需要完整上下文的文档",
        "typical_sections": "1个（整个文档）"
    }
}


class SmartChunkingService:
    """智能分块服务 - 使用LLM自动选择最佳分块策略"""
    
    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
        self.enabled = getattr(settings, 'ENABLE_SMART_CHUNKING', True)
    
    async def analyze_and_select_strategy(
        self,
        structured_content: List[Dict],
        document_name: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        分析文档结构并选择最佳分块策略
        
        Args:
            structured_content: 解析后的文档结构
            document_name: 文档名称
            metadata: 文档元数据
            
        Returns:
            {
                "strategy": "level_1",
                "reason": "文档有明确的一级标题结构...",
                "confidence": 0.85,
                "document_analysis": {...}
            }
        """
        if not self.enabled:
            logger.info("智能分块未启用，使用默认策略 level_1")
            return {
                "strategy": "level_1",
                "reason": "智能分块未启用，使用默认策略",
                "confidence": 1.0,
                "document_analysis": None
            }
        
        # 1. 分析文档结构
        analysis = self._analyze_document_structure(structured_content)
        
        # 2. 如果文档很短，直接返回 no_split
        if analysis["total_tokens"] < 2000:
            logger.info(f"文档较短 ({analysis['total_tokens']} tokens)，使用 no_split 策略")
            return {
                "strategy": "no_split",
                "reason": f"文档较短（{analysis['total_tokens']} tokens），不需要分块",
                "confidence": 1.0,
                "document_analysis": analysis
            }
        
        # 3. 如果没有标题结构，使用 fixed_token
        if analysis["heading_count"] == 0:
            logger.info("文档无标题结构，使用 fixed_token 策略")
            return {
                "strategy": "fixed_token",
                "reason": "文档没有明确的标题结构，使用固定Token分块",
                "confidence": 0.9,
                "document_analysis": analysis
            }
        
        # 4. 使用 LLM 分析并选择策略
        try:
            result = await self._llm_select_strategy(
                analysis=analysis,
                document_name=document_name,
                metadata=metadata
            )
            result["document_analysis"] = analysis
            return result
        except Exception as e:
            logger.error(f"LLM策略选择失败，使用启发式方法: {e}")
            # 回退到启发式方法
            return self._heuristic_select_strategy(analysis)
    
    def _analyze_document_structure(self, structured_content: List[Dict]) -> Dict[str, Any]:
        """分析文档结构"""
        analysis = {
            "total_tokens": 0,
            "total_paragraphs": 0,
            "heading_count": 0,
            "heading_levels": {},
            "average_section_length": 0,
            "has_images": False,
            "has_tables": False,
            "toc_preview": []
        }
        
        current_heading = None
        section_lengths = []
        current_section_length = 0
        
        for item in structured_content:
            item_type = item.get("type", "")
            content = item.get("content", "")
            
            # 估算 token 数
            tokens = self._estimate_tokens(content)
            analysis["total_tokens"] += tokens
            
            if item_type == "paragraph":
                analysis["total_paragraphs"] += 1
                current_section_length += tokens
                
            elif item_type == "heading":
                level = item.get("level", 1)
                analysis["heading_count"] += 1
                analysis["heading_levels"][level] = analysis["heading_levels"].get(level, 0) + 1
                
                # 记录目录预览（前20个标题）
                if len(analysis["toc_preview"]) < 20:
                    analysis["toc_preview"].append({
                        "level": level,
                        "title": content[:50]
                    })
                
                # 保存上一个章节的长度
                if current_heading is not None:
                    section_lengths.append(current_section_length)
                current_heading = content
                current_section_length = 0
                
            elif item_type == "image":
                analysis["has_images"] = True
                
            elif item_type == "table":
                analysis["has_tables"] = True
        
        # 保存最后一个章节
        if current_section_length > 0:
            section_lengths.append(current_section_length)
        
        # 计算平均章节长度
        if section_lengths:
            analysis["average_section_length"] = sum(section_lengths) / len(section_lengths)
        
        return analysis
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数"""
        if not text:
            return 0
        # 中文约 0.5 token/字符，英文约 0.25 token/字符
        chinese_ratio = sum(1 for c in text if '\u4e00' <= c <= '\u9fff') / max(len(text), 1)
        if chinese_ratio > 0.5:
            return int(len(text) * 0.5)
        else:
            return int(len(text) * 0.25)
    
    async def _llm_select_strategy(
        self,
        analysis: Dict[str, Any],
        document_name: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """使用 LLM 选择最佳分块策略"""
        
        # 构建 TOC 预览文本
        toc_text = ""
        for item in analysis["toc_preview"]:
            indent = "  " * (item["level"] - 1)
            toc_text += f"{indent}- {item['title']}\n"
        
        # 构建标题层级统计
        heading_stats = ""
        for level, count in sorted(analysis["heading_levels"].items()):
            heading_stats += f"  - {level}级标题: {count}个\n"
        
        prompt = f"""你是一个文档分析专家。请分析以下文档结构，选择最佳的分块策略。

## 文档信息
- 文档名称: {document_name}
- 总Token数: {analysis['total_tokens']}
- 段落数: {analysis['total_paragraphs']}
- 标题数: {analysis['heading_count']}
- 平均章节长度: {int(analysis['average_section_length'])} tokens
- 包含图片: {'是' if analysis['has_images'] else '否'}
- 包含表格: {'是' if analysis['has_tables'] else '否'}

## 标题层级统计
{heading_stats}

## 目录预览
{toc_text}

## 可选策略
1. level_1: 按一级标题分块 - 适用于结构清晰、一级标题明确的文档
2. level_2: 按二级标题分块 - 适用于一级标题下内容过长的文档
3. level_3: 按三级标题分块 - 适用于详细结构的技术文档
4. fixed_token: 按固定Token分块 - 适用于无明确标题结构的文档
5. no_split: 不分块 - 适用于短文档或需要完整上下文的文档

## 选择原则
1. 每个分块应该是一个完整的语义单元
2. 分块不宜过大（建议 < 4000 tokens）也不宜过小（建议 > 500 tokens）
3. 优先选择能保持文档逻辑结构的策略

请返回JSON格式：
{{
    "strategy": "level_1|level_2|level_3|fixed_token|no_split",
    "reason": "选择该策略的原因（简洁说明）",
    "confidence": 0.0-1.0
}}
"""
        
        # 使用默认的 provider（deepseek），如果配置了的话
        # 优先使用 deepseek，如果没有配置则尝试 qwen，最后尝试 kimi
        provider = "deepseek"
        if not (settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_BASE and settings.DEEPSEEK_MODEL):
            if settings.QWEN_API_KEY and settings.QWEN_API_BASE and settings.QWEN_MODEL:
                provider = "qwen"
            elif settings.KIMI_API_KEY and settings.KIMI_API_BASE and settings.KIMI_MODEL:
                provider = "kimi"
            else:
                raise ValueError("没有可用的 LLM provider 配置（需要配置 DeepSeek、Qwen 或 Kimi 中的至少一个）")
        
        response = await self.llm_client.chat(
            provider,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        # 解析响应
        try:
            # 尝试提取 JSON
            result = self._extract_json(response)
            
            # 验证策略有效性
            if result.get("strategy") not in CHUNKING_STRATEGIES:
                logger.warning(f"LLM返回无效策略 {result.get('strategy')}，使用 level_1")
                result["strategy"] = "level_1"
            
            logger.info(f"LLM选择分块策略: {result['strategy']}, 原因: {result.get('reason', '')}")
            return result
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}, 响应: {response[:200]}")
            raise
    
    def _extract_json(self, text: str) -> Dict:
        """从文本中提取 JSON"""
        import re
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except:
            pass
        
        # 尝试提取 JSON 代码块
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # 尝试提取花括号内容
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        raise ValueError("无法从响应中提取 JSON")
    
    def _heuristic_select_strategy(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """启发式策略选择（LLM失败时的回退）"""
        
        total_tokens = analysis["total_tokens"]
        heading_levels = analysis["heading_levels"]
        avg_section_length = analysis["average_section_length"]
        
        # 短文档
        if total_tokens < 2000:
            return {
                "strategy": "no_split",
                "reason": "文档较短，不需要分块",
                "confidence": 0.9,
                "document_analysis": analysis
            }
        
        # 无标题
        if analysis["heading_count"] == 0:
            return {
                "strategy": "fixed_token",
                "reason": "文档无标题结构",
                "confidence": 0.85,
                "document_analysis": analysis
            }
        
        # 根据标题层级分布选择
        level_1_count = heading_levels.get(1, 0)
        level_2_count = heading_levels.get(2, 0)
        level_3_count = heading_levels.get(3, 0)
        
        # 如果一级标题数量合适且平均章节长度适中
        if 3 <= level_1_count <= 15 and avg_section_length < 4000:
            return {
                "strategy": "level_1",
                "reason": f"有 {level_1_count} 个一级标题，平均章节长度 {int(avg_section_length)} tokens",
                "confidence": 0.8,
                "document_analysis": analysis
            }
        
        # 一级标题太少但二级标题合适
        if level_1_count < 3 and 5 <= level_2_count <= 30:
            return {
                "strategy": "level_2",
                "reason": f"一级标题较少({level_1_count}个)，使用二级标题分块({level_2_count}个)",
                "confidence": 0.75,
                "document_analysis": analysis
            }
        
        # 章节太大，使用更细的分块
        if avg_section_length > 4000 and level_2_count > 0:
            return {
                "strategy": "level_2",
                "reason": f"平均章节长度过大({int(avg_section_length)} tokens)，使用二级标题分块",
                "confidence": 0.7,
                "document_analysis": analysis
            }
        
        if avg_section_length > 4000 and level_3_count > 10:
            return {
                "strategy": "level_3",
                "reason": f"平均章节长度过大，使用三级标题分块",
                "confidence": 0.65,
                "document_analysis": analysis
            }
        
        # 默认使用一级标题
        return {
            "strategy": "level_1",
            "reason": "使用默认的一级标题分块策略",
            "confidence": 0.6,
            "document_analysis": analysis
        }
    
    async def evaluate_chunking_quality(
        self,
        chunks: List[Dict],
        strategy: str
    ) -> Dict[str, Any]:
        """
        评估分块质量
        
        Returns:
            {
                "score": 0-100,
                "passed": True/False,
                "issues": [...],
                "suggestions": [...]
            }
        """
        issues = []
        suggestions = []
        
        # 检查分块数量
        chunk_count = len(chunks)
        if chunk_count == 0:
            return {
                "score": 0,
                "passed": False,
                "issues": ["分块数量为0"],
                "suggestions": ["检查文档内容是否为空"]
            }
        
        # 检查分块大小
        chunk_sizes = []
        too_small = 0
        too_large = 0
        
        for chunk in chunks:
            content = chunk.get("content", "")
            size = self._estimate_tokens(content)
            chunk_sizes.append(size)
            
            if size < 100:
                too_small += 1
            elif size > 8000:
                too_large += 1
        
        if too_small > 0:
            issues.append(f"{too_small} 个分块过小 (<100 tokens)")
            suggestions.append("考虑使用更粗粒度的分块策略")
        
        if too_large > 0:
            issues.append(f"{too_large} 个分块过大 (>8000 tokens)")
            suggestions.append("考虑使用更细粒度的分块策略")
        
        # 计算分块大小的标准差
        if len(chunk_sizes) > 1:
            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            variance = sum((s - avg_size) ** 2 for s in chunk_sizes) / len(chunk_sizes)
            std_dev = variance ** 0.5
            cv = std_dev / avg_size if avg_size > 0 else 0
            
            if cv > 1.5:
                issues.append(f"分块大小差异过大 (CV={cv:.2f})")
                suggestions.append("考虑使用 fixed_token 策略以获得更均匀的分块")
        
        # 计算分数
        base_score = 100
        
        # 扣分规则
        if too_small > 0:
            base_score -= min(too_small * 5, 20)
        if too_large > 0:
            base_score -= min(too_large * 10, 30)
        if chunk_count < 2 and strategy != "no_split":
            base_score -= 15
            issues.append("分块数量过少")
        
        score = max(0, base_score)
        threshold = getattr(settings, 'CHUNKING_QUALITY_THRESHOLD', 70)
        
        return {
            "score": score,
            "passed": score >= threshold,
            "chunk_count": chunk_count,
            "avg_chunk_size": int(sum(chunk_sizes) / len(chunk_sizes)) if chunk_sizes else 0,
            "min_chunk_size": min(chunk_sizes) if chunk_sizes else 0,
            "max_chunk_size": max(chunk_sizes) if chunk_sizes else 0,
            "issues": issues,
            "suggestions": suggestions
        }

