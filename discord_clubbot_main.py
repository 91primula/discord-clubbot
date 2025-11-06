# ────────────────────────────────────────────────
# 🎛 Discord ClubBot (가입인증 + 승급 + 라디오 + 유튜브)
# 🔄 2025-11 최신 완성본 (cookies.txt + 제어버튼 + 자동등록 통합)
# ────────────────────────────────────────────────

import os
import asyncio
import discord
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
COOKIES_FILE = os.getenv("COOKIES_FILE", None)

YTDLP_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "nocheckcertificate": True,
    "skip_download": True,
    "cookiefile": COOKIES_FILE,  # 로그인 영상 지원
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ────────────────────────────────────────────────
# 🎚 Player UI + 음성 재생 클래스
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

        # 연결
        try:
            if self.vc and self.vc.is_connected():
                await self.vc.move_to(channel)
            else:
                self.vc = await channel.connect()
        except Exception as e:
            await interaction.followup.send(f"음성채널 연결 실패: {e}")
            return

        # 재생
        try:
            ff_opts = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            self.source = discord.FFmpegPCMAudio(source_url, before_options=ff_opts, options="-vn")
            self.vc.play(self.source)
            self.current_title = title
        except Exception as e:
            await interaction.followup.send(f"재생 실패: {e}")
            return

        # 제어 메시지
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
# 📻 라디오 URL 목록
# ────────────────────────────────────────────────
RADIO_URLS = {
    "play_mbc": ("📻 MBC 표준FM", "http://smbc-mbc.akamaized.net/standardfm?_fw=1"),
    "play_fm4u": ("🎶 MBC FM4U", "http://smbc-mbc.akamaized.net/fm4u?_fw=1"),
    "play_sbs_love": ("💘 SBS 러브FM", "http://sbs-live-webcast.gscdn.com/lovefm/_definst_/lovefm.stream/playlist.m3u8"),
    "play_sbs_power": ("⚡ SBS 파워FM", "http://sbs-live-webcast.gscdn.com/powerfm/_definst_/powerfm.stream/playlist.m3u8"),
    "play_cbs": ("🎵 CBS 음악FM", "http://cbs-live.gscdn.com/cbs/_definst_/cbs.stream/playlist.m3u8"),
}

# ────────────────────────────────────────────────
# 🎛 버튼 뷰
# ────────────────────────────────────────────────
class NickButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="/NICK 실행", style=ButtonStyle.primary, custom_id="nick_exec"))


# ────────────────────────────────────────────────
# 🔔 고정 안내 메시지 자동 보장
# ────────────────────────────────────────────────
async def ensure_welcome_messages(guild: discord.Guild):
    async def pin_if_not_exists(channel, text, view=None):
        try:
            pinned = [m async for m in channel.pins()]
            if not any(text.splitlines()[0] in (m.content or "") for m in pinned):
                msg = await channel.send(text, view=view)
                await msg.pin()
        except Exception:
            pass

    # 가입
    if CHANNEL_JOIN_ID:
        ch = guild.get_channel(CHANNEL_JOIN_ID)
        if ch:
            text = (
                "🎊삐약 디스코드 서버에 오신 것을 환영합니다!\n"
                "🎊✨운영진 또는 오픈톡 공지사항에 있는 디스코드 인증코드를 채팅으로 남겨주세요!\n"
                "🪪 별명 변경은 아래 버튼을 눌러 /NICK 실행!"
            )
            await pin_if_not_exists(ch, text, NickButtonView())

    # 승급
    if CHANNEL_PROMOTE_ID:
        ch = guild.get_channel(CHANNEL_PROMOTE_ID)
        if ch:
            text = "🪖 쟁탈원 승급을 위해 승인 코드를 입력하세요."
            await pin_if_not_exists(ch, text)

    # 라디오
    if CHANNEL_RADIO_ID:
        ch = guild.get_channel(CHANNEL_RADIO_ID)
        if ch:
            text = (
                "📡✨ 라디오봇 접속 완료!\n"
                "🎧 음성 채널 접속 후 아래 버튼으로 방송 선택!\n"
                "또는 /youtube_url, /youtube_검색 명령어로 유튜브 재생 가능"
            )
            view = View(timeout=None)
            for key, (label, _) in RADIO_URLS.items():
                view.add_item(Button(label=label, custom_id=key))
            await pin_if_not_exists(ch, text, view)


# ────────────────────────────────────────────────
# ⚙️ 슬래시 명령어 등록
# ────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 로그인 완료: {bot.user}")
    guild = bot.get_guild(GUILD_ID)

    # 슬래시 명령어 동기화
    try:
        synced = await bot.tree.sync(guild=guild) if guild else await bot.tree.sync()
        print(f"🌐 {len(synced)}개의 명령어 동기화 완료")
        ch = bot.get_channel(CHANNEL_RADIO_ID) or bot.get_channel(CHANNEL_JOIN_ID)
        if ch:
            await ch.send(f"✅ **명령어 {len(synced)}개 동기화 완료!**")
    except Exception as e:
        print(f"❌ 동기화 실패: {e}")

    # 고정 메시지 보장
    try:
        if guild:
            await ensure_welcome_messages(guild)
    except Exception as e:
        print(f"❌ 안내 메시지 생성 실패: {e}")


# ────────────────────────────────────────────────
# 📻 라디오 버튼 이벤트
# ────────────────────────────────────────────────
@bot.event
async def on_interaction(interaction: discord.Interaction):
    # 닉명 명령 실행 버튼
    if interaction.type == discord.InteractionType.component:
        cid = interaction.data.get("custom_id")
        if cid == "nick_exec":
            await interaction.response.send_message("/NICK 명령어를 실행하세요!", ephemeral=True)
            return

        # 라디오 버튼 처리
        if cid in RADIO_URLS:
            title, url = RADIO_URLS[cid]
            await voice_player.join_and_play(interaction, url, title)
            return

    await bot.process_application_commands(interaction)


# ────────────────────────────────────────────────
# 🎧 유튜브 명령어
# ────────────────────────────────────────────────
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


# ────────────────────────────────────────────────
# ▶️ 실행
# ────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
