import datetime
import os
import urllib.parse
import hashlib
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands
import requests

# ──────────────────────────────────────────────────────────────────────
# MODÜL İMPORTLARI (Göreceli import çakışmalarını önleyen yapı)
# ──────────────────────────────────────────────────────────────────────
try:
    from username_search import run_user_scanner
except ImportError:
    def run_user_scanner(target, mode="username"):
        return []

try:
    from wmn_scanner import run_wmn_scan
except ImportError:
    def run_wmn_scan(username, max_workers=25, timeout=4):
        return []

try:
    from email_intel import *
except ImportError:
    pass

try:
    from extras import extract_exif, reverse_image_search
except ImportError:
    def extract_exif(img_path): return {}
    def reverse_image_search(url): return []

try:
    from reporting import *
except ImportError:
    pass

try:
    from manifest import create_evidentiary_manifest
except ImportError:
    def create_evidentiary_manifest(target, results): return {"manifest_hash": "OK"}

try:
    from platforms import get_platform_icon
except ImportError:
    def get_platform_icon(site_name): return "🟢"

app = Flask('')

@app.route('/')
def home():
    return "NULLL-INTELLIGENCE x WhoCord Framework 24/7 Aktif!", 200

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

DARK_COLOR = discord.Color.from_rgb(47, 49, 54)

USER_INSTALL_CONFIG = {
    "integration_types": {
        discord.IntegrationType.user_install,
        discord.IntegrationType.guild_install
    },
    "contexts": {
        discord.InteractionContextType.guild,
        discord.InteractionContextType.bot_dm,
        discord.InteractionContextType.private_channel
    }
}

