#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from collections import deque
from datetime import datetime

import discord

try:
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.rp.rp_engine import (
        Ctx,
        acquire_runtime_lock,
        end_room,
        generate_rp_opening,
        generate_rp_reply,
        ingest_plain_chat,
        get_channel_user_alias,
        set_channel_user_alias,
        is_room_active,
        load_room,
        save_room,
        release_runtime_lock,
        runtime_healthcheck,
        start_room,
        touch_runtime_lock,
        _load_active_rooms,
        _save_active_rooms,
    )
except ModuleNotFoundError:
    import sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / 'utility').exists():
            sys.path.append(str(_p))
            break
    from utility.common.env_prefer_dotenv import load_env_prefer_dotenv
    from utility.rp.rp_engine import (
        Ctx,
        acquire_runtime_lock,
        end_room,
        generate_rp_opening,
        generate_rp_reply,
        ingest_plain_chat,
        get_channel_user_alias,
        set_channel_user_alias,
        is_room_active,
        load_room,
        save_room,
        release_runtime_lock,
        runtime_healthcheck,
        start_room,
        touch_runtime_lock,
        _load_active_rooms,
        _save_active_rooms,
    )

ALLOWED_PREFIX = '!rp'
MAX_SEEN_MESSAGE_IDS = 2000

GUIDE_PATH = Path('/home/user/.openclaw/workspace/utility/rp/rp_guide.md')
COMMAND_SEEN_PATH = Path('/home/user/.openclaw/workspace/memory/rp_rooms/_command_seen.json')

def _load_rp_guide_text() -> str:
    try:
        return GUIDE_PATH.read_text(encoding='utf-8').strip()
    except Exception:
        return ''

# ---- command dedupe state ----
def _load_command_seen() -> dict[str, int]:
    try:
        import json
        if COMMAND_SEEN_PATH.exists():
            obj=json.loads(COMMAND_SEEN_PATH.read_text(encoding='utf-8'))
            if isinstance(obj, dict):
                return {str(k): int(v) for k,v in obj.items()}
    except Exception:
        pass
    return {}

def _save_command_seen(data: dict[str, int]) -> None:
    try:
        import json, time
        now=int(time.time())
        # 6시간 이상 지난 키 정리 + 최대 4000개
        data={k:v for k,v in data.items() if now-v < 21600}
        if len(data) > 4000:
            items=sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:4000]
            data=dict(items)
        COMMAND_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        COMMAND_SEEN_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass

def _mark_command_once(message_id: str) -> bool:
    import time
    seen=_load_command_seen()
    mid=str(message_id)
    if mid in seen:
        return False
    seen[mid]=int(time.time())
    _save_command_seen(seen)
    return True

def _parse_csv_ids(raw: str) -> set[str]:
    return {x.strip() for x in (raw or '').replace('\n', ',').split(',') if x.strip()}

