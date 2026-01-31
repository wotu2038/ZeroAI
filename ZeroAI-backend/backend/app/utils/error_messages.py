"""
友好错误消息工具

提供用户友好的错误提示，而不是暴露技术细节
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ErrorCode(Enum):
    """错误代码"""
    # 文档处理错误
    PARSE_FAILED = "PARSE_FAILED"
    CHUNKING_QUALITY_LOW = "CHUNKING_QUALITY_LOW"
    EXTRACTION_QUALITY_LOW = "EXTRACTION_QUALITY_LOW"
    GRAPH_QUALITY_LOW = "GRAPH_QUALITY_LOW"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_ERROR = "LLM_ERROR"
    
    # 存储错误
    NEO4J_UNAVAILABLE = "NEO4J_UNAVAILABLE"
    MILVUS_UNAVAILABLE = "MILVUS_UNAVAILABLE"
    MYSQL_UNAVAILABLE = "MYSQL_UNAVAILABLE"
    
    # 检索错误
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    RERANK_FAILED = "RERANK_FAILED"
    
    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"


@dataclass
class FriendlyError:
    """友好错误"""
    code: ErrorCode
    title: str
    message: str
    suggestion: str
    technical_detail: Optional[str] = None
    recoverable: bool = True


# 错误消息映射
ERROR_MESSAGES: Dict[ErrorCode, Dict[str, str]] = {
    # 文档处理错误
    ErrorCode.PARSE_FAILED: {
        "title": "文档解析失败",
        "message": "无法解析该文档，请检查文档格式是否正确",
        "suggestion": "支持的格式：.docx、.doc。请确保文档未损坏，且不含加密内容。"
    },
    ErrorCode.CHUNKING_QUALITY_LOW: {
        "title": "分块质量不达标",
        "message": "文档结构不适合自动分块",
        "suggestion": "您可以手动选择分块策略（如按二级标题分块），或调整文档结构后重新上传。"
    },
    ErrorCode.EXTRACTION_QUALITY_LOW: {
        "title": "知识提取质量不达标",
        "message": "自动提取的知识图谱质量较低，需要人工审核",
        "suggestion": "请在「待审核」列表中查看详情并处理。"
    },
    ErrorCode.GRAPH_QUALITY_LOW: {
        "title": "图谱结构质量不达标",
        "message": "知识图谱的结构不够完整",
        "suggestion": "建议检查文档内容是否清晰，或尝试使用不同的分析模式。"
    },
    ErrorCode.LLM_TIMEOUT: {
        "title": "AI处理超时",
        "message": "文档内容较多，AI处理时间超出预期",
        "suggestion": "请稍后重试。如问题持续，可将文档拆分为多个小文档。"
    },
    ErrorCode.LLM_ERROR: {
        "title": "AI服务暂时不可用",
        "message": "无法连接到AI服务",
        "suggestion": "请稍后重试。如问题持续，请联系管理员。"
    },
    
    # 存储错误
    ErrorCode.NEO4J_UNAVAILABLE: {
        "title": "知识图谱服务暂时不可用",
        "message": "无法连接到知识图谱数据库",
        "suggestion": "请稍后重试，或联系管理员检查服务状态。"
    },
    ErrorCode.MILVUS_UNAVAILABLE: {
        "title": "向量服务暂时不可用",
        "message": "检索功能受限，仅支持关键词搜索",
        "suggestion": "语义搜索功能将在服务恢复后自动生效。"
    },
    ErrorCode.MYSQL_UNAVAILABLE: {
        "title": "数据库服务暂时不可用",
        "message": "无法连接到数据库",
        "suggestion": "请稍后重试，或联系管理员。"
    },
    
    # 检索错误
    ErrorCode.RETRIEVAL_FAILED: {
        "title": "检索失败",
        "message": "无法完成检索操作",
        "suggestion": "请检查查询内容，或稍后重试。"
    },
    ErrorCode.EMBEDDING_FAILED: {
        "title": "语义分析失败",
        "message": "无法理解查询内容",
        "suggestion": "请尝试重新表述您的问题。"
    },
    ErrorCode.RERANK_FAILED: {
        "title": "结果排序失败",
        "message": "检索结果可能未按最佳顺序排列",
        "suggestion": "结果仍可参考，但排序可能不够精准。"
    },
    
    # 通用错误
    ErrorCode.UNKNOWN_ERROR: {
        "title": "操作失败",
        "message": "发生未知错误",
        "suggestion": "请稍后重试，如问题持续请联系管理员。"
    },
    ErrorCode.VALIDATION_ERROR: {
        "title": "输入验证失败",
        "message": "输入内容不符合要求",
        "suggestion": "请检查输入内容，确保格式正确。"
    },
    ErrorCode.FILE_NOT_FOUND: {
        "title": "文件不存在",
        "message": "找不到指定的文件",
        "suggestion": "请确认文件路径正确，或重新上传文件。"
    },
    ErrorCode.PERMISSION_DENIED: {
        "title": "权限不足",
        "message": "您没有权限执行此操作",
        "suggestion": "请联系管理员获取相应权限。"
    },
}


def get_friendly_error(
    code: ErrorCode,
    technical_detail: str = None
) -> FriendlyError:
    """
    获取友好的错误信息
    
    Args:
        code: 错误代码
        technical_detail: 技术细节（仅用于日志，不展示给用户）
        
    Returns:
        FriendlyError: 友好错误对象
    """
    error_info = ERROR_MESSAGES.get(code, ERROR_MESSAGES[ErrorCode.UNKNOWN_ERROR])
    
    return FriendlyError(
        code=code,
        title=error_info["title"],
        message=error_info["message"],
        suggestion=error_info["suggestion"],
        technical_detail=technical_detail,
        recoverable=code not in [
            ErrorCode.PERMISSION_DENIED,
            ErrorCode.PARSE_FAILED
        ]
    )


def create_error_response(
    code: ErrorCode,
    technical_detail: str = None,
    include_detail: bool = False
) -> Dict[str, Any]:
    """
    创建错误响应（用于 API 返回）
    
    Args:
        code: 错误代码
        technical_detail: 技术细节
        include_detail: 是否包含技术细节（仅调试模式）
        
    Returns:
        错误响应字典
    """
    error = get_friendly_error(code, technical_detail)
    
    response = {
        "success": False,
        "error": {
            "code": error.code.value,
            "title": error.title,
            "message": error.message,
            "suggestion": error.suggestion,
            "recoverable": error.recoverable
        }
    }
    
    if include_detail and error.technical_detail:
        response["error"]["detail"] = error.technical_detail
    
    return response


def classify_exception(exception: Exception) -> ErrorCode:
    """
    根据异常类型分类错误代码
    
    Args:
        exception: 异常对象
        
    Returns:
        对应的错误代码
    """
    error_message = str(exception).lower()
    exception_type = type(exception).__name__
    
    # 超时相关
    if "timeout" in error_message or "timed out" in error_message:
        return ErrorCode.LLM_TIMEOUT
    
    # LLM 相关
    if "openai" in error_message or "llm" in error_message:
        return ErrorCode.LLM_ERROR
    
    # 数据库相关
    if "neo4j" in error_message or "bolt" in error_message:
        return ErrorCode.NEO4J_UNAVAILABLE
    
    if "milvus" in error_message:
        return ErrorCode.MILVUS_UNAVAILABLE
    
    if "mysql" in error_message or "sqlalchemy" in error_message:
        return ErrorCode.MYSQL_UNAVAILABLE
    
    # 文件相关
    if "not found" in error_message or "filenotfound" in exception_type.lower():
        return ErrorCode.FILE_NOT_FOUND
    
    if "permission" in error_message:
        return ErrorCode.PERMISSION_DENIED
    
    # 验证相关
    if "validation" in error_message or "invalid" in error_message:
        return ErrorCode.VALIDATION_ERROR
    
    return ErrorCode.UNKNOWN_ERROR

