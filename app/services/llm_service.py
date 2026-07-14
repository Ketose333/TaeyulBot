import os
import json
import logging
import asyncio
from typing import List, Dict

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.utils.file_tool import FS_TOOLS
from app.utils.media_tools import MediaSink, make_media_tools

_MAX_TOOL_ROUNDS = 4

# Gemini 무료 티어의 이미지 생성 모델(nano-banana-pro-preview 등) 쿼터가 0으로 막혀 있고
# 결제 계정을 연결하지 않기로 해서, 대안이 정해지기 전까지 이미지 생성 도구를 LLM에서 임시로 뺀다.
# 음성 생성(TTS)은 별도 모델이라 영향 없음.
_ENABLE_IMAGE_GENERATION = False

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

def _strip_leaked_speaker_labels(text: str, speaker_names: List[str]) -> str:
    """대화 기록의 "이름: 내용" 표기를 모델이 자기 응답에서 흉내내는 걸 방지하는 후처리.
    ausboss/DiscordLangAgent의 detect_and_replace와 동일한 안전망(stop 시퀀스가 못 막았을 때 대비)."""
    result = text
    for name in filter(None, speaker_names):
        marker = f"{name}:"
        # 응답 맨 앞에 자기/상대 이름표가 붙어 나온 경우 제거
        if result.startswith(marker):
            result = result[len(marker):].lstrip()
        # 중간에 새 화자 턴을 지어내기 시작한 경우, 그 지점부터 잘라낸다
        cut_at = result.find(f"\n{marker}")
        if cut_at != -1:
            result = result[:cut_at].rstrip()
    return result


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

    async def _invoke_with_tools(self, eng_instance, messages: list, allow_fs_tools: bool, media_sink, stop: list = None):
        if not hasattr(eng_instance, "bind_tools"):
            return await eng_instance.ainvoke(messages, stop=stop)

        # 파일시스템 도구(FS_TOOLS)는 owner 세션에서만, 이미지/음성 생성 도구는
        # 게이팅 없이 전체 유저에게 항상 노출한다.
        tools = list(FS_TOOLS) if allow_fs_tools else []
        tools += make_media_tools(media_sink, self.gemini_api_key, include_image=_ENABLE_IMAGE_GENERATION)
        tools_by_name = {t.name: t for t in tools}

        bound = eng_instance.bind_tools(tools)
        current_messages = list(messages)
        response = await bound.ainvoke(current_messages, stop=stop)

        rounds = 0
        while getattr(response, "tool_calls", None) and rounds < _MAX_TOOL_ROUNDS:
            current_messages.append(response)
            for call in response.tool_calls:
                tool_fn = tools_by_name.get(call["name"])
                if tool_fn is None:
                    result = f"알 수 없는 도구: {call['name']}"
                else:
                    try:
                        result = await tool_fn.ainvoke(call["args"])
                    except Exception as e:
                        result = f"도구 실행 실패: {e}"
                current_messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
            response = await bound.ainvoke(current_messages, stop=stop)
            rounds += 1

        return response

    async def generate_response(
        self, session_id: str, user_message: str, author_id: str = None, author_name: str = None
    ):
        """반환값: (ai_text, attachments). attachments는 [(bytes, filename), ...]이며
        이미지/음성 생성 tool이 호출되지 않았으면 빈 리스트."""
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
            # 참고: ausboss/DiscordLangAgent MAINTEMPLATE — 장문 설명 대신 실제 발화 예시(few-shot)로
            # 톤을 보여주는 방식. 대화 기록 "이름: 내용" 표기가 모델 응답에 새는 걸 막는 지시만 남기고
            # 나머지는 위 페르소나 문서에 이미 있으므로 중복 서술하지 않는다.
            prompt_sections.append(
                "다음은 한태율이 실제로 답하는 예시입니다(형식만 참고, 문장 그대로 반복 금지):\n"
                "한태율: 응, 좋아 바로 확인해볼게.\n"
                "한태율: 맞아 그 지적 정확해, 바로 고칠게.\n\n"
                "대화 기록의 \"이름: 내용\" 표기는 발화자 구분용일 뿐 당신이 따라 할 형식이 아닙니다. "
                "답변 앞에 \"이름:\"을 붙이거나 새 화자 턴을 지어내지 말고, 본문 안에서만 이름을 언급해 "
                "발언자를 구분하세요."
            )
            system_message = SystemMessage(content="\n\n---\n\n".join(prompt_sections))
            llm_messages = [system_message] + context_messages

            # DiscordLangAgent의 stop_sequence(f"{name}:") 패턴: 모델이 새 화자 턴을 지어내기
            # 시작하는 순간 생성을 끊는다.
            stop_sequences = list(filter(None, {f"{author_name}:" if author_name else None, "한태율:"}))

            ai_content = ""
            engine_used = ""
            media_sink = MediaSink()

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
                        response = await self._invoke_with_tools(
                            eng_instance, llm_messages, is_owner, media_sink, stop=stop_sequences
                        )
                        ai_content = _extract_text(response.content)
                        ai_content = _strip_leaked_speaker_labels(ai_content, [author_name, "한태율"])
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
        return ai_content, media_sink.items
