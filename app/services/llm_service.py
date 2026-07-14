import os
import json
import logging
import asyncio
from typing import List, Dict

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.utils.file_tool import FS_TOOLS

_FS_TOOLS_BY_NAME = {t.name: t for t in FS_TOOLS}
_MAX_TOOL_ROUNDS = 4

log = logging.getLogger(__name__)

_PERSONA_DIR = os.path.join(os.path.dirname(__file__), "..", "persona")


def _read_persona_file(filename: str) -> str:
    path = os.path.join(_PERSONA_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_persona_prompt() -> str:
    # SOUL/IDENTITY/EMOTION은 항상 로드되는 페르소나 원문. MEMORY/USER는 오너 개인정보를
    # 담고 있어 owner 세션에서만 별도로 주입한다(AGENTS.md의 "MEMORY.md는 메인 세션에서만" 규칙과 동일).
    sections = [_read_persona_file(f) for f in ("SOUL.md", "IDENTITY.md", "EMOTION.md")]
    return "\n\n---\n\n".join(s for s in sections if s)


def _build_owner_context_prompt() -> str:
    sections = [_read_persona_file(f) for f in ("USER.md", "MEMORY.md")]
    return "\n\n---\n\n".join(s for s in sections if s)

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

        self.owner_discord_id = os.getenv("OWNER_DISCORD_ID", "").strip()
        self.persona_prompt = _build_persona_prompt()
        self.owner_context_prompt = _build_owner_context_prompt()

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

    async def _invoke_with_tools(self, eng_instance, messages: list, allow_fs_tools: bool):
        if not allow_fs_tools or not hasattr(eng_instance, "bind_tools"):
            return await eng_instance.ainvoke(messages)

        bound = eng_instance.bind_tools(FS_TOOLS)
        current_messages = list(messages)
        response = await bound.ainvoke(current_messages)

        rounds = 0
        while getattr(response, "tool_calls", None) and rounds < _MAX_TOOL_ROUNDS:
            current_messages.append(response)
            for call in response.tool_calls:
                tool_fn = _FS_TOOLS_BY_NAME.get(call["name"])
                if tool_fn is None:
                    result = f"알 수 없는 도구: {call['name']}"
                else:
                    try:
                        result = await tool_fn.ainvoke(call["args"])
                    except Exception as e:
                        result = f"도구 실행 실패: {e}"
                current_messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
            response = await bound.ainvoke(current_messages)
            rounds += 1

        return response

    async def generate_response(
        self, session_id: str, user_message: str, author_id: str = None, author_name: str = None
    ) -> str:
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
            
            # 여러 디스코드 사용자를 구분/비교할 수 있도록 "이름: 내용" 형태로 저장한다
            # (참고: ausboss/DiscordLangAgent의 f"{name}: {message_content}" 패턴).
            stored_message = f"{author_name}: {user_message}" if author_name else user_message
            history.append(HumanMessage(content=stored_message))
            
            # Slice messages to the last 30 for context window limit
            context_messages = history[-30:]

            # 페르소나 원문(SOUL/IDENTITY/EMOTION) 기반 시스템 프롬프트.
            # owner(OWNER_DISCORD_ID) 세션에서만 USER.md/MEMORY.md(개인정보 포함)를 추가로 주입한다.
            persona_prompt = getattr(self, "persona_prompt", "") or _build_persona_prompt()
            owner_discord_id = getattr(self, "owner_discord_id", "")
            owner_context_prompt = getattr(self, "owner_context_prompt", "")

            is_owner = bool(owner_discord_id and author_id is not None and str(author_id) == owner_discord_id)

            prompt_sections = [persona_prompt] if persona_prompt else []
            if is_owner and owner_context_prompt:
                prompt_sections.append(owner_context_prompt)
            prompt_sections.append(
                "당신은 사주와 운세를 봐주는 디스코드 봇이기도 합니다. 위 페르소나 톤을 유지하면서 "
                "사주/운세 질문에도 자연스럽게 답해 주세요. 대화 기록의 사용자 메시지는 "
                "\"이름: 내용\" 형태로 표시됩니다. 같은 채널에 여러 사람이 섞여 있을 수 있으니 "
                "이름으로 발언자를 구분하고, 여러 사용자의 말을 비교/요약해 달라는 요청에는 "
                "이름을 명시해서 답하세요."
            )
            system_message = SystemMessage(content="\n\n---\n\n".join(prompt_sections))
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
                        response = await self._invoke_with_tools(eng_instance, llm_messages, is_owner)
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
