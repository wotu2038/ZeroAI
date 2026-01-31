"""
LangGraph工作流定义
"""
import logging
from typing import Dict, Any
from .state import DocumentGenerationState, GenerationStage
from .agents import (
    ContentRetriever,
    DocumentGenerator,
    DocumentReviewer,
    DocumentOptimizer,
    Orchestrator
)

logger = logging.getLogger(__name__)


async def run_document_generation_workflow(state: DocumentGenerationState) -> DocumentGenerationState:
    """
    执行文档生成工作流
    
    工作流流程：
    1. 检索相关内容（Episode、Entity、Edge，必要时Community）
    2. 生成初始文档
    3. 评审文档质量
    4. 协调决策：是否需要优化
    5. 如果需要优化，执行优化并回到评审
    6. 如果不需要优化，输出最终文档
    """
    try:
        # 步骤1: 检索
        logger.info("开始检索相关内容")
        state = await ContentRetriever.retrieve(state)
        
        # 步骤2: 生成
        logger.info("开始生成文档")
        state = await DocumentGenerator.generate(state)
        
        # 步骤3-6: 迭代优化循环
        max_iterations = state.get("max_iterations", 3)
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            state["iteration_count"] = iteration
            
            # 步骤3: 评审
            logger.info(f"开始评审文档（第{iteration}次迭代）")
            state = await DocumentReviewer.review(state)
            
            # 步骤4: 协调决策
            logger.info("开始协调决策")
            state = await Orchestrator.decide(state)
            
            # 步骤5: 判断是否需要优化
            if not state.get("should_continue", False):
                logger.info("文档质量达标，结束迭代")
                break
            
            # 步骤6: 优化
            logger.info(f"开始优化文档（第{iteration}次迭代）")
            state = await DocumentOptimizer.optimize(state)
        
        # 如果达到最大迭代次数仍未达标，标记为最终版本
        if iteration >= max_iterations:
            state["is_final"] = True
            state["current_stage"] = GenerationStage.COMPLETED
            state["progress"] = 100
            state["current_step"] = f"达到最大迭代次数（{max_iterations}），输出最终文档"
            logger.info(f"达到最大迭代次数（{max_iterations}），结束迭代")
        
        return state
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}", exc_info=True)
        state["current_stage"] = GenerationStage.FAILED
        state["current_step"] = f"工作流执行失败: {str(e)}"
        raise

