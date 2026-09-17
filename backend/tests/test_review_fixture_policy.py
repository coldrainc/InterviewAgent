from pathlib import Path

from interview_agent.fixtures.review_site_admin import ADMIN_REVIEW_SITE_FIXTURE


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_SOURCES = [
    ROOT / "backend" / "src",
    ROOT / "apps" / "desktop" / "src",
    ROOT / "scripts",
]


def test_admin_fixture_is_anonymous_and_marked_as_test_data() -> None:
    serialized = repr(ADMIN_REVIEW_SITE_FIXTURE)
    assert ADMIN_REVIEW_SITE_FIXTURE["plan"]["metadata"] == {
        "fixture": True,
        "fixture_kind": "admin_test",
    }
    assert "陈雨寒" not in serialized
    assert "knowledge_base/interview" not in serialized
    assert "面试题/interview" not in serialized


def test_production_sources_do_not_contain_retired_personal_template() -> None:
    forbidden = ("陈雨寒", "cyh-14-day-interview-review")
    for source_root in PRODUCTION_SOURCES:
        for path in source_root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                assert marker not in text, f"retired personal template marker found in {path}"
