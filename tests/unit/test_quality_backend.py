import json
import time

import httpx

from backend.core.providers.base import (
    ChunkContext,
    ChunkSegment,
    ChunkTranslationRequest,
    SegmentContext,
    TranslationMemoryEntry,
    TranslationRequest,
)
from backend.core.providers.openai_provider import OpenAITranslationProvider
from backend.core.quality.book_term_memory import BookTermMemoryBuilder
from backend.core.quality.content_filter import ContentFilter
from backend.core.quality.glossary_store import GlossaryStore
from backend.core.quality.prompt_builder import TranslationPromptBuilder
from backend.domain.enums import SegmentType
from backend.domain.models import Segment, SegmentExtra


def test_content_filter_skips_empty_url_and_punctuation_only_text() -> None:
    content_filter = ContentFilter()

    assert content_filter.should_translate_text("Hello world") is True
    assert content_filter.should_translate_text("") is False
    assert content_filter.should_translate_text("https://example.com") is False
    assert content_filter.should_translate_text("...") is False


def test_content_filter_skips_numeric_page_and_roman_marker_text() -> None:
    content_filter = ContentFilter()

    assert content_filter.should_translate_text("1984") is False
    assert content_filter.should_translate_text("12/347") is False
    assert content_filter.should_translate_text("Page 12") is False
    assert content_filter.should_translate_text("xii") is False
    assert content_filter.should_translate_text("Chapter IV") is True
    assert content_filter.should_translate_text("Model 3") is True


def test_content_filter_skips_obvious_href_anchor_fragments() -> None:
    content_filter = ContentFilter()

    assert content_filter.should_translate_text("toc.xhtml#part-1") is False
    assert content_filter.should_translate_text("nav.xhtml#chapter_02") is False
    assert content_filter.should_translate_text("#chapter-1") is True
    assert content_filter.should_translate_text("chapter-1") is True



def test_glossary_store_and_prompt_builder_render_glossary_block() -> None:
    glossary_store = GlossaryStore.from_text("mage => 法师\n# comment\nartifact=圣遗物")
    prompt = TranslationPromptBuilder(glossary_store).build(
        TranslationRequest(
            text="artifact mage",
            source_language="en",
            target_language="zh",
            book_title="Guide",
            context=SegmentContext(
                chapter_title="Intro",
                chapter_order=1,
                segment_id=1,
                segment_order=1,
                segment_type=SegmentType.PARAGRAPH,
                extra=SegmentExtra(),
            ),
        )
    )

    assert "mage => 法师" in prompt
    assert "artifact => 圣遗物" in prompt


def test_prompt_builder_uses_fast_lane_for_low_risk_segment_types() -> None:
    prompt = TranslationPromptBuilder().build(
        TranslationRequest(
            text="Chapter 1",
            source_language="en",
            target_language="zh",
            book_title="Guide",
            context=SegmentContext(
                chapter_title="Intro",
                chapter_order=1,
                segment_id=11,
                segment_order=1,
                segment_type=SegmentType.TITLE,
                extra=SegmentExtra(),
                previous_source_texts=("Previous heading",),
                previous_translated_texts=("之前标题",),
            ),
        )
    )

    assert "Routing mode: fast_lane" in prompt
    assert "Translate the provided short text into fluent Simplified Chinese." in prompt
    assert "Previous source context:" not in prompt
    assert "Previous translated context:" not in prompt


def test_prompt_builder_keeps_heavy_context_for_paragraph_segments() -> None:
    prompt = TranslationPromptBuilder().build(
        TranslationRequest(
            text="Hello world",
            source_language="en",
            target_language="zh",
            book_title="Guide",
            context=SegmentContext(
                chapter_title="Intro",
                chapter_order=1,
                segment_id=12,
                segment_order=2,
                segment_type=SegmentType.PARAGRAPH,
                extra=SegmentExtra(),
                previous_source_texts=("Previous source",),
                previous_translated_texts=("上一段译文",),
            ),
        )
    )

    assert "Routing mode: heavy_context" in prompt
    assert "Previous source context:" in prompt
    assert "Previous translated context:" in prompt



def test_openai_provider_extracts_output_text_from_response_payload() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": "你好，世界",
                    }
                ]
            }
        ]
    }

    assert OpenAITranslationProvider._extract_output_text(payload) == "你好，世界"



