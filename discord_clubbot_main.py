"""
Discord ClubBot - 가입/승급/라디오 통합 봇
사용법:
1) 환경변수 설정: DISCORD_TOKEN, GUILD_ID, CHANNEL_JOIN_ID, CHANNEL_PROMOTE_ID, CHANNEL_RADIO_ID,
   ROLE_CLUB_ID, ROLE_WARRIOR_ID
2) 필요한 패키지: discord.py>=2.0, yt_dlp, PyNaCl, ffmpeg(시스템에 설치)
   pip install -U discord.py yt_dlp PyNaCl
3) 실행: python discord_clubbot.py

설명:
- 채널에 고정(고정 메시지)로 안내문을 남기고 버튼을 통해 Modal(팝업)로 입력 받습니다.
- 가입 인증 코드: 241120 -> 역할 '클럽원' 부여
- 승급 인증 코드: 021142 -> 역할 '쟁탈원' 부여
- 닉네임 변경은 /nick_modal 또는 버튼을 통해 모달로 입력 받아 멤버의 별명을 변경합니다.
- 라디오는 음성 채널 연결 후 여러 정적 라디오 명령어 및 유튜브 URL/검색 재생, 재생/일시정지/정지 버튼을 제공합니다.

주의: 실제 라디오 스트리밍은 서버 환경(FFmpeg, PyNaCl) 설정에 따라 달라질 수 있습니다.
"""

import os
import asyncio
from typing import Optional, List

import discord
from discord import app_commands
from discord.ext import commands

# yt_dlp는 라디오(YouTube) 스트리밍에 사용
import yt_dlp

# 환경변수 로드(원하면 dotenv 사용)
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)
CHANNEL_JOIN_ID = int(os.getenv("CHANNEL_JOIN_ID", "0") or 0)       # 가입인증 채널
CHANNEL_PROMOTE_ID = int(os.getenv("CHANNEL_PROMOTE_ID", "0") or 0) # 승급인증 채널
CHANNEL_RADIO_ID = int(os.getenv("CHANNEL_RADIO_ID", "0") or 0)     # 라디오 채널
ROLE_CLUB_ID = int(os.getenv("ROLE_CLUB_ID", "0") or 0)             # 클럽원 역할 ID
ROLE_WARRIOR_ID = int(os.getenv("ROLE_WARRIOR_ID", "0") or 0)       # 쟁탈원 역할 ID

# 정답 코드
JOIN_CODE = "241120"
PROMOTE_CODE = "021142"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
# 고정 메시지 ID들을 런타임에 저장
fixed_messages = {
    "join": None,
    "join_second": None,
    "promote": None,
    "radio": None,
}

# ---------------------- UI: Modals & Views ----------------------
class CodeModal(discord.ui.Modal, title="인증 코드 입력"):
    code = discord.ui.TextInput(label="인증 코드", placeholder="인증 코드를 입력하세요", max_length=32)

    def __init__(self, kind: str, author: discord.Member):
        super().__init__()
        self.kind = kind  # 'join' or 'promote'
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        entered = self.code.value.strip()
        channel = interaction.channel
        # 정답 확인
        if self.kind == 'join':
            if entered == JOIN_CODE:
                # 역할 부여
                role = interaction.guild.get_role(ROLE_CLUB_ID)
                if role:
                    try:
                        await self.author.add_roles(role, reason="가입 인증 성공")
                    except Exception:
                        pass
                await interaction.response.send_message('🎉정답입니다!! 클럽원 역할이 부여되었습니다!! 별명을 인게임 캐릭명으로 변경해주세요!', ephemeral=False)
                # 5초 후 고정 메시지를 제외하고 삭제
                await asyncio.sleep(5)
                await purge_channel_except_fixed(channel)
            else:
                await interaction.response.send_message('❌ 정답이 아닙니다', ephemeral=False)
                await asyncio.sleep(30)
                await purge_channel_except_fixed(channel)
        elif self.kind == 'promote':
            if entered == PROMOTE_CODE:
                role = interaction.guild.get_role(ROLE_WARRIOR_ID)
                if role:
                    try:
                        await self.author.add_roles(role, reason="승급 인증 성공")
                    except Exception:
                        pass
                await interaction.response.send_message('🎉정답입니다!! 쟁탈원 역할이 부여되었습니다!', ephemeral=False)
                await asyncio.sleep(5)
                await purge_channel_except_fixed(channel)
            else:
                await interaction.response.send_message('❌ 정답이 아닙니다', ephemeral=False)
                await asyncio.sleep(30)
                await purge_channel_except_fixed(channel)

