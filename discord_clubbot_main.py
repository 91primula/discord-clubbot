# ────────────────────────────────────────────────
# 🎛 Discord ClubBot - 완전 통합판
# ✅ 가입인증 + 승급 + 라디오 + 유튜브 + cookies.txt
# 🔄 2025-11 최신 안정버전
# ────────────────────────────────────────────────

import os
import discord
import asyncio
from discord.ext import commands
from discord import app_commands, ButtonStyle
from discord.ui import View, Button
from dotenv import load_dotenv
import yt_dlp

# ────────────────────────────────────────────────
# ✅ 환경 변수
# ────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
CHANNEL_JOIN_ID = int(os.getenv("CHANNEL_JOIN_ID", 0))
CHANNEL_PROMOTE_ID = int(os.getenv("CHANNEL_PROMOTE_ID", 0))
CHANNEL_RADIO_ID = int(os.getenv("CHANNEL_RADIO_ID", 0))
ROLE_JOIN_ID = int(os.getenv("ROLE_JOIN_ID", 0))       # 인증 완료 역할
ROLE_PROMOTE_ID = int(os.getenv("ROLE_PROMOTE_ID", 0)) # 승급 역할
JOIN_CODE = os.getenv("JOIN_CODE", "JOIN1234")         # 인증 코드
PROMOTE_CODE = os.getenv("PROMOTE_CODE", "PROMOTE1234")# 승급 코드
COOKIES_FILE = os.getenv("COOKIES_FILE", None)

