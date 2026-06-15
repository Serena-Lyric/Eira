"""Resolve the default persona prompt for chat/voice orchestrators.

Priority: persona.system_prompt > personality+scenario+first_mes build > fallback.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# 最终 fallback — 当 DB 无默认 persona 或所有字段为空时使用
DEFAULT_PERSONA_FALLBACK = (
    "你是一个友好的AI导游助手，名字叫'Eira'。请用中文回复，语气亲切自然、热情开朗。\n\n"
    "你可以在回复中插入以下动作标记来触发Live2D角色动画：\n"
    "- [wave] — 挥手（用于打招呼）\n"
    "- [nod] — 点头（用于表示同意或确认）\n"
    "- [happy] — 开心（用于表达愉快或称赞）\n"
    "- [greet] — 鞠躬欢迎\n"
    "- [surprised] — 惊讶（用于感叹或新奇事物）\n"
    "- [sad] — 难过（用于表达遗憾或安慰）\n"
    "- [think] — 思考（用于需要想一想的问题）\n"
    "- [angry] — 生气（用于表达不满或义愤）\n"
    "- [shy] — 害羞（用于被夸奖或不好意思）\n"
    "- [wink] — 眨眼（用于俏皮的回复）\n"
    "- [confused] — 困惑（用于不确定或复杂问题）\n"
    "- [tap] — 轻点身体（用于强调或提醒）\n\n"
    "动作标记应该自然地出现在对话中，不要滥用。每轮对话最多使用1-2个标记。"
)


async def get_default_persona_prompt() -> str:
    """Query the default persona from DB and build a system prompt.

    Returns:
        The persona's system_prompt if set, otherwise a prompt built from
        personality + scenario + first_mes.  Falls back to empty string if
        no default persona exists or all text fields are empty — callers
        should then use DEFAULT_PERSONA_FALLBACK.
    """
    try:
        from sqlalchemy import select
        from app.infra.db import get_session_factory
        from app.domain.persona.models import Persona

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Persona).where(
                    Persona.is_default == True,
                    Persona.scope == "public",
                    Persona.disabled == False,
                ).limit(1)
            )
            persona = result.scalar_one_or_none()
            if persona is None:
                logger.debug("persona_resolver.no_default")
                return ""

            # 优先使用显式 system_prompt
            if persona.system_prompt and persona.system_prompt.strip():
                logger.info(
                    "persona_resolver.using_system_prompt",
                    persona_id=persona.id,
                    name=persona.name,
                )
                return persona.system_prompt.strip()

            # Fallback: 从其他字段构建
            parts = []
            if persona.personality and persona.personality.strip():
                parts.append(f"性格: {persona.personality.strip()}")
            if persona.scenario and persona.scenario.strip():
                parts.append(f"场景: {persona.scenario.strip()}")
            if persona.first_mes and persona.first_mes.strip():
                parts.append(f"参考开场白: {persona.first_mes.strip()}")
            if persona.mes_example and persona.mes_example.strip():
                parts.append(f"对话示例: {persona.mes_example.strip()}")

            if parts:
                prompt = "\n".join(parts)
                logger.info(
                    "persona_resolver.built_from_fields",
                    persona_id=persona.id,
                    name=persona.name,
                    field_count=len(parts),
                )
                return prompt

            logger.info(
                "persona_resolver.empty",
                persona_id=persona.id,
                name=persona.name,
            )
            return ""

    except Exception as exc:
        logger.warning("persona_resolver.error", error=str(exc))
        return ""