def test_openai_provider_extracts_response_payload_from_sse_stream() -> None:
    raw_sse = "\n\n".join(
        [
            "event: response.created\ndata: "
            + json.dumps(
                {
                    "type": "response.created",
                    "response": {
                        "id": "resp_1",
                        "output": [],
                    },
                }
            ),
            "event: response.completed\ndata: "
            + json.dumps(
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_1",
                        "model": "gpt-5.4",
                        "output": [
                            {
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "你好，世界",
                                    }
                                ]
                            }
                        ],
                    },
                }
            ),
        ]
    )

    payload = OpenAITranslationProvider._load_response_payload(raw_sse)

    assert payload["model"] == "gpt-5.4"
    assert OpenAITranslationProvider._extract_output_text(payload) == "你好，世界"



def test_openai_provider_parses_chunk_items_from_json_array() -> None:
    items = OpenAITranslationProvider._parse_chunk_items(
        '[{"segment_id": 1, "translated_text": "你好"}, {"segment_id": 2, "translated_text": "世界"}]'
    )

    assert [item.segment_id for item in items] == [1, 2]
    assert [item.translated_text for item in items] == ["你好", "世界"]


def test_openai_provider_extracts_json_array_from_wrapped_text() -> None:
    items = OpenAITranslationProvider._parse_chunk_items(
        'Here is the JSON:\n[{"segment_id": 1, "translated_text": "你好"}]\nDone.'
    )

    assert [item.segment_id for item in items] == [1]
    assert [item.translated_text for item in items] == ["你好"]



def test_openai_provider_sends_responses_input_as_message_list() -> None:
    captured_payload: dict[str, object] = {}
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode("utf-8")))
        captured_headers.update(request.headers)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.4",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": "你好",
                            }
                        ]
                    }
                ],
            },
        )

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = OpenAITranslationProvider(
        model_name="gpt-5.4",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        response = provider.translate(
            TranslationRequest(
                text="Hello world",
                source_language="en",
                target_language="zh",
                book_title="Guide",
                context=SegmentContext(
                    chapter_title="Intro",
                    chapter_order=1,
                    segment_id=1,
                    segment_order=1,
                    segment_type=SegmentType.PARAGRAPH,
                    extra=SegmentExtra(),
                ),
            )
        )
    finally:
        shared_client.close()

    assert response.translated_text == "你好"
    assert isinstance(captured_payload["input"], list)
    assert captured_payload["input"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Hello world",
                }
            ],
        }
    ]
    assert captured_headers["authorization"] == "Bearer test-key"


def test_openai_provider_sends_chat_completions_messages_for_segment_translation() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "你好",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = OpenAITranslationProvider(
        model_name="deepseek-chat",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
            "api_mode": "chat_completions",
        },
        http_client=shared_client,
    )
    try:
        response = provider.translate(
            TranslationRequest(
                text="Hello world",
                source_language="en",
                target_language="zh",
                book_title="Guide",
                context=SegmentContext(
                    chapter_title="Intro",
                    chapter_order=1,
                    segment_id=1,
                    segment_order=1,
                    segment_type=SegmentType.PARAGRAPH,
                    extra=SegmentExtra(),
                ),
            )
        )
    finally:
        shared_client.close()

    assert response.translated_text == "你好"
    assert "messages" in captured_payload
    assert captured_payload["messages"][0]["role"] == "system"
    assert "Translate the provided text into fluent Simplified Chinese." in captured_payload["messages"][0]["content"]
    assert captured_payload["messages"][1] == {
        "role": "user",
        "content": "Hello world",
    }
    assert "instructions" not in captured_payload
    assert "input" not in captured_payload