YTDLP_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "nocheckcertificate": True,
    "skip_download": True,
    "cookiefile": COOKIES_FILE,
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ────────────────────────────────────────────────
# 🎚 Player + 제어 버튼
# ────────────────────────────────────────────────
class PlayerControllerView(View):
    def __init__(self, player: "VoicePlayer"):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="⏸ / ▶ 재생제어", style=ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, button: Button):
        if not self.player.vc:
            await interaction.response.send_message("🎧 재생 중이 아닙니다.", ephemeral=True)
            return
        if self.player.vc.is_playing():
            self.player.vc.pause()
            await interaction.response.send_message("⏸ 일시정지되었습니다.", ephemeral=True)
        elif self.player.vc.is_paused():
            self.player.vc.resume()
            await interaction.response.send_message("▶ 재개되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("상태를 확인할 수 없습니다.", ephemeral=True)

    @discord.ui.button(label="⏹ 정지", style=ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: Button):
        await self.player.stop()
        await interaction.response.send_message("⏹ 정지 완료", ephemeral=True)


class VoicePlayer:
    def __init__(self):
        self.vc: discord.VoiceClient | None = None
        self.source = None
        self.current_title = None
        self.current_msg = None

    async def join_and_play(self, interaction: discord.Interaction, source_url: str, title: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("먼저 음성채널에 들어가 주세요.", ephemeral=True)
            return

        await interaction.response.defer()
        channel = interaction.user.voice.channel

        try:
            if self.vc and self.vc.is_connected():
                await self.vc.move_to(channel)
            else:
                self.vc = await channel.connect()
        except Exception as e:
            await interaction.followup.send(f"음성채널 연결 실패: {e}")
            return

        try:
            ff_opts = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            self.source = discord.FFmpegPCMAudio(source_url, before_options=ff_opts, options="-vn")
            self.vc.play(self.source)
            self.current_title = title
        except Exception as e:
            await interaction.followup.send(f"재생 실패: {e}")
            return

        view = PlayerControllerView(self)
        msg = await interaction.followup.send(f"▶️ **현재 재생중:** {title}", view=view)
        self.current_msg = msg

    async def stop(self):
        if self.vc:
            try:
                if self.vc.is_playing() or self.vc.is_paused():
                    self.vc.stop()
                await self.vc.disconnect()
            except Exception:
                pass
            self.vc = None
        if self.current_msg:
            try:
                await self.current_msg.delete()
            except Exception:
                pass


voice_player = VoicePlayer()

# ────────────────────────────────────────────────
# 📻 라디오 URL
# ────────────────────────────────────────────────
RADIO_URLS = {
    "play_mbc": ("📻 MBC 표준FM", "https://minisw.imbc.com/dsfm/_definst_/sfm.stream/playlist.m3u8?_lsu_sa_=67A1D91483F53A74F44145103B61D041F5783835A00C326E3B7059a0768B39E69AaB435137E2F64A009534D1FAb4C16EABD96878E7BC0619921152E8E7EBFA931B98327E0489D778A4F3C574C9FEC7FB758F680E766F6EF2502994C223A3FD615A1C1E1FDE8F18BBC61C0DCA3ECFAD04"),
    "play_fm4u": ("🎶 MBC FM4U", "https://minimw.imbc.com/dmfm/_definst_/mfm.stream/playlist.m3u8?_lsu_sa_=6A11AB1DB3A739D4DA4B55B13B712A47350D3C95500FB2123270F4a9D64E322699a9A3273D325249E0CC39E12FbCA1C7864BAF1C2B179F0ACD0C01522928E2C8F565B89E342A5EACC78FE208B80AE1FE6C864F4B28E1D0E70172AC45367E4814BF8F4A2D445F6B7ACED29B6CFEE6E70E"),
    "play_sbs_love": ("💘 SBS 러브FM", "https://radiolive.sbs.co.kr/lovepc/lovefm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjIwMzcxNzMsInBhdGgiOiIvbG92ZWZtLnN0cmVhbSIsImR1cmF0aW9uIjotMSwidW5vIjoiYWIyMTlhZmMtMWIxNC00ODczLWI1MDktOTNmYjNjZTljYjgwIiwiaWF0IjoxNzYxOTkzOTczfQ.ebt9XpFVApTFX_T_fTCqNZvgv24XxwFlCso27Gm522I"),
    "play_sbs_power": ("⚡ SBS 파워FM", "https://radiolive.sbs.co.kr/powerpc/powerfm.stream/playlist.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NjIwMzcxODUsInBhdGgiOiIvcG93ZXJmbS5zdHJlYW0iLCJkdXJhdGlvbiI6LTEsInVubyI6IjhlMDMwOWYzLTE0NmItNDg5MC05ZDRlLTU3YzU4NDJkZWQ4YyIsImlhdCI6MTc2MTk5Mzk4NX0.YhsR4d864lBc9DajabAbHHu4WewCBxpOgK_quJxcUIM"),
    "play_cbs": ("🎵 CBS 음악FM", "https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/chunklist.m3u8"),
}

# ────────────────────────────────────────────────
# 📜 안내 고정 메시지
# ────────────────────────────────────────────────
class NickButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="/NICK 실행", style=ButtonStyle.primary, custom_id="nick_exec"))


async def ensure_welcome_messages(guild: discord.Guild):
    async def pin_if_not_exists(channel, text, view=None):
        try:
            pinned = [m async for m in channel.pins()]
            if not any(text.splitlines()[0] in (m.content or "") for m in pinned):
                msg = await channel.send(text, view=view)
                await msg.pin()
        except Exception:
            pass

    if CHANNEL_JOIN_ID:
        ch = guild.get_channel(CHANNEL_JOIN_ID)
        if ch:
            txt = (
                "🎊 삐약 서버에 오신 것을 환영합니다!\n"
                "운영진 또는 공지의 인증코드를 입력하면 자동 인증됩니다!\n"
                "예시: `/인증 1234`\n\n"
                "닉네임은 아래 버튼을 눌러 변경 가능!"
            )
            await pin_if_not_exists(ch, txt, NickButtonView())

    if CHANNEL_PROMOTE_ID:
        ch = guild.get_channel(CHANNEL_PROMOTE_ID)
        if ch:
            txt = "🪖 쟁탈 승급 코드 입력 시 자동 승급됩니다. 예시: `/승급 CODE`"
            await pin_if_not_exists(ch, txt)

    if CHANNEL_RADIO_ID:
        ch = guild.get_channel(CHANNEL_RADIO_ID)
        if ch:
            txt = (
                "📡 라디오봇 접속 완료!\n"
                "음성채널 입장 후 아래 방송 중 선택 가능.\n"
                "또는 /youtube_url, /youtube_검색 명령어 사용 가능."
            )
            view = View(timeout=None)
            for key, (label, _) in RADIO_URLS.items():
                view.add_item(Button(label=label, custom_id=key))
            await pin_if_not_exists(ch, txt, view)

