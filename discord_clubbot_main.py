# ───────────────────────────────────────────────────────────
# Discord ClubBot - 통합 가입/승급/라디오 관리봇 (2025 완전통합판)
# 파일명: discord_clubbot_main.py
# ───────────────────────────────────────────────────────────
import os
import asyncio
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import functools

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', '0'))
CHANNEL_JOIN_ID = int(os.getenv('CHANNEL_JOIN_ID', '0'))
CHANNEL_PROMOTE_ID = int(os.getenv('CHANNEL_PROMOTE_ID', '0'))
CHANNEL_RADIO_ID = int(os.getenv('CHANNEL_RADIO_ID', '0'))

ROLE_CLUBER_ID = int(os.getenv('ROLE_CLUBER_ID', '0'))
ROLE_FIGHTER_ID = int(os.getenv('ROLE_FIGHTER_ID', '0'))

JOIN_CODE = os.getenv('JOIN_CODE', '241120')
PROMOTE_CODE = os.getenv('PROMOTE_CODE', '021142')

RADIOS = {
    'mbc표준fm': os.getenv('STREAM_MBC', 'https://example.com/mbc_standard_stream.mp3'),
    'mbcfm4u': os.getenv('STREAM_FM4U', 'https://example.com/mbc_fm4u_stream.mp3'),
    'sbs러브fm': os.getenv('STREAM_SBS_LOVE', 'https://example.com/sbs_love_stream.mp3'),
    'sbs파워fm': os.getenv('STREAM_SBS_POWER', 'https://example.com/sbs_power_stream.mp3'),
    'cbs음악fm': os.getenv('STREAM_CBS', 'https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/chunklist.m3u8')
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ────────────────────────────────
# 유틸 함수
# ────────────────────────────────
async def ensure_pinned_message(channel: discord.TextChannel, content: str, view: discord.ui.View):
    pinned = [m async for m in channel.pins()]
    key = content.splitlines()[0]
    for m in pinned:
        if m.content.startswith(key):
            return m
    msg = await channel.send(content, view=view)
    await msg.pin()
    return msg

async def delete_non_pinned_messages_after(channel: discord.TextChannel, delay: int):
    await asyncio.sleep(delay)
    pinned = [m async for m in channel.pins()]
    pinned_ids = {m.id for m in pinned}
    async for m in channel.history(limit=200):
        if m.id not in pinned_ids:
            try:
                await m.delete()
            except:
                pass

# ────────────────────────────────
# 모달 (코드입력/닉변경/유튜브입력)
# ────────────────────────────────
class CodeModal(discord.ui.Modal, title="인증 코드 입력"):
    code = discord.ui.TextInput(label="인증 코드", placeholder="코드를 입력하세요")

    def __init__(self, correct_code, role_id, role_name):
        super().__init__()
        self.correct_code = correct_code
        self.role_id = role_id
        self.role_name = role_name

    async def on_submit(self, interaction: discord.Interaction):
        if self.code.value.strip() == self.correct_code:
            role = interaction.guild.get_role(self.role_id)
            if role:
                await interaction.user.add_roles(role)
            await interaction.response.send_message(f"🎉 정답입니다! {self.role_name} 역할이 부여되었습니다.")
        else:
            await interaction.response.send_message("❌ 인증 실패! 코드를 다시 확인하세요.", ephemeral=True)
        asyncio.create_task(delete_non_pinned_messages_after(interaction.channel, 5))


class NickModal(discord.ui.Modal, title="별명 변경"):
    nick = discord.ui.TextInput(label="변경할 닉네임", max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.user.edit(nick=self.nick.value)
            await interaction.response.send_message("✅ 닉네임이 변경되었습니다.", ephemeral=True)
        except:
            await interaction.response.send_message("⚠️ 닉네임 변경 실패: 권한 확인 필요", ephemeral=True)


class YoutubeURLModal(discord.ui.Modal, title="YouTube URL 재생"):
    url = discord.ui.TextInput(label="유튜브 링크", placeholder="https://youtube.com/...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await start_youtube_play(interaction, self.url.value)


class YoutubeSearchModal(discord.ui.Modal, title="YouTube 검색 재생"):
    query = discord.ui.TextInput(label="검색어", placeholder="검색할 단어를 입력하세요", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await start_youtube_search(interaction, self.query.value)

# ────────────────────────────────
# 뷰 / 버튼
# ────────────────────────────────
class JoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="가입인증", style=discord.ButtonStyle.primary)
    async def join(self, interaction, button):
        await interaction.response.send_modal(CodeModal(JOIN_CODE, ROLE_CLUBER_ID, "클럽원"))
    @discord.ui.button(label="별명변경", style=discord.ButtonStyle.secondary)
    async def nick(self, interaction, button):
        await interaction.response.send_modal(NickModal())


class PromoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="승급인증", style=discord.ButtonStyle.primary)
    async def promote(self, interaction, button):
        await interaction.response.send_modal(CodeModal(PROMOTE_CODE, ROLE_FIGHTER_ID, "쟁탈원"))

# ────────────────────────────────
# 라디오 및 유튜브 제어 뷰
# ────────────────────────────────
class RadioView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # 라디오 5개 버튼
        for key in RADIOS.keys():
            self.add_item(RadioButton(label=key))
        # 유튜브 재생 버튼
        self.add_item(YoutubeURLButton())
        self.add_item(YoutubeSearchButton())
        # 재생 컨트롤
        self.add_item(ControlButton("▶ 재생", "resume", discord.ButtonStyle.success))
        self.add_item(ControlButton("⏸ 일시정지", "pause", discord.ButtonStyle.secondary))
        self.add_item(ControlButton("⛔ 정지", "stop", discord.ButtonStyle.danger))


class RadioButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction):
        await start_radio_playback(interaction, self.label)


class YoutubeURLButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🎥 YouTube URL", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        await interaction.response.send_modal(YoutubeURLModal())


class YoutubeSearchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔍 YouTube 검색", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        await interaction.response.send_modal(YoutubeSearchModal())


class ControlButton(discord.ui.Button):
    def __init__(self, label, action, style):
        super().__init__(label=label, style=style)
        self.action = action

    async def callback(self, interaction):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("🎧 음성 연결이 없습니다.", ephemeral=True)
            return
        if self.action == "resume":
            if vc.is_paused():
                vc.resume()
                await interaction.response.send_message("▶ 재생을 다시 시작했습니다.")
        elif self.action == "pause":
            if vc.is_playing():
                vc.pause()
                await interaction.response.send_message("⏸ 일시정지했습니다.")
        elif self.action == "stop":
            await stop_and_disconnect(vc)
            await interaction.response.send_message("⛔ 재생 정지 및 음성채널 퇴장 완료.")
            asyncio.create_task(delete_non_pinned_messages_after(interaction.channel, 1))

# ────────────────────────────────
# 오디오 관련 함수
# ────────────────────────────────
FFMPEG_OPTIONS = {'options': '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
YTDL_OPTS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

async def start_radio_playback(interaction, key):
    await interaction.response.defer(ephemeral=True)
    member = interaction.user
    if not member.voice or not member.voice.channel:
        await interaction.followup.send("⚠️ 음성채널에 먼저 접속하세요.", ephemeral=True)
        return
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        vc = await member.voice.channel.connect()

    stream = RADIOS.get(key)
    if not stream:
        await interaction.followup.send("⚠️ 라디오 스트림을 찾을 수 없습니다.")
        return

    if "youtube.com" in stream or "youtu.be" in stream:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, stream, download=False))
        source = discord.FFmpegPCMAudio(data["url"], **FFMPEG_OPTIONS)
    else:
        source = discord.FFmpegPCMAudio(stream, **FFMPEG_OPTIONS)
    vc.play(source)
    await interaction.followup.send(f"📻 {key} 재생 시작!")

