"""
文档生成Agent实现
"""
import logging
from typing import Dict, Any, Optional, List
from .state import DocumentGenerationState, GenerationStage

logger = logging.getLogger(__name__)


class ContentRetriever:
    """内容检索Agent - 检索Episode、Entity、Edge，必要时检索Community"""
    
    @staticmethod
    async def retrieve(state: DocumentGenerationState) -> DocumentGenerationState:
        """
        根据用户问题检索相关内容
        
        检索策略（方案B）：
        1. 优先检索Episode、Entity、Edge（使用Graphiti语义搜索）
        2. 如果结果不足或需要高层次概念，补充检索Community
        """
        user_query = state["user_query"]
        retrieval_limit = state.get("retrieval_limit", 20)
        group_id = state.get("group_id")
        group_ids = state.get("group_ids")
        all_documents = state.get("all_documents", False)
        
        logger.info(f"开始检索相关内容: query='{user_query}', limit={retrieval_limit}")
        
        # 使用 HybridRetriever 进行混合检索
        from app.services.hybrid_retriever import HybridRetriever, HybridRetrievalConfig, RetrievalScheme
        from app.core.graphiti_client import get_graphiti_instance
        
        all_results = []
        
        try:
            # 初始化 HybridRetriever
            graphiti = get_graphiti_instance("local")
            retriever = HybridRetriever(
                embedder=graphiti.embedder,
                reranker=graphiti.cross_encoder
            )
            
            # 确定检索范围
            target_group_ids = None
            if group_id:
                target_group_ids = [group_id]
            elif group_ids:
                target_group_ids = group_ids
            # all_documents 时 target_group_ids 为 None，表示检索全部文档
            
            # 配置检索参数
            config = HybridRetrievalConfig(
                scheme=RetrievalScheme.DEFAULT,
                final_top_k=retrieval_limit
            )
            
            # 执行混合检索
            retrieval_results = await retriever.retrieve(
                query=user_query,
                group_ids=target_group_ids,
                config=config
            )
            
            # 将 HybridRetriever 的 RetrievalResult 转换为 Agent 需要的格式
            for result in retrieval_results:
                # RetrievalResult 包含: uuid, name, content, score, source_type, group_id, metadata
                agent_result = {
                    "type": result.source_type,  # episode, entity, edge, community
                    "name": result.name,
                    "content": result.content,
                    "score": result.score,
                    "source": result.group_id or result.uuid,  # 使用 group_id 或 uuid 作为 source
                    "raw_data": {
                        "uuid": result.uuid,
                        "source_type": result.source_type,
                        "group_id": result.group_id,
                        "metadata": result.metadata or {}
                    }
                }
                all_results.append(agent_result)
            
            logger.info(f"HybridRetriever检索完成，返回 {len(all_results)} 个结果")
            
        except Exception as e:
            logger.error(f"HybridRetriever检索失败: {e}", exc_info=True)
            # 如果检索失败，返回空结果，不影响后续流程
        
        # 注意：HybridRetriever 已经包含了 Episode、Entity、Edge、Community 的检索
        # 所以不需要额外的检索逻辑
        
        # 4. 去重和排序
        seen = set()
        unique_results = []
        for result in all_results:
            key = (result["type"], result["name"], result["source"])
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        # 按相关性分数排序
        unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # 限制数量
        retrieved_content = unique_results[:retrieval_limit]
        
        # 统计各类型数量
        episode_count = sum(1 for r in retrieved_content if r["type"] == "episode")
        entity_count = sum(1 for r in retrieved_content if r["type"] == "entity")
        edge_count = sum(1 for r in retrieved_content if r["type"] == "edge")
        community_count = sum(1 for r in retrieved_content if r["type"] == "community")
        
        state["retrieved_content"] = retrieved_content
        state["current_stage"] = GenerationStage.RETRIEVING
        state["progress"] = 10
        state["current_step"] = f"已检索到 {len(retrieved_content)} 条相关内容（Episode: {episode_count}, Entity: {entity_count}, Edge: {edge_count}, Community: {community_count}）"
        
        logger.info(f"检索完成: 找到 {len(retrieved_content)} 条相关内容")
        
        return state