# ────────────────────────────────────────────────
# ⚙️ 슬래시 명령어
# ────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 로그인 완료: {bot.user}")
    guild = bot.get_guild(GUILD_ID)
    try:
        synced = await bot.tree.sync(guild=guild) if guild else await bot.tree.sync()
        print(f"🌐 {len(synced)}개의 명령어 동기화 완료")
    except Exception as e:
        print(f"❌ 동기화 실패: {e}")
    if guild:
        await ensure_welcome_messages(guild)

# 가입 인증
@bot.tree.command(name="인증", description="가입 인증 코드 입력")
async def 인증(interaction: discord.Interaction, 코드: str):
    if 코드.strip() == JOIN_CODE:
        role = interaction.guild.get_role(ROLE_JOIN_ID)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ 인증 성공! 역할 `{role.name}` 부여 완료.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 인증 역할이 설정되지 않았습니다.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ 인증 코드가 올바르지 않습니다.", ephemeral=True)

# 승급
@bot.tree.command(name="승급", description="승급 코드 입력")
async def 승급(interaction: discord.Interaction, 코드: str):
    if 코드.strip() == PROMOTE_CODE:
        role = interaction.guild.get_role(ROLE_PROMOTE_ID)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"🪖 승급 완료! `{role.name}` 역할이 부여되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 승급 역할이 설정되지 않았습니다.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ 승급 코드가 올바르지 않습니다.", ephemeral=True)

# 유튜브
@bot.tree.command(name="youtube_url", description="유튜브 URL 재생")
async def youtube_url(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    try:
        with yt_dlp.YoutubeDL(YTDLP_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            stream = info["url"]
            title = info.get("title", "유튜브 오디오")
        await voice_player.join_and_play(interaction, stream, f"🎵 {title}")
    except Exception as e:
        await interaction.followup.send(f"유튜브 재생 실패: {e}")

@bot.tree.command(name="youtube_검색", description="유튜브 검색 후 첫 영상 재생")
async def youtube_검색(interaction: discord.Interaction, 키워드: str):
    await interaction.response.defer()
    try:
        query = f"ytsearch1:{키워드}"
        with yt_dlp.YoutubeDL(YTDLP_OPTS) as ydl:
            info = ydl.extract_info(query, download=False)["entries"][0]
            stream = info["url"]
            title = info["title"]
        await voice_player.join_and_play(interaction, stream, f"🔍 {title}")
    except Exception as e:
        await interaction.followup.send(f"검색 실패: {e}")

@bot.tree.command(name="정지", description="현재 재생 중지 및 음성 퇴장")
async def stop(interaction: discord.Interaction):
    await voice_player.stop()
    await interaction.response.send_message("⛔ 정지 및 퇴장 완료", ephemeral=True)

# 버튼 이벤트
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        cid = interaction.data.get("custom_id")
        if cid == "nick_exec":
            await interaction.response.send_message("/NICK 명령어를 직접 실행해주세요!", ephemeral=True)
            return
        if cid in RADIO_URLS:
            title, url = RADIO_URLS[cid]
            await voice_player.join_and_play(interaction, url, title)
            return
    await bot.process_application_commands(interaction)

# ────────────────────────────────────────────────
# ▶️ 실행
# ────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