def test_openai_provider_omits_reasoning_when_not_configured() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": "你好",
                            }
                        ]
                    }
                ],
            },
        )

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = OpenAITranslationProvider(
        model_name="deepseek-chat",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        provider.translate(
            TranslationRequest(
                text="Hello world",
                source_language="en",
                target_language="zh",
                book_title="Guide",
                context=SegmentContext(
                    chapter_title="Intro",
                    chapter_order=1,
                    segment_id=1,
                    segment_order=1,
                    segment_type=SegmentType.PARAGRAPH,
                    extra=SegmentExtra(),
                ),
            )
        )
    finally:
        shared_client.close()

    assert "reasoning" not in captured_payload


def test_openai_provider_respects_requests_per_minute_limit() -> None:
    request_timestamps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_timestamps.append(time.perf_counter())
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": "你好",
                            }
                        ]
                    }
                ],
            },
        )

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = OpenAITranslationProvider(
        model_name="deepseek-chat",
        options={
            "api_key": "test-key-rpm",
            "base_url": "https://rpm.example.test",
            "max_requests_per_minute": 1,
            "request_rate_limit_window_seconds": 0.05,
        },
        http_client=shared_client,
    )
    request_payload = TranslationRequest(
        text="Hello world",
        source_language="en",
        target_language="zh",
        book_title="Guide",
        context=SegmentContext(
            chapter_title="Intro",
            chapter_order=1,
            segment_id=1,
            segment_order=1,
            segment_type=SegmentType.PARAGRAPH,
            extra=SegmentExtra(),
        ),
    )
    try:
        provider.translate(request_payload)
        provider.translate(request_payload)
    finally:
        shared_client.close()

    assert len(request_timestamps) == 2
    assert request_timestamps[1] - request_timestamps[0] >= 0.045


