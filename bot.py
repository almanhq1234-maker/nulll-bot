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
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")
ABUSEIPDB_KEY = os.getenv("ABUSEIPDB_KEY", "")  # opsiyonel

COLOR = discord.Color.from_rgb(47, 49, 54)

# Eski senkron istemci: e-posta modülleri için.
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


async def get_json(url, params=None, headers=None, timeout=12):
    def request():
        response = SESSION.get(
            url, params=params, headers=headers, timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    return await asyncio.to_thread(request)


async def aget_json(url, params=None, headers=None, timeout=12):
    """aiohttp ile JSON al. 404 durumunda None döner."""
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


# ---------- Güvenlik yardımcıları (SSRF koruması) ----------

async def resolve_public(host: str):
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("Özel/yerel IP adreslerine istek gönderilemez.")
        return [str(ip)]
    except ValueError as exc:
        if "istek gönderilemez" in str(exc):
            raise

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("Domain çözümlenemedi.")

    ips = list({i[4][0] for i in infos})
    if not ips:
        raise ValueError("Domain çözümlenemedi.")

    for item in ips:
        if not ipaddress.ip_address(item.split("%")[0]).is_global:
            raise ValueError("Hedef özel/yerel bir adrese çözülüyor.")
    return ips


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


# ==================== EMAIL BREACH (Sızıntı Analizi) ====================

def parse_names(data):
    result = []

    def walk(value):
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for key in ("breach", "breachName", "breachID", "name"):
                if isinstance(value.get(key), str):
                    result.append(value[key])
                    return
            for key in ("breaches", "breaches_details", "exposedBreaches"):
                if key in value:
                    walk(value[key])

    walk(data)
    return list(dict.fromkeys(result))


def parse_records(data):
    records = []

    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            if any(
                key in value for key in (
                    "exposedData", "exposed_data", "xposed_data",
                    "breachedDate", "breached_date", "dataClasses"
                )
            ):
                records.append(value)

            for key in (
                "ExposedBreaches", "exposedBreaches",
                "breaches_details", "breaches"
            ):
                if key in value:
                    walk(value[key])

    walk(data)
    return records


@bot.tree.command(
    name="email-sızıntı",
    description="E-posta veri ihlali ve sızıntı kaynağı kontrolü"
)
@app_commands.checks.cooldown(1, 10.0)
async def email_leak(interaction: discord.Interaction, email: str):
    await interaction.response.defer(ephemeral=True)

    email = email.strip().lower()

    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ):
        await interaction.followup.send(
            "Geçerli bir e-posta adresi gir.",
            ephemeral=True
        )
        return

    try:
        analytics = {}
        analytics_error = None

        try:
            analytics = await get_json(
                "https://api.xposedornot.com/v1/breach-analytics",
                params={"email": email}
            )
        except requests.HTTPError as exc:
            analytics_error = (
                exc.response.status_code if exc.response else 0
            )
        except Exception as exc:
            print("XON analytics:", type(exc).__name__, str(exc)[:300])
            analytics_error = 0

        records = parse_records(analytics) if analytics else []
        names = parse_names(analytics) if analytics else []

        basic_error = None
        if not names and not records:
            try:
                basic = await get_json(
                    "https://api.xposedornot.com/v1/check-email/"
                    + urllib.parse.quote(email, safe="")
                )
                names = parse_names(basic)
            except requests.HTTPError as exc:
                basic_error = (
                    exc.response.status_code if exc.response else 0
                )
            except Exception as exc:
                print("XON basic:", type(exc).__name__, str(exc)[:300])
                basic_error = 0

        hibp_error = None
        hibp_records = []

        if HIBP_API_KEY:
            try:
                hibp_records = await get_json(
                    "https://haveibeenpwned.com/api/v3/breachedaccount/"
                    + urllib.parse.quote(email, safe=""),
                    params={"truncateResponse": "false"},
                    headers={
                        "hibp-api-key": HIBP_API_KEY,
                        "Accept": "application/json",
                        "User-Agent": "NULLL-INTELLIGENCE"
                    }
                )

                if not isinstance(hibp_records, list):
                    hibp_records = []

            except requests.HTTPError as exc:
                hibp_error = (
                    exc.response.status_code if exc.response else 0
                )
            except Exception as exc:
                print("HIBP:", type(exc).__name__, str(exc)[:300])
                hibp_error = 0

        embed = embed_base(
            "📧 NULLL INTELLIGENCE | Email Breach Analysis",
            f"**Sorgulanan e-posta:** `{email}`"
        )

        for record in hibp_records:
            if isinstance(record, dict):
                hibp_name = record.get("Name", "Bilinmeyen ihlal")
                names.append(str(hibp_name))

                data_classes = record.get("DataClasses", [])
                records.append({
                    "breach": hibp_name,
                    "breachedDate": record.get("BreachDate"),
                    "exposedData": data_classes,
                    "domain": record.get("Domain"),
                    "description": record.get("Description"),
                    "isVerified": record.get("IsVerified")
                })

        names = list(dict.fromkeys(names))

        if not names and not records:
            if (
                analytics_error == 429
                or basic_error == 429
                or hibp_error == 429
            ):
                embed.color = discord.Color.orange()
                embed.add_field(
                    name="API sınırı",
                    value="İstek sınırına ulaşıldı. Bir süre sonra tekrar dene.",
                    inline=False
                )
            elif (
                analytics_error is not None
                or basic_error is not None
                or hibp_error is not None
            ):
                embed.color = discord.Color.orange()
                embed.add_field(
                    name="API yanıtı",
                    value=(
                        "Servislerden biri sonuç veremedi. Bu durum "
                        "e-postanın temiz olduğu anlamına gelmez."
                    ),
                    inline=False
                )
            else:
                embed.color = discord.Color.green()
                embed.add_field(
                    name="Sonuç",
                    value=(
                        "Kontrol edilen kaynaklarda bilinen ihlal "
                        "bulunamadı. Bu, kesin olarak sızıntı yok "
                        "demek değildir."
                    ),
                    inline=False
                )
        else:
            embed.color = discord.Color.red()
            embed.add_field(
                name="Bulunan ihlal sayısı",
                value=f"`{len(names) if names else len(records)}`",
                inline=False
            )

            by_name = {}

            for record in records:
                name = str(
                    record.get("breach")
                    or record.get("breachName")
                    or record.get("breachID")
                    or record.get("name")
                    or "Bilinmeyen ihlal"
                )
                by_name[name] = record

            for name in names:
                by_name.setdefault(name, {})

            if not by_name:
                by_name["Bilinmeyen ihlal"] = {}

            for name, record in list(by_name.items())[:10]:
                date = (
                    record.get("breachedDate")
                    or record.get("breached_date")
                    or record.get("BreachDate")
                    or record.get("date")
                    or "API yanıtında yok"
                )

                exposed = (
                    record.get("exposedData")
                    or record.get("exposed_data")
                    or record.get("xposed_data")
                    or record.get("dataClasses")
                    or record.get("DataClasses")
                    or []
                )

                if isinstance(exposed, str):
                    exposed = [x.strip() for x in re.split(r"[,;|]", exposed)]

                if not isinstance(exposed, list):
                    exposed = []

                details = [
                    f"**Tarih:** {str(date)[:100]}",
                    "**Veri türleri:** " + (
                        ", ".join(str(x) for x in exposed[:15])
                        if exposed else "API yanıtında bulunmuyor"
                    )
                ]

                domain = record.get("domain") or record.get("Domain")
                if domain:
                    details.append(f"**Domain:** {str(domain)[:150]}")

                description = (
                    record.get("description")
                    or record.get("Description")
                )
                if description:
                    description = re.sub(
                        r"<[^>]*>", " ", str(description)
                    )
                    details.append(
                        f"**Açıklama:** {description[:250]}"
                    )

                verified = record.get("isVerified")
                if verified is not None:
                    details.append(
                        "**Doğrulanmış ihlal:** "
                        + ("Evet" if verified else "Hayır")
                    )

                embed.add_field(
                    name=name[:250],
                    value="\n".join(details)[:1024],
                    inline=False
                )

        embed.add_field(
            name="Gizlilik notu",
            value=(
                "Bu rapor ihlal kaynaklarını ve servislerin sağladığı "
                "metadata bilgilerini gösterir; sızdırılmış parolaları "
                "ve özel kayıtların içeriklerini göstermez."
            ),
            inline=False
        )

        footer(embed, interaction)
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as exc:
        print("EMAIL ERROR:", type(exc).__name__, str(exc)[:500])
        await interaction.followup.send(
            "E-posta analizi başarısız oldu. Render loglarını kontrol et.",
            ephemeral=True
        )


