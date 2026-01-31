"""
知识库管理API
"""
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Body
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import os
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.mysql_client import get_db
from app.core.auth import get_current_user, get_current_admin_user
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember, MemberRole, document_knowledge_base_association
from app.models.document_upload import DocumentUpload, DocumentStatus
from app.models.document_library import DocumentLibrary
from app.models.task_queue import TaskQueue, TaskStatus, TaskType
from app.services.knowledge_base_service import KnowledgeBaseService
from app.tasks.enhanced_document_processing import process_document_enhanced_task
from app.models.schemas import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseMemberResponse,
    KnowledgeBaseMemberListResponse,
    AddMemberRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库管理"])


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    request: KnowledgeBaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建知识库"""
    try:
        kb = KnowledgeBaseService.create_knowledge_base(
            db=db,
            name=request.name,
            creator_name=current_user.username,  # 使用当前登录用户
            description=request.description,
            visibility=request.visibility
        )
        return KnowledgeBaseResponse(**kb.to_dict())
    except Exception as e:
        logger.error(f"创建知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建知识库失败: {str(e)}")


@router.get("/discover", response_model=KnowledgeBaseListResponse)
async def discover_knowledge_bases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词（搜索名称和描述）"),
    category: Optional[str] = Query(None, description="分类筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发现知识库（搜索、分类筛选、综合排序）"""
    try:
        knowledge_bases, total = KnowledgeBaseService.discover_knowledge_bases(
            db=db,
            keyword=keyword,
            category=category,
            page=page,
            page_size=page_size,
            username=current_user.username
        )
        
        # 为每个知识库添加当前用户的成员信息
        kb_responses = []
        for kb in knowledge_bases:
            kb_dict = kb.to_dict()
            # 检查当前用户是否是成员
            has_permission, role = KnowledgeBaseService.check_member_permission(
                db, kb.id, current_user.username
            )
            kb_dict["is_member"] = has_permission
            kb_dict["user_role"] = role.value if role else None
            kb_responses.append(KnowledgeBaseResponse(**kb_dict))
        
        return KnowledgeBaseListResponse(
            knowledge_bases=kb_responses,
            total=total
        )
    except Exception as e:
        logger.error(f"发现知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发现知识库失败: {str(e)}")


