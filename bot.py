import os
import re
import ssl
import socket
import asyncio
import datetime
import urllib.parse
import ipaddress
import time
import io
import subprocess
import hashlib
import json
from threading import Thread

import aiohttp
import requests
import discord
import dns.asyncresolver
import dns.exception
import dns.resolver
import phonenumbers
from phonenumbers import carrier, geocoder, timezone as pn_timezone
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ==================== CONFIG ====================

app = Flask(__name__)


@app.route("/")
def home():
    return "NULLL INTELLIGENCE - Bot aktif!"


def keep_alive():
    Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),
            use_reloader=False
        ),
        daemon=True
    ).start()


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

UA = {"User-Agent": "NULLL-INTELLIGENCE/2.0"}


class NullBot(commands.Bot):
    http_session: aiohttp.ClientSession = None
    is_processing: bool = False

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession(headers=UA)
        await self.tree.sync()
        print("Slash komutları senkronize edildi.")

    async def close(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()


bot = NullBot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")
ABUSEIPDB_KEY = os.getenv("ABUSEIPDB_KEY", "")

# --- YETKİLENDİRME VE AYARLAR ---
OWNER_ID = 1484592449153142789  # Sadece senin ID'n yetki verebilir

# Log Kanalı ve Webhook Bilgileri
LOG_CHANNEL_ID = 1559255221039927487
LOG_WEBHOOK_URL = "https://discord.com/api/webhooks/1559255273586040832/8Kx3KlomyNdJclumYc2Igpw3BFMOPbHe_5J83qPuVrbrIdfDlA2KRNLB3QVxqk8JeZV4"

COLOR = discord.Color.from_rgb(47, 49, 54)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "NULLL-INTELLIGENCE/1.0"})

DOMAIN_RE = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
)


def embed_base(title, description=None, color=COLOR):
    return discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )


def footer(embed, interaction):
    embed.set_footer(
        text=f"Sorgulayan: {interaction.user.name} | NULLL INTELLIGENCE",
        icon_url=interaction.user.display_avatar.url
    )


# ==================== ID BAZLI YETKİLENDİRME SİSTEMİ ====================

AUTH_FILE = "authorized_users.json"


def load_auth():
    if not os.path.exists(AUTH_FILE):
        return []
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_auth(users):
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


async def check_access(interaction: discord.Interaction) -> bool:
    """Sadece bot sahibi ve yetkili listedekilerin botu kullanmasını sağlar."""
    if interaction.user.id == OWNER_ID:
        return True
    
    auth_users = load_auth()
    if interaction.user.id in auth_users:
        return True
        
    return False


# ==================== YARDIMCI VE APİ FONKSİYONLARI ====================

async def dns_lookup_func(name: str, record_type: str = "MX"):
    """Google DoH üzerinden DNS sorgusu"""
    url = f"https://dns.google/resolve?name={urllib.parse.quote(name)}&type={record_type.upper()}"
    try:
        return await aget_json(url)
    except Exception as e:
        print("DNS Lookup Hatası:", repr(e))
        return None