# ==================== EMAILFINDER (Domain Bazlı E-Posta Arama) ====================

def filter_emails(email_list):
    return [email for email in email_list if not (email.startswith('u0027@') or email.startswith('22@'))]

async def loading_bar(interaction):
    stages = [
        "🔄 E-postalar taranıyor [▒▒▒▒▒▒▒▒▒▒] 0%",
        "🔄 E-postalar taranıyor [█▒▒▒▒▒▒▒▒▒] 10%",
        "🔄 E-postalar taranıyor [██▒▒▒▒▒▒▒▒] 20%",
        "🔄 E-postalar taranıyor [███▒▒▒▒▒▒▒] 30%",
        "🔄 E-postalar taranıyor [████▒▒▒▒▒▒] 40%",
        "🔄 E-postalar taranıyor [█████▒▒▒▒▒] 50%",
        "🔄 E-postalar taranıyor [██████▒▒▒▒] 60%",
        "🔄 E-postalar taranıyor [███████▒▒▒] 70%",
        "🔄 E-postalar taranıyor [████████▒▒] 80%",
        "🔄 E-postalar taranıyor [█████████▒] 90%",
        "🔄 E-postalar taranıyor [██████████] 100%",
    ]
    for stage in stages:
        try:
            await interaction.edit_original_response(content=stage)
        except Exception:
            pass
        await asyncio.sleep(0.4)

