import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_EMBEDDING_MODEL
    
    async def get_embedding(self, text: str) -> list:
        """获取文本的embedding向量"""
        url = f"{self.base_url}/api/embeddings"
        
        data = {
            "model": self.model,
            "prompt": text
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                result = response.json()
                return result.get("embedding", [])
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return []
    
    async def get_embeddings(self, texts: list[str]) -> list[list]:
        """批量获取embeddings"""
        embeddings = []
        for text in texts:
            embedding = await self.get_embedding(text)
            embeddings.append(embedding)
        return embeddings


embedding_client = EmbeddingClient()

