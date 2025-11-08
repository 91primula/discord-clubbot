# ───────────────────────────────────────────────────────────
# 🎛 Discord 통합 관리봇
# (가입인증 + 승급인증 + 라디오/유튜브, 큐/재생리스트 제거 + yt_dlp 예외 처리)
# ───────────────────────────────────────────────────────────
# ⚙️ 필수 환경변수 (.env / Koyeb 환경 설정)
# DISCORD_TOKEN=봇토큰
# GUILD_ID=123456789012345678
# CHANNEL_JOIN_ID=가입인증채널ID
# CHANNEL_PROMOTE_ID=승급인증채널ID
# CHANNEL_RADIO_ID=라디오채널ID
# JOIN_CODE=241120
# PROMOTE_CODE=021142
# JOIN_ROLE_NAME=클럽원
# PROMOTE_ROLE_NAME=쟁탈원
# YTDLP_COOKIES=cookies.txt              # (선택) 파일 경로 직접 지정 방식
# YTDLP_COOKIES_CONTENT=쿠키내용전부     # (선택) Secret에 통으로 넣는 방식
# ───────────────────────────────────────────────────────────

import os
import asyncio
from typing import Optional, Dict
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import yt_dlp

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

YTDLP_COOKIES = os.getenv("YTDLP_COOKIES")
YTDLP_COOKIES_CONTENT = os.getenv("YTDLP_COOKIES_CONTENT")

# YTDLP_COOKIES가 없고, 내용 기반 Secret이 있다면 실행 시 cookies.txt 생성
if (not YTDLP_COOKIES) and YTDLP_COOKIES_CONTENT:
    try:
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(YTDLP_COOKIES_CONTENT)
        YTDLP_COOKIES = "cookies.txt"
    except Exception as e:
        print("[YTDLP] ❌ Failed to write cookies.txt:", e)

# 디버그 로그: 현재 쿠키 설정 상태
print("[YTDLP] ENV YTDLP_COOKIES =", YTDLP_COOKIES)
print(
    "[YTDLP] ENV YTDLP_COOKIES_CONTENT length =",
    len(YTDLP_COOKIES_CONTENT) if YTDLP_COOKIES_CONTENT else 0,
)

if YTDLP_COOKIES and os.path.exists(YTDLP_COOKIES):
    print("[YTDLP] ✅ cookies file FOUND at", YTDLP_COOKIES)
else:
    print("[YTDLP] ❌ NO valid cookies file detected - yt-dlp will run WITHOUT login")

# ────────────────────────────────
# 📻 라디오 URL
# ────────────────────────────────
RADIO_URLS = {
    "mbc표준fm": os.getenv("RADIO_MBC_STD_URL"),
    "mbcfm4u": os.getenv("RADIO_MBC_FM4U_URL"),
    "sbs러브fm": os.getenv("RADIO_SBS_LOVE_URL"),
    "sbs파워fm": os.getenv("RADIO_SBS_POWER_URL"),
    "cbs음악fm": os.getenv("RADIO_CBS_MUSIC_URL"),
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
# 🎵 yt-dlp Helper
# ────────────────────────────────

def build_ytdlp_opts() -> dict:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "default_search": "ytsearch",
        "cachedir": False,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extract_flat": False,
        "retries": 3,
    }
    if YTDLP_COOKIES and os.path.exists(YTDLP_COOKIES):
        opts["cookiefile"] = YTDLP_COOKIES
        print("[YTDLP] ▶ Using cookiefile:", YTDLP_COOKIES)
    else:
        print("[YTDLP] ▶ Not using any cookiefile")
    return opts


async def ytdlp_extract_stream(url: str) -> Optional[str]:
    """단일 영상/검색 결과에서 실제 오디오 스트림 URL 추출"""
    loop = asyncio.get_running_loop()

    def _extract() -> Optional[str]:
        try:
            with yt_dlp.YoutubeDL(build_ytdlp_opts()) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                if "entries" in info:
                    info = info["entries"][0]
                return info.get("url")
        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if ("Sign in to confirm" in msg
                    or "Private video" in msg
                    or "age-restricted" in msg):
                return "LOGIN_REQUIRED"
            return None
        except Exception:
            return None

    return await loop.run_in_executor(None, _extract)


