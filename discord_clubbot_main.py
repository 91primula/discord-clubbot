# ───────────────────────────────────────────────────────────
# Discord ClubBot - 통합 가입/승급/라디오 관리봇 (2025 최신 수정판)
# discord_clubbot_main.py
# ───────────────────────────────────────────────────────────
import os
import asyncio
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
from discord.ui import View, Button, Modal, TextInput

# ────────────────────────────────
# ✅ 환경 변수 로드
# ────────────────────────────────
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', '0'))
CHANNEL_JOIN_ID = int(os.getenv('CHANNEL_JOIN_ID', '0'))
CHANNEL_PROMOTE_ID = int(os.getenv('CHANNEL_PROMOTE_ID', '0'))
CHANNEL_RADIO_ID = int(os.getenv('CHANNEL_RADIO_ID', '0'))

JOIN_CODE = os.getenv('JOIN_CODE', '241120')
PROMOTE_CODE = os.getenv('PROMOTE_CODE', '021142')
JOIN_ROLE_NAME = os.getenv('JOIN_ROLE_NAME', '클럽원')
PROMOTE_ROLE_NAME = os.getenv('PROMOTE_ROLE_NAME', '쟁탈원')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ────────────────────────────────
# ✅ 유틸 함수
# ────────────────────────────────
async def add_role_by_name(guild: discord.Guild, member: discord.Member, role_name: str):
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        try:
            role = await guild.create_role(name=role_name)
        except Exception:
            return False
    try:
        await member.add_roles(role, reason='인증 코드 입력')
        return True
    except Exception:
        return False


async def delete_non_pinned(channel: discord.TextChannel):
    try:
        async for m in channel.history(limit=200):
            if not m.pinned and not m.type in (discord.MessageType.pins_add,):
                try:
                    await m.delete()
                except Exception:
                    pass
    except Exception:
        pass

# ────────────────────────────────
# ✅ 별명 변경 Modal & Button
# ────────────────────────────────
class NickModal(Modal, title='별명 변경'):
    nick = TextInput(label='바꿀 별명', placeholder='원하시는 별명을 입력하세요', max_length=32)

    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.member.edit(nick=self.nick.value, reason='사용자 요청 별명 변경')
            await interaction.response.send_message(f'✅ 별명이 `{self.nick.value}`(으)로 변경되었습니다.', ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message('❌ 권한 부족: 별명을 변경할 수 없습니다.', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'오류: {e}', ephemeral=True)


class NickButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='별명 변경', style=discord.ButtonStyle.primary, custom_id='nick_btn')
    async def nick_button(self, interaction: discord.Interaction, button: Button):
        modal = NickModal(interaction.user)
        await interaction.response.send_modal(modal)

# ────────────────────────────────
# ✅ 환영/승급/라디오 고정메시지
# ────────────────────────────────
async def ensure_welcome_messages(guild: discord.Guild):
    # 가입 안내
    if CHANNEL_JOIN_ID:
        ch = guild.get_channel(CHANNEL_JOIN_ID)
        if ch:
            content = (
                '🎊삐약 디스코드 서버에 오신 것을 환영합니다!\n'
                '🎊✨운영진 또는 오픈톡 공지사항에 있는 디스코드 인증코드를 채팅으로 남겨주세요!\n'
                '🎊🎊🎊\n'
                '🪪✨ 별명 변경 안내\n'
                '버튼을 눌러 바로 /NICK 명령어를 실행하세요.\n'
                '🎊🎊🎊'
            )
            pinned = [m async for m in ch.pins()]
            if not any('삐약 디스코드 서버에 오신 것을 환영합니다' in (m.content or '') for m in pinned):
                msg = await ch.send(content, view=NickButtonView())
                try:
                    await msg.pin()
                except Exception:
                    pass

    # 승급 안내
    if CHANNEL_PROMOTE_ID:
        ch = guild.get_channel(CHANNEL_PROMOTE_ID)
        if ch:
            content = (
                '🪖 쟁탈원으로 승급하기 위해서는\n'
                '🪖 운영진이 안내해준 승인인증 코드를 입력해주시기 바랍니다.'
            )
            pinned = [m async for m in ch.pins()]
            if not any('쟁탈원으로 승급하기 위해서는' in (m.content or '') for m in pinned):
                msg = await ch.send(content)
                try:
                    await msg.pin()
                except Exception:
                    pass

    # 라디오 안내
    if CHANNEL_RADIO_ID:
        ch = guild.get_channel(CHANNEL_RADIO_ID)
        if ch:
            content = (
                '📡✨ 라디오봇 접속 완료!\n'
                '🎶 음성 채널에 들어간 후 아래 명령어 사용 가능\n\n'
                '📻 /mbc표준fm : MBC 표준FM 재생\n'
                '📻 /mbcfm4u : MBC FM4U 재생\n'
                '📻 /sbs러브fm : SBS 러브FM 재생\n'
                '📻 /sbs파워fm : SBS 파워FM 재생\n'
                '📻 /cbs음악fm : CBS 음악FM 재생\n'
                '🎧 /youtube_url : 유튜브 링크 재생\n'
                '🎧 /youtube_검색 : 키워드 검색 재생\n'
                '⛔ /정지 : 재생 중지 + 음성채널 퇴장\n\n'
                '⭐ 명령어 실행 전 봇 아이콘 확인 후 사용'
            )
            pinned = [m async for m in ch.pins()]
            if not any('📡✨ 라디오봇 접속 완료!' in (m.content or '') for m in pinned):
                view = View(timeout=None)
                view.add_item(Button(label='MBC 표준FM', custom_id='play_mbc'))
                view.add_item(Button(label='MBC FM4U', custom_id='play_fm4u'))
                view.add_item(Button(label='SBS 러브FM', custom_id='play_sbs_love'))
                view.add_item(Button(label='SBS 파워FM', custom_id='play_sbs_power'))
                view.add_item(Button(label='CBS 음악FM', custom_id='play_cbs'))
                msg = await ch.send(content, view=view)
                try:
                    await msg.pin()
                except Exception:
                    pass