def get_gravatar_url(email: str, size: int = 400) -> str:
    """Gravatar URL üreticisi"""
    email_clean = email.strip().lower()
    email_hash = hashlib.md5(email_clean.encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=404"


async def hudson_rock_search(endpoint: str, param: str, value: str):
    """Hudson Rock Cavalier OSINT API sorgusu"""
    url = f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/{endpoint}?{param}={urllib.parse.quote(value)}"
    try:
        return await aget_json(url)
    except Exception as e:
        print("Hudson Rock API Hatası:", repr(e))
        return None


async def xposed_or_not_search(email: str):
    """XposedOrNot İhlal Tarama API sorgusu"""
    url = f"https://api.xposedornot.com/v1/check-email/{urllib.parse.quote(email)}"
    try:
        return await aget_json(url)
    except Exception as e:
        print("XposedOrNot API Hatası:", repr(e))
        return None


async def ip_geolocation(ip: str):
    """ip-api.com optimize edilmiş coğrafi konum sorgusu (fields=66846719)"""
    url = f"http://ip-api.com/json/{urllib.parse.quote(str(ip))}?fields=66846719"
    try:
        return await aget_json(url)
    except Exception as e:
        print("IP Geolocation API Hatası:", repr(e))
        return None


async def send_log(interaction: discord.Interaction, command_name: str, target_info: str):
    """Yapılan her sorguyu webhook veya doğrudan kanal üzerinden loglar."""
    if LOG_WEBHOOK_URL:
        try:
            payload = {
                "embeds": [{
                    "title": "📜 Sorgu Logu",
                    "description": f"**Komut:** `/{command_name}`\n**Hedef/Parametre:** `{target_info}`",
                    "color": 3092790,
                    "fields": [
                        {"name": "Kullanıcı", "value": f"{interaction.user} (`{interaction.user.id}`)", "inline": True},
                        {"name": "Konum/Sunucu", "value": interaction.guild.name if interaction.guild else "Özel Mesaj / Grup", "inline": True}
                    ],
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }]
            }
            async with bot.http_session.post(LOG_WEBHOOK_URL, json=payload) as resp:
                if resp.status in (200, 204):
                    return
        except Exception as e:
            print("Webhook log hatası:", repr(e))

    if LOG_CHANNEL_ID:
        try:
            channel = bot.get_channel(LOG_CHANNEL_ID)
            if not channel:
                channel = await bot.fetch_channel(LOG_CHANNEL_ID)
            if channel:
                embed = embed_base("📜 Sorgu Logu", f"**Komut:** `/{command_name}`\n**Hedef/Parametre:** `{target_info}`")
                embed.add_field(name="Kullanıcı", value=f"{interaction.user} (`{interaction.user.id}`)", inline=True)
                embed.add_field(name="Konum/Sunucu", value=interaction.guild.name if interaction.guild else "Özel Mesaj / Grup", inline=True)
                await channel.send(embed=embed)
        except Exception as e:
            print("Kanal log gönderme hatası:", repr(e))


async def aget_json(url, params=None, headers=None, timeout=12):
    async with bot.http_session.get(
        url,
        params=params,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=timeout)
    ) as resp:
        if resp.status == 404:
            return None
        resp.raise_for_status()
        return await resp.json(content_type=None)


# ---------- Cooldown / hata yönetimi ----------

@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Çok hızlısın. {error.retry_after:.0f} sn sonra tekrar dene."
    else:
        print("TREE ERROR:", type(error).__name__, str(error)[:300])
        msg = "Komut çalıştırılırken hata oluştu."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


@bot.event
async def on_ready():
    print(f"NULLL INTELLIGENCE aktif: {bot.user} ({bot.user.id})")


# ==================== YETKİLENDİRME KOMUTLARI (SAHİP ÖZEL) ====================

@bot.tree.command(name="yetki-ver", description="[Yalnızca Bot Sahibi] Belirtilen kullanıcıya bot kullanım yetkisi verir")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Yetki verilecek kullanıcı")
async def yetki_ver(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Bu komutu sadece bot sahibi kullanabilir!", ephemeral=True)
        return

    auth_users = load_auth()
    if user.id in auth_users:
        await interaction.response.send_message(f"{user.mention} zaten yetkiye sahip!", ephemeral=True)
        return

    auth_users.append(user.id)
    save_auth(auth_users)

    embed = embed_base("✅ Yetki Verildi", f"**Kullanıcı:** {user.mention} (`{user.id}`)")
    footer(embed, interaction)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="yetki-al", description="[Yalnızca Bot Sahibi] Kullanıcının bot kullanım yetkisini alır")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Yetkisi alınacak kullanıcı")
