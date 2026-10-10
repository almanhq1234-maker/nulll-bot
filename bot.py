import datetime
import os
import urllib.parse
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands
import requests
import whois

app = Flask('')

@app.route('/')
def home():
    return "NULLL- INTELLIGENCE Bot 24/7 Aktif!"

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

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,continent,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy"
EMAIL_API_URL = "https://api.xposedornot.com/v1/check-email/{email}"

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
    print(f"NULLL- INTELLIGENCE Aktif: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    try:
        await bot.sync_commands()
        print("Komutlar Discord'a başarıyla senkronize edildi!")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")
    print("-----------------------------------------")

@bot.slash_command(name="ara", description="NULLL- INTELLIGENCE - Kimlik Denetimi", **USER_INSTALL_CONFIG)
async def ara(ctx, user_id: str):
    await ctx.defer()
    try:
        user = await bot.fetch_user(int(user_id))
        timestamp_ms = ((user.id >> 22) + 1420070400000) / 1000.0
        created_at = datetime.datetime.fromtimestamp(timestamp_ms, datetime.timezone.utc).strftime("%d.%m.%Y - %H:%M:%S UTC")

        embed = discord.Embed(
            title="🛡️ `NULLL- INTELLIGENCE` | Discord Kimlik Denetimi", 
            color=DARK_COLOR
        )
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        embed.add_field(name="👤 Kullanıcı Adı", value=f"`{user.name}`", inline=True)
        embed.add_field(name="🏷️ Görünen Ad", value=f"`{user.display_name}`", inline=True)
        embed.add_field(name="🤖 Bot mu?", value="`Evet`" if user.bot else "`Hayır`", inline=True)
        
        embed.add_field(name="🆔 Discord ID", value=f"```text\n{user.id}\n```", inline=False)
        embed.add_field(name="📅 Hesabın Oluşturulma Tarihi", value=f"```text\n{created_at}\n```", inline=False)
        
        embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL- INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ **Hata:** `{e}`", ephemeral=True)

@bot.slash_command(name="ip-lookup", description="NULLL- INTELLIGENCE - Detaylı IP ve Harita Sorgulama", **USER_INSTALL_CONFIG)
async def ip_lookup(ctx, ip_address: str):
    await ctx.defer()
    try:
        res = requests.get(IP_API_URL.format(ip=ip_address)).json()
        if res.get("status") == "success":
            embed = discord.Embed(
                title="🌐 `NULLL- INTELLIGENCE` | IP Network Analysis", 
                description=f"> **Hedef IP Adresi:** `{ip_address}`",
                color=DARK_COLOR
            )
            
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

            embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL- INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("❌ **Hata:** Geçersiz IP adresi!", ephemeral=True)
    except Exception as e:
        await ctx.respond(f"❌ **Hata:** `{e}`", ephemeral=True)

@bot.slash_command(name="email-sızıntı", description="NULLL- INTELLIGENCE - Email Sızıntı Kontrolü", **USER_INSTALL_CONFIG)
async def email_leak(ctx, email: str):
    await ctx.defer(ephemeral=True)
    try:
        r = requests.get(EMAIL_API_URL.format(email=email), timeout=5)
        leaks = []
        if r.status_code == 200:
            data = r.json()
            if "breaches" in data and data["breaches"]:
                leaks = [str(b) for b in data["breaches"]]

        embed = discord.Embed(
            title="📧 `NULLL- INTELLIGENCE` | Sızıntı Analizi",
            description=f"> **Sorgulanan E-Posta:** `{email}`",
            color=discord.Color.red() if leaks else discord.Color.green()
        )
        
        if leaks:
            embed.add_field(name="⚠️ Sızıntı Durumu", value="`Sızıntı Tespit Edildi!`", inline=False)
            leak_text = "\n".join([f"• {l}" for l in leaks[:10]])
            embed.add_field(name="📂 Kaynaklar", value=f"```text\n{leak_text}\n```", inline=False)
        else:
            embed.add_field(name="✅ Sızıntı Durumu", value="`Veri sızıntısı bulunamadı, temiz.`", inline=False)

        embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL- INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ **Hata:** `{e}`", ephemeral=True)

@bot.slash_command(name="username", description="NULLL- INTELLIGENCE - Kullanıcı Adı Sosyal Medya Taraması", **USER_INSTALL_CONFIG)
async def username_check(ctx, username: str):
    await ctx.defer()
    
    platforms = {
        "GitHub": f"https://github.com/{username}",
        "Instagram": f"https://www.instagram.com/{username}/",
        "Twitter / X": f"https://x.com/{username}",
        "Reddit": f"https://www.reddit.com/user/{username}/",
        "Pinterest": f"https://www.pinterest.com/{username}/",
        "Telegram": f"https://t.me/{username}",
        "TikTok": f"https://www.tiktok.com/@{username}",
        "Steam": f"https://steamcommunity.com/id/{username}",
        "Twitch": f"https://www.twitch.tv/{username}"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    found = []
    for name, url in platforms.items():
        try:
            r = requests.get(url, headers=headers, timeout=3, allow_redirects=True)
            if r.status_code == 200:
                found.append(f"🟢 [{name}]({url})")
        except:
            continue

    embed = discord.Embed(
        title="🔍 `NULLL- INTELLIGENCE` | WhatsMyName OSINT", 
        description=f"> **Hedef Kullanıcı Adı:** `{username}`",
        color=DARK_COLOR
    )
    
    if found:
        profiles_text = "\n".join(found)
        embed.add_field(name="🔗 Bulunan Aktif Profiller", value=profiles_text, inline=False)
    else:
        embed.add_field(name="❌ Sonuç", value="`Belirtilen platformlarda açık profil bulunamadı.`", inline=False)

    embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL- INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
    await ctx.respond(embed=embed)

@bot.slash_command(name="domain-sorgu", description="NULLL- INTELLIGENCE - Domain Whois", **USER_INSTALL_CONFIG)
async def domain_lookup(ctx, domain_name: str):
    await ctx.defer()
    try:
        w = whois.whois(domain_name)
        embed = discord.Embed(
            title="🌐 `NULLL- INTELLIGENCE` | Domain WHOIS Bilgisi", 
            description=f"> **Hedef Domain:** `{domain_name}`",
            color=DARK_COLOR
        )
        embed.add_field(name="📝 Kayıt Sağlayıcısı (Registrar)", value=f"```text\n{str(w.registrar or 'Bilinmiyor')}\n```", inline=False)
        embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL- INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ **Hata:** `{e}`", ephemeral=True)

@bot.slash_command(name="url-analiz", description="NULLL- INTELLIGENCE - URL Analiz", **USER_INSTALL_CONFIG)
async def url_analysis(ctx, target_url: str):
    await ctx.defer()
    if not target_url.startswith("http"):
        target_url = "https://" + target_url
    try:
        res = requests.get(target_url, timeout=5)
        embed = discord.Embed(
            title="🔍 `NULLL- INTELLIGENCE` | Web URL Bağlantı Analizi", 
            description=f"> **Hedef URL:** `{target_url}`",
            color=DARK_COLOR
        )
        embed.add_field(name="📡 HTTP Durum Kodu", value=f"`{res.status_code}`", inline=True)
        embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL- INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ **Bağlantı Hatası:** `{e}`", ephemeral=True)

@bot.slash_command(name="adres-sorgu", description="NULLL- INTELLIGENCE - Adres Harita Sorgulama", **USER_INSTALL_CONFIG)
async def adres_sorgu(ctx, adres: str):
    await ctx.defer()
    maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(adres)}"
    
    embed = discord.Embed(
        title="📍 `NULLL- INTELLIGENCE` | Adres & Harita Sorgu", 
        color=DARK_COLOR
    )
    embed.add_field(name="🏢 Aranan Adres", value=f"```text\n{adres}\n```", inline=False)
    embed.add_field(name="🗺️ Harita Bağlantısı", value=f"[Google Maps üzerinde Aç ↗]({maps_url})", inline=False)
    embed.set_footer(text=f"Sorgulayan: {ctx.author.name} • NULLL- INTELLIGENCE", icon_url=ctx.author.display_avatar.url)
    
    await ctx.respond(embed=embed)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("HATA: DISCORD_TOKEN çevre değişkeni bulunamadı!")
    else:
        keep_alive()
        bot.run(BOT_TOKEN)
