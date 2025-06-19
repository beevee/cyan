import sys
from pathlib import Path

# Ensure project root is on sys.path so "main" module can be imported when tests
# are executed from any directory.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main  # noqa: E402


def test_nested_checkbox():
    sample = (
        "1. Project overview\n"
        "   1. [ ] Draft initial requirements document.\n"
    )
    expected = [
        "",
        "- Project overview",
        "  - Draft initial requirements document.",
    ]

    report = main.build_report(sample)
    assert report == expected


def test_multiple_nested_checkboxes():
    sample = (
        "5. Team training plan\n"
        "   1. Identify training needs.\n"
        "   2. Select vendor.\n"
        "   3. Schedule sessions.\n"
        "   4. Estimate budget.\n"
        "   5. Get approvals.\n"
        "   6. [ ] Send calendar invitations.\n"
        "   7. Follow-up actions\n"
        "      1. [ ] Prepare feedback survey.\n"
    )

    expected = [
        "",
        "- Team training plan",
        "  - Send calendar invitations.",
        "",
        "- Team training plan",
        "  - Follow-up actions",
        "    - Prepare feedback survey.",
    ]

    report = main.build_report(sample)
    assert report == expected


def test_children_included():
    sample = (
        "- Parent\n"
        "  - [ ] Root task\n"
        "    - Child 1\n"
        "    - Child 2\n"
    )

    expected = [
        "",
        "- Parent",
        "  - Root task",
        "    - Child 1",
        "    - Child 2",
    ]

    report = main.build_report(sample)
    assert report == expected