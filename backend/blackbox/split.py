"""Train/test split by template, so test runs come from task templates never seen in training."""

import random

TEST_FRACTION = 0.28


def test_templates(templates: list[str], seed: int = 0) -> set[str]:
    """A fixed, seeded choice of templates held out for testing."""
    shuffled = sorted(templates)
    random.Random(seed).shuffle(shuffled)
    return set(shuffled[: max(1, round(len(shuffled) * TEST_FRACTION))])


def split_by_hash(template_id: str) -> str:
    """Split for imported runs, whose full template list isn't known up front: stable per template."""
    import hashlib

    return "test" if int(hashlib.sha1(template_id.encode()).hexdigest(), 16) % 100 < TEST_FRACTION * 100 else "train"


def split_of(template_id: str, templates: list[str]) -> str:
    return "test" if template_id in test_templates(templates) else "train"
