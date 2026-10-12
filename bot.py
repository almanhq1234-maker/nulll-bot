
import os
import re
import ipaddress
import datetime
import urllib.parse
import asyncio
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

import requests
import whois
import discord
from discord.ext import commands
from flask import Flask


# ============================================================
# NULLL INTELLIGENCE - SECRET SERVICE AGENCY
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "NULLL INTELLIGENCE | SECRET SERVICE AGENCY - Bot aktif!"


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


def keep_alive():
    Thread(target=run_flask, daemon=True).start()


# ============================================================
# DISCORD BOT
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class NullBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash komutları senkronize edildi.")


bot = NullBot()

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")

DARK_COLOR = discord.Color.from_rgb(47, 49, 54)

IP_API_URL = "http://ip-api.com/json/{}"
XON_CHECK_URL = "https://api.xposedornot.com/v1/check-email/{}"
XON_ANALYTICS_URL = "https://api.xposedornot.com/v1/breach-analytics"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "NULLL-INTELLIGENCE/1.0"
})


def make_embed(title, description=None, color=DARK_COLOR):
    return discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )


def add_footer(embed, interaction):
    embed.set_footer(
        text=f"Sorgulayan: {interaction.user.name} | NULLL INTELLIGENCE",
        icon_url=interaction.user.display_avatar.url
    )


async def run_request(url, params=None, headers=None, timeout=12):
    loop = asyncio.get_running_loop()

    def request():
        response = SESSION.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    return await loop.run_in_executor(None, request)


