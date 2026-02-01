# ───────────────────────────────────────────────────────────
# 🎛 Discord 통합 관리봇
# (가입인증 + 승급인증 + 라디오/유튜브, 큐/재생리스트 제거)
# ───────────────────────────────────────────────────────────

import os
import asyncio
from typing import Optional, Dict
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
# ────────────────────────────────
# ✅ 환경변수 로드
# ────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
CHANNEL_JOIN_ID = int(os.getenv("CHANNEL_JOIN_ID", "0"))
CHANNEL_PROMOTE_ID = int(os.getenv("CHANNEL_PROMOTE_ID", "0"))
CHANNEL_RADIO_ID = int(os.getenv("CHANNEL_RADIO_ID", "0"))

JOIN_CODE = os.getenv("JOIN_CODE", "241120")
PROMOTE_CODE = os.getenv("PROMOTE_CODE", "021142")
JOIN_ROLE_NAME = os.getenv("JOIN_ROLE_NAME", "클럽원")
PROMOTE_ROLE_NAME = os.getenv("PROMOTE_ROLE_NAME", "쟁탈원")


# ────────────────────────────────
# 📻 라디오 URL
# ────────────────────────────────
RADIO_URLS = {
    "📻mbc표준fm": os.getenv("RADIO_MBC_STD_URL"),
    "📻mbcfm4u": os.getenv("RADIO_MBC_FM4U_URL"),
    "📻mbc올댓뮤직": os.getenv("RADIO_MBC_ALLTHATMUSIC_URL"),
    "📻sbs러브fm": os.getenv("RADIO_SBS_LOVE_URL"),
    "📻sbs파워fm": os.getenv("RADIO_SBS_POWER_URL"),
    "📻cbs음악fm": os.getenv("RADIO_CBS_MUSIC_URL"),
}
# RADIO_URLS: Dict[str, str]

# 핀 고정 태그
PIN_TAG_JOIN = "[JOIN_PIN]"
PIN_TAG_PROMOTE = "[PROMOTE_PIN]"
PIN_TAG_RADIO = "[RADIO_PIN]"

# ────────────────────────────────
# 🤖 봇 설정
# ────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ────────────────────────────────
# 🧩 공통 유틸
# ────────────────────────────────

async def send_or_followup(i: discord.Interaction, content: str, ephemeral: bool = False):
    """
    interaction이 아직 응답 전이면 response.send_message,
    이미 defer/응답된 상태면 followup.send 사용.
    Unknown interaction 방지용.
    """
    try:
        if i.response.is_done():
            return await i.followup.send(content, ephemeral=ephemeral)
        else:
            return await i.response.send_message(content, ephemeral=ephemeral)
    except discord.NotFound:
        return


async def ensure_pinned_message(channel: discord.TextChannel, content: str, tag: str, view: Optional[View] = None):
    pins = await channel.pins()
    for m in pins:
        if tag in m.content:
            await m.edit(content=content, view=view)
            return
    sent = await channel.send(content, view=view)
    await sent.pin()


async def purge_non_pinned(channel: discord.TextChannel):
    pins = await channel.pins()
    pin_ids = {m.id for m in pins}
    deleted = await channel.purge(
        limit=200,
        check=lambda m: m.id not in pin_ids
    )
    print(f"[PURGE] {channel.name}: deleted {len(deleted)} messages (non-pinned)")

async def cleanup_all_non_pinned(channel: discord.TextChannel) -> int:
    """채널의 핀 고정 메시지를 제외하고 가능한 모든 메시지를 삭제합니다.
    - bulk delete 제한(14일) 회피를 위해 개별 삭제를 시도합니다.
    - 권한/오래된 메시지/고정 메시지는 건너뛰거나 실패할 수 있습니다.
    반환: 삭제 시도 성공 개수
    """
    pins = await channel.pins()
    pin_ids = {m.id for m in pins}
    deleted_count = 0
    # 최근 메시지부터 삭제
    async for msg in channel.history(limit=None, oldest_first=False):
        if msg.id in pin_ids:
            continue
        try:
            await msg.delete()
            deleted_count += 1
            # 레이트리밋 완화
            if deleted_count % 20 == 0:
                await asyncio.sleep(1)
        except discord.Forbidden:
            print("[CLEANUP] ❌ 메시지 삭제 권한이 없습니다. (MANAGE_MESSAGES)")
            break
        except discord.HTTPException:
            # 삭제 불가 메시지(권한/기간/기타) 등은 스킵
            continue
        except Exception:
            continue
    return deleted_count