@router.post("/{kb_id}/share-to-all")
async def share_knowledge_base_to_all(
    kb_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """一键共享：将所有激活用户添加为知识库成员（仅Admin）"""
    try:
        result = KnowledgeBaseService.share_to_all_users(
            db=db,
            kb_id=kb_id,
            default_role="viewer"
        )
        
        return {
            "message": "一键共享成功",
            "success_count": result["success_count"],
            "skipped_count": result["skipped_count"],
            "total_users": result["total_users"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"一键共享失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"一键共享失败: {str(e)}")


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db)
):
    """获取知识库详情"""
    kb = KnowledgeBaseService.get_knowledge_base(db, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return KnowledgeBaseResponse(**kb.to_dict())


@router.get("", response_model=KnowledgeBaseListResponse)
async def get_knowledge_bases(
    filter_type: Optional[str] = Query(None, description="筛选类型：my_created（我创建的）/my_joined（我加入的）/shared（共享知识库）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取知识库列表"""
    try:
        knowledge_bases = []
        username = current_user.username
        
        if filter_type == "my_created":
            # 获取我创建的
            knowledge_bases = KnowledgeBaseService.get_knowledge_bases_by_creator(db, username)
        elif filter_type == "my_joined":
            # 获取我加入的
            knowledge_bases = KnowledgeBaseService.get_joined_knowledge_bases(db, username)
        elif filter_type == "shared":
            # 获取共享知识库（排除我创建的）
            knowledge_bases = KnowledgeBaseService.get_shared_knowledge_bases(db, exclude_creator=username)
        else:
            # 默认：获取我创建的 + 我加入的 + 共享的（排除我创建的）
            created = KnowledgeBaseService.get_knowledge_bases_by_creator(db, username)
            joined = KnowledgeBaseService.get_joined_knowledge_bases(db, username)
            shared = KnowledgeBaseService.get_shared_knowledge_bases(db, exclude_creator=username)
            # 合并并去重
            kb_ids = set()
            knowledge_bases = []
            for kb in created + joined + shared:
                if kb.id not in kb_ids:
                    kb_ids.add(kb.id)
                    knowledge_bases.append(kb)
        
        # 为每个知识库添加当前用户的成员信息
        kb_responses = []
        for kb in knowledge_bases:
            kb_dict = kb.to_dict()
            # 检查当前用户是否是成员
            has_permission, role = KnowledgeBaseService.check_member_permission(
                db, kb.id, username
            )
            kb_dict["is_member"] = has_permission
            kb_dict["user_role"] = role.value if role else None
            kb_responses.append(KnowledgeBaseResponse(**kb_dict))
        
        return KnowledgeBaseListResponse(
            knowledge_bases=kb_responses,
            total=len(kb_responses)
        )
    except Exception as e:
        logger.error(f"获取知识库列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取知识库列表失败: {str(e)}")


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: int,
    request: KnowledgeBaseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新知识库（仅创建者）"""
    # 检查权限
    has_permission, role = KnowledgeBaseService.check_member_permission(
        db, kb_id, current_user.username, MemberRole.OWNER
    )
    if not has_permission or role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="只有创建者可以编辑知识库")
    
    try:
        kb = KnowledgeBaseService.update_knowledge_base(
            db=db,
            kb_id=kb_id,
            name=request.name,
            description=request.description,
            visibility=request.visibility
        )
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        return KnowledgeBaseResponse(**kb.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新知识库失败: {str(e)}")


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除知识库（仅创建者）"""
    # 检查权限
    has_permission, role = KnowledgeBaseService.check_member_permission(
        db, kb_id, current_user.username, MemberRole.OWNER
    )
    if not has_permission or role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="只有创建者可以删除知识库")
    
    try:
        success = KnowledgeBaseService.delete_knowledge_base(db, kb_id)
        if not success:
            raise HTTPException(status_code=404, detail="知识库不存在")
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除知识库失败: {str(e)}")


@router.get("/{kb_id}/members", response_model=KnowledgeBaseMemberListResponse)
async def get_members(
    kb_id: int,
    db: Session = Depends(get_db)
):
    """获取知识库成员列表"""
    try:
        members = KnowledgeBaseService.get_members(db, kb_id)
        return KnowledgeBaseMemberListResponse(
            members=[KnowledgeBaseMemberResponse(**m.to_dict()) for m in members]
        )
    except Exception as e:
        logger.error(f"获取成员列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取成员列表失败: {str(e)}")


@router.post("/{kb_id}/members", response_model=KnowledgeBaseMemberResponse)
async def add_member(
    kb_id: int,
    request: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加成员（仅创建者）"""
    # 检查权限
    has_permission, role = KnowledgeBaseService.check_member_permission(
        db, kb_id, current_user.username, MemberRole.OWNER
    )
    if not has_permission or role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="只有创建者可以添加成员")
    
    try:
        member = KnowledgeBaseService.add_member(
            db=db,
            kb_id=kb_id,
            member_name=request.member_name,
            role=request.role
        )
        if not member:
            raise HTTPException(status_code=400, detail="成员已存在")
        return KnowledgeBaseMemberResponse(**member.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加成员失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"添加成员失败: {str(e)}")


@router.delete("/{kb_id}/members/{member_name}")
async def remove_member(
    kb_id: int,
    member_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移除成员（仅创建者）"""
    # 检查权限
    has_permission, role = KnowledgeBaseService.check_member_permission(
        db, kb_id, current_user.username, MemberRole.OWNER
    )
    if not has_permission or role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="只有创建者可以移除成员")
    
    try:
        success = KnowledgeBaseService.remove_member(db, kb_id, member_name)
        if not success:
            raise HTTPException(status_code=400, detail="移除成员失败（成员不存在或不能移除创建者）")
        return {"message": "移除成员成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除成员失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"移除成员失败: {str(e)}")


@router.post("/{kb_id}/join", response_model=KnowledgeBaseMemberResponse)
async def join_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """加入知识库（仅共享知识库）"""
    try:
        member = KnowledgeBaseService.join_knowledge_base(
            db=db,
            kb_id=kb_id,
            member_name=current_user.username  # 使用当前登录用户
        )
        if not member:
            raise HTTPException(status_code=400, detail="加入失败（知识库不存在、不是共享知识库或已加入）")
        return KnowledgeBaseMemberResponse(**member.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加入知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"加入知识库失败: {str(e)}")


@router.post("/{kb_id}/leave")
async def leave_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """退出知识库"""
    try:
        success = KnowledgeBaseService.leave_knowledge_base(
            db=db,
            kb_id=kb_id,
            member_name=current_user.username
        )
        if not success:
            raise HTTPException(status_code=400, detail="退出失败（不是成员或不能退出创建者身份）")
        return {"message": "退出成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"退出知识库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"退出知识库失败: {str(e)}")


class DocumentUploadAndProcessRequest(BaseModel):
    """文档上传和处理请求"""
    chunk_strategy: str = Field("level_1", description="分块策略：level_1, level_2, level_3, level_4, level_5, fixed_token, no_split")
    max_tokens_per_section: int = Field(8000, ge=1000, le=20000, description="每个章节的最大token数")
    analysis_mode: str = Field("smart_segment", description="模板生成方案：smart_segment, full_chunk")
    provider: str = Field("local", description="LLM提供商")
    use_thinking: bool = Field(False, description="是否启用Thinking模式")


class DocumentUploadAndProcessResponse(BaseModel):
    """文档上传和处理响应"""
    task_id: str = Field(..., description="任务ID（用于追踪整个流程）")
    document_id: int = Field(..., description="文档ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="消息")


class AddDocumentsFromLibraryRequest(BaseModel):
    """从文档库添加文档到知识库的请求"""
    document_library_ids: List[int] = Field(..., description="文档库文档ID列表")
    chunk_strategy: str = Field("auto", description="分块策略")
    max_tokens_per_section: int = Field(8000, ge=1000, le=20000, description="每个章节的最大token数")
    analysis_mode: str = Field("smart_segment", description="模板生成方案：smart_segment, full_chunk")
    provider: str = Field("local", description="LLM提供商")
    use_thinking: bool = Field(False, description="是否启用Thinking模式")


class AddDocumentsFromLibraryResponse(BaseModel):
    """从文档库添加文档的响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    tasks: List[dict] = Field(default_factory=list, description="创建的任务列表")


@router.post("/{kb_id}/documents/add-from-library", response_model=AddDocumentsFromLibraryResponse)
async def add_documents_from_library(
    kb_id: int,
    request: AddDocumentsFromLibraryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    从文档库添加文档到知识库并自动处理
    
    流程：
    1. 从文档库读取文档信息
    2. 创建 DocumentUpload 记录（复制文件路径）
    3. 建立 DocumentLibrary ↔ KnowledgeBase 关联
    4. 启动处理任务
    """
    try:
        # 验证知识库存在性和权限
        kb = KnowledgeBaseService.get_knowledge_base(db, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        
        # 检查用户权限（必须是成员）
        has_permission, role = KnowledgeBaseService.check_member_permission(
            db, kb_id, current_user.username
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="您没有权限向此知识库添加文档")
        
        # 验证文档库文档是否存在
        library_documents = db.query(DocumentLibrary).filter(
            DocumentLibrary.id.in_(request.document_library_ids)
        ).all()
        
        if len(library_documents) != len(request.document_library_ids):
            found_ids = {doc.id for doc in library_documents}
            missing_ids = set(request.document_library_ids) - found_ids
            raise HTTPException(status_code=404, detail=f"文档库文档不存在: {missing_ids}")
        
        # 验证文件格式（只支持 .docx）
        invalid_docs = [doc for doc in library_documents if doc.file_type != "docx"]
        if invalid_docs:
            invalid_names = [doc.original_name for doc in invalid_docs]
            raise HTTPException(status_code=400, detail=f"以下文档不支持（只支持 .docx 格式）: {', '.join(invalid_names)}")
        
        # 验证分块策略
        valid_strategies = ["auto", "level_1", "level_2", "level_3", "level_4", "level_5", "fixed_token", "no_split"]
        if request.chunk_strategy not in valid_strategies:
            raise HTTPException(status_code=400, detail=f"无效的分块策略: {request.chunk_strategy}")
        
        # 验证模板生成方案
        if request.analysis_mode not in ["smart_segment", "full_chunk"]:
            raise HTTPException(status_code=400, detail=f"无效的模板生成方案: {request.analysis_mode}")
        
        created_tasks = []
        
        # 为每个文档创建 DocumentUpload 记录并启动处理任务
        for library_doc in library_documents:
            # 检查文件是否存在
            if not os.path.isabs(library_doc.file_path):
                file_path_abs = os.path.join("/app", library_doc.file_path)
            else:
                file_path_abs = library_doc.file_path
            
            if not os.path.exists(file_path_abs):
                logger.warning(f"文档库文件不存在，跳过: {library_doc.file_path}")
                continue
            
            # 创建 DocumentUpload 记录（复制文件路径）
            db_document = DocumentUpload(
                file_name=library_doc.original_name,  # 使用原始文件名
                file_size=library_doc.file_size,
                file_path=library_doc.file_path,  # 直接复制文件路径
                file_extension=f".{library_doc.file_type}",
                status=DocumentStatus.VALIDATED,
                knowledge_base_id=kb_id,
                library_document_id=library_doc.id,  # 关联文档库文档
                chunk_strategy=request.chunk_strategy,
                max_tokens_per_section=request.max_tokens_per_section,
                analysis_mode=request.analysis_mode
            )
            db.add(db_document)
            db.flush()  # 获取 ID
            
            logger.info(f"创建 DocumentUpload 记录: ID={db_document.id}, Library_ID={library_doc.id}, KB_ID={kb_id}")
            
            # 建立 DocumentLibrary ↔ KnowledgeBase 关联
            # 检查关联是否已存在
            from sqlalchemy import select, insert
            existing_association = db.execute(
                select(document_knowledge_base_association).where(
                    document_knowledge_base_association.c.document_id == library_doc.id,
                    document_knowledge_base_association.c.knowledge_base_id == kb_id
                )
            ).first()
            
            if not existing_association:
                db.execute(
                    insert(document_knowledge_base_association).values(
                        document_id=library_doc.id,
                        knowledge_base_id=kb_id
                    )
                )
                logger.info(f"建立文档库-知识库关联: Document_ID={library_doc.id}, KB_ID={kb_id}")
            
            # 更新文档库文档状态
            from app.models.document_library import DocumentLibraryStatus
            library_doc.status = DocumentLibraryStatus.ASSIGNED.value
            db.flush()
            
            # 创建Celery任务（使用增强版任务）
            celery_task = process_document_enhanced_task.delay(
                upload_id=db_document.id,
                chunk_strategy=request.chunk_strategy,
                max_tokens_per_section=request.max_tokens_per_section,
                analysis_mode=request.analysis_mode,
                provider=request.provider,
                use_thinking=request.use_thinking,
                enable_quality_gate=True,  # 启用质量门禁
                enable_concurrent=True      # 启用并发处理
            )
            
            # 创建任务记录
            task = TaskQueue(
                task_id=celery_task.id,
                upload_id=db_document.id,
                task_type=TaskType.PROCESS_DOCUMENT.value,
                status=TaskStatus.PENDING.value,
                progress=0,
                current_step="等待处理"
            )
            db.add(task)
            
            created_tasks.append({
                "task_id": celery_task.id,
                "document_id": db_document.id,
                "library_document_id": library_doc.id,
                "document_name": library_doc.original_name,
                "status": "pending"
            })
            
            logger.info(f"已创建知识库文档处理任务: task_id={celery_task.id}, upload_id={db_document.id}, library_id={library_doc.id}")
        
        db.commit()
        
        return AddDocumentsFromLibraryResponse(
            success=True,
            message=f"成功添加 {len(created_tasks)} 个文档到知识库，正在处理中...",
            tasks=created_tasks
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从文档库添加文档失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"添加文档失败: {str(e)}")


@router.post("/{kb_id}/documents/upload-and-process", response_model=DocumentUploadAndProcessResponse)
async def upload_and_process_document(
    kb_id: int,
    file: UploadFile = File(...),
    chunk_strategy: str = Query("level_1", description="分块策略"),
    max_tokens_per_section: int = Query(8000, ge=1000, le=20000, description="每个章节的最大token数"),
    analysis_mode: str = Query("smart_segment", description="模板生成方案：smart_segment, full_chunk"),
    provider: str = Query("local", description="LLM提供商"),
    use_thinking: bool = Query(False, description="是否启用Thinking模式"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传文档到知识库并自动处理（整合步骤2-5）
    
    流程：
    1. 上传文件（步骤1）
    2. 解析文档（步骤2）
    3. 分块（步骤3）
    4. LLM生成模板（步骤4）
    5. 处理文档并保存到Neo4j（步骤5）
    """
    try:
        # 验证知识库存在性和权限
        kb = KnowledgeBaseService.get_knowledge_base(db, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        
        # 检查用户权限（必须是成员）
        has_permission, role = KnowledgeBaseService.check_member_permission(
            db, kb_id, current_user.username
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="您没有权限向此知识库上传文档")
        
        # 验证文件格式
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension != ".docx":
            raise HTTPException(status_code=400, detail="只支持 .docx 格式")
        
        # 读取文件内容
        content = await file.read()
        file_size = len(content)
        
        # 验证文件大小（50MB限制）
        max_size = 50 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(status_code=400, detail=f"文件大小超过限制：最大支持 50MB，当前文件 {file_size / 1024 / 1024:.2f}MB")
        
        # 验证分块策略
        valid_strategies = ["level_1", "level_2", "level_3", "level_4", "level_5", "fixed_token", "no_split"]
        if chunk_strategy not in valid_strategies:
            raise HTTPException(status_code=400, detail=f"无效的分块策略: {chunk_strategy}")
        
        # 验证模板生成方案
        if analysis_mode not in ["smart_segment", "full_chunk"]:
            raise HTTPException(status_code=400, detail=f"无效的模板生成方案: {analysis_mode}")
        
        # 保存文件到uploads目录
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        file_name = file.filename or f"文档_{file_id}{file_extension}"
        file_path = os.path.join(upload_dir, f"{file_id}{file_extension}")
        
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"文件已保存: {file_path}, 大小: {file_size} 字节")
        
        # 保存到数据库
        db_document = DocumentUpload(
            file_name=file_name,
            file_size=file_size,
            file_path=file_path,
            file_extension=file_extension,
            status=DocumentStatus.VALIDATED,
            knowledge_base_id=kb_id,
            chunk_strategy=chunk_strategy,
            max_tokens_per_section=max_tokens_per_section,
            analysis_mode=analysis_mode
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        
        logger.info(f"文档上传记录已保存到数据库: ID={db_document.id}, KB_ID={kb_id}")
        
        # 创建Celery任务（使用增强版任务）
        celery_task = process_document_enhanced_task.delay(
            upload_id=db_document.id,
            chunk_strategy=chunk_strategy,  # 可以设置为 "auto" 使用智能分块
            max_tokens_per_section=max_tokens_per_section,
            analysis_mode=analysis_mode,
            provider=provider,
            use_thinking=use_thinking,
            enable_quality_gate=True,  # 启用质量门禁
            enable_concurrent=True      # 启用并发处理
        )
        
        # 创建任务记录
        task = TaskQueue(
            task_id=celery_task.id,
            upload_id=db_document.id,
            task_type=TaskType.PROCESS_DOCUMENT.value,
            status=TaskStatus.PENDING.value,
            progress=0,
            current_step="等待处理"
        )
        db.add(task)
        db.commit()
        
        logger.info(f"已创建知识库文档处理任务: task_id={celery_task.id}, upload_id={db_document.id}")
        
        return DocumentUploadAndProcessResponse(
            task_id=celery_task.id,
            document_id=db_document.id,
            status="pending",
            message="文档上传成功，正在处理..."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传和处理文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传和处理失败: {str(e)}")


@router.get("/{kb_id}/documents")
async def get_knowledge_base_documents(
    kb_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词（文件名）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取知识库的文档列表"""
    try:
        # 验证知识库存在性
        kb = KnowledgeBaseService.get_knowledge_base(db, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        
        # 检查用户权限（必须是成员）
        has_permission, role = KnowledgeBaseService.check_member_permission(
            db, kb_id, current_user.username
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="您没有权限查看此知识库的文档")
        
        # 查询文档
        from sqlalchemy import or_
        query = db.query(DocumentUpload).filter(DocumentUpload.knowledge_base_id == kb_id)
        
        # 搜索条件
        if search:
            query = query.filter(
                or_(
                    DocumentUpload.file_name.like(f"%{search}%"),
                    DocumentUpload.file_path.like(f"%{search}%")
                )
            )
        
        # 获取总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * page_size
        documents = query.order_by(DocumentUpload.upload_time.desc()).offset(offset).limit(page_size).all()
        
        # 转换为字典列表
        documents_list = [doc.to_dict() for doc in documents]
        
        return {
            "documents": documents_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识库文档列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.delete("/{kb_id}/documents/{document_id}")
async def delete_knowledge_base_document(
    kb_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除知识库的文档（包括Neo4j图谱数据和文件）"""
    try:
        # 验证知识库存在性
        kb = KnowledgeBaseService.get_knowledge_base(db, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        
        # 检查用户权限（必须是创建者或编辑者）
        has_permission, role = KnowledgeBaseService.check_member_permission(
            db, kb_id, current_user.username
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="您没有权限删除此知识库的文档")
        
        # 检查角色（只有owner和editor可以删除）
        if role not in [MemberRole.OWNER, MemberRole.EDITOR]:
            raise HTTPException(status_code=403, detail="只有创建者和编辑者可以删除文档")
        
        # 查询文档
        document = db.query(DocumentUpload).filter(
            DocumentUpload.id == document_id,
            DocumentUpload.knowledge_base_id == kb_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 获取文档的group_id（document_id字段）
        group_id = document.document_id
        
        # 如果文档已处理完成（有group_id），删除Neo4j中的图谱数据
        if group_id:
            from app.core.neo4j_client import neo4j_client
            
            # 统计要删除的数据
            stats_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            WITH collect(e.uuid) as episode_uuids
            
            MATCH (n:Entity)
            WHERE n.group_id = $group_id
            
            MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
            WHERE r.group_id = $group_id OR (size(episode_uuids) > 0 AND r.episode_uuid IN episode_uuids)
            
            RETURN 
              size(episode_uuids) as episode_count,
              count(DISTINCT n) as entity_count,
              count(DISTINCT r) as relationship_count
            """
            
            stats_result = neo4j_client.execute_query(stats_query, {"group_id": group_id})
            stats = stats_result[0] if stats_result else {}
            episode_count = stats.get("episode_count", 0)
            entity_count = stats.get("entity_count", 0)
            relationship_count = stats.get("relationship_count", 0)
            
            # 1. 删除所有相关的关系（先删除关系，避免约束问题）
            delete_relationships_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            WITH collect(e.uuid) as episode_uuids
            
            MATCH ()-[r:RELATES_TO|MENTIONS|CONTAINS|HAS_MEMBER]->()
            WHERE r.group_id = $group_id OR (size(episode_uuids) > 0 AND r.episode_uuid IN episode_uuids)
            DELETE r
            RETURN count(r) as deleted_count
            """
            
            neo4j_client.execute_write(delete_relationships_query, {"group_id": group_id})
            logger.info(f"已删除 {relationship_count} 个关系")
            
            # 2. 删除所有相关的Entity节点
            delete_entities_query = """
            MATCH (n:Entity)
            WHERE n.group_id = $group_id
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """
            
            neo4j_client.execute_write(delete_entities_query, {"group_id": group_id})
            logger.info(f"已删除 {entity_count} 个实体")
            
            # 3. 删除所有相关的Episode节点
            delete_episodes_query = """
            MATCH (e:Episodic)
            WHERE e.group_id = $group_id
            DETACH DELETE e
            RETURN count(e) as deleted_count
            """
            
            neo4j_client.execute_write(delete_episodes_query, {"group_id": group_id})
            logger.info(f"已删除 {episode_count} 个Episode")
            
            # 4. 删除所有相关的Community（如果group_id匹配）
            # 先统计要删除的Community数量
            count_communities_query = """
            MATCH (c:Community)
            WHERE (c.group_id = $group_id OR 
                   (c.group_id IS NOT NULL AND 
                    (toString(c.group_id) CONTAINS $group_id OR 
                     $group_id IN c.group_id)))
            RETURN count(c) as deleted_count
            """
            count_result = neo4j_client.execute_query(count_communities_query, {"group_id": group_id})
            deleted_communities = count_result[0].get("deleted_count", 0) if count_result else 0
            
            # 删除Community
            delete_communities_query = """
            MATCH (c:Community)
            WHERE (c.group_id = $group_id OR 
                   (c.group_id IS NOT NULL AND 
                    (toString(c.group_id) CONTAINS $group_id OR 
                     $group_id IN c.group_id)))
            DELETE c
            """
            neo4j_client.execute_write(delete_communities_query, {"group_id": group_id})
            logger.info(f"已删除 {deleted_communities} 个Community")
        
        # 删除文件（处理相对路径）
        if document.file_path:
            file_path_to_delete = document.file_path
            if not os.path.isabs(file_path_to_delete):
                file_path_to_delete = os.path.join("/app", file_path_to_delete)
            
            if os.path.exists(file_path_to_delete):
                try:
                    os.remove(file_path_to_delete)
                    logger.info(f"文件已删除: {file_path_to_delete}")
                except Exception as e:
                    logger.warning(f"删除文件失败: {e}")
        
        # 删除Markdown文件
        if document.parsed_content_path:
            parsed_content_file_abs = os.path.join("/app", document.parsed_content_path)
            if os.path.exists(parsed_content_file_abs):
                try:
                    os.remove(parsed_content_file_abs)
                    logger.info(f"已删除parsed_content.md文件: {parsed_content_file_abs}")
                except Exception as e:
                    logger.warning(f"删除parsed_content.md文件失败: {e}")
        
        if document.summary_content_path:
            summary_content_file_abs = os.path.join("/app", document.summary_content_path)
            if os.path.exists(summary_content_file_abs):
                try:
                    os.remove(summary_content_file_abs)
                    logger.info(f"已删除summary_content.md文件: {summary_content_file_abs}")
                except Exception as e:
                    logger.warning(f"删除summary_content.md文件失败: {e}")
        
        if document.structured_content_path:
            structured_content_file_abs = os.path.join("/app", document.structured_content_path)
            if os.path.exists(structured_content_file_abs):
                try:
                    os.remove(structured_content_file_abs)
                    logger.info(f"已删除structured_content.json文件: {structured_content_file_abs}")
                except Exception as e:
                    logger.warning(f"删除structured_content.json文件失败: {e}")
        
        # 删除解析文件目录（如果为空）
        document_id_for_content = f"upload_{document_id}"
        parsed_content_dir = os.path.join("/app", "uploads", "parsed_content", document_id_for_content)
        if os.path.exists(parsed_content_dir):
            try:
                # 检查目录是否为空
                if not os.listdir(parsed_content_dir):
                    os.rmdir(parsed_content_dir)
                    logger.info(f"已删除空目录: {parsed_content_dir}")
            except Exception as e:
                logger.warning(f"删除目录失败: {e}")
        
        # 删除数据库记录
        db.delete(document)
        db.commit()
        
        return {
            "message": "文档删除成功",
            "id": document_id,
            "deleted_neo4j": {
                "episodes": episode_count if group_id else 0,
                "entities": entity_count if group_id else 0,
                "relationships": relationship_count if group_id else 0,
                "communities": deleted_communities if group_id else 0
            } if group_id else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除知识库文档失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

