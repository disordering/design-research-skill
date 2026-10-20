import asyncio
import io

from PIL import Image

from engine.contracts import Decision, ReviewContext
from engine.criteria import CriteriaLibrary
from engine.service import ReviewEngine
from engine.stub import StubModel


def _png_bytes(width: int = 640, height: int = 360) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_stub_review_has_full_rule_coverage_and_evidence():
    criteria = CriteriaLibrary.load("判据库_v1.json")
    engine = ReviewEngine(
        criteria,
        StubModel(),
        provider="stub",
        model_name="contract-stub-v1",
        is_stub=True,
    )
    report = asyncio.run(
        engine.review(
            _png_bytes(),
            context=ReviewContext(design_goal="测试任务"),
            analysis_mode="two_pass",
        )
    )

    assert report.status == "partial"
    assert report.model.is_stub is True
    assert len(report.rule_results) == 24
    assert report.rule_results[18].decision is Decision.CANDIDATE_ISSUE
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.id == "F001"
    assert finding.review_status == "unreviewed"
    assert finding.evidence.x + finding.evidence.width <= 1
    assert finding.principle
    assert finding.detection
    assert finding.description
    assert finding.suggestion


def test_single_pass_still_produces_contract():
    criteria = CriteriaLibrary.load("判据库_v1.json")
    engine = ReviewEngine(
        criteria,
        StubModel(),
        provider="stub",
        model_name="contract-stub-v1",
        is_stub=True,
    )
    report = asyncio.run(
        engine.review(_png_bytes(), analysis_mode="single_pass")
    )
    assert report.model.analysis_mode == "single_pass"
    assert report.summary.rules_total == 24