# ---- discord runtime client ----
class RpDiscordClient(discord.Client):
    def __init__(self, *args, runtime_pid: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_channel_ids = _parse_csv_ids(os.getenv('RP_ALLOWED_CHANNEL_IDS', ''))
        self.allowed_guild_ids = _parse_csv_ids(os.getenv('RP_ALLOWED_GUILD_IDS', ''))
        self.reply_mode = (os.getenv('RP_REPLY_MODE', 'active') or 'active').strip().lower()
        self.seen_message_ids: set[str] = set()
        self.seen_order: deque[str] = deque(maxlen=MAX_SEEN_MESSAGE_IDS)
        self.runtime_pid = int(runtime_pid or os.getpid())
        self.health_recover = (os.getenv('RP_HEALTHCHECK_RECOVER', '1').strip() != '0')

    async def on_ready(self) -> None:
        print(f'RP Mode Runtime ready: {self.user}')
        if self.allowed_channel_ids:
            print(f'RP allowed channels: {sorted(self.allowed_channel_ids)}')
        if self.allowed_guild_ids:
            print(f'RP allowed guilds: {sorted(self.allowed_guild_ids)}')
        touch_runtime_lock(self.runtime_pid)
        hc = runtime_healthcheck(recover=self.health_recover)
        if not hc.get('ok', True):
            print(f"RP healthcheck issues: {hc.get('issues', [])}")
            if hc.get('recovered'):
                print(f"RP runtime recovered: {hc.get('recovered')}")

    def _log_bot_turn(self, ctx: Ctx, text: str, message_id: str = '') -> None:
        """RP 로그에 봇 발화도 함께 저장한다(사후 활용/백업 목적)."""
        if not (text or '').strip():
            return
        bot_uid = str(self.user.id) if self.user else 'bot'
        bot_name = str(self.user.display_name) if self.user and getattr(self.user, 'display_name', None) else '한태율'
        bctx = Ctx(platform=ctx.platform, channel_id=ctx.channel_id, user_id=bot_uid)
        ingest_plain_chat(bctx, text, message_id=message_id, speaker_name=bot_name)

    @staticmethod
    def _compose_opening(user_alias: str, opening: str = '', bot_name: str = 'RP') -> str:
        return generate_rp_opening(user_alias=user_alias, opening=opening, bot_name=bot_name)

    @staticmethod
    def _parent_channel_id(message: discord.Message) -> str:
        ch = message.channel
        if isinstance(ch, discord.Thread) and getattr(ch, 'parent_id', None):
            return str(ch.parent_id)
        return str(ch.id)

    def _is_mention_to_me(self, message: discord.Message) -> bool:
        if not self.user:
            return False
        return any(getattr(m, 'id', None) == self.user.id for m in (message.mentions or []))

    @staticmethod
    def _contains_any(text: str, words: list[str]) -> bool:
        t = (text or '').lower()
        return any(w in t for w in words)

    def _is_direct_call(self, message: discord.Message, content: str) -> bool:
        if self._is_mention_to_me(message):
            return True
        name_tokens = ['태율', '한태율']
        if self.user and getattr(self.user, 'display_name', None):
            name_tokens.append(str(self.user.display_name).lower())
        t = (content or '').lower()
        return any(tok in t for tok in name_tokens if tok)

    def _is_early_room_turn(self, ctx: Ctx) -> bool:
        room = load_room(ctx) or {}
        history = room.get('history') or []
        return len(history) <= 2

    def _get_room_flags(self, ctx: Ctx) -> dict:
        room = load_room(ctx) or {}
        temp = room.get('temp') if isinstance(room.get('temp'), dict) else {}
        return temp

    def _set_room_flags(self, ctx: Ctx, temp: dict) -> None:
        room = load_room(ctx)
        if not room:
            return
        room['temp'] = temp
        save_room(ctx, room)

    async def _maybe_natural_disengage(self, ctx: Ctx, message: discord.Message, content: str) -> bool:
        """True면 이번 턴은 응답하지 않음."""
        room = load_room(ctx) or {}
        participants = room.get('participants') or []
        temp = room.get('temp') if isinstance(room.get('temp'), dict) else {}
        suppressed = bool(temp.get('suppressed', False))

        direct_call = self._is_direct_call(message, content)
        disengage_cues = ['둘이', '둘만', '대기해', '잠깐 빠져', '잠깐만 빠져', '이따 불러', '쉬고 있어']

        # 명시 비개입 신호 -> 자연 이탈 1회 후 침묵
        if self._contains_any(content, disengage_cues) and direct_call:
            temp['suppressed'] = True
            temp['suppressed_at'] = datetime.now().isoformat()
            self._set_room_flags(ctx, temp)
            await message.reply('알겠어. 잠시 물러나 있을게. 필요하면 불러줘.', mention_author=False)
            return True

        if suppressed:
            # 다시 직접 호출되면 복귀
            if direct_call:
                temp['suppressed'] = False
                temp.pop('suppressed_at', None)
                self._set_room_flags(ctx, temp)
                return False
            return True

        # 제3자 대화로 보이면 자동 침묵 진입(명령어 없이 자연 이탈)
        # 조건: 참여자 2명 이상 + 나를 직접 호출하지 않음 + 다른 사람 멘션 포함
        mentions_others = any(getattr(m, 'id', None) != (self.user.id if self.user else None) for m in (message.mentions or []))
        if len(participants) >= 2 and (not direct_call) and mentions_others:
            temp['suppressed'] = True
            temp['suppressed_at'] = datetime.now().isoformat()
            self._set_room_flags(ctx, temp)
            await message.reply('둘이 이야기 이어가. 나는 잠깐 뒤로 물러나 있을게.', mention_author=False)
            return True

        return False

    def _is_allowed_message(self, message: discord.Message) -> bool:
        if self.allowed_guild_ids and message.guild and str(message.guild.id) not in self.allowed_guild_ids:
            return False
        if self.allowed_channel_ids:
            cid = str(message.channel.id)
            pcid = self._parent_channel_id(message)
            if cid not in self.allowed_channel_ids and pcid not in self.allowed_channel_ids:
                return False
        return True

    def _mark_seen(self, message_id: str) -> bool:
        if message_id in self.seen_message_ids:
            return False
        self.seen_message_ids.add(message_id)
        self.seen_order.append(message_id)
        while len(self.seen_message_ids) > MAX_SEEN_MESSAGE_IDS and self.seen_order:
            old = self.seen_order.popleft()
            self.seen_message_ids.discard(old)
        return True

    async def close(self) -> None:
        release_runtime_lock(self.runtime_pid)
        await super().close()

    @staticmethod
    def _derive_thread_title(opening: str = '') -> str:
        topic = (opening or '').strip()
        if topic:
            # 주제 지정 시 그대로 제목으로 사용(길이만 안전하게 제한)
            return topic[:90]
        # 주제 미지정 시 자연어 기본 제목
        return "새로운 장면"

    def _resolve_alias(self, ctx: Ctx, message: discord.Message) -> str:
        uid = str(message.author.id)
        alias = get_channel_user_alias(ctx, speaker_id=uid)
        if alias:
            return alias
        # 스레드면 부모 채널 호칭 설정을 상속
        ch = message.channel
        if isinstance(ch, discord.Thread) and getattr(ch, 'parent_id', None):
            pctx = Ctx(platform='discord', channel_id=str(ch.parent_id), user_id=ctx.user_id)
            alias = get_channel_user_alias(pctx, speaker_id=uid)
            if alias:
                # 이후 매턴 조회 비용 줄이기 위해 현재 룸에 저장
                set_channel_user_alias(ctx, alias, speaker_id=uid)
                return alias

        # alias 미설정 시 발화자 display_name 사용 (owner/제3자 동일 규칙)
        return message.author.display_name

    async def _start_in_thread(self, message: discord.Message, opening: str = '') -> None:
        name = self._derive_thread_title(opening)
        try:
            thread = await message.create_thread(name=name, auto_archive_duration=1440)
        except Exception as e:
            await message.reply(f'스레드 생성 실패: {e}', mention_author=False)
            return

        ctx = Ctx(platform='discord', channel_id=str(thread.id), user_id=str(message.author.id))
        parent_ctx = Ctx(platform='discord', channel_id=str(message.channel.id), user_id=str(message.author.id))
        parent_alias = get_channel_user_alias(parent_ctx, speaker_id=str(message.author.id))
        if parent_alias:
            set_channel_user_alias(ctx, parent_alias, speaker_id=str(message.author.id))

        start_room(ctx, title=name, kind='thread', opening=opening)
        room = load_room(ctx) or {}
        room['parent_channel_id'] = str(getattr(message.channel, 'id', '') or '')
        save_room(ctx, room)
        try:
            active = _load_active_rooms()
            rid = f"discord_{str(thread.id)}"
            if rid in active and isinstance(active[rid], dict):
                active[rid]['parent_channel_id'] = str(getattr(message.channel, 'id', '') or '')
                _save_active_rooms(active)
        except Exception:
            pass
        alias = self._resolve_alias(ctx, message)
        opening_text = self._compose_opening(alias, opening, bot_name=(self.user.display_name if self.user else "RP"))
        if (opening_text or '').strip():
            sent = await thread.send(opening_text)
            self._log_bot_turn(ctx, opening_text, message_id=str(getattr(sent, 'id', '') or ''))

    async def _start_in_current(self, message: discord.Message, kind: str, opening: str = '') -> None:
        ctx = Ctx(platform='discord', channel_id=str(message.channel.id), user_id=str(message.author.id))
        start_room(ctx, title=getattr(message.channel, 'name', ''), kind=kind, opening=opening)
        alias = self._resolve_alias(ctx, message)
        opening_text = self._compose_opening(alias, opening, bot_name=(self.user.display_name if self.user else "RP"))
        if (opening_text or '').strip():
            sent = await message.channel.send(opening_text)
            self._log_bot_turn(ctx, opening_text, message_id=str(getattr(sent, 'id', '') or ''))

    async def _end_in_current(self, message: discord.Message) -> None:
        ctx = Ctx(platform='discord', channel_id=str(message.channel.id), user_id=str(message.author.id))
        ok, _ = end_room(ctx)

        if (not ok) and isinstance(message.channel, discord.TextChannel):
            try:
                active = _load_active_rooms()
                parent_id = str(message.channel.id)
                owner_id = str(message.author.id)
                candidates = []
                for _, meta in active.items():
                    if not isinstance(meta, dict):
                        continue
                    if str(meta.get('parent_channel_id') or '') != parent_id:
                        continue
                    if str(meta.get('owner_id') or '') != owner_id:
                        continue
                    cid = str(meta.get('channel_id') or '')
                    updated = str(meta.get('updated_at') or '')
                    if cid:
                        candidates.append((updated, cid))
                targets = []
                if candidates:
                    candidates.sort(reverse=True)
                    targets = [candidates[0][1]]
                for cid in targets:
                    tctx = Ctx(platform='discord', channel_id=cid, user_id=owner_id)
                    ended, _ = end_room(tctx)
                    if ended:
                        try:
                            ch = await self.fetch_channel(int(cid))
                            if isinstance(ch, discord.Thread):
                                await ch.edit(archived=True, locked=False)
                        except Exception:
                            pass
                if targets:
                    ok = True
            except Exception:
                pass

        if ok and isinstance(message.channel, discord.Thread):
            try:
                await message.channel.edit(archived=True, locked=False)
            except Exception:
                pass

    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent) -> None:
        """스레드가 !rp 끝 없이 삭제된 경우 active index를 정리한다."""
        try:
            ctx = Ctx(platform='discord', channel_id=str(payload.thread_id), user_id='0')
            end_room(ctx)
        except Exception:
            pass

        # 레이스 대비: active index에 남은 stale 키를 직접 제거
        try:
            from utility.rp.rp_engine import _load_active_rooms, _save_active_rooms
            active = _load_active_rooms()
            rid = f"discord_{str(payload.thread_id)}"
            if rid in active:
                del active[rid]
                _save_active_rooms(active)
        except Exception:
            pass

    async def on_raw_thread_update(self, payload: discord.RawThreadUpdateEvent) -> None:
        """아카이브 전환 시 active index를 동기화한다."""
        try:
            data = getattr(payload, 'data', {}) or {}
            meta = data.get('thread_metadata') or {}
            archived = bool(meta.get('archived', False))
            thread_id = str(getattr(payload, 'thread_id', '') or data.get('id') or '')
            if not thread_id:
                return
            ctx = Ctx(platform='discord', channel_id=thread_id, user_id='0')
            if archived:
                end_room(ctx)
        except Exception:
            pass

    async def _handle_rp_command(self, message: discord.Message, ctx: Ctx, content: str) -> bool:
        """RP 명령 처리. 처리했으면 True."""
        if not content.startswith(ALLOWED_PREFIX):
            return False

        parts = content.split()
        cmd = parts[1] if len(parts) > 1 else ''

        if not cmd:
            guide = _load_rp_guide_text()
            if guide:
                await message.channel.send(guide)
            else:
                await message.channel.send('가이드 파일을 찾지 못했어.')
            return True

        if cmd == '시작':
            opening = content.split(None, 2)[2].strip() if len(parts) >= 3 else ''
            if isinstance(message.channel, discord.DMChannel):
                await self._start_in_current(message, kind='dm', opening=opening)
                return True
            if isinstance(message.channel, discord.Thread):
                await self._start_in_current(message, kind='thread', opening=opening)
                return True
            await self._start_in_thread(message, opening=opening)
            return True

        if cmd == '끝':
            await self._end_in_current(message)
            return True

        if cmd in ('이름', '호칭'):
            alias = content.split(None, 2)[2].strip() if len(parts) >= 3 else ''
            set_channel_user_alias(ctx, alias, speaker_id=str(message.author.id))
            if alias:
                await message.reply(f'좋아, 이제부터 사용자 호칭은 {alias}로 고정할게.', mention_author=False)
            else:
                await message.reply('사용자 호칭 고정을 해제했어. 기본 호칭으로 돌아갈게.', mention_author=False)
            return True

        if cmd == '가이드':
            guide = _load_rp_guide_text()
            if not guide:
                await message.channel.send('가이드 파일을 찾지 못했어.')
                return True
            sent = await message.channel.send(guide)
            try:
                await sent.pin(reason='RP guide')
            except Exception:
                pass
            return True

        sub = ' '.join(parts[1:]).strip()
        if sub in ('사용자명', '이름확인'):
            current_alias = self._resolve_alias(ctx, message)
            await message.reply(f'현재 사용자명: `{current_alias}`', mention_author=False)
            return True

        await message.channel.send("없는 명령어야. `!rp 시작 [주제]` / `!rp 끝` / `!rp 이름 [호칭]` / `!rp 사용자명` / `!rp 가이드` 중에서 써줘.")
        return True

    async def _handle_room_turn(self, message: discord.Message, ctx: Ctx, content: str) -> None:
        """활성 RP 룸 일반 대화 처리."""
        speaker_alias = self._resolve_alias(ctx, message) or message.author.display_name
        ingested = ingest_plain_chat(ctx, content, message_id=str(message.id), speaker_name=speaker_alias)
        if not ingested:
            return

        touch_runtime_lock(self.runtime_pid)

        if await self._maybe_natural_disengage(ctx, message, content):
            return

        if self.reply_mode == 'off':
            return
        if self.reply_mode == 'mention' and not self._is_mention_to_me(message):
            return

        alias = self._resolve_alias(ctx, message)
        reply = generate_rp_reply(
            ctx,
            user_display=alias,
            bot_name=(self.user.display_name if self.user else 'RP'),
        )
        if not (reply or '').strip():
            return
        sent = await message.reply(reply, mention_author=False)
        self._log_bot_turn(ctx, reply, message_id=str(getattr(sent, 'id', '') or ''))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not self._mark_seen(str(message.id)):
            return

        content = (message.content or '').strip()
        if not content:
            return

        is_rp_command = content.startswith(ALLOWED_PREFIX)

        if isinstance(message.channel, discord.Thread) and getattr(message.channel, 'archived', False) and (not is_rp_command):
            return
        if is_rp_command and (not _mark_command_once(str(message.id))):
            return
        if (not is_rp_command) and (not self._is_allowed_message(message)):
            return

        ctx = Ctx(platform='discord', channel_id=str(message.channel.id), user_id=str(message.author.id))
        active_room = is_room_active(ctx)

        if content.startswith('!') and not is_rp_command and active_room:
            return

        if await self._handle_rp_command(message, ctx, content):
            return

        await self._handle_room_turn(message, ctx, content)

# ---- process entry ----
def main() -> int:
    load_env_prefer_dotenv()
    token = (os.getenv('DISCORD_BOT_TOKEN') or '').strip()
    if not token:
        print('DISCORD_BOT_TOKEN이 필요함')
        return 2

    token_fp = hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]
    pid = os.getpid()
    ok, msg = acquire_runtime_lock(token_fp, pid)
    if not ok:
        print(msg)
        return 3

    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guilds = True

    client = RpDiscordClient(intents=intents, runtime_pid=pid)
    try:
        client.run(token)
    finally:
        release_runtime_lock(pid)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
