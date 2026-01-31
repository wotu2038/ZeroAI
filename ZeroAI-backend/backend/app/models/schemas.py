from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# 实体相关模型
class EntityCreate(BaseModel):
    name: str
    type: str = Field(..., description="实体类型：Person, Organization, Location, Concept, Event等")
    properties: Dict[str, Any] = Field(default_factory=dict)


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class Entity(BaseModel):
    id: str
    name: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


# 关系相关模型
class RelationshipCreate(BaseModel):
    source: str = Field(..., description="源实体名称或ID")
    target: str = Field(..., description="目标实体名称或ID")
    type: str = Field(..., description="关系类型：KNOWS, WORKS_FOR, LOCATED_IN, RELATED_TO等")
    properties: Dict[str, Any] = Field(default_factory=dict)


class RelationshipUpdate(BaseModel):
    type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class Relationship(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


# 图查询模型
class GraphQuery(BaseModel):
    query: str = Field(..., description="Cypher查询语句")


class GraphNode(BaseModel):
    id: str
    labels: List[str]
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any]


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# LLM相关模型
class LLMChatRequest(BaseModel):
    provider: Literal["qianwen", "qwen", "deepseek", "kimi", "local"] = Field(..., description="LLM提供商")
    messages: List[Dict[str, str]] = Field(..., description="对话消息列表")
    temperature: float = Field(default=0.7, ge=0, le=2)
    use_thinking: bool = Field(default=False, description="是否启用Thinking模式（仅本地大模型支持）")
    cross_encoder_mode: Literal["default", "enhanced", "smart"] = Field(default="default", description="交叉编码方案：default（默认）、enhanced（增强）、smart（智能增强）")


class LLMExtractRequest(BaseModel):
    provider: Literal["qianwen", "qwen", "deepseek", "kimi", "local"] = Field(..., description="LLM提供商")
    text: str = Field(..., description="待提取的文本")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Episode元数据（可选）")


class LLMResponse(BaseModel):
    content: str
    retrieval_results: Optional[List[Dict[str, Any]]] = Field(default=None, description="Graphiti检索结果")
    retrieval_count: int = Field(default=0, description="检索结果数量")
    retrieval_time: Optional[float] = Field(default=None, description="检索耗时（毫秒）")
    has_context: bool = Field(default=False, description="是否有知识图谱上下文")
    # 增强字段（可选，向后兼容）
    answer: Optional[str] = Field(default=None, description="回答内容（与content相同，用于前端兼容）")
    document_summaries: Optional[List[Dict[str, Any]]] = Field(default=None, description="相关文档总结列表")
    knowledge_coverage: Optional[Dict[str, Any]] = Field(default=None, description="知识覆盖度分析")
    knowledge_gaps: Optional[List[str]] = Field(default=None, description="知识缺口提示")
    follow_up_questions: Optional[List[str]] = Field(default=None, description="追问建议")


# 导入数据模型
class ImportDataRequest(BaseModel):
    format: Literal["csv", "json"] = Field(..., description="数据格式")
    data: str = Field(..., description="数据内容（CSV字符串或JSON字符串）")


class ImportResult(BaseModel):
    success: bool
    entities_created: int = 0
    relationships_created: int = 0
    errors: List[str] = Field(default_factory=list)


# 路径查询模型
class PathQueryRequest(BaseModel):
    source: str = Field(..., description="源实体名称")
    target: Optional[str] = Field(None, description="目标实体名称（可选，如果不提供则查找源实体的所有关系链）")
    max_depth: int = Field(10, ge=1, le=10, description="最大路径长度（跳数）")
    limit: int = Field(100, ge=1, le=500, description="返回路径数量限制")


class PathSegment(BaseModel):
    """路径中的一段（一个关系）"""
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    relation_id: str
    relation_type: str
    relation_name: Optional[str] = None
    relation_fact: Optional[str] = None


class PathResult(BaseModel):
    """一条完整路径"""
    path_id: str
    segments: List[PathSegment]
    length: int  # 路径长度（跳数）
    is_shortest: bool = False  # 是否为最短路径


class PathQueryResponse(BaseModel):
    """路径查询响应"""
    source: str
    target: Optional[str]
    paths: List[PathResult]
    total_paths: int
    shortest_length: Optional[int] = None  # 最短路径长度


# 需求助手相关模型
class RequirementCreate(BaseModel):
    """创建需求请求"""
    name: str = Field(..., description="需求名称")
    content: str = Field(..., description="需求文档内容（Markdown格式）")
    version: Optional[str] = Field(None, description="版本号")
    description: Optional[str] = Field(None, description="需求描述（摘要）")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class RequirementUpdate(BaseModel):
    """更新需求请求"""
    name: Optional[str] = None
    content: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Requirement(BaseModel):
    """需求实体"""
    id: str
    name: str
    content: str
    version: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    features_count: int = Field(default=0, description="功能点数量")
    modules_count: int = Field(default=0, description="模块数量")