@bot.tree.command(name="emailfinder", description="Belirtilen domain ile ilişkili açık e-postaları ara")
@app_commands.checks.cooldown(1, 15.0)
async def emailfinder(interaction: discord.Interaction, domain: str):
    if bot.is_processing:
        await interaction.response.send_message("Bot şu an başka bir tarama yürütüyor. Lütfen bekleyin.", ephemeral=True)
        return

    domain = domain.strip().lower()
    if not DOMAIN_RE.fullmatch(domain):
        await interaction.response.send_message("Geçerli bir domain adı gir.", ephemeral=True)
        return

    bot.is_processing = True

    try:
        await interaction.response.defer(ephemeral=True)
        await loading_bar(interaction)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(['emailfinder', '-d', domain], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        )

        if result.returncode == 0:
            emails = re.findall(r'[\w\.-]+@[\w\.-]+', result.stdout)
            filtered_emails = filter_emails(emails)

            if filtered_emails:
                total_emails = len(filtered_emails)
                email_list_message = '\n'.join(filtered_emails)
                final_message = f'**Bulunan e-posta sayısı (filtrelenmiş): {total_emails}**'

                if len(email_list_message) > 1800:
                    file_io = io.StringIO(email_list_message)
                    await interaction.edit_original_response(content=f'{final_message}\nSonuçlar çok uzun olduğu için dosya olarak gönderildi.')
                    await interaction.followup.send(file=discord.File(file_io, filename=f'{domain}_emails.txt'), ephemeral=True)
                else:
                    await interaction.edit_original_response(content=f'{final_message}\n```text\n{email_list_message}\n```')
            else:
                await interaction.edit_original_response(content='Belirtilen domain için geçerli e-posta bulunamadı.')
        else:
            stderr_msg = result.stderr.strip() or "Bilinmeyen hata"
            await interaction.edit_original_response(content=f'Tarama hatası: `{stderr_msg[:500]}`')

    except Exception as e:
        print("emailfinder hatası:", repr(e))
        await interaction.edit_original_response(content='E-posta arama işlemi sırasında bir hata oluştu.')

    finally:
        bot.is_processing = False


# ==================== DISCORD USER ====================

