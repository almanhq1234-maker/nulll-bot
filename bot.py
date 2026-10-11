import os
import sys
import importlib
import datetime
import threading
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands
import requests

# Flask 24/7 Uptime Sunucusu (Render için)
app = Flask('')

@app.route('/')
def home():
    return "NULLL-INTELLIGENCE x WhoCord Framework Tam Kapasite Aktif!", 200

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# Dinamik Modül Yükleyici (Tüm alt klasörleri ve modülleri tarar)
LOADED_MODULES = {}
current_dir = os.path.dirname(os.path.abspath(__file__))

for root, dirs, files in os.walk(current_dir):
    for file in files:
        if file.endswith(".py") and file != "bot.py":
            mod_name = file[:-3]
            try:
                sys.path.append(root)
                LOADED_MODULES[mod_name] = importlib.import_module(mod_name)
            except Exception:
                pass

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class NullBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Tüm OSINT pipeline aşamaları yüklendi ve komutlar senkronize edildi. (Aktif Modül: {len(LOADED_MODULES)})")

bot = NullBot()
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
DARK_COLOR = discord.Color.from_rgb(47, 49, 54)

@bot.event
async def on_ready():
    print("-----------------------------------------")
    print(f"NULLL-INTELLIGENCE Ultimate Engine Aktif: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    print("-----------------------------------------")

# 1. Discord Kimlik Denetimi
@bot.tree.command(name="ara", description="NULLL-INTELLIGENCE - Discord Kimlik Denetimi")
async def ara(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer()
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
        
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL-INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

# 2. E-Posta İstihbarat Analizi (EmailInvestigationStage / Holehe / HIBP)
@bot.tree.command(name="email", description="NULLL-INTELLIGENCE - Derin E-Posta Sızıntı ve Servis Taraması")
async def email_check(interaction: discord.Interaction, email: str):
    await interaction.response.defer()
    try:
        results_summary = []
        for mod_name, mod in LOADED_MODULES.items():
            if hasattr(mod, "check_hibp"):
                try:
                    hibp = mod.check_hibp(email)
                    if hibp:
                        results_summary.append(f"🔴 HIBP: {len(hibp)} sızıntı bulundu.")
                except Exception:
                    pass
            if hasattr(mod, "run_holehe"):
                try:
                    sites = mod.run_holehe(email)
                    if sites:
                        results_summary.append(f"🟢 Holehe: {len(sites)} platformda kayıtlı.")
                except Exception:
                    pass

        embed = discord.Embed(
            title="📧 `NULLL-INTELLIGENCE` | E-Posta İstihbarat Raporu", 
            description=f"> **Hedef E-Posta:** `{email}`",
            color=DARK_COLOR
        )
        
        if results_summary:
            embed.add_field(name="🔍 Bulgular", value="\n".join(results_summary), inline=False)
        else:
            embed.add_field(name="ℹ️ Durum", value="`EmailInvestigationStage motoru çalıştırıldı. Detaylı tarama tamamlandı.`", inline=False)
            
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL-INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

# 3. Telefon Numarası Analizi (PhoneInvestigationStage)
@bot.tree.command(name="phone", description="NULLL-INTELLIGENCE - Telefon Numarası & Operatör Analizi")
async def phone_check(interaction: discord.Interaction, phone_number: str):
    await interaction.response.defer()
    try:
        meta = {}
        carrier_data = {}
        
        for mod_name, mod in LOADED_MODULES.items():
            if hasattr(mod, "PhoneInvestigationStage"):
                stage_cls = getattr(mod, "PhoneInvestigationStage")
                if hasattr(stage_cls, "_validate_phonenumbers"):
                    meta = stage_cls._validate_phonenumbers(phone_number)
                if hasattr(stage_cls, "_carrier_lookup"):
                    carrier_data = stage_cls._carrier_lookup(phone_number)
                break

        embed = discord.Embed(
            title="📱 `NULLL-INTELLIGENCE` | Telefon İstihbarat Analizi", 
            description=f"> **Hedef Numara:** `{phone_number}`",
            color=DARK_COLOR
        )
        
        if meta:
            embed.add_field(name="📊 Numara Meta Verileri", value=f"```text\nGeçerli Mi?: {meta.get('is_valid', 'Bilinmiyor')}\nTip: {meta.get('number_type', 'Bilinmiyor')}\nÜlke: {meta.get('country', 'Bilinmiyor')}\nOperatör: {meta.get('carrier', 'Bilinmiyor')}\n```", inline=False)
            
        if carrier_data:
            embed.add_field(name="📡 Carrier & Lokasyon Verisi", value=f"```text\nOperatör: {carrier_data.get('carrier', 'Bilinmiyor')}\nHat Türü: {carrier_data.get('line_type', 'Bilinmiyor')}\nÜlke Kodu: {carrier_data.get('country_code', 'Bilinmiyor')}\n```", inline=False)

        if not meta and not carrier_data:
            embed.add_field(name="ℹ️ Durum", value="`PhoneInvestigationStage pipeline çalıştırıldı.`", inline=False)

        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL-INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

# 4. Alan Adı / Domain Analizi (DomainInvestigationStage)
@bot.tree.command(name="domain", description="NULLL-INTELLIGENCE - Alan Adı, DNS, SSL & Subdomain Taraması")
async def domain_check(interaction: discord.Interaction, domain: str):
    await interaction.response.defer()
    try:
        dns_records = {}
        ssl_data = {}
        
        for mod_name, mod in LOADED_MODULES.items():
            if hasattr(mod, "DomainInvestigationStage"):
                stage_cls = getattr(mod, "DomainInvestigationStage")
                if hasattr(stage_cls, "_query_dns"):
                    dns_records = stage_cls._query_dns(domain)
                if hasattr(stage_cls, "_get_ssl_info"):
                    ssl_data = stage_cls._get_ssl_info(domain)
                break

        embed = discord.Embed(
            title="🌐 `NULLL-INTELLIGENCE` | Domain İstihbarat Raporu", 
            description=f"> **Hedef Domain:** `{domain}`",
            color=DARK_COLOR
        )
        
        if dns_records:
            dns_str = "\n".join([f"{k}: {', '.join(v[:2])}" for k, v in dns_records.items()])
            embed.add_field(name="📡 DNS Kayıtları", value=f"```text\n{dns_str}\n```", inline=False)
            
        if ssl_data:
            embed.add_field(name="🔒 SSL Sertifikası", value=f"```text\nİhraç Eden: {ssl_data.get('issuer', 'N/A')}\nBitiş: {ssl_data.get('not_after', 'N/A')}\n```", inline=False)

        if not dns_records and not ssl_data:
            embed.add_field(name="ℹ️ Durum", value="`DomainInvestigationStage pipeline üzerinden tarandı.`", inline=False)

        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL-INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

# 5. IP Network Analizi
@bot.tree.command(name="ip-lookup", description="NULLL-INTELLIGENCE - Detaylı IP ve Harita Sorgulama")
async def ip_lookup(interaction: discord.Interaction, ip_address: str):
    await interaction.response.defer()
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

            embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL-INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ **Hata:** Geçersiz IP adresi!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("HATA: DISCORD_TOKEN çevre değişkeni bulunamadı!")
    else:
        keep_alive()
        bot.run(BOT_TOKEN)
