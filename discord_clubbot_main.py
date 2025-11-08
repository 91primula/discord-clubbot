# ───────────────────────────────────────────────────────────
# 🎛 Discord 통합 관리봇 (가입인증 + 승급인증 + 라디오/유튜브) 2025-11 완전판
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
# YTDLP_COOKIES=cookies.txt   # (선택사항)
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

RADIO_URLS = {
    "mbc표준fm": "https://minisw.imbc.com/dsfm/_definst_/sfm.stream/playlist.m3u8?_lsu_sa_=61112E1583FB3CA4544AE5C23A41D044E56B3CD5F00CA2033A702FaE565334E6AEaF43243CD2C640E02E35215DbE316333E2409974760494C4BDEA30DF43A460D6494D94E16DB4B554063EF2C9715A26E8F8132F2E7C60C702A088D0C707B68A15BAFD759969CE735CA3E0560987064A",
    "mbcfm4u": "https://minimw.imbc.com/dmfm/_definst_/mfm.stream/playlist.m3u8?_lsu_sa_=6971C51D139B39945940F5663041064025503355BF0EA23B38504AaD86BC3F9668aDD36230C2CB4100463A6175bC8171C5785076FC120267056BAFD2FB8CCC4952C3AAD8A1247657240B99AE1804334CA2004DC670EC73ABAF885C491F357916C857E0EE9A1BF42399D328100E2EA27F",
    "sbs러브fm": "https://radiolive.sbs.co.kr/lovepc/lovefm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjI2MjI2NjMsInBhdGgiOiIvbG92ZWZtLnN0cmVhbSIsImR1cmF0aW9uIjotMSwidW5vIjoiMjEzYjM4MGYtNTgzYS00NmYyLWJmM2QtN2M4OWZjMWIxYjA1IiwiaWF0IjoxNzYyNTc5NDYzfQ.8W4kaPVi4DlG0hOF9VhZaqx_LhF9BdXIM_hqtBV98GU",
    "sbs파워fm": "https://radiolive.sbs.co.kr/powerpc/powerfm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjI2MjI2NzIsInBhdGgiOiIvcG93ZXJmbS5zdHJlYW0iLCJkdXJhdGlvbiI6LTEsInVubyI6Ijg2YzRiNmY0LWNlMWEtNDI0Ni04YTY4LTI4OTYwZmY1MTYxYyIsImlhdCI6MTc2MjU3OTQ3Mn0.bzsqw24uEDU61sQ1slyUyLGvZusH3VrD7MWWD7pB-Ww",
    "cbs음악fm": "https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/chunklist.m3u8",
}

PIN_TAG_JOIN = "[JOIN_PIN]"
PIN_TAG_PROMOTE = "[PROMOTE_PIN]"
PIN_TAG_RADIO = "[RADIO_PIN]"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ────────────────────────────────
# 🎵 YTDLP Helper (fallback 모드 포함)
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


async def ytdlp_extract_url(url: str) -> Optional[str]:
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
            if "Sign in to confirm" in msg or "Private video" in msg or "age-restricted" in msg:
                return "LOGIN_REQUIRED"
            return None
        except Exception:
            return None

    return await loop.run_in_executor(None, _extract)


async def ytdlp_search_first(query: str) -> Optional[Dict[str, str]]:
    loop = asyncio.get_running_loop()

    def _search() -> Optional[Dict[str, str]]:
        q = f"ytsearch1:{query}"
        with yt_dlp.YoutubeDL(build_ytdlp_opts()) as ydl:
            info = ydl.extract_info(q, download=False)
            if info and info.get("entries"):
                e = info["entries"][0]
                return {"title": e.get("title", "unknown"), "webpage_url": e.get("webpage_url")}
            return None

    return await loop.run_in_executor(None, _search)

# ────────────────────────────────
# 🎧 Guild 오디오 상태
# ────────────────────────────────