@bot.tree.command(name="ara", description="Discord hesap bilgileri")
@app_commands.checks.cooldown(1, 5.0)
async def ara(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(ephemeral=True)

    try:
        if not user_id.isdigit():
            await interaction.followup.send("Geçersiz ID.", ephemeral=True)
            return

        user = await bot.fetch_user(int(user_id))
        embed = embed_base("🛡️ NULLL INTELLIGENCE | Discord Lookup")

        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Kullanıcı", value=user.name, inline=True)
        embed.add_field(name="ID", value=str(user.id), inline=True)
        embed.add_field(
            name="Bot mu?",
            value="Evet" if user.bot else "Hayır",
            inline=True
        )
        embed.add_field(
            name="Oluşturulma",
            value=user.created_at.strftime("%d.%m.%Y %H:%M UTC"),
            inline=False
        )

        if user.banner:
            embed.set_image(url=user.banner.url)

        footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except discord.NotFound:
        await interaction.followup.send("Kullanıcı bulunamadı.", ephemeral=True)
    except Exception as exc:
        print("ARA:", repr(exc))
        await interaction.followup.send("Sorgu başarısız.", ephemeral=True)


# ==================== IP LOOKUP ====================

@bot.tree.command(
    name="ip-lookup",
    description="Genel IP bilgileri, açık portlar ve itibar"
)
@app_commands.checks.cooldown(1, 10.0)
async def ip_lookup(interaction: discord.Interaction, ip_address: str):
    await interaction.response.defer(ephemeral=True)

    try:
        ip = ipaddress.ip_address(ip_address.strip())
    except ValueError:
        await interaction.followup.send("Geçersiz IP.", ephemeral=True)
        return

    if not ip.is_global:
        await interaction.followup.send("Genel bir IP adresi gir.", ephemeral=True)
        return

    try:
        geo_task = aget_json(f"https://ipwho.is/{ip}")
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

        if not geo or not geo.get("success"):
            await interaction.followup.send("IP bulunamadı.", ephemeral=True)
            return

        conn = geo.get("connection") or {}
        tz = geo.get("timezone") or {}
        sec = geo.get("security") or {}

        embed = embed_base(
            "🌐 NULLL INTELLIGENCE | IP Analysis",
            f"**IP:** `{ip}`"
        )

        rows = [
            ("Ülke", geo.get("country")),
            ("Bölge", geo.get("region")),
            ("Şehir", geo.get("city")),
            ("Posta kodu", geo.get("postal")),
            ("Zaman dilimi", tz.get("id")),
            ("ISP", conn.get("isp")),
            ("Organizasyon", conn.get("org")),
            ("ASN", conn.get("asn")),
        ]
        for label, value in rows:
            embed.add_field(
                name=label,
                value=str(value or "Bilinmiyor")[:200],
                inline=True
            )

        if sec:
            flags = [
                k.upper() for k in ("proxy", "vpn", "tor", "hosting")
                if sec.get(k)
            ]
            embed.add_field(
                name="Sinyaller",
                value=", ".join(flags) if flags else "Yok",
                inline=True
            )

        if idb:
            ports = idb.get("ports") or []
            vulns = idb.get("vulns") or []
            tags = idb.get("tags") or []
            hostnames = idb.get("hostnames") or []

            embed.add_field(
                name="Açık portlar (Shodan InternetDB)",
                value=(", ".join(map(str, ports[:30])) or "Yok")[:1000],
                inline=False
            )
            if vulns:
                embed.add_field(
                    name=f"Bilinen CVE ({len(vulns)})",
                    value=", ".join(vulns[:15])[:1000],
                    inline=False
                )
            if tags:
                embed.add_field(
                    name="Etiketler",
                    value=", ".join(tags)[:500],
                    inline=True
                )
            if hostnames:
                embed.add_field(
                    name="Hostname",
                    value=", ".join(hostnames[:5])[:500],
                    inline=True
                )

        if abuse:
            score = abuse.get("abuseConfidenceScore", 0)
            embed.add_field(
                name="AbuseIPDB",
                value=(
                    f"Skor: **{score}/100**\n"
                    f"Rapor sayısı (90 gün): {abuse.get('totalReports', 0)}\n"
                    f"Kullanım türü: {abuse.get('usageType') or 'Bilinmiyor'}"
                ),
                inline=False
            )
            if score >= 50:
                embed.color = discord.Color.red()
            elif score >= 10:
                embed.color = discord.Color.orange()

        lat, lon = geo.get("latitude"), geo.get("longitude")
        if lat is not None and lon is not None:
            embed.add_field(
                name="Harita",
                value=f"[Yaklaşık konumu aç](https://maps.google.com/?q={lat},{lon})",
                inline=False
            )

        footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except Exception as exc:
        print("IP:", repr(exc))
        await interaction.followup.send("IP sorgusu başarısız.", ephemeral=True)


# ==================== PHONE LOOKUP ====================

PHONE_TYPES = {
    phonenumbers.PhoneNumberType.MOBILE: "Mobil",
    phonenumbers.PhoneNumberType.FIXED_LINE: "Sabit hat",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Sabit/Mobil",
    phonenumbers.PhoneNumberType.TOLL_FREE: "Ücretsiz hat",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "Ücretli hat",
    phonenumbers.PhoneNumberType.VOIP: "VoIP",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Kişisel numara",
    phonenumbers.PhoneNumberType.PAGER: "Çağrı cihazı",
    phonenumbers.PhoneNumberType.UAN: "UAN",
    phonenumbers.PhoneNumberType.UNKNOWN: "Bilinmiyor",
}


@bot.tree.command(
    name="phone-sorgu",
    description="Telefon numarası doğrulama (ülke, hat türü, operatör)"
)
@app_commands.checks.cooldown(1, 5.0)
async def phone_lookup(interaction: discord.Interaction, phone_number: str):
    await interaction.response.defer(ephemeral=True)

    raw = phone_number.strip()
    if not raw.startswith("+"):
        raw = "+" + "".join(c for c in raw if c.isdigit())

    try:
        num = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException:
        await interaction.followup.send(
            "Numara ayrıştırılamadı. Ülke koduyla gir (örn. +905xxxxxxxxx).",
            ephemeral=True
        )
        return

    valid = phonenumbers.is_valid_number(num)
    possible = phonenumbers.is_possible_number(num)

    embed = embed_base(
        "📱 NULLL INTELLIGENCE | Phone Lookup",
        color=discord.Color.green() if valid else discord.Color.orange()
    )
    embed.add_field(
        name="Uluslararası biçim",
        value=f"`{phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)}`",
        inline=True
    )
    embed.add_field(
        name="Geçerli mi?",
        value="Evet" if valid else ("Biçim olası" if possible else "Hayır"),
        inline=True
    )
    embed.add_field(
        name="Ülke kodu",
        value=f"+{num.country_code} ({phonenumbers.region_code_for_number(num) or '?'})",
        inline=True
    )
    embed.add_field(
        name="Hat türü",
        value=PHONE_TYPES.get(phonenumbers.number_type(num), "Bilinmiyor"),
        inline=True
    )
    embed.add_field(
        name="Bölge",
        value=geocoder.description_for_number(num, "tr") or "Bilinmiyor",
        inline=True
    )
    embed.add_field(
        name="Operatör (ilk tahsis)",
        value=carrier.name_for_number(num, "tr") or "Bilinmiyor",
        inline=True
    )
    zones = pn_timezone.time_zones_for_number(num)
    embed.add_field(
        name="Zaman dilimi",
        value=", ".join(zones[:3]) if zones else "Bilinmiyor",
        inline=False
    )
    embed.add_field(
        name="Not",
        value=(
            "Operatör bilgisi numaranın ilk tahsis edildiği operatördür; "
            "numara taşıma (MNP) yapılmış olabilir."
        ),
        inline=False
    )

    footer(embed, interaction)
    await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== USERNAME SCAN ====================

WMN_URL = (
    "https://raw.githubusercontent.com/"
    "WebBreacher/WhatsMyName/main/wmn-data.json"
)
WMN_TTL = 24 * 3600
wmn_cache = None
wmn_loaded_at = 0.0
wmn_lock = asyncio.Lock()


async def load_wmn():
    global wmn_cache, wmn_loaded_at

    async with wmn_lock:
        if wmn_cache is not None and time.time() - wmn_loaded_at < WMN_TTL:
            return wmn_cache

        try:
            wmn_cache = await aget_json(WMN_URL, timeout=20)
            wmn_loaded_at = time.time()
            return wmn_cache
        except Exception as exc:
            print("WMN:", repr(exc))
            return wmn_cache


async def probe_site(session, sem, site, username):
    template = site.get("uri_check", "")
    if "{account}" not in template:
        return None
    if site.get("post_body") or site.get("valid") is False:
        return None

    url = template.replace("{account}", urllib.parse.quote(username, safe=""))

    async with sem:
        try:
            async with session.get(
                url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=7)
            ) as resp:
                raw = await resp.content.read(300_000)
                body = raw.decode("utf-8", errors="ignore")
                status = resp.status
        except Exception:
            return None

    m_code = site.get("m_code")
    m_string = site.get("m_string") or ""
    e_code = site.get("e_code")
    e_string = site.get("e_string") or ""

    if m_code is not None and status == m_code:
        return None
    if m_string and m_string in body:
        return None

    if e_code is None and not e_string:
        return None
    if e_code is not None and status != e_code:
        return None
    if e_string and e_string not in body:
        return None

    return {
        "name": site.get("name", "Unknown"),
        "url": site.get("uri_pretty", "").replace("{account}", username) or url,
        "cat": site.get("cat", "")
    }