def test_openai_provider_detects_runtime_capabilities_from_models_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path.endswith("/v1/models")
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "custom-model",
                            "context_window": 64000,
                            "supports_reasoning": True,
                            "supports_structured_outputs": True,
                        }
                    ]
                },
            )
        assert request.method == "POST"
        if request.url.path.endswith("/v1/responses"):
            return httpx.Response(200, json={"id": "probe-response"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="custom-model",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        detection = provider.detect_runtime_capabilities()
    finally:
        shared_client.close()

    assert detection.options["api_mode"] == "responses"
    assert detection.options["detected_context_window"] == 64000
    assert detection.options["reasoning_mode"] == "reasoning"
    assert detection.options["structured_output_strength"] == "strong"
    assert detection.option_sources["api_mode"] == "endpoint_capability_detection"
    assert detection.option_sources["detected_context_window"] == "endpoint_models_payload"
    assert detection.metadata["probe_status"] == "ok"
    assert detection.metadata["confidence"] == "high"
    assert detection.metadata["model_listed"] is True
    assert detection.metadata["cache_hit"] is False


def test_openai_provider_uses_persistent_models_cache_for_known_model_hints(tmp_path) -> None:
    OpenAITranslationProvider.reset_endpoint_capability_cache()
    request_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_paths.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            assert request.url.path.endswith("/v1/models")
            return httpx.Response(200, json={"data": [{"id": "gpt-5.4"}]})
        assert request.method == "POST"
        if request.url.path.endswith("/v1/responses"):
            return httpx.Response(200, json={"id": "probe-response"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    cache_root = tmp_path / "endpoint-capabilities"
    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="gpt-5.4",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
            "_fanbook_endpoint_capability_cache_root": str(cache_root),
        },
        http_client=shared_client,
    )
    try:
        first_detection = provider.detect_runtime_capabilities()
    finally:
        shared_client.close()

    assert request_paths == [
        "GET /v1/models",
        "POST /v1/responses",
        "POST /v1/responses",
        "POST /v1/responses",
    ]
    assert first_detection.options["api_mode"] == "responses"
    assert first_detection.options["detected_context_window"] == 1050000
    assert first_detection.options["structured_output_strength"] == "strong"
    assert first_detection.options["reasoning_mode"] == "reasoning"
    assert first_detection.option_sources["detected_context_window"] == "endpoint_model_directory"
    assert first_detection.metadata["snapshot_source"] == "live_probe"
    assert first_detection.metadata["confidence"] == "high"
    assert first_detection.metadata["cache_hit"] is False

    OpenAITranslationProvider.reset_endpoint_capability_cache()

    def fail_on_network(_: httpx.Request) -> httpx.Response:
        raise AssertionError("persistent endpoint capability cache should avoid a second /models request")

    cached_client = httpx.Client(transport=httpx.MockTransport(fail_on_network))
    cached_provider = OpenAITranslationProvider(
        model_name="gpt-5.4",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
            "_fanbook_endpoint_capability_cache_root": str(cache_root),
        },
        http_client=cached_client,
    )
    try:
        second_detection = cached_provider.detect_runtime_capabilities()
    finally:
        cached_client.close()

    assert second_detection.options["detected_context_window"] == 1050000
    assert second_detection.metadata["snapshot_source"] == "persistent_cache"
    assert second_detection.metadata["cache_hit"] is True


def test_openai_provider_uses_known_catalog_hint_for_gpt_4_1_mini() -> None:
    OpenAITranslationProvider.reset_endpoint_capability_cache()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "gpt-4.1-mini"}]})
        assert request.method == "POST"
        if request.url.path.endswith("/v1/responses"):
            return httpx.Response(200, json={"id": "probe-response"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="gpt-4.1-mini",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        detection = provider.detect_runtime_capabilities()
    finally:
        shared_client.close()
        OpenAITranslationProvider.reset_endpoint_capability_cache()

    assert detection.options["detected_context_window"] == 1047576
    assert detection.option_sources["detected_context_window"] == "endpoint_model_directory"
    assert detection.metadata["catalog_match"] == "gpt-4.1-mini"


def test_openai_provider_uses_known_catalog_hint_for_gpt_5_2() -> None:
    OpenAITranslationProvider.reset_endpoint_capability_cache()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "gpt-5.2"}]})
        assert request.method == "POST"
        if request.url.path.endswith("/v1/responses"):
            return httpx.Response(200, json={"id": "probe-response"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="gpt-5.2",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        detection = provider.detect_runtime_capabilities()
    finally:
        shared_client.close()
        OpenAITranslationProvider.reset_endpoint_capability_cache()

    assert detection.options["detected_context_window"] == 400000
    assert detection.option_sources["detected_context_window"] == "endpoint_model_directory"
    assert detection.metadata["catalog_match"] == "gpt-5.2"


def test_openai_provider_uses_known_catalog_hint_for_o3_pro() -> None:
    OpenAITranslationProvider.reset_endpoint_capability_cache()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "o3-pro"}]})
        assert request.method == "POST"
        if request.url.path.endswith("/v1/responses"):
            return httpx.Response(200, json={"id": "probe-response"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="o3-pro",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        detection = provider.detect_runtime_capabilities()
    finally:
        shared_client.close()
        OpenAITranslationProvider.reset_endpoint_capability_cache()

    assert detection.options["detected_context_window"] == 200000
    assert detection.option_sources["detected_context_window"] == "endpoint_model_directory"
    assert detection.metadata["catalog_match"] == "o3-pro"


def test_openai_provider_marks_structured_outputs_weak_when_probe_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "weak-structured-model"}]})
        assert request.method == "POST"
        if request.url.path.endswith("/v1/responses"):
            payload = json.loads(request.content.decode("utf-8"))
            if "text" in payload:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": "response_format json_schema is not supported for this model",
                        }
                    },
                )
            return httpx.Response(200, json={"id": "probe-response"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="weak-structured-model",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        detection = provider.detect_runtime_capabilities()
    finally:
        shared_client.close()
        OpenAITranslationProvider.reset_endpoint_capability_cache()

    assert detection.options["api_mode"] == "responses"
    assert detection.options["structured_output_strength"] == "weak"
    assert detection.options["reasoning_mode"] == "reasoning"
    assert detection.option_sources["structured_output_strength"] == "endpoint_capability_detection"
    assert detection.metadata["confidence"] == "high"
    deep_probe = detection.metadata["deep_probe"]
    assert deep_probe["attempts"]["responses_structured"]["status"] == "unsupported"


def test_openai_provider_treats_2xx_probe_error_payload_as_unsupported_and_falls_back() -> None:
    request_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_paths.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "chat-only-model"}]})
        assert request.method == "POST"
        if request.url.path.endswith("/v1/responses"):
            payload = json.loads(request.content.decode("utf-8"))
            assert isinstance(payload.get("input"), list)
            return httpx.Response(
                200,
                json={
                    "code": -1000,
                    "message": "correct request is POST /v1/chat/completions, not /v1/responses",
                    "data": None,
                },
            )
        if request.url.path.endswith("/v1/chat/completions"):
            payload = json.loads(request.content.decode("utf-8"))
            if "response_format" in payload:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": "response_format json_schema is not supported for this model",
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": "chat-probe-response",
                    "choices": [
                        {
                            "message": {
                                "content": "OK",
                            }
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="chat-only-model",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    try:
        detection = provider.detect_runtime_capabilities()
    finally:
        shared_client.close()
        OpenAITranslationProvider.reset_endpoint_capability_cache()

    assert request_paths == [
        "GET /v1/models",
        "POST /v1/responses",
        "POST /v1/chat/completions",
        "POST /v1/chat/completions",
    ]
    assert detection.options["api_mode"] == "chat_completions"
    assert detection.options["structured_output_strength"] == "weak"
    assert "reasoning_mode" not in detection.options
    assert detection.metadata["confidence"] == "high"
    deep_probe = detection.metadata["deep_probe"]
    assert deep_probe["chosen_api_mode"] == "chat_completions"
    assert deep_probe["attempts"]["responses_basic"]["status"] == "unsupported"
    assert deep_probe["attempts"]["chat_completions_basic"]["status"] == "supported"
    assert deep_probe["attempts"]["chat_completions_structured"]["status"] == "unsupported"



def test_openai_provider_sends_chunk_input_as_structured_json() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.4",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": '[{"segment_id": 101, "translated_text": "你好"}]',
                            }
                        ]
                    }
                ],
            },
        )

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = OpenAITranslationProvider(
        model_name="gpt-5.4",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
            "max_output_tokens": 321,
        },
        http_client=shared_client,
    )
    try:
        response = provider.translate_chunk(
            ChunkTranslationRequest(
                source_language="en",
                target_language="zh",
                book_title="Guide",
                context=ChunkContext(
                    chapter_title="Intro",
                    chapter_order=1,
                    chunk_id="chunk-1",
                    chunk_sequence=1,
                    previous_source_texts=("Hello",),
                    previous_translated_texts=("你好",),
                    translation_memory=(
                        TranslationMemoryEntry(source_text="Alice", translated_text="爱丽丝"),
                    ),
                ),
                segments=(
                    ChunkSegment(
                        segment_id=101,
                        segment_order=1,
                        segment_type=SegmentType.PARAGRAPH,
                        source_text="Hello world",
                        extra=SegmentExtra(),
                    ),
                ),
            )
        )
    finally:
        shared_client.close()

    assert [item.segment_id for item in response.items] == [101]
    assert response.items[0].translated_text == "你好"
    assert captured_payload["max_output_tokens"] == 321
    assert "Return a JSON array only." in str(captured_payload["instructions"])
    serialized_input = captured_payload["input"][0]["content"][0]["text"]
    assert json.loads(serialized_input) == [
        {
            "segment_id": 101,
            "segment_type": "paragraph",
            "source_text": "Hello world",
        }
    ]


