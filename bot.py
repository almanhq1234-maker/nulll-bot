import datetime
import os
import urllib.parse
import discord
from discord.ext import commands
import requests
import whois

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Token'ı doğrudan yazmak yerine Render Environment Variables'dan güvenle çekiyoruz:
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,continent,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy"
EMAIL_API_URL = "https://api.xposedornot.com/v1/check-email/{email}"
WHATSMYNAME_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"


@bot.event
async def on_ready():
    print("-----------------------------------------")
    print(f"NULLL- INTELLIGENCE Aktif: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    print("Komutlar aktif!")
    print("-----------------------------------------")


@bot.slash_command(name="ara", description="NULLL- INTELLIGENCE - Kimlik Denetimi")
async def ara(ctx, user_id: str):
    await ctx.defer()
    try:
        user = await bot.fetch_user(int(user_id))
        timestamp_ms = ((user.id >> 22) + 1420070400000) / 1000.0
        created_at = datetime.datetime.fromtimestamp(timestamp_ms, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        embed = discord.Embed(title="🛡️ NULLL- INTELLIGENCE - Kimlik Denetimi", color=discord.Color.dark_purple())
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.add_field(name="Kullanıcı Adı", value=str(user.name), inline=True)
        embed.add_field(name="Görünen Ad", value=str(user.display_name), inline=True)
        embed.add_field(name="Discord ID", value=str(user.id), inline=False)
        embed.add_field(name="Oluşturulma (UTC)", value=str(created_at), inline=False)
        embed.add_field(name="Bot mu?", value="Evet" if user.bot else "Hayır", inline=True)
        embed.set_footer(text=f"Sorgulayan: {ctx.author.name}")
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"Hata oluştu: {e}", ephemeral=True)


@bot.slash_command(name="ip-lookup", description="NULLL- INTELLIGENCE - IP ve Harita Sorgulama")
async def ip_lookup(ctx, ip_address: str):
    await ctx.defer()
    try:
        res = requests.get(IP_API_URL.format(ip=ip_address)).json()
        if res.get("status") == "success":
            embed = discord.Embed(title="🌐 NULLL- NetScan & Maps", color=discord.Color.dark_theme())
            embed.add_field(name="Ülke", value=f"{res.get('country')} ({res.get('countryCode')})", inline=True)
            embed.add_field(name="Şehir", value=str(res.get('city')), inline=True)
            embed.add_field(name="ISS", value=str(res.get('isp')), inline=True)
            
            lat, lon = res.get("lat"), res.get("lon")
            if lat and lon:
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                embed.add_field(name="Harita", value=f"[Google Maps'te Aç]({maps_url})", inline=False)

            embed.set_footer(text=f"Sorgulayan: {ctx.author.name}")
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("Geçersiz IP adresi!", ephemeral=True)
    except Exception as e:
        await ctx.respond(f"Hata: {e}", ephemeral=True)


@bot.slash_command(name="email-sızıntı", description="NULLL- INTELLIGENCE - Email Sızıntı Kontrolü")
async def email_leak(ctx, email: str):
    await ctx.defer(ephemeral=True)
    try:
        r = requests.get(EMAIL_API_URL.format(email=email), timeout=5)
        leaks = []
        if r.status_code == 200:
            data = r.json()
            if "breaches" in data and data["breaches"]:
                leaks = [str(b) for b in data["breaches"]]

        embed = discord.Embed(title="📧 NULLL- Leak Intelligence")
        if leaks:
            embed.color = discord.Color.red()
            embed.add_field(name="Durum", value="Sızıntı Tespit Edildi!", inline=False)
            embed.add_field(name="Kaynaklar", value="\n".join([f"• {l}" for l in leaks[:10]]), inline=False)
        else:
            embed.color = discord.Color.green()
            embed.add_field(name="Durum", value="Temiz kayıt.", inline=False)

        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"Hata: {e}", ephemeral=True)


@bot.slash_command(name="username", description="NULLL- INTELLIGENCE - Kullanıcı Adı Tarama")
async def username_check(ctx, username: str):
    await ctx.defer()
    embed = discord.Embed(title="🔍 NULLL- WhatsMyName", description=f"Aranıyor: {username}")
    await ctx.respond(embed=embed)


@bot.slash_command(name="domain-sorgu", description="NULLL- INTELLIGENCE - Domain Whois")
async def domain_lookup(ctx, domain_name: str):
    await ctx.defer()
    try:
        w = whois.whois(domain_name)
        embed = discord.Embed(title="🌐 NULLL- Domain Intelligence")
        embed.add_field(name="Kayıt", value=str(w.registrar or "Bilinmiyor"), inline=False)
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"Hata: {e}", ephemeral=True)


@bot.slash_command(name="url-analiz", description="NULLL- INTELLIGENCE - URL Analiz")
async def url_analysis(ctx, target_url: str):
    await ctx.defer()
    if not target_url.startswith("http"):
        target_url = "https://" + target_url
    try:
        res = requests.get(target_url, timeout
