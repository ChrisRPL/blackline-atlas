from __future__ import annotations

import base64

from training.scripts.serve_liquid_vl_openai import build_template_messages, normalize_content_parts


def test_normalize_content_parts_keeps_text_and_marks_images() -> None:
    loaded: list[str] = []

    def fake_loader(url: str) -> object:
        loaded.append(url)
        return {"loaded": url}

    parts, images = normalize_content_parts(
        [
            {"type": "text", "text": "Current frame"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,AAAA"},
            },
            {"type": "text", "text": "Baseline frame"},
        ],
        image_loader=fake_loader,
    )

    assert parts == [
        {"type": "text", "text": "Current frame"},
        {"type": "image"},
        {"type": "text", "text": "Baseline frame"},
    ]
    assert images == [{"loaded": "data:image/png;base64,AAAA"}]
    assert loaded == ["data:image/png;base64,AAAA"]


def test_build_template_messages_supports_string_system_and_multimodal_user() -> None:
    tiny_png = base64.b64encode(b"tiny-image").decode("ascii")
    seen: list[str] = []

    def fake_loader(url: str) -> object:
        seen.append(url)
        return {"image": url}

    messages, images = build_template_messages(
        [
            {"role": "system", "content": "Return JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{tiny_png}"},
                    },
                ],
            },
        ],
        image_loader=fake_loader,
    )

    assert messages == [
        {"role": "system", "content": [{"type": "text", "text": "Return JSON only."}]},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe"},
                {"type": "image"},
            ],
        },
    ]
    assert len(images) == 1
    assert seen[0].startswith("data:image/png;base64,")
