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
from discord import app_commands
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

class NullBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash komutları başarıyla senkronize edildi!")

bot = NullBot()

BOT_TOKEN = os.getenv("DISCORD_TOKEN")

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,continent,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy"
XPOSED_API_URL = "https://api.xposedornot.com/v1/check-email/{email}"

DARK_COLOR = discord.Color.from_rgb(47, 49, 54)

# ──────────────────────────────────────────────────────────────────────
# PLATFORMS REGISTRY
# ──────────────────────────────────────────────────────────────────────
PLATFORM_ICONS = {
    "github": "🐙", "twitter": "🐦", "x": "🐦", "reddit": "🤖", "youtube": "▶️",
    "instagram": "📸", "tiktok": "🎵", "facebook": "📘", "linkedin": "💼",
    "pinterest": "📌", "snapchat": "👻", "twitch": "🎮", "steam": "🎮",
    "gitlab": "🦊", "bitbucket": "🪣", "keybase": "🔑", "soundcloud": "🎵",
    "medium": "✍️", "dev": "💻", "telegram": "✈️", "gravatar": "🌐",
    "patreon": "🎨", "tumblr": "📝", "producthunt": "🚀", "hacknews": "🔶"
}

def get_platform_icon(site_name: str) -> str:
    key = site_name.lower().strip()
    for p, icon in PLATFORM_ICONS.items():
        if p in key:
            return icon
    return "🟢"

# ──────────────────────────────────────────────────────────────────────
# WMN SCANNER MOTORU
# ──────────────────────────────────────────────────────────────────────
_WMN_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
_cached_wmn_data = None
_wmn_lock = threading.Lock()

def _load_wmn_data():
    global _cached_wmn_data
    with _wmn_lock:
        if _cached_wmn_data is not None:
            return _cached_wmn_data
        try:
            resp = requests.get(_WMN_URL, headers={"User-Agent": "WhoCord-OSINT/1.1"}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "sites" in data:
                    _cached_wmn_data = data
                    return data
        except Exception:
            pass
    return None

def _is_hit(resp, site: dict) -> bool:
    body = resp.text or ""
    e_string = site.get("e_string") or ""
    m_string = site.get("m_string") or ""
    e_code = site.get("e_code")
    m_code = site.get("m_code")

    if m_code is not None and resp.status_code == m_code:
        return False
    if m_string and m_string in body:
        return False
    if e_string and e_string in body:
        return True
    if e_code is not None and resp.status_code == e_code:
        return not e_string
    return False

def _probe_site(site: dict, username: str, timeout: int) -> dict | None:
    method = str(site.get("request_method") or "GET").upper()
    if method != "GET":
        return None
    uri_check = site.get("uri_check") or ""
    if "{account}" not in uri_check:
        return None

    url = uri_check.replace("{account}", username)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if _is_hit(resp, site):
            return {
                "site": site.get("name") or "unknown",
                "url": url,
                "status": resp.status_code,
            }
    except Exception:
        pass
    return None

def run_wmn_scan(username: str, max_workers: int = 25, timeout: int = 4) -> list[dict]:
    data = _load_wmn_data()
    if not data or not data.get("sites"):
        return []

    sites = data["sites"]
    hits = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_probe_site, s, username, timeout): s for s in sites}
        for fut in as_completed(futures):
            try:
                res = fut.result()
                if res:
                    hits.append(res)
            except Exception:
                pass
    return hits


