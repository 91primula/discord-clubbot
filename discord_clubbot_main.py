# ───────────────────────────────────────────────────────────
# 🎛 Discord 통합 관리봇 (가입인증 + 승급인증 + 라디오/유튜브 + 재생리스트) 2025-11 완전판
# ───────────────────────────────────────────────────────────
# ⚙️ 필수 환경변수 (.env)
# DISCORD_TOKEN=봇토큰
# GUILD_ID=123456789012345678
# CHANNEL_JOIN_ID=가입인증채널ID
# CHANNEL_PROMOTE_ID=승급인증채널ID
# CHANNEL_RADIO_ID=라디오채널ID
# JOIN_CODE=241120
# PROMOTE_CODE=021142
# JOIN_ROLE_NAME=클럽원
# PROMOTE_ROLE_NAME=쟁탈원
# YTDLP_COOKIES=cookies.txt   # (선택, 연령제한/로그인 필요영상용)
# ───────────────────────────────────────────────────────────

import os
import asyncio
from typing import Optional, Dict, List
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

# ────────────────────────────────
# 📻 라디오 URL
# ────────────────────────────────
RADIO_URLS: Dict[str, str] = {
    "mbc표준fm": "https://minisw.imbc.com/dsfm/_definst_/sfm.stream/playlist.m3u8?_lsu_sa_=61112E1583FB3CA4544AE5C23A41D044E56B3CD5F00CA2033A702FaE565334E6AEaF43243CD2C640E02E35215DbE316333E2409974760494C4BDEA30DF43A460D6494D94E16DB4B554063EF2C9715A26E8F8132F2E7C60C702A088D0C707B68A15BAFD759969CE735CA3E0560987064A",
    "mbcfm4u": "https://minimw.imbc.com/dmfm/_definst_/mfm.stream/playlist.m3u8?_lsu_sa_=6971C51D139B39945940F5663041064025503355BF0EA23B38504AaD86BC3F9668aDD36230C2CB4100463A6175bC8171C5785076FC120267056BAFD2FB8CCC4952C3AAD8A1247657240B99AE1804334CA2004DC670EC73ABAF885C491F357916C857E0EE9A1BF42399D328100E2EA27F",
    "sbs러브fm": "https://radiolive.sbs.co.kr/lovepc/lovefm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjI2MjI2NjMsInBhdGgiOiIvbG92ZWZtLnN0cmVhbSIsImR1cmF0aW9uIjotMSwidW5vIjoiMjEzYjM4MGYtNTgzYS00NmYyLWJmM2QtN2M4OWZjMWIxYjA1IiwiaWF0IjoxNzYyNTc5NDYzfQ.8W4kaPVi4DlG0hOF9VhZaqx_LhF9BdXIM_hqtBV98GU",
    "sbs파워fm": "https://radiolive.sbs.co.kr/powerpc/powerfm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjI2MjI2NzIsInBhdGgiOiIvcG93ZXJmbS5zdHJlYW0iLCJkdXJhdGlvbiI6LTEsInVubyI6Ijg2YzRiNmY0LWNlMWEtNDI0Ni04YTY4LTI4OTYwZmY1MTYxYyIsImlhdCI6MTc2MjU3OTQ3Mn0.bzsqw24uEDU61sQ1slyUyLGvZusH3VrD7MWWD7pB-Ww",
    "cbs음악fm": "https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/chunklist.m3u8",
}

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
    """검색어로 유튜브 1개 찾기 (title, webpage_url 반환)"""
    loop = asyncio.get_running_loop()

    def _search() -> Optional[Dict[str, str]]:
        q = f"ytsearch1:{query}"
        with yt_dlp.YoutubeDL(build_ytdlp_opts()) as ydl:
            info = ydl.extract_info(q, download=False)
            if info and info.get("entries"):
                e = info["entries"][0]
                return {
                    "title": e.get("title", "unknown"),
                    "webpage_url": e.get("webpage_url"),
                }
            return None

    return await loop.run_in_executor(None, _search)

