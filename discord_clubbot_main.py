# Discord ClubBot - 통합 가입/승급/라디오 관리봇
# 파일명: discord_clubbot.py
# 사용법: 환경변수 설정 후 `python discord_clubbot.py` 실행

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
# 채널 ID들 - 환경변수로 설정하세요
CHANNEL_JOIN_ID = int(os.getenv('CHANNEL_JOIN_ID', '0'))       # 가입인증 채널
CHANNEL_PROMOTE_ID = int(os.getenv('CHANNEL_PROMOTE_ID', '0'))   # 승급인증 채널
CHANNEL_RADIO_ID = int(os.getenv('CHANNEL_RADIO_ID', '0'))       # 라디오 안내 채널

# 역할 ID들
ROLE_CLUBER_ID = int(os.getenv('ROLE_CLUBER_ID', '0'))
ROLE_FIGHTER_ID = int(os.getenv('ROLE_FIGHTER_ID', '0'))

# 정답 코드
JOIN_CODE = os.getenv('JOIN_CODE', '241120')
PROMOTE_CODE = os.getenv('PROMOTE_CODE', '021142')

# 라디오 스트림 URL (실제 작동하는 스트림 URL로 교체하세요)
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

# --- Utilities ---
async def ensure_pinned_message(channel: discord.TextChannel, content: str, view: discord.ui.View):
    # 고정된 안내문이 이미 있으면 패스
    pinned = [m async for m in channel.pins()]
    # look for message that starts with first line of content
    key = content.splitlines()[0]
    for m in pinned:
        if m.content.startswith(key) or (m.embeds and m.embeds[0].title == key):
            return m

    # 없다면 새로 보낸 뒤 고정
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
            except Exception:
                pass

# --- Modal classes ---
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
            # 부여
            role = guild.get_role(self.success_role_id)
            if role:
                try:
                    await author.add_roles(role, reason='정상 인증')
                except Exception:
                    pass
            await interaction.response.send_message(f'🎉정답입니다!! {self.success_message} 역할이 부여되었습니다!', ephemeral=False)
            # 5초 뒤 비고정 메시지 삭제
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
        except Exception as e:
            await interaction.response.send_message('⚠️ 닉네임 변경 실패: 관리자 권한 또는 봇 권한을 확인하세요.', ephemeral=True)

# --- Views / Buttons ---
class JoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='가입인증', style=discord.ButtonStyle.primary, custom_id='join_button')
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CodeModal(correct_code=JOIN_CODE, success_role_id=ROLE_CLUBER_ID, success_message='클럽원')
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='별명변경', style=discord.ButtonStyle.secondary, custom_id='nick_button')
    async def nick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NickModal()
        await interaction.response.send_modal(modal)

class PromoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='승급인증', style=discord.ButtonStyle.primary, custom_id='promote_button')
    async def promote_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CodeModal(correct_code=PROMOTE_CODE, success_role_id=ROLE_FIGHTER_ID, success_message='쟁탈원')
        await interaction.response.send_modal(modal)

# 라디오 제어 버튼 뷰
class RadioControlView(discord.ui.View):
    def __init__(self, key: str):
        super().__init__(timeout=None)
        self.key = key

    @discord.ui.button(label='재생', style=discord.ButtonStyle.success, custom_id='radio_play')
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await start_radio_playback(interaction, self.key)

    @discord.ui.button(label='일시정지', style=discord.ButtonStyle.secondary, custom_id='radio_pause')
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message('⏸ 일시정지되었습니다.', ephemeral=True)
        else:
            await interaction.response.send_message('재생 중인 것이 없습니다.', ephemeral=True)

    @discord.ui.button(label='정지', style=discord.ButtonStyle.danger, custom_id='radio_stop')
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            await stop_and_disconnect(vc)
            await interaction.response.send_message('⏹ 정지 및 음성 채널에서 퇴장했습니다.', ephemeral=True)
            # 안내문 제외 메시지 삭제
            channel = interaction.channel
            asyncio.create_task(delete_non_pinned_messages_after(channel, 1))
        else:
            await interaction.response.send_message('재생중인 음성 연결이 없습니다.', ephemeral=True)

