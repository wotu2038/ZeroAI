"""
知识库服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, desc
from typing import List, Optional, Tuple
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember, KnowledgeBaseVisibility, MemberRole
import logging

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """知识库服务类"""
    
    @staticmethod
    def create_knowledge_base(
        db: Session,
        name: str,
        creator_name: str,
        description: Optional[str] = None,
        visibility: str = "private"
    ) -> KnowledgeBase:
        """
        创建知识库
        
        Args:
            db: 数据库会话
            name: 知识库名称
            creator_name: 创建者名称
            description: 描述
            visibility: 可见性（private/shared）
        
        Returns:
            KnowledgeBase: 创建的知识库对象
        """
        # 创建知识库
        kb = KnowledgeBase(
            name=name,
            description=description,
            creator_name=creator_name,
            visibility=KnowledgeBaseVisibility.PRIVATE if visibility == "private" else KnowledgeBaseVisibility.SHARED,
            member_count=1
        )
        db.add(kb)
        db.flush()  # 获取ID
        
        # 添加创建者为owner
        member = KnowledgeBaseMember(
            knowledge_base_id=kb.id,
            member_name=creator_name,
            role=MemberRole.OWNER
        )
        db.add(member)
        db.commit()
        db.refresh(kb)
        
        logger.info(f"知识库创建成功: ID={kb.id}, name={name}, creator={creator_name}")
        return kb
    
    @staticmethod
    def get_knowledge_base(db: Session, kb_id: int) -> Optional[KnowledgeBase]:
        """获取知识库详情"""
        return db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    
    @staticmethod
    def get_knowledge_bases_by_creator(
        db: Session,
        creator_name: str
    ) -> List[KnowledgeBase]:
        """获取创建者创建的知识库列表"""
        return db.query(KnowledgeBase).filter(
            KnowledgeBase.creator_name == creator_name
        ).order_by(KnowledgeBase.created_at.desc()).all()
    
    @staticmethod
    def get_shared_knowledge_bases(
        db: Session,
        exclude_creator: Optional[str] = None
    ) -> List[KnowledgeBase]:
        """
        获取共享知识库列表
        
        Args:
            db: 数据库会话
            exclude_creator: 排除的创建者（用于获取别人创建的共享知识库）
        """
        query = db.query(KnowledgeBase).filter(
            KnowledgeBase.visibility == KnowledgeBaseVisibility.SHARED
        )
        
        if exclude_creator:
            query = query.filter(KnowledgeBase.creator_name != exclude_creator)
        
        return query.order_by(KnowledgeBase.created_at.desc()).all()
    
    @staticmethod
    def get_joined_knowledge_bases(
        db: Session,
        member_name: str
    ) -> List[KnowledgeBase]:
        """获取成员加入的知识库列表（不包括自己创建的，只返回共享知识库）"""
        # 获取成员加入的知识库ID列表
        member_kb_ids = db.query(KnowledgeBaseMember.knowledge_base_id).filter(
            and_(
                KnowledgeBaseMember.member_name == member_name,
                KnowledgeBaseMember.role != MemberRole.OWNER
            )
        ).subquery()
        
        # 查询知识库（只返回共享知识库）
        return db.query(KnowledgeBase).filter(
            and_(
                KnowledgeBase.id.in_(member_kb_ids),
                KnowledgeBase.visibility == KnowledgeBaseVisibility.SHARED
            )
        ).order_by(KnowledgeBase.created_at.desc()).all()
    
    @staticmethod
    def update_knowledge_base(
        db: Session,
        kb_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[str] = None
    ) -> Optional[KnowledgeBase]:
        """更新知识库"""
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            return None
        
        # 记录之前的visibility状态
        old_visibility = kb.visibility
        
        if name is not None:
            kb.name = name
        if description is not None:
            kb.description = description
        if visibility is not None:
            new_visibility = KnowledgeBaseVisibility.PRIVATE if visibility == "private" else KnowledgeBaseVisibility.SHARED
            
            # 如果从共享改为个人，删除所有非创建者成员
            if old_visibility == KnowledgeBaseVisibility.SHARED and new_visibility == KnowledgeBaseVisibility.PRIVATE:
                # 删除所有非创建者成员
                deleted_count = db.query(KnowledgeBaseMember).filter(
                    and_(
                        KnowledgeBaseMember.knowledge_base_id == kb_id,
                        KnowledgeBaseMember.role != MemberRole.OWNER
                    )
                ).delete()
                
                # 更新成员数量（只保留创建者）
                kb.member_count = 1
                
                logger.info(f"知识库从共享改为个人，已删除 {deleted_count} 个非创建者成员: kb_id={kb_id}")
            
            kb.visibility = new_visibility
        
        db.commit()
        db.refresh(kb)
        
        logger.info(f"知识库更新成功: ID={kb_id}")
        return kb
    
    @staticmethod
    def delete_knowledge_base(db: Session, kb_id: int) -> bool:
        """删除知识库"""
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            return False
        
        db.delete(kb)
        db.commit()
        
        logger.info(f"知识库删除成功: ID={kb_id}")
        return True
    
    @staticmethod
    def check_member_permission(
        db: Session,
        kb_id: int,
        member_name: str,
        required_role: Optional[MemberRole] = None
    ) -> tuple[bool, Optional[MemberRole]]:
        """
        检查成员权限
        
        Returns:
            (has_permission, member_role): 是否有权限，成员角色
        """
        member = db.query(KnowledgeBaseMember).filter(
            and_(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.member_name == member_name
            )
        ).first()
        
        if not member:
            return False, None
        
        # 如果是owner，拥有所有权限
        if member.role == MemberRole.OWNER:
            return True, member.role
        
        # 检查是否需要特定角色
        if required_role:
            role_hierarchy = {
                MemberRole.OWNER: 4,
                MemberRole.ADMIN: 3,
                MemberRole.EDITOR: 2,
                MemberRole.VIEWER: 1
            }
            return role_hierarchy.get(member.role, 0) >= role_hierarchy.get(required_role, 0), member.role
        
        return True, member.role
    
    @staticmethod
    def add_member(
        db: Session,
        kb_id: int,
        member_name: str,
        role: str = "viewer"
    ) -> Optional[KnowledgeBaseMember]:
        """添加成员"""
        # 检查是否已存在
        existing = db.query(KnowledgeBaseMember).filter(
            and_(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.member_name == member_name
            )
        ).first()
        
        if existing:
            return None  # 已存在
        
        # 添加成员
        member = KnowledgeBaseMember(
            knowledge_base_id=kb_id,
            member_name=member_name,
            role=MemberRole.OWNER if role == "owner" else
                 MemberRole.ADMIN if role == "admin" else
                 MemberRole.EDITOR if role == "editor" else
                 MemberRole.VIEWER
        )
        db.add(member)
        
        # 更新成员数量
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if kb:
            kb.member_count += 1
        
        db.commit()
        db.refresh(member)
        
        logger.info(f"成员添加成功: kb_id={kb_id}, member={member_name}")
        return member
    
    @staticmethod
    def remove_member(
        db: Session,
        kb_id: int,
        member_name: str
    ) -> bool:
        """移除成员"""
        member = db.query(KnowledgeBaseMember).filter(
            and_(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.member_name == member_name
            )
        ).first()
        
        if not member:
            return False
        
        # 不能移除owner
        if member.role == MemberRole.OWNER:
            return False
        
        db.delete(member)
        
        # 更新成员数量
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if kb:
            kb.member_count -= 1
        
        db.commit()
        
        logger.info(f"成员移除成功: kb_id={kb_id}, member={member_name}")
        return True
    
    @staticmethod
    def get_members(
        db: Session,
        kb_id: int
    ) -> List[KnowledgeBaseMember]:
        """获取知识库成员列表"""
        return db.query(KnowledgeBaseMember).filter(
            KnowledgeBaseMember.knowledge_base_id == kb_id
        ).order_by(KnowledgeBaseMember.joined_at.asc()).all()
    
    @staticmethod
    def join_knowledge_base(
        db: Session,
        kb_id: int,
        member_name: str
    ) -> Optional[KnowledgeBaseMember]:
        """加入知识库"""
        # 检查知识库是否存在且为共享
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb or kb.visibility != KnowledgeBaseVisibility.SHARED:
            return None
        
        # 检查是否已加入
        existing = db.query(KnowledgeBaseMember).filter(
            and_(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.member_name == member_name
            )
        ).first()
        
        if existing:
            return existing  # 已加入
        
        # 加入知识库
        return KnowledgeBaseService.add_member(db, kb_id, member_name, "viewer")
    
    @staticmethod
    def share_to_all_users(
        db: Session,
        kb_id: int,
        default_role: str = "viewer"
    ) -> dict:
        """
        一键共享：将所有激活用户添加为知识库成员
        
        Args:
            db: 数据库会话
            kb_id: 知识库ID
            default_role: 默认成员角色（默认：viewer）
        
        Returns:
            dict: 统计信息 {"success_count": int, "skipped_count": int, "total_users": int}
        """
        from app.models.user import User
        
        # 检查知识库是否存在且为共享
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise ValueError("知识库不存在")
        if kb.visibility != KnowledgeBaseVisibility.SHARED:
            raise ValueError("只有共享知识库可以使用一键共享功能")
        
        # 获取所有激活用户
        active_users = db.query(User).filter(User.is_active == True).all()
        total_users = len(active_users)
        
        success_count = 0
        skipped_count = 0
        
        # 批量添加成员
        for user in active_users:
            # 检查是否已存在
            existing = db.query(KnowledgeBaseMember).filter(
                and_(
                    KnowledgeBaseMember.knowledge_base_id == kb_id,
                    KnowledgeBaseMember.member_name == user.username
                )
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # 添加成员
            try:
                KnowledgeBaseService.add_member(db, kb_id, user.username, default_role)
                success_count += 1
            except Exception as e:
                logger.warning(f"添加用户 {user.username} 为成员失败: {e}")
                skipped_count += 1
        
        # 更新知识库的成员数量
        kb.member_count = db.query(KnowledgeBaseMember).filter(
            KnowledgeBaseMember.knowledge_base_id == kb_id
        ).count()
        db.commit()
        
        return {
            "success_count": success_count,
            "skipped_count": skipped_count,
            "total_users": total_users
        }
    
    @staticmethod
    def leave_knowledge_base(
        db: Session,
        kb_id: int,
        member_name: str
    ) -> bool:
        """
        退出知识库
        
        Args:
            db: 数据库会话
            kb_id: 知识库ID
            member_name: 成员名称
        
        Returns:
            bool: 是否成功退出
        """
        # 查找成员
        member = db.query(KnowledgeBaseMember).filter(
            and_(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.member_name == member_name
            )
        ).first()
        
        if not member:
            return False  # 不是成员
        
        # 不能退出创建者的身份
        if member.role == MemberRole.OWNER:
            return False  # 创建者不能退出
        
        # 移除成员
        db.delete(member)
        
        # 更新成员数量
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if kb:
            kb.member_count -= 1
        
        db.commit()
        
        logger.info(f"成员退出知识库成功: kb_id={kb_id}, member={member_name}")
        return True
    
    @staticmethod
    def discover_knowledge_bases(
        db: Session,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        username: Optional[str] = None
    ) -> Tuple[List[KnowledgeBase], int]:
        """
        发现知识库（搜索、分类筛选、综合排序）
        
        Args:
            db: 数据库会话
            keyword: 搜索关键词（搜索名称和描述）
            category: 分类筛选
            page: 页码
            page_size: 每页数量
            username: 当前用户名（用于排除已创建的知识库）
        
        Returns:
            (知识库列表, 总数)
        """
        # 只查询共享知识库（包括当前用户创建的）
        query = db.query(KnowledgeBase).filter(
            KnowledgeBase.visibility == KnowledgeBaseVisibility.SHARED
        )
        
        # 关键词搜索（名称或描述）
        if keyword:
            keyword_pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    KnowledgeBase.name.like(keyword_pattern),
                    KnowledgeBase.description.like(keyword_pattern)
                )
            )
        
        # 分类筛选
        if category:
            query = query.filter(KnowledgeBase.category == category)
        
        # 获取总数
        total = query.count()
        
        # 综合排序：成员数、内容数、更新时间
        # 排序公式：(member_count * 0.4 + document_count * 0.3 + 最近更新加分) * 权重
        # 简化：先按成员数降序，再按内容数降序，最后按更新时间降序
        query = query.order_by(
            desc(KnowledgeBase.member_count),
            desc(KnowledgeBase.document_count),
            desc(KnowledgeBase.last_updated_at),
            desc(KnowledgeBase.created_at)
        )
        
        # 分页
        offset = (page - 1) * page_size
        knowledge_bases = query.offset(offset).limit(page_size).all()
        
        return knowledge_bases, total

