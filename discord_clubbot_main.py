# ───────────────────────────────────────────────────────────
# Discord ClubBot - 가입/승급/라디오/유튜브 통합 관리봇
# 2025 완전 자동화 + 안정화 버전
# ───────────────────────────────────────────────────────────
import os
import asyncio
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import yt_dlp

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
CHANNEL_JOIN = int(os.getenv("CHANNEL_JOIN", 0))
CHANNEL_PROMOTE = int(os.getenv("CHANNEL_PROMOTE", 0))
CHANNEL_RADIO = int(os.getenv("CHANNEL_RADIO", 0))
ROLE_CLUB = int(os.getenv("ROLE_CLUB", 0))
ROLE_WAR = int(os.getenv("ROLE_WAR", 0))

intents = discord.Intents.all()

# ───────────────────────────────────────────────────────────
# 커스텀 Bot
class ClubBot(commands.Bot):
    async def setup_hook(self):
        print("⚙️ 채널 안내문 자동 세팅 중...")
        await self.wait_until_ready()
        await setup_channel_messages()
        print("✅ 안내문 자동 고정 완료.")

bot = ClubBot(command_prefix="!", intents=intents)
tree = bot.tree

# ───────────────────────────────────────────────────────────
# 모달 정의
class JoinModal(Modal, title="가입 인증"):
    code_input = TextInput(label="인증코드", placeholder="241120")
    async def on_submit(self, interaction: discord.Interaction):
        if self.code_input.value.strip() == "241120":
            role = interaction.guild.get_role(ROLE_CLUB)
            await interaction.user.add_roles(role)
            await interaction.response.send_message("🎉 클럽원 역할이 부여되었습니다!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 잘못된 코드입니다.", ephemeral=True)

class PromoteModal(Modal, title="승급 인증"):
    code_input = TextInput(label="승급코드", placeholder="021142")
    async def on_submit(self, interaction: discord.Interaction):
        if self.code_input.value.strip() == "021142":
            role = interaction.guild.get_role(ROLE_WAR)
            await interaction.user.add_roles(role)
            await interaction.response.send_message("🎊 쟁탈원 역할이 부여되었습니다!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 잘못된 코드입니다.", ephemeral=True)

class NickModal(Modal, title="별명 변경"):
    nick_input = TextInput(label="변경할 별명", placeholder="인게임 캐릭명")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.user.edit(nick=self.nick_input.value)
            await interaction.response.send_message("✅ 별명이 변경되었습니다!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 실패: {e}", ephemeral=True)

# ───────────────────────────────────────────────────────────
# 임시 메시지 삭제
async def clear_temp_messages(channel):
    async for msg in channel.history(limit=50):
        if not msg.pinned:
            try: await msg.delete()
            except: pass

# ───────────────────────────────────────────────────────────
# 안내 메시지 자동 등록
async def setup_channel_messages():
    join = bot.get_channel(CHANNEL_JOIN)
    promote = bot.get_channel(CHANNEL_PROMOTE)
    radio = bot.get_channel(CHANNEL_RADIO)

    # 가입 안내
    if join:
        await join.purge(limit=50)
        msg = await join.send(
            "🎊✨ 디스코드 서버에 오신 것을 환영합니다! ✨🎊\n"
            "🪪 1️⃣ 가입 인증 진행\n아래 버튼으로 인증\n"
            "🪪 2️⃣ 별명 변경 진행\n버튼 클릭 후 입력"
        )
        await msg.pin()
        view = View()
        view.add_item(Button(label="가입인증", style=discord.ButtonStyle.primary, custom_id="join"))
        view.add_item(Button(label="별명변경", style=discord.ButtonStyle.secondary, custom_id="nick"))
        await join.send(view=view)

    # 승급 안내
    if promote:
        await promote.purge(limit=50)
        msg = await promote.send(
            "🪖 쟁탈원 승급 인증을 진행해주세요.\n"
            "아래 버튼으로 인증"
        )
        await msg.pin()
        view = View()
        view.add_item(Button(label="승급인증", style=discord.ButtonStyle.primary, custom_id="promote"))
        await promote.send(view=view)

    # 라디오 안내
    if radio:
        await radio.purge(limit=50)
        msg = await radio.send(
            "📡✨ 라디오봇 접속 완료!\n\n"
            "📻 /mbc표준fm /mbcfm4u /sbs러브fm /sbs파워fm /cbs음악fm\n"
            "🎧 /youtube_url /youtube_검색\n"
            "⏸ /정지"
        )
        await msg.pin()

# ───────────────────────────────────────────────────────────
# 버튼 이벤트 처리
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
# 라디오 스트림 URL
RADIO_URLS = {
    "mbc표준fm": "http://miniplay.imbc.com/aod/_definst_/mp4:mbcfm01.stream/playlist.m3u8",
    "mbcfm4u": "http://miniplay.imbc.com/aod/_definst_/mp4:mbcfm02.stream/playlist.m3u8",
    "sbs러브fm": "https://stream.sbs.co.kr/S01/RLOVEFM_APP.smil/playlist.m3u8",
    "sbs파워fm": "https://stream.sbs.co.kr/S01/RPOWERFM_APP.smil/playlist.m3u8",
    "cbs음악fm": "http://aac.cbs.co.kr/cbs939/_definst_/cbs939.stream/playlist.m3u8",
}
voice_clients = {}

async def play_radio(interaction: discord.Interaction, url: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("⚠️ 음성 채널에 먼저 들어가주세요!", ephemeral=True)
        return
    vc = voice_clients.get(interaction.guild.id)
    if vc is None or not vc.is_connected():
        vc = await interaction.user.voice.channel.connect()
        voice_clients[interaction.guild.id] = vc
    vc.stop()
    vc.play(discord.FFmpegPCMAudio(url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"))
    await interaction.response.send_message(f"📻 재생 시작!", ephemeral=True)

# ───────────────────────────────────────────────────────────
# 라디오 명령어 등록
def register_radio_commands():
    for name, url in RADIO_URLS.items():
        async def cmd(interaction: discord.Interaction, *, u=url):
            await play_radio(interaction, u)
        tree.command(name=name, description=f"{name} 라디오 재생")(cmd)

register_radio_commands()

# ───────────────────────────────────────────────────────────
# 유튜브 URL
@tree.command(name="youtube_url", description="유튜브 URL 재생")
async def youtube_url(interaction: discord.Interaction, url: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("⚠️ 음성 채널에 먼저 들어가주세요!", ephemeral=True)
        return
    vc = await interaction.user.voice.channel.connect()
    ydl_opts = {"format": "bestaudio"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        stream = info["url"]
    vc.play(discord.FFmpegPCMAudio(stream))
    await interaction.response.send_message(f"🎵 `{info['title']}` 재생 중!", ephemeral=True)

# 유튜브 검색
@tree.command(name="youtube_검색", description="유튜브 검색어로 재생")
async def youtube_search(interaction: discord.Interaction, 키워드: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("⚠️ 음성 채널에 먼저 들어가주세요!", ephemeral=True)
        return
    vc = await interaction.user.voice.channel.connect()
    with yt_dlp.YoutubeDL({"format": "bestaudio", "noplaylist": True, "quiet": True}) as ydl:
        info = ydl.extract_info(f"ytsearch:{키워드}", download=False)["entries"][0]
        stream = info["url"]
    vc.play(discord.FFmpegPCMAudio(stream))
    await interaction.response.send_message(f"🎶 `{info['title']}` 재생 중!", ephemeral=True)

# 정지
@tree.command(name="정지", description="모든 재생 중단")
async def stop_music(interaction: discord.Interaction):
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if vc:
        vc.stop()
        await vc.disconnect()
    await interaction.response.send_message("⛔ 재생 중단!", ephemeral=True)

# ───────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {bot.user}")
    try:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print("✅ 명령어 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")

# ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