# ────────────────────────────────
# 🎧 길드 오디오/큐 상태
# ────────────────────────────────

class GuildAudioState:
    def __init__(self):
        self.queue: List[Dict[str, str]] = []   # {title, stream_url}
        self.now: Optional[Dict[str, str]] = None

    def clear_radio(self):
        """라디오 재생 시 큐와 현재곡 정리용 (원하면 라디오는 별도 처리)."""
        self.queue.clear()
        self.now = None


AUDIO: Dict[int, GuildAudioState] = {}


def get_state(guild_id: int) -> GuildAudioState:
    if guild_id not in AUDIO:
        AUDIO[guild_id] = GuildAudioState()
    return AUDIO[guild_id]

# ────────────────────────────────
# 🧩 공통 유틸
# ────────────────────────────────

async def ensure_pinned_message(channel: discord.TextChannel, content: str, tag: str, view: Optional[View] = None):
    """tag 포함된 기존 핀 찾고 갱신, 없으면 새로 보내고 고정"""
    pins = await channel.pins()
    for m in pins:
        if tag in m.content:
            await m.edit(content=content, view=view)
            return
    sent = await channel.send(content, view=view)
    await sent.pin()


async def purge_non_pinned(channel: discord.TextChannel):
    """핀 된 메시지 빼고 최근 메시지 정리"""
    pins = await channel.pins()
    pin_ids = {m.id for m in pins}
    await channel.purge(limit=200, check=lambda m: m.id not in pin_ids)


async def connect_to_user_channel(inter: discord.Interaction) -> Optional[discord.VoiceClient]:
    """유저가 들어간 음성채널에 봇 연결/이동"""
    user = inter.user
    if not isinstance(user, discord.Member) or not user.voice:
        await inter.response.send_message("🎧 먼저 음성 채널에 들어가주세요.", ephemeral=True)
        return None

    vc = inter.guild.voice_client
    if vc and vc.channel != user.voice.channel:
        await vc.move_to(user.voice.channel)
    if not vc:
        vc = await user.voice.channel.connect()
    return vc

# ────────────────────────────────
# 🔘 모달
# ────────────────────────────────

class JoinModal(Modal, title="가입 인증"):
    code = TextInput(label="가입코드", placeholder="241120", required=True)

    async def on_submit(self, i: discord.Interaction):
        ch = i.channel
        if self.code.value.strip() == JOIN_CODE:
            role = discord.utils.get(i.guild.roles, name=JOIN_ROLE_NAME)
            if role:
                await i.user.add_roles(role)
            await i.response.send_message("🎉 정답입니다! 클럽원 역할이 부여되었습니다!", ephemeral=False)
        else:
            await i.response.send_message("❌ 정답이 아닙니다.", ephemeral=False)

        if isinstance(ch, discord.TextChannel):
            asyncio.create_task(purge_non_pinned(ch))


class PromoteModal(Modal, title="승급 인증"):
    code = TextInput(label="승급코드", placeholder="021142", required=True)

    async def on_submit(self, i: discord.Interaction):
        ch = i.channel
        if self.code.value.strip() == PROMOTE_CODE:
            role = discord.utils.get(i.guild.roles, name=PROMOTE_ROLE_NAME)
            if role:
                await i.user.add_roles(role)
            await i.response.send_message("🎉 정답입니다! 쟁탈원 역할이 부여되었습니다!", ephemeral=False)
        else:
            await i.response.send_message("❌ 정답이 아닙니다.", ephemeral=False)

        if isinstance(ch, discord.TextChannel):
            asyncio.create_task(purge_non_pinned(ch))


class YoutubeURLModal(Modal, title="YouTube URL 재생"):
    url = TextInput(label="URL 입력", placeholder="https://www.youtube.com/watch?v=...", required=True)

    async def on_submit(self, i: discord.Interaction):
        await queue_youtube(i, self.url.value.strip())


