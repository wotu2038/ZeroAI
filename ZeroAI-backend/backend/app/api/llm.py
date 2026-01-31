from fastapi import APIRouter, HTTPException
from app.models.schemas import LLMChatRequest, LLMResponse, LLMExtractRequest
from app.core.llm_client import llm_client
from app.services.graphiti_service import GraphitiService
from app.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=LLMResponse)
async def chat(request: LLMChatRequest):
    """LLM对话（增强版：自动查询知识图谱，严格基于Graphiti检索结果）"""
    import time
    retrieval_start_time = time.time()
    
    try:
        # 获取最后一条用户消息
        user_messages = [msg for msg in request.messages if msg.get("role") == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="没有用户消息")
        
        last_user_message = user_messages[-1]["content"]
        
        # 从知识图谱检索相关信息（使用Graphiti）
        graph_context = ""
        retrieval_results = []
        retrieval_count = 0
        has_context = False
        
        try:
            # 步骤1: 使用Graphiti进行语义检索（优先使用完整问题）
            logger.info(f"开始Graphiti语义检索: query='{last_user_message}'")
            search_results = await GraphitiService.retrieve(
                query=last_user_message,
                provider=request.provider,
                limit=10  # 增加检索数量，确保能找到相关结果
            )
            logger.info(f"Graphiti语义检索完成，返回 {len(search_results) if search_results else 0} 个结果")
            
            # 如果检索结果为空，尝试提取问题中的关键词（中文实体名称）
            if not search_results or len(search_results) == 0:
                import re
                # 方法1: 提取所有2-3个字符的中文词（通常是实体名称）
                all_chinese = re.findall(r'[\u4e00-\u9fa5]+', last_user_message)
                keywords = []
                for text in all_chinese:
                    # 提取2-3个字符的词
                    for i in range(len(text) - 1):
                        if i + 2 <= len(text):
                            word = text[i:i+2]
                            if word not in keywords:
                                keywords.append(word)
                        if i + 3 <= len(text):
                            word = text[i:i+3]
                            if word not in keywords:
                                keywords.append(word)
                
                # 过滤掉常见的停用词
                stopwords = ['什么', '关系', '是', '和', '的', '了', '在', '有', '我', '你', '他', '她', '它', '这', '那', '哪', '怎么', '如何', '为什么', '一个', '两个', '三个']
                keywords = [kw for kw in keywords if kw not in stopwords and len(kw) >= 2]
                logger.info(f"Extracted keywords from query: {keywords}")
                if keywords:
                    # 对每个关键词分别检索
                    all_results = []
                    for keyword in keywords[:3]:  # 最多检索3个关键词
                        try:
                            logger.info(f"Searching for keyword: {keyword}")
                            keyword_results = await GraphitiService.retrieve(
                                query=keyword,
                                provider=request.provider,
                                limit=5
                            )
                            logger.info(f"Found {len(keyword_results) if keyword_results else 0} results for keyword: {keyword}")
                            if keyword_results:
                                all_results.extend(keyword_results)
                        except Exception as e:
                            logger.warning(f"Failed to search for keyword {keyword}: {e}")
                            continue
                    # 去重
                    seen_ids = set()
                    unique_results = []
                    for result in all_results:
                        result_id = f"{result.get('type')}_{result.get('id')}"
                        if result_id not in seen_ids:
                            seen_ids.add(result_id)
                            unique_results.append(result)
                    search_results = unique_results[:10]  # 最多10个结果
                    logger.info(f"关键词检索完成，共找到 {len(search_results)} 个结果")
            
            # 保存检索结果用于返回
            if search_results and len(search_results) > 0:
                retrieval_results = search_results
                retrieval_count = len(search_results)
                has_context = True
                logger.info(f"检索成功，找到 {retrieval_count} 个相关结果")
            
            if search_results and len(search_results) > 0:
                # 构建知识图谱上下文（优先使用关系，因为关系包含更完整的信息）
                graph_context = "\n\n【知识图谱信息】\n"
                edges_info = []
                nodes_info = []
                
                # 分离关系和节点
                edge_results = [r for r in search_results if r.get("type") == "edge"]
                node_results = [r for r in search_results if r.get("type") == "node"]
                
                # 优先处理关系（边），因为关系包含fact字段，信息更完整
                for result in edge_results[:8]:  # 最多使用8个关系
                    source_name = result.get("source_name", "")
                    target_name = result.get("target_name", "")
                    rel_type = result.get("rel_type") or result.get("type", "")
                    fact = result.get("fact", "")  # Graphiti的关系事实描述
                    
                    # 如果有fact，直接使用fact（这是最完整的信息）
                    if fact:
                        edge_info = f"- {fact}"
                    else:
                        # 如果没有fact，构建关系描述
                        if source_name and target_name:
                            edge_info = f"- {source_name} --[{rel_type}]--> {target_name}"
                        else:
                            # 如果连名称都没有，跳过这个结果
                            continue
                    edges_info.append(edge_info)
                
                # 处理实体（节点）
                for result in node_results[:5]:  # 最多使用5个实体
                    node_name = result.get("properties", {}).get("name", "")
                    if not node_name:
                        continue
                    node_type = result.get("labels", [""])[0] if result.get("labels") else "Entity"
                    props = result.get("properties", {})
                    summary = props.get("summary", "")
                    
                    if summary:
                        node_info = f"- {node_name} ({node_type}): {summary}"
                    else:
                        props_str = ", ".join([f"{k}: {v}" for k, v in props.items() if k not in ["name", "summary", "name_embedding"]])
                        node_info = f"- {node_name} ({node_type})"
                        if props_str:
                            node_info += f": {props_str}"
                    nodes_info.append(node_info)
                
                # 先显示关系（更重要），再显示实体
                if edges_info:
                    graph_context += "关系：\n" + "\n".join(edges_info) + "\n"
                if nodes_info:
                    graph_context += "实体：\n" + "\n".join(nodes_info) + "\n"
                
                graph_context += "\n**请严格基于以上知识图谱信息回答用户的问题。如果知识图谱中有相关信息，请直接使用这些信息回答，不要说\"没有找到相关信息\"。只有在知识图谱中确实没有相关信息时，才可以说\"根据知识图谱信息，没有找到相关信息\"。**\n"
        except Exception as e:
            logger.warning(f"Failed to retrieve from knowledge graph: {e}")
            # 如果检索失败，继续使用LLM回答，但不提供图谱上下文
        
        # 构建增强的消息列表
        enhanced_messages = []
        
        # 添加系统提示
        system_prompt = """你是一个知识图谱助手，可以帮助用户查询和理解知识图谱中的信息。

**核心原则**：你的回答必须**严格且完全基于**下面提供的知识图谱信息。

**回答规则**：
1. **必须使用**知识图谱中提供的信息来回答问题
2. 如果知识图谱中**有相关信息**，请直接使用这些信息回答，不要说"没有找到相关信息"
3. 如果知识图谱中**确实没有相关信息**，才可以说"根据知识图谱信息，没有找到相关信息"
4. **绝对不要**编造、推测或添加任何知识图谱中没有的信息
5. 回答时，请引用具体的实体名称和关系类型"""
        
        if graph_context:
            system_prompt += graph_context
        else:
            system_prompt += "\n\n注意：当前知识图谱中没有检索到相关信息，请如实告知用户。"
        
        enhanced_messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 添加历史消息（除了最后一条用户消息）
        for msg in request.messages[:-1]:
            enhanced_messages.append(msg)
        
        # 添加最后一条用户消息
        enhanced_messages.append({
            "role": "user",
            "content": last_user_message
        })
        
        # 调用LLM生成回答（严格基于检索结果）
        content = await llm_client.chat(
            provider=request.provider,
            messages=enhanced_messages,
            temperature=request.temperature,
            use_thinking=request.use_thinking if request.provider == "local" else False
        )
        
        # 计算检索耗时
        retrieval_time = (time.time() - retrieval_start_time) * 1000  # 转换为毫秒
        
        logger.info(f"LLM回答生成完成，基于 {retrieval_count} 个检索结果")
        
        return LLMResponse(
            content=content,
            retrieval_results=retrieval_results,
            retrieval_count=retrieval_count,
            retrieval_time=retrieval_time,
            has_context=has_context
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM调用失败: {str(e)}")


@router.post("/extract", response_model=dict)
async def extract_entities(request: LLMExtractRequest):
    """使用Graphiti从文本中自动提取实体和关系"""
    try:
        # 构建元数据
        metadata = {"source": "llm_extract"}
        if hasattr(request, 'metadata') and request.metadata:
            metadata.update(request.metadata)
        
        # 使用Graphiti自动提取实体和关系
        result = await GraphitiService.add_episode(
            content=request.text,
            provider=request.provider,
            metadata=metadata
        )
        
        return {
            "episode_id": result.get("episode_id"),
            "extracted": {
                "entities": result.get("entities", []),
                "relationships": result.get("relationships", [])
            },
            "entities_created": result.get("entities_created", 0),
            "relationships_created": result.get("relationships_created", 0),
            "errors": []
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Extract entities error: {e}", exc_info=True)
        
        # 检查是否是文本长度超限错误
        if "文本内容过长" in error_msg or "tokens" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        # 检查是否是 token 长度超限错误（来自 LLM API）
        elif "maximum context length" in error_msg.lower() or "context length" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"文本内容过长，超过了模型的最大上下文长度限制。\n\n错误详情: {error_msg}\n\n建议：\n1. 将文本分割成多个较小的部分，分别提交\n2. 缩短文本内容，只保留关键信息\n3. 对于长文档，建议使用文档上传功能，系统会自动分块处理"
            )
        # 检查是否是 response_format 错误
        elif "response_format" in error_msg.lower() or "unavailable" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"LLM API 配置错误: {error_msg}"
            )
        elif "404" in error_msg:
            if request.provider == "qianwen" or request.provider == "qwen":
                raise HTTPException(
                    status_code=404,
                    detail=f"千问3 API 端点错误（404）。请检查 QWEN_API_BASE 配置是否正确。当前配置: {settings.QWEN_API_BASE}。错误详情: {error_msg}"
                )
        
        raise HTTPException(status_code=500, detail=f"提取失败: {error_msg}")


@router.get("/providers", response_model=list)
async def get_providers():
    """获取可用的LLM提供商"""
    providers = []
    if llm_client.qianwen_api_key:
        providers.append("qianwen")
    if llm_client.local_client:
        providers.append("local")
    return providers

