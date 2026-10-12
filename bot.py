
import os
import re
import asyncio
import datetime
import urllib.parse
import ipaddress
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

import requests
import whois
import discord
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


class NullBot(commands.Bot):
    async def setup_hook(self):
        await self.tree.sync()
        print("Slash komutları senkronize edildi.")


bot = NullBot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")

COLOR = discord.Color.from_rgb(47, 49, 54)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "NULLL-INTELLIGENCE/1.0"})


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


@bot.event
async def on_ready():
    print(f"NULLL INTELLIGENCE aktif: {bot.user} ({bot.user.id})")


# ==================== EMAIL BREACH ====================

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
            # Yalnızca ihlal kaydı olabilecek nesneleri al.
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
        # 1. XposedOrNot ayrıntılı analiz
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

        # 2. Temel XposedOrNot kontrolü
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

        # 3. HIBP, yalnızca kullanıcı API anahtarı tanımladıysa
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

        # HIBP yanıtlarını da kayıt listesine dönüştür.
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

            # Kayıtları isimleri üzerinden birleştir.
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
                    # HTML etiketlerini kaldır.
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


# ==================== DISCORD USER ====================

@bot.tree.command(name="ara", description="Discord hesap bilgileri")
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

        footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except Exception as exc:
        print("ARA:", repr(exc))
        await interaction.followup.send("Sorgu başarısız.", ephemeral=True)


# ==================== IP LOOKUP ====================

@bot.tree.command(name="ip-lookup", description="Genel IP bilgileri")
async def ip_lookup(interaction: discord.Interaction, ip_address: str):
    await interaction.response.defer(ephemeral=True)

    try:
        ip = ipaddress.ip_address(ip_address.strip())

        if not ip.is_global:
            await interaction.followup.send(
                "Genel bir IP adresi gir.", ephemeral=True
            )
            return

        data = await get_json(
            f"http://ip-api.com/json/{ip}",
            params={"fields": (
                "status,message,continent,country,countryCode,"
                "regionName,city,zip,lat,lon,timezone,isp,org,as,proxy"
            )}
        )

        if data.get("status") != "success":
            await interaction.followup.send(
                "IP bulunamadı.", ephemeral=True
            )
            return

        embed = embed_base(
            "🌐 NULLL INTELLIGENCE | IP Analysis",
            f"**IP:** `{ip}`"
        )

        for label, key in [
            ("Ülke", "country"), ("Bölge", "regionName"),
            ("Şehir", "city"), ("Posta kodu", "zip"),
            ("Zaman dilimi", "timezone"), ("ISP", "isp"),
            ("Organizasyon", "org"), ("AS", "as"),
            ("Proxy sinyali", "proxy")
        ]:
            embed.add_field(
                name=label,
                value=str(data.get(key) or "Bilinmiyor")[:200],
                inline=True
            )

        lat, lon = data.get("lat"), data.get("lon")
        if lat is not None and lon is not None:
            url = f"https://maps.google.com/?q={lat},{lon}"
            embed.add_field(
                name="Harita",
                value=f"[Yaklaşık konumu aç]({url})",
                inline=False
            )

        footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except ValueError:
        await interaction.followup.send("Geçersiz IP.", ephemeral=True)
    except Exception as exc:
        print("IP:", repr(exc))
        await interaction.followup.send("IP sorgusu başarısız.", ephemeral=True)


# ==================== PHONE LOOKUP ====================

@bot.tree.command(name="phone-sorgu", description="Telefon numarası biçim kontrolü")
async def phone_lookup(interaction: discord.Interaction, phone_number: str):
    await interaction.response.defer(ephemeral=True)

    number = "".join(c for c in phone_number if c.isdigit())

    if not 7 <= len(number) <= 15:
        await interaction.followup.send("Numara geçersiz.", ephemeral=True)
        return

    country = "Bilinmiyor"
    for prefix, name in [
        ("90", "Türkiye"), ("44", "Birleşik Krallık"),
        ("49", "Almanya"), ("1", "ABD/Kanada")
    ]:
        if number.startswith(prefix):
            country = name
            break

    embed = embed_base("📱 NULLL INTELLIGENCE | Phone Lookup")
    embed.add_field(name="Numara", value=f"`+{number}`", inline=True)
    embed.add_field(name="Ülke kodu tahmini", value=country, inline=True)
    embed.add_field(
        name="Not",
        value="Operatör ve hat türü bu komut tarafından doğrulanmaz.",
        inline=False
    )
    embed.add_field(
        name="WhatsApp",
        value=f"[Bağlantıyı aç](https://wa.me/{number})",
        inline=False
    )

    footer(embed, interaction)
    await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== USERNAME SCAN ====================

WMN_URL = (
    "https://raw.githubusercontent.com/"
    "WebBreacher/WhatsMyName/main/wmn-data.json"
)
wmn_cache = None
wmn_lock = asyncio.Lock()


async def load_wmn():
    global wmn_cache

    async with wmn_lock:
        if wmn_cache is not None:
            return wmn_cache

        try:
            wmn_cache = await get_json(WMN_URL, timeout=15)
            return wmn_cache
        except Exception as exc:
            print("WMN:", repr(exc))
            return None


