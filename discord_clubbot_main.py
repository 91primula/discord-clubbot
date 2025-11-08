# ───────────────────────────────────────────────────────────
# 🎛 Discord 통합 관리봇 (가입인증 + 승급인증 + 라디오/유튜브) 2025-11
# ───────────────────────────────────────────────────────────
# • 고정 안내문 메시지를 각 채널에 자동 게시/고정하고, 버튼으로 모달을 띄워 작업합니다.
# • /명령어도 모두 제공됩니다. (버튼=모달, 슬래시명령=옵션 입력)
# • 라디오/유튜브 재생, 일시정지, 정지(+채널 정리)까지 지원합니다.
# • 필요한 환경변수(.env):
#   DISCORD_TOKEN=...
#   GUILD_ID=123456789012345678
#   CHANNEL_JOIN_ID=...      # 가입인증 안내 채널 ID
#   CHANNEL_PROMOTE_ID=...   # 승급인증 안내 채널 ID
#   CHANNEL_RADIO_ID=...     # 라디오 안내 채널 ID
#   JOIN_CODE=241120
#   PROMOTE_CODE=021142
#   JOIN_ROLE_NAME=클럽원
#   PROMOTE_ROLE_NAME=쟁탈원
#   YTDLP_COOKIES=cookies.txt   # (선택) YouTube 제한 회피용 cookies.txt 경로
# 
# • 필수 런타임:
#   - FFmpeg (외부 실행파일)
#   - PyNaCl (discord.py 음성)
#   - yt-dlp (유튜브 오디오 추출)
# 
# • 주의: Koyeb/Heroku 등에서는 FFmpeg와 PyNaCl 설치가 필요합니다.
#   requirements.txt 예시: discord.py==2.4.0, PyNaCl, yt-dlp, python-dotenv
# ───────────────────────────────────────────────────────────

import os
import asyncio
from typing import Optional, List, Dict

from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput

import yt_dlp

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
YTDLP_COOKIES = os.getenv("YTDLP_COOKIES")  # 선택

# 라디오 스트림 URL (필요 시 수정)
RADIO_URLS: Dict[str, str] = {
    "mbc표준fm": "https://minisw.imbc.com/dsfm/_definst_/sfm.stream/playlist.m3u8",
    "mbcfm4u": "https://minisw.imbc.com/fm4u/_definst_/fm4u.stream/playlist.m3u8",
    "sbs러브fm": "https://sbs-live.akamaized.net/hls/live/2005540/SBS_Love_FM/playlist.m3u8",
    "sbs파워fm": "https://sbs-live.akamaized.net/hls/live/2005541/SBS_Power_FM/playlist.m3u8",
    "cbs음악fm": "https://wowza.cbs.co.kr/CBS_MFM/_definst_/MFM.stream/playlist.m3u8",
}

# 고정 안내문에 심어둘 식별 태그 (메시지 찾기 용)
PIN_TAG_JOIN = "[JOIN_PIN]"
PIN_TAG_PROMOTE = "[PROMOTE_PIN]"
PIN_TAG_RADIO = "[RADIO_PIN]"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ────────────────────────────────
# YT-DLP 헬퍼
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
    }
    if YTDLP_COOKIES and os.path.exists(YTDLP_COOKIES):
        opts["cookiefile"] = YTDLP_COOKIES
    return opts

