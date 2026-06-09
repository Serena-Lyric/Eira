"""G-2.1 Validation Gate: Knowledge Pipeline Throughput & Correctness.

Metric: Upload 30-page PDF → status=ready, total time <= 60s, chunk count >= 50 and <= 200.

Usage:
    python tests/validation/test_g2_1_knowledge_pipeline.py
Or:
    uv run pytest tests/validation/test_g2_1_knowledge_pipeline.py -v -s
"""

import asyncio
import json
import os
import sys
import time
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

# ── Generate 30-page PDF fixture (run once at module level) ──────────────

PDF_PATH = os.path.join(os.path.dirname(__file__), "test_30page.pdf")


def _generate_pdf_if_needed():
    if os.path.exists(PDF_PATH):
        return
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    paragraphs = [
        "The West Lake in Hangzhou is a UNESCO World Heritage site spanning 6.5 square kilometers. "
        "The lake is divided by causeways into distinct sections, each with unique scenery. "
        "The Ten Scenes of West Lake include Spring Dawn at Su Causeway and Autumn Moon over the Calm Lake. "
        "Visitors enjoy boat rides, lakeside walks, and cultural performances throughout the year. "
        "The surrounding hills feature temples, pagodas, and Longjing tea plantations. "
        "Local cuisine includes freshwater fish, lotus root, and Dongpo pork. ",

        "The Forbidden City in Beijing served as the imperial palace for 24 emperors across Ming and Qing dynasties. "
        "Covering 72 hectares with over 9000 rooms, it is the world's largest palace complex. "
        "Construction began in 1406 and took 14 years with over a million workers. "
        "The Hall of Supreme Harmony is the largest wooden structure in China. "
        "Yellow glazed tiles cover the roofs as yellow was the imperial color. "
        "The Palace Museum houses over 1.8 million artifacts spanning Chinese civilization. ",

        "Mount Huangshan features peculiar granite peaks, ancient pine trees, sea of clouds, and hot springs. "
        "These four natural wonders earned it the title of China's most beautiful mountain. "
        "The famous Welcoming Guest Pine has become an iconic symbol of Chinese hospitality. "
        "Sunrise viewings from the summit draw thousands of visitors who climb the steep granite steps. "
        "The mountain has inspired countless Chinese paintings and poems over centuries. ",

        "Zhangjiajie National Forest Park features thousands of quartzite sandstone pillars rising from the valley. "
        "These unique geological formations inspired the floating mountains in the movie Avatar. "
        "The Bailong Elevator built into a cliff takes visitors up 300 meters for panoramic views. "
        "The glass bridge spanning a deep canyon offers thrilling experiences for adventurous tourists. "
        "The park is home to diverse wildlife including the endangered Chinese giant salamander. ",

        "Jiuzhaigou Valley is a nature reserve famous for colorful lakes, multi-level waterfalls and snow peaks. "
        "The water is so clear that fallen trees are visible on lake bottoms even at great depths. "
        "Tibetan villages within the valley add cultural richness to the spectacular natural beauty. "
        "Autumn brings the most dramatic display of red and gold foliage reflecting in crystal waters. "
        "The valley was inscribed as a UNESCO World Heritage site in 1992 for its outstanding value. ",

        "The Great Wall stretches over 21,000 kilometers across northern China through diverse terrain. "
        "Built over multiple dynasties, the Ming Dynasty sections near Beijing are the most preserved. "
        "The wall follows mountain ridges creating a dramatic silhouette visible from space. "
        "Watchtowers at regular intervals served as signal stations and garrison posts for soldiers. "
        "The Badaling section receives the most visitors and has been restored for safe tourist access. ",

        "The Li River flows through Guilin creating one of China's most photographed landscapes. "
        "The 83-kilometer cruise from Guilin to Yangshuo passes through a gallery of karst peaks. "
        "Cormorant fishermen practice their ancient fishing technique along the riverbanks at dusk. "
        "The limestone formations reflected in crystal waters create a dreamlike natural painting. "
        "Elephant Trunk Hill in downtown Guilin is the city's iconic landmark resembling an elephant drinking. ",
    ]

    for page in range(30):
        pdf.add_page()
        pdf.set_font("Helvetica", size=14)
        title = f"Page {page+1} - China Scenic Spots Travel Guide"
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(6)

        pdf.set_font("Helvetica", size=10)
        # Write 3 paragraphs per page
        for i in range(3):
            idx = (page + i) % len(paragraphs)
            pdf.multi_cell(0, 5, paragraphs[idx] * 2)  # double for more content
            pdf.ln(4)

    pdf.output(PDF_PATH)
    print(f"[G-2.1] Generated 30-page PDF: {os.path.getsize(PDF_PATH)} bytes")