def probe_site(site, username):
    if site.get("request_method", "GET").upper() != "GET":
        return None

    template = site.get("uri_check", "")
    if "{account}" not in template:
        return None

    url = template.replace(
        "{account}", urllib.parse.quote(username, safe="")
    )

    try:
        response = SESSION.get(url, timeout=4, allow_redirects=True)
        body = response.text or ""

        m_code = site.get("m_code")
        m_string = site.get("m_string") or ""
        e_code = site.get("e_code")
        e_string = site.get("e_string") or ""

        if m_code is not None and response.status_code == m_code:
            return None
        if m_string and m_string in body:
            return None

        hit = bool(e_string and e_string in body)
        if e_code is not None and response.status_code == e_code:
            hit = hit or not e_string

        if hit:
            return {
                "name": site.get("name", "Unknown"),
                "url": url
            }
    except Exception:
        pass

    return None


async def scan_username(username):
    data = await load_wmn()
    if not data or not isinstance(data.get("sites"), list):
        return []

    loop = asyncio.get_running_loop()

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            loop.run_in_executor(pool, probe_site, site, username)
            for site in data["sites"][:120]
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]


@bot.tree.command(name="username", description="Herkese açık profil eşleşmeleri")
async def username_check(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)

    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", username):
        await interaction.followup.send("Kullanıcı adı geçersiz.", ephemeral=True)
        return

    hits = await scan_username(username)
    embed = embed_base(
        "🔎 NULLL INTELLIGENCE | Username Scan",
        f"**Kullanıcı adı:** `{username}`"
    )

    if hits:
        for hit in hits[:15]:
            embed.add_field(
                name=hit["name"][:250],
                value=f"[Profili aç]({hit['url']})",
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


# ==================== DOMAIN WHOIS ====================

@bot.tree.command(name="domain-sorgu", description="Domain WHOIS")
async def domain_lookup(interaction: discord.Interaction, domain_name: str):
    await interaction.response.defer(ephemeral=True)

    domain_name = domain_name.strip().lower()

    if not re.fullmatch(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
        domain_name
    ):
        await interaction.followup.send("Domain geçersiz.", ephemeral=True)
        return

    try:
        result = await asyncio.to_thread(whois.whois, domain_name)
        embed = embed_base(
            "🌐 NULLL INTELLIGENCE | WHOIS",
            f"**Domain:** `{domain_name}`"
        )

        for label, attr in [
            ("Registrar", "registrar"),
            ("Oluşturulma", "creation_date"),
            ("Bitiş", "expiration_date"),
            ("Durum", "status")
        ]:
            embed.add_field(
                name=label,
                value=str(getattr(result, attr, None) or "Bilinmiyor")[:900],
                inline=False
            )

        footer(embed, interaction)
        await interaction.followup.send(embed=embed)

    except Exception as exc:
        print("WHOIS:", repr(exc))
        await interaction.followup.send("WHOIS başarısız.", ephemeral=True)


# ==================== URL ANALYSIS ====================

@bot.tree.command(name="url-analiz", description="URL HTTP durum kontrolü")
async def url_analysis(interaction: discord.Interaction, target_url: str):
    await interaction.response.defer(ephemeral=True)

    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    try:
        parsed = urllib.parse.urlparse(target_url)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            await interaction.followup.send("URL geçersiz.", ephemeral=True)
            return

        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if not ip.is_global:
                await interaction.followup.send(
                    "Özel IP adreslerine istek gönderilemez.",
                    ephemeral=True
                )
                return
        except ValueError:
            if parsed.hostname.lower() == "localhost":
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

        status = response.status_code
        response.close()

        embed = embed_base(
            "🌐 NULLL INTELLIGENCE | URL Analysis",
            f"**URL:** `{target_url[:900]}`"
        )
        embed.add_field(name="HTTP durum kodu", value=str(status))
        embed.add_field(
            name="Güvenlik",
            value="HTTP yanıtı sitenin güvenli olduğunu kanıtlamaz.",
            inline=False
        )

        footer(embed, interaction)
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as exc:
        print("URL:", repr(exc))
        await interaction.followup.send("URL kontrolü başarısız.", ephemeral=True)


# ==================== ADDRESS MAP ====================

@bot.tree.command(name="adres-sorgu", description="Adresi Google Maps'te aç")
async def adres_sorgu(interaction: discord.Interaction, adres: str):
    await interaction.response.defer(ephemeral=True)

    encoded = urllib.parse.quote(adres.strip(), safe="")
    url = "https://www.google.com/maps/search/?api=1&query=" + encoded

    embed = embed_base(
        "📍 NULLL INTELLIGENCE | Address Search",
        f"**Adres:** `{adres[:900]}`"
    )
    embed.add_field(
        name="Harita",
        value=f"[Google Maps'te aç]({url})",
        inline=False
    )
    embed.add_field(
        name="Bilgilendirme",
        value="Bu bağlantı adresi doğrulamaz veya bir kişinin konumunu tespit etmez.",
        inline=False
    )

    footer(embed, interaction)
    await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== START ====================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN Render Environment içinde tanımlı değil.")

    keep_alive()
    bot.run(TOKEN)