async def ytdlp_extract_url(url: str) -> Optional[str]:
    loop = asyncio.get_running_loop()
    def _extract() -> Optional[str]:
        with yt_dlp.YoutubeDL(build_ytdlp_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return None
            if "entries" in info:
                info = info["entries"][0]
            return info.get("url")
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
# 길드별 오디오 상태
# ────────────────────────────────

class GuildAudioState:
    def __init__(self):
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.now: Optional[str] = None
        self.player_task: Optional[asyncio.Task] = None
        self.paused: bool = False

    def reset(self):
        self.queue = asyncio.Queue()
        self.now = None
        self.player_task = None
        self.paused = False

AUDIO: Dict[int, GuildAudioState] = {}

def get_state(guild_id: int) -> GuildAudioState:
    if guild_id not in AUDIO:
        AUDIO[guild_id] = GuildAudioState()
    return AUDIO[guild_id]

# ────────────────────────────────
# 공통 유틸
# ────────────────────────────────

async def ensure_pinned_message(channel: discord.TextChannel, content: str, tag: str, view: Optional[View] = None) -> None:
    """채널에 tag가 포함된 고정 메시지가 없다면 새로 보내고 고정. 있으면 그대로 둠."""
    pins = await channel.pins()
    for m in pins:
        if tag in m.content:
            # 이미 있음 → 최신 안내로 업데이트(내용이 바뀌었으면)
            if m.content != content:
                await m.edit(content=content, view=view)
            else:
                if view is not None:
                    try:
                        await m.edit(view=view)
                    except discord.HTTPException:
                        pass
            return
    # 없으면 새로 게시 후 고정
    sent = await channel.send(content, view=view)
    try:
        await sent.pin()
    except discord.HTTPException:
        pass

async def purge_non_pinned(channel: discord.TextChannel) -> None:
    pins = await channel.pins()
    pin_ids = {m.id for m in pins}
    def _not_pinned(m: discord.Message) -> bool:
        return m.id not in pin_ids
    await channel.purge(limit=200, check=_not_pinned)

async def cleanup_later(channel: discord.TextChannel, delay: int) -> None:
    await asyncio.sleep(delay)
    await purge_non_pinned(channel)

async def connect_to_user_channel(inter: discord.Interaction) -> Optional[discord.VoiceClient]:
    if not inter.user or not isinstance(inter.user, discord.Member):
        await inter.response.send_message("음성 채널 정보를 확인할 수 없습니다.", ephemeral=True)
        return None
    voice = inter.user.voice
    if not voice or not voice.channel:
        await inter.response.send_message("먼저 음성 채널에 접속해주세요.", ephemeral=True)
        return None
    vc = inter.guild.voice_client
    if vc and vc.channel.id != voice.channel.id:
        await vc.move_to(voice.channel)
    if not vc:
        vc = await voice.channel.connect()
    return vc

# ────────────────────────────────
# 모달
# ────────────────────────────────

class JoinVerifyModal(Modal, title="가입 인증"):
    code: TextInput
    def __init__(self):
        super().__init__()
        self.code = TextInput(label="가입인증 코드", placeholder="예: 241120", required=True, max_length=10)
        self.add_item(self.code)

    async def on_submit(self, interaction: discord.Interaction):
        ch = interaction.channel
        if self.code.value.strip() == JOIN_CODE:
            role = discord.utils.get(interaction.guild.roles, name=JOIN_ROLE_NAME)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="가입 인증 완료")
                except discord.HTTPException:
                    pass
            await interaction.response.send_message("🎉정답입니다!! 클럽원 역할이 부여되었습니다!! 별명을 인게임 캐릭명으로 변경해주세요!", ephemeral=False)
            # 5초 후 고정 제외 삭제
            if isinstance(ch, discord.TextChannel):
                asyncio.create_task(cleanup_later(ch, 5))
        else:
            await interaction.response.send_message("❌ 정답이 아닙니다", ephemeral=False)
            if isinstance(ch, discord.TextChannel):
                asyncio.create_task(cleanup_later(ch, 30))

class PromoteVerifyModal(Modal, title="승급 인증"):
    code: TextInput
    def __init__(self):
        super().__init__()
        self.code = TextInput(label="승급인증 코드", placeholder="예: 021142", required=True, max_length=10)
        self.add_item(self.code)

    async def on_submit(self, interaction: discord.Interaction):
        ch = interaction.channel
        if self.code.value.strip() == PROMOTE_CODE:
            role = discord.utils.get(interaction.guild.roles, name=PROMOTE_ROLE_NAME)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="승급 인증 완료")
                except discord.HTTPException:
                    pass
            await interaction.response.send_message("🎉정답입니다!! 쟁탈원 역할이 부여되었습니다!", ephemeral=False)
            if isinstance(ch, discord.TextChannel):
                asyncio.create_task(cleanup_later(ch, 5))
        else:
            await interaction.response.send_message("❌ 정답이 아닙니다", ephemeral=False)
            if isinstance(ch, discord.TextChannel):
                asyncio.create_task(cleanup_later(ch, 30))