# ── Test ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_g2_1_knowledge_pipeline_throughput():
    """G-2.1: 30-page PDF pipeline completes within 60s, 50-200 chunks."""
    _generate_pdf_if_needed()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 1. Register and login
        email = f"g21-{uuid.uuid4().hex[:8]}@test.com"
        r = await c.post(
            "/auth/register",
            json={"email": email, "password": "Passw0rd!", "display_name": "G21Tester"},
        )
        assert r.status_code == 201, f"Register failed: {r.text}"

        r = await c.post(
            "/auth/login",
            json={"email": email, "password": "Passw0rd!"},
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Read the PDF from disk
        with open(PDF_PATH, "rb") as f:
            pdf_bytes = f.read()
        pdf_size_kb = len(pdf_bytes) / 1024
        print(f"\n[G-2.1] PDF size: {pdf_size_kb:.1f} KB")

        # 3. Upload PDF
        print("[G-2.1] Uploading PDF...")
        t_upload = time.perf_counter()

        # Use content param for simplicity
        r = await c.post(
            "/documents/upload",
            files={"file": ("scenic_guide_30pages.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert r.status_code == 201, (
            f"Upload failed (status={r.status_code}): {r.text[:500]}"
        )
        upload_data = r.json()
        doc_id = upload_data["document_id"]
        print(f"[G-2.1] Document ID: {doc_id}, initial status: {upload_data['status']}")

        # 4. Poll for completion
        print("[G-2.1] Waiting for pipeline completion...")
        max_wait = 120
        poll_interval = 2.0
        waited = 0.0
        final_status = None
        chunk_count = 0
        error_msg = None

        while waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval

            r = await c.get(f"/documents/{doc_id}/progress", headers=headers)
            if r.status_code != 200:
                print(f"  [{waited:.0f}s] progress endpoint returned {r.status_code}")
                continue

            progress_data = r.json()
            status = progress_data["status"]
            stage = progress_data.get("stage", "")
            progress_val = progress_data.get("progress", 0)
            print(f"  [{waited:.0f}s] status={status}, stage={stage}, progress={progress_val}")

            if status in ("ready", "failed"):
                final_status = status
                error_msg = progress_data.get("error")
                # Get detailed document info for chunk count
                r2 = await c.get(f"/documents/{doc_id}", headers=headers)
                if r2.status_code == 200:
                    doc_detail = r2.json()
                    chunk_count = doc_detail.get("chunk_count", 0)
                break

        t_total = time.perf_counter() - t_upload

        # 5. Report results
        print(f"\n[G-2.1] ===== RESULTS =====")
        print(f"[G-2.1] Final status: {final_status}")
        print(f"[G-2.1] Total time: {t_total:.2f}s")
        print(f"[G-2.1] Chunk count: {chunk_count}")
        if error_msg:
            print(f"[G-2.1] Error: {error_msg}")

        # 6. Assertions
        assert final_status == "ready", (
            f"G-2.1 FAILED: Pipeline did not reach 'ready'. "
            f"Status: {final_status}, Error: {error_msg}"
        )

        assert t_total <= 60, (
            f"G-2.1 FAILED: Pipeline took {t_total:.2f}s, exceeds 60s threshold"
        )

        assert 50 <= chunk_count <= 200, (
            f"G-2.1 FAILED: Chunk count {chunk_count} not in range [50, 200]"
        )

        print(f"[G-2.1] ===== PASSED =====")
        print(f"[G-2.1] Time: {t_total:.2f}s <= 60s V")
        print(f"[G-2.1] Chunks: {chunk_count} in [50, 200] V")


# ── Standalone runner ──────────────────────────────────────────────────

if __name__ == "__main__":
    _generate_pdf_if_needed()
    asyncio.run(test_g2_1_knowledge_pipeline_throughput())
