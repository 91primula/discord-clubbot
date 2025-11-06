# ───────────────────────────────────────────────────────────
# Discord ClubBot - 통합 가입/승급/라디오 관리봇 (수정완성판)
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

# ───────────────────────────────
# ✅ 환경변수 로드
# ───────────────────────────────
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
    'cbs음악fm': os.getenv('STREAM_CBS', 'https://example.com/cbs_music_stream.mp3')
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ───────────────────────────────
# 🔧 유틸리티
# ───────────────────────────────
async def ensure_pinned_message(channel: discord.TextChannel, content: str, view: discord.ui.View):
    pinned = [m async for m in channel.pins()]
    key = content.splitlines()[0]
    for m in pinned:
        if m.content.startswith(key) or (m.embeds and m.embeds[0].title == key):
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

# ───────────────────────────────
# 🪪 Modal 클래스
# ───────────────────────────────
class CodeModal(discord.ui.Modal, title='인증 코드 입력'):
    code = discord.ui.TextInput(label='인증 코드', placeholder='코드를 입력하세요')

    def __init__(self, *, correct_code: str, success_role_id: int, success_message: str, wrong_cleanup_delay=30, correct_cleanup_delay=5):
        super().__init__()
        self.correct_code = correct_code
        self.success_role_id = success_role_id
        self.success_message = success_message
        self.wrong_cleanup_delay = wrong_cleanup_delay
        self.correct_cleanup_delay = correct_cleanup_delay

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        channel = interaction.channel
        author = interaction.user
        if self.code.value.strip() == self.correct_code:
            role = guild.get_role(self.success_role_id)
            if role:
                try:
                    await author.add_roles(role, reason='정상 인증')
                except:
                    pass
            await interaction.response.send_message(f'🎉정답입니다!! {self.success_message} 역할이 부여되었습니다!', ephemeral=False)
            asyncio.create_task(delete_non_pinned_messages_after(channel, self.correct_cleanup_delay))
        else:
            await interaction.response.send_message('❌ 정답이 아닙니다', ephemeral=False)
            asyncio.create_task(delete_non_pinned_messages_after(channel, self.wrong_cleanup_delay))

class NickModal(discord.ui.Modal, title='별명 변경'):
    nick = discord.ui.TextInput(label='변경하실 별명', placeholder='원하시는 닉네임을 입력하세요', max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.user.edit(nick=self.nick.value)
            await interaction.response.send_message('✅ 닉네임이 변경되었습니다.', ephemeral=True)
        except:
            await interaction.response.send_message('⚠️ 닉네임 변경 실패: 관리자 권한 또는 봇 권한을 확인하세요.', ephemeral=True)

# ───────────────────────────────
# 💬 버튼 뷰
# ───────────────────────────────
class JoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='가입인증', style=discord.ButtonStyle.primary)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CodeModal(correct_code=JOIN_CODE, success_role_id=ROLE_CLUBER_ID, success_message='클럽원')
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='별명변경', style=discord.ButtonStyle.secondary)
    async def nick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NickModal()
        await interaction.response.send_modal(modal)

class PromoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='승급인증', style=discord.ButtonStyle.primary)
    async def promote_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CodeModal(correct_code=PROMOTE_CODE, success_role_id=ROLE_FIGHTER_ID, success_message='쟁탈원')
        await interaction.response.send_modal(modal)

# ───────────────────────────────
# 📻 라디오 재생 보조함수
# ───────────────────────────────
FFMPEG_OPTIONS = {'options': '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
YTDL_OPTS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

async def stop_and_disconnect(vc: discord.VoiceClient):
    try:
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await vc.disconnect()
    except:
        pass

async def start_radio_playback(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    member = interaction.user
    if not member.voice or not member.voice.channel:
        await interaction.followup.send('⚠️ 먼저 음성 채널에 접속해 주세요.', ephemeral=True)
        return

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        try:
            vc = await member.voice.channel.connect()
        except Exception as e:
            await interaction.followup.send(f'🔌 음성 채널 연결 실패: {e}', ephemeral=True)
            return

    stream = RADIOS.get(key)
    if not stream:
        await interaction.followup.send('⚠️ 설정된 스트림이 없습니다.', ephemeral=True)
        return

    try:
        if 'youtube.com' in stream or 'youtu.be' in stream:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, stream, download=False))
            url = data['url']
        else:
            url = stream
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        vc.play(source)
        await interaction.followup.send(f'▶️ {key} 재생을 시작했습니다.', ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f'❌ 재생 실패: {e}', ephemeral=True)

