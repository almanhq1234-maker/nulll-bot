#  _  _ _  _ _    _     
#  |\ | |  | |    |     
#  | \| |__| |___ |___  
#
# NULL - Data breach searching Discord Bot 
# https://github.com/RocketGod-git/hackcheck-data-breach-search-discord-bot


import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import io
import traceback
import re
from datetime import datetime, timedelta
from xml.sax.saxutils import escape
from threading import Thread
from flask import Flask

import discord
from discord.ui import Modal, TextInput, Button, View
from discord import ButtonStyle

import aiohttp
from aiohttp import ClientTimeout, ClientError, ClientResponseError, ServerTimeoutError
import requests

from aiolimiter import AsyncLimiter
limiter = AsyncLimiter(8, 1)

from reportlab.lib.pagesizes import elevenSeventeen, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
import csv
import ast 

# ---------------------------------------------------------------------
# Flask 24/7 Uptime Sunucusu (Render İçin)
# ---------------------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "NULL Hackcheck Discord Bot 24/7 Aktif!", 200

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# ---------------------------------------------------------------------
# Logging Konfigürasyonu
# ---------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(), 
        RotatingFileHandler('hackcheck.log', maxBytes=5*1024*1024, backupCount=2, encoding='utf-8', mode='a')  
    ]
)
logging.getLogger('discord').setLevel(logging.WARNING)


timeout = ClientTimeout(total=120)
retry_attempts = 3
backoff_factor = 0.5


def load_config():
    file_config = {}
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as config_file:
                file_config = json.load(config_file)
    except Exception as e:
        logging.warning(f"config.json okunamadı: {e}")

    token = file_config.get("discord_token")
    if not token or token == "DISCORD_BOT_TOKENINIZ":
        token = os.getenv("DISCORD_TOKEN", "")

    api_key = file_config.get("hackcheck_api_key")
    if not api_key or api_key == "HACKCHECK_API_KEYINIZ":
        api_key = os.getenv("HACKCHECK_API_KEY", "")

    webhook = file_config.get("webhook_url")
    if not webhook or webhook == "WEBHOOK_URLINIZ":
        webhook = os.getenv("WEBHOOK_URL", "")

    return {
        "discord_token": token,
        "hackcheck_api_key": api_key,
        "webhook_url": webhook
    }


config = load_config()


def validate_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


async def register_render_ip():
    """Bot her açıldığında Render IP adresini Hackcheck'e otomatik kaydeder."""
    api_key = config.get("hackcheck_api_key", "")
    if not api_key:
        return
    url = f"https://api.hackcheck.io/auth/ip?key={api_key}"
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                text = await response.text()
                if response.status == 200:
                    logging.info(f"Render IP başarıyla Hackcheck'e kaydedildi: {text}")
                else:
                    logging.warning(f"IP kaydı sırasında uyarı/hata ({response.status}): {text}")
    except Exception as e:
        logging.error(f"IP otomatik kayıt isteği başarısız oldu: {e}")


def prepare_data_for_csv(results):
    prepared_data = []
    for result in results:
        row = {key: value for key, value in result.items() if key != 'source'}
        source_info = result.get('source', {})
        source_name = source_info.get('name', 'Unknown source')
        source_date = source_info.get('date', 'No date provided')
        row['source'] = f"Name: {source_name}, Date: {source_date}"
        prepared_data.append(row)
    return prepared_data


def create_csv_file(data, filename_prefix="results"):
    if not data:  
        return None

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"

    keys = data[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)

    return filename


