"""
对话模式增强服务

实现增强版对话模式功能：
1. 文档逐个总结
2. 问题-文档关系分析
3. 知识覆盖度分析
4. 知识缺口提示
5. 推荐追问
"""
import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from app.core.config import settings
from app.core.llm_client import LLMClient
from app.services.hybrid_retriever import HybridRetriever, RetrievalResult, RetrievalScheme

logger = logging.getLogger(__name__)


@dataclass
class DocumentSummary:
    """文档总结"""
    document_id: str
    document_name: str
    upload_id: int
    knowledge_base_name: str
    relationship: str  # 核心来源 / 补充来源 / 参考来源
    key_content: str
    suggestion: str
    relevance_score: float
    preview_url: str
    has_smart_summary: bool = False


@dataclass
class ConversationResponse:
    """对话响应"""
    # 直接回答
    answer: str
    
    # 文档总结列表
    document_summaries: List[DocumentSummary] = field(default_factory=list)
    
    # 知识覆盖度分析
    coverage_analysis: Optional[Dict] = None
    
    # 知识缺口提示
    knowledge_gaps: List[str] = field(default_factory=list)
    
    # 推荐追问
    follow_up_questions: List[str] = field(default_factory=list)
    
    # 引用来源（文末）
    references: List[Dict] = field(default_factory=list)
    
    # 原始检索结果（用于前端显示）
    retrieval_results: List[RetrievalResult] = field(default_factory=list)
    
    # 元数据
    retrieval_count: int = 0
    scheme_used: str = "default"