async def ytdlp_search_first(query: str) -> Optional[Dict[str, str]]:
    """
    검색어로 유튜브 1개 찾기.
    - 정상: {title, webpage_url}
    - 로그인 필요: {"_login_required": "1"}
    - 실패: None
    """
    loop = asyncio.get_running_loop()

    def _search() -> Optional[Dict[str, str]]:
        try:
            q = f"ytsearch1:{query}"
            with yt_dlp.YoutubeDL(build_ytdlp_opts()) as ydl:
                info = ydl.extract_info(q, download=False)
                if not info or not info.get("entries"):
                    return None
                e = info["entries"][0]
                return {
                    "title": e.get("title", "unknown"),
                    "webpage_url": e.get("webpage_url"),
                }
        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if ("Sign in to confirm" in msg
                    or "Private video" in msg
                    or "age-restricted" in msg):
                return {"_login_required": "1"}
            return None
        except Exception:
            return None

    return await loop.run_in_executor(None, _search)

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


class YoutubeURLModal(Modal, title="YouTube URL 재생"):
    url = TextInput(label="URL 입력", placeholder="재생하려는 음악의 YouTube URL을 입력하시오", required=True)

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(thinking=True)
        await play_youtube(i, self.url.value.strip())


class YoutubeSearchModal(Modal, title="YouTube 검색 재생"):
    q = TextInput(label="검색어", placeholder="노래 제목 또는 키워드", required=True)

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(thinking=True)

        found = await ytdlp_search_first(self.q.value.strip())
        if not found:
            await send_or_followup(i, "🔎 검색 결과를 찾지 못했습니다.", ephemeral=True)
            return

        if isinstance(found, dict) and found.get("_login_required") == "1":
            await send_or_followup(
                i,
                "⚠️ 로그인(쿠키)이 필요한 영상만 검색되었습니다.\n"
                "cookies.txt를 설정하거나, 다른 검색어/영상으로 시도해주세요.",
                ephemeral=True,
            )
            return

        await play_youtube(i, found["webpage_url"], title=found.get("title"))


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
        for r in ["📻mbc표준fm", "📻mbcfm4u", "📻sbs러브fm", "📻sbs파워fm", "📻cbs음악fm"]:
            self.add_item(Button(label=f"{r}", style=discord.ButtonStyle.primary, custom_id=r))
        # 유튜브 (단일 재생)
        self.add_item(Button(label="🎧YouTube URL", style=discord.ButtonStyle.success, custom_id="yturl"))
        self.add_item(Button(label="🎧YouTube 검색", style=discord.ButtonStyle.success, custom_id="ytsearch"))
        # 정지
        self.add_item(Button(label="⛔정지", style=discord.ButtonStyle.danger, custom_id="stop"))

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

    if cid == "yturl":
        await i.response.send_modal(YoutubeURLModal())
        return

    if cid == "ytsearch":
        await i.response.send_modal(YoutubeSearchModal())
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

async def play_youtube(i: discord.Interaction, url: str, title: Optional[str] = None):
    vc = await connect_to_user_channel(i)
    if not vc:
        return

    stream = await ytdlp_extract_stream(url)

    if not stream:
        await send_or_followup(
            i,
            "⚠️ 유튜브 정보를 불러오지 못했습니다.\n"
            "이미지만 있는 영상이거나, 지원되지 않는 형식일 수 있어요.",
            ephemeral=True,
        )
        return

    if stream == "LOGIN_REQUIRED":
        await send_or_followup(
            i,
            "⚠️ 로그인(쿠키)이 필요한 영상입니다. cookies.txt 설정을 확인해주세요.",
            ephemeral=True,
        )
        return

    item_title = title or url

    if vc.is_playing():
        vc.stop()

    src = discord.FFmpegPCMAudio(
        stream,
        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        options="-vn",
    )
    vc.play(src)

    await send_or_followup(i, f"🎵 재생 시작: {item_title}", ephemeral=False)


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
    if vc and vc.channel != user.voice.channel:
        await vc.move_to(user.voice.channel)
    if not vc:
        vc = await user.voice.channel.connect()
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
                "✨ 🆕 가입 인증 후에는 아래 버튼으로 별명 변경을 진행해주세요!",
                PIN_TAG_JOIN,
                JoinView(),
            )
        if (ch := guild.get_channel(CHANNEL_PROMOTE_ID)):
            await ensure_pinned_message(
                ch,
                f"{PIN_TAG_PROMOTE}\n"
                "🪖 쟁탈원 승급 인증을 진행해주세요!\n"
                "✨ 아래 버튼을 눌러 승급코드를 입력하면 자동으로 역할 부여됩니다.",
                PIN_TAG_PROMOTE,
                PromoteView(),
            )
        if (ch := guild.get_channel(CHANNEL_RADIO_ID)):
            await ensure_pinned_message(
                ch,
                f"{PIN_TAG_RADIO}\n"
                "📡 라디오/유튜브 봇 접속 완료!\n"
                "📡📻 라디오 채널별 버튼을 눌러 라디오를 듣거나\n"
                "📡🎧 유튜브 URL 기반 재생 or 검색(키워드) 기반으로 유튜브 음악을 바로 재생하세요.",
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
