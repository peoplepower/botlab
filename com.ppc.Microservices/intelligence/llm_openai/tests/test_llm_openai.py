import logging
from unittest.mock import patch

from intelligence.intelligence import Intelligence  # type: ignore
from intelligence.llm_openai.location_llm_openai_microservice import (
    MAX_RETRY_ATTEMPTS,
)
from signals.llm import (  # type: ignore
    PROVIDER_API_OPENAI_CHAT_COMPLETION,
    PROVIDER_API_OPENAI_RESPONSE,
)
from locations.location import Location  # type: ignore

from botengine_pytest import BotEnginePyTest

# Module path for patching the logger
_MUT_LOGGER = "intelligence.llm_openai.location_llm_openai_microservice.LocationLLMOpenAIMicroservice"


class MockRequestingMicroservice(Intelligence):
    """Mock microservice that requests LLM completions and receives responses."""

    def __init__(self, botengine, parent):
        Intelligence.__init__(self, botengine, parent)
        self.last_response = None
        self.last_reference = None
        self.last_argument = None
        self.llm_response_count = 0
        self.last_usage_provider = None
        self.last_usage_model = None
        self.last_usage_data = None
        self.last_usage_cost = None

    def initialize(self, botengine):
        pass

    def new_version(self, botengine):
        pass

    def llm_response(self, botengine, response, reference, argument):
        self.last_response = response
        self.last_reference = reference
        self.last_argument = argument
        self.llm_response_count += 1

    def track_llm_usage(self, botengine, provider, model, usage, cost_usd=None):
        self.last_usage_provider = provider
        self.last_usage_model = model
        self.last_usage_data = usage
        self.last_usage_cost = cost_usd

    def track_statistics(self, botengine, ms):
        pass


