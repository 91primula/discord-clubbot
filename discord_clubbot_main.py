# ───────────────────────────────────────────────────────────
# Discord ClubBot - 통합 가입/승급/라디오/유튜브 관리봇 (2025 최신 완성판)
# discord_clubbot_main.py
# ───────────────────────────────────────────────────────────
import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from dotenv import load_dotenv
import yt_dlp
import functools

# ───────────────────────────────────────────────────────────
# ✅ 환경 변수 로드
# ───────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')

# ───────────────────────────────────────────────────────────
# ⚙️ 기본 설정
# ───────────────────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
yt_dlp.utils.bug_reports_message = lambda: ''

# ───────────────────────────────────────────────────────────
# 🎵 유튜브 관련 설정
# ───────────────────────────────────────────────────────────
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'geo_bypass': True,
    'cookiefile': 'cookies.txt'
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# ───────────────────────────────────────────────────────────
# 🎮 가입 인증 버튼
# ───────────────────────────────────────────────────────────
class JoinVerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="join_verify"))

# ───────────────────────────────────────────────────────────
# 🪪 별명 변경 버튼
# ───────────────────────────────────────────────────────────
class NicknameChangeView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="별명변경", style=discord.ButtonStyle.success, custom_id="nickname_change"))

# ───────────────────────────────────────────────────────────
# 🎙️ 오디오 재생 관련
# ───────────────────────────────────────────────────────────
async def ensure_voice(interaction):
    """사용자가 음성 채널에 있으면 연결"""
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("⚠️ 먼저 음성채널에 들어가주세요!", ephemeral=True)
        return None
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not vc:
        vc = await interaction.user.voice.channel.connect()
    elif vc.channel != interaction.user.voice.channel:
        await vc.move_to(interaction.user.voice.channel)
    return vc

# ───────────────────────────────────────────────────────────
# 🎧 유튜브 재생
# ───────────────────────────────────────────────────────────
async def start_youtube_play(interaction, url):
    vc = await ensure_voice(interaction)
    if not vc:
        return
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, url, download=False))
    song = data['url']
    title = data.get('title', '알 수 없는 제목')
    vc.stop()
    vc.play(discord.FFmpegPCMAudio(song))
    await interaction.response.send_message(f"🎶 지금 재생 중: **{title}**")

# 🎧 유튜브 검색
async def start_youtube_search(interaction, query):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, f"ytsearch:{query}", download=False))
    if not data or 'entries' not in data or len(data['entries']) == 0:
        await interaction.response.send_message("검색 결과가 없습니다.", ephemeral=True)
        return
    video = data['entries'][0]
    await start_youtube_play(interaction, f"https://www.youtube.com/watch?v={video['id']}")

# ───────────────────────────────────────────────────────────
# 🔘 유튜브 모달
# ───────────────────────────────────────────────────────────
class YoutubeURLModal(Modal, title="🎧 유튜브 URL로 재생"):
    url = TextInput(label="유튜브 URL 입력", placeholder="https://www.youtube.com/watch?v=...")

    async def on_submit(self, interaction):
        await start_youtube_play(interaction, self.url.value)

class YoutubeSearchModal(Modal, title="🔎 유튜브 검색으로 재생"):
    query = TextInput(label="검색어 입력", placeholder="노래 제목 또는 키워드 입력")

    async def on_submit(self, interaction):
        await start_youtube_search(interaction, self.query.value)

