"""
LLM 提取质量评估服务

评估 Graphiti 从文档中提取的实体和关系的质量
"""
import logging
import json
import random
from typing import Dict, List, Any, Optional
from app.core.config import settings
from app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ExtractionQualityService:
    """LLM提取质量评估服务"""
    
    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
        self.sample_size = getattr(settings, 'EXTRACTION_QUALITY_SAMPLE_SIZE', 10)
    
    async def evaluate_extraction_quality(
        self,
        entities: List[Dict],
        relationships: List[Dict],
        source_content: str,
        document_name: str,
        provider: str = "local"
    ) -> Dict[str, Any]:
        """
        评估LLM提取的实体和关系质量
        
        三个核心指标：
        1. 覆盖度 (Coverage): 是否提取了源文本中的主要信息
        2. 一致性 (Consistency): 提取的信息是否与源文本一致
        3. 完整性 (Completeness): 实体和关系信息是否完整
        
        Returns:
            {
                "score": 0-100,
                "passed": True/False,
                "coverage_score": 0-100,
                "consistency_score": 0-100,
                "completeness_score": 0-100,
                "details": {...},
                "issues": [...],
                "suggestions": [...]
            }
        """
        logger.info(f"开始评估提取质量: 文档={document_name}, 实体数={len(entities)}, 关系数={len(relationships)}")
        
        # 1. 覆盖度评估
        coverage_result = await self._evaluate_coverage(
            entities=entities,
            relationships=relationships,
            source_content=source_content,
            provider=provider
        )
        
        # 2. 一致性评估（采样验证）
        consistency_result = await self._evaluate_consistency(
            entities=entities,
            source_content=source_content,
            provider=provider
        )
        
        # 3. 完整性评估
        completeness_result = self._evaluate_completeness(
            entities=entities,
            relationships=relationships
        )
        
        # 综合评分
        weights = {
            "coverage": 0.35,
            "consistency": 0.35,
            "completeness": 0.30
        }
        
        total_score = (
            coverage_result["score"] * weights["coverage"] +
            consistency_result["score"] * weights["consistency"] +
            completeness_result["score"] * weights["completeness"]
        )
        
        # 收集所有问题和建议
        all_issues = (
            coverage_result.get("issues", []) +
            consistency_result.get("issues", []) +
            completeness_result.get("issues", [])
        )
        
        all_suggestions = (
            coverage_result.get("suggestions", []) +
            consistency_result.get("suggestions", []) +
            completeness_result.get("suggestions", [])
        )
        
        threshold = getattr(settings, 'EXTRACTION_QUALITY_THRESHOLD', 70)
        
        result = {
            "score": round(total_score, 1),
            "passed": total_score >= threshold,
            "coverage_score": coverage_result["score"],
            "consistency_score": consistency_result["score"],
            "completeness_score": completeness_result["score"],
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "details": {
                "coverage": coverage_result,
                "consistency": consistency_result,
                "completeness": completeness_result
            },
            "issues": all_issues,
            "suggestions": all_suggestions
        }
        
        logger.info(f"提取质量评估完成: 分数={result['score']}, 通过={result['passed']}")
        return result
    
    async def _evaluate_coverage(
        self,
        entities: List[Dict],
        relationships: List[Dict],
        source_content: str,
        provider: str = "local"
    ) -> Dict[str, Any]:
        """
        评估覆盖度
        
        使用 LLM 判断提取的实体是否覆盖了源文本中的主要信息
        """
        # 提取实体名称列表
        entity_names = [e.get("name", "") for e in entities if e.get("name")]
        
        # 构建关系描述
        relationship_descriptions = []
        for r in relationships[:20]:  # 限制数量
            source = r.get("source_name", r.get("source", ""))
            target = r.get("target_name", r.get("target", ""))
            rel_type = r.get("type", r.get("name", ""))
            if source and target and rel_type:
                relationship_descriptions.append(f"{source} --[{rel_type}]--> {target}")
        
        # 截取源内容（避免太长）
        content_preview = source_content[:4000] if len(source_content) > 4000 else source_content
        
        prompt = f"""你是一个信息提取质量评估专家。请评估以下提取结果是否充分覆盖了源文本中的主要信息。

## 源文本（部分）
{content_preview}

## 已提取的实体（{len(entity_names)}个）
{', '.join(entity_names[:30])}
{f'... 还有 {len(entity_names) - 30} 个实体' if len(entity_names) > 30 else ''}

## 已提取的关系（{len(relationships)}个）
{chr(10).join(relationship_descriptions) if relationship_descriptions else '无关系'}

## 评估任务
请评估：
1. 是否提取了源文本中的主要实体（人物、组织、概念、功能等）
2. 是否提取了实体之间的主要关系
3. 是否有重要信息被遗漏

请返回JSON格式：
{{
    "score": 0-100,
    "main_entities_covered": true/false,
    "main_relationships_covered": true/false,
    "missing_entities": ["可能遗漏的重要实体1", "实体2"],
    "missing_relationships": ["可能遗漏的重要关系1"],
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1"]
}}
"""
        
        try:
            response = await self.llm_client.chat(
                provider=provider,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            result = self._extract_json(response)
            return {
                "score": result.get("score", 70),
                "main_entities_covered": result.get("main_entities_covered", True),
                "main_relationships_covered": result.get("main_relationships_covered", True),
                "missing_entities": result.get("missing_entities", []),
                "missing_relationships": result.get("missing_relationships", []),
                "issues": result.get("issues", []),
                "suggestions": result.get("suggestions", [])
            }
            
        except Exception as e:
            logger.error(f"覆盖度评估失败: {e}")
            # 回退到简单评估
            return self._fallback_coverage_evaluation(entities, relationships)
    
    async def _evaluate_consistency(
        self,
        entities: List[Dict],
        source_content: str,
        provider: str = "local"
    ) -> Dict[str, Any]:
        """
        评估一致性
        
        采样验证实体是否真实存在于源文本中
        """
        if not entities:
            return {
                "score": 0,
                "verified_count": 0,
                "sample_size": 0,
                "issues": ["没有提取到任何实体"],
                "suggestions": ["检查文档内容是否有效"]
            }
        
        # 随机采样
        sample_size = min(self.sample_size, len(entities))
        sampled_entities = random.sample(entities, sample_size)
        
        # 使用 LLM 验证
        verified_count = 0
        failed_entities = []
        
        for entity in sampled_entities:
            entity_name = entity.get("name", "")
            if not entity_name:
                continue
                
            is_valid = await self._verify_entity_exists(
                entity_name=entity_name,
                source_content=source_content,
                provider=provider
            )
            
            if is_valid:
                verified_count += 1
            else:
                failed_entities.append(entity_name)
        
        # 计算一致性分数
        consistency_rate = verified_count / sample_size if sample_size > 0 else 0
        score = round(consistency_rate * 100)
        
        issues = []
        suggestions = []
        
        if failed_entities:
            issues.append(f"以下实体可能不存在于源文本中: {', '.join(failed_entities[:5])}")
            suggestions.append("检查LLM提取的准确性，考虑调整提取参数")
        
        return {
            "score": score,
            "verified_count": verified_count,
            "sample_size": sample_size,
            "failed_entities": failed_entities,
            "issues": issues,
            "suggestions": suggestions
        }
    
    async def _verify_entity_exists(
        self,
        entity_name: str,
        source_content: str,
        provider: str = "local"
    ) -> bool:
        """验证单个实体是否真实存在于源文本中"""
        
        # 首先尝试简单的字符串匹配
        if entity_name.lower() in source_content.lower():
            return True
        
        # 使用 LLM 进行语义验证
        content_preview = source_content[:3000]
        
        prompt = f"""请验证以下实体是否真实存在于源文本中。

## 源文本
{content_preview}

## 待验证实体
{entity_name}

请判断这个实体（或其同义词、缩写）是否在源文本中被提及或描述。

只返回 true 或 false："""
        
        try:
            response = await self.llm_client.chat(
                provider=provider,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            return "true" in response.lower()
            
        except Exception as e:
            logger.warning(f"实体验证失败: {entity_name}, error: {e}")
            # 验证失败时保守地返回 True
            return True
    
    def _evaluate_completeness(
        self,
        entities: List[Dict],
        relationships: List[Dict]
    ) -> Dict[str, Any]:
        """
        评估完整性
        
        检查实体和关系信息是否完整
        """
        issues = []
        suggestions = []
        
        # 检查实体完整性
        entities_without_name = sum(1 for e in entities if not e.get("name"))
        entities_without_type = sum(1 for e in entities if not e.get("type") and not e.get("labels"))
        entities_without_summary = sum(1 for e in entities if not e.get("summary"))
        
        entity_score = 100
        if entities_without_name > 0:
            entity_score -= 20
            issues.append(f"{entities_without_name} 个实体缺少名称")
        if entities_without_type > len(entities) * 0.3:
            entity_score -= 15
            issues.append(f"{entities_without_type} 个实体缺少类型")
        if entities_without_summary > len(entities) * 0.5:
            entity_score -= 10
            issues.append(f"{entities_without_summary} 个实体缺少摘要")
        
        # 检查关系完整性
        rels_without_type = sum(1 for r in relationships if not r.get("type") and not r.get("name"))
        rels_without_source = sum(1 for r in relationships if not r.get("source") and not r.get("source_name"))
        rels_without_target = sum(1 for r in relationships if not r.get("target") and not r.get("target_name"))
        
        rel_score = 100
        if rels_without_type > 0:
            rel_score -= 20
            issues.append(f"{rels_without_type} 个关系缺少类型")
        if rels_without_source > 0 or rels_without_target > 0:
            rel_score -= 30
            issues.append("存在关系缺少源或目标节点")
        
        # 检查实体-关系比例
        if len(entities) > 0 and len(relationships) == 0:
            rel_score -= 20
            issues.append("有实体但没有关系")
            suggestions.append("检查关系提取是否正常工作")
        elif len(entities) > 10 and len(relationships) < len(entities) * 0.3:
            rel_score -= 10
            issues.append("关系数量相对实体数量较少")
        
        # 综合评分
        score = (entity_score * 0.5 + rel_score * 0.5)
        
        return {
            "score": max(0, round(score)),
            "entity_completeness": entity_score,
            "relationship_completeness": rel_score,
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "issues": issues,
            "suggestions": suggestions
        }
    
    def _fallback_coverage_evaluation(
        self,
        entities: List[Dict],
        relationships: List[Dict]
    ) -> Dict[str, Any]:
        """覆盖度评估的回退方案"""
        
        # 基于数量的简单评估
        entity_count = len(entities)
        rel_count = len(relationships)
        
        issues = []
        suggestions = []
        
        if entity_count == 0:
            score = 0
            issues.append("没有提取到任何实体")
        elif entity_count < 3:
            score = 40
            issues.append("提取的实体数量较少")
            suggestions.append("检查文档内容或提取配置")
        elif entity_count < 10:
            score = 70
        else:
            score = 85
        
        return {
            "score": score,
            "main_entities_covered": entity_count >= 3,
            "main_relationships_covered": rel_count >= 1,
            "missing_entities": [],
            "missing_relationships": [],
            "issues": issues,
            "suggestions": suggestions
        }
    
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