@bot.event
async def on_ready():
    print("-----------------------------------------")
    print(f"NULLL- INTELLIGENCE Aktif: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    print("-----------------------------------------")

@bot.tree.command(name="ara", description="NULLL- INTELLIGENCE - Kimlik Denetimi")
async def ara(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer()
    try:
        user = await bot.fetch_user(int(user_id))
        timestamp_ms = ((user.id >> 22) + 1420070400000) / 1000.0
        created_at = datetime.datetime.fromtimestamp(timestamp_ms, datetime.timezone.utc).strftime("%d.%m.%Y - %H:%M:%S UTC")

        embed = discord.Embed(title="🛡️ `NULLL- INTELLIGENCE` | Discord Kimlik Denetimi", color=DARK_COLOR)
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        embed.add_field(name="👤 Kullanıcı Adı", value=f"`{user.name}`", inline=True)
        embed.add_field(name="🏷️ Görünen Ad", value=f"`{user.display_name}`", inline=True)
        embed.add_field(name="🤖 Bot mu?", value="`Evet`" if user.bot else "`Hayır`", inline=True)
        
        embed.add_field(name="🆔 Discord ID", value=f"```text\n{user.id}\n```", inline=False)
        embed.add_field(name="📅 Hesabın Oluşturulma Tarihi", value=f"```text\n{created_at}\n```", inline=False)
        
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

@bot.tree.command(name="ip-lookup", description="NULLL- INTELLIGENCE - Detaylı IP ve Harita Sorgulama")
async def ip_lookup(interaction: discord.Interaction, ip_address: str):
    await interaction.response.defer()
    try:
        res = requests.get(IP_API_URL.format(ip=ip_address)).json()
        if res.get("status") == "success":
            embed = discord.Embed(title="🌐 `NULLL- INTELLIGENCE` | IP Network Analysis", description=f"> **Hedef IP Adresi:** `{ip_address}`", color=DARK_COLOR)
            
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

            embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ **Hata:** Geçersiz IP adresi!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

@bot.tree.command(name="email-sızıntı", description="NULLL- INTELLIGENCE - Ultra Güçlü E-Posta İstihbarat & Sızıntı Analizi")
async def email_leak(interaction: discord.Interaction, email: str):
    await interaction.response.defer(ephemeral=True)
    email = email.strip().lower()
    hibp_api_key = os.getenv("HIBP_API_KEY", "")
    
    leaks = []
    emailrep_data = {}
    gravatar_url = None

    try:
        if hibp_api_key:
            headers = {"User-Agent": "WhoCord-OSINT/1.1", "hibp-api-key": hibp_api_key, "Accept": "application/json"}
            r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", headers=headers, params={"truncateResponse": "false"}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    leaks = [b.get("Name", str(b)) for b in data]
        
        r2 = requests.get(XPOSED_API_URL.format(email=email), timeout=5)
        if r2.status_code == 200:
            data2 = r2.json()
            if "breaches" in data2 and data2["breaches"]:
                for b in data2["breaches"]:
                    b_str = str(b)
                    if b_str not in leaks:
                        leaks.append(b_str)
    except Exception:
        pass

    try:
        r = requests.get(f"https://emailrep.io/{email}", headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            emailrep_data = r.json()
    except Exception:
        pass

    try:
        email_hash = hashlib.md5(email.encode()).hexdigest()
        g_url = f"https://www.gravatar.com/avatar/{email_hash}?d=404&s=200"
        r = requests.get(g_url, timeout=5)
        if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
            gravatar_url = g_url
    except Exception:
        pass

    embed = discord.Embed(
        title="📧 `NULLL- INTELLIGENCE` | Ultra E-Posta Analizi",
        description=f"> **Sorgulanan E-Posta:** `{email}`",
        color=discord.Color.red() if leaks or emailrep_data.get("reputation") == "low" else discord.Color.green()
    )
    
    if leaks:
        embed.add_field(name="⚠️ Tespit Edilen Veri İhlalleri (Sızıntı)", value=f"```text\n" + "\n".join([f"• {l}" for l in leaks[:10]]) + "\n```", inline=False)
    else:
        embed.add_field(name="✅ Sızıntı Durumu", value="`Herhangi bir veri ihlali bulunamadı (Temiz).`", inline=False)
        
    rep = emailrep_data.get("reputation", "Bilinmiyor")
    suspicious = emailrep_data.get("suspicious", False)
    embed.add_field(name="🛡️ EmailRep İtibar Skoru", value=f"`{str(rep).upper()}` | Şüpheli: `{'Evet' if suspicious else 'Hayır'}`", inline=False)

    if gravatar_url:
        embed.add_field(name="🖼️ Profil Görseli (Gravatar)", value=f"[Görseli Aç ↗]({gravatar_url})", inline=False)
        embed.set_thumbnail(url=gravatar_url)

    embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="phone-sorgu", description="NULLL- INTELLIGENCE - PhoneInfo Tarzı Detaylı Telefon Analizi")
async def phone_lookup(interaction: discord.Interaction, phone_number: str):
    await interaction.response.defer(ephemeral=True)
    clean_phone = "".join(filter(str.isdigit, phone_number))
    
    country_name = "Bilinmiyor / Uluslararası"
    carrier = "Bilinmiyor"
    line_type = "Mobil / Sabit Hat"
    
    if clean_phone.startswith("90"):
        country_name = "Türkiye (+90)"
        carrier = "Türk Telekom / Turkcell / Vodafone"
    elif clean_phone.startswith("1"):
        country_name = "ABD / Kanada (+1)"
        carrier = "North American Numbering Plan"
    elif clean_phone.startswith("44"):
        country_name = "Birleşik Krallık (+44)"
        carrier = "UK Carrier"
    elif clean_phone.startswith("49"):
        country_name = "Almanya (+49)"
        carrier = "German Carrier"

    embed = discord.Embed(
        title="📱 `NULLL- INTELLIGENCE` | PhoneInfo İstihbarat Analizi",
        description=f"> **Hedef Numara:** `+{clean_phone}`",
        color=DARK_COLOR
    )
    
    embed.add_field(name="🌍 Ülke / Bölge", value=f"`{country_name}`", inline=True)
    embed.add_field(name="📶 Muhtemel Operatör", value=f"`{carrier}`", inline=True)
    embed.add_field(name="📞 Hat Türü", value=f"`{line_type}`", inline=True)
    
    embed.add_field(name="🔍 Biçimlendirilmiş Format", value=f"```text\n+{clean_phone}\n```", inline=False)
    
    whatsapp_url = f"https://wa.me/{clean_phone}"
    embed.add_field(name="💬 Hızlı Bağlantılar", value=f"[WhatsApp ile Sohbet Başlat ↗]({whatsapp_url})", inline=False)
    
    embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="username", description="NULLL- INTELLIGENCE - WMN Gelişmiş Sosyal Medya Taraması")
async def username_check(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    
    hits = run_wmn_scan(username, max_workers=20, timeout=4)

    embed = discord.Embed(
        title="🔍 `NULLL- INTELLIGENCE` | WMN Gelişmiş Kullanıcı Adı Taraması", 
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
        if len(hits) > 15:
            embed.set_footer(text=f"Ve {len(hits) - 15} tane daha profil bulundu! • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        else:
            embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
    else:
        embed.add_field(name="❌ Sonuç", value="`Belirtilen kullanıcı adı için aktif profil bulunamadı.`", inline=False)
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="domain-sorgu", description="NULLL- INTELLIGENCE - Domain Whois")
async def domain_lookup(interaction: discord.Interaction, domain_name: str):
    await interaction.response.defer()
    try:
        w = whois.whois(domain_name)
        embed = discord.Embed(title="🌐 `NULLL- INTELLIGENCE` | Domain WHOIS Bilgisi", description=f"> **Hedef Domain:** `{domain_name}`", color=DARK_COLOR)
        embed.add_field(name="📝 Kayıt Sağlayıcısı (Registrar)", value=f"```text\n{str(w.registrar or 'Bilinmiyor')}\n```", inline=False)
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** `{e}`", ephemeral=True)

@bot.tree.command(name="url-analiz", description="NULLL- INTELLIGENCE - URL Analiz")
async def url_analysis(interaction: discord.Interaction, target_url: str):
    await interaction.response.defer()
    if not target_url.startswith("http"):
        target_url = "https://" + target_url
    try:
        res = requests.get(target_url, timeout=5)
        embed = discord.Embed(title="🌐 `NULLL- INTELLIGENCE` | Web URL Bağlantı Analizi", description=f"> **Hedef URL:** `{target_url}`", color=DARK_COLOR)
        embed.add_field(name="📡 HTTP Durum Kodu", value=f"`{res.status_code}`", inline=True)
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Bağlantı Hatası:** `{e}`", ephemeral=True)

@bot.tree.command(name="adres-sorgu", description="NULLL- INTELLIGENCE - Adres Harita Sorgulama")
async def adres_sorgu(interaction: discord.Interaction, adres: str):
    await interaction.response.defer()
    maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(adres)}"
    
    embed = discord.Embed(title="📍 `NULLL- INTELLIGENCE` | Adres & Harita Sorgu", color=DARK_COLOR)
    embed.add_field(name="🏢 Aranan Adres", value=f"```text\n{adres}\n```", inline=False)
    embed.add_field(name="🗺️ Harita Bağlantısı", value=f"[Google Maps üzerinde Aç ↗]({maps_url})", inline=False)
    embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • NULLL- INTELLIGENCE", icon_url=interaction.user.display_avatar.url)
    
    await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("HATA: DISCORD_TOKEN çevre değişkeni bulunamadı!")
    else:
        keep_alive()
        bot.run(BOT_TOKEN)