@bot.event
async def on_ready():
    print("-----------------------------------------")
    print(f"NULLL INTELLIGENCE aktif: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("-----------------------------------------")


# ============================================================
# 1. DISCORD USER LOOKUP
# ============================================================

@bot.tree.command(
    name="ara",
    description="Discord hesabının herkese açık temel bilgilerini göster"
)
async def ara(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer()

    try:
        if not user_id.isdigit():
            await interaction.followup.send(
                "Geçerli bir Discord ID gir.",
                ephemeral=True
            )
            return

        user = await bot.fetch_user(int(user_id))

        created_at = user.created_at.strftime(
            "%d.%m.%Y %H:%M:%S UTC"
        )

        embed = make_embed(
            "🛡️ NULLL INTELLIGENCE | Discord Account",
            f"**Kullanıcı:** `{user.name}`"
        )

        embed.set_thumbnail(
            url=user.display_avatar.url
        )

        embed.add_field(
            name="Kullanıcı adı",
            value=f"`{user.name}`",
            inline=True
        )
        embed.add_field(
            name="Bot mu?",
            value="Evet" if user.bot else "Hayır",
            inline=True
        )
        embed.add_field(
            name="Discord ID",
            value=f"`{user.id}`",
            inline=False
        )
        embed.add_field(
            name="Hesap oluşturulma tarihi",
            value=f"`{created_at}`",
            inline=False
        )

        add_footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except discord.NotFound:
        await interaction.followup.send(
            "Discord kullanıcısı bulunamadı.",
            ephemeral=True
        )
    except Exception as exc:
        print("ara hatası:", repr(exc))
        await interaction.followup.send(
            "Sorgu başarısız oldu.",
            ephemeral=True
        )


# ============================================================
# 2. PUBLIC IP LOOKUP
# ============================================================

@bot.tree.command(
    name="ip-lookup",
    description="Genel IP adresi için ağ ve yaklaşık konum bilgisi"
)
async def ip_lookup(interaction: discord.Interaction, ip_address: str):
    await interaction.response.defer(ephemeral=True)

    try:
        address = ipaddress.ip_address(ip_address.strip())

        if not address.is_global:
            await interaction.followup.send(
                "Yalnızca genel, internete yönlendirilebilir IP adresleri sorgulanabilir.",
                ephemeral=True
            )
            return

        data = await run_request(
            IP_API_URL.format(str(address)),
            params={"fields": (
                "status,message,continent,country,countryCode,"
                "regionName,city,zip,lat,lon,timezone,isp,org,as,proxy"
            )}
        )

        if data.get("status") != "success":
            await interaction.followup.send(
                "IP adresi için bilgi bulunamadı.",
                ephemeral=True
            )
            return

        embed = make_embed(
            "🌐 NULLL INTELLIGENCE | IP Analysis",
            f"**IP adresi:** `{address}`"
        )

        fields = [
            ("Kıta", data.get("continent")),
            ("Ülke", data.get("country")),
            ("Bölge", data.get("regionName")),
            ("Şehir", data.get("city")),
            ("Posta kodu", data.get("zip")),
            ("Zaman dilimi", data.get("timezone")),
            ("ISP", data.get("isp")),
            ("Organizasyon", data.get("org")),
            ("AS", data.get("as")),
            ("Proxy/VPN sinyali", data.get("proxy")),
        ]

        for name, value in fields:
            embed.add_field(
                name=name,
                value=f"`{str(value or 'Bilinmiyor')[:200]}`",
                inline=True
            )

        lat = data.get("lat")
        lon = data.get("lon")

        if lat is not None and lon is not None:
            maps_url = (
                "https://www.google.com/maps/search/?api=1&query="
                f"{lat},{lon}"
            )
            embed.add_field(
                name="Harita",
                value=f"[Yaklaşık konumu aç]({maps_url})",
                inline=False
            )

        embed.set_footer(
            text="IP konumları yaklaşık değerlerdir; VPN tespiti kesin değildir."
        )
        await interaction.followup.send(embed=embed)

    except ValueError:
        await interaction.followup.send(
            "Geçerli bir IPv4 veya IPv6 adresi gir.",
            ephemeral=True
        )
    except Exception as exc:
        print("ip-lookup hatası:", repr(exc))
        await interaction.followup.send(
            "IP sorgusu başarısız oldu.",
            ephemeral=True
        )


# ============================================================
# 3. EMAIL BREACH ANALYSIS
# ============================================================

def normalize_breach_names(data):
    """XposedOrNot temel kontrol yanıtındaki ihlal adlarını ayıklar."""
    names = data.get("breaches", [])

    if not isinstance(names, list):
        return []

    result = []

    for item in names:
        if isinstance(item, list):
            result.extend(str(x) for x in item)
        elif isinstance(item, str):
            result.append(item)

    return list(dict.fromkeys(result))


def get_breach_records(data):
    """Analitik yanıtındaki ihlal kayıtlarını farklı biçimlerde okur."""
    records = data.get("ExposedBreaches")

    if isinstance(records, dict):
        records = (
            records.get("breaches")
            or records.get("exposedBreaches")
            or []
        )

    if not isinstance(records, list):
        records = data.get("exposedBreaches", [])

    if isinstance(records, dict):
        records = list(records.values())

    if not isinstance(records, list):
        return []

    return [item for item in records if isinstance(item, dict)]


def get_breach_summary_names(data):
    summary = data.get("BreachesSummary", {})

    if isinstance(summary, dict):
        details = summary.get("breaches_details", [])

        if isinstance(details, list):
            names = []

            for item in details:
                if isinstance(item, dict):
                    name = (
                        item.get("breach")
                        or item.get("breachName")
                        or item.get("name")
                    )
                    if name:
                        names.append(str(name))
                elif isinstance(item, str):
                    names.append(item)

            if names:
                return names

    return []


@bot.tree.command(
    name="email-sızıntı",
    description="E-posta için bilinen veri ihlallerini ve veri türlerini kontrol et"
)
async def email_leak(interaction: discord.Interaction, email: str):
    await interaction.response.defer(ephemeral=True)

    email = email.strip().lower()

    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ):
        await interaction.followup.send(
            "Geçerli bir e-posta adresi gir.",
            ephemeral=True
        )
        return

    try:
        # Önce ayrıntılı ücretsiz analiz
        analytics = await run_request(
            XON_ANALYTICS_URL,
            params={"email": email}
        )

        records = get_breach_records(analytics)

        names = get_breach_summary_names(analytics)

        # Analitik yanıtı isim içeriyorsa temel sonuçları da sakla
        if not names:
            names = [
                str(
                    record.get("breach")
                    or record.get("breachName")
                    or record.get("breachID")
                    or record.get("name")
                    or "Bilinmeyen ihlal"
                )
                for record in records
            ]

        # Analitik kayıt sağlamadıysa temel e-posta kontrolü
        if not names and not records:
            check_url = XON_CHECK_URL.format(
                urllib.parse.quote(email, safe="")
            )

            check_data = await run_request(check_url)
            names = normalize_breach_names(check_data)

        embed = make_embed(
            "📧 NULLL INTELLIGENCE | Email Breach Analysis",
            f"**Sorgulanan e-posta:** `{email}`"
        )

        if not names and not records:
            embed.color = discord.Color.green()
            embed.add_field(
                name="Sonuç",
                value=(
                    "Bilinen bir ihlal bulunamadı. Bu sonuç, "
                    "e-postanın hiçbir veri ihlalinde yer almadığını "
                    "kesin olarak kanıtlamaz."
                ),
                inline=False
            )
        else:
            embed.color = discord.Color.red()

            embed.add_field(
                name="Bulunan ihlal sayısı",
                value=f"`{len(set(names)) if names else len(records)}`",
                inline=True
            )

            # Ayrıntılı API kayıtlarını göster
            if records:
                for record in records[:8]:
                    name = (
                        record.get("breach")
                        or record.get("breachName")
                        or record.get("breachID")
                        or record.get("name")
                        or "Bilinmeyen ihlal"
                    )

                    date = (
                        record.get("breachedDate")
                        or record.get("breached_date")
                        or record.get("date")
                        or record.get("year")
                        or "Bilinmiyor"
                    )

                    exposed = (
                        record.get("exposedData")
                        or record.get("exposed_data")
                        or record.get("xposed_data")
                        or record.get("dataClasses")
                        or []
                    )

                    if isinstance(exposed, str):
                        exposed = re.split(r"[;,|]", exposed)

                    if not isinstance(exposed, list):
                        exposed = []

                    domain = record.get("domain", "")
                    industry = record.get("industry", "")
                    risk = (
                        record.get("risk")
                        or record.get("riskLevel")
                        or record.get("risk_level")
                        or "Belirtilmemiş"
                    )
                    description = record.get("description", "")
                    count = (
                        record.get("exposedRecords")
                        or record.get("exposed_records")
                        or record.get("records")
                    )

                    details = [
                        f"**İhlal tarihi:** {str(date)[:100]}",
                        "**Veri türleri:** " + (
                            ", ".join(str(x) for x in exposed[:10])
                            if exposed
                            else "API bu kayıtta belirtmiyor"
                        ),
                        f"**Risk:** {str(risk)[:80]}"
                    ]

                    if domain:
                        details.append(f"**Domain:** {str(domain)[:120]}")

                    if industry:
                        details.append(
                            f"**Sektör:** {str(industry)[:100]}"
                        )

                    if count is not None:
                        details.append(
                            f"**İhlaldeki kayıt sayısı:** {str(count)[:50]}"
                        )

                    if description:
                        details.append(
                            f"**Açıklama:** {str(description)[:250]}"
                        )

                    embed.add_field(
                        name=str(name)[:250],
                        value="\n".join(details)[:1024],
                        inline=False
                    )

                if len(records) > 8:
                    embed.add_field(
                        name="Diğer ihlaller",
                        value=(
                            f"İlk 8 ayrıntılı kayıt gösterildi. "
                            f"API toplam {len(records)} kayıt döndürdü."
                        ),
                        inline=False
                    )

            else:
                # Yalnızca isimler mevcutsa olmayan ayrıntıları uydurma
                embed.add_field(
                    name="Bulunan ihlal kaynakları",
                    value="\n".join(
                        f"• {name}" for name in names[:15]
                    )[:1024] or "İhlal adı alınamadı.",
                    inline=False
                )

                embed.add_field(
                    name="Ayrıntı durumu",
                    value=(
                        "Ücretsiz API bu sorguda yalnızca ihlal adlarını "
                        "döndürdü. Tarih ve veri türleri bu yanıtta "
                        "bulunmadığından doğrulanamadı."
                    ),
                    inline=False
                )

        embed.add_field(
            name="Gizlilik notu",
            value=(
                "Bu rapor bilinen ihlallerin özetidir. "
                "Sızdırılmış parolaları veya özel kayıt içeriklerini "
                "göstermez."
            ),
            inline=False
        )

        add_footer(embed, interaction)
        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response else 0

        print("E-posta API HTTP hatası:", status)

        if status == 404:
            message = (
                "Bu e-posta için kayıt bulunamadı veya API "
                "uç noktası yanıt vermedi."
            )
        elif status == 429:
            message = (
                "Ücretsiz API istek sınırına ulaşıldı. "
                "Bir süre sonra tekrar dene."
            )
        else:
            message = f"E-posta API isteği başarısız oldu (HTTP {status})."

        await interaction.followup.send(message, ephemeral=True)

    except requests.Timeout:
        await interaction.followup.send(
            "E-posta API'si zamanında yanıt vermedi.",
            ephemeral=True
        )
    except Exception as exc:
        print("email-sızıntı hatası:", repr(exc))
        await interaction.followup.send(
            "E-posta analizi başarısız oldu. Render loglarını kontrol et.",
            ephemeral=True
        )


# ============================================================
# 4. PHONE NUMBER FORMAT / COUNTRY PREFIX
# ============================================================

@bot.tree.command(
    name="phone-sorgu",
    description="Telefon numarasını biçimlendir ve ülke kodunu tahmin et"
)
async def phone_lookup(
    interaction: discord.Interaction,
    phone_number: str
):
    await interaction.response.defer(ephemeral=True)

    clean_phone = "".join(
        char for char in phone_number if char.isdigit()
    )

    if not 7 <= len(clean_phone) <= 15:
        await interaction.followup.send(
            "Telefon numarası uzunluğu geçersiz.",
            ephemeral=True
        )
        return

    countries = [
        ("90", "Türkiye (+90)"),
        ("44", "Birleşik Krallık (+44)"),
        ("49", "Almanya (+49)"),
        ("1", "ABD / Kanada (+1)")
    ]

    country = "Bilinmiyor"
    for prefix, label in countries:
        if clean_phone.startswith(prefix):
            country = label
            break

    embed = make_embed(
        "📱 NULLL INTELLIGENCE | Phone Analysis"
    )

    embed.add_field(
        name="Numara",
        value=f"`+{clean_phone}`",
        inline=False
    )
    embed.add_field(
        name="Ülke kodu tahmini",
        value=f"`{country}`",
        inline=True
    )
    embed.add_field(
        name="Operatör",
        value="Bu komut operatörü doğrulamaz.",
        inline=True
    )
    embed.add_field(
        name="WhatsApp bağlantısı",
        value=f"[Bağlantıyı aç](https://wa.me/{clean_phone})",
        inline=False
    )

    add_footer(embed, interaction)
    await interaction.followup.send(embed=embed, ephemeral=True)


# ============================================================
# 5. USERNAME SEARCH - WHATSMYNAME
# ============================================================

PLATFORM_ICONS = {
    "github": "🐙",
    "twitter": "🐦",
    "x.com": "🐦",
    "reddit": "🤖",
    "youtube": "▶️",
    "instagram": "📸",
    "tiktok": "🎵",
    "facebook": "📘",
    "linkedin": "💼",
    "pinterest": "📌",
    "snapchat": "👻",
    "twitch": "🎮",
    "steam": "🎮",
    "gitlab": "🦊",
    "telegram": "✈️",
    "gravatar": "🌐"
}

WMN_URL = (
    "https://raw.githubusercontent.com/"
    "WebBreacher/WhatsMyName/main/wmn-data.json"
)

wmn_cache = None
wmn_lock = asyncio.Lock()


def get_platform_icon(site):
    key = site.lower()

    for platform, icon in PLATFORM_ICONS.items():
        if platform in key:
            return icon

    return "🔗"


async def load_wmn():
    global wmn_cache

    async with wmn_lock:
        if wmn_cache is not None:
            return wmn_cache

        try:
            response = await asyncio.to_thread(
                SESSION.get,
                WMN_URL,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and isinstance(
                data.get("sites"), list
            ):
                wmn_cache = data
                return data

        except Exception as exc:
            print("WMN yükleme hatası:", repr(exc))

    return None


def probe_username(site, username):
    if str(site.get("request_method", "GET")).upper() != "GET":
        return None

    template = site.get("uri_check", "")

    if "{account}" not in template:
        return None

    url = template.replace(
        "{account}",
        urllib.parse.quote(username, safe="")
    )

    try:
        response = SESSION.get(
            url,
            timeout=4,
            allow_redirects=True
        )

        body = response.text or ""
        e_string = site.get("e_string") or ""
        m_string = site.get("m_string") or ""
        e_code = site.get("e_code")
        m_code = site.get("m_code")

        if m_code is not None and response.status_code == m_code:
            return None

        if m_string and m_string in body:
            return None

        matched = bool(e_string and e_string in body)

        if e_code is not None and response.status_code == e_code:
            matched = matched or not e_string

        if matched:
            return {
                "site": site.get("name", "Unknown"),
                "url": url
            }

    except Exception:
        pass

    return None


async def run_wmn_scan(username):
    data = await load_wmn()

    if not data:
        return []

    sites = data["sites"][:120]
    loop = asyncio.get_running_loop()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            loop.run_in_executor(
                executor, probe_username, site, username
            )
            for site in sites
        ]

        results = await asyncio.gather(
            *futures,
            return_exceptions=True
        )

    return [
        result for result in results
        if isinstance(result, dict)
    ]


@bot.tree.command(
    name="username",
    description="Herkese açık kullanıcı adı profillerini kontrol et"
)
async def username_check(
    interaction: discord.Interaction,
    username: str
):
    await interaction.response.defer()

    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", username):
        await interaction.followup.send(
            "Kullanıcı adı geçersiz.",
            ephemeral=True
        )
        return

    hits = await run_wmn_scan(username)

    embed = make_embed(
        "🔍 NULLL INTELLIGENCE | Username Scan",
        f"**Kullanıcı adı:** `{username}`"
    )

    if hits:
        for hit in hits[:15]:
            site = hit["site"]
            icon = get_platform_icon(site)

            embed.add_field(
                name=f"{icon} {site[:200]}",
                value=f"[Profili aç]({hit['url']})",
                inline=False
            )

        if len(hits) > 15:
            embed.add_field(
                name="Ek sonuçlar",
                value=f"{len(hits) - 15} ek eşleşme bulundu.",
                inline=False
            )
    else:
        embed.add_field(
            name="Sonuç",
            value=(
                "Kontrol edilen kaynaklarda eşleşme bulunamadı. "
                "Bu, kullanıcının başka sitelerde hesabı olmadığı "
                "anlamına gelmez."
            ),
            inline=False
        )

    add_footer(embed, interaction)
    await interaction.followup.send(embed=embed)


# ============================================================
# 6. DOMAIN WHOIS
# ============================================================

@bot.tree.command(
    name="domain-sorgu",
    description="Domain WHOIS kayıt bilgisi"
)
async def domain_lookup(
    interaction: discord.Interaction,
    domain_name: str
):
    await interaction.response.defer(ephemeral=True)

    domain_name = domain_name.strip().lower()

    if (
        len(domain_name) > 253
        or not re.fullmatch(
            r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
            domain_name
        )
    ):
        await interaction.followup.send(
            "Geçerli bir domain adı gir.",
            ephemeral=True
        )
        return

    try:
        result = await asyncio.to_thread(
            whois.whois,
            domain_name
        )

        embed = make_embed(
            "🌐 NULLL INTELLIGENCE | Domain WHOIS",
            f"**Domain:** `{domain_name}`"
        )

        for field, value in [
            ("Registrar", getattr(result, "registrar", None)),
            ("Oluşturulma tarihi", getattr(result, "creation_date", None)),
            ("Bitiş tarihi", getattr(result, "expiration_date", None)),
            ("Durum", getattr(result, "status", None))
        ]:
            embed.add_field(
                name=field,
                value=f"`{str(value or 'Bilinmiyor')[:900]}`",
                inline=False
            )

        add_footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except Exception as exc:
        print("WHOIS hatası:", repr(exc))
        await interaction.followup.send(
            "WHOIS sorgusu başarısız oldu.",
            ephemeral=True
        )


# ============================================================
# 7. URL ANALYSIS
# ============================================================

@bot.tree.command(
    name="url-analiz",
    description="URL erişilebilirlik ve HTTP durum kontrolü"
)
async def url_analysis(
    interaction: discord.Interaction,
    target_url: str
):
    await interaction.response.defer(ephemeral=True)

    if not target_url.startswith(("https://", "http://")):
        target_url = "https://" + target_url

    try:
        parsed = urllib.parse.urlparse(target_url)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            await interaction.followup.send(
                "Geçerli bir HTTP/HTTPS URL gir.",
                ephemeral=True
            )
            return

        # İç ağlara ve yerel servislere istek göndermeyi engelle.
        try:
            address = ipaddress.ip_address(parsed.hostname)

            if not address.is_global:
                await interaction.followup.send(
                    "Yerel veya özel IP adresleri sorgulanamaz.",
                    ephemeral=True
                )
                return
        except ValueError:
            if parsed.hostname.lower() in (
                "localhost", "localhost.localdomain"
            ):
                await interaction.followup.send(
                    "Yerel adresler sorgulanamaz.",
                    ephemeral=True
                )
                return

        response = await asyncio.to_thread(
            SESSION.get,
            target_url,
            timeout=8,
            allow_redirects=False,
            stream=True
        )

        status_code = response.status_code
        final_url = response.url
        response.close()

        embed = make_embed(
            "🌐 NULLL INTELLIGENCE | URL Analysis",
            f"**URL:** `{target_url[:900]}`"
        )

        embed.add_field(
            name="HTTP durum kodu",
            value=f"`{status_code}`",
            inline=True
        )
        embed.add_field(
            name="Redirect",
            value=(
                "Var"
                if 300 <= status_code < 400
                else "Yok"
            ),
            inline=True
        )
        embed.add_field(
            name="Not",
            value="HTTP yanıtı, sitenin güvenli olduğunu kanıtlamaz.",
            inline=False
        )

        add_footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except Exception as exc:
        print("URL analizi hatası:", repr(exc))
        await interaction.followup.send(
            "URL isteği başarısız oldu.",
            ephemeral=True
        )


# ============================================================
# 8. ADDRESS / MAP SEARCH
# ============================================================

@bot.tree.command(
    name="adres-sorgu",
    description="Bir adresi harita üzerinde aç"
)
async def adres_sorgu(
    interaction: discord.Interaction,
    adres: str
):
    await interaction.response.defer(ephemeral=True)

    encoded = urllib.parse.quote(adres.strip(), safe="")

    maps_url = (
        "https://www.google.com/maps/search/?api=1&query="
        + encoded
    )

    embed = make_embed(
        "📍 NULLL INTELLIGENCE | Map Search",
        f"**Girilen adres:**\n`{adres[:900]}`"
    )

    embed.add_field(
        name="Harita",
        value=f"[Google Maps'te aç]({maps_url})",
        inline=False
    )

    embed.add_field(
        name="Bilgilendirme",
        value=(
            "Bu komut adresin doğruluğunu veya bir kişinin "
            "orada bulunduğunu doğrulamaz."
        ),
        inline=False
    )

    add_footer(embed, interaction)
    await interaction.followup.send(embed=embed)


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN ortam değişkeni bulunamadı!"
        )

    keep_alive()
    bot.run(BOT_TOKEN)