async def delete_non_pinned_after_delay(channel: discord.TextChannel, delay: int = 5):
    """
    delay초 후, 해당 채널에서 '핀 고정 메시지'를 제외하고 전부 삭제
    """
    await asyncio.sleep(delay)
    if not isinstance(channel, discord.TextChannel):
        return
    try:
        await purge_non_pinned(channel)
    except discord.Forbidden:
        print("[YT_CLEANUP] ❌ 메시지 삭제 권한이 없습니다. (MANAGE_MESSAGES 확인)")
    except Exception as e:
        print("[YT_CLEANUP] 오류:", e)


async def delete_later_and_purge(msg: discord.Message, delay: int):
    """인증 안내/알림 메시지 delay초 뒤 삭제 + 채널 정리"""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass

    ch = msg.channel
    if isinstance(ch, discord.TextChannel):
        try:
            await purge_non_pinned(ch)
        except Exception:
            pass


async def delete_radio_messages_after_stop(channel: discord.TextChannel, delay: int = 3):
    """
    stop 버튼 사용 시 라디오 채널에서만
    delay초 뒤, 핀 고정 메시지 제외 전체 삭제
    """
    await asyncio.sleep(delay)

    if not isinstance(channel, discord.TextChannel):
        return

    # 라디오 전용 채널에서만 작동
    if channel.id != CHANNEL_RADIO_ID:
        return

    try:
        await purge_non_pinned(channel)
    except discord.Forbidden:
        print("[RADIO_CLEANUP] ❌ 메시지 삭제 권한이 없습니다. (MANAGE_MESSAGES 확인)")
    except Exception as e:
        print("[RADIO_CLEANUP] 오류:", e)

# ────────────────────────────────
# 🔘 모달
# ────────────────────────────────

class JoinModal(Modal, title="가입 인증"):
    code = TextInput(label="가입코드", placeholder="오픈톡방 공지의 디스코드 가입코드를 입력하시오", required=True)

    async def on_submit(self, i: discord.Interaction):
        is_correct = (self.code.value.strip() == JOIN_CODE)

        if is_correct:
            role = discord.utils.get(i.guild.roles, name=JOIN_ROLE_NAME)
            if role:
                await i.user.add_roles(role)
            await i.response.send_message("🎉 정답입니다! 클럽원 역할이 부여되었습니다!", ephemeral=False)
            try:
                msg = await i.original_response()
                asyncio.create_task(delete_later_and_purge(msg, 5))
            except Exception:
                pass
        else:
            await i.response.send_message("❌ 정답이 아닙니다.", ephemeral=False)
            try:
                msg = await i.original_response()
                asyncio.create_task(delete_later_and_purge(msg, 10))
            except Exception:
                pass


class PromoteModal(Modal, title="승급 인증"):
    code = TextInput(label="승급코드", placeholder="운영진에게 승급코드를 물어보고 입력하시오", required=True)

    async def on_submit(self, i: discord.Interaction):
        is_correct = (self.code.value.strip() == PROMOTE_CODE)

        if is_correct:
            role = discord.utils.get(i.guild.roles, name=PROMOTE_ROLE_NAME)
            if role:
                await i.user.add_roles(role)
            await i.response.send_message("🎉 정답입니다! 쟁탈원 역할이 부여되었습니다!", ephemeral=False)
            try:
                msg = await i.original_response()
                asyncio.create_task(delete_later_and_purge(msg, 5))
            except Exception:
                pass
        else:
            await i.response.send_message("❌ 정답이 아닙니다.", ephemeral=False)
            try:
                msg = await i.original_response()
                asyncio.create_task(delete_later_and_purge(msg, 10))
            except Exception:
                pass



class NicknameModal(Modal, title="서버 별명 변경"):
    new_nick = TextInput(
        label="새 별명",
        placeholder="텔즈 캐릭터명을 입력하시오",
        required=True,
        max_length=32,
    )

    async def on_submit(self, i: discord.Interaction):
        nick = self.new_nick.value.strip()
        try:
            await i.user.edit(nick=nick)
            await i.response.send_message(f"✅ 별명이 `{nick}`(으)로 변경되었습니다.", ephemeral=True)
        except discord.Forbidden:
            await i.response.send_message("❌ 봇에 닉네임 변경 권한이 없어요. 관리자에게 권한을 확인 요청해주세요.", ephemeral=True)
        except Exception:
            await i.response.send_message("⚠️ 별명 변경 중 오류가 발생했습니다.", ephemeral=True)

