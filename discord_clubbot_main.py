# ───────────────────────────────────────────────────────────
# Discord ClubBot - 통합 가입/승급/라디오 관리봇 (2025 최신 수정판, cookies.txt 불필요)
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
    """역할 이름으로 역할 부여 (없으면 자동 생성)"""
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
    """고정되지 않은 메시지 정리"""
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
# ✅ on_ready
# ────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 로그인 완료: {bot.user} ({bot.user.id})")
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"🌐 {len(synced)}개의 명령어 동기화 완료 ({GUILD_ID})")
    except Exception as e:
        print(f"❌ 슬래시 명령어 동기화 실패: {e}")

# ────────────────────────────────
# ✅ 코드 입력 처리 (가입/승급)
# ────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 가입 인증 처리
    if message.channel.id == CHANNEL_JOIN_ID:
        if message.content.strip() == JOIN_CODE:
            ok = await add_role_by_name(message.guild, message.author, JOIN_ROLE_NAME)
            await message.channel.send('🎉 정답입니다! 클럽원 역할이 부여되었습니다!' if ok else '⚠️ 역할 부여 실패')
        else:
            await message.channel.send('❌ 정답이 아닙니다')
        await asyncio.sleep(30)
        await delete_non_pinned(message.channel)
        return

    # 승급 인증 처리
    if message.channel.id == CHANNEL_PROMOTE_ID:
        if message.content.strip() == PROMOTE_CODE:
            ok = await add_role_by_name(message.guild, message.author, PROMOTE_ROLE_NAME)
            await message.channel.send('🎉 정답입니다! 쟁탈원 역할이 부여되었습니다!' if ok else '⚠️ 역할 부여 실패')
        else:
            await message.channel.send('❌ 정답이 아닙니다')
        await asyncio.sleep(30)
        await delete_non_pinned(message.channel)
        return

    await bot.process_commands(message)

# ────────────────────────────────
# ✅ 라디오 / 유튜브 플레이어
# ────────────────────────────────
YTDLP_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'nocheckcertificate': True,
    'skip_download': True,
    'ignoreerrors': True,
}

class VoicePlayer:
    def __init__(self):
        self.vc: discord.VoiceClient | None = None
        self.current_msg: discord.Message | None = None
        self.source = None

    async def join_and_play(self, interaction: discord.Interaction, source_url: str, title: str = '라디오'):
        """음성채널 연결 및 재생"""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message('⚠️ 먼저 음성 채널에 입장해 주세요.', ephemeral=True)
            return
        channel = interaction.user.voice.channel
        try:
            if self.vc and self.vc.is_connected():
                await self.vc.move_to(channel)
            else:
                self.vc = await channel.connect()
        except Exception as e:
            await interaction.response.send_message(f'❌ 음성채널 연결 실패: {e}', ephemeral=True)
            return

        try:
            ff_opts = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
            self.source = discord.FFmpegPCMAudio(source_url, before_options=ff_opts, options='-vn')
            self.vc.play(self.source)
        except Exception as e:
            await interaction.response.send_message(f'❌ 재생 실패: {e}', ephemeral=True)
            return

        await interaction.response.send_message(f'▶️ 재생 중: **{title}**')

    async def stop(self):
        if self.vc:
            try:
                await self.vc.disconnect()
            except Exception:
                pass
            self.vc = None
            self.source = None

voice_player = VoicePlayer()

RADIO_URLS = {
    'mbc': 'https://minisw.imbc.com/dsfm/_definst_/sfm.stream/playlist.m3u8',
    'fm4u': 'https://minimw.imbc.com/dmfm/_definst_/mfm.stream/playlist.m3u8',
    'sbs_love': 'https://radiolive.sbs.co.kr/lovepc/lovefm.stream/playlist.m3u8',
    'sbs_power': 'https://radiolive.sbs.co.kr/powerpc/powerfm.stream/playlist.m3u8',
    'cbs': 'https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/chunklist.m3u8',
}

async def extract_audio_url(youtube_url: str):
    """cookies.txt 없이도 YouTube 오디오 추출 (예외 안전)"""
    loop = asyncio.get_event_loop()
    def run():
        try:
            with yt_dlp.YoutubeDL(YTDLP_OPTS) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                for f in info.get('formats', [info]):
                    if f.get('acodec') != 'none':
                        return f.get('url')
                return info.get('url')
        except Exception:
            return None
    return await loop.run_in_executor(None, run)

# ────────────────────────────────
# ✅ 슬래시 명령어 등록
# ────────────────────────────────
@bot.tree.command(name='mbc표준fm', description='MBC 표준FM 재생')
async def cmd_mbc(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS['mbc'], title='MBC 표준FM')

@bot.tree.command(name='mbcfm4u', description='MBC FM4U 재생')
async def cmd_fm4u(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS['fm4u'], title='MBC FM4U')

@bot.tree.command(name='sbs러브fm', description='SBS 러브FM 재생')
async def cmd_sbs_love(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS['sbs_love'], title='SBS 러브FM')

@bot.tree.command(name='sbs파워fm', description='SBS 파워FM 재생')
async def cmd_sbs_power(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS['sbs_power'], title='SBS 파워FM')

@bot.tree.command(name='cbs음악fm', description='CBS 음악FM 재생')
async def cmd_cbs(interaction: discord.Interaction):
    await voice_player.join_and_play(interaction, RADIO_URLS['cbs'], title='CBS 음악FM')

@bot.tree.command(name='youtube_url', description='유튜브 링크 재생')
@app_commands.describe(url='YouTube 영상 URL')
async def cmd_youtube_url(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    audio_url = await extract_audio_url(url)
    if not audio_url:
        await interaction.followup.send('❌ 오디오 추출 실패 (로그인 필요 영상일 수 있습니다).')
        return
    await voice_player.join_and_play(interaction, audio_url, title='YouTube')

@bot.tree.command(name='정지', description='재생 중지 및 음성채널 퇴장')
async def cmd_stop(interaction: discord.Interaction):
    await voice_player.stop()
    await interaction.response.send_message('⏹️ 재생을 중지하고 음성채널에서 퇴장했습니다.')

# ────────────────────────────────
# ✅ 실행
# ────────────────────────────────
if __name__ == '__main__':
    if not TOKEN:
        print('❌ DISCORD_TOKEN not set in .env')
        raise SystemExit(1)
    bot.run(TOKEN)
