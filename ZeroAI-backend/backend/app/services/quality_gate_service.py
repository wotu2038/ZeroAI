"""
质量门禁服务

整合三层质量评估，决定是否继续处理
"""
import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass
from app.core.config import settings

logger = logging.getLogger(__name__)


class QualityStatus(Enum):
    """质量状态"""
    PASSED = "passed"           # 通过
    RETRY = "retry"             # 需要重试
    MANUAL_REVIEW = "manual"    # 需要人工审核
    FAILED = "failed"           # 失败


@dataclass
class QualityResult:
    """质量评估结果"""
    status: QualityStatus
    overall_score: float
    chunking_score: float
    extraction_score: float
    graph_score: float
    issues: List[str]
    suggestions: List[str]
    retry_strategy: Optional[str] = None
    details: Optional[Dict] = None


class QualityGateService:
    """
    质量门禁服务
    
    整合三层质量评估：
    1. 分块质量（SmartChunkingService）
    2. 提取质量（ExtractionQualityService）
    3. 图结构质量
    """
    
    def __init__(self):
        self.threshold = getattr(settings, 'QUALITY_GATE_THRESHOLD', 70)
        self.max_retries = getattr(settings, 'QUALITY_GATE_MAX_RETRIES', 3)
        
        # 重试策略顺序
        self.retry_strategies = [
            ("level_2", "尝试使用二级标题分块"),
            ("level_3", "尝试使用三级标题分块"),
            ("fixed_token", "尝试使用固定Token分块")
        ]
    
    def evaluate(
        self,
        chunking_result: Dict[str, Any],
        extraction_result: Dict[str, Any],
        graph_result: Dict[str, Any] = None,
        current_retry: int = 0,
        current_strategy: str = None
    ) -> QualityResult:
        """
        综合评估三层质量
        
        Args:
            chunking_result: 分块质量评估结果
            extraction_result: 提取质量评估结果
            graph_result: 图结构质量评估结果（可选）
            current_retry: 当前重试次数
            current_strategy: 当前使用的分块策略
            
        Returns:
            QualityResult: 综合评估结果
        """
        # 获取各层分数
        chunking_score = chunking_result.get("score", 0)
        extraction_score = extraction_result.get("score", 0)
        graph_score = graph_result.get("score", 100) if graph_result else 100
        
        # 权重配置
        weights = {
            "chunking": 0.25,
            "extraction": 0.45,
            "graph": 0.30
        }
        
        # 如果没有图结构评估，调整权重
        if graph_result is None:
            weights = {
                "chunking": 0.35,
                "extraction": 0.65,
                "graph": 0.0
            }
        
        # 计算综合分数
        overall_score = (
            chunking_score * weights["chunking"] +
            extraction_score * weights["extraction"] +
            graph_score * weights["graph"]
        )
        
        # 收集问题和建议
        issues = []
        suggestions = []
        
        issues.extend(chunking_result.get("issues", []))
        issues.extend(extraction_result.get("issues", []))
        if graph_result:
            issues.extend(graph_result.get("issues", []))
        
        suggestions.extend(chunking_result.get("suggestions", []))
        suggestions.extend(extraction_result.get("suggestions", []))
        if graph_result:
            suggestions.extend(graph_result.get("suggestions", []))
        
        # 判断是否通过
        all_passed = (
            chunking_result.get("passed", False) and
            extraction_result.get("passed", False) and
            (graph_result is None or graph_result.get("passed", False))
        )
        
        if all_passed and overall_score >= self.threshold:
            return QualityResult(
                status=QualityStatus.PASSED,
                overall_score=overall_score,
                chunking_score=chunking_score,
                extraction_score=extraction_score,
                graph_score=graph_score,
                issues=issues,
                suggestions=suggestions,
                details={
                    "chunking": chunking_result,
                    "extraction": extraction_result,
                    "graph": graph_result
                }
            )
        
        # 未通过，判断是重试还是人工审核
        if current_retry < self.max_retries:
            # 选择下一个重试策略
            retry_strategy = self._select_retry_strategy(
                current_strategy=current_strategy,
                chunking_result=chunking_result,
                extraction_result=extraction_result
            )
            
            if retry_strategy:
                logger.info(
                    f"质量不达标 (分数: {overall_score:.1f}), "
                    f"准备重试: {retry_strategy}"
                )
                
                return QualityResult(
                    status=QualityStatus.RETRY,
                    overall_score=overall_score,
                    chunking_score=chunking_score,
                    extraction_score=extraction_score,
                    graph_score=graph_score,
                    issues=issues,
                    suggestions=suggestions,
                    retry_strategy=retry_strategy,
                    details={
                        "chunking": chunking_result,
                        "extraction": extraction_result,
                        "graph": graph_result
                    }
                )
        
        # 重试次数用尽或无可用策略，需要人工审核
        logger.warning(
            f"质量不达标且无法重试 (分数: {overall_score:.1f}, 重试次数: {current_retry}), "
            f"需要人工审核"
        )
        
        return QualityResult(
            status=QualityStatus.MANUAL_REVIEW,
            overall_score=overall_score,
            chunking_score=chunking_score,
            extraction_score=extraction_score,
            graph_score=graph_score,
            issues=issues,
            suggestions=suggestions,
            details={
                "chunking": chunking_result,
                "extraction": extraction_result,
                "graph": graph_result
            }
        )
    
    def _select_retry_strategy(
        self,
        current_strategy: str,
        chunking_result: Dict[str, Any],
        extraction_result: Dict[str, Any]
    ) -> Optional[str]:
        """
        选择重试策略
        
        根据当前问题选择最合适的下一个策略
        """
        # 已尝试过的策略
        tried_strategies = set()
        if current_strategy:
            tried_strategies.add(current_strategy)
        
        # 分析问题类型
        chunking_issues = chunking_result.get("issues", [])
        
        # 如果分块过大，使用更细粒度的策略
        if any("过大" in issue for issue in chunking_issues):
            for strategy, _ in self.retry_strategies:
                if strategy not in tried_strategies:
                    return strategy
        
        # 如果分块过小，使用更粗粒度的策略
        if any("过小" in issue for issue in chunking_issues):
            coarse_strategies = ["level_1", "no_split"]
            for strategy in coarse_strategies:
                if strategy not in tried_strategies and strategy != current_strategy:
                    return strategy
        
        # 默认按顺序尝试
        for strategy, _ in self.retry_strategies:
            if strategy not in tried_strategies:
                return strategy
        
        return None
    
    def create_review_record(
        self,
        document_id: int,
        quality_result: QualityResult,
        document_name: str
    ) -> Dict[str, Any]:
        """
        创建待审核记录
        
        当质量不达标且需要人工审核时调用
        """
        return {
            "document_id": document_id,
            "document_name": document_name,
            "status": "pending_review",
            "overall_score": quality_result.overall_score,
            "chunking_score": quality_result.chunking_score,
            "extraction_score": quality_result.extraction_score,
            "graph_score": quality_result.graph_score,
            "issues": quality_result.issues,
            "suggestions": quality_result.suggestions,
            "details": quality_result.details,
            "review_actions": [
                {
                    "action": "approve",
                    "label": "通过并继续处理",
                    "description": "忽略质量问题，继续创建知识图谱"
                },
                {
                    "action": "retry_with_strategy",
                    "label": "更换策略重试",
                    "description": "使用不同的分块策略重新处理"
                },
                {
                    "action": "reject",
                    "label": "拒绝处理",
                    "description": "放弃此文档的知识图谱创建"
                }
            ]
        }