class GuildAudioState:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.now = None
        self.player_task = None
        self.paused = False

    def reset(self):
        self.queue = asyncio.Queue()
        self.now = None
        self.player_task = None
        self.paused = False

AUDIO = {}
def get_state(guild_id: int) -> GuildAudioState:
    if guild_id not in AUDIO:
        AUDIO[guild_id] = GuildAudioState()
    return AUDIO[guild_id]

# ────────────────────────────────
# 🧩 공통 유틸
# ────────────────────────────────

async def ensure_pinned_message(channel, content, tag, view=None):
    pins = await channel.pins()
    for m in pins:
        if tag in m.content:
            await m.edit(content=content, view=view)
            return
    sent = await channel.send(content, view=view)
    await sent.pin()

async def purge_non_pinned(channel):
    pins = await channel.pins()
    pin_ids = {m.id for m in pins}
    await channel.purge(limit=200, check=lambda m: m.id not in pin_ids)

async def connect_to_user_channel(inter):
    if not isinstance(inter.user, discord.Member) or not inter.user.voice:
        await inter.response.send_message("🎧 먼저 음성 채널에 들어가주세요.", ephemeral=True)
        return None
    vc = inter.guild.voice_client
    if vc and vc.channel != inter.user.voice.channel:
        await vc.move_to(inter.user.voice.channel)
    if not vc:
        vc = await inter.user.voice.channel.connect()
    return vc

# ────────────────────────────────
# 🔘 모달
# ────────────────────────────────

class JoinModal(Modal, title="가입 인증"):
    code = TextInput(label="가입코드", placeholder="241120", required=True)
    async def on_submit(self, i):
        ch = i.channel
        if self.code.value.strip() == JOIN_CODE:
            role = discord.utils.get(i.guild.roles, name=JOIN_ROLE_NAME)
            if role: await i.user.add_roles(role)
            await i.response.send_message("🎉 정답입니다! 클럽원 역할이 부여되었습니다!", ephemeral=False)
            asyncio.create_task(purge_non_pinned(ch))
        else:
            await i.response.send_message("❌ 정답이 아닙니다.", ephemeral=False)
            asyncio.create_task(purge_non_pinned(ch))

class PromoteModal(Modal, title="승급 인증"):
    code = TextInput(label="승급코드", placeholder="021142", required=True)
    async def on_submit(self, i):
        ch = i.channel
        if self.code.value.strip() == PROMOTE_CODE:
            role = discord.utils.get(i.guild.roles, name=PROMOTE_ROLE_NAME)
            if role: await i.user.add_roles(role)
            await i.response.send_message("🎉 정답입니다! 쟁탈원 역할이 부여되었습니다!", ephemeral=False)
            asyncio.create_task(purge_non_pinned(ch))
        else:
            await i.response.send_message("❌ 정답이 아닙니다.", ephemeral=False)
            asyncio.create_task(purge_non_pinned(ch))

class YoutubeURLModal(Modal, title="YouTube URL"):
    url = TextInput(label="URL 입력", placeholder="https://www.youtube.com/watch?v=...", required=True)
    async def on_submit(self, i):
        await play_youtube(i, self.url.value.strip())

class YoutubeSearchModal(Modal, title="YouTube 검색"):
    q = TextInput(label="검색어", placeholder="노래 제목 입력", required=True)
    async def on_submit(self, i):
        found = await ytdlp_search_first(self.q.value.strip())
        if not found:
            await i.response.send_message("검색 결과를 찾지 못했습니다.", ephemeral=True)
            return
        await play_youtube(i, found["webpage_url"], announce_title=found.get("title"))

# ────────────────────────────────
# 🔘 View 버튼
# ────────────────────────────────

class JoinView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="join"))
        self.add_item(Button(label="별명 변경", style=discord.ButtonStyle.secondary, custom_id="nick"))

class PromoteView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="승급인증", style=discord.ButtonStyle.primary, custom_id="promote"))

