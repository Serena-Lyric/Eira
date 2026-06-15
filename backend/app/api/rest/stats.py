"""Admin dashboard stats endpoint.

Returns real counts from the database:
  - total_accounts: number of users in the users table
  - total_conversations: number of user+assistant message pairs (一问一答 = 1 turn)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, require_admin
from app.domain.identity.models import User
from app.domain.conversation.models import ChatMessage

router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


class StatsOut(BaseModel):
    total_accounts: int
    total_conversations: int


@router.get("/", response_model=StatsOut, summary="获取运营统计数据")
async def get_stats(
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_admin),
) -> StatsOut:
    # 统计已有账号数量
    accounts_result = await db.execute(select(func.count(User.id)))
    total_accounts: int = accounts_result.scalar_one()

    # 统计对话数：一问（user角色）一答（assistant角色）为一次
    # 通过统计 user 角色的消息数来代表对话次数
    user_msg_result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.role == "user")
    )
    total_conversations: int = user_msg_result.scalar_one()

    return StatsOut(
        total_accounts=total_accounts,
        total_conversations=total_conversations,
    )