# ────────────────────────────────
# 🔘 View / 버튼 UI
# ────────────────────────────────

class JoinView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🪪가입인증", style=discord.ButtonStyle.primary, custom_id="join"))
        self.add_item(Button(label="🆕별명 변경", style=discord.ButtonStyle.danger, custom_id="nick_change"))


class PromoteView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🪪승급인증", style=discord.ButtonStyle.primary, custom_id="promote"))


class RadioView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # 라디오 버튼
        for r in ["📻mbc표준fm", "📻mbcfm4u", "📻mbc올댓뮤직", "📻sbs러브fm", "📻sbs파워fm", "📻cbs음악fm"]:
            self.add_item(Button(label=f"{r}", style=discord.ButtonStyle.primary, custom_id=r))
        # 정지
        self.add_item(Button(label="⛔라디오 정지", style=discord.ButtonStyle.danger, custom_id="stop"))
        # 하리보(다른 음악봇) 명령어 안내/정리 버튼
        self.add_item(Button(label="🧸하리보 명령어 확인", style=discord.ButtonStyle.success, custom_id="haribocmd"))
        self.add_item(Button(label="🗑️음성방 정리", style=discord.ButtonStyle.danger, custom_id="voice_clean"))

# ────────────────────────────────
# 🧠 버튼 인터랙션 핸들러
# ────────────────────────────────

@bot.listen("on_interaction")
async def on_inter(i: discord.Interaction):
    if i.type != discord.InteractionType.component:
        return

    cid = i.data.get("custom_id")

    if cid == "join":
        await i.response.send_modal(JoinModal())
        return

    if cid == "promote":
        await i.response.send_modal(PromoteModal())
        return

    if cid == "nick_change":
        await i.response.send_modal(NicknameModal())
        return

    if cid == "voice_clean":
        # 해당 채널에서 핀 고정 메시지를 제외하고 모두 삭제
        # (ephemeral 메시지는 채널 메시지가 아니라 삭제 대상이 아닙니다)
        await i.response.defer(ephemeral=True, thinking=True)
        channel = i.channel
        if isinstance(channel, discord.TextChannel):
            deleted = await cleanup_all_non_pinned(channel)
            await send_or_followup(i, f"🧹 정리 완료! (핀 제외) 삭제 시도: {deleted}개", ephemeral=True)
        else:
            await send_or_followup(i, "❌ 이 버튼은 텍스트 채널에서만 사용할 수 있어요.", ephemeral=True)
            return


    if cid == "voice_clean":
        # 안내 메시지 없이 조용히 정리만 수행
        await i.response.defer(ephemeral=True, thinking=True)

        channel = i.channel
        if isinstance(channel, discord.TextChannel):
            await cleanup_all_non_pinned(channel)

        # defer로 생긴 "thinking..."(ephemeral) 흔적 제거
        try:
            await i.delete_original_response()
        except Exception:
            pass

        return

if cid == "haribocmd":
    # 안내(ephemeral) 없이 조용히 처리
    await i.response.defer(ephemeral=True)

    guide = (
        "!!play \"제목\" or \"YouTube 동영상 URL\" : 명령 실행시 바로 재생함\n"
        "!!search \"제목\" : 명령 실행 후 관련 동영상 목록을 보여줌(선택 재생)\n"
        "!!clean : 봇이 보낸 채팅 청소\n"
        "!!정지 : 재생중인거 정지하고 음성방에서 퇴장"
    )
    try:
        await i.channel.send(guide)
    except Exception as e:
        print("[HARIBO] guide send failed:", e)

    # defer로 생긴 ephemeral 응답 흔적(로딩)을 지우고 싶으면 아래 추가
    try:
        await i.delete_original_response()
    except Exception:
        pass

    return

    

    if cid == "stop":
        vc = i.guild.voice_client
        if vc:
            await vc.disconnect(force=True)

        # 안내 메시지 (성공/실패와 무관하게 정리 로직은 채널 기준으로 동작)
        try:
            await send_or_followup(i, "⛔ 재생을 정지하고 음성 채널에서 나갔습니다.", ephemeral=False)
        except Exception:
            pass

        # 라디오 채널이라면 3초 뒤 핀 제외 전체 삭제
        channel = i.channel
        if isinstance(channel, discord.TextChannel):
            asyncio.create_task(delete_radio_messages_after_stop(channel, 3))

        return

    if cid in RADIO_URLS:
        await radio_play(i, cid)
        return

# ────────────────────────────────
# 🎵 재생 로직
# ────────────────────────────────