class NickChangeModal(Modal, title="별명 변경"):
    nick: TextInput
    def __init__(self):
        super().__init__()
        self.nick = TextInput(label="새 별명 (인게임 캐릭명)", placeholder="예: 삐약전사", required=True, max_length=32)
        self.add_item(self.nick)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.user.edit(nick=self.nick.value.strip())
            await interaction.response.send_message("✅ 별명을 변경했습니다!", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("⚠️ 별명 변경에 실패했습니다. 권한을 확인해주세요.", ephemeral=True)

class YoutubeURLModal(Modal, title="YouTube 링크 재생"):
    url: TextInput
    def __init__(self):
        super().__init__()
        self.url = TextInput(label="YouTube URL", placeholder="https://www.youtube.com/watch?v=...", required=True)
        self.add_item(self.url)

    async def on_submit(self, interaction: discord.Interaction):
        await play_youtube(interaction, self.url.value.strip())

class YoutubeSearchModal(Modal, title="YouTube 검색 재생"):
    query: TextInput
    def __init__(self):
        super().__init__()
        self.query = TextInput(label="검색어", placeholder="노래 제목 or 키워드", required=True)
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        found = await ytdlp_search_first(self.query.value.strip())
        if not found:
            await interaction.response.send_message("검색 결과를 찾지 못했습니다.", ephemeral=True)
            return
        await play_youtube(interaction, found["webpage_url"], announce_title=found.get("title"))

# ────────────────────────────────
# 버튼 View (Persistent)
# ────────────────────────────────

class JoinView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="btn_join_verify"))
        self.add_item(Button(label="별명 변경 안내", style=discord.ButtonStyle.secondary, custom_id="btn_nick_change"))

    @discord.ui.button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="btn_join_verify_dup")
    async def _dup_a(self, interaction: discord.Interaction, button: Button):
        pass  # placeholder; 실제 버튼은 위 add_item으로 생성 (persistent용)

class PromoteView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="승급인증", style=discord.ButtonStyle.primary, custom_id="btn_promote_verify"))

    @discord.ui.button(label="승급인증", style=discord.ButtonStyle.primary, custom_id="btn_promote_verify_dup")
    async def _dup_b(self, interaction: discord.Interaction, button: Button):
        pass

class RadioView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # 라디오 5종
        self.add_item(Button(label="/mbc표준fm", style=discord.ButtonStyle.primary, custom_id="btn_radio_mbc_sfm"))
        self.add_item(Button(label="/mbcfm4u", style=discord.ButtonStyle.primary, custom_id="btn_radio_mbc_fm4u"))
        self.add_item(Button(label="/sbs러브fm", style=discord.ButtonStyle.primary, custom_id="btn_radio_sbs_love"))
        self.add_item(Button(label="/sbs파워fm", style=discord.ButtonStyle.primary, custom_id="btn_radio_sbs_power"))
        self.add_item(Button(label="/cbs음악fm", style=discord.ButtonStyle.primary, custom_id="btn_radio_cbs_mfm"))
        # 유튜브
        self.add_item(Button(label="/youtube_url", style=discord.ButtonStyle.secondary, custom_id="btn_youtube_url"))
        self.add_item(Button(label="/youtube_검색", style=discord.ButtonStyle.secondary, custom_id="btn_youtube_search"))
        # 컨트롤
        self.add_item(Button(label="/재생", style=discord.ButtonStyle.success, custom_id="btn_play"))
        self.add_item(Button(label="/일시정지", style=discord.ButtonStyle.secondary, custom_id="btn_pause"))
        self.add_item(Button(label="/정지", style=discord.ButtonStyle.danger, custom_id="btn_stop"))

    @discord.ui.button(label="/dummy", style=discord.ButtonStyle.secondary, custom_id="btn_dummy")
    async def _dup_c(self, interaction: discord.Interaction, button: Button):
        pass