# ───────────────────────────────
# 🔊 슬래시 명령어 등록
# ───────────────────────────────
@bot.tree.command(name='정지', description='재생 중지 + 음성 채널 퇴장')
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await stop_and_disconnect(vc)
        await interaction.response.send_message('⏹ 정지 및 음성 채널에서 퇴장했습니다.')
    else:
        await interaction.response.send_message('재생중인 것이 없습니다.')

# ✅ 오류 수정된 부분 — 명령 자동 등록 함수
def register_radio_command(cmd_name: str):
    @bot.tree.command(name=cmd_name, description=f'{cmd_name} 재생')
    async def radio_command(interaction: discord.Interaction):
        await start_radio_playback(interaction, cmd_name)

for cmd_name in RADIOS.keys():
    register_radio_command(cmd_name)

# ───────────────────────────────
# 🎧 YouTube 재생 / 검색
# ───────────────────────────────
@bot.tree.command(name='youtube_URL', description='YouTube 링크 재생')
@app_commands.describe(url='재생할 유튜브 링크')
async def youtube_url(interaction: discord.Interaction, url: str):
    await start_radio_playback(interaction, url)

@bot.tree.command(name='youtube_검색', description='키워드로 유튜브 검색 후 첫 영상 재생')
@app_commands.describe(query='검색어')
async def youtube_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)
    search_url = f"ytsearch:{query}"
    member = interaction.user
    guild = interaction.guild
    if not member.voice or not member.voice.channel:
        await interaction.followup.send('⚠️ 먼저 음성 채널에 접속해 주세요.', ephemeral=True)
        return
    vc = guild.voice_client
    if not vc:
        vc = await member.voice.channel.connect()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, search_url, download=False))
    entry = data['entries'][0]
    url = entry['url']
    source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
    vc.play(source)
    await interaction.followup.send(f'▶️ "{query}" 첫 번째 영상 재생을 시작했습니다.')

# ───────────────────────────────
# 🚀 on_ready 시 안내문 자동 고정
# ───────────────────────────────
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} ({bot.user.id})')
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print('⚠️ GUILD_ID 설정 확인 필요')
        return

    try:
        if CHANNEL_JOIN_ID:
            ch = bot.get_channel(CHANNEL_JOIN_ID)
            join_text = (
                '🎊✨삐약 디스코드 서버에 오신 것을 환영합니다!✨🎊\n'
                '🪪 1️⃣가입 인증 안내\n아래 버튼을 눌러 가입 인증을 진행해주세요\n'
            )
            await ensure_pinned_message(ch, join_text, JoinView())

        if CHANNEL_PROMOTE_ID:
            ch2 = bot.get_channel(CHANNEL_PROMOTE_ID)
            promote_text = (
                '🪖 쟁탈원 승급 안내\n'
                '운영진이 안내한 승인코드를 입력해주세요.\n'
            )
            await ensure_pinned_message(ch2, promote_text, PromoteView())

        if CHANNEL_RADIO_ID:
            ch3 = bot.get_channel(CHANNEL_RADIO_ID)
            radio_text = (
                '📡✨ 라디오봇 접속 완료!\n'
                '🎶 아래 명령어로 라디오를 재생할 수 있습니다.\n'
                '📻 /mbc표준fm, /mbcfm4u, /sbs러브fm, /sbs파워fm, /cbs음악fm\n'
                '🎧 /youtube_URL [링크], /youtube_검색 [검색어]\n'
                '⛔ /정지 : 재생 중지 및 퇴장'
            )
            view = discord.ui.View(timeout=None)
            for key in RADIOS.keys():
                async def make_cb(interaction: discord.Interaction, _key=key):
                    await start_radio_playback(interaction, _key)
                btn = discord.ui.Button(label=key, style=discord.ButtonStyle.primary)
                btn.callback = make_cb
                view.add_item(btn)
            await ensure_pinned_message(ch3, radio_text, view)
    except Exception as e:
        print('⚠️ 초기 안내문 생성 오류:', e)

# ───────────────────────────────
# 🧩 실행
# ───────────────────────────────
if __name__ == '__main__':
    if not TOKEN:
        print('❌ 환경변수 DISCORD_TOKEN이 누락되었습니다.')
    else:
        bot.run(TOKEN)