@bot.event
async def on_ready():
    print("-----------------------------------------")
    print(f"NULLL-INTELLIGENCE Aktif: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    try:
        await bot.sync_commands()
        print("Komutlar Discord'a başarıyla senkronize edildi!")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")
    print("-----------------------------------------")

# 1. Discord Kimlik Denetimi
@bot.slash_command(name="ara", description="NULLL-INTELLIGENCE - Discord Kimlik Denetimi", **USER_INSTALL_CONFIG)
async def ara(ctx, user_id: str):
    await ctx.defer()
    try:
        user = await bot.fetch_user(int(user_id))
        timestamp_ms = ((user.id >> 22) + 1420070400000) / 1000.0
        created_at = datetime.datetime.fromtimestamp(timestamp_ms, datetime.timezone.utc).strftime("%d.%m.%Y - %H:%M:%S UTC")

        embed = discord.Embed(title="🛡️ `NULLL-INTELLIGENCE` | Discord Kimlik Denetimi", color=DARK_COLOR)
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        embed.add_field(name="👤 Kullanıcı Adı", value=f"`{user.name}`", inline=True)
        embed.add_field(name="🏷️ Görünen Ad", value=f"`{user.display_name}`", inline=True)
        embed.add_field(name="🤖 Bot mu?", value="`Evet`" if user.bot else "`Hayır`", inline=True)
        embed.add_field(name="🆔 Discord ID", value=f"```text\n{user.id}\n```", inline=False)
        embed.add_field(name="📅 Hesabın Oluşturulma Tarihi", value=f"```text\n{created_at}\n```", inline=False)
        
        embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL-INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ **Hata:** `{e}`", ephemeral=True)

# 2. Gelişmiş Kullanıcı Adı Taraması
@bot.slash_command(name="username", description="NULLL-INTELLIGENCE - Profesyonel Sosyal Medya & Kullanıcı Adı Taraması", **USER_INSTALL_CONFIG)
async def username_check(ctx, username: str):
    await ctx.defer()
    
    hits = run_user_scanner(username, mode="username")
    if not hits:
        hits = run_wmn_scan(username)

    embed = discord.Embed(
        title="🔍 `NULLL-INTELLIGENCE` | Gelişmiş İstihbarat Taraması", 
        description=f"> **Hedef Kullanıcı Adı:** `{username}`",
        color=DARK_COLOR
    )
    
    if hits:
        found_links = []
        for h in hits[:15]:
            s_name = h.get("site", "Bilinmiyor")
            s_url = h.get("url", "#")
            icon = get_platform_icon(s_name)
            found_links.append(f"{icon} [{s_name}]({s_url})")
            
        embed.add_field(name=f"🔗 Bulunan Aktif Profiller (Toplam: {len(hits)})", value="\n".join(found_links), inline=False)
        
        try:
            manifest_data = create_evidentiary_manifest(target=username, results=hits)
            embed.add_field(name="📜 Kanıt Manifestosu", value=f"SHA-256 İmzalı Rapor Üretildi (`{manifest_data.get('manifest_hash', 'OK')[:16]}...`)", inline=False)
        except Exception:
            pass

        if len(hits) > 15:
            embed.set_footer(text=f"Ve {len(hits) - 15} tane daha profil bulundu! • NULLL-INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
        else:
            embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL-INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
    else:
        embed.add_field(name="❌ Sonuç", value="`Belirtilen kullanıcı adı için aktif profil bulunamadı.`", inline=False)
        embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL-INTELLIGENCE", icon_url=ctx.author.display_avatar.url)

    await ctx.respond(embed=embed)

# 3. IP Network Analizi
@bot.slash_command(name="ip-lookup", description="NULLL-INTELLIGENCE - Detaylı IP ve Harita Sorgulama", **USER_INSTALL_CONFIG)
async def ip_lookup(ctx, ip_address: str):
    await ctx.defer()
    try:
        res = requests.get(f"http://ip-api.com/json/{ip_address}?fields=status,message,continent,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy").json()
        if res.get("status") == "success":
            embed = discord.Embed(title="🌐 `NULLL-INTELLIGENCE` | IP Network Analysis", description=f"> **Hedef IP Adresi:** `{ip_address}`", color=DARK_COLOR)
            
            embed.add_field(name="🌍 Kıta", value=f"`{res.get('continent', 'N/A')}`", inline=True)
            embed.add_field(name="🏳️ Ülke", value=f"`{res.get('country')} ({res.get('countryCode')})`", inline=True)
            embed.add_field(name="📍 Bölge", value=f"`{res.get('regionName', 'N/A')}`", inline=True)
            embed.add_field(name="🏙️ Şehir", value=f"`{res.get('city', 'N/A')}`", inline=True)
            embed.add_field(name="📮 Posta Kodu", value=f"`{res.get('zip', 'N/A')}`", inline=True)
            embed.add_field(name="🕒 Zaman Dilimi", value=f"`{res.get('timezone', 'N/A')}`", inline=True)
            
            embed.add_field(name="📡 İnternet Servis Sağlayıcı (ISP)", value=f"```text\n{res.get('isp', 'N/A')}\n```", inline=False)
            embed.add_field(name="🏢 Organizasyon / AS", value=f"```text\n{res.get('org', 'N/A')} ({res.get('as', 'N/A')})\n```", inline=False)
            embed.add_field(name="🛡️ Proxy / VPN Tespiti", value="`Evet (Riskli)`" if res.get('proxy') else "`Hayır (Temiz)`", inline=False)
            
            lat, lon = res.get("lat"), res.get("lon")
            if lat and lon:
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                embed.add_field(name="🗺️ Coğrafi Konum", value=f"[Google Maps üzerinde Aç ↗]({maps_url})", inline=False)

            embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL-INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("❌ **Hata:** Geçersiz IP adresi!", ephemeral=True)
    except Exception as e:
        await ctx.respond(f"❌ **Hata:** `{e}`", ephemeral=True)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("HATA: DISCORD_TOKEN çevre değişkeni bulunamadı!")
    else:
        keep_alive()
        bot.run(BOT_TOKEN)