def test_openai_provider_sends_chat_completions_messages_for_chunk_translation() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '```json\n[{"segment_id":101,"translated_text":"你好"}]\n```',
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = OpenAITranslationProvider(
        model_name="deepseek-chat",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
            "api_mode": "chat_completions",
            "max_output_tokens": 321,
        },
        http_client=shared_client,
    )
    try:
        response = provider.translate_chunk(
            ChunkTranslationRequest(
                source_language="en",
                target_language="zh",
                book_title="Guide",
                context=ChunkContext(
                    chapter_title="Intro",
                    chapter_order=1,
                    chunk_id="chunk-chat",
                    chunk_sequence=1,
                ),
                segments=(
                    ChunkSegment(
                        segment_id=101,
                        segment_order=1,
                        segment_type=SegmentType.PARAGRAPH,
                        source_text="Hello world",
                        extra=SegmentExtra(),
                    ),
                ),
            )
        )
    finally:
        shared_client.close()

    assert response.items[0].translated_text == "你好"
    assert captured_payload["max_tokens"] == 321
    assert captured_payload["messages"][0]["role"] == "system"
    assert "Return a JSON array only." in captured_payload["messages"][0]["content"]
    serialized_input = captured_payload["messages"][1]["content"]
    assert json.loads(serialized_input) == [
        {
            "segment_id": 101,
            "segment_type": "paragraph",
            "source_text": "Hello world",
        }
    ]


