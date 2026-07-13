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

        gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        groq_api_key = os.getenv("GROQ_API_KEY", "")

        # Initialize Google Gemini 3.5 Flash
        if gemini_api_key.strip():
            self.gemini_llm = ChatGoogleGenerativeAI(
                model="gemini-3.5-flash",
                google_api_key=gemini_api_key,
                temperature=0.7
            )
            log.info("Google Gemini 3.5 Flash engine initialized.")
        else:
            self.gemini_llm = None
            log.warning("GEMINI_API_KEY is missing or empty. Gemini engine will not be available.")

        # Initialize Groq Cloud (Llama 3.3 70B)
        if groq_api_key.strip():
            self.groq_llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=groq_api_key,
                temperature=0.7
            )
            log.info("Groq Llama 3.3 70B engine initialized (Fallback).")
        else:
            self.groq_llm = None
            log.warning("GROQ_API_KEY is missing or empty. Groq fallback engine will not be available.")

        self.history_file_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "chat_history.json"
        )
        self.locks: Dict[str, asyncio.Lock] = {}

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
            
            # Keep only the last 10 messages for context
            data[session_id] = [_serialize_message(msg) for msg in history[-10:]]
            
            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log.error("Failed to save chat history for session %s: %s", session_id, e)

    async def generate_response(self, session_id: str, user_message: str) -> str:
        # Get or create a lock specifically for this session to handle sequential ordering
        if session_id not in self.locks:
            self.locks[session_id] = asyncio.Lock()
        session_lock = self.locks[session_id]

        async with session_lock:
            history = await asyncio.to_thread(self._load_history_unsafe, session_id)
            
            # Append new user message to the active history
            history.append(HumanMessage(content=user_message))
            
            # Slice messages to the last 10 for context window limit
            context_messages = history[-10:]

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

            # Try Google Gemini first
            if self.gemini_llm:
                try:
                    log.info("Attempting Gemini API call for session %s...", session_id)
                    response = await self.gemini_llm.ainvoke(llm_messages)
                    ai_content = _extract_text(response.content)
                    engine_used = "Gemini"
                except Exception as e:
                    log.warning("Gemini API call failed for session %s, attempting fallback: %s", session_id, e)

            # Fallback to Groq if Gemini failed or wasn't configured
            if not ai_content and self.groq_llm:
                try:
                    log.info("Attempting Groq Llama 3.3 fallback call for session %s...", session_id)
                    response = await self.groq_llm.ainvoke(llm_messages)
                    ai_content = _extract_text(response.content)
                    engine_used = "Groq"
                except Exception as e:
                    log.error("Groq fallback call also failed for session %s: %s", session_id, e)
                    raise RuntimeError(f"Both Google Gemini and Groq API calls failed. Error: {e}")

            if not ai_content:
                raise RuntimeError("No LLM service is available or successfully responded.")

            # Update and save history
            history.append(AIMessage(content=ai_content))
            await asyncio.to_thread(self._save_history_unsafe, session_id, history)

        log.info("Successfully generated response for session %s using %s.", session_id, engine_used)
        return ai_content