# ────────────────────────────────
# ✅ on_ready
# ────────────────────────────────
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (id: {bot.user.id})')
    if GUILD_ID:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            await ensure_welcome_messages(guild)
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID) if GUILD_ID else None)
    except Exception:
        pass

# ────────────────────────────────
# ✅ 코드 입력 처리 (가입/승급)
# ────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id == CHANNEL_JOIN_ID:
        if message.content.strip() == JOIN_CODE:
            ok = await add_role_by_name(message.guild, message.author, JOIN_ROLE_NAME)
            await message.channel.send('🎉정답입니다!! 클럽원 역할이 부여되었습니다!' if ok else '⚠️ 역할 부여 실패')
        else:
            await message.channel.send('❌ 정답이 아닙니다')
        await asyncio.sleep(30)
        await delete_non_pinned(message.channel)
        return

    if message.channel.id == CHANNEL_PROMOTE_ID:
        if message.content.strip() == PROMOTE_CODE:
            ok = await add_role_by_name(message.guild, message.author, PROMOTE_ROLE_NAME)
            await message.channel.send('🎉정답입니다!! 쟁탈원 역할이 부여되었습니다!' if ok else '⚠️ 역할 부여 실패')
        else:
            await message.channel.send('❌ 정답이 아닙니다')
        await asyncio.sleep(30)
        await delete_non_pinned(message.channel)
        return

    await bot.process_commands(message)

# ────────────────────────────────
# ✅ 라디오 재생
# ────────────────────────────────
YTDLP_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'nocheckcertificate': True,
    'skip_download': True,
}

class VoicePlayer:
    def __init__(self):
        self.vc: discord.VoiceClient | None = None
        self.current_msg: discord.Message | None = None
        self.source = None

    async def join_and_play(self, interaction: discord.Interaction, source_url: str, title: str = '라디오'):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message('먼저 음성 채널에 입장해 주세요.', ephemeral=True)
            return
        channel = interaction.user.voice.channel
        try:
            if self.vc and self.vc.is_connected():
                await self.vc.move_to(channel)
            else:
                self.vc = await channel.connect()
        except Exception as e:
            await interaction.response.send_message(f'음성채널 연결 실패: {e}', ephemeral=True)
            return

        try:
            ff_opts = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
            self.source = discord.FFmpegPCMAudio(source_url, before_options=ff_opts, options='-vn')
            self.vc.play(self.source)
        except Exception as e:
            await interaction.response.send_message(f'재생 실패: {e}', ephemeral=True)
            return

        view = View(timeout=None)
        view.add_item(Button(label='일시정지', custom_id='radio_pause'))
        view.add_item(Button(label='정지', custom_id='radio_stop'))
        content = f'▶️ 현재 재생중: {title}\n(하단 버튼으로 제어 가능)'
        await interaction.response.send_message(content, view=view)
        self.current_msg = await interaction.original_response()

    async def stop(self):
        if self.vc:
            try:
                await self.vc.disconnect()
            except Exception:
                pass
            self.vc = None
            self.source = None
            if self.current_msg:
                try:
                    await self.current_msg.delete()
                except Exception:
                    pass

voice_player = VoicePlayer()

