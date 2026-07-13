import os
import json
import logging
import asyncio
from typing import List, Dict

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

log = logging.getLogger(__name__)

def _serialize_message(msg: BaseMessage) -> dict:
    if isinstance(msg, HumanMessage):
        return {"role": "user", "content": msg.content}
    elif isinstance(msg, AIMessage):
        return {"role": "ai", "content": msg.content}
    return {"role": "user" if msg.type == "human" else "ai", "content": msg.content}

def _deserialize_message(data: dict) -> BaseMessage:
    if data["role"] == "user":
        return HumanMessage(content=data["content"])
    else:
        return AIMessage(content=data["content"])

def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                texts.append(part["text"])
            elif isinstance(part, str):
                texts.append(part)
        return "".join(texts)
    return str(content)

class LLMService:
    def __init__(self):
        # LangSmith tracing (Optional)
        langchain_api_key = os.getenv("LANGCHAIN_API_KEY", "")
        if langchain_api_key.strip():
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = langchain_api_key
            os.environ["LANGCHAIN_PROJECT"] = "taeyulbot-llm-chat"
            log.info("LangSmith tracing enabled.")
        else:
            log.info("LangSmith tracing not enabled (API key missing or empty).")

        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")

        self.history_file_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "chat_history.json"
        )
        self.locks: Dict[str, asyncio.Lock] = {}

    def _get_llm_engine(self, engine_name: str, temperature: float):
        # Support unit test mocks
        if engine_name.lower() == "gemini" and hasattr(self, "gemini_llm") and self.gemini_llm:
            return self.gemini_llm
        if engine_name.lower() == "groq" and hasattr(self, "groq_llm") and self.groq_llm:
            return self.groq_llm

        if engine_name.lower() == "gemini":
            if self.gemini_api_key.strip():
                return ChatGoogleGenerativeAI(
                    model="gemini-3.5-flash",
                    google_api_key=self.gemini_api_key,
                    temperature=temperature
                )
            return None
        elif engine_name.lower() == "groq":
            if self.groq_api_key.strip():
                return ChatGroq(
                    model="llama-3.3-70b-versatile",
                    groq_api_key=self.groq_api_key,
                    temperature=temperature
                )
            return None
        return None

    async def reset_history(self, session_id: str) -> None:
        if session_id not in self.locks:
            self.locks[session_id] = asyncio.Lock()
        session_lock = self.locks[session_id]

        async with session_lock:
            try:
                if os.path.exists(self.history_file_path):
                    with open(self.history_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if session_id in data:
                        del data[session_id]
                        with open(self.history_file_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=4)
                        log.info("Reset chat history for session %s.", session_id)
            except Exception as e:
                log.error("Failed to reset history for session %s: %s", session_id, e)

    def _load_history_unsafe(self, session_id: str) -> List[BaseMessage]:
        if not os.path.exists(self.history_file_path):
            return []
        try:
            with open(self.history_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            session_data = data.get(session_id, [])
            return [_deserialize_message(item) for item in session_data]
        except Exception as e:
            log.error("Failed to load chat history for session %s: %s", session_id, e)
            return []

    def _save_history_unsafe(self, session_id: str, history: List[BaseMessage]) -> None:
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.history_file_path), exist_ok=True)
            
            data = {}
            if os.path.exists(self.history_file_path):
                with open(self.history_file_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = {}
            
            # Keep only the last 30 messages for context (expanded from 10!)
            data[session_id] = [_serialize_message(msg) for msg in history[-30:]]
            
            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log.error("Failed to save chat history for session %s: %s", session_id, e)

    async def generate_response(self, session_id: str, user_message: str) -> str:
        # Load channel settings
        from app.utils.channel_settings import get_channel_settings
        try:
            channel_id = int(session_id)
        except ValueError:
            channel_id = 0

        settings = get_channel_settings(channel_id)
        preferred_model = settings["model"]
        temperature = settings["temperature"]

        # Get or create a lock specifically for this session to handle sequential ordering
        if session_id not in self.locks:
            self.locks[session_id] = asyncio.Lock()
        session_lock = self.locks[session_id]

        async with session_lock:
            history = await asyncio.to_thread(self._load_history_unsafe, session_id)
            
            # Append new user message to the active history
            history.append(HumanMessage(content=user_message))
            
            # Slice messages to the last 30 for context window limit
            context_messages = history[-30:]

            # System prompt to ensure polite, natural Korean and defined persona
            system_message = SystemMessage(
                content=(
                    "당신은 사주와 운세를 봐주고 편안하게 대화를 나눌 수 있는 친절하고 다정한 디스코드 봇 '한태율'입니다. "
                    "사용자에게 반말이나 거친 표현은 피하고, 정중하고 부드러운 한국어 구어체(해요체)로 답변해 주세요."
                )
            )
            llm_messages = [system_message] + context_messages

            ai_content = ""
            engine_used = ""

            # Determine primary and fallback engines based on settings
            if preferred_model == "Groq":
                engines = [("Groq", self._get_llm_engine("groq", temperature)), 
                           ("Gemini", self._get_llm_engine("gemini", temperature))]
            else:
                engines = [("Gemini", self._get_llm_engine("gemini", temperature)), 
                           ("Groq", self._get_llm_engine("groq", temperature))]

            # Call primary and then fallback if it fails
            for eng_name, eng_instance in engines:
                if eng_instance:
                    try:
                        log.info("Attempting %s API call (temp=%s) for session %s...", eng_name, temperature, session_id)
                        response = await eng_instance.ainvoke(llm_messages)
                        ai_content = _extract_text(response.content)
                        engine_used = eng_name
                        break
                    except Exception as e:
                        log.warning("%s API call failed for session %s, attempting fallback: %s", eng_name, session_id, e)

            if not ai_content:
                raise RuntimeError("Both Google Gemini and Groq API calls failed or were not configured.")

            # Update and save history
            history.append(AIMessage(content=ai_content))
            await asyncio.to_thread(self._save_history_unsafe, session_id, history)

        log.info("Successfully generated response for session %s using %s.", session_id, engine_used)
        return ai_content