def test_openai_provider_can_reuse_injected_http_client_across_providers() -> None:
    captured_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.4",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": "你好",
                            }
                        ]
                    }
                ],
            },
        )

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider_one = OpenAITranslationProvider(
        model_name="gpt-5.4",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    provider_two = OpenAITranslationProvider(
        model_name="gpt-5.4",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )
    request_payload = TranslationRequest(
        text="Hello world",
        source_language="en",
        target_language="zh",
        book_title="Guide",
        context=SegmentContext(
            chapter_title="Intro",
            chapter_order=1,
            segment_id=1,
            segment_order=1,
            segment_type=SegmentType.PARAGRAPH,
            extra=SegmentExtra(),
        ),
    )

    try:
        first = provider_one.translate(request_payload)
        provider_one.close()
        second = provider_two.translate(request_payload)
    finally:
        shared_client.close()

    assert first.translated_text == "你好"
    assert second.translated_text == "你好"
    assert len(captured_payloads) == 2
    assert captured_payloads[0]["input"] == captured_payloads[1]["input"]


def test_openai_provider_detects_runtime_metadata_from_models_endpoint() -> None:
    OpenAITranslationProvider.reset_endpoint_capability_cache()
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "custom-model",
                            "context_window": 128000,
                            "supported_endpoints": ["chat/completions"],
                            "capabilities": {
                                "reasoning": True,
                                "structured_outputs": True,
                            },
                        }
                    ]
                },
            )
        if request.url.path.endswith("/v1/chat/completions"):
            return httpx.Response(200, json={"id": "probe-chat"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    shared_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAITranslationProvider(
        model_name="custom-model",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=shared_client,
    )

    try:
        detected = provider.detect_runtime_metadata()
    finally:
        shared_client.close()
        OpenAITranslationProvider.reset_endpoint_capability_cache()

    assert requested_urls == [
        "https://api.example.test/v1/models",
        "https://api.example.test/v1/chat/completions",
        "https://api.example.test/v1/chat/completions",
    ]
    assert detected == {
        "api_mode": "chat_completions",
        "detected_context_window": 128000,
        "reasoning_mode": "reasoning",
        "structured_output_strength": "strong",
    }


def test_openai_provider_reuses_cached_runtime_metadata_detection() -> None:
    OpenAITranslationProvider.reset_endpoint_capability_cache()
    request_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_paths.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "cached-model",
                            "context_window": 64000,
                        }
                    ]
                },
            )
        if request.url.path.endswith("/v1/responses"):
            return httpx.Response(200, json={"id": "probe-response"})
        raise AssertionError(f"unexpected probe request: {request.method} {request.url}")

    provider_one_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider_two_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider_one = OpenAITranslationProvider(
        model_name="cached-model",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=provider_one_client,
    )
    provider_two = OpenAITranslationProvider(
        model_name="cached-model",
        options={
            "api_key": "test-key",
            "base_url": "https://api.example.test",
        },
        http_client=provider_two_client,
    )

    try:
        first = provider_one.detect_runtime_metadata()
        second = provider_two.detect_runtime_metadata()
    finally:
        provider_one_client.close()
        provider_two_client.close()
        OpenAITranslationProvider.reset_endpoint_capability_cache()

    assert request_paths == [
        "GET /v1/models",
        "POST /v1/responses",
        "POST /v1/responses",
        "POST /v1/responses",
    ]
    assert first == {
        "api_mode": "responses",
        "detected_context_window": 64000,
        "structured_output_strength": "strong",
        "reasoning_mode": "reasoning",
    }
    assert second == first


def test_openai_provider_pool_size_option_prefers_explicit_value() -> None:
    assert OpenAITranslationProvider._pool_size_option(12, fallback=30) == 12
    assert OpenAITranslationProvider._pool_size_option(None, fallback=9) == 9
    assert OpenAITranslationProvider._pool_size_option("invalid", fallback=7) == 7


def test_prompt_builder_uses_fast_lane_for_low_risk_chunks() -> None:
    prompt = TranslationPromptBuilder().build_chunk(
        ChunkTranslationRequest(
            source_language="en",
            target_language="zh",
            book_title="Guide",
            context=ChunkContext(
                chapter_title="Intro",
                chapter_order=1,
                chunk_id="chunk-fast",
                chunk_sequence=1,
                previous_source_texts=("Prev",),
                previous_translated_texts=("前文",),
                following_source_texts=("Next",),
                translation_memory=(
                    TranslationMemoryEntry(source_text="Sword", translated_text="剑"),
                ),
            ),
            segments=(
                ChunkSegment(
                    segment_id=201,
                    segment_order=1,
                    segment_type=SegmentType.TITLE,
                    source_text="Chapter 1",
                    extra=SegmentExtra(),
                ),
                ChunkSegment(
                    segment_id=202,
                    segment_order=2,
                    segment_type=SegmentType.LIST_ITEM,
                    source_text="First item",
                    extra=SegmentExtra(),
                ),
            ),
        )
    )

    assert "Routing mode: fast_lane" in prompt
    assert "Translate each short segment into fluent Simplified Chinese." in prompt
    assert "Previous source context:" not in prompt
    assert "Previous translated context:" not in prompt
    assert "Following source context:" not in prompt
    assert "Recent translation memory:" not in prompt


