import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from app.services.llm_service import LLMService, _serialize_message, _deserialize_message
from langchain_core.messages import HumanMessage, AIMessage

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
            svc.gemini_llm = MagicMock()
            svc.groq_llm = MagicMock()
            
            # Setup mock invoke to fail for Gemini and succeed for Groq
            async def mock_gemini_ainvoke(*args, **kwargs):
                raise ValueError("Gemini quota exceeded")
                
            async def mock_groq_ainvoke(*args, **kwargs):
                mock_response = MagicMock()
                mock_response.content = "Groq response"
                return mock_response
                
            svc.gemini_llm.ainvoke = mock_gemini_ainvoke
            svc.groq_llm.ainvoke = mock_groq_ainvoke
            
            # Call generate_response
            reply = await svc.generate_response("session-1", "test prompt")
            
            # Should fall back and return Groq response
            assert reply == "Groq response"
            
            # Check history saved
            history = svc._load_history_unsafe("session-1")
            assert len(history) == 2
            assert isinstance(history[0], HumanMessage)
            assert history[0].content == "test prompt"
            assert isinstance(history[1], AIMessage)
            assert history[1].content == "Groq response"

def test_channel_store():
    from app.utils.channel_store import enable_free_response, disable_free_response, is_free_response_enabled
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_channels_file = os.path.join(tmpdir, "free_channels.json")
        with patch("app.utils.channel_store.CHANNELS_PATH", temp_channels_file):
            # Initially false
            assert not is_free_response_enabled(999)
            
            # Enable it
            enable_free_response(999)
            assert is_free_response_enabled(999)
            
            # Disable it
            disable_free_response(999)
            assert not is_free_response_enabled(999)