class DocumentGenerator:
    """文档生成Agent - 整合检索结果和相似需求生成文档"""
    
    @staticmethod
    async def generate(state: DocumentGenerationState) -> DocumentGenerationState:
        """生成初始文档"""
        from .prompts import build_generation_prompt
        from app.core.llm_client import get_llm_client
        
        # 构建生成Prompt（整合检索结果）
        prompt = build_generation_prompt(
            user_query=state["user_query"],
            retrieved_content=state["retrieved_content"],
            new_requirement=state.get("new_requirement"),
            similar_requirements=state["similar_requirements"]
        )
        
        # 调用LLM生成
        llm_client = get_llm_client("local")
        use_thinking = state.get("use_thinking", False)
        document = await llm_client.generate(
            provider="local",
            prompt=prompt,
            temperature=0.7,
            max_tokens=8000,
            use_thinking=use_thinking
        )
        
        state["current_document"] = document
        state["current_stage"] = GenerationStage.GENERATING
        state["progress"] = 40  # 生成阶段占40%（10%检索 + 30%生成）
        state["current_step"] = "文档生成完成"
        
        return state


class DocumentReviewer:
    """文档评审Agent - 评审文档质量"""
    
    @staticmethod
    async def review(state: DocumentGenerationState) -> DocumentGenerationState:
        """评审文档质量"""
        from .prompts import build_review_prompt
        from app.core.llm_client import get_llm_client
        import json
        import re
        
        # 构建评审Prompt
        prompt = build_review_prompt(state["current_document"])
        
        # 调用LLM评审
        llm_client = get_llm_client("local")
        use_thinking = state.get("use_thinking", False)
        review_result = await llm_client.generate(
            provider="local",
            prompt=prompt,
            temperature=0.3,  # 评审需要更低的温度
            max_tokens=2000,
            use_thinking=use_thinking
        )
        
        # 解析评审结果（JSON格式）
        review_report = DocumentReviewer._parse_review_result(review_result)
        
        state["review_report"] = review_report
        state["quality_score"] = review_report.get("overall_score", 0.0)
        state["current_stage"] = GenerationStage.REVIEWING
        state["progress"] = 50 + (state["iteration_count"] * 10)  # 评审阶段进度
        state["current_step"] = f"文档评审完成，质量评分: {state['quality_score']:.1f}/100"
        
        return state
    
    @staticmethod
    def _parse_review_result(review_text: str) -> Dict[str, Any]:
        """解析评审结果JSON"""
        import json
        import re
        
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', review_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(review_text)
        except json.JSONDecodeError:
            logger.warning(f"评审结果解析失败，使用默认值: {review_text[:100]}")
            # 返回默认评审报告
            return {
                "overall_score": 70.0,
                "completeness_score": 70.0,
                "accuracy_score": 70.0,
                "consistency_score": 70.0,
                "readability_score": 70.0,
                "issues": ["评审结果解析失败"],
                "suggestions": []
            }


class DocumentOptimizer:
    """文档优化Agent - 根据评审结果优化文档"""
    
    @staticmethod
    async def optimize(state: DocumentGenerationState) -> DocumentGenerationState:
        """根据评审结果优化文档"""
        from .prompts import build_optimization_prompt
        from app.core.llm_client import get_llm_client
        
        # 构建优化Prompt
        prompt = build_optimization_prompt(
            state["current_document"],
            state["review_report"]
        )
        
        # 调用LLM优化
        llm_client = get_llm_client("local")
        use_thinking = state.get("use_thinking", False)
        optimized_document = await llm_client.generate(
            provider="local",
            prompt=prompt,
            temperature=0.5,
            max_tokens=8000,
            use_thinking=use_thinking
        )
        
        state["current_document"] = optimized_document
        state["iteration_count"] += 1
        state["current_stage"] = GenerationStage.OPTIMIZING
        state["progress"] = 60 + (state["iteration_count"] * 5)  # 优化阶段进度
        state["current_step"] = f"文档优化完成（第{state['iteration_count']}次迭代）"
        
        return state


class Orchestrator:
    """协调Agent - 决定是否继续迭代"""
    
    @staticmethod
    async def decide(state: DocumentGenerationState) -> DocumentGenerationState:
        """决定是否继续迭代"""
        quality_score = state["quality_score"]
        iteration_count = state["iteration_count"]
        max_iterations = state["max_iterations"]
        quality_threshold = state["quality_threshold"]
        
        # 决策逻辑
        should_continue = (
            quality_score < quality_threshold and
            iteration_count < max_iterations
        )
        
        state["should_continue"] = should_continue
        state["is_final"] = not should_continue
        
        if not should_continue:
            state["current_stage"] = GenerationStage.COMPLETED
            state["progress"] = 100
            state["current_step"] = f"文档生成完成，最终质量评分: {quality_score:.1f}/100"
        else:
            state["current_step"] = f"需要继续优化（当前评分: {quality_score:.1f} < 阈值: {quality_threshold}）"
        
        return state
    
    @staticmethod
    def should_continue(state: DocumentGenerationState) -> str:
        """路由函数"""
        return "continue" if state["should_continue"] else "finish"