class Feature(BaseModel):
    """功能点实体"""
    id: str
    name: str
    description: Optional[str] = None
    module_name: Optional[str] = Field(None, description="所属模块名称")
    properties: Dict[str, Any] = Field(default_factory=dict)


class Module(BaseModel):
    """模块实体"""
    id: str
    name: str
    description: Optional[str] = None
    features_count: int = Field(default=0, description="功能点数量")
    properties: Dict[str, Any] = Field(default_factory=dict)


class SimilarRequirementQuery(BaseModel):
    """相似需求查询请求"""
    requirement_id: Optional[str] = Field(None, description="需求ID（如果提供，则查询与该需求相似的其他需求）")
    query_text: Optional[str] = Field(None, description="查询文本（如果提供，则基于文本查询相似需求）")
    limit: int = Field(10, ge=1, le=50, description="返回结果数量限制")
    include_features: bool = Field(True, description="是否包含功能点重合度")
    include_modules: bool = Field(True, description="是否包含模块重合度")


class SimilarRequirementResult(BaseModel):
    """相似需求查询结果"""
    requirement: Requirement
    similarity_score: float = Field(..., description="相似度分数（0-1）")
    semantic_score: Optional[float] = Field(None, description="语义相似度分数")
    feature_overlap_count: Optional[int] = Field(None, description="功能点重合数量")
    feature_overlap_ratio: Optional[float] = Field(None, description="功能点重合比例")
    module_overlap_count: Optional[int] = Field(None, description="模块重合数量")
    module_overlap_ratio: Optional[float] = Field(None, description="模块重合比例")
    common_features: Optional[List[str]] = Field(None, description="共同功能点列表")
    common_modules: Optional[List[str]] = Field(None, description="共同模块列表")


class SimilarRequirementResponse(BaseModel):
    """相似需求查询响应"""
    query_requirement: Optional[Requirement] = Field(None, description="查询的需求（如果提供了requirement_id）")
    results: List[SimilarRequirementResult]
    total: int


class RequirementDocumentGenerateRequest(BaseModel):
    """需求文档生成请求（同步）"""
    new_requirement_id: str = Field(..., description="新需求ID")
    similar_requirement_ids: List[str] = Field(..., description="相似历史需求ID列表")
    format: Literal["markdown", "word", "pdf"] = Field("markdown", description="生成文档格式")
    template: Optional[str] = Field(None, description="文档模板（可选）")
    include_similarity_analysis: bool = Field(True, description="是否包含相似度分析")


class RequirementDocumentGenerateAsyncRequest(BaseModel):
    """异步生成需求文档请求"""
    user_query: str = Field(..., description="用户问题/需求描述")
    new_requirement_id: Optional[str] = Field(None, description="新需求ID（可选）")
    similar_requirement_ids: List[str] = Field(default_factory=list, description="相似历史需求ID列表（可选）")
    format: Literal["markdown", "word", "pdf"] = Field("markdown", description="生成文档格式")
    max_iterations: int = Field(3, ge=1, le=10, description="最大迭代次数")
    quality_threshold: float = Field(80.0, ge=0, le=100, description="质量阈值")
    retrieval_limit: int = Field(20, ge=5, le=50, description="检索结果数量限制")
    use_thinking: bool = Field(default=False, description="是否启用Thinking模式（仅本地大模型支持）")
    
    # 检索模式
    group_id: Optional[str] = Field(None, description="单文档模式：指定group_id")
    group_ids: Optional[List[str]] = Field(None, description="多文档模式：指定group_id列表")
    all_documents: bool = Field(False, description="全部文档模式：检索所有文档")


class RequirementDocumentGenerateResponse(BaseModel):
    """需求文档生成响应"""
    document_id: str
    document_name: str
    format: str
    content: Optional[str] = Field(None, description="文档内容（Markdown格式）")
    file_path: Optional[str] = Field(None, description="生成的文件路径（Word/PDF格式）")
    download_url: Optional[str] = Field(None, description="下载URL")


# Word 文档处理相关模型
class WordDocumentProcessResponse(BaseModel):
    """Word 文档处理响应"""
    success: bool
    document_id: str
    document_name: str
    document_episode_uuid: str
    section_episodes: List[str]
    image_episodes: List[str] = Field(default_factory=list)
    table_episodes: List[str] = Field(default_factory=list)
    statistics: Dict[str, Any]


class DocumentEpisodesResponse(BaseModel):
    """文档 Episode 查询响应"""
    document_id: str
    document_episode: Optional[Dict[str, Any]] = None
    section_episodes: List[Dict[str, Any]] = Field(default_factory=list)
    image_episodes: List[Dict[str, Any]] = Field(default_factory=list)
    table_episodes: List[Dict[str, Any]] = Field(default_factory=list)


