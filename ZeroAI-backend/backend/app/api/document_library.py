"""
文档库 API 路由

提供文档库的 RESTful API
"""
import os
import uuid
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.mysql_client import get_db
from app.services.document_library_service import DocumentLibraryService
from app.models.document_library import DocumentLibraryStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/document-library", tags=["文档库"])


# ==================== 请求/响应模型 ====================

class FolderCreate(BaseModel):
    """创建文件夹请求"""
    name: str
    parent_id: Optional[int] = None
    description: Optional[str] = None


class FolderUpdate(BaseModel):
    """更新文件夹请求"""
    name: Optional[str] = None
    description: Optional[str] = None


class DocumentUpdate(BaseModel):
    """更新文档请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    folder_id: Optional[int] = None
    tags: Optional[str] = None


class KnowledgeBaseAssociation(BaseModel):
    """知识库关联请求"""
    knowledge_base_id: int


class ApiResponse(BaseModel):
    """通用 API 响应"""
    success: bool
    message: str = ""
    data: Optional[dict] = None


# ==================== 文件夹 API ====================

@router.post("/folders", response_model=ApiResponse)
async def create_folder(request: FolderCreate, db: Session = Depends(get_db)):
    """创建文件夹"""
    try:
        folder = DocumentLibraryService.create_folder(
            name=request.name,
            parent_id=request.parent_id,
            description=request.description,
            db=db
        )
        return ApiResponse(
            success=True,
            message="文件夹创建成功",
            data=folder.to_dict()
        )
    except Exception as e:
        logger.error(f"创建文件夹失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/folders/tree")
async def get_folder_tree(db: Session = Depends(get_db)):
    """获取文件夹树结构"""
    tree = DocumentLibraryService.get_folder_tree(db=db)
    return {
        "success": True,
        "data": tree
    }


@router.delete("/folders/{folder_id}", response_model=ApiResponse)
async def delete_folder(folder_id: int, db: Session = Depends(get_db)):
    """删除文件夹"""
    try:
        result = DocumentLibraryService.delete_folder(folder_id, db=db)
        if result:
            return ApiResponse(success=True, message="文件夹删除成功")
        else:
            raise HTTPException(status_code=404, detail="文件夹不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"删除文件夹失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 文档 API ====================

@router.post("/documents/upload", response_model=ApiResponse)
async def upload_document(
    file: UploadFile = File(...),
    folder_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    上传文档到文档库
    
    支持的格式：.docx, .doc, .pdf
    """
    try:
        # 验证文件类型
        allowed_extensions = {".docx", ".doc", ".pdf"}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}"
            )
        
        # 生成唯一文件名
        unique_name = f"{uuid.uuid4().hex}{file_ext}"
        
        # 保存文件
        upload_dir = os.path.join("uploads", "document_library")
        os.makedirs(os.path.join("/app", upload_dir), exist_ok=True)
        
        file_path = os.path.join(upload_dir, unique_name)
        abs_path = os.path.join("/app", file_path)
        
        content = await file.read()
        with open(abs_path, "wb") as f:
            f.write(content)
        
        # 创建文档记录
        document = DocumentLibraryService.upload_document(
            file_name=unique_name,
            original_name=file.filename,
            file_path=file_path,
            file_size=len(content),
            file_type=file_ext[1:],  # 去掉点
            folder_id=folder_id,
            db=db
        )
        
        return ApiResponse(
            success=True,
            message="文档上传成功",
            data=document.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def get_documents(
    folder_id: Optional[int] = Query(None, description="文件夹ID"),
    status: Optional[str] = Query(None, description="状态筛选"),
    knowledge_base_id: Optional[int] = Query(None, description="知识库ID"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取文档列表"""
    documents, total = DocumentLibraryService.get_documents(
        folder_id=folder_id,
        status=status,
        knowledge_base_id=knowledge_base_id,
        search=search,
        page=page,
        page_size=page_size,
        db=db
    )
    
    return {
        "success": True,
        "data": {
            "items": [doc.to_dict(include_knowledge_bases=True) for doc in documents],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.get("/documents/unassigned")
async def get_unassigned_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取未分配的文档"""
    documents, total = DocumentLibraryService.get_unassigned_documents(
        page=page,
        page_size=page_size,
        db=db
    )
    
    return {
        "success": True,
        "data": {
            "items": [doc.to_dict() for doc in documents],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@router.get("/documents/{document_id}")
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """获取单个文档详情"""
    document = DocumentLibraryService.get_document(document_id, db=db)
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return {
        "success": True,
        "data": document.to_dict(include_knowledge_bases=True)
    }


@router.put("/documents/{document_id}", response_model=ApiResponse)
async def update_document(
    document_id: int,
    request: DocumentUpdate,
    db: Session = Depends(get_db)
):
    """更新文档信息"""
    document = DocumentLibraryService.update_document(
        document_id=document_id,
        title=request.title,
        description=request.description,
        folder_id=request.folder_id,
        tags=request.tags,
        db=db
    )
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return ApiResponse(
        success=True,
        message="文档更新成功",
        data=document.to_dict()
    )


@router.delete("/documents/{document_id}", response_model=ApiResponse)
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """删除文档"""
    result = DocumentLibraryService.delete_document(document_id, db=db)
    
    if not result:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return ApiResponse(success=True, message="文档删除成功")


@router.get("/documents/{document_id}/download")
async def download_document(document_id: int, db: Session = Depends(get_db)):
    """下载文档"""
    document = DocumentLibraryService.get_document(document_id, db=db)
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    abs_path = document.file_path if os.path.isabs(document.file_path) \
        else os.path.join("/app", document.file_path)
    
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        path=abs_path,
        filename=document.original_name,
        media_type="application/octet-stream"
    )


# ==================== 知识库关联 API ====================

@router.post("/documents/{document_id}/knowledge-bases", response_model=ApiResponse)
async def add_to_knowledge_base(
    document_id: int,
    request: KnowledgeBaseAssociation,
    db: Session = Depends(get_db)
):
    """将文档添加到知识库"""
    result = DocumentLibraryService.add_to_knowledge_base(
        document_id=document_id,
        knowledge_base_id=request.knowledge_base_id,
        db=db
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="文档或知识库不存在")
    
    return ApiResponse(success=True, message="文档已添加到知识库")


@router.delete("/documents/{document_id}/knowledge-bases/{knowledge_base_id}", response_model=ApiResponse)
async def remove_from_knowledge_base(
    document_id: int,
    knowledge_base_id: int,
    db: Session = Depends(get_db)
):
    """从知识库移除文档"""
    result = DocumentLibraryService.remove_from_knowledge_base(
        document_id=document_id,
        knowledge_base_id=knowledge_base_id,
        db=db
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="文档或知识库不存在")
    
    return ApiResponse(success=True, message="文档已从知识库移除")


# ==================== 统计 API ====================

@router.get("/statistics")
async def get_statistics(db: Session = Depends(get_db)):
    """获取文档库统计信息"""
    stats = DocumentLibraryService.get_statistics(db=db)
    
    return {
        "success": True,
        "data": stats
    }