class RadioView(View):
    def __init__(self):
        super().__init__(timeout=None)
        radios = ["mbc표준fm","mbcfm4u","sbs러브fm","sbs파워fm","cbs음악fm"]
        for r in radios:
            self.add_item(Button(label=f"/{r}", style=discord.ButtonStyle.primary, custom_id=r))
        self.add_item(Button(label="/youtube_url", style=discord.ButtonStyle.secondary, custom_id="yturl"))
        self.add_item(Button(label="/youtube_검색", style=discord.ButtonStyle.secondary, custom_id="ytsearch"))
        self.add_item(Button(label="/정지", style=discord.ButtonStyle.danger, custom_id="stop"))

@bot.listen("on_interaction")
async def on_inter(i):
    if not i.type == discord.InteractionType.component: return
    cid = i.data.get("custom_id")
    if cid == "join": await i.response.send_modal(JoinModal())
    elif cid == "promote": await i.response.send_modal(PromoteModal())
    elif cid == "yturl": await i.response.send_modal(YoutubeURLModal())
    elif cid == "ytsearch": await i.response.send_modal(YoutubeSearchModal())
    elif cid == "stop":
        vc = i.guild.voice_client
        if vc: await vc.disconnect(force=True)
        await purge_non_pinned(i.channel)
        await i.response.send_message("⛔ 정지되었습니다.", ephemeral=False)
    elif cid in RADIO_URLS:
        await radio_play(i, cid)

# ────────────────────────────────
# 🎵 오디오 재생
# ────────────────────────────────

async def enqueue_and_play(i, stream):
    vc = await connect_to_user_channel(i)
    if not vc: return
    vc.stop()
    source = discord.FFmpegPCMAudio(stream, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn")
    vc.play(source)

async def play_youtube(i, url, announce_title=None):
    stream = await ytdlp_extract_url(url)
    if not stream:
        await i.response.send_message("⚠️ 유튜브 정보를 불러오지 못했습니다.", ephemeral=True)
        return
    if stream == "LOGIN_REQUIRED":
        await i.response.send_message("⚠️ 로그인(쿠키)이 필요한 영상입니다.", ephemeral=True)
        return
    await enqueue_and_play(i, stream)
    await i.response.send_message(f"🎵 재생 중: {announce_title or url}")

async def radio_play(i, key):
    url = RADIO_URLS.get(key)
    if not url:
        await i.response.send_message("라디오 URL 없음", ephemeral=True)
        return
    await enqueue_and_play(i, url)
    await i.response.send_message(f"📻 {key} 재생 시작!")

# ────────────────────────────────
# ✨ on_ready
# ────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ 로그인됨: {bot.user}")
    bot.add_view(JoinView())
    bot.add_view(PromoteView())
    bot.add_view(RadioView())

    guild = bot.get_guild(GUILD_ID)
    if guild:
        if (ch := guild.get_channel(CHANNEL_JOIN_ID)):
            await ensure_pinned_message(ch, f"{PIN_TAG_JOIN}\\n🎊 삐약 디스코드 서버에 오신 것을 환영합니다!\\n아래 버튼으로 가입인증!", PIN_TAG_JOIN, JoinView())
        if (ch := guild.get_channel(CHANNEL_PROMOTE_ID)):
            await ensure_pinned_message(ch, f"{PIN_TAG_PROMOTE}\\n🪖 쟁탈원 승급 인증을 진행해주세요!", PIN_TAG_PROMOTE, PromoteView())
        if (ch := guild.get_channel(CHANNEL_RADIO_ID)):
            await ensure_pinned_message(ch, f"{PIN_TAG_RADIO}\\n📡 라디오봇 접속 완료!\\n명령어 버튼을 클릭하세요!", PIN_TAG_RADIO, RadioView())
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("✅ 슬래시 명령어 동기화 완료")
    except Exception as e:
        print("명령어 동기화 실패:", e)

# ────────────────────────────────
# 🚀 실행
# ────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ DISCORD_TOKEN 미설정")
    bot.run(TOKEN)