async def radio_play(i: discord.Interaction, key: str):
    url = RADIO_URLS.get(key)
    if not url:
        await send_or_followup(i, "📻 라디오 URL이 설정되지 않았습니다.", ephemeral=True)
        return

    vc = await connect_to_user_channel(i)
    if not vc:
        return

    if vc.is_playing():
        vc.stop()

    src = discord.FFmpegPCMAudio(
        url,
        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        options="-vn",
    )
    vc.play(src)

    await send_or_followup(i, f"📻 {key} 재생 시작!", ephemeral=False)

# ────────────────────────────────
# 🔊 음성 채널 연결 유틸
# ────────────────────────────────

async def connect_to_user_channel(inter: discord.Interaction) -> Optional[discord.VoiceClient]:
    user = inter.user
    if not isinstance(user, discord.Member) or not user.voice:
        await send_or_followup(inter, "🎧 먼저 음성 채널에 들어가주세요.", ephemeral=True)
        return None

    vc = inter.guild.voice_client

    # 이미 연결돼 있고, 다른 채널에 있으면 이동
    if vc and vc.channel != user.voice.channel:
        await vc.move_to(user.voice.channel)

    # 아직 안 들어가있으면 → self_deaf=True 로 접속 (헤드셋 닫힌 상태)
    if not vc:
        vc = await user.voice.channel.connect(self_deaf=True)

    # 혹시 이미 들어가 있는데 헤드셋이 열려 있으면 한번 더 강제로 닫고 싶다면 (선택사항)
    try:
        await vc.guild.change_voice_state(
            channel=vc.channel,
            self_deaf=True,
            self_mute=False
        )
    except Exception:
        pass

    return vc

# ────────────────────────────────
# ✨ on_ready
# ────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ 로그인됨: {bot.user} (id: {bot.user.id})")

    # Persistent View 등록
    bot.add_view(JoinView())
    bot.add_view(PromoteView())
    bot.add_view(RadioView())

    guild = bot.get_guild(GUILD_ID)
    if guild:
        if (ch := guild.get_channel(CHANNEL_JOIN_ID)):
            await ensure_pinned_message(
                ch,
                f"{PIN_TAG_JOIN}\n"
                "🎊 삐약 디스코드 서버에 오신 것을 환영합니다!\n"
                "✨ 🪪 운영진 또는 공지에서 인증코드를 확인한 뒤 아래 버튼으로 가입 인증을 진행해주세요!\n"
                "✨\n"
                "✨ 🆕 가입 인증 후에는 아래 버튼으로 별명 변경을 진행해주세요!\n"
                "✨",
                PIN_TAG_JOIN,
                JoinView(),
            )
        if (ch := guild.get_channel(CHANNEL_PROMOTE_ID)):
            await ensure_pinned_message(
                ch,
                f"{PIN_TAG_PROMOTE}\n"
                "🪖 쟁탈원 승급 인증을 진행해주세요!\n"
                "✨ 아래 버튼을 눌러 승급코드를 입력하면 자동으로 역할 부여됩니다.\n"
                "✨",
                PIN_TAG_PROMOTE,
                PromoteView(),
            )
        if (ch := guild.get_channel(CHANNEL_RADIO_ID)):
            await ensure_pinned_message(
                ch,
                f"{PIN_TAG_RADIO}\n"
                "📡 라디오/유튜브 봇 접속 완료!\n"
                "📡 먼저 음성채널(음악)에 접속해주세요!\n"
                " \n"
                "📡📻 라디오 채널별 버튼을 눌러 라디오를 듣거나📻\n"
                " \n"
                "📡🎧 유튜브 URL 기반 재생 or 검색(키워드) 기반으로 유튜브 음악을 바로 재생하세요.🎧\n"
                "🎶하리보 명령어 모음\n"
                "!!play 제목 or YouTube 동영상 URL : 명령 실행시 바로 재생함\n"
                "!!search 제목 : 명령 실행 후 관련 동영상 목록을 보여줌(선택 재생)\n"
                "!!clean : 하리보봇이 보낸 채팅 청소\n"
                "!!정지 : 재생중인거 정지하고 음성방에서 퇴장\n"
                "📡",
                PIN_TAG_RADIO,
                RadioView(),
            )

    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("✅ 슬래시 명령어 동기화 완료 (현재 등록된 명령어 기준)")
    except Exception as e:
        print("명령어 동기화 실패:", e)

# ────────────────────────────────
# 🚀 실행
# ────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ DISCORD_TOKEN 미설정")
    bot.run(TOKEN)
