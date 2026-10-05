from cuentas_manager import cargar_cuentas, guardar_cuentas
import os
import asyncio
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import requests

LARAVEL_API_URL = "https://darkviolet-rat-754475.hostingersite.com/api/bot/credenciales"
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN", "fstflix_super_secret_bot_token_2026")

def fetch_laravel_credentials(email: str):
    try:
        response = requests.post(
            LARAVEL_API_URL, 
            json={"correo": email},
            headers={"Authorization": f"Bearer {BOT_API_TOKEN}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error llamando a Laravel API: {e}")
    return None

from playwright.async_api import async_playwright

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
WEB_USER = os.getenv("WEB_USER", "Gianpierre")
WEB_PASS = os.getenv("WEB_PASS", "gianpier21")
ROYPLAY_CODE = "GIANPI4869"

CHOOSING_PLATFORM, CHOOSING_ACTION, TYPING_EMAIL = range(3)


def is_allowed(user_id: int) -> bool:
    try:
        with open("usuarios_permitidos.txt", "r") as f:
            allowed = [int(line.strip()) for line in f if line.strip().isdigit()]
    except FileNotFoundError:
        allowed = [5190513736]
    return user_id in allowed



async def quitar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != 5190513736:
        await update.message.reply_text("⛔ No tienes permisos.")
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ Uso correcto: /quitar <ID_DE_TELEGRAM>")
        return
        
    quitar_id = context.args[0]
    
    if quitar_id == "5190513736":
        await update.message.reply_text("⚠️ No puedes eliminar tu propio ID de administrador.")
        return
        
    try:
        with open("usuarios_permitidos.txt", "r") as f:
            existentes = [line.strip() for line in f if line.strip().isdigit()]
            
        if quitar_id not in existentes:
            await update.message.reply_text("⚠️ Ese ID no está en la lista blanca.")
            return
            
        existentes.remove(quitar_id)
        
        with open("usuarios_permitidos.txt", "w") as f:
            for uid in existentes:
                f.write(f"{uid}\n")
                
        await update.message.reply_text(f"✅ El ID {quitar_id} fue eliminado. Ya no tiene acceso al bot.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al quitar el ID: {e}")

async def lista_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != 5190513736:
        await update.message.reply_text("⛔ No tienes permisos.")
        return
        
    try:
        with open("usuarios_permitidos.txt", "r") as f:
            existentes = [line.strip() for line in f if line.strip().isdigit()]
            
        msg = "📋 *Usuarios Autorizados:*\n\n"
        for i, uid in enumerate(existentes, 1):
            admin_tag = " (Admin)" if uid == "5190513736" else ""
            msg += f"{i}. `{uid}`{admin_tag}\n"
            
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer la lista: {e}")


async def ver_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != 5190513736:
        await update.message.reply_text("⛔ No tienes permisos.")
        return

    try:
        import os
        if not os.path.exists("historial_uso.txt"):
            await update.message.reply_text("📭 Aún no hay registros de uso.")
            return

        with open("historial_uso.txt", "r", encoding="utf-8") as f:
            lineas = f.readlines()

        if not lineas:
            await update.message.reply_text("📭 El historial está vacío.")
            return

        # Tomar las últimas 15 peticiones para no saturar el mensaje
        ultimas = lineas[-15:]
        msg = "📖 *Últimas 15 peticiones (Más recientes al final):*\n\n"
        
        # Usamos un bloque de código para que quede perfectamente alineado y limpio
        msg += "```text\n"
        for linea in ultimas:
            msg += f"{linea.strip()}\n"
        msg += "```"

        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer el historial: {e}")

async def stats_uso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != 5190513736:
        await update.message.reply_text("⛔ No tienes permisos.")
        return
        
    try:
        from datetime import datetime
        hoy = datetime.now().strftime("%Y-%m-%d")
        total_peticiones = 0
        peticiones_hoy = 0
        
        plataformas = {'netflix': 0, 'disney': 0, 'prime': 0}
        
        if os.path.exists("historial_uso.txt"):
            with open("historial_uso.txt", "r", encoding="utf-8") as f:
                lineas = f.readlines()
                total_peticiones = len(lineas)
                for linea in lineas:
                    if hoy in linea:
                        peticiones_hoy += 1
                    
                    if "netflix" in linea.lower(): plataformas['netflix'] += 1
                    elif "disney" in linea.lower(): plataformas['disney'] += 1
                    elif "prime" in linea.lower(): plataformas['prime'] += 1
                        
        msg = f"📊 *Estadísticas del Bot*\n\n"
        msg += f"📅 Peticiones hoy: *{peticiones_hoy}*\n"
        msg += f"📈 Total peticiones (Histórico): *{total_peticiones}*\n\n"
        msg += f"*Por plataforma (Histórico):*\n"
        msg += f"🔴 Netflix: {plataformas['netflix']}\n"
        msg += f"🔵 Disney: {plataformas['disney']}\n"
        msg += f"📦 Prime: {plataformas['prime']}\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer las estadísticas: {e}")

async def agregar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Solo tú (el admin principal)
    if update.effective_user.id != 5190513736:
        await update.message.reply_text("⛔ No tienes permisos de administrador para usar este comando.")
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ Uso correcto: /agregar <ID_DE_TELEGRAM>")
        return
        
    nuevo_id = context.args[0]
    
    if not nuevo_id.isdigit():
        await update.message.reply_text("⚠️ El ID debe ser un número.")
        return
        
    # Verificar si ya existe
    try:
        with open("usuarios_permitidos.txt", "r") as f:
            existentes = [line.strip() for line in f if line.strip().isdigit()]
        if nuevo_id in existentes:
            await update.message.reply_text("⚠️ Ese ID ya está en la lista blanca.")
            return
    except:
        pass
        
    # Agregar
    try:
        with open("usuarios_permitidos.txt", "a") as f:
            f.write(f"\n{nuevo_id}\n")
        await update.message.reply_text(f"✅ ¡Éxito! El ID {nuevo_id} fue agregado a la lista blanca. Esa persona ya puede usar el bot de inmediato.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar el ID: {e}")

async def mi_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Tu ID de Telegram es: {update.effective_user.id}")

def check_15_mins(texto: str) -> tuple[bool, str]:
    meses = {'enero':1, 'febrero':2, 'marzo':3, 'abril':4, 'mayo':5, 'junio':6, 'julio':7, 'agosto':8, 'septiembre':9, 'octubre':10, 'noviembre':11, 'diciembre':12}
    match = re.search(r'(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4}),\s+(\d{1,2}):(\d{2})', texto.lower())
    if not match:
        return True, "" 
        
    dia = int(match.group(1))
    mes_str = match.group(2)
    anio = int(match.group(3))
    hora = int(match.group(4))
    minuto = int(match.group(5))
    mes = meses.get(mes_str, 1)
    
    try:
        from datetime import timezone, timedelta
        codigo_time = datetime(anio, mes, dia, hora, minuto)
        now_utc = datetime.now(timezone.utc)
        now = now_utc.astimezone(timezone(timedelta(hours=-5))).replace(tzinfo=None)
        diff = now - codigo_time
        if diff.total_seconds() < 0:
            diff = codigo_time - now
            
        if diff.total_seconds() > 15 * 60:
            return False, "❌ El último código enviado ya venció. Por favor, solicita uno nuevo en la plataforma."
        return True, ""
    except:
        