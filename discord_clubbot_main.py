# ───────────────────────────────────────────────────────────
# Discord ClubBot - 가입/승급/라디오 관리봇 (2025 안정 수정판)
# ───────────────────────────────────────────────────────────
import os
import asyncio
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import yt_dlp
import functools

# ───────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))  # 서버 ID 입력
CHANNEL_JOIN = int(os.getenv("CHANNEL_JOIN", 0))  # 가입 채널 ID
CHANNEL_PROMOTE = int(os.getenv("CHANNEL_PROMOTE", 0))  # 승급 채널 ID
CHANNEL_RADIO = int(os.getenv("CHANNEL_RADIO", 0))  # 라디오 채널 ID
ROLE_CLUB = int(os.getenv("ROLE_CLUB", 0))  # 클럽원 역할 ID
ROLE_WAR = int(os.getenv("ROLE_WAR", 0))  # 쟁탈원 역할 ID
# ───────────────────────────────────────────────────────────

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ───────────────────────────────────────────────────────────
# 가입 인증 모달
class JoinModal(Modal, title="가입 인증"):
    code_input = TextInput(label="인증 코드를 입력하세요", placeholder="241120", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if self.code_input.value.strip() == "241120":
            role = interaction.guild.get_role(ROLE_CLUB)
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "🎉정답입니다!! 클럽원 역할이 부여되었습니다!! 별명을 인게임 캐릭명으로 변경해주세요!",
                ephemeral=True,
            )
            await asyncio.sleep(5)
            await clear_temp_messages(interaction.channel)
        else:
            await interaction.response.send_message("❌ 정답이 아닙니다.", ephemeral=True)
            await asyncio.sleep(30)
            await clear_temp_messages(interaction.channel)

# ───────────────────────────────────────────────────────────
# 승급 인증 모달
class PromoteModal(Modal, title="승급 인증"):
    code_input = TextInput(label="승급 코드를 입력하세요", placeholder="021142", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if self.code_input.value.strip() == "021142":
            role = interaction.guild.get_role(ROLE_WAR)
            await interaction.user.add_roles(role)
            await interaction.response.send_message("🎉정답입니다!! 쟁탈원 역할이 부여되었습니다!", ephemeral=True)
            await asyncio.sleep(5)
            await clear_temp_messages(interaction.channel)
        else:
            await interaction.response.send_message("❌ 정답이 아닙니다.", ephemeral=True)
            await asyncio.sleep(30)
            await clear_temp_messages(interaction.channel)

# ───────────────────────────────────────────────────────────
# 별명 변경 모달
class NickModal(Modal, title="별명 변경"):
    nick_input = TextInput(label="변경할 별명을 입력하세요", placeholder="인게임 캐릭명", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.user.edit(nick=self.nick_input.value)
            await interaction.response.send_message("✅ 별명이 성공적으로 변경되었습니다!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 별명 변경 실패: {e}", ephemeral=True)

# ───────────────────────────────────────────────────────────
# 임시 메시지 삭제 함수 (고정 메시지 제외)
async def clear_temp_messages(channel):
    async for msg in channel.history(limit=50):
        if not msg.pinned:
            await msg.delete()

# ───────────────────────────────────────────────────────────
# 고정 안내 메시지 + 버튼 등록 함수
async def setup_channel_messages():
    await bot.wait_until_ready()

    join_channel = bot.get_channel(CHANNEL_JOIN)
    promote_channel = bot.get_channel(CHANNEL_PROMOTE)
    radio_channel = bot.get_channel(CHANNEL_RADIO)

    # 가입 인증 안내
    if join_channel:
        await join_channel.purge(limit=50)
        msg1 = await join_channel.send(
            "🎊✨삐약 디스코드 서버에 오신 것을 환영합니다!✨🎊\n"
            "🎊✨운영진 또는 오픈톡 공지사항을 통해 디스코드 인증코드를 확인해주세요!\n\n"
            "🪪✨ 1️⃣ 가입 인증 진행\n아래 버튼을 눌러 가입 인증을 진행해주세요",
        )
        await msg1.pin()
        view1 = View()
        view1.add_item(Button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="join"))
        await join_channel.send(view=view1)

        msg2 = await join_channel.send("🪪✨ 2️⃣별명 변경 진행(인겜 캐릭명으로 통일)")
        await msg2.pin()
        view2 = View()
        view2.add_item(Button(label="별명변경", style=discord.ButtonStyle.secondary, custom_id="nick"))
        await join_channel.send(view=view2)

    # 승급 인증 안내
    if promote_channel:
        await promote_channel.purge(limit=50)
        msg = await promote_channel.send(
            "🪖 쟁탈원으로 승급하기 위해서는\n"
            "🪖 운영진이 안내해준 승인인증 코드를 입력해주시기 바랍니다.\n\n"
            "아래 버튼을 눌러 승급 인증을 진행해주세요"
        )
        await msg.pin()
        view = View()
        view.add_item(Button(label="승급인증", style=discord.ButtonStyle.primary, custom_id="promote"))
        await promote_channel.send(view=view)

    # 라디오 안내
    if radio_channel:
        await radio_channel.purge(limit=50)
        msg = await radio_channel.send(
            "📡✨ 라디오봇 접속 완료!\n🎶 음성 채널에 들어간 후 아래 명령어 사용 가능\n\n"
            "📻 /mbc표준fm   📻 /mbcfm4u   📻 /sbs러브fm   📻 /sbs파워fm   📻 /cbs음악fm\n"
            "🎧 /youtube_url   🎧 /youtube_검색\n"
            "▶️ /재생   ⏸️ /일시정지   ⛔ /정지\n\n⭐ 모든 봇 실행할 때는 명령어상 아이콘 확인 후 실행"
        )
        await msg.pin()

# ───────────────────────────────────────────────────────────
# 버튼 클릭 이벤트
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or "custom_id" not in interaction.data:
        return
    cid = interaction.data["custom_id"]

    if cid == "join":
        await interaction.response.send_modal(JoinModal())
    elif cid == "nick":
        await interaction.response.send_modal(NickModal())
    elif cid == "promote":
        await interaction.response.send_modal(PromoteModal())

# ───────────────────────────────────────────────────────────
# 라디오 및 유튜브 명령어
@tree.command(name="youtube_url", description="유튜브 URL로 재생")
async def youtube_url(interaction: discord.Interaction, url: str):
    await interaction.response.send_message(f"🎵 유튜브 URL 재생 시작: {url}", ephemeral=True)

@tree.command(name="youtube_검색", description="유튜브 검색으로 재생")
async def youtube_search(interaction: discord.Interaction, 키워드: str):
    await interaction.response.send_message(f"🔍 '{키워드}' 검색 결과 재생 시작", ephemeral=True)

@tree.command(name="정지", description="모든 음악 정지 및 메시지 정리")
async def stop_music(interaction: discord.Interaction):
    await interaction.response.send_message("⛔ 모든 재생을 정지했습니다.", ephemeral=True)
    await asyncio.sleep(3)
    await clear_temp_messages(interaction.channel)

# ───────────────────────────────────────────────────────────
# 봇 준비 이벤트
@bot.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {bot.user}")
    try:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ 슬래시 명령어 동기화 완료 (GUILD: {GUILD_ID})")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")

    await setup_channel_messages()

# ───────────────────────────────────────────────────────────
# 실행부
if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
