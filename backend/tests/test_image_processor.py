"""Tests for app.handlers.image_processor — collect_image_descriptors."""
import pytest
from app.handlers.image_processor import collect_image_descriptors
from app.utils import Stub


class TestCollectImageDescriptors:
    def test_regular_attachments(self):
        msg = Stub(
            attachments=[
                Stub(url="http://example.com/img.png", content_type="image/png"),
                Stub(url="http://example.com/doc.pdf", content_type="application/pdf"),
            ],
            embeds=[],
            stickers=[],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test-source")
        assert len(descriptors) == 2
        kinds = {d["kind"] for d in descriptors}
        assert "attachment" in kinds
        assert all(d["source"] == "test-source" for d in descriptors)

    def test_skips_non_image_attachment(self):
        msg = Stub(
            attachments=[
                Stub(url="http://example.com/file.txt", content_type="text/plain"),
            ],
            embeds=[],
            stickers=[],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 0

    def test_attachment_with_no_url(self):
        msg = Stub(
            attachments=[
                Stub(url=None, content_type="image/png"),
            ],
            embeds=[],
            stickers=[],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 0

    def test_embed_image(self):
        msg = Stub(
            attachments=[],
            embeds=[
                Stub(type="image", url="http://example.com/embed.png"),
            ],
            stickers=[],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 1
        assert descriptors[0]["kind"] == "embed"

    def test_embed_thumbnail(self):
        msg = Stub(
            attachments=[],
            embeds=[
                Stub(type="rich", url=None, thumbnail=Stub(url="http://example.com/thumb.png")),
            ],
            stickers=[],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 1
        assert descriptors[0]["kind"] == "embed_thumbnail"

    def test_embed_image_fallback(self):
        msg = Stub(
            attachments=[],
            embeds=[
                Stub(type="rich", url=None, thumbnail=None, image=Stub(url="http://example.com/img.png")),
            ],
            stickers=[],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 1
        assert descriptors[0]["kind"] == "embed_image"

    def test_stickers(self):
        msg = Stub(
            attachments=[],
            embeds=[],
            stickers=[Stub(url="http://example.com/sticker.png")],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 1
        assert descriptors[0]["kind"] == "sticker"

    def test_sticker_without_url(self):
        msg = Stub(
            attachments=[],
            embeds=[],
            stickers=[Stub(url=None)],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 0

    def test_custom_emoji(self):
        msg = Stub(
            attachments=[],
            embeds=[],
            stickers=[],
            content="Hello <:myemoji:1234567890> world",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 1
        assert descriptors[0]["kind"] == "custom_emoji"
        assert "emojis/1234567890.png" in descriptors[0]["url"]

    def test_animated_emoji(self):
        msg = Stub(
            attachments=[],
            embeds=[],
            stickers=[],
            content="Check <a:cool:9876543210> this",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 1
        assert descriptors[0]["kind"] == "custom_emoji"
        assert "emojis/9876543210.png" in descriptors[0]["url"]

    def test_multiple_emojis(self):
        msg = Stub(
            attachments=[],
            embeds=[],
            stickers=[],
            content="<:a:1> <:b:2> <:c:3>",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 3

    def test_no_content_type_still_matches_image(self):
        msg = Stub(
            attachments=[
                Stub(url="http://example.com/img.jpg", content_type=""),
            ],
            embeds=[],
            stickers=[],
            content="",
        )
        descriptors = collect_image_descriptors(msg, "test")
        assert len(descriptors) == 0

    def test_empty_everything(self):
        msg = Stub(attachments=[], embeds=[], stickers=[], content="")
        descriptors = collect_image_descriptors(msg, "test")
        assert descriptors == []
