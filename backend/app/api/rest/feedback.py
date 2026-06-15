"""Feedback endpoints — user suggestions and admin reply management."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db_session, require_admin, check_write_rate_limit
from app.domain.identity.models import User
from app.domain.conversation.models import Feedback
from app.domain.conversation.repository import FeedbackRepository

router = APIRouter(prefix="/feedback", tags=["feedback"])
admin_router = APIRouter(
    prefix="/admin/dashboard/feedback", tags=["admin-feedback"]
)


# ── Schemas ──────────────────────────────────────────────────────────

class FeedbackIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="反馈内容")


class FeedbackOut(BaseModel):
    success: bool
    message: str = Field(default="反馈已提交，感谢您的建议！")
    feedback_id: int | None = Field(default=None)
    created_at: str | None = Field(default=None)


class FeedbackItem(BaseModel):
    """Admin 面板展示的反馈条目。"""
    id: int
    timestamp: str
    content: str
    replied: bool
    reply_text: str | None = None

    model_config = {"from_attributes": True}


class ReplyIn(BaseModel):
    reply_text: str = Field(min_length=1, max_length=5000)


class ReplyOut(BaseModel):
    success: bool
    message: str = "回复已保存"


def _to_feedback_item(fb: Feedback) -> FeedbackItem:
    """将 ORM 模型转为前端 FeedbackItem。"""
    ts = fb.created_at
    # 根据距今多久格式化时间戳
    now = datetime.now(timezone.utc)
    delta = now - ts
    if delta.days == 0:
        timestamp = ts.strftime("%H:%M")
    elif delta.days == 1:
        timestamp = "昨天"
    elif delta.days < 7:
        timestamp = f"{delta.days}天前"
    else:
        timestamp = ts.strftime("%m-%d")
    return FeedbackItem(
        id=fb.id,
        timestamp=timestamp,
        content=fb.content,
        replied=fb.replied,
        reply_text=fb.reply_text,
    )


# ── User endpoints ───────────────────────────────────────────────────

@router.post("", response_model=FeedbackOut, summary="提交用户反馈")
async def submit_feedback(
    req: FeedbackIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_write_rate_limit),
) -> FeedbackOut:
    """接收用户意见反馈或问题报告，持久化到数据库。

    反馈内容最大 5000 字符，需认证。
    """
    if not req.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="反馈内容不能为空",
        )

    repo = FeedbackRepository(db)
    fb = Feedback(user_id=user.id, content=req.text.strip())
    fb = await repo.create(fb)

    return FeedbackOut(
        success=True,
        message="反馈已提交，感谢您的建议！",
        feedback_id=fb.id,
        created_at=fb.created_at.isoformat(),
    )


# ── Admin endpoints ──────────────────────────────────────────────────

@admin_router.get("", response_model=list[FeedbackItem], summary="获取服务建议列表")
async def list_feedback(
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_admin),
) -> list[FeedbackItem]:
    """获取用户提交的服务建议列表，按时间倒序。

    仅管理员可访问。支持 ?limit 参数（默认 10）。
    """
    repo = FeedbackRepository(db)
    items = await repo.list_all(limit=min(limit, 100))
    return [_to_feedback_item(fb) for fb in items]


@admin_router.post(
    "/{feedback_id}/reply",
    response_model=ReplyOut,
    summary="回复服务建议",
)
async def reply_feedback(
    feedback_id: int,
    req: ReplyIn,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_admin),
) -> ReplyOut:
    """管理员回复用户提交的服务建议。

    保存回复内容，标记该反馈为已回复状态。
    """
    if not req.reply_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="回复内容不能为空",
        )

    repo = FeedbackRepository(db)
    fb = await repo.get_by_id(feedback_id)
    if fb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="反馈不存在",
        )

    await repo.update_reply(feedback_id, req.reply_text.strip())
    return ReplyOut(success=True, message="回复已保存")