# --- Radio playback helpers ---
FFMPEG_OPTIONS = {
    'options': '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}
YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

async def start_radio_playback(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    member = interaction.user
    voice_state = member.voice
    if not voice_state or not voice_state.channel:
        await interaction.followup.send('⚠️ 먼저 음성 채널에 접속해 주세요.', ephemeral=True)
        return

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        try:
            vc = await voice_state.channel.connect()
        except Exception as e:
            await interaction.followup.send(f'🔌 음성 채널 연결 실패: {e}', ephemeral=True)
            return

    # 정해진 라디오 스트림이 있으면 그것을 재생
    stream = RADIOS.get(key)
    if stream:
        # 만약 stream이 유튜브 링크라면 yt_dlp로 가져오기
        if 'youtube.com' in stream or 'youtu.be' in stream:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, stream, download=False))
            url = data['url']
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            vc.play(source)
            await interaction.followup.send(f'▶️ {key} 재생을 시작했습니다.', ephemeral=False)
        else:
            source = discord.FFmpegPCMAudio(stream, **FFMPEG_OPTIONS)
            vc.play(source)
            await interaction.followup.send(f'▶️ {key} 재생을 시작했습니다.', ephemeral=False)

    else:
        await interaction.followup.send('⚠️ 설정된 스트림이 없습니다. 관리자에게 문의하세요.', ephemeral=True)

async def stop_and_disconnect(vc: discord.VoiceClient):
    try:
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await vc.disconnect()
    except Exception:
        pass

# --- Slash commands for radio & stop ---
@bot.tree.command(name='정지', description='재생 중지 + 음성 채널 퇴장')
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await stop_and_disconnect(vc)
        await interaction.response.send_message('⏹ 정지 및 음성 채널에서 퇴장했습니다.')
        channel = interaction.channel
        asyncio.create_task(delete_non_pinned_messages_after(channel, 1))
    else:
        await interaction.response.send_message('재생중인 것이 없습니다.')

# -- 라디오 전용 명령 등록 (예: /mbc표준fm) --
for cmd_name in ['mbc표준fm', 'mbcfm4u', 'sbs러브fm', 'sbs파워fm', 'cbs음악fm']:
    async def make_cmd(interaction: discord.Interaction, _cmd=cmd_name):
        # 바로 재생 시도
        # 아래 함수은 interaction에서 호출
        await start_radio_playback(interaction, _cmd)

    # attach to tree
    bot.tree.command(name=cmd_name, description=f'{cmd_name} 재생')(make_cmd)

# YouTube URL 재생
@bot.tree.command(name='youtube_URL', description='YouTube 링크 재생')
@app_commands.describe(url='재생할 유튜브 링크')
async def youtube_url(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    member = interaction.user
    voice_state = member.voice
    if not voice_state or not voice_state.channel:
        await interaction.followup.send('⚠️ 먼저 음성 채널에 접속해 주세요.', ephemeral=True)
        return

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        try:
            vc = await voice_state.channel.connect()
        except Exception as e:
            await interaction.followup.send(f'🔌 음성 채널 연결 실패: {e}', ephemeral=True)
            return

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, url, download=False))
        audio_url = data['url']
        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
        vc.play(source)
        await interaction.followup.send('▶️ YouTube 링크 재생을 시작했습니다.')
    except Exception as e:
        await interaction.followup.send(f'❌ 재생 실패: {e}', ephemeral=True)

# YouTube 검색 후 첫 영상 재생 (간단한 구현: ytdl로 검색 링크 이용)
@bot.tree.command(name='youtube_검색', description='키워드로 유튜브 검색 후 첫 영상 재생')
@app_commands.describe(query='검색어')
async def youtube_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)
    search_url = f"ytsearch:{query}"
    guild = interaction.guild
    member = interaction.user
    voice_state = member.voice
    if not voice_state or not voice_state.channel:
        await interaction.followup.send('⚠️ 먼저 음성 채널에 접속해 주세요.', ephemeral=True)
        return

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        try:
            vc = await voice_state.channel.connect()
        except Exception as e:
            await interaction.followup.send(f'🔌 음성 채널 연결 실패: {e}', ephemeral=True)
            return

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, search_url, download=False))
        # ytsearch 결과는 entries 리스트를 가짐
        entry = data['entries'][0]
        audio_url = entry['url'] if 'url' in entry else entry['webpage_url']
        # 추출된 정보에서 직접 재생 URL을 얻거나 FFmpeg로 웹페이지를 넣어 재생
        source = discord.FFmpegPCMAudio(entry['url'], **FFMPEG_OPTIONS) if 'url' in entry else discord.FFmpegPCMAudio(entry['webpage_url'], **FFMPEG_OPTIONS)
        vc.play(source)
        await interaction.followup.send(f'▶️ 검색어 "{query}" 기준 첫 영상 재생을 시작했습니다.')
    except Exception as e:
        await interaction.followup.send(f'❌ 검색/재생 실패: {e}', ephemeral=True)