RADIO_URLS = {
    'mbc': 'http://vod.imbc.com/servlet/getAudio?type=live&ch=standard',
    'fm4u': 'http://example.com/fm4u_stream',
    'sbs_love': 'http://example.com/sbs_love',
    'sbs_power': 'http://example.com/sbs_power',
    'cbs': 'http://example.com/cbs_music',
}

async def extract_audio_url(youtube_url: str):
    loop = asyncio.get_event_loop()
    def run():
        with yt_dlp.YoutubeDL(YTDLP_OPTS) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            for f in info.get('formats', [info]):
                if f.get('acodec') != 'none':
                    return f.get('url')
            return info.get('url')
    return await loop.run_in_executor(None, run)

# ────────────────────────────────
# ✅ 슬래시 명령어 등록
# ────────────────────────────────
@bot.tree.command(name='mbc표준fm', description='MBC 표준FM 재생')
async def cmd_mbc(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS.get('mbc', ''), title='MBC 표준FM')

@bot.tree.command(name='mbcfm4u', description='MBC FM4U 재생')
async def cmd_fm4u(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS.get('fm4u', ''), title='MBC FM4U')

@bot.tree.command(name='sbs러브fm', description='SBS 러브FM 재생')
async def cmd_sbs_love(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS.get('sbs_love', ''), title='SBS 러브FM')

@bot.tree.command(name='sbs파워fm', description='SBS 파워FM 재생')
async def cmd_sbs_power(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS.get('sbs_power', ''), title='SBS 파워FM')

@bot.tree.command(name='cbs음악fm', description='CBS 음악FM 재생')
async def cmd_cbs(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS.get('cbs', ''), title='CBS 음악FM')

@bot.tree.command(name='youtube_url', description='유튜브 URL 재생')
@app_commands.describe(url='YouTube 영상 URL')
async def cmd_youtube_url(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    audio_url = await extract_audio_url(url)
    if not audio_url:
        await interaction.followup.send('오디오 추출 실패')
        return
    await voice_player.join_and_play(interaction, audio_url, title='YouTube 재생')

@bot.tree.command(name='youtube_검색', description='유튜브에서 키워드 검색 후 첫 결과 재생')
@app_commands.describe(keyword='검색 키워드')
async def cmd_youtube_search(interaction: discord.Interaction, keyword: str):
    await interaction.response.defer()
    query = f'ytsearch1:{keyword}'
    audio_url = await extract_audio_url(query)
    if not audio_url:
        await interaction.followup.send('검색 실패')
        return
    await voice_player.join_and_play(interaction, audio_url, title=f'YouTube 검색: {keyword}')

@bot.tree.command(name='정지', description='재생 중지 및 음성채널 퇴장')
async def cmd_stop(interaction: discord.Interaction):
    await voice_player.stop()
    await interaction.response.send_message('⏹️ 재생을 중지하고 음성 채널에서 나갑니다.')
    if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
        await delete_non_pinned(interaction.channel)

# ────────────────────────────────
# ✅ 버튼 이벤트 처리
# ────────────────────────────────
@bot.event
async def on_interaction(interaction: discord.Interaction):
    cid = getattr(interaction, 'data', {}).get('custom_id') if getattr(interaction, 'data', None) else None
    if not cid:
        return
    try:
        if cid == 'play_mbc': return await cmd_mbc(interaction)
        if cid == 'play_fm4u': return await cmd_fm4u(interaction)
        if cid == 'play_sbs_love': return await cmd_sbs_love(interaction)
        if cid == 'play_sbs_power': return await cmd_sbs_power(interaction)
        if cid == 'play_cbs': return await cmd_cbs(interaction)
        if cid == 'radio_pause':
            if voice_player.vc and voice_player.vc.is_playing():
                voice_player.vc.pause()
                await interaction.response.send_message('⏸️ 일시정지되었습니다.', ephemeral=True)
            elif voice_player.vc and voice_player.vc.is_paused():
                voice_player.vc.resume()
                await interaction.response.send_message('▶️ 재개되었습니다.', ephemeral=True)
            else:
                await interaction.response.send_message('재생중이 아닙니다.', ephemeral=True)
            return
        if cid == 'radio_stop':
            await voice_player.stop()
            await interaction.response.send_message('⏹️ 정지되었습니다.', ephemeral=True)
            if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
                await delete_non_pinned(interaction.channel)
            return
        if cid == 'nick_btn':
            modal = NickModal(interaction.user)
            await interaction.response.send_modal(modal)
            return
    except Exception:
        pass

# ────────────────────────────────
# ✅ 실행
# ────────────────────────────────
if __name__ == '__main__':
    if not TOKEN:
        print('❌ DISCORD_TOKEN not set in .env')
        raise SystemExit(1)
    bot.run(TOKEN)