async def scan_username(username):
    data = await load_wmn()
    if not data or not isinstance(data.get("sites"), list):
        return None, 0

    sem = asyncio.Semaphore(40)
    connector = aiohttp.TCPConnector(limit=60, ttl_dns_cache=300)

    async with aiohttp.ClientSession(headers=UA, connector=connector) as session:
        sites = data["sites"]
        results = await asyncio.gather(
            *(probe_site(session, sem, s, username) for s in sites),
            return_exceptions=True
        )

    hits = [r for r in results if isinstance(r, dict)]
    return hits, len(sites)


@bot.tree.command(name="username", description="Herkese açık profil eşleşmeleri")
@app_commands.checks.cooldown(1, 60.0)
async def username_check(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)

    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", username):
        await interaction.followup.send("Kullanıcı adı geçersiz.", ephemeral=True)
        return

    hits, total = await scan_username(username)

    if hits is None:
        await interaction.followup.send(
            "Site listesi yüklenemedi, sonra tekrar dene.", ephemeral=True
        )
        return

    embed = embed_base(
        "🔎 NULLL INTELLIGENCE | Username Scan",
        f"**Kullanıcı adı:** `{username}`\n"
        f"**Taranan site:** {total} | **Eşleşme:** {len(hits)}"
    )

    if hits:
        hits.sort(key=lambda h: (h["cat"], h["name"].lower()))
        lines = [f"[{h['name']}]({h['url']})" for h in hits]

        chunk, chunks = "", []
        for line in lines:
            if len(chunk) + len(line) + 3 > 1000:
                chunks.append(chunk)
                chunk = ""
            chunk += line + " • "
        if chunk:
            chunks.append(chunk)

        for i, text in enumerate(chunks[:5], 1):
            embed.add_field(
                name="Eşleşmeler" if i == 1 else f"Eşleşmeler ({i})",
                value=text.rstrip(" • "),
                inline=False
            )
        if len(chunks) > 5:
            embed.add_field(
                name="Not",
                value="Çok fazla eşleşme var, ilk bölüm gösterildi.",
                inline=False
            )
        embed.add_field(
            name="Uyarı",
            value="Eşleşmeler aynı kişiye ait olduğunu kanıtlamaz; yanlış pozitif olabilir.",
            inline=False
        )
    else:
        embed.add_field(
            name="Sonuç",
            value="Kontrol edilen kaynaklarda eşleşme bulunamadı.",
            inline=False
        )

    footer(embed, interaction)
    await interaction.followup.send(embed=embed)