class DocumentContentResponse(BaseModel):
    """文档内容响应"""
    document_id: str
    original_content: Optional[str] = Field(None, description="原始文档内容（纯文本）")
    parsed_content: str = Field(..., description="解析后的文档全部内容（合并所有Episode）")
    file_path: Optional[str] = Field(None, description="原始文件路径")
    original_filename: Optional[str] = Field(None, description="原始文件名")


class DocumentListItem(BaseModel):
    """文档列表项"""
    document_id: str = Field(..., description="文档ID（group_id）")
    document_name: str = Field(..., description="文档名称")
    created_at: Optional[str] = Field(None, description="创建时间")
    total_episodes: int = Field(0, description="Episode总数")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="统计信息")


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentListItem] = Field(default_factory=list)
    total: int = Field(0, description="文档总数")


class RealtimeParsedContentResponse(BaseModel):
    """实时解析文档内容响应"""
    document_id: str
    parsed_content: str
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)


# 模板管理相关模型
class TemplateCreate(BaseModel):
    """创建模板请求"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    category: str = Field(default="custom", description="模板分类")
    entity_types: Dict[str, Any] = Field(..., description="实体类型定义")
    edge_types: Dict[str, Any] = Field(..., description="关系类型定义")
    edge_type_map: Dict[str, Any] = Field(..., description="关系类型映射")
    is_default: bool = Field(default=False, description="是否默认模板")


class TemplateUpdate(BaseModel):
    """更新模板请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = None
    entity_types: Optional[Dict[str, Any]] = None
    edge_types: Optional[Dict[str, Any]] = None
    edge_type_map: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class TemplateResponse(BaseModel):
    """模板响应"""
    id: int
    name: str
    description: Optional[str]
    category: str
    entity_types: Dict[str, Any]
    edge_types: Dict[str, Any]
    edge_type_map: Dict[str, Any]
    is_default: bool
    is_system: bool
    is_llm_generated: Optional[bool] = False
    source_document_id: Optional[int] = None
    analysis_mode: Optional[str] = None
    llm_provider: Optional[str] = None
    generated_at: Optional[str] = None
    usage_count: int
    created_at: str
    updated_at: str
    created_by: Optional[str]


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    templates: List[TemplateResponse] = Field(default_factory=list)
    total: int = Field(0, description="模板总数")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(10, description="每页数量")


class TemplateValidateRequest(BaseModel):
    """模板校验请求"""
    entity_types: Dict[str, Any]
    edge_types: Dict[str, Any]
    edge_type_map: Dict[str, Any]


class TemplateValidateResponse(BaseModel):
    """模板校验响应"""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TemplateGenerateRequest(BaseModel):
    """LLM生成模板请求"""
    document_id: int = Field(..., description="文档上传ID")
    analysis_mode: str = Field(..., description="分析模式：smart_segment（智能分段）或 full_chunk（全文分块）")
    template_name: Optional[str] = Field(None, description="模板名称（可选，不提供则自动生成）")
    description: Optional[str] = Field(None, description="模板描述（可选）")
    category: str = Field(default="custom", description="模板分类")


class TemplateGenerateResponse(BaseModel):
    """LLM生成模板响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="提示信息")


# 知识库相关模型
class KnowledgeBaseCreateRequest(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    visibility: Literal["private", "shared"] = Field("private", description="可见性：private（个人）/shared（共享）")


class KnowledgeBaseUpdateRequest(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    visibility: Optional[Literal["private", "shared"]] = Field(None, description="可见性")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    id: int
    name: str
    description: Optional[str]
    cover_icon: Optional[str]
    cover_image: Optional[str]
    creator_name: Optional[str]
    category: Optional[str]
    visibility: str
    default_template_id: Optional[int]
    member_count: int
    document_count: int
    last_updated_at: Optional[str]
    created_at: str
    updated_at: str
    is_member: Optional[bool] = Field(None, description="当前用户是否是成员")
    user_role: Optional[str] = Field(None, description="当前用户在知识库中的角色")


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应"""
    knowledge_bases: List[KnowledgeBaseResponse] = Field(default_factory=list)
    total: int = Field(0, description="总数")


class KnowledgeBaseMemberResponse(BaseModel):
    """知识库成员响应"""
    id: int
    knowledge_base_id: int
    member_name: str
    role: str
    joined_at: str


class KnowledgeBaseMemberListResponse(BaseModel):
    """知识库成员列表响应"""
    members: List[KnowledgeBaseMemberResponse] = Field(default_factory=list)


class AddMemberRequest(BaseModel):
    """添加成员请求"""
    member_name: str = Field(..., description="成员名称")
    role: Literal["owner", "admin", "editor", "viewer"] = Field("viewer", description="成员角色")