# 글로벌 persistent 핸들러 등록
@bot.listen("on_interaction")
async def persistent_button_router(interaction: discord.Interaction):
    if not interaction.type == discord.InteractionType.component:
        return
    cid = interaction.data.get("custom_id") if interaction.data else None
    if cid == "btn_join_verify":
        await interaction.response.send_modal(JoinVerifyModal())
    elif cid == "btn_nick_change":
        await interaction.response.send_modal(NickChangeModal())
    elif cid == "btn_promote_verify":
        await interaction.response.send_modal(PromoteVerifyModal())
    elif cid == "btn_radio_mbc_sfm":
        await radio_play(interaction, "mbc표준fm")
    elif cid == "btn_radio_mbc_fm4u":
        await radio_play(interaction, "mbcfm4u")
    elif cid == "btn_radio_sbs_love":
        await radio_play(interaction, "sbs러브fm")
    elif cid == "btn_radio_sbs_power":
        await radio_play(interaction, "sbs파워fm")
    elif cid == "btn_radio_cbs_mfm":
        await radio_play(interaction, "cbs음악fm")
    elif cid == "btn_youtube_url":
        await interaction.response.send_modal(YoutubeURLModal())
    elif cid == "btn_youtube_search":
        await interaction.response.send_modal(YoutubeSearchModal())
    elif cid == "btn_play":
        await cmd_play(interaction)
    elif cid == "btn_pause":
        await cmd_pause(interaction)
    elif cid == "btn_stop":
        await cmd_stop(interaction, cleanup=True)

# ────────────────────────────────
# 고정 안내문 내용
# ────────────────────────────────

JOIN_TEXT = f"""
{PIN_TAG_JOIN}
🎊✨삐약 디스코드 서버에 오신 것을 환영합니다!✨🎊\n🎊✨먼저 운영진 또는 오픈톡 공지사항을 통해 디스코드 인증코드를 확인해주세요!\n✨\n🪪✨ 1️⃣가입 인증 안내\n가입 인증을 위해 아래 버튼을 눌러주세요\n(가입인증)\n\n🪪✨ 2️⃣별명 변경 안내, 캐릭명으로 별명을 변경하세요\n(별명 변경 안내)
""".strip()

PROMOTE_TEXT = f"""
{PIN_TAG_PROMOTE}
🪖 쟁탈원으로 승급하기 위해서는\n🪖 운영진이 안내해준 승인인증 코드를 입력해주시기 바랍니다. \n아래 버튼을 눌러 승급 인증을 진행해주세요\n(승급인증)
""".strip()

RADIO_TEXT = f"""
{PIN_TAG_RADIO}
📡✨ 라디오봇 접속 완료!\n🎶 음성 채널에 들어간 후 아래 명령어 사용 가능\n\n📻 /mbc표준fm   📻 /mbcfm4u   📻 /sbs러브fm   📻 /sbs파워fm   📻 /cbs음악fm\n🎧 /youtube_url   🎧 /youtube_검색\n▶️ /재생   ⏸️/일시정지   ⛔ /정지\n\n⭐ 모든 봇 실행할 때는 명렁어상 아이콘 확인 후 실행
""".strip()

# ────────────────────────────────
# 오디오 재생 로직
# ────────────────────────────────