def test_prompt_builder_falls_back_to_heavy_context_for_mixed_chunks() -> None:
    prompt = TranslationPromptBuilder().build_chunk(
        ChunkTranslationRequest(
            source_language="en",
            target_language="zh",
            book_title="Guide",
            context=ChunkContext(
                chapter_title="Intro",
                chapter_order=1,
                chunk_id="chunk-heavy",
                chunk_sequence=1,
                previous_source_texts=("Prev",),
                previous_translated_texts=("前文",),
                following_source_texts=("Next",),
                translation_memory=(
                    TranslationMemoryEntry(source_text="Alice", translated_text="爱丽丝"),
                ),
            ),
            segments=(
                ChunkSegment(
                    segment_id=301,
                    segment_order=1,
                    segment_type=SegmentType.TITLE,
                    source_text="Chapter 1",
                    extra=SegmentExtra(),
                ),
                ChunkSegment(
                    segment_id=302,
                    segment_order=2,
                    segment_type=SegmentType.PARAGRAPH,
                    source_text="Hello world",
                    extra=SegmentExtra(),
                ),
            ),
        )
    )

    assert "Routing mode: heavy_context" in prompt
    assert "Previous source context:" in prompt
    assert "Previous translated context:" in prompt
    assert "Following source context:" in prompt
    assert "Recent translation memory:" in prompt


def test_prompt_builder_includes_chapter_memory_and_dialogue_focus() -> None:
    prompt = TranslationPromptBuilder().build_chunk(
        ChunkTranslationRequest(
            source_language="en",
            target_language="zh",
            book_title="Novel",
            context=ChunkContext(
                chapter_title="Chapter One",
                chapter_order=1,
                chunk_id="chunk-dialogue",
                chunk_sequence=2,
                chapter_summary="Recurring names and settings: Alice => 爱丽丝, Manor",
                narrative_mode="dialogue_focus",
            ),
            segments=(
                ChunkSegment(
                    segment_id=1,
                    segment_order=1,
                    segment_type=SegmentType.PARAGRAPH,
                    source_text='"Alice," he said.',
                    extra=SegmentExtra(),
                ),
            ),
        )
    )

    assert "Dialogue focus:" in prompt
    assert "Chapter memory:" in prompt
    assert "Alice => 爱丽丝" in prompt


def test_book_term_memory_builder_tracks_repeated_terms_and_targets() -> None:
    builder = BookTermMemoryBuilder()
    snapshot = builder.build(
        chapters=(
            type(
                "Batch",
                (),
                {
                    "chapter": type("Chapter", (), {"id": 1})(),
                    "segments": (
                        Segment(
                            chapter_id=1,
                            order=1,
                            source_text="Alice answered softly.",
                            translated_text="爱丽丝 回答。",
                            segment_type=SegmentType.PARAGRAPH,
                            status="translated",
                        ),
                        Segment(
                            chapter_id=1,
                            order=2,
                            source_text="Alice answered again.",
                            translated_text="艾丽斯 回答。",
                            segment_type=SegmentType.PARAGRAPH,
                            status="translated",
                        ),
                    ),
                },
            )(),
        ),
    )

    alice_entry = next(entry for entry in snapshot.entries if entry.source == "Alice")
    assert snapshot.hints_for_chapter(1)
    assert alice_entry.occurrences == 2
    assert {candidate.text for candidate in alice_entry.target_candidates} >= {"爱丽丝", "艾丽斯"}



def test_content_filter_applies_to_segments() -> None:
    segment = Segment(
        chapter_id=1,
        order=1,
        source_text="...",
        segment_type=SegmentType.PARAGRAPH,
        status="pending",
    )

    assert ContentFilter().should_translate_segment(segment) is False


def test_content_filter_skips_anchor_like_nav_fragments_only_for_nav_segments() -> None:
    nav_segment = Segment(
        chapter_id=1,
        order=1,
        source_text="#chapter-1",
        segment_type=SegmentType.PARAGRAPH,
        status="pending",
        extra=SegmentExtra(is_nav=True),
    )
    body_segment = Segment(
        chapter_id=1,
        order=2,
        source_text="#chapter-1",
        segment_type=SegmentType.PARAGRAPH,
        status="pending",
        extra=SegmentExtra(),
    )

    content_filter = ContentFilter()

    assert content_filter.should_translate_segment(nav_segment) is False
    assert content_filter.should_translate_segment(body_segment) is True