class YoutubeSearchModal(Modal, title="YouTube 검색 재생"):
    q = TextInput(label="검색어", placeholder="노래 제목 또는 키워드", required=True)

    async def on_submit(self, i: discord.Interaction):
        found = await ytdlp_search_first(self.q.value.strip())
        if not found:
            await i.response.send_message("🔎 검색 결과를 찾지 못했습니다.", ephemeral=True)
            return
        await queue_youtube(i, found["webpage_url"], title=found.get("title"))

# ────────────────────────────────
# 🔘 View / 버튼 UI
# ────────────────────────────────

class JoinView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="join"))
        self.add_item(Button(label="별명 변경 안내", style=discord.ButtonStyle.secondary, custom_id="nick_info"))


class PromoteView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="승급인증", style=discord.ButtonStyle.primary, custom_id="promote"))


class RadioView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # 라디오
        for r in ["mbc표준fm", "mbcfm4u", "sbs러브fm", "sbs파워fm", "cbs음악fm"]:
            self.add_item(Button(label=f"{r}", style=discord.ButtonStyle.primary, custom_id=r))
        # 유튜브
        self.add_item(Button(label="YouTube URL", style=discord.ButtonStyle.secondary, custom_id="yturl"))
        self.add_item(Button(label="YouTube 검색", style=discord.ButtonStyle.secondary, custom_id="ytsearch"))
        # 재생 컨트롤
        self.add_item(Button(label="재생리스트", style=discord.ButtonStyle.secondary, custom_id="show_queue"))
        self.add_item(Button(label="⏭ 다음", style=discord.ButtonStyle.secondary, custom_id="next_track"))
        # 정지
        self.add_item(Button(label="정지", style=discord.ButtonStyle.danger, custom_id="stop"))

# ────────────────────────────────
# 🧠 버튼 인터랙션 핸들러
# ────────────────────────────────

@bot.listen("on_interaction")
async def on_inter(i: discord.Interaction):
    if i.type != discord.InteractionType.component:
        return

    cid = i.data.get("custom_id")

    # 가입 / 승급
    if cid == "join":
        await i.response.send_modal(JoinModal())
        return

    if cid == "promote":
        await i.response.send_modal(PromoteModal())
        return

    if cid == "nick_info":
        await i.response.send_message("🔤 디스코드 '서버 프로필 편집'에서 별명을 변경해주세요.", ephemeral=True)
        return

    # 유튜브
    if cid == "yturl":
        await i.response.send_modal(YoutubeURLModal())
        return

    if cid == "ytsearch":
        await i.response.send_modal(YoutubeSearchModal())
        return

    if cid == "show_queue":
        await show_queue(i)
        return

    if cid == "next_track":
        await skip_track(i)
        return

    # 정지
    if cid == "stop":
        vc = i.guild.voice_client
        state = get_state(i.guild.id)
        state.queue.clear()
        state.now = None
        if vc:
            await vc.disconnect(force=True)
        await purge_non_pinned(i.channel)
        await i.response.send_message("⛔ 재생을 정지하고 음성 채널에서 나갔습니다.", ephemeral=False)
        return

    # 라디오
    if cid in RADIO_URLS:
        await radio_play(i, cid)
        return

# ────────────────────────────────
# 🎵 재생 / 큐 로직
# ────────────────────────────────

async def start_next(guild: discord.Guild):
    """큐에서 다음 곡 재생"""
    state = get_state(guild.id)
    if not state.queue:
        state.now = None
        return

    item = state.queue.pop(0)
    state.now = item

    vc = guild.voice_client
    if not vc:
        state.now = None
        return

    src = discord.FFmpegPCMAudio(
        item["stream_url"],
        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        options="-vn",
    )

    def _after(error):
        # 다음 곡 자동 재생
        fut = asyncio.run_coroutine_threadsafe(start_next(guild), bot.loop)
        try:
            fut.result()
        except Exception as e:
            print("next track error:", e)

    vc.play(src, after=_after)


