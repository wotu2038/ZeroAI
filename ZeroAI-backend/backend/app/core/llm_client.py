from typing import Literal, Optional
from openai import OpenAI
import httpx
import json
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

LLMProvider = Literal["qianwen", "qwen", "deepseek", "kimi", "local"]


class LLMClient:
    def __init__(self):
        self.qianwen_client = None
        self.deepseek_client = None
        self.kimi_client = None
        self.local_client = None
        self._init_clients()
    
    def _init_clients(self):
        """初始化LLM客户端"""
        # 千问3使用HTTP客户端（支持QWEN和QIANWEN两种命名）
        self.qianwen_api_key = settings.QWEN_API_KEY or settings.QIANWEN_API_KEY
        self.qianwen_api_base = settings.QWEN_API_BASE or settings.QIANWEN_API_BASE
        self.qianwen_model = settings.QWEN_MODEL
        
        # DeepSeek 客户端（使用OpenAI兼容接口）
        if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_BASE:
            try:
                deepseek_base_url = settings.DEEPSEEK_API_BASE.rstrip('/')
                if not deepseek_base_url.endswith("/v1"):
                    if "/v1" not in deepseek_base_url:
                        deepseek_base_url = f"{deepseek_base_url}/v1"
                self.deepseek_client = OpenAI(
                    api_key=settings.DEEPSEEK_API_KEY,
                    base_url=deepseek_base_url
                )
                logger.info(f"DeepSeek 客户端初始化成功: {deepseek_base_url}")
            except Exception as e:
                logger.warning(f"DeepSeek 客户端初始化失败: {e}")
                self.deepseek_client = None
        
        # Kimi 客户端（使用OpenAI兼容接口）
        if settings.KIMI_API_KEY and settings.KIMI_API_BASE:
            try:
                kimi_base_url = settings.KIMI_API_BASE.rstrip('/')
                if not kimi_base_url.endswith("/v1"):
                    if "/v1" not in kimi_base_url:
                        kimi_base_url = f"{kimi_base_url}/v1"
                self.kimi_client = OpenAI(
                    api_key=settings.KIMI_API_KEY,
                    base_url=kimi_base_url
                )
                logger.info(f"Kimi 客户端初始化成功: {kimi_base_url}")
            except Exception as e:
                logger.warning(f"Kimi 客户端初始化失败: {e}")
                self.kimi_client = None
        
        # 本地大模型客户端（使用OpenAI兼容接口）
        # 只有当配置有效时才初始化（避免占位符导致错误）
        if settings.LOCAL_LLM_API_BASE_URL and not settings.LOCAL_LLM_API_BASE_URL.startswith("http://your_") and not settings.LOCAL_LLM_API_BASE_URL.startswith("https://your_"):
            try:
                local_base_url = settings.LOCAL_LLM_API_BASE_URL.rstrip('/')
                # 确保 base_url 包含 /v1（OpenAI 客户端会自动添加 /chat/completions）
                if not local_base_url.endswith("/v1"):
                    if "/v1" not in local_base_url:
                        local_base_url = f"{local_base_url}/v1"
                self.local_client = OpenAI(
                    api_key=settings.LOCAL_LLM_API_KEY,
                    base_url=local_base_url
                )
            except Exception as e:
                logger.warning(f"本地大模型客户端初始化失败（配置可能无效）: {e}")
                self.local_client = None
    
    async def chat(
        self,
        provider: LLMProvider,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        use_thinking: bool = False
    ) -> str:
        """调用LLM进行对话"""
        if provider == "qianwen" or provider == "qwen":
            return await self._chat_qianwen(messages, model, temperature)
        elif provider == "deepseek":
            return await self._chat_deepseek(messages, model, temperature)
        elif provider == "kimi":
            return await self._chat_kimi(messages, model, temperature)
        elif provider == "local":
            return await self._chat_local(messages, model, temperature, use_thinking)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def _chat_qianwen(
        self,
        messages: list,
        model: Optional[str],
        temperature: float
    ) -> str:
        """千问3对话"""
        if not self.qianwen_api_key:
            raise ValueError("千问3 API key not configured")
        
        model = model or self.qianwen_model
        # 千问3 API格式
        url = f"{self.qianwen_api_base}/api/v1/services/aigc/text-generation/generation"
        
        # 转换消息格式
        qianwen_messages = []
        for msg in messages:
            qianwen_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        headers = {
            "Authorization": f"Bearer {self.qianwen_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "input": {
                "messages": qianwen_messages
            },
            "parameters": {
                "temperature": temperature
            }
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5分钟超时
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            # 处理千问API响应格式
            if "output" in result:
                if "choices" in result["output"]:
                    return result["output"]["choices"][0]["message"]["content"]
                elif "text" in result["output"]:
                    # 千问API可能返回 text 字段
                    return result["output"]["text"]
                else:
                    # 尝试直接获取文本内容
                    logger.warning(f"Unexpected qianwen response format: {result}")
                    if "text" in result:
                        return result["text"]
                    raise ValueError(f"Unexpected response format: {result}")
            elif "choices" in result:
                return result["choices"][0]["message"]["content"]
            else:
                raise ValueError(f"Unexpected response format: {result}")
    
    async def _chat_deepseek(
        self,
        messages: list,
        model: Optional[str],
        temperature: float
    ) -> str:
        """DeepSeek 对话（使用OpenAI兼容接口）"""
        if not self.deepseek_client:
            raise ValueError("DeepSeek 客户端未初始化")
        
        model = model or settings.DEEPSEEK_MODEL
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.deepseek_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
        )
        return response.choices[0].message.content
    
    async def _chat_kimi(
        self,
        messages: list,
        model: Optional[str],
        temperature: float
    ) -> str:
        """Kimi 对话（使用OpenAI兼容接口）"""
        if not self.kimi_client:
            raise ValueError("Kimi 客户端未初始化")
        
        model = model or settings.KIMI_MODEL
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.kimi_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
        )
        return response.choices[0].message.content
    
    async def _chat_local(
        self,
        messages: list,
        model: Optional[str],
        temperature: float,
        use_thinking: bool = False
    ) -> str:
        """本地大模型对话（OpenAI兼容接口）"""
        if not self.local_client:
            raise ValueError("本地大模型 API 未配置")
        
        model = model or settings.LOCAL_LLM_MODEL
        # 构建请求参数
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        # 如果启用Thinking模式，添加extra_body参数
        if use_thinking:
            request_params["extra_body"] = {"thinking": True}
            logger.info(f"启用Thinking模式: extra_body={request_params['extra_body']}")
        else:
            logger.info(f"未启用Thinking模式 (use_thinking={use_thinking})")
        
        # 使用异步方式调用
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.local_client.chat.completions.create(**request_params)
        )
        return response.choices[0].message.content
    
    async def extract_entities(
        self,
        provider: LLMProvider,
        text: str
    ) -> dict:
        """从文本中提取实体和关系"""
        prompt = f"""请从以下文本中提取实体和关系，返回JSON格式：
{{
  "entities": [
    {{"name": "实体名称", "type": "实体类型", "properties": {{"key": "value"}}}}
  ],
  "relationships": [
    {{"source": "源实体", "target": "目标实体", "type": "关系类型", "properties": {{}}}}
  ]
}}

文本内容：
{text}

只返回JSON，不要其他内容。"""
        
        messages = [
            {"role": "system", "content": "你是一个知识图谱实体抽取专家，擅长从文本中提取结构化信息。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat(provider, messages, temperature=0.3, use_thinking=False)
        
        # 解析JSON响应
        try:
            # 尝试提取JSON部分
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response: {response}")
            return {"entities": [], "relationships": []}
    
    async def generate(
        self,
        provider: LLMProvider,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_thinking: bool = False
    ) -> str:
        """生成文本（基于prompt）"""
        messages = [
            {"role": "user", "content": prompt}
        ]
        return await self.chat(provider, messages, temperature=temperature, use_thinking=use_thinking)


llm_client = LLMClient()


def get_llm_client(provider: Optional[LLMProvider] = None) -> LLMClient:
    """获取LLM客户端实例"""
    return llm_client