class TestLocationLLMOpenAIMicroservice:
    def _setup(self):
        """Common setup for tests."""
        botengine = BotEnginePyTest({})
        botengine.reset()

        location = Location(botengine, 12345)
        location.initialize(botengine)
        location.new_version(botengine)

        mut = location.intelligence_modules[
            "intelligence.llm_openai.location_llm_openai_microservice"
        ]
        return botengine, location, mut

    def _add_mock_microservice(self, botengine, location):
        """Add a mock requesting microservice to the location."""
        mock = MockRequestingMicroservice(botengine, location)
        module_key = "intelligence.mock_requesting_microservice"
        location.intelligence_modules[module_key] = mock
        return mock

    def _make_chat_request_content(
        self, intelligence_id, reference="ref_1", messages=None, **kwargs
    ):
        """Build a valid llm_chat_request content dict (Chat Completion API)."""
        content = {
            "intelligence_id": intelligence_id,
            "reference": reference,
            "messages": messages or [{"role": "user", "content": "Hello"}],
        }
        content.update(kwargs)
        return content

    def _make_response_api_content(
        self, intelligence_id, reference="ref_1", input_text=None, **kwargs
    ):
        """Build a valid llm_chat_request content dict for the Response API."""
        content = {
            "intelligence_id": intelligence_id,
            "reference": reference,
            "provider_api": PROVIDER_API_OPENAI_RESPONSE,
            "input": input_text or "Hello",
        }
        content.update(kwargs)
        return content

    def test_initialization_and_new_version(self):
        """Should initialize with empty state; new_version migrates missing attrs."""
        botengine, location, mut = self._setup()
        assert mut is not None
        assert mut._llm_request_mappings == {}
        assert mut._pending_requests == {}

        # Simulate older version missing _pending_requests
        delattr(mut, "_pending_requests")
        mut.new_version(botengine)
        assert mut._pending_requests == {}

    def test_llm_chat_request_validation(self):
        """Requests missing required fields should be rejected."""
        botengine, location, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        invalid_contents = [
            # Missing intelligence_id
            {"reference": "ref_1", "messages": [{"role": "user", "content": "Hello"}]},
            # Missing reference
            {"intelligence_id": "some_id", "messages": [{"role": "user", "content": "Hello"}]},
        ]
        for content in invalid_contents:
            with patch.object(logger, "error") as mock_error:
                mut.llm_chat_request(botengine, content)
                mock_error.assert_called_once()

        # Missing messages uses a mangled logger name, so verify by state only
        mut.llm_chat_request(botengine, {"intelligence_id": "some_id", "reference": "ref_1"})

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    def test_llm_chat_request_valid_with_params(self):
        """Valid request should store mapping/pending; params and argument pass through."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content = self._make_chat_request_content(
            mock.intelligence_id,
            argument={"task": "summarize"},
            max_tokens=1000,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        mut.llm_chat_request(botengine, content)

        # Mapping stored with argument
        ts, int_id, arg = mut._llm_request_mappings["ref_1"]
        assert int_id == mock.intelligence_id
        assert arg == {"task": "summarize"}

        # Pending request stored with all params
        pending = mut._pending_requests["ref_1"]
        assert pending["intelligence_id"] == mock.intelligence_id
        assert pending["retry_attempts"] == 0
        assert pending["argument"] == {"task": "summarize"}
        assert pending["openai_params"]["messages"] == [{"role": "user", "content": "Hello"}]
        assert pending["openai_params"]["max_tokens"] == 1000
        assert pending["openai_params"]["temperature"] == 0.5
        assert pending["openai_params"]["response_format"] == {"type": "json_object"}
        assert pending["timeout_timer_set"] is True

    def test_llm_chat_request_model_priority(self):
        """Model priority: request > org property > default (gpt-4o-mini)."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        # Default model
        content = self._make_chat_request_content(mock.intelligence_id, reference="r1")
        mut.llm_chat_request(botengine, content)
        assert mut._pending_requests["r1"]["openai_params"]["model"] == "gpt-4o-mini"

        # Org property overrides default
        botengine.organization_properties["LLM_OPENAI_DEFAULT_MODEL"] = "gpt-4-turbo"
        content = self._make_chat_request_content(mock.intelligence_id, reference="r2")
        mut.llm_chat_request(botengine, content)
        assert mut._pending_requests["r2"]["openai_params"]["model"] == "gpt-4-turbo"

        # Request model overrides org property
        content = self._make_chat_request_content(mock.intelligence_id, reference="r3", model="gpt-4o")
        mut.llm_chat_request(botengine, content)
        assert mut._pending_requests["r3"]["openai_params"]["model"] == "gpt-4o"

    def test_duplicate_request_cooldown(self):
        """Duplicates blocked within 10s cooldown (timestamp reset); allowed after."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Within cooldown — blocked but timestamp reset to enforce window
        cooldown_time = botengine.get_timestamp() + 5000
        botengine.set_timestamp(cooldown_time)
        mut.llm_chat_request(botengine, content)
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 0
        assert mut._pending_requests["ref_1"]["timestamp_ms"] == cooldown_time

        # After cooldown — replaced with fresh request
        new_time = botengine.get_timestamp() + 11000
        botengine.set_timestamp(new_time)
        mut.llm_chat_request(botengine, content)
        assert mut._pending_requests["ref_1"]["timestamp_ms"] == new_time
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 0

    def test_datastream_routing(self):
        """datastream_updated routes to correct handlers; unknown address is a no-op."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        # Routes llm_chat_request
        content = self._make_chat_request_content(mock.intelligence_id)
        mut.datastream_updated(botengine, "llm_chat_request", content)
        assert "ref_1" in mut._pending_requests

        # Routes openai response
        response = {
            "key": "ref_1",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "choices": [{"message": {"content": "Hello!"}}],
        }
        mut.datastream_updated(botengine, "openai", response)
        assert mock.llm_response_count == 1

        # Unknown address — no raise
        mut.datastream_updated(botengine, "unknown_address", {})

    def test_openai_response_error_handling(self):
        """Responses with missing key, unknown mapping, or removed microservice log errors."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)
        logger = logging.getLogger(_MUT_LOGGER)

        # Missing key
        with patch.object(logger, "error") as mock_error:
            mut.openai(botengine, {"model": "gpt-4o-mini", "usage": {}})
            mock_error.assert_called_once()

        # No mapping for key
        with patch.object(logger, "warning") as mock_warning:
            mut.openai(botengine, {"key": "unknown_ref", "model": "gpt-4o-mini", "usage": {}})
            mock_warning.assert_called()

        # Microservice removed after request was made
        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)
        del location.intelligence_modules["intelligence.mock_requesting_microservice"]
        with patch.object(logger, "error") as mock_error:
            mut.openai(botengine, {"key": "ref_1", "model": "gpt-4o-mini", "usage": {}})
            mock_error.assert_called_once()

    def test_timer_fired_dispatch(self):
        """timer_fired routes timeout/retry types; non-dict argument is ignored."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Timeout increments retry_attempts
        mut.timer_fired(botengine, {"type": "llm_timeout", "reference": "ref_1"})
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 1

        # Retry re-attempts (request still pending)
        mut.timer_fired(botengine, {"type": "llm_retry", "reference": "ref_1"})
        assert "ref_1" in mut._pending_requests

        # Non-dict arguments — no raise
        mut.timer_fired(botengine, "some_string_argument")
        mut.timer_fired(botengine, None)

    def test_timeout_retry_lifecycle(self):
        """Retries increment; after MAX_RETRY_ATTEMPTS the request is abandoned with None response."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content = self._make_chat_request_content(
            mock.intelligence_id, argument={"task": "test"}
        )
        mut.llm_chat_request(botengine, content)
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 0

        # Incremental retries
        mut._handle_request_timeout(botengine, "ref_1")
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 1
        mut._handle_request_timeout(botengine, "ref_1")
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 2

        # Exhaust retries
        mut._pending_requests["ref_1"]["retry_attempts"] = MAX_RETRY_ATTEMPTS - 1
        mut._handle_request_timeout(botengine, "ref_1")

        # Request abandoned, microservice receives None failure
        assert "ref_1" not in mut._pending_requests
        assert mock.llm_response_count == 1
        assert mock.last_response is None
        assert mock.last_reference == "ref_1"
        assert mock.last_argument == {"task": "test"}

        # Nonexistent references are no-ops
        mut._handle_request_timeout(botengine, "nonexistent_ref")
        mut._handle_request_retry(botengine, "nonexistent_ref")

    def test_request_mapping_lifecycle(self):
        """Mappings: store/get, not-found returns (None, None), auto-purge after 30m, expire on get."""
        botengine, location, mut = self._setup()

        # Store and retrieve
        mut._store_request_mapping(botengine, "ref_1", "int_id_1", {"arg": 1})
        int_id, arg = mut._get_request_mapping(botengine, "ref_1")
        assert int_id == "int_id_1"
        assert arg == {"arg": 1}

        # Not found
        int_id, arg = mut._get_request_mapping(botengine, "nonexistent")
        assert int_id is None and arg is None

        # Within 30m window — not purged
        mut._store_request_mapping(botengine, "recent_ref", "recent_id", None)
        botengine.set_timestamp(botengine.get_timestamp() + 29 * 60 * 1000)
        mut._store_request_mapping(botengine, "new_ref", "new_id", None)
        assert "recent_ref" in mut._llm_request_mappings

        # After 30m — auto-purged on store, expired on get
        botengine.set_timestamp(botengine.get_timestamp() + 31 * 60 * 1000)
        mut._store_request_mapping(botengine, "newest_ref", "newest_id", None)
        assert "recent_ref" not in mut._llm_request_mappings

        int_id, arg = mut._get_request_mapping(botengine, "new_ref")
        assert int_id is None and arg is None
        assert "new_ref" not in mut._llm_request_mappings

    def test_make_openai_request_no_pending(self):
        """_make_openai_request with no pending request should log error."""
        botengine, location, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        with patch.object(logger, "error") as mock_error:
            mut._make_openai_request(botengine, "nonexistent_ref")
            mock_error.assert_called_once()

    def test_end_to_end_request_response(self):
        """Full flow: request -> response routed back with usage tracking -> cleanup."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        # 1. Send chat request
        request_content = self._make_chat_request_content(
            mock.intelligence_id,
            reference="e2e_ref",
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "What is 2+2?"},
            ],
            argument={"callback": "math"},
            temperature=0.0,
        )
        mut.llm_chat_request(botengine, request_content)
        assert "e2e_ref" in mut._pending_requests
        assert "e2e_ref" in mut._llm_request_mappings

        # 2. Simulate OpenAI response
        response = {
            "key": "e2e_ref",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 25, "completion_tokens": 5, "total_tokens": 30},
            "cost_usd": 0.001,
            "choices": [{"message": {"role": "assistant", "content": "4"}}],
        }
        mut.openai(botengine, response)

        # 3. Verify response routing
        assert mock.llm_response_count == 1
        assert mock.last_reference == "e2e_ref"
        assert mock.last_argument == {"callback": "math"}
        assert mock.last_response["choices"][0]["message"]["content"] == "4"
        assert mock.last_response["provider"] == "openai"

        # 4. Verify usage tracking
        assert mock.last_usage_provider == "openai"
        assert mock.last_usage_model == "gpt-4o-mini"
        assert mock.last_usage_cost == 0.001

        # 5. Verify cleanup
        assert "e2e_ref" not in mut._pending_requests

    def test_multiple_concurrent_requests(self):
        """Multiple requests tracked independently; out-of-order responses work."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content_1 = self._make_chat_request_content(
            mock.intelligence_id, reference="req_1",
            messages=[{"role": "user", "content": "First"}], argument={"order": 1},
        )
        content_2 = self._make_chat_request_content(
            mock.intelligence_id, reference="req_2",
            messages=[{"role": "user", "content": "Second"}], argument={"order": 2},
        )
        mut.llm_chat_request(botengine, content_1)
        mut.llm_chat_request(botengine, content_2)
        assert "req_1" in mut._pending_requests
        assert "req_2" in mut._pending_requests

        # Respond to second first
        mut.openai(botengine, {"key": "req_2", "model": "gpt-4o-mini", "usage": {},
                                "choices": [{"message": {"content": "Second response"}}]})
        assert mock.last_reference == "req_2"
        assert mock.last_argument == {"order": 2}
        assert "req_2" not in mut._pending_requests
        assert "req_1" in mut._pending_requests

        # Then first
        mut.openai(botengine, {"key": "req_1", "model": "gpt-4o-mini", "usage": {},
                                "choices": [{"message": {"content": "First response"}}]})
        assert mock.llm_response_count == 2
        assert mock.last_reference == "req_1"
        assert "req_1" not in mut._pending_requests

    # ===========================================================================
    # Provider API tests
    # ===========================================================================

    def test_response_api_valid_request(self):
        """Response API request with 'input' should be accepted and stored."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content = self._make_response_api_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        assert "ref_1" in mut._pending_requests
        assert "ref_1" in mut._llm_request_mappings
        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["input"] == "Hello"
        assert "messages" not in pending["openai_params"]

    def test_response_api_missing_input_rejected(self):
        """Response API request without 'input' should be rejected."""
        botengine, location, mut = self._setup()

        content = {
            "intelligence_id": "some_id",
            "reference": "ref_1",
            "provider_api": PROVIDER_API_OPENAI_RESPONSE,
        }
        mut.llm_chat_request(botengine, content)

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    def test_chat_completion_missing_messages_rejected(self):
        """Chat Completion (default) request without 'messages' should be rejected."""
        botengine, location, mut = self._setup()

        content = {
            "intelligence_id": "some_id",
            "reference": "ref_1",
            "provider_api": PROVIDER_API_OPENAI_CHAT_COMPLETION,
        }
        mut.llm_chat_request(botengine, content)

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    def test_openai_params_exclude_routing_fields(self):
        """Routing fields should be excluded from openai_params."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content = self._make_chat_request_content(
            mock.intelligence_id,
            argument={"task": "test"},
            provider_api=PROVIDER_API_OPENAI_CHAT_COMPLETION,
        )
        mut.llm_chat_request(botengine, content)

        params = mut._pending_requests["ref_1"]["openai_params"]
        assert "intelligence_id" not in params
        assert "reference" not in params
        assert "argument" not in params
        assert "provider_api" not in params

    def test_openai_params_include_metadata(self):
        """openai_params should include metadata with bundle_id and microservice name."""
        botengine, location, mut = self._setup()
        mock = self._add_mock_microservice(botengine, location)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        params = mut._pending_requests["ref_1"]["openai_params"]
        assert "metadata" in params
        assert "bundle_id" in params["metadata"]
        assert params["metadata"]["microservice"] == "MockRequestingMicroservice"


# ===========================================================================
# Intelligence.track_llm_usage tests
# ===========================================================================

class MinimalIntelligence(Intelligence):
    """Minimal Intelligence subclass that does NOT override track_llm_usage,
    allowing tests to exercise the base-class implementation directly."""

    def __init__(self, botengine, parent):
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        pass

    def new_version(self, botengine):
        pass


class TestIntelligenceTrackLLMUsage:
    """Tests for Intelligence.track_llm_usage() and related helpers."""

    def _make_microservice(self):
        botengine = BotEnginePyTest({})
        botengine.reset()
        location = Location(botengine, 12345)
        location.initialize(botengine)
        location.new_version(botengine)
        ms = MinimalIntelligence(botengine, location)
        return botengine, ms

    def test_init_and_auto_initialize(self):
        """_init_llm_usage() creates zeroed structure; track/get auto-init when missing."""
        botengine, ms = self._make_microservice()
        ms._init_llm_usage()

        assert ms.llm_usage["requests"] == 0
        assert ms.llm_usage["prompt_tokens"] == 0
        assert ms.llm_usage["completion_tokens"] == 0
        assert ms.llm_usage["total_tokens"] == 0
        assert ms.llm_usage["cost_usd"] == 0.0
        assert ms.llm_usage["by_provider"] == {}
        assert ms.llm_usage["by_model"] == {}

        # Auto-init from track_llm_usage
        delattr(ms, "llm_usage")
        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini", {})
        assert hasattr(ms, "llm_usage")

        # Auto-init from get_llm_usage
        delattr(ms, "llm_usage")
        usage = ms.get_llm_usage(botengine)
        assert usage["requests"] == 0

    def test_token_and_request_accumulation(self):
        """Requests/tokens accumulate; missing token fields default to 0."""
        botengine, ms = self._make_microservice()
        ms._init_llm_usage()

        # Empty usage — defaults to zero
        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini", {})
        assert ms.llm_usage["requests"] == 1
        assert ms.llm_usage["prompt_tokens"] == 0

        # Accumulates tokens across calls
        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini",
                           {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini",
                           {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300})

        assert ms.llm_usage["requests"] == 3
        assert ms.llm_usage["prompt_tokens"] == 300
        assert ms.llm_usage["completion_tokens"] == 150
        assert ms.llm_usage["total_tokens"] == 450

    def test_cost_tracking(self):
        """Cost accumulates when provided; cost_usd=None leaves total unchanged."""
        botengine, ms = self._make_microservice()
        ms._init_llm_usage()

        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini", {}, cost_usd=None)
        assert ms.llm_usage["cost_usd"] == 0.0

        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini", {}, cost_usd=0.005)
        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini", {}, cost_usd=0.010)
        assert abs(ms.llm_usage["cost_usd"] - 0.015) < 1e-9

    def test_by_provider_and_model_breakdown(self):
        """Usage tracked separately per provider and model with accumulation."""
        botengine, ms = self._make_microservice()
        ms._init_llm_usage()

        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini",
                           {"total_tokens": 100}, cost_usd=0.002)
        ms.track_llm_usage(botengine, "openai", "gpt-4o",
                           {"total_tokens": 200}, cost_usd=0.010)
        ms.track_llm_usage(botengine, "anthropic", "claude-3-haiku",
                           {"total_tokens": 300}, cost_usd=None)

        # By provider
        assert ms.llm_usage["by_provider"]["openai"]["requests"] == 2
        assert ms.llm_usage["by_provider"]["openai"]["total_tokens"] == 300
        assert abs(ms.llm_usage["by_provider"]["openai"]["cost_usd"] - 0.012) < 1e-9
        assert ms.llm_usage["by_provider"]["anthropic"]["requests"] == 1
        assert ms.llm_usage["by_provider"]["anthropic"]["total_tokens"] == 300
        assert ms.llm_usage["by_provider"]["anthropic"]["cost_usd"] == 0.0

        # By model
        assert ms.llm_usage["by_model"]["gpt-4o-mini"]["requests"] == 1
        assert ms.llm_usage["by_model"]["gpt-4o-mini"]["total_tokens"] == 100
        assert ms.llm_usage["by_model"]["gpt-4o"]["requests"] == 1
        assert ms.llm_usage["by_model"]["gpt-4o"]["total_tokens"] == 200
        assert ms.llm_usage["by_model"]["claude-3-haiku"]["total_tokens"] == 300

    def test_get_returns_copy_and_reset_clears(self):
        """get_llm_usage() returns a defensive copy; reset_llm_usage() zeroes everything."""
        botengine, ms = self._make_microservice()
        ms._init_llm_usage()

        ms.track_llm_usage(botengine, "openai", "gpt-4o-mini",
                           {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                           cost_usd=0.005)

        # Copy — mutating it doesn't affect internal state
        usage = ms.get_llm_usage(botengine)
        usage["requests"] = 999
        assert ms.llm_usage["requests"] == 1

        # Reset clears all
        ms.reset_llm_usage(botengine)
        assert ms.llm_usage["requests"] == 0
        assert ms.llm_usage["prompt_tokens"] == 0
        assert ms.llm_usage["completion_tokens"] == 0
        assert ms.llm_usage["total_tokens"] == 0
        assert ms.llm_usage["cost_usd"] == 0.0
        assert ms.llm_usage["by_provider"] == {}
        assert ms.llm_usage["by_model"] == {}
