from __future__ import annotations


def build_candidate_user_content(
    *,
    prompt_text: str,
    current_image: object,
    baseline_image: object,
) -> list[dict[str, object]]:
    return [
        {"type": "text", "text": prompt_text},
        {"type": "image", "image": current_image},
        {"type": "image", "image": baseline_image},
    ]