# ==================== DOMAIN (RDAP) ====================

def rdap_event(data, action):
    for ev in data.get("events", []):
        if ev.get("eventAction") == action:
            return ev.get("eventDate", "")[:10]
    return None


def rdap_registrar(data):
    for ent in data.get("entities", []):
        if "registrar" in ent.get("roles", []):
            vcard = ent.get("vcardArray")
            if vcard and len(vcard) > 1:
                for item in vcard[1]:
                    if item[0] == "fn":
                        return item[3]
    return None


@bot.tree.command(name="domain-sorgu", description="Domain kayıt bilgisi (RDAP)")
@app_commands.checks.cooldown(1, 10.0)
async def domain_lookup(interaction: discord.Interaction, domain_name: str):
    await interaction.response.defer(ephemeral=True)

    domain_name = domain_name.strip().lower()
    if not DOMAIN_RE.fullmatch(domain_name):
        await interaction.followup.send("Domain geçersiz.", ephemeral=True)
        return

    try:
        data = await aget_json(f"https://rdap.org/domain/{domain_name}", timeout=15)
        if not data:
            await interaction.followup.send("Domain kaydı bulunamadı.", ephemeral=True)
            return

        embed = embed_base(
            "🌐 NULLL INTELLIGENCE | Domain (RDAP)",
            f"**Domain:** `{domain_name}`"
        )

        ns = [n.get("ldhName") for n in data.get("nameservers", []) if n.get("ldhName")]
        created = rdap_event(data, "registration")
        expires = rdap_event(data, "expiration")
        registrar = rdap_registrar(data)

        embed.add_field(name="Registrar", value=str(registrar or "Bilinmiyor"), inline=False)
        embed.add_field(name="Oluşturulma", value=str(created or "Bilinmiyor"), inline=True)
        embed.add_field(name="Bitiş tarihi", value=str(expires or "Bilinmiyor"), inline=True)
        embed.add_field(name="Nameservers", value=", ".join(ns[:4]) if ns else "Bilinmiyor", inline=False)

        footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except Exception as exc:
        print("RDAP ERROR:", repr(exc))
        await interaction.followup.send("Domain sorgusu başarısız oldu.", ephemeral=True)


# ==================== STARTUP ====================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN ortam değişkeni bulunamadı!")

    keep_alive()
    bot.run(TOKEN)