class GraphQualityService:
    """
    图结构质量评估服务
    
    评估生成的知识图谱的结构质量
    """
    
    def __init__(self):
        self.threshold = getattr(settings, 'GRAPH_QUALITY_THRESHOLD', 70)
    
    def evaluate(
        self,
        entities: List[Dict],
        relationships: List[Dict],
        communities: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        评估图结构质量
        
        五个维度：
        1. 连通性 (Connectivity)
        2. 密度 (Density)
        3. 孤立节点率 (Isolation)
        4. 聚类系数 (Clustering)
        5. 社区覆盖 (Community Coverage)
        """
        issues = []
        suggestions = []
        
        entity_count = len(entities)
        rel_count = len(relationships)
        community_count = len(communities) if communities else 0
        
        # 基础检查
        if entity_count == 0:
            return {
                "score": 0,
                "passed": False,
                "issues": ["图中没有实体"],
                "suggestions": ["检查实体提取是否正常"]
            }
        
        # 1. 连通性评估
        connectivity_score = self._evaluate_connectivity(entities, relationships)
        
        # 2. 密度评估
        density_score = self._evaluate_density(entity_count, rel_count)
        
        # 3. 孤立节点评估
        isolation_score = self._evaluate_isolation(entities, relationships)
        
        # 4. 社区覆盖评估
        community_score = self._evaluate_community_coverage(
            entities, communities
        ) if communities else 100
        
        # 综合评分
        weights = {
            "connectivity": 0.30,
            "density": 0.25,
            "isolation": 0.25,
            "community": 0.20
        }
        
        if not communities:
            weights = {
                "connectivity": 0.40,
                "density": 0.30,
                "isolation": 0.30,
                "community": 0.0
            }
        
        overall_score = (
            connectivity_score * weights["connectivity"] +
            density_score * weights["density"] +
            isolation_score * weights["isolation"] +
            community_score * weights["community"]
        )
        
        # 收集问题
        if connectivity_score < 60:
            issues.append("图的连通性较差")
            suggestions.append("检查实体之间的关系是否被正确提取")
        
        if density_score < 50:
            issues.append("图的密度过低")
            suggestions.append("可能需要更多的关系提取")
        
        if isolation_score < 60:
            issues.append("存在较多孤立节点")
            suggestions.append("检查是否有实体未被关联")
        
        if communities and community_score < 50:
            issues.append("社区覆盖不足")
            suggestions.append("考虑重新构建社区")
        
        return {
            "score": round(overall_score, 1),
            "passed": overall_score >= self.threshold,
            "connectivity_score": connectivity_score,
            "density_score": density_score,
            "isolation_score": isolation_score,
            "community_score": community_score,
            "entity_count": entity_count,
            "relationship_count": rel_count,
            "community_count": community_count,
            "issues": issues,
            "suggestions": suggestions
        }
    
    def _evaluate_connectivity(
        self,
        entities: List[Dict],
        relationships: List[Dict]
    ) -> float:
        """评估连通性"""
        if len(entities) <= 1:
            return 100
        
        # 构建邻接表
        adj = {}
        entity_ids = set()
        
        for e in entities:
            eid = e.get("uuid") or e.get("id") or e.get("name")
            if eid:
                entity_ids.add(eid)
                adj[eid] = set()
        
        for r in relationships:
            source = r.get("source_uuid") or r.get("source") or r.get("source_name")
            target = r.get("target_uuid") or r.get("target") or r.get("target_name")
            if source in adj:
                adj[source].add(target)
            if target in adj:
                adj[target].add(source)
        
        # 使用 BFS 计算最大连通分量
        visited = set()
        max_component_size = 0
        
        for start in entity_ids:
            if start in visited:
                continue
            
            component_size = 0
            queue = [start]
            
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component_size += 1
                
                for neighbor in adj.get(node, []):
                    if neighbor not in visited and neighbor in entity_ids:
                        queue.append(neighbor)
            
            max_component_size = max(max_component_size, component_size)
        
        # 最大连通分量占比
        connectivity = max_component_size / len(entity_ids) if entity_ids else 0
        return round(connectivity * 100, 1)
    
    def _evaluate_density(self, entity_count: int, rel_count: int) -> float:
        """评估图密度"""
        if entity_count <= 1:
            return 100
        
        # 理论最大边数
        max_edges = entity_count * (entity_count - 1) / 2
        
        # 实际密度
        density = rel_count / max_edges if max_edges > 0 else 0
        
        # 对于知识图谱，0.1-0.3 的密度是比较健康的
        # 太稀疏说明关系太少，太密集可能是过度连接
        if density < 0.05:
            score = density / 0.05 * 60
        elif density < 0.3:
            score = 60 + (density - 0.05) / 0.25 * 40
        else:
            score = 100 - (density - 0.3) * 50
        
        return max(0, min(100, round(score, 1)))
    
    def _evaluate_isolation(
        self,
        entities: List[Dict],
        relationships: List[Dict]
    ) -> float:
        """评估孤立节点率"""
        if not entities:
            return 100
        
        # 收集有关系的节点
        connected_nodes = set()
        for r in relationships:
            source = r.get("source_uuid") or r.get("source") or r.get("source_name")
            target = r.get("target_uuid") or r.get("target") or r.get("target_name")
            if source:
                connected_nodes.add(source)
            if target:
                connected_nodes.add(target)
        
        # 计算孤立节点数
        entity_ids = set()
        for e in entities:
            eid = e.get("uuid") or e.get("id") or e.get("name")
            if eid:
                entity_ids.add(eid)
        
        isolated = entity_ids - connected_nodes
        isolation_rate = len(isolated) / len(entity_ids) if entity_ids else 0
        
        # 孤立率越低越好
        score = (1 - isolation_rate) * 100
        return round(score, 1)
    
    def _evaluate_community_coverage(
        self,
        entities: List[Dict],
        communities: List[Dict]
    ) -> float:
        """评估社区覆盖率"""
        if not communities:
            return 100  # 如果没有社区，不扣分
        
        # 收集社区中的实体
        covered_entities = set()
        for c in communities:
            members = c.get("members", []) or c.get("entity_ids", [])
            for m in members:
                if isinstance(m, dict):
                    covered_entities.add(m.get("uuid") or m.get("id"))
                else:
                    covered_entities.add(m)
        
        # 计算覆盖率
        entity_ids = set()
        for e in entities:
            eid = e.get("uuid") or e.get("id")
            if eid:
                entity_ids.add(eid)
        
        if not entity_ids:
            return 100
        
        coverage = len(covered_entities & entity_ids) / len(entity_ids)
        return round(coverage * 100, 1)