def create_pdf_from_csv(csv_filename, filename_prefix="results"):
    timestamp = csv_filename.split('_')[-1].split('.')[0]
    pdf_filename = f"{filename_prefix}_{timestamp}.pdf"

    with open(csv_filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        data = [list(row) for row in reader]

    readable_style = ParagraphStyle(
        name='Readable',
        fontName='Times-Roman',  
        fontSize=10,
        leading=12,  
        alignment=TA_LEFT,
    )

    styles = getSampleStyleSheet()
    styleNormal = styles['Normal']
    styleNormal.wordWrap = 'CJK'  

    for i, row in enumerate(data):
        for j, cell in enumerate(row):
            if j == len(row) - 1:
                try:
                    source_dict = ast.literal_eval(cell)
                    source_str = f"{source_dict.get('name', 'N/A')}: {source_dict.get('date', 'No date')}"
                    data[i][j] = Paragraph(escape(source_str), readable_style)
                except (ValueError, SyntaxError):
                    data[i][j] = Paragraph(escape(cell), readable_style)
            else:
                data[i][j] = Paragraph(escape(cell), readable_style)

    pdf = SimpleDocTemplate(pdf_filename, pagesize=landscape(elevenSeventeen))

    usable_width = landscape(elevenSeventeen)[0] - 2 * 72 
    column_widths = [usable_width * 0.19,  
                     usable_width * 0.10,  
                     usable_width * 0.10,  
                     usable_width * 0.10,  
                     usable_width * 0.08,  
                     usable_width * 0.08,  
                     usable_width * 0.20,  
                     usable_width * 0.15]  

    table = Table(data, colWidths=column_widths, repeatRows=1)

    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
    ])
    table.setStyle(style)

    elems = [table]
    pdf.build(elems)

    return pdf_filename


class PaginatorView(discord.ui.View):
    def __init__(self, data, term, search_type, page_size=4):
        super().__init__()
        self.data = data
        self.term = term
        self.search_type = search_type
        self.page_size = page_size
        self.current_page = 0
        self.max_page = (len(self.data) - 1) // page_size
        self.message = None

        self.back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.primary, disabled=(self.current_page == 0))
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, disabled=(self.current_page >= self.max_page))
        
        self.add_item(self.back_button)
        self.add_item(self.next_button)
        self.back_button.callback = self.back_button_callback
        self.next_button.callback = self.next_button_callback

    async def back_button_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_buttons_and_message(interaction)

    async def next_button_callback(self, interaction: discord.Interaction):
        if self.current_page < self.max_page:
            self.current_page += 1
        await self.update_buttons_and_message(interaction)

    async def update_buttons_and_message(self, interaction):
        try:
            self.back_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= self.max_page
            await self.update_message(interaction)
            await interaction.response.edit_message(view=self)
        except discord.NotFound:
            logging.error("Error: Message not found when trying to edit.")
        except discord.HTTPException as e:
            logging.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logging.error(f"Unhandled exception: {e}")

    async def update_message(self, interaction):
        start = self.current_page * self.page_size
        end = start + self.page_size
        limited_results = {"results": self.data[start:end]}
        content = format_breaches(self.term, self.search_type, limited_results)
        try:
            if self.message:
                await self.message.edit(content=content, view=self)
            else:
                self.message = await interaction.followup.send(content=content, view=self)
        except discord.NotFound:
            logging.error("Error: Message not found when trying to send or edit.")
        except discord.HTTPException as e:
            logging.error(f"HTTP error while sending or editing message: {e}")
        except Exception as e:
            logging.error(f"Unhandled exception during message update: {e}")

    async def on_timeout(self):
        self.back_button.disabled = True
        self.next_button.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except discord.NotFound:
            logging.error("Error: Message not found during timeout.")
        except discord.HTTPException as e:
            logging.error(f"HTTP error occurred during on_timeout: {e}")
        except Exception as e:
            logging.error(f"Unhandled exception during on_timeout: {e}")

    def stop_paginator(self):
        self.stop()


