"""One-shot script: upload Live2D models from docs/originalfile/2D to OSS and register in assets table.

Usage:
    cd backend
    python scripts/seed_models.py

Requires the same env vars as the backend (EIRA_DB_DSN, EIRA_OSS_ENDPOINT, etc.).
"""

import asyncio
import os
import sys
import uuid

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infra.oss import get_oss_client, presign_get
from app.infra.db import get_session_factory
from sqlalchemy import text

BUCKET = "eira-live2d"
MODELS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "originalfile", "2D"
)

# Models to upload: (display_name, filename)
MODELS = [
    ("mao_pro_zh", "mao_pro_zh.zip"),
    ("hiyori_pro_zh", "hiyori_pro_zh.zip"),
    ("akari_vts", "akari_vts.rar"),
    ("hiyori_vts", "hiyori_vts.rar"),
    ("PinkHair_workshop_2802653785", "PinkHair_workshop_2802653785.rar"),
    ("haru", "haru.zip"),
    ("MaidCyrene", "MaidCyrene20251105_by_MomokaSono_f86e9234d0bc76edc325d4d3901454fe.zip"),
]


async def main():
    oss = get_oss_client()
    factory = get_session_factory()

    # Create bucket if needed
    try:
        oss.create_bucket(Bucket=BUCKET)
        print(f"[seed] Created bucket: {BUCKET}")
    except Exception:
        print(f"[seed] Bucket already exists: {BUCKET}")

    asset_ids = []
    async with factory() as session:
        for display_name, filename in MODELS:
            filepath = os.path.join(MODELS_DIR, filename)
            if not os.path.exists(filepath):
                print(f"[seed] SKIP (not found): {filename}")
                continue

            file_size = os.path.getsize(filepath)
            ext = filename.rsplit(".", 1)[-1].lower()
            mime = "application/zip" if ext == "zip" else "application/x-rar-compressed"

            # Upload to OSS
            asset_key = uuid.uuid4().hex[:12]
            oss_key = f"live2d/{asset_key}/{filename}"
            with open(filepath, "rb") as f:
                oss.put_object(Bucket=BUCKET, Key=oss_key, Body=f.read())

            # Register in DB
            result = await session.execute(
                text(
                    """INSERT INTO assets (user_id, kind, name, oss_key, mime_type, file_size, meta)
                    VALUES (1, 'live2d_model', :name, :oss_key, :mime, :size, '{}')
                    RETURNING id"""
                ),
                {
                    "name": display_name,
                    "oss_key": oss_key,
                    "mime": mime,
                    "size": file_size,
                },
            )
            row = result.fetchone()
            asset_id = row[0] if row else 0
            asset_ids.append(asset_id)
            await session.commit()
            print(f"[seed] OK  id={asset_id}  {display_name}  ({file_size // 1024 // 1024} MB)")

    # Set first model as default
    if asset_ids:
        async with factory() as session:
            result = await session.execute(
                text("SELECT oss_key FROM assets WHERE id = :id"),
                {"id": asset_ids[0]},
            )
            row = result.fetchone()
            if row:
                from app.domain.system.service import SystemSettingService
                svc = SystemSettingService(session)
                current = await svc.get("persona_config") or {}
                if isinstance(current, dict):
                    current["active_model_id"] = row[0]
                    current["active_model_display_name"] = MODELS[0][0]
                    await svc.set("persona_config", current, description="默认 Live2D 模型")
                    await session.commit()
                print(f"[seed] Default model set: {MODELS[0][0]}")

    print(f"[seed] Done. {len(asset_ids)} models uploaded.")


if __name__ == "__main__":
    asyncio.run(main())
