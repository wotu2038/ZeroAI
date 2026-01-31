"""
文档生成状态定义
"""
from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum


class GenerationStage(str, Enum):
    """生成阶段"""
    INIT = "init"                    # 初始化
    RETRIEVING = "retrieving"        # 检索中
    GENERATING = "generating"        # 生成中
    REVIEWING = "reviewing"          # 评审中
    OPTIMIZING = "optimizing"        # 优化中
    COMPLETED = "completed"          # 已完成
    FAILED = "failed"                # 失败


class DocumentGenerationState(TypedDict):
    """文档生成状态"""
    # 输入参数
    user_query: str  # 用户问题/需求描述
    new_requirement_id: Optional[str]  # 新需求ID（可选）
    similar_requirement_ids: List[str]  # 相似历史需求ID列表
    format: str  # markdown, word, pdf
    max_iterations: int  # 最大迭代次数
    quality_threshold: float  # 质量阈值
    retrieval_limit: int  # 检索结果数量限制
    use_thinking: bool  # 是否启用Thinking模式（仅本地大模型支持）
    
    # 检索模式
    group_id: Optional[str]  # 单文档模式
    group_ids: Optional[List[str]]  # 多文档模式
    all_documents: bool  # 全部文档模式
    
    # 检索结果（Episode、Entity、Edge、Community）
    retrieved_content: List[Dict[str, Any]]  # 检索到的相关内容
    # 格式: [
    #   {
    #     "type": "episode" | "entity" | "edge" | "community",
    #     "name": "...",
    #     "content": "...",
    #     "score": 0.85,
    #     "source": "group_id或episode_uuid"
    #   }
    # ]
    
    # 需求数据
    new_requirement: Dict[str, Any]  # 新需求信息（如果提供了ID）
    similar_requirements: List[Dict[str, Any]]  # 相似历史需求
    
    # 生成过程
    current_document: str  # 当前文档内容
    review_report: Optional[Dict[str, Any]]  # 评审报告
    quality_score: float  # 当前质量评分（0-100）
    iteration_count: int  # 当前迭代次数
    
    # 状态控制
    current_stage: GenerationStage
    should_continue: bool  # 是否继续迭代
    is_final: bool  # 是否为最终版本
    
    # 元数据
    task_id: str  # Celery任务ID
    progress: int  # 进度（0-100）
    current_step: str  # 当前步骤描述