class ConversationService:
    """
    对话模式增强服务
    
    提供完整的对话体验：
    - 直接回答用户问题
    - 展示相关文档总结
    - 分析知识覆盖度
    - 提示知识缺口
    - 推荐追问
    """
    
    def __init__(self, llm_client: LLMClient = None, provider: str = "deepseek"):
        self.llm_client = llm_client or LLMClient()
        # 从 Graphiti 实例获取 embedder 和 reranker（Cross-encoder）
        from app.core.graphiti_client import get_graphiti_instance
        graphiti = get_graphiti_instance(provider)
        self.retriever = HybridRetriever(
            embedder=graphiti.embedder,
            reranker=graphiti.cross_encoder
        )
        # 初始化 Mem0 客户端（用于对话记忆管理）
        try:
            from app.core.mem0_client import get_mem0_client
            self.memory = get_mem0_client(provider=provider)
            logger.info(f"Mem0 客户端已初始化 (provider={provider})")
        except Exception as e:
            logger.warning(f"Mem0 客户端初始化失败，将不使用记忆功能: {e}")
            self.memory = None
    
    async def chat(
        self,
        query: str,
        group_ids: Optional[List[str]] = None,
        scheme: str = "default",
        history: List[Dict] = None,
        top_k: int = 10,
        provider: str = "deepseek",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ConversationResponse:
        """
        执行增强版对话
        
        Args:
            query: 用户问题
            group_ids: 知识库范围（None 表示全部）
            scheme: 检索方案 (default, enhanced, smart, fast)
            history: 对话历史
            top_k: 检索数量
            
        Returns:
            完整的对话响应
        """
        logger.info(f"开始对话: query='{query[:50]}...', scheme={scheme}, user_id={user_id}, session_id={session_id}")
        
        # 1. 检索 Mem0 记忆（如果启用）
        memories = []
        if self.memory and user_id:
            try:
                memories = await self._retrieve_memories(
                    query=query,
                    user_id=user_id,
                    session_id=session_id
                )
                logger.info(f"检索到 {len(memories)} 条相关记忆")
            except Exception as e:
                logger.warning(f"Mem0 记忆检索失败: {e}")
        
        # 2. 检索知识库相关内容
        retrieval_results = await self._retrieve(
            query=query,
            group_ids=group_ids,
            scheme=scheme,
            top_k=top_k
        )
        
        # 3. 生成文档总结
        document_summaries = await self._summarize_documents(
            query=query,
            results=retrieval_results,
            provider=provider
        )
        
        # 4. 分析知识覆盖度
        coverage_analysis = await self._analyze_coverage(
            query=query,
            results=retrieval_results
        )
        
        # 5. 生成直接回答（合并 Mem0 记忆和知识库检索结果）
        answer, references = await self._generate_answer(
            query=query,
            results=retrieval_results,
            memories=memories,
            history=history,
            provider=provider
        )
        
        # 6. 检测知识缺口
        knowledge_gaps = await self._detect_knowledge_gaps(
            query=query,
            answer=answer,
            results=retrieval_results,
            provider=provider
        )
        
        # 7. 生成推荐追问
        follow_up_questions = await self._generate_follow_ups(
            query=query,
            answer=answer,
            results=retrieval_results,
            provider=provider
        )
        
        # 8. 保存对话到 Mem0（如果启用）
        if self.memory and user_id:
            try:
                await self._save_memory(
                    query=query,
                    answer=answer,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Mem0 记忆保存失败: {e}")
        
        return ConversationResponse(
            answer=answer,
            document_summaries=document_summaries,
            coverage_analysis=coverage_analysis,
            knowledge_gaps=knowledge_gaps,
            follow_up_questions=follow_up_questions,
            references=references,
            retrieval_results=retrieval_results,  # 保存原始检索结果
            retrieval_count=len(retrieval_results),
            scheme_used=scheme
        )
    
    async def _retrieve(
        self,
        query: str,
        group_ids: Optional[List[str]],
        scheme: str,
        top_k: int
    ) -> List[RetrievalResult]:
        """执行检索"""
        from app.services.hybrid_retriever import HybridRetrievalConfig, RetrievalScheme
        
        config = HybridRetrievalConfig(
            scheme=RetrievalScheme(scheme),
            final_top_k=top_k,
            enable_rerank=(scheme != "fast")
        )
        
        return await self.retriever.retrieve(
            query=query,
            group_ids=group_ids,
            config=config
        )
    
    async def _summarize_documents(
        self,
        query: str,
        results: List[RetrievalResult],
        provider: str = "local"
    ) -> List[DocumentSummary]:
        """
        对检索到的文档进行逐个总结
        
        优化：复用构建知识图谱时生成的智能摘要
        """
        # 按文档分组
        doc_groups = self._group_by_document(results)
        
        summaries = []
        for group_id, doc_results in doc_groups.items():
            summary = await self._analyze_document_relevance(
                query=query,
                group_id=group_id,
                results=doc_results,
                provider=provider
            )
            if summary:
                summaries.append(summary)
        
        # 按相关度排序
        summaries.sort(key=lambda x: x.relevance_score, reverse=True)
        return summaries
    
    def _group_by_document(self, results: List[RetrievalResult]) -> Dict[str, List[RetrievalResult]]:
        """按文档（group_id）分组"""
        groups = {}
        for r in results:
            gid = r.group_id or "unknown"
            if gid not in groups:
                groups[gid] = []
            groups[gid].append(r)
        return groups
    
    async def _analyze_document_relevance(
        self,
        query: str,
        group_id: str,
        results: List[RetrievalResult],
        provider: str = "local"
    ) -> Optional[DocumentSummary]:
        """分析文档与问题的相关性"""
        # 获取文档信息
        doc_info = await self._get_document_info(group_id)
        if not doc_info:
            return None
        
        # 尝试获取已有的智能摘要
        existing_summary = await self._get_existing_summary(group_id)
        
        if existing_summary:
            # 有智能摘要：只需分析与问题的关系（轻量级）
            prompt = f"""请分析文档摘要与用户问题的相关性。

用户问题：{query}

文档：《{doc_info['document_name']}》

文档摘要（已有）：
{existing_summary[:2000]}

请输出JSON格式：
{{
    "relationship": "核心来源|补充来源|参考来源",
    "key_content": "与问题最相关的内容摘要（50字以内）",
    "suggestion": "给用户的建议（如：重点参考第X章）",
    "relevance_score": 0-100
}}"""
        else:
            # 无智能摘要：使用检索结果生成
            context = "\n".join([r.content[:500] for r in results[:5]])
            prompt = f"""请根据用户问题和文档内容，生成简洁的文档总结。

用户问题：{query}

文档内容（来自《{doc_info['document_name']}》）：
{context[:3000]}

请输出JSON格式：
{{
    "relationship": "核心来源|补充来源|参考来源",
    "key_content": "与问题相关的关键内容摘要（50字以内）",
    "suggestion": "给用户的建议",
    "relevance_score": 0-100
}}"""
        
        try:
            response = await self.llm_client.chat(
                provider=provider,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            result = self._extract_json(response)
            
            return DocumentSummary(
                document_id=group_id,
                document_name=doc_info["document_name"],
                upload_id=doc_info["upload_id"],
                knowledge_base_name=doc_info.get("knowledge_base_name", ""),
                relationship=result.get("relationship", "参考来源"),
                key_content=result.get("key_content", ""),
                suggestion=result.get("suggestion", ""),
                relevance_score=result.get("relevance_score", 50),
                preview_url=f"/api/word-document/upload_{doc_info['upload_id']}/preview",
                has_smart_summary=existing_summary is not None
            )
            
        except Exception as e:
            logger.warning(f"分析文档相关性失败: {e}")
            return DocumentSummary(
                document_id=group_id,
                document_name=doc_info["document_name"],
                upload_id=doc_info["upload_id"],
                knowledge_base_name=doc_info.get("knowledge_base_name", ""),
                relationship="参考来源",
                key_content="",
                suggestion="",
                relevance_score=50,
                preview_url=f"/api/word-document/upload_{doc_info['upload_id']}/preview",
                has_smart_summary=False
            )
    
    async def _get_document_info(self, group_id: str) -> Optional[Dict]:
        """获取文档信息"""
        from app.core.mysql_client import SessionLocal
        from app.models.document_upload import DocumentUpload
        from app.models.knowledge_base import KnowledgeBase
        
        db = SessionLocal()
        try:
            # 从 group_id 提取 upload_id
            parts = group_id.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                upload_id = int(parts[1])
            else:
                return None
            
            doc = db.query(DocumentUpload).filter(DocumentUpload.id == upload_id).first()
            if doc:
                # 查询知识库名称
                knowledge_base_name = ""
                if doc.knowledge_base_id:
                    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == doc.knowledge_base_id).first()
                    if kb:
                        knowledge_base_name = kb.name
                
                return {
                    "upload_id": doc.id,
                    "document_name": doc.file_name,
                    "knowledge_base_name": knowledge_base_name
                }
            return None
        finally:
            db.close()
    
    async def _get_existing_summary(self, group_id: str) -> Optional[str]:
        """获取已有的智能摘要"""
        from app.core.neo4j_client import neo4j_client
        
        query = """
        MATCH (e:Episodic)
        WHERE e.group_id = $group_id 
          AND e.name ENDS WITH '_文档级'
        RETURN e.content as content
        LIMIT 1
        """
        
        try:
            result = neo4j_client.execute_query(query, {"group_id": group_id})
            if result and len(result) > 0:
                return result[0].get("content")
        except Exception as e:
            logger.warning(f"获取智能摘要失败: {e}")
        
        return None
    
    async def _analyze_coverage(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> Dict[str, Any]:
        """分析知识覆盖度"""
        if not results:
            return {
                "coverage_level": "low",
                "message": "未找到相关信息",
                "covered_aspects": [],
                "missing_aspects": []
            }
        
        # 统计覆盖情况
        source_types = set(r.source_type for r in results)
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        
        # 确定覆盖级别
        if avg_score > 0.7 and len(results) >= 5:
            coverage_level = "high"
            message = "知识库中有丰富的相关信息"
        elif avg_score > 0.5 and len(results) >= 3:
            coverage_level = "medium"
            message = "知识库中有一些相关信息"
        else:
            coverage_level = "low"
            message = "知识库中相关信息较少"
        
        return {
            "coverage_level": coverage_level,
            "message": message,
            "result_count": len(results),
            "avg_score": round(avg_score, 2),
            "source_types": list(source_types),
            "document_count": len(self._group_by_document(results))
        }
    
    async def _generate_answer(
        self,
        query: str,
        results: List[RetrievalResult],
        memories: List[Dict] = None,
        history: List[Dict] = None,
        provider: str = "local"
    ) -> tuple:
        """生成直接回答"""
        # 构建上下文
        context = self._build_context(results)
        
        # 构建记忆上下文
        # 根据 Mem0 官方示例，每个记忆项包含 "memory" 字段
        memory_context = ""
        if memories:
            memory_context = "\n\n**相关历史记忆**：\n"
            for i, mem in enumerate(memories[:5], 1):  # 最多5条记忆
                # 根据官方示例，记忆项是字典，包含 "memory" 字段
                memory_text = mem.get("memory", "") if isinstance(mem, dict) else str(mem)
                if memory_text:
                    memory_context += f"{i}. {memory_text}\n"
        
        # 构建 prompt
        system_prompt = """你是一个知识库助手，根据提供的信息回答用户问题。

**回答原则**：
1. 严格基于提供的信息回答，不要臆造
2. 如果信息不足，如实说明
3. 在回答中标注信息来源（如：根据《文档名》...）
4. 使用清晰的结构和要点
5. 可以参考历史记忆，但优先使用最新的知识库信息

**信息来源**：
""" + context + memory_context
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加历史对话
        if history:
            for h in history[-5:]:  # 最近5轮
                messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        
        messages.append({"role": "user", "content": query})
        
        answer = await self.llm_client.chat(provider=provider, messages=messages, temperature=0.5)
        
        # 提取引用
        references = self._extract_references(results)
        
        return answer, references
    
    def _build_context(self, results: List[RetrievalResult]) -> str:
        """构建上下文"""
        context_parts = []
        
        for i, r in enumerate(results[:10], 1):
            source_type_cn = {
                "entity": "实体",
                "edge": "关系",
                "episode": "内容",
                "community": "主题"
            }.get(r.source_type, r.source_type)
            
            context_parts.append(f"[{source_type_cn}{i}] {r.name}: {r.content[:500]}")
        
        return "\n\n".join(context_parts)
    
    async def _retrieve_memories(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> List[Dict]:
        """
        从 Mem0 检索相关记忆
        
        Args:
            query: 查询文本
            user_id: 用户ID
            session_id: 会话ID（可选）
            
        Returns:
            记忆列表
        """
        if not self.memory:
            return []
        
        try:
            # 根据 Mem0 官方示例：memory.search(query=message, user_id=user_id, limit=3)
            # 返回格式：{"results": [...]}，每个结果包含 "memory" 字段
            # 使用方式：memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories["results"])
            
            # 调用 Mem0 search 方法
            # 注意：Mem0 的 search 方法不支持 session_id 参数，只支持 query, user_id, limit
            # session_id 会在 add 方法中使用，用于区分不同会话的记忆
            memories_result = self.memory.search(query=query, user_id=user_id, limit=5)
            
            # 根据官方示例，返回格式是 {"results": [...]}
            # 每个结果包含 "memory" 字段
            if isinstance(memories_result, dict) and "results" in memories_result:
                return memories_result["results"]
            elif isinstance(memories_result, list):
                # 如果直接返回列表，直接使用
                return memories_result
            else:
                logger.warning(f"Mem0 search 返回格式异常: {type(memories_result)}")
                return []
            
        except Exception as e:
            logger.error(f"Mem0 记忆检索失败: {e}")
            return []
    
    async def _save_memory(
        self,
        query: str,
        answer: str,
        user_id: str,
        session_id: Optional[str] = None
    ):
        """
        保存对话到 Mem0
        
        Args:
            query: 用户问题
            answer: 助手回答
            user_id: 用户ID
            session_id: 会话ID（可选）
        """
        if not self.memory:
            return
        
        try:
            # 根据 Mem0 官方示例：memory.add(messages, user_id=user_id)
            # messages 是消息列表，直接传递，不需要字典包装
            messages = [
                {"role": "user", "content": query},
                {"role": "assistant", "content": answer}
            ]
            
            # 调用 Mem0 add 方法
            # 根据官方示例，参数是位置参数或关键字参数
            # 调用 Mem0 add 方法保存记忆
            # 注意：Mem0 的 add 方法不支持 session_id 参数，只支持 messages 和 user_id
            # session_id 可以通过其他方式实现（例如在 user_id 中包含 session 信息）
            self.memory.add(messages, user_id=user_id)
            
            logger.info(f"对话已保存到 Mem0: user_id={user_id}, session_id={session_id}")
            
        except Exception as e:
            logger.error(f"Mem0 记忆保存失败: {e}")
    
    def _extract_references(self, results: List[RetrievalResult]) -> List[Dict]:
        """提取引用来源"""
        references = []
        seen = set()
        
        for r in results:
            if r.group_id and r.group_id not in seen:
                seen.add(r.group_id)
                references.append({
                    "group_id": r.group_id,
                    "name": r.name,
                    "source_type": r.source_type
                })
        
        return references[:10]
    
    async def _detect_knowledge_gaps(
        self,
        query: str,
        answer: str,
        results: List[RetrievalResult],
        provider: str = "local"
    ) -> List[str]:
        """检测知识缺口"""
        if len(results) >= 5:
            return []  # 信息充足，无需提示
        
        prompt = f"""根据用户问题和生成的回答，判断是否存在知识缺口。

用户问题：{query}

生成的回答：{answer[:1000]}

如果回答中提到"没有找到"、"无法确定"等，或者回答不够完整，请列出可能缺失的知识点。
返回JSON格式：{{"gaps": ["缺口1", "缺口2"]}}
如果没有明显缺口，返回：{{"gaps": []}}"""
        
        try:
            response = await self.llm_client.chat(
                provider=provider,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            result = self._extract_json(response)
            return result.get("gaps", [])[:3]
        except:
            return []
    
    async def _generate_follow_ups(
        self,
        query: str,
        answer: str,
        results: List[RetrievalResult],
        provider: str = "local"
    ) -> List[str]:
        """生成推荐追问"""
        prompt = f"""根据用户问题和回答，生成3个相关的追问建议。

用户问题：{query}

回答摘要：{answer[:500]}

请生成3个有价值的追问，帮助用户深入了解相关内容。
返回JSON格式：{{"questions": ["问题1", "问题2", "问题3"]}}"""
        
        try:
            response = await self.llm_client.chat(
                provider=provider,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            result = self._extract_json(response)
            return result.get("questions", [])[:3]
        except:
            return []
    
    def _extract_json(self, text: str) -> Dict:
        """从文本中提取 JSON"""
        import re
        
        try:
            return json.loads(text)
        except:
            pass
        
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        return {}

