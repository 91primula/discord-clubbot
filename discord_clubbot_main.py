# ────────────────────────────────────────────────
# 🎛 Discord ClubBot 통합판 (가입인증 + 승급 + 라디오 + 유튜브)
# ────────────────────────────────────────────────
import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp

# ────────────────────────────────────────────────
# ✅ 환경 변수 로드
# ────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
VERIFY_CHANNEL_ID = int(os.getenv("VERIFY_CHANNEL_ID", 0))
ROLE_JOIN = int(os.getenv("ROLE_JOIN", 0))
ROLE_MEMBER = int(os.getenv("ROLE_MEMBER", 0))
ROLE_UPGRADE = int(os.getenv("ROLE_UPGRADE", 0))
COOKIES_FILE = os.getenv("COOKIES_FILE", "/app/cookies.txt")

# ────────────────────────────────────────────────
# 🎵 yt_dlp 설정 (cookies.txt 없어도 안전하게)
# ────────────────────────────────────────────────
YTDLP_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "nocheckcertificate": True,
    "skip_download": True,
}

if os.path.exists(COOKIES_FILE):
    YTDLP_OPTS["cookiefile"] = COOKIES_FILE
else:
    print(f"[INFO] cookies.txt 없음 → 비로그인 상태로 유튜브 재생 진행")

# ────────────────────────────────────────────────
# ⚙️ 봇 기본 설정
# ────────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ────────────────────────────────────────────────
# 🚀 on_ready 이벤트
# ────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ 로그인 성공: {bot.user}")
    print(f"✅ Slash 명령어 동기화 완료 (서버 ID: {GUILD_ID})")

    # 인증 안내 메시지 자동 고정
    channel = bot.get_channel(VERIFY_CHANNEL_ID)
    if channel:
        await channel.send(
            "📢 **신규 회원님 반갑습니다!**\n\n"
            "아래 버튼을 눌러 **가입 인증**을 진행해주세요 👇"
        )
    else:
        print("⚠️ VERIFY_CHANNEL_ID 채널을 찾을 수 없습니다.")

# ────────────────────────────────────────────────
# 🎫 가입 인증 버튼
# ────────────────────────────────────────────────
class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="✅ 가입 인증하기", style=discord.ButtonStyle.success, custom_id="verify"
            )
        )

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data.get("custom_id") == "verify":
        role = interaction.guild.get_role(ROLE_MEMBER)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "✅ 인증 완료! 회원 역할이 부여되었습니다.", ephemeral=True
            )
        else:
            await interaction.response.send_message("⚠️ ROLE_MEMBER 설정이 잘못되었습니다.", ephemeral=True)

# ────────────────────────────────────────────────
# 🧩 슬래시 명령어
# ────────────────────────────────────────────────

# 가입 인증 명령어
@tree.command(name="가입인증", description="가입 인증 버튼을 표시합니다.", guild=discord.Object(id=GUILD_ID))
async def verify_command(interaction: discord.Interaction):
    await interaction.response.send_message("아래 버튼을 눌러 인증하세요 👇", view=VerifyButton())

# 쟁탈/승급 명령어
@tree.command(name="승급", description="멤버에서 쟁탈 멤버로 승급합니다.", guild=discord.Object(id=GUILD_ID))
async def levelup_command(interaction: discord.Interaction):
    member = interaction.user
    role_join = interaction.guild.get_role(ROLE_MEMBER)
    role_upgrade = interaction.guild.get_role(ROLE_UPGRADE)

    if not role_join or not role_upgrade:
        await interaction.response.send_message("⚠️ ROLE 설정이 잘못되었습니다.", ephemeral=True)
        return

    if role_join in member.roles:
        await member.remove_roles(role_join)
    await member.add_roles(role_upgrade)
    await interaction.response.send_message("🎉 쟁탈 멤버로 승급되었습니다!", ephemeral=True)

# 유튜브 재생 명령어
@tree.command(name="유튜브", description="유튜브 오디오를 재생합니다.", guild=discord.Object(id=GUILD_ID))
async def youtube_command(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not voice_channel:
        await interaction.followup.send("⚠️ 먼저 음성 채널에 들어가 주세요.")
        return

    vc = await voice_channel.connect()
    try:
        with yt_dlp.YoutubeDL(YTDLP_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info["url"]
            title = info.get("title", "제목 없음")

        vc.play(discord.FFmpegPCMAudio(audio_url))
        await interaction.followup.send(f"🎶 재생 중: **{title}**")
    except Exception as e:
        await interaction.followup.send(f"❌ 재생 실패: {str(e)}")
        if vc.is_connected():
            await vc.disconnect()

# 라디오 명령어
@tree.command(name="라디오", description="라디오 방송을 재생합니다.", guild=discord.Object(id=GUILD_ID))
async def radio_command(interaction: discord.Interaction, station: str):
    radio_urls = {
        "MBC": "http://mini.imbc.com/webplayer/inc/miniPlayer.aspx?channel=sfm",
        "KBS": "http://kbs.gscdn.com/kbsaudio/kbs1fm.pls",
        "SBS": "http://streaming.sbs.co.kr/SBSFM",
    }
    url = radio_urls.get(station.upper())
    if not url:
        await interaction.response.send_message("⚠️ 지원하지 않는 방송국입니다 (MBC, KBS, SBS 중 선택).")
        return

    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not voice_channel:
        await interaction.response.send_message("⚠️ 음성 채널에 먼저 들어가 주세요.")
        return

    vc = await voice_channel.connect()
    vc.play(discord.FFmpegPCMAudio(url))
    await interaction.response.send_message(f"📻 **{station} 라디오** 재생을 시작합니다.")

# ────────────────────────────────────────────────
# ▶️ 봇 실행
# ────────────────────────────────────────────────
bot.run(TOKEN)