class NickModal(discord.ui.Modal, title="별명 변경"):
    newnick = discord.ui.TextInput(label="새 별명", placeholder="인게임 캐릭명으로 입력하세요", max_length=32)

    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.member.edit(nick=self.newnick.value.strip(), reason="사용자 요청 별명 변경")
            await interaction.response.send_message(f'✅ 별명이 `{self.newnick.value.strip()}`(으)로 변경되었습니다.', ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message('권한이 부족하여 별명을 변경할 수 없습니다.', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'오류 발생: {e}', ephemeral=True)

# Buttons & Views
class JoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="join_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 모달 실행
        modal = CodeModal('join', interaction.user)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="별명변경", style=discord.ButtonStyle.secondary, custom_id="nick_button")
    async def nick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NickModal(interaction.user)
        await interaction.response.send_modal(modal)

class PromoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="승급인증", style=discord.ButtonStyle.primary, custom_id="promote_button")
    async def promote_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CodeModal('promote', interaction.user)
        await interaction.response.send_modal(modal)

# Radio control view (재생/일시정지/정지)
class RadioControlView(discord.ui.View):
    def __init__(self, bot, ctx_channel_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.ctx_channel_id = ctx_channel_id

    @discord.ui.button(label="재생", style=discord.ButtonStyle.success, custom_id="radio_play")
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 재생 로직: 사용자가 음성 채널에 있어야 함
        voice_state = interaction.user.voice
        if not voice_state or not voice_state.channel:
            await interaction.response.send_message('먼저 음성 채널에 들어가세요.', ephemeral=True)
            return
        await interaction.response.send_message(▶️ 재생 명령을 받았습니다. (버튼)', ephemeral=True)
        # 실제 재생은 명령어에서 처리

    @discord.ui.button(label="일시정지", style=discord.ButtonStyle.secondary, custom_id="radio_pause")
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        vc = guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message('⏸️ 일시정지 되었습니다.', ephemeral=True)
        else:
            await interaction.response.send_message('재생 중인 음성이 없습니다.', ephemeral=True)

    @discord.ui.button(label="정지", style=discord.ButtonStyle.danger, custom_id="radio_stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        vc = guild.voice_client
        if vc:
            vc.stop()
            try:
                await vc.disconnect()
            except Exception:
                pass
            await interaction.response.send_message('⛔ 재생이 중지되고 음성 연결이 해제되었습니다.', ephemeral=True)
            # 고정 메시지를 제외하고 삭제
            ch = bot.get_channel(self.ctx_channel_id)
            if ch:
                await purge_channel_except_fixed(ch)
        else:
            await interaction.response.send_message('재생 중인 음성이 없습니다.', ephemeral=True)

# ---------------------- Helper functions ----------------------
async def ensure_fixed_messages():
    """서버 시작 시 각 채널에 고정 안내 메시지를 남기고 ID 저장"""
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID) if GUILD_ID else None

    # JOIN 채널
    if CHANNEL_JOIN_ID:
        ch = bot.get_channel(CHANNEL_JOIN_ID)
        if ch:
            join_text = (
                "🎊✨삐약 디스코드 서버에 오신 것을 환영합니다!✨🎊\n"
                "🎊✨먼저 운영진 또는 오픈톡 공지사항을 통해 디스코드 인증코드를 확인해주세요!\n"
                "✨\n"
                "🪪✨ 1️⃣가입 인증 진행\n"
                "아래 버튼을 눌러 가입 인증을 진행해주세요\n"
                "(가입인증)\n"
            )
            # 안내문 고정 메시지
            msg = None
            async for m in ch.history(limit=100):
                if m.author == bot.user and '삐약 디스코드 서버에 오신 것을 환영합니다' in (m.content or ''):
                    msg = m
                    break
            if not msg:
                msg = await ch.send(join_text, view=JoinView())
                try:
                    await msg.pin()
                except Exception:
                    pass
            fixed_messages['join'] = msg.id

            # 두번째 고정 안내
            second_text = (
                "🪪✨ 2️⃣별명 변경 진행(인겜 캐릭명으로 통일)\n"
                "(별명변경)\n"
            )
            msg2 = None
            async for m in ch.history(limit=100):
                if m.author == bot.user and '별명 변경 진행' in (m.content or ''):
                    msg2 = m
                    break
            if not msg2:
                msg2 = await ch.send(second_text, view=JoinView())
                try:
                    await msg2.pin()
                except Exception:
                    pass
            fixed_messages['join_second'] = msg2.id

    # PROMOTE 채널
    if CHANNEL_PROMOTE_ID:
        ch = bot.get_channel(CHANNEL_PROMOTE_ID)
        if ch:
            promote_text = (
                "🪖 쟁탈원으로 승급하기 위해서는\n"
                "🪖 운영진이 안내해준 승인인증 코드를 입력해주시기 바랍니다. \n"
                "아래 버튼을 눌러 승급 인증을 진행해주세요\n"
                "(승급인증)\n"
            )
            msg = None
            async for m in ch.history(limit=100):
                if m.author == bot.user and '쟁탈원으로 승급하기 위해서는' in (m.content or ''):
                    msg = m
                    break
            if not msg:
                msg = await ch.send(promote_text, view=PromoteView())
                try:
                    await msg.pin()
                except Exception:
                    pass
            fixed_messages['promote'] = msg.id

    # RADIO 채널
    if CHANNEL_RADIO_ID:
        ch = bot.get_channel(CHANNEL_RADIO_ID)
        if ch:
            radio_text = (
                "📡✨ 라디오봇 접속 완료!\n"
                "🎶 음성 채널에 들어간 후 아래 명령어 사용 가능\n\n"
                "📻 /mbc표준fm   📻 /mbcfm4u   📻 /sbs러브fm   📻 /sbs파워fm   📻 /cbs음악fm\n"
                "🎧 /youtube_url   🎧 /youtube_검색\n"
                "▶️ /재생   ⏸️/일시정지   ⛔ /정지\n\n"
                "(위에 5개 / 2개 / 3개는 각각 버튼형식으로 만들어서 라디오 및 컨트롤을 제공합니다.)\n"
                "⭐ 모든 봇 실행할 때는 명령어상 아이콘 확인 후 실행\n"
            )
            msg = None
            async for m in ch.history(limit=100):
                if m.author == bot.user and '라디오봇 접속 완료' in (m.content or ''):
                    msg = m
                    break
            if not msg:
                msg = await ch.send(radio_text, view=RadioControlView(bot, CHANNEL_RADIO_ID))
                try:
                    await msg.pin()
                except Exception:
                    pass
            fixed_messages['radio'] = msg.id

async def purge_channel_except_fixed(channel: discord.TextChannel):
    """고정 메시지(fixed_messages)에 해당하지 않는 최근 메시지를 삭제합니다."""
    keep_ids = {v for v in fixed_messages.values() if v}

    def _check(m: discord.Message):
        return m.id not in keep_ids and m.author != bot.user

    try:
        # bulk purge (14일 이내 메시지만 삭제 가능)
        await channel.purge(limit=100, check=_check)
    except Exception:
        # fallback: delete individually
        async for m in channel.history(limit=200):
            if _check(m):
                try:
                    await m.delete()
                except Exception:
                    pass

# ---------------------- Slash commands (앱 커맨드) ----------------------

@bot.event
async def on_ready():
    print(f"봇 준비 완료: {bot.user} (Guild: {GUILD_ID})")
    # 고정 메시지 보장
    bot.loop.create_task(ensure_fixed_messages())

# 직접 모달 실행 가능한 커맨드
@bot.tree.command(name="가입인증", description="가입 인증 모달을 엽니다")
async def 가입인증(interaction: discord.Interaction):
    modal = CodeModal('join', interaction.user)
    await interaction.response.send_modal(modal)

@bot.tree.command(name="승급인증", description="승급 인증 모달을 엽니다")
async def 승급인증(interaction: discord.Interaction):
    modal = CodeModal('promote', interaction.user)
    await interaction.response.send_modal(modal)

@bot.tree.command(name="nick", description="별명 변경을 합니다 (인게임 이름으로)")
@app_commands.describe(newnick='변경할 별명을 입력하세요')
async def nick(interaction: discord.Interaction, newnick: str):
    try:
        await interaction.user.edit(nick=newnick)
        await interaction.response.send_message(f'✅ 별명이 `{newnick}`(으)로 변경되었습니다.', ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message('권한이 없어 별명을 변경할 수 없습니다.', ephemeral=True)

# ---------------------- 라디오: 음성 연결 및 재생 ----------------------
# 정적 라디오 스트림 URL (예시: 실제 스트림 URL로 교체 필요)
RADIO_STATIONS = {
    'mbc표준fm': 'https://example.com/mbc_standard_stream',
    'mbcfm4u': 'https://example.com/mbcfm4u_stream',
    'sbs러브fm': 'https://example.com/sbs_love_stream',
    'sbs파워fm': 'https://example.com/sbs_power_stream',
    'cbs음악fm': 'https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/chunklist.m3u8',
}

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'), data=data)

async def connect_voice_and_play(interaction: discord.Interaction, source_url: str, title: Optional[str]=None):
    voice_state = interaction.user.voice
    if not voice_state or not voice_state.channel:
        await interaction.response.send_message('먼저 음성 채널에 입장해 주세요.', ephemeral=True)
        return
    channel = voice_state.channel
    guild = interaction.guild
    vc = guild.voice_client
    try:
        if not vc or not vc.is_connected():
            vc = await channel.connect()
    except Exception:
        # 이미 연결되어있을 수 있음. 시도 계속
        vc = guild.voice_client
    if not vc:
        await interaction.response.send_message('음성 연결에 실패했습니다.', ephemeral=True)
        return

    # 재생 준비
    try:
        source = await YTDLSource.from_url(source_url, loop=bot.loop, stream=True)
        vc.play(source)
        display = f'▶️ `{title or source.title or "재생중"}` 재생중...'
        await interaction.response.send_message(display, view=RadioControlView(bot, CHANNEL_RADIO_ID), ephemeral=False)
    except Exception as e:
        await interaction.response.send_message(f'오류로 인해 재생할 수 없습니다: {e}', ephemeral=True)

# 라디오 명령어들
@bot.tree.command(name='mbc표준fm', description='MBC 표준FM 재생')
async def mbc표준fm(interaction: discord.Interaction):
    url = RADIO_STATIONS.get('mbc표준fm')
    await connect_voice_and_play(interaction, url, 'MBC 표준FM')

@bot.tree.command(name='mbcfm4u', description='MBC FM4U 재생')
async def mbcfm4u(interaction: discord.Interaction):
    url = RADIO_STATIONS.get('mbcfm4u')
    await connect_voice_and_play(interaction, url, 'MBC FM4U')

@bot.tree.command(name='sbs러브fm', description='SBS 러브FM 재생')
async def sbs러브fm(interaction: discord.Interaction):
    url = RADIO_STATIONS.get('sbs러브fm')
    await connect_voice_and_play(interaction, url, 'SBS 러브FM')

@bot.tree.command(name='sbs파워fm', description='SBS 파워FM 재생')
async def sbs파워fm(interaction: discord.Interaction):
    url = RADIO_STATIONS.get('sbs파워fm')
    await connect_voice_and_play(interaction, url, 'SBS 파워FM')

@bot.tree.command(name='cbs음악fm', description='CBS 음악FM 재생')
async def cbs음악fm(interaction: discord.Interaction):
    url = RADIO_STATIONS.get('cbs음악fm')
    await connect_voice_and_play(interaction, url, 'CBS 음악FM')

@bot.tree.command(name='youtube_url', description='유튜브 URL로 재생')
@app_commands.describe(url='재생할 유튜브 URL')
async def youtube_url(interaction: discord.Interaction, url: str):
    await connect_voice_and_play(interaction, url, 'YouTube URL 재생')

@bot.tree.command(name='youtube_검색', description='유튜브에서 검색하여 첫번째 영상 재생')
@app_commands.describe(query='검색어')
async def youtube_검색(interaction: discord.Interaction, query: str):
    # yt_dlp를 이용한 검색: youtube 검색 URL로 변환
    search_url = f"ytsearch1:{query}"
    await connect_voice_and_play(interaction, search_url, f'YouTube 검색: {query}')

@bot.tree.command(name='정지', description='라디오/유튜브 재생 중지')
async def 정지(interaction: discord.Interaction):
    guild = interaction.guild
    vc = guild.voice_client
    ch = bot.get_channel(CHANNEL_RADIO_ID) if CHANNEL_RADIO_ID else interaction.channel
    if vc:
        vc.stop()
        try:
            await vc.disconnect()
        except Exception:
            pass
        await interaction.response.send_message('⛔ 재생이 중지되고 음성 연결이 해제되었습니다.', ephemeral=False)
        if ch:
            await purge_channel_except_fixed(ch)
    else:
        await interaction.response.send_message('재생 중인 음성이 없습니다.', ephemeral=True)

# ---------------------- 버튼으로도 라디오 실행 (채널 고정 메시지에 표시되는 뷰에서 작동)
# 라디오 채널 내 버튼으로 특정 방송을 재생시키려면 커스텀 ID를 보고 처리할 수 있습니다.

@bot.event
async def on_interaction(interaction: discord.Interaction):
    # interaction.type 기본은 application_command 또는 component
    if interaction.type != discord.InteractionType.component:
        return
    custom_id = interaction.data.get('custom_id')
    if not custom_id:
        return
    # 가입/승급/닉 버튼은 View에서 이미 처리되므로 라디오 전용 커스텀만 처리
    if custom_id.startswith('radio_station_'):
        station_key = custom_id.replace('radio_station_', '')
        url = RADIO_STATIONS.get(station_key)
        if url:
            await connect_voice_and_play(interaction, url, station_key)

# ---------------------- 봇 실행 처리 ----------------------

# 앱 명령어 동기화 유틸리티
async def sync_commands():
    await bot.wait_until_ready()
    try:
        guild = discord.Object(id=GUILD_ID) if GUILD_ID else None
        if guild:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print('길드 명령어 동기화 완료')
        else:
            await bot.tree.sync()
            print('글로벌 명령어 동기화 완료')
    except Exception as e:
        print('명령어 동기화 오류:', e)

bot.loop.create_task(sync_commands())

if __name__ == '__main__':
    if not TOKEN:
        print('환경변수 DISCORD_TOKEN을 설정하세요.')
    else:
        bot.run(TOKEN)