async def yetki_al(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Bu komutu sadece bot sahibi kullanabilir!", ephemeral=True)
        return

    auth_users = load_auth()
    if user.id not in auth_users:
        await interaction.response.send_message(f"{user.mention} zaten yetkili değil!", ephemeral=True)
        return

    auth_users.remove(user.id)
    save_auth(auth_users)

    embed = embed_base("❌ Yetki Alındı", f"**Kullanıcı:** {user.mention} (`{user.id}`)")
    footer(embed, interaction)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== 1. EMAIL OSINT (HUDSON ROCK & XPOSEDORNOT) ====================

@bot.tree.command(name="email-osint", description="E-posta için Hudson Rock stealer ve ihlal taraması")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.checks.cooldown(1, 10.0)
async def email_osint(interaction: discord.Interaction, email: str):
    if not await check_access(interaction):
        await interaction.response.send_message("Bu botu kullanabilmek için bot sahibinden yetki almalısın!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    email = email.strip().lower()
    await send_log(interaction, "email-osint", email)

    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        await interaction.followup.send("Geçerli bir e-posta adresi gir.", ephemeral=True)
        return

    output_file = f"result_{interaction.user.id}.json"

    try:
        hudson_res = await hudson_rock_search("search-by-email", "email", email)
        xon_res = await xposed_or_not_search(email)

        data = {"target": email, "stealer_logs": {}, "breaches": []}
        
        if hudson_res and isinstance(hudson_res, dict) and hudson_res.get("stealers"):
            data["stealer_logs"] = hudson_res["stealers"][0]

        if xon_res and isinstance(xon_res, dict) and "exposed_breaches" in xon_res:
            breaches_det = xon_res["exposed_breaches"].get("breaches_details", [])
            data["breaches"] = [b.get("breach") for b in breaches_det if isinstance(b, dict)]

        embed = embed_base("📧 NULLL INTELLIGENCE | Email OSINT Report", f"**Hedef e-posta:** `{email}`")
        embed.set_thumbnail(url=get_gravatar_url(email))

        stealer = data.get("stealer_logs", {})
        if stealer:
            embed.add_field(
                name="💻 Hudson Rock Stealer Log Bilgisi",
                value=f"• **Bilgisayar:** `{stealer.get('computer_name', 'Bilinmiyor')}`\n• **IP:** `{stealer.get('ip', 'Bilinmiyor')}`\n• **Tarih:** `{stealer.get('date', 'Bilinmiyor')}`",
                inline=False
            )
        else:
            embed.add_field(name="💻 Hudson Rock Stealer", value="Kayıt bulunamadı.", inline=False)

        breaches = data.get("breaches", [])
        if breaches:
            embed.add_field(name=f"⚠️ İhlaller ({len(breaches)})", value=", ".join(breaches[:10]), inline=False)

        footer(embed, interaction)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        file_obj = discord.File(output_file, filename=f"{email.split('@')[0]}_osint.json")
        await interaction.followup.send(embed=embed, file=file_obj, ephemeral=True)

    except Exception as exc:
        print("EMAIL OSINT ERROR:", repr(exc))
        await interaction.followup.send("E-posta OSINT analizi sırasında bir hata oluştu.", ephemeral=True)
    finally:
        if os.path.exists(output_file):
            os.remove(output_file)


# ==================== 2. IP LOOKUP (IP-API OPTIMIZE & SHODAN & ABUSEIPDB) ====================

@bot.tree.command(name="ip-lookup", description="Genel IP bilgileri, açık portlar ve itibar")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.checks.cooldown(1, 10.0)
async def ip_lookup(interaction: discord.Interaction, ip_address: str):
    if not await check_access(interaction):
        await interaction.response.send_message("Bu botu kullanabilmek için bot sahibinden yetki almalısın!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await send_log(interaction, "ip-lookup", ip_address)

    try:
        ip = ipaddress.ip_address(ip_address.strip())
    except ValueError:
        await interaction.followup.send("Geçersiz IP.", ephemeral=True)
        return

    if not ip.is_global:
        await interaction.followup.send("Genel bir IP adresi gir.", ephemeral=True)
        return

    try:
        geo_task = ip_geolocation(str(ip))
        idb_task = aget_json(f"https://internetdb.shodan.io/{ip}")
        abuse_task = None
        if ABUSEIPDB_KEY:
            abuse_task = aget_json(
                "https://api.abuseipdb.com/api/v2/check",
                params={"ipAddress": str(ip), "maxAgeInDays": 90},
                headers={"Key": ABUSEIPDB_KEY, "Accept": "application/json"}
            )

        tasks = [geo_task, idb_task] + ([abuse_task] if abuse_task else [])
        results = await asyncio.gather(*tasks, return_exceptions=True)

        geo = results[0] if isinstance(results[0], dict) else None
        idb = results[1] if isinstance(results[1], dict) else None
        abuse = None
        if abuse_task and isinstance(results[2], dict):
            abuse = results[2].get("data")

        if not geo or geo.get("status") != "success":
            await interaction.followup.send("IP bulunamadı.", ephemeral=True)
            return

        embed = embed_base("🌐 NULLL INTELLIGENCE | IP Analysis", f"**IP:** `{ip}`")
        embed.add_field(name="Ülke", value=str(geo.get("country")), inline=True)
        embed.add_field(name="Şehir", value=str(geo.get("city")), inline=True)
        embed.add_field(name="ISP", value=str(geo.get("isp")), inline=True)
        embed.add_field(name="Organizasyon", value=str(geo.get("org")), inline=True)
        embed.add_field(name="AS", value=str(geo.get("as")), inline=True)
        embed.add_field(name="Mobil mi?", value="Evet" if geo.get("mobile") else "Hayır", inline=True)
        embed.add_field(name="Proxy/VPN?", value="Evet" if geo.get("proxy") else "Hayır", inline=True)

        if idb:
            ports = idb.get("ports") or []
            vulns = idb.get("vulns") or []
            embed.add_field(name="Açık Portlar (Shodan)", value=(", ".join(map(str, ports[:25])) or "Yok")[:1000], inline=False)
            if vulns:
                embed.add_field(name="Bilinen CVE'ler", value=", ".join(vulns[:10])[:1000], inline=False)

        if abuse:
            score = abuse.get("abuseConfidenceScore", 0)
            embed.add_field(name="AbuseIPDB Skoru", value=f"**{score}/100** (Rapor: {abuse.get('totalReports', 0)})", inline=False)

        footer(embed, interaction)
        await interaction.followup.send(embed=embed)
    except Exception as exc:
        print("IP LOOKUP ERROR:", repr(exc))
        await interaction.followup.send("IP sorgusu başarısız.", ephemeral=True)


# ==================== 3. PHONE LOOKUP ====================

PHONE_TYPES = {
    phonenumbers.PhoneNumberType.MOBILE: "Mobil",
    phonenumbers.PhoneNumberType.FIXED_LINE: "Sabit Hat",
    phonenumbers.PhoneNumberType.VOIP: "VoIP",
    phonenumbers.PhoneNumberType.UNKNOWN: "Bilinmiyor"
}


@bot.tree.command(name="phone-sorgu", description="Telefon numarası doğrulama ve operatör sorgusu")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.checks.cooldown(1, 5.0)
async def phone_lookup(interaction: discord.Interaction, phone_number: str):
    if not await check_access(interaction):
        await interaction.response.send_message("Bu botu kullanabilmek için bot sahibinden yetki almalısın!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await send_log(interaction, "phone-sorgu", phone_number)

    raw = phone_number.strip()
    if not raw.startswith("+"):
        raw = "+" + "".join(c for c in raw if c.isdigit())

    try:
        num = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException:
        await interaction.followup.send("Numara ayrıştırılamadı. Ülke koduyla gir (örn: +905xxxxxxxxx).", ephemeral=True)
        return

    valid = phonenumbers.is_valid_number(num)
    embed = embed_base("📱 NULLL INTELLIGENCE | Phone Lookup", color=discord.Color.green() if valid else discord.Color.orange())
    embed.add_field(name="Format", value=f"`{phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)}`", inline=True)
    embed.add_field(name="Geçerli mi?", value="Evet" if valid else "Hayır", inline=True)
    embed.add_field(name="Ülke Kodu", value=f"+{num.country_code}", inline=True)
    embed.add_field(name="Hat Türü", value=PHONE_TYPES.get(phonenumbers.number_type(num), "Diğer"), inline=True)
    embed.add_field(name="Bölge", value=geocoder.description_for_number(num, "tr") or "Bilinmiyor", inline=True)
    embed.add_field(name="Operatör", value=carrier.name_for_number(num, "tr") or "Bilinmiyor", inline=True)

    footer(embed, interaction)
    await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== 4. DOMAIN (RDAP) ====================

@bot.tree.command(name="domain-sorgu", description="Domain kayıt bilgisi (RDAP)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.checks.cooldown(1, 10.0)
async def domain_lookup(interaction: discord.Interaction, domain_name: str):
    if not await check_access(interaction):
        await interaction.response.send_message("Bu botu kullanabilmek için bot sahibinden yetki almalısın!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await send_log(interaction, "domain-sorgu", domain_name)
    
    domain_name = domain_name.strip().lower()
    try:
        data = await aget_json(f"https://rdap.org/domain/{domain_name}", timeout=15)
        if not data:
            await interaction.followup.send("Domain bulunamadı.", ephemeral=True)
            return
        embed = embed_base("🌐 Domain (RDAP)", f"Domain: `{domain_name}`")
        footer(embed, interaction)
        await interaction.followup.send(embed=embed)
    except:
        await interaction.followup.send("Sorgu başarısız.", ephemeral=True)


# ==================== STARTUP ====================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN bulunamadı!")
    keep_alive()
    bot.run(TOKEN)