# --- 봇 초기화: 고정 안내문 생성 ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    await bot.wait_until_ready()

    guild = bot.get_guild(GUILD_ID) if GUILD_ID else None
    if not guild:
        print('GUILD_ID가 설정되어 있지 않거나 봇이 해당 길드에 없습니다.')

    # 가입 채널 안내문
    try:
        if CHANNEL_JOIN_ID:
            ch = bot.get_channel(CHANNEL_JOIN_ID)
            join_text = ('🎊✨삐약 디스코드 서버에 오신 것을 환영합니다!✨🎊\n'
                         '🎊✨먼저 운영진 또는 오픈톡 공지사항을 통해 디스코드 인증코드를 확인해주세요!\n\n'
                         '🪪✨ 1️⃣가입 인증 안내\n'
                         '아래 버튼을 눌러 가입 인증을 진행해주세요\n')
            await ensure_pinned_message(ch, join_text, JoinView())

        # 승급 채널 안내문
        if CHANNEL_PROMOTE_ID:
            ch2 = bot.get_channel(CHANNEL_PROMOTE_ID)
            promote_text = ('🪖 쟁탈원으로 승급하기 위해서는\n'
                            '🪖 운영진이 안내해준 승인인증 코드를 입력해주시기 바랍니다.\n'
                            '아래 버튼을 눌러 승급 인증을 진행해주세요\n')
            await ensure_pinned_message(ch2, promote_text, PromoteView())

        # 라디오 채널 안내문
        if CHANNEL_RADIO_ID:
            ch3 = bot.get_channel(CHANNEL_RADIO_ID)
            radio_text = ('📡✨ 라디오봇 접속 완료!\n'
                          '🎶 음성 채널에 들어간 후 아래 명령어 사용 가능\n\n'
                          '📻 /mbc표준fm : MBC 표준FM 재생\n'
                          '📻 /mbcfm4u : MBC FM4U 재생\n'
                          '📻 /sbs러브fm : SBS 러브FM 재생\n'
                          '📻 /sbs파워fm : SBS 파워FM 재생\n'
                          '📻 /cbs음악fm : CBS 음악FM 재생\n'
                          '🎧 /youtube_URL : URL 링크 이용 유튜브 링크 재생\n'
                          '🎧 /youtube_검색 : 키워드 검색어 이용 재생/검색 후 첫 영상을 재생함\n'
                          '⛔ /정지 : 재생 중지 + 음성채널 퇴장\n\n'
                          '📡✨ 라디오봇 Youtube Play 오류시\n'
                          '🎶 뽀삐 명령어 사용\n\n'
                          '🎧 /재생 [링크] : YouTube 링크 재생\n\n'
                          '⭐ 모든 봇 실행할 때는 명렁어상 아이콘 확인 후 실행')
            # 라디오뷰에는 각 라디오에 대한 재생 버튼을 한 번에 표시
            view = discord.ui.View(timeout=None)
            for key in RADIOS.keys():
                # custom_id로 라디오키를 전달
                async def make_cb(interaction: discord.Interaction, _key=key):
                    await start_radio_playback(interaction, _key)

                btn = discord.ui.Button(label=key, style=discord.ButtonStyle.primary)
                btn.callback = make_cb
                view.add_item(btn)

            # 추가로 정지 버튼
            stop_btn = discord.ui.Button(label='정지', style=discord.ButtonStyle.danger)
            async def stop_cb(interaction: discord.Interaction):
                vc = interaction.guild.voice_client
                if vc:
                    await stop_and_disconnect(vc)
                    await interaction.response.send_message('⏹ 정지 및 음성 채널에서 퇴장했습니다.', ephemeral=True)
                else:
                    await interaction.response.send_message('재생중인 것이 없습니다.', ephemeral=True)
            stop_btn.callback = stop_cb
            view.add_item(stop_btn)

            # 고정 안내문 생성
            await ensure_pinned_message(ch3, radio_text, view)

    except Exception as e:
        print('초기 안내문 생성 중 오류:', e)

# --- 토큰으로 실행 ---
if __name__ == '__main__':
    if not TOKEN:
        print('환경변수 DISCORD_TOKEN을 설정하세요.')
    else:
        bot.run(TOKEN)
