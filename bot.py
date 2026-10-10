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
    return "NULLL- INTELLIGENCE Bot Aktif!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

BOT_TOKEN = os.getenv("DISCORD_TOKEN")

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,continent,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy"
EMAIL_API_URL = "https://api.xposedornot.com/v1/check-email/{email}"

@bot.event
async def on_ready():
    print("-----------------------------------------")
    print(f"NULLL- INTELLIGENCE Aktif: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    try:
        # Komutları Discord sunucularına anında kaydeder
        await bot.sync_commands()
        print("Komutlar Discord'a başarıyla senkronize edildi!")
    except Exception as e:
        print(f"Senkronizasyon hatası: {e}")
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

@bot.slash_command(name="ip-lookup", description="NULLL- INTELLIGENCE - Detaylı IP ve Harita Sorgulama")
async def ip_lookup(ctx, ip_address: str):
    await ctx.defer()
    try:
        res = requests.get(IP_API_URL.format(ip=ip_address)).json()
        if res.get("status") == "success":
            embed = discord.Embed(title="🌐 Corvex NetScan & Maps", color=discord.Color.dark_theme())
            embed.description = f"**IP Lookup:** `{ip_address}`\n"
            
            embed.add_field(name="Continent", value=str(res.get('continent', 'N/A')), inline=True)
            embed.add_field(name="Country", value=f"{res.get('country')} ({res.get('countryCode')})", inline=True)
            embed.add_field(name="Region", value=str(res.get('regionName', 'N/A')), inline=True)
            
            embed.add_field(name="City", value=str(res.get('city', 'N/A')), inline=True)
            embed.add_field(name="Zip Code", value=str(res.get('zip', 'N/A')), inline=True)
            embed.add_field(name="Latitude", value=str(res.get('lat', 'N/A')), inline=True)
            
            embed.add_field(name="Longitude", value=str(res.get('lon', 'N/A')), inline=True)
            embed.add_field(name="Timezone", value=str(res.get('timezone', 'N/A')), inline=True)
            embed.add_field(name="ISP", value=str(res.get('isp', 'N/A')), inline=True)
            
            embed.add_field(name="AS Number", value=str(res.get('as', 'N/A')), inline=False)
            embed.add_field(name="Organization", value=str(res.get('org', 'N/A')), inline=False)
            embed.add_field(name="Proxy/VPN", value="Yes" if res.get('proxy') else "No", inline=False)
            
            lat, lon = res.get("lat"), res.get("lon")
            if lat and lon:
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                embed.add_field(name="🗺️ Konum Haritası", value=f"[Google Maps'te Aç]({maps_url})", inline=False)

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
            embed.add_field(name="Durum", value="Sızıntı Tespit Edildi
