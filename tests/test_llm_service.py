import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from app.services.llm_service import LLMService, _serialize_message, _deserialize_message, _strip_leaked_speaker_labels
from langchain_core.messages import HumanMessage, AIMessage

def test_strip_leaked_speaker_labels_leading():
    text = "김은성: 발표 잘 될 거야! 긴장하지 마."
    assert _strip_leaked_speaker_labels(text, ["김은성", "한태율"]) == "발표 잘 될 거야! 긴장하지 마."

def test_strip_leaked_speaker_labels_hallucinated_turn():
    text = "그래, 잘 될 거야!\n김은성: 고마워\n한태율: 힘내"
    assert _strip_leaked_speaker_labels(text, ["김은성", "한태율"]) == "그래, 잘 될 거야!"

def test_strip_leaked_speaker_labels_no_match_untouched():
    text = "결론: 오늘 운세는 좋아."
    assert _strip_leaked_speaker_labels(text, ["김은성", "한태율"]) == text

def test_serialization():
    msg = HumanMessage(content="hello")
    serialized = _serialize_message(msg)
    assert serialized == {"role": "user", "content": "hello"}
    
    deserialized = _deserialize_message(serialized)
    assert isinstance(deserialized, HumanMessage)
    assert deserialized.content == "hello"

    msg_ai = AIMessage(content="world")
    serialized_ai = _serialize_message(msg_ai)
    assert serialized_ai == {"role": "ai", "content": "world"}
    
    deserialized_ai = _deserialize_message(serialized_ai)
    assert isinstance(deserialized_ai, AIMessage)
    assert deserialized_ai.content == "world"

@pytest.mark.asyncio
async def test_llm_service_fallback_behavior():
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = os.path.join(tmpdir, "chat_history.json")
        
        # Patch the history file path to be a temp file
        with patch("app.services.llm_service.LLMService.__init__", lambda self: None):
            svc = LLMService()
            svc.history_file_path = history_file
            svc.locks = {}
            svc.gemini_api_key = ""
            svc.groq_api_key = ""
            svc.gemini_llm = MagicMock()
            svc.groq_llm = MagicMock()

            # Setup mock invoke to fail for Gemini and succeed for Groq
            async def mock_gemini_ainvoke(*args, **kwargs):
                raise ValueError("Gemini quota exceeded")

            async def mock_groq_ainvoke(*args, **kwargs):
                mock_response = MagicMock()
                mock_response.content = "Groq response"
                mock_response.tool_calls = None
                return mock_response

            svc.gemini_llm.ainvoke = mock_gemini_ainvoke
            svc.groq_llm.ainvoke = mock_groq_ainvoke
            # bind_tools()는 자기 자신을 반환하게 해서 위 ainvoke 목이 그대로 쓰이게 한다
            svc.gemini_llm.bind_tools = lambda tools: svc.gemini_llm
            svc.groq_llm.bind_tools = lambda tools: svc.groq_llm

            # Call generate_response
            reply, attachments = await svc.generate_response("session-1", "test prompt")

            # Should fall back and return Groq response
            assert reply == "Groq response"
            assert attachments == []
            
            # Check history saved
            history = svc._load_history_unsafe("session-1")
            assert len(history) == 2
            assert isinstance(history[0], HumanMessage)
            assert history[0].content == "test prompt"
            assert isinstance(history[1], AIMessage)
            assert history[1].content == "Groq response"

def test_channel_store():
    from app.utils.channel_settings import enable_free_response, disable_free_response, is_free_response_enabled

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_channels_file = os.path.join(tmpdir, "free_channels.json")
        with patch("app.utils.channel_settings.CHANNELS_PATH", temp_channels_file):
            # Initially false
            assert not is_free_response_enabled(999)
            
            # Enable it
            enable_free_response(999)
            assert is_free_response_enabled(999)
            
            # Disable it
            disable_free_response(999)
            assert not is_free_response_enabled(999)

def test_channel_settings():
    import tempfile
    from app.utils.channel_settings import get_channel_settings, set_channel_setting
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_settings_file = os.path.join(tmpdir, "channel_settings.json")
        with patch("app.utils.channel_settings.SETTINGS_PATH", temp_settings_file):
            # Default values
            settings = get_channel_settings(12345)
            assert settings["temperature"] == 0.7
            assert settings["model"] == "Gemini"
            
            # Set values
            set_channel_setting(12345, "temperature", 1.0)
            set_channel_setting(12345, "model", "Groq")
            
            # Read back
            settings = get_channel_settings(12345)
            assert settings["temperature"] == 1.0
            assert settings["model"] == "Groq"