# ───────────────────────────────────────────────────────────
# 📻 라디오 버튼
# ───────────────────────────────────────────────────────────
RADIO_URLS = {
    "mbc표준fm": "https://minisw.imbc.com/dsfm/_definst_/sfm.stream/playlist.m3u8?_lsu_sa_=62010F1C837937A4FF49C56D35C12A40E51F3ED57D0512493FD0D0aE664C3DD6EAaEA3F030E25C4CF0183F7121b991791BDD256A06B76A190B69E131229B405CFDCF3FFAD11651E510B19C9FBF0F076A0CCF560E291EC8B289FF62DF15A9EF80500584BD0E3E2A6F2A9367A07A1C49CD",
    "mbcfm4u": "https://minimw.imbc.com/dmfm/_definst_/mfm.stream/playlist.m3u8?_lsu_sa_=66017C1F137E3AE44846E57138314C4B854E3AB5860702DA3660C8a6066233A6D7a2E3A235D25F4B5003342166b7111060C8297A51725D8EE3D35A0351618E0E11DE3621B89898A2DD8FE6A3CB43EFA416BAFA5FF0B8AB2D8238B9EB320BDE72FE21F1E1494B3E182642ED7DFE5911A3",
    "sbs러브fm": "https://radiolive.sbs.co.kr/lovepc/lovefm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjI0ODIxOTksInBhdGgiOiIvbG92ZWZtLnN0cmVhbSIsImR1cmF0aW9uIjotMSwidW5vIjoiNWRjNjgzYzItYjc4OS00NDQzLWJkNDktNGFjYzk0NDk5YTM1IiwiaWF0IjoxNzYyNDM4OTk5fQ.4jkkaI5C8hcjkTsEQfmz7QFDlcj3ZikVyiEgXg1DL_0",
    "sbs파워fm": "https://radiolive.sbs.co.kr/powerpc/powerfm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjI0ODIyMTIsInBhdGgiOiIvcG93ZXJmbS5zdHJlYW0iLCJkdXJhdGlvbiI6LTEsInVubyI6IjAwZWM5YzhhLThhZGYtNDUwOS05ZTQyLTljMzg5OGY0ZDAxMSIsImlhdCI6MTc2MjQzOTAxMn0.NNpO7hA4rYedMNT4vAauuhICIWhMAl0wJEzRo2gUf_4",
    "cbs음악fm": "https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/chunklist.m3u8"
}

class RadioButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        for label in ["📻 MBC 표준FM", "🎵 MBC FM4U", "🎶 SBS 러브FM", "🎧 SBS 파워FM", "🎼 CBS 음악FM"]:
            self.add_item(Button(label=label, style=discord.ButtonStyle.primary, custom_id=f"radio_{label}"))

# ───────────────────────────────────────────────────────────
# 🎚️ 재생 제어 버튼
# ───────────────────────────────────────────────────────────
class ControlButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="▶ 재생", style=discord.ButtonStyle.success, custom_id="play"))
        self.add_item(Button(label="⏸ 일시정지", style=discord.ButtonStyle.secondary, custom_id="pause"))
        self.add_item(Button(label="⏹ 정지", style=discord.ButtonStyle.danger, custom_id="stop"))

# ───────────────────────────────────────────────────────────
# ✅ 봇 시작 시 자동 안내 메시지 생성
# ───────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {bot.user}")
    print(f"🔍 GUILD_ID = {GUILD_ID}")

    guild = bot.get_guild(int(GUILD_ID))
    if not guild:
        print("❌ [오류] GUILD_ID로 서버를 찾지 못했습니다. .env 설정 확인!")
        return
    print(f"🏠 연결된 서버: {guild.name}")

    join_channel = discord.utils.get(guild.text_channels, name="가입인증")
    if join_channel:
        print(f"📢 가입인증 채널 찾음: {join_channel.name}")
        pinned = await join_channel.pins()
        if not pinned:
            msg1 = await join_channel.send(
                "🎊✨삐약 디스코드 서버에 오신 것을 환영합니다!✨🎊\n"
                "🪪 1️⃣가입 인증 안내\n"
                "아래 버튼을 눌러 가입 인증을 진행해주세요\n"
                "(가입인증) ⬇️",
                view=JoinVerifyView()
            )
            await msg1.pin()

            msg2 = await join_channel.send(
                "🪪 2️⃣별명 변경 안내(가입 인증 후)\n"
                "아래 버튼을 눌러 별명 변경을 진행해주세요\n"
                "(별명변경) ⬇️",
                view=NicknameChangeView()
            )
            await msg2.pin()
        else:
            print("📌 기존 고정 메시지가 존재함.")
    else:
        print("⚠️ [주의] '가입인증' 채널을 찾을 수 없습니다. 이름 확인!")

    radio_channel = discord.utils.get(guild.text_channels, name="라디오")
    if radio_channel:
        print(f"📡 라디오 채널 찾음: {radio_channel.name}")
        radio_msg = (
            "📡✨ 라디오봇 접속 완료!\n"
            "🎶 아래 버튼으로 라디오 또는 유튜브를 재생하세요.\n"
            "📻 MBC, SBS, CBS 실시간 방송 지원\n"
            "🎧 유튜브 검색 및 URL 재생 가능"
        )
        await radio_channel.send(radio_msg, view=RadioButtons())
        await radio_channel.send("🎛 재생 제어", view=ControlButtons())
    else:
        print("⚠️ [주의] '라디오' 채널을 찾을 수 없습니다. 이름 확인!")

    print("✅ 모든 시스템 준비 완료!")

# ───────────────────────────────────────────────────────────
# 🧩 실행
# ───────────────────────────────────────────────────────────
bot.run(TOKEN)
