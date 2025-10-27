import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
from difflib import get_close_matches
from transformers import pipeline
import unicodedata
import random
import requests
from server import keep_alive
import os

#keep_alive()

# ---------- Funciones de normalización y coincidencias ----------
def normalizar(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn')
    return texto

def encontrar_similar(msg, respuestas):
    claves_normalizadas = {normalizar(k): k for k in respuestas.keys()}
    msg_norm = normalizar(msg)
    coincidencias = get_close_matches(msg_norm, claves_normalizadas.keys(), n=1, cutoff=0.6)
    if coincidencias:
        return claves_normalizadas[coincidencias[0]]
    return None

chatbot = pipeline("text-generation", model="distilgpt2", device=-1)

def traducir_texto(texto, origen="es", destino="en"):
    """
    Traduce texto usando MyMemory API gratuita
    """
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": texto, "langpair": f"{origen}|{destino}"}
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        return data.get("responseData", {}).get("translatedText", texto)
    except:
        return texto

def chat_ia_es(mensaje):
    """
    Recibe mensaje en español, lo traduce a inglés,
    genera respuesta con GPT-2, y traduce al español.
    """
    try:
        # Traducir mensaje a inglés
        mensaje_en = traducir_texto(mensaje, origen="es", destino="en")

        # Generar respuesta con GPT-2
        resultado = chatbot(
            mensaje_en,
            max_new_tokens=50,
            max_length=120,
            temperature=0.9,
            repetition_penalty=2.4
        )
        respuesta_en = resultado[0]['generated_text'].split("\n")[0]

        # Traducir respuesta de vuelta al español
        respuesta_es = traducir_texto(respuesta_en, origen="en", destino="es")
        return respuesta_es
    except Exception as e:
        return f"No pude responder 😅 ({e})"

# ---------- Configuración del bot ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # necesario para detectar nuevos miembros
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Evento cuando el bot se conecta ----------
@bot.event
async def on_ready():
    await bot.tree.sync()
    mensaje_diario.start()
    print(f"{bot.user} está conectado y listo!")

# ---------- Evento principal ----------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = normalizar(message.content)

    # Responder palabras clave solo si mencionan al bot
    if message.content.startswith("!ia"):
        pregunta = message.content[len("!ia"):]
        respuesta = chat_ia_es(pregunta)
        await message.channel.send(respuesta)

    await bot.process_commands(message)

# ---------- Evento cuando un miembro se une ----------
@bot.event
async def on_member_join(member):
    # ID del canal de bienvenida
    canal_id = 1431435545594036254  # reemplaza con el ID real de tu canal
    canal = bot.get_channel(canal_id)
    if canal:
        mensaje_bienvenida = (
            f"✨ ¡Bienvenido {member.mention}! ✨\n"
            "🌟 Que disfrutes tu estadía en nuestro servidor 🌟\n"
            "💬 ¡No olvides leer las reglas y presentarte! 💬"
        )
        await canal.send(mensaje_bienvenida)

@bot.tree.command(name="leave", description="Bloquea a un usuario (solo Creador)")
@app_commands.describe(user="Usuario a bloquear")
async def leave(interaction: discord.Interaction, user: discord.Member):
    rol_creador = discord.utils.get(interaction.user.roles, name="Creador")
    if not rol_creador:
        await interaction.response.send_message("No tienes permisos para usar este comando", ephemeral=True)
        return

    if not user:
        await interaction.response.send_message("Usuario no encontrado.", ephemeral=True)
        return

    rol_bloqueado = discord.utils.get(interaction.guild.roles, name="Bloqueado")
    if not rol_bloqueado:
        await interaction.response.send_message("No existe un rol de Bloqueado")
        return

    await user.add_roles(rol_bloqueado)
    await interaction.response.send_message(f"{user.mention} ha sido bloqueado.")

@bot.tree.command(name="enter", description="Desbloquea a un usuario (solor Creador)")
@app_commands.describe(user="Usuario a desbloquear")
async def enter(interaction: discord.Interaction, user: discord.Member):
    rol_creador = discord.utils.get(interaction.user.roles, name="Creador")
    if not rol_creador:
        await interaction.response.send_message("No tienes permisos para usar este comando", ephemeral=True)
        return

    if not user:
        await interaction.response.send_message("Usuario no encontrado.", ephemeral=True)
        return
    
    rol_bloqueado = discord.utils.get(interaction.guild.roles, name="Bloqueado")
    if not rol_bloqueado:
        await interaction.response.send_message("No existe un rol de Bloqueado", ephemeral=True)
        return
    
    await user.remove_roles(rol_bloqueado)
    await interaction.response.send_message(f"{user.mention} ha sido desbloqueado")

@bot.tree.command(name="clima", description="Muestra el clima actual de una ciudad")
@app_commands.describe(ciudad="Nombre de la ciudad")
async def clima(interaction: discord.Interaction, ciudad: str):
    api_key = "5bb3e0bb3fcdc1fa499c0c165372c5f1"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={api_key}&units=metric&lang=es"
    
    respuesta = requests.get(url).json()

    if respuesta.get("cod") != 200:
        await interaction.response.send_message(f"No se encontró la ciudad `{ciudad}`.")
        return
    
    nombre = respuesta["name"]
    temp = respuesta["main"]["temp"]
    desc = respuesta["weather"][0]["description"]

    await interaction.response.send_message(
        f"Clima en **{nombre}**:\nTemperatura: {temp}°C\nCondición: {desc}"
    )

@tasks.loop(hours=24)
async def mensaje_diario():
    canal_id = 1431431151402221601
    canal = bot.get_channel(canal_id)
    if canal:
        await canal.send("Buenos días a todos! Que tengan un día increíble")

@bot.tree.command(name="meme", description="Envia un meme aleatorio")
async def meme(interaction: discord.Interaction):
    url = "https://meme-api.com/gimme"

    try:
        respuesta = requests.get(url).json()
        imagen = respuesta.get("url")
        titulo = respuesta.get("tittle", "Meme random")

        if imagen:
            embed = discord.Embed(title=titulo, color=0x00ff00)
            embed.set_image(url=imagen)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No pude obtener un meme ahora, intenta más tarde!")

    except Exception as e:
        await interaction.response.send_message(f"Ocurrió un error: {e}")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong")

# ---------- Ejecutar bot ----------
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("Error: no se encontro DISCORD TOKEN en las variables de entorno")
else:
    bot.run(TOKEN)