async def stop_and_disconnect(vc):
    if vc.is_playing() or vc.is_paused():
        vc.stop()
    await vc.disconnect()

# 유튜브 재생
async def start_youtube_play(interaction, url):
    await interaction.response.defer(ephemeral=True)
    member = interaction.user
    if not member.voice or not member.voice.channel:
        await interaction.followup.send("⚠️ 음성채널에 먼저 접속하세요.", ephemeral=True)
        return
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        vc = await member.voice.channel.connect()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, url, download=False))
    source = discord.FFmpegPCMAudio(data["url"], **FFMPEG_OPTIONS)
    vc.play(source)
    await interaction.followup.send("🎧 YouTube 링크 재생 시작!")

# 유튜브 검색
async def start_youtube_search(interaction, query):
    await interaction.response.defer(ephemeral=True)
    member = interaction.user
    if not member.voice or not member.voice.channel:
        await interaction.followup.send("⚠️ 음성채널에 먼저 접속하세요.", ephemeral=True)
        return
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        vc = await member.voice.channel.connect()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, f"ytsearch:{query}", download=False))
    entry = data["entries"][0]
    source = discord.FFmpegPCMAudio(entry["url"], **FFMPEG_OPTIONS)
    vc.play(source)
    await interaction.followup.send(f"🎶 '{query}' 첫 영상 재생 시작!")

# ────────────────────────────────
# on_ready - 안내문 자동고정
# ────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 로그인 완료: {bot.user}")
    await bot.wait_until_ready()

    if CHANNEL_JOIN_ID:
        ch = bot.get_channel(CHANNEL_JOIN_ID)
        join_text = "🎊✨ 삐약 서버에 오신 걸 환영합니다!\n아래 버튼으로 가입 인증 진행하세요!"
        await ensure_pinned_message(ch, join_text, JoinView())

    if CHANNEL_PROMOTE_ID:
        ch = bot.get_channel(CHANNEL_PROMOTE_ID)
        promote_text = "🪖 쟁탈원 승급 인증을 위해 아래 버튼을 눌러주세요."
        await ensure_pinned_message(ch, promote_text, PromoteView())

    if CHANNEL_RADIO_ID:
        ch = bot.get_channel(CHANNEL_RADIO_ID)
        radio_text = (
            "📡✨ 라디오봇 접속 완료!\n"
            "🎶 아래 명령어로 라디오를 재생할 수 있습니다.\n"
            "📻 /mbc표준fm, /mbcfm4u, /sbs러브fm, /sbs파워fm, /cbs음악fm\n"
            "🎧 /youtubeURL [링크], /youtube검색 [검색어]\n"
            "⛔ /정지 : 재생 중지 및 퇴장"
        )
        await ensure_pinned_message(ch, radio_text, RadioView())

# ────────────────────────────────
# 실행
# ────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("❌ 환경변수 DISCORD_TOKEN이 설정되지 않았습니다.")
    else:
        bot.run(TOKEN)
