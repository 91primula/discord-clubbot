# ────────────────────────────────────────────────
# 🎛 Discord ClubBot - 가입 + 별명 + 라디오 + 유튜브 통합봇
# ────────────────────────────────────────────────
import os
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ────────────────────────────────────────────────
# ✅ 뷰 (가입/별명 변경)
# ────────────────────────────────────────────────
class JoinVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="가입 인증", style=discord.ButtonStyle.green)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ 가입 인증 완료되었습니다!", ephemeral=True)


class NicknameChangeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="별명 변경", style=discord.ButtonStyle.blurple)
    async def nickname_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✏️ 별명 변경 창이 열렸습니다!", ephemeral=True)

# ────────────────────────────────────────────────
# 🎧 라디오 + 유튜브 버튼
# ────────────────────────────────────────────────
class RadioButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📻 MBC 표준FM", style=discord.ButtonStyle.primary)
    async def mbc_standard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎶 MBC 표준FM 재생 시작!", ephemeral=True)

    @discord.ui.button(label="🎵 MBC FM4U", style=discord.ButtonStyle.primary)
    async def mbc_fm4u(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎶 MBC FM4U 재생 시작!", ephemeral=True)

    @discord.ui.button(label="📡 SBS 러브FM", style=discord.ButtonStyle.primary)
    async def sbs_love(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎶 SBS 러브FM 재생 시작!", ephemeral=True)

    @discord.ui.button(label="⚡ SBS 파워FM", style=discord.ButtonStyle.primary)
    async def sbs_power(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎶 SBS 파워FM 재생 시작!", ephemeral=True)

    @discord.ui.button(label="🎼 CBS 음악FM", style=discord.ButtonStyle.primary)
    async def cbs_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎶 CBS 음악FM 재생 시작!", ephemeral=True)

    @discord.ui.button(label="🎧 유튜브 검색", style=discord.ButtonStyle.secondary)
    async def youtube_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔍 유튜브 검색어를 입력해주세요!", ephemeral=True)

    @discord.ui.button(label="🔗 유튜브 URL 재생", style=discord.ButtonStyle.secondary)
    async def youtube_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎥 유튜브 URL을 입력해주세요!", ephemeral=True)

# ────────────────────────────────────────────────
# ▶️ 재생 컨트롤 버튼
# ────────────────────────────────────────────────
class ControlButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⏯ 재생", style=discord.ButtonStyle.success)
    async def play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("▶️ 재생!", ephemeral=True)

    @discord.ui.button(label="⏸ 일시정지", style=discord.ButtonStyle.secondary)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏸ 일시정지!", ephemeral=True)

    @discord.ui.button(label="⏹ 정지", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏹ 정지!", ephemeral=True)

# ────────────────────────────────────────────────
# 🛰️ on_ready 이벤트
# ────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {bot.user}")
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print(f"❌ GUILD_ID({GUILD_ID})로 서버를 찾지 못했습니다. .env 확인!")
        return
    print(f"🏠 서버 연결됨: {guild.name}")

    # 가입인증 채널
    join_channel = discord.utils.get(guild.text_channels, name="가입인증")
    if join_channel:
        print(f"📢 가입인증 채널 찾음: {join_channel.name}")
        await join_channel.send(
            "🎊✨삐약 디스코드 서버에 오신 것을 환영합니다!✨🎊\n"
            "🪪 1️⃣가입 인증 안내\n"
            "아래 버튼을 눌러 가입 인증을 진행해주세요",
            view=JoinVerifyView()
        )
        await join_channel.send(
            "🪪 2️⃣별명 변경 안내(가입 인증 후)\n"
            "아래 버튼을 눌러 별명 변경을 진행해주세요",
            view=NicknameChangeView()
        )
    else:
        print("⚠️ '가입인증' 채널을 찾을 수 없습니다. 이름 확인!")

    # 라디오 채널
    radio_channel = discord.utils.get(guild.text_channels, name="라디오")
    if radio_channel:
        print(f"📡 라디오 채널 찾음: {radio_channel.name}")
        await radio_channel.send(
            "📡✨ 라디오봇 접속 완료!\n"
            "🎶 아래 버튼으로 라디오 또는 유튜브를 재생하세요.\n"
            "📻 /mbc표준fm /mbcfm4u /sbs러브fm /sbs파워fm /cbs음악fm\n"
            "🎧 /youtubeURL [링크], /youtube검색 [검색어]\n"
            "⛔ /정지 : 재생 중지 및 퇴장",
            view=RadioButtons()
        )
        await radio_channel.send("🎛 재생 제어", view=ControlButtons())
    else:
        print("⚠️ '라디오' 채널을 찾을 수 없습니다. 이름 확인!")

    print("✅ 모든 설정 완료!")

# ────────────────────────────────────────────────
# 🚀 봇 실행
# ────────────────────────────────────────────────
bot.run(TOKEN)