async def make_hackcheck_request(search_type, term, max_pages=75):
    api_key = config.get("hackcheck_api_key", "")
    all_results = []
    offset = 0
    limit = 75 
    page_count = 0

    async with aiohttp.ClientSession(timeout=timeout) as session:
        has_more_data = True

        while has_more_data and page_count < max_pages:
            async with limiter:
                url = f"https://api.hackcheck.io/search/{api_key}/{search_type.replace(' ', '_')}/{term}?offset={offset}&limit={limit}"
                try:
                    async with session.get(url) as response:
                        data = await response.json()  
                        if response.status != 200:
                            error_message = data.get('error', 'Unknown error')
                            logging.error(f"API Error: {error_message}")
                            logging.error(f"API Response: {data}")  
                            return {"error": f"API Error: {error_message}"}

                        all_results.extend(data.get("results", []))
                        pagination_info = data.get('pagination', {})

                        next_page = pagination_info.get('next')
                        if next_page:
                            offset = next_page['offset']
                            limit = next_page['limit']
                        else:
                            has_more_data = False

                        page_count += 1

                except aiohttp.ClientError as e:
                    logging.error(f"ClientError occurred: {e}")
                except json.JSONDecodeError as e:
                    logging.error(f"JSONDecodeError occurred: {e}")
                except asyncio.TimeoutError as e:
                    logging.error(f"TimeoutError occurred: {e}")
                except Exception as e:
                    logging.error(f"An unexpected error occurred: {type(e).__name__}: {e}")
                    traceback_str = traceback.format_exc()  
                    logging.error(f"Traceback: {traceback_str}")
                    return {"error": "An unexpected error occurred during the API request."}

    return {"results": all_results}


def format_breaches(term, search_type, response):
    header = f"{term}:\n\n"

    if not response or "results" not in response or not response["results"]:
        return f"No breaches found for {search_type} '{term}'."

    breach_list = []
    for breach in response["results"]:
        details = []
        source_info = breach.get("source", {})
        source_name = source_info.get("name", "Unknown source")
        date = source_info.get("date", "No date")  

        details.append(f"- Source: {source_name} ({date})")  

        for key in ["email", "password", "username", "full_name", "ip_address", "phone_number", "hash"]:
            value = breach.get(key)
            if value:
                details.append(f"  {key.replace('_', ' ').capitalize()}: {value}")

        breach_list.append('\n'.join(details))

    return header + '\n\n'.join(breach_list)


async def attempt_delete_with_retries(filename, max_attempts=5):
    attempt = 0
    while attempt < max_attempts:
        try:
            os.remove(filename)
            return True  
        except PermissionError as e:
            logging.warning(f"PermissionError when trying to delete file {filename}. Retrying... Attempt {attempt + 1}/{max_attempts}")
            await asyncio.sleep(1)  
        except FileNotFoundError:
            logging.warning(f"File {filename} not found. It may have already been deleted.")
            return False  
        except Exception as e:
            logging.error(f"Failed to delete file {filename} on attempt {attempt + 1}: {e}")
            break  
        finally:
            attempt += 1

    logging.error(f"Could not delete file {filename} after {max_attempts} attempts.")
    return False  


class SearchModal(Modal):
    def __init__(self, search_type, bot):
        super().__init__(title=f"Search by {search_type.capitalize()}")
        self.search_type = search_type
        self.bot = bot
        self.add_item(TextInput(label=f"Enter {search_type}", custom_id="search_term"))

    async def on_submit(self, interaction: discord.Interaction):
        term = self.children[0].value
        if interaction.guild:
            guild_name = interaction.guild.name
            channel_name = interaction.channel.name
        else:
            guild_name = "Direct Message"
            channel_name = "Direct Message"

        logging.info(f"{interaction.user} searched for '{term}' from '{channel_name}' at '{guild_name}'")

        if self.search_type == "email" and not validate_email(term):
            await interaction.response.send_message("The provided email is invalid. Please enter a valid email address.")
            return

        if config.get("webhook_url"):
            asyncio.create_task(self.send_webhook_message(interaction.user, term, interaction, interaction.guild))
        
        await interaction.response.defer(ephemeral=False)
        asyncio.create_task(self.process_search(interaction, term))
        
    async def process_search(self, interaction: discord.Interaction, term: str):
        try:
            await interaction.followup.send("Processing your search. Please wait...")

            full_results = await make_hackcheck_request(self.search_type, term)
            if "error" in full_results:
                logging.error(full_results["error"])
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")
                return

            reversed_results = list(
