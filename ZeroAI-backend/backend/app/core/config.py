from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # Neo4j配置（从.env读取）
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    
    # 千问配置（支持QWEN和QIANWEN两种命名）
    # 完全从 .env 文件读取，不设置任何默认值
    QWEN_API_KEY: str
    QWEN_API_BASE: str
    QWEN_MODEL: str
    # 向后兼容
    QIANWEN_API_KEY: str = ""
    QIANWEN_API_BASE: str = "https://dashscope.aliyuncs.com"
    
    # DeepSeek 配置（从.env读取）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = ""
    DEEPSEEK_MODEL: str = ""
    DEEPSEEK_TIMEOUT: int = 30
    DEEPSEEK_MAX_RETRIES: int = 3
    
    # Kimi 配置（从.env读取）
    KIMI_API_KEY: str = ""
    KIMI_API_BASE: str = ""
    KIMI_MODEL: str = ""
    KIMI_TIMEOUT: int = 30
    KIMI_MAX_RETRIES: int = 3
    
    # 本地大模型配置（从.env读取，已废弃，保留用于兼容）
    LOCAL_LLM_API_BASE_URL: str = ""
    LOCAL_LLM_API_KEY: str = ""
    LOCAL_LLM_MODEL: str = ""
    
    # Ollama Embedding配置（从.env读取）
    OLLAMA_BASE_URL: str
    OLLAMA_EMBEDDING_MODEL: str
    
    # MySQL数据库配置（从.env读取）
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str
    
    # Redis配置（用于Celery，从.env读取）
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: str = ""  # Redis密码（可选）
    
    # JWT配置（必须在 .env 中设置）
    # 可使用命令生成：python -c "import secrets; print(secrets.token_urlsafe(32))"
    JWT_SECRET_KEY: str
    
    # 默认管理员配置（可选，从 .env 读取）
    # 如果未设置，首次启动时不会自动创建管理员用户
    DEFAULT_ADMIN_USERNAME: str = ""
    DEFAULT_ADMIN_PASSWORD: str = ""
    DEFAULT_ADMIN_EMAIL: str = ""
    
    # ==================== 智能分块配置 ====================
    # 是否启用LLM智能分块策略选择
    ENABLE_SMART_CHUNKING: bool = True
    # 分块质量阈值（0-100），低于此分数需要重试
    CHUNKING_QUALITY_THRESHOLD: int = 70
    
    # ==================== 质量评估配置 ====================
    # 提取质量评估采样数量
    EXTRACTION_QUALITY_SAMPLE_SIZE: int = 10
    # 提取质量阈值（0-100）
    EXTRACTION_QUALITY_THRESHOLD: int = 70
    # 图结构质量阈值（0-100）
    GRAPH_QUALITY_THRESHOLD: int = 70
    # 质量门禁综合阈值（0-100）
    QUALITY_GATE_THRESHOLD: int = 70
    # 质量门禁最大重试次数
    QUALITY_GATE_MAX_RETRIES: int = 3
    
    # ==================== LLM摘要配置 ====================
    # 摘要质量阈值（0-100）
    SUMMARY_QUALITY_THRESHOLD: int = 60
    
    # ==================== Episode处理配置 ====================
    # Episode并发处理最大数量
    EPISODE_MAX_CONCURRENT: int = 5
    
    # ==================== Milvus配置（可选）====================
    MILVUS_HOST: str = ""
    MILVUS_PORT: int = 19530
    MILVUS_USERNAME: str = ""
    MILVUS_PASSWORD: str = ""
    # 是否启用Milvus向量存储
    ENABLE_MILVUS: bool = False
    
    # ==================== Community配置 ====================
    # 是否启用自动Community构建
    ENABLE_AUTO_COMMUNITY: bool = True
    # 构建Community所需的最少实体数量
    COMMUNITY_MIN_ENTITIES: int = 5
    # Community构建超时时间（秒），默认180秒（3分钟）
    COMMUNITY_BUILD_TIMEOUT: float = 180.0
    
    # ==================== Cognee配置 ====================
    # Cognee章节模板生成阈值
    # 章节数量 < 此阈值：为每个章节单独生成模板（方案2）
    # 章节数量 >= 此阈值：为所有章节生成一个模板（方案1）
    COGNEE_SECTION_TEMPLATE_THRESHOLD: int = 5
    # Cognee LLM 请求超时时间（秒），默认600秒（10分钟）
    # 注意：litellm 会将此值乘以10，所以设置600会变成6000.0秒
    COGNEE_LLM_REQUEST_TIMEOUT: float = 600.0
    
    class Config:
        # 优先从环境变量读取（docker-compose的env_file已加载）
        # 如果环境变量不存在，则尝试从.env文件读取
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