@pytest.mark.asyncio
async def test_rp_skip_reply_when_judge_says_skip(tmp_path, monkeypatch):
    """제3자끼리의 대화로 판정되면 응답 없이(None) 대화 기록만 남긴다."""
    from app.utils import rp_store

    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    rp_store.start_room("rp-skip", opening="장면")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = os.path.join(tmpdir, "chat_history.json")
        with patch("app.services.llm_service.LLMService.__init__", lambda self: None):
            svc = LLMService()
            svc.history_file_path = history_file
            svc.locks = {}
            svc.gemini_api_key = "x"
            svc.groq_api_key = ""
            svc.gemini_llm = MagicMock()
            svc.gemini_llm.bind_tools = lambda tools: svc.gemini_llm

            async def mock_ainvoke(messages, stop=None):
                resp = MagicMock()
                resp.tool_calls = None
                if len(messages) == 1 and "REPLY 또는 SKIP" in str(messages[0].content):
                    resp.content = "SKIP"
                else:
                    resp.content = "이건 호출되면 안 됨"
                return resp

            svc.gemini_llm.ainvoke = mock_ainvoke

            reply, attachments = await svc.generate_response(
                "rp-skip", "다른사람: 안녕", author_name="관찰자"
            )

            assert reply is None
            assert attachments == []
            history = svc._load_history_unsafe("rp-skip")
            assert len(history) == 1
            assert isinstance(history[0], HumanMessage)


@pytest.mark.asyncio
async def test_rp_replies_when_judge_says_reply(tmp_path, monkeypatch):
    from app.utils import rp_store

    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    rp_store.start_room("rp-reply", opening="장면")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = os.path.join(tmpdir, "chat_history.json")
        with patch("app.services.llm_service.LLMService.__init__", lambda self: None):
            svc = LLMService()
            svc.history_file_path = history_file
            svc.locks = {}
            svc.gemini_api_key = "x"
            svc.groq_api_key = ""
            svc.gemini_llm = MagicMock()
            svc.gemini_llm.bind_tools = lambda tools: svc.gemini_llm

            async def mock_ainvoke(messages, stop=None):
                resp = MagicMock()
                resp.tool_calls = None
                if len(messages) == 1 and "REPLY 또는 SKIP" in str(messages[0].content):
                    resp.content = "REPLY"
                else:
                    resp.content = "정상 응답이야."
                return resp

            svc.gemini_llm.ainvoke = mock_ainvoke

            reply, attachments = await svc.generate_response(
                "rp-reply", "한태율아 뭐해", author_name="유저"
            )

            assert reply == "정상 응답이야."


@pytest.mark.asyncio
async def test_rp_direct_address_skips_judge(tmp_path, monkeypatch):
    """멘션/DM 등으로 직접 불렸으면 판정 없이 항상 응답한다."""
    from app.utils import rp_store

    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    rp_store.start_room("rp-direct", opening="장면")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = os.path.join(tmpdir, "chat_history.json")
        with patch("app.services.llm_service.LLMService.__init__", lambda self: None):
            svc = LLMService()
            svc.history_file_path = history_file
            svc.locks = {}
            svc.gemini_api_key = "x"
            svc.groq_api_key = ""
            svc.gemini_llm = MagicMock()
            svc.gemini_llm.bind_tools = lambda tools: svc.gemini_llm

            call_count = {"n": 0}

            async def mock_ainvoke(messages, stop=None):
                call_count["n"] += 1
                resp = MagicMock()
                resp.tool_calls = None
                resp.content = "직접 응답이야."
                return resp

            svc.gemini_llm.ainvoke = mock_ainvoke

            reply, attachments = await svc.generate_response(
                "rp-direct", "한태율아", author_name="유저", is_direct_address=True
            )

            assert reply == "직접 응답이야."
            assert call_count["n"] == 1  # 판정 호출 없이 바로 생성 1회만


@pytest.mark.asyncio
async def test_rp_retries_once_on_truncated_response(tmp_path, monkeypatch):
    from app.utils import rp_store

    monkeypatch.setattr(rp_store, "ROOMS_PATH", str(tmp_path / "rp_rooms.json"))
    rp_store.start_room("rp-retry", opening="장면")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = os.path.join(tmpdir, "chat_history.json")
        with patch("app.services.llm_service.LLMService.__init__", lambda self: None):
            svc = LLMService()
            svc.history_file_path = history_file
            svc.locks = {}
            svc.gemini_api_key = "x"
            svc.groq_api_key = ""
            svc.gemini_llm = MagicMock()
            svc.gemini_llm.bind_tools = lambda tools: svc.gemini_llm

            call_count = {"n": 0}

            async def mock_ainvoke(messages, stop=None):
                call_count["n"] += 1
                resp = MagicMock()
                resp.tool_calls = None
                resp.content = "그는 손을" if call_count["n"] == 1 else "그는 손을 내밀었다."
                return resp

            svc.gemini_llm.ainvoke = mock_ainvoke

            reply, attachments = await svc.generate_response(
                "rp-retry", "장면 진행해줘", author_name="유저", is_direct_address=True
            )

            assert reply == "그는 손을 내밀었다."
            assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_llm_service_reset_history():
    from app.services.llm_service import LLMService
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_history_file = os.path.join(tmpdir, "chat_history.json")
        with patch("app.services.llm_service.LLMService.__init__", lambda self: None):
            svc = LLMService()
            svc.history_file_path = temp_history_file
            svc.locks = {}
            
            # Write dummy history
            svc._save_history_unsafe("session-reset", [HumanMessage(content="hello")])
            assert len(svc._load_history_unsafe("session-reset")) == 1
            
            # Reset history
            await svc.reset_history("session-reset")
            assert len(svc._load_history_unsafe("session-reset")) == 0