async def queue_youtube(i: discord.Interaction, url: str, title: Optional[str] = None):
    """유튜브 곡을 큐에 추가하고, 재생 중이 아니면 바로 재생"""
    vc = await connect_to_user_channel(i)
    if not vc:
        return

    stream = await ytdlp_extract_stream(url)
    if not stream:
        await i.response.send_message("⚠️ 유튜브 정보를 불러오지 못했습니다.", ephemeral=True)
        return
    if stream == "LOGIN_REQUIRED":
        await i.response.send_message("⚠️ 로그인(쿠키)이 필요한 영상입니다. cookies.txt 설정을 확인해주세요.", ephemeral=True)
        return

    # 큐에 추가
    state = get_state(i.guild.id)
    item_title = title or url
    state.queue.append({"title": item_title, "stream_url": stream})

    # 지금 아무것도 안 틀고 있으면 바로 재생
    if not vc.is_playing():
        await start_next(i.guild)
        await i.response.send_message(f"🎵 재생 시작: {item_title}", ephemeral=False)
    else:
        await i.response.send_message(f"➕ 대기열에 추가됨: {item_title}", ephemeral=False)


async def show_queue(i: discord.Interaction):
    state = get_state(i.guild.id)
    lines = []

    if state.now:
        lines.append(f"▶ 현재 재생: {state.now['title']}")

    if state.queue:
        for idx, item in enumerate(state.queue[:10], start=1):
            lines.append(f"{idx}. {item['title']}")
    else:
        if not state.now:
            lines.append("대기열이 비어 있습니다.")

    await i.response.send_message("\n".join(lines), ephemeral=True)


async def skip_track(i: discord.Interaction):
    vc = i.guild.voice_client
    if not vc or not vc.is_playing():
        await i.response.send_message("⏹ 현재 재생 중인 곡이 없습니다.", ephemeral=True)
        return

    vc.stop()  # after 콜백에서 자동으로 다음곡 재생
    await i.response.send_message("⏭ 다음 곡으로 이동합니다.", ephemeral=True)


async def radio_play(i: discord.Interaction, key: str):
    """라디오 재생(큐 초기화 후 바로 재생)"""
    url = RADIO_URLS.get(key)
    if not url:
        await i.response.send_message("📻 라디오 URL이 설정되지 않았습니다.", ephemeral=True)
        return

    vc = await connect_to_user_channel(i)
    if not vc:
        return

    # 라디오 틀 때는 큐 비우기
    state = get_state(i.guild.id)
    state.clear_radio()

    src = discord.FFmpegPCMAudio(
        url,
        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        options="-vn",
    )
    vc.stop()
    vc.play(src)
    await i.response.send_message(f"📻 {key} 재생 시작!", ephemeral=False)

# ────────────────────────────────
# ✨ on_ready
# ────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ 로그인됨: {bot.user} (id: {bot.user.id})")

    # persistent view 등록 (재부팅 후에도 버튼 유지)
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
                "✨ 운영진 또는 공지에서 인증코드를 확인한 뒤 아래 버튼으로 가입 인증을 진행해주세요!",
                PIN_TAG_JOIN,
                JoinView(),
            )
        if (ch := guild.get_channel(CHANNEL_PROMOTE_ID)):
            await ensure_pinned_message(
                ch,
                f"{PIN_TAG_PROMOTE}\n"
                "🪖 쟁탈원 승급 인증을 진행해주세요!\n"
                "✨ 아래 버튼을 눌러 승급코드를 입력하면 자동으로 역할이 부여됩니다.",
                PIN_TAG_PROMOTE,
                PromoteView(),
            )
        if (ch := guild.get_channel(CHANNEL_RADIO_ID)):
            await ensure_pinned_message(
                ch,
                f"{PIN_TAG_RADIO}\n"
                "📡 라디오/유튜브 봇 접속 완료!\n"
                "원하는 버튼을 눌러 라디오를 재생하거나 유튜브 음악을 큐에 추가하세요.",
                PIN_TAG_RADIO,
                RadioView(),
            )

    # (슬래시 명령어를 별도로 추가할 경우를 대비한 sync — 현재는 버튼/모달만 사용)
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