async def audio_player_loop(inter: discord.Interaction, vc: discord.VoiceClient):
    state = get_state(inter.guild_id)
    while True:
        url = await state.queue.get()
        state.now = url
        # yt / radio 모두 FFmpeg로 재생
        source = discord.FFmpegPCMAudio(url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn")
        vc.play(source)
        while vc.is_playing() or state.paused:
            await asyncio.sleep(0.5)
        state.now = None

async def enqueue_and_ensure_player(inter: discord.Interaction, stream_url: str) -> None:
    vc = inter.guild.voice_client
    if not vc:
        vc = await connect_to_user_channel(inter)
        if not vc:
            return
    state = get_state(inter.guild_id)
    await state.queue.put(stream_url)
    if not state.player_task or state.player_task.done():
        state.player_task = asyncio.create_task(audio_player_loop(inter, vc))

async def radio_play(inter: discord.Interaction, key: str) -> None:
    url = RADIO_URLS.get(key)
    if not url:
        await inter.response.send_message("라디오 URL을 찾을 수 없습니다.", ephemeral=True)
        return
    vc = await connect_to_user_channel(inter)
    if not vc:
        return
    # 라디오는 즉시 재생 (큐 초기화)
    state = get_state(inter.guild_id)
    if vc.is_playing():
        vc.stop()
    state.reset()
    source = discord.FFmpegPCMAudio(url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn")
    vc.play(source)
    await inter.response.send_message(f"📻 라디오 재생: **{key}**", ephemeral=False)

async def play_youtube(inter: discord.Interaction, url: str, announce_title: Optional[str] = None) -> None:
    vc = await connect_to_user_channel(inter)
    if not vc:
        return
    # 유튜브는 큐에 추가
    stream = await ytdlp_extract_url(url)
    if not stream:
        await inter.response.send_message("YouTube 오디오 URL을 추출하지 못했습니다.", ephemeral=True)
        return
    await enqueue_and_ensure_player(inter, stream)
    title = announce_title or url
    if not inter.response.is_done():
        await inter.response.send_message(f"🎵 대기열 추가: {title}", ephemeral=False)
    else:
        await inter.followup.send(f"🎵 대기열 추가: {title}")

# ────────────────────────────────
# 슬래시 명령어
# ────────────────────────────────

guild_obj = discord.Object(id=GUILD_ID) if GUILD_ID else None

def gscope():
    return guild_obj

@bot.tree.command(name="가입인증", description="가입 인증 코드를 입력합니다.", guild=gscope())
async def cmd_join_verify(interaction: discord.Interaction, 코드: str):
    # 슬래시 버전: 바로 검증
    if 코드.strip() == JOIN_CODE:
        role = discord.utils.get(interaction.guild.roles, name=JOIN_ROLE_NAME)
        if role:
            try:
                await interaction.user.add_roles(role, reason="가입 인증 완료(슬래시)")
            except discord.HTTPException:
                pass
        await interaction.response.send_message("🎉정답입니다!! 클럽원 역할이 부여되었습니다!! 별명을 인게임 캐릭명으로 변경해주세요!", ephemeral=False)
        if isinstance(interaction.channel, discord.TextChannel):
            asyncio.create_task(cleanup_later(interaction.channel, 5))
    else:
        await interaction.response.send_message("❌ 정답이 아닙니다", ephemeral=False)
        if isinstance(interaction.channel, discord.TextChannel):
            asyncio.create_task(cleanup_later(interaction.channel, 30))

@bot.tree.command(name="승급인증", description="승급 인증 코드를 입력합니다.", guild=gscope())
async def cmd_promote_verify(interaction: discord.Interaction, 코드: str):
    if 코드.strip() == PROMOTE_CODE:
        role = discord.utils.get(interaction.guild.roles, name=PROMOTE_ROLE_NAME)
        if role:
            try:
                await interaction.user.add_roles(role, reason="승급 인증 완료(슬래시)")
            except discord.HTTPException:
                pass
        await interaction.response.send_message("🎉정답입니다!! 쟁탈원 역할이 부여되었습니다!", ephemeral=False)
        if isinstance(interaction.channel, discord.TextChannel):
            asyncio.create_task(cleanup_later(interaction.channel, 5))
    else:
        await interaction.response.send_message("❌ 정답이 아닙니다", ephemeral=False)
        if isinstance(interaction.channel, discord.TextChannel):
            asyncio.create_task(cleanup_later(interaction.channel, 30))

@bot.tree.command(name="nick", description="별명을 변경합니다.", guild=gscope())
async def cmd_nick(interaction: discord.Interaction, 새별명: str):
    try:
        await interaction.user.edit(nick=새별명.strip())
        await interaction.response.send_message("✅ 별명을 변경했습니다!", ephemeral=True)
    except discord.HTTPException:
        await interaction.response.send_message("⚠️ 별명 변경에 실패했습니다. 권한을 확인해주세요.", ephemeral=True)

# 라디오 5종
@bot.tree.command(name="mbc표준fm", description="MBC 표준FM 재생", guild=gscope())
async def cmd_mbc_sfm(interaction: discord.Interaction):
    await radio_play(interaction, "mbc표준fm")

@bot.tree.command(name="mbcfm4u", description="MBC FM4U 재생", guild=gscope())
async def cmd_mbc_fm4u(interaction: discord.Interaction):
    await radio_play(interaction, "mbcfm4u")

@bot.tree.command(name="sbs러브fm", description="SBS 러브FM 재생", guild=gscope())
async def cmd_sbs_love(interaction: discord.Interaction):
    await radio_play(interaction, "sbs러브fm")

@bot.tree.command(name="sbs파워fm", description="SBS 파워FM 재생", guild=gscope())
async def cmd_sbs_power(interaction: discord.Interaction):
    await radio_play(interaction, "sbs파워fm")

@bot.tree.command(name="cbs음악fm", description="CBS 음악FM 재생", guild=gscope())
async def cmd_cbs_mfm(interaction: discord.Interaction):
    await radio_play(interaction, "cbs음악fm")

# YouTube
@bot.tree.command(name="youtube_url", description="YouTube URL로 재생", guild=gscope())
async def cmd_youtube_url(interaction: discord.Interaction, url: str):
    await play_youtube(interaction, url)

@bot.tree.command(name="youtube_검색", description="YouTube 검색 후 첫 영상 재생", guild=gscope())
async def cmd_youtube_search(interaction: discord.Interaction, 키워드: str):
    found = await ytdlp_search_first(키워드)
    if not found:
        await interaction.response.send_message("검색 결과를 찾지 못했습니다.", ephemeral=True)
        return
    await play_youtube(interaction, found["webpage_url"], announce_title=found.get("title"))

# 컨트롤
@bot.tree.command(name="재생", description="일시정지 해제/재생", guild=gscope())
async def cmd_play(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and not vc.is_playing():
        try:
            vc.resume()
        except Exception:
            pass
    await interaction.response.send_message("▶️ 재생", ephemeral=True)

@bot.tree.command(name="일시정지", description="현재 재생을 일시정지", guild=gscope())
async def cmd_pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        try:
            vc.pause()
        except Exception:
            pass
    await interaction.response.send_message("⏸️ 일시정지", ephemeral=True)

@bot.tree.command(name="정지", description="재생을 정지하고 채널을 정리", guild=gscope())
async def cmd_stop(interaction: discord.Interaction, cleanup: bool = False):
    vc = interaction.guild.voice_client
    if vc:
        try:
            vc.stop()
            await vc.disconnect(force=True)
        except Exception:
            pass
    get_state(interaction.guild_id).reset()
    await interaction.response.send_message("⛔ 정지", ephemeral=False)
    if cleanup and isinstance(interaction.channel, discord.TextChannel):
        await purge_non_pinned(interaction.channel)

# ────────────────────────────────
# on_ready: 명령어 동기화 + 고정 안내문 보장
# ────────────────────────────────

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    # 명령어 동기화 (길드 우선)
    try:
        if GUILD_ID:
            await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        else:
            await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print("Command sync failed:", e)

    # Persistent Views 등록 (재시작 후에도 버튼 작동)
    try:
        bot.add_view(JoinView())
        bot.add_view(PromoteView())
        bot.add_view(RadioView())
    except Exception:
        pass

    # 고정 안내 보장
    guild = bot.get_guild(GUILD_ID) if GUILD_ID else None
    if guild:
        if CHANNEL_JOIN_ID:
            ch: Optional[discord.TextChannel] = guild.get_channel(CHANNEL_JOIN_ID)  # type: ignore
            if ch and isinstance(ch, discord.TextChannel):
                await ensure_pinned_message(ch, JOIN_TEXT, PIN_TAG_JOIN, view=JoinView())
        if CHANNEL_PROMOTE_ID:
            ch: Optional[discord.TextChannel] = guild.get_channel(CHANNEL_PROMOTE_ID)  # type: ignore
            if ch and isinstance(ch, discord.TextChannel):
                await ensure_pinned_message(ch, PROMOTE_TEXT, PIN_TAG_PROMOTE, view=PromoteView())
        if CHANNEL_RADIO_ID:
            ch: Optional[discord.TextChannel] = guild.get_channel(CHANNEL_RADIO_ID)  # type: ignore
            if ch and isinstance(ch, discord.TextChannel):
                await ensure_pinned_message(ch, RADIO_TEXT, PIN_TAG_RADIO, view=RadioView())

# ────────────────────────────────
# 실행
# ────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN 이(가) 설정되지 않았습니다.")
    bot.run(TOKEN)
