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
        codigo_time = datetime(anio, mes, dia, hora, minuto)
        now = datetime.now()
        diff = now - codigo_time
        if diff.total_seconds() < 0:
            diff = codigo_time - now
            
        if diff.total_seconds() > 15 * 60:
            return False, f"❌ El último código encontrado es del {dia} de {mes_str.capitalize()} a las {hora:02d}:{minuto:02d}.\n\nTiene más de 15 minutos de antigüedad, por lo tanto **ya no es válido**."
        return True, ""
    except:
        return True, ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_allowed(update.effective_user.id):
        msg = "⛔ No tienes autorización para usar este bot."
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.edit_message_text(msg)
        return ConversationHandler.END
        
    keyboard = [
        [InlineKeyboardButton("Netflix", callback_data="plat_netflix")],
        [InlineKeyboardButton("Disney", callback_data="plat_disney")],
        [InlineKeyboardButton("Prime", callback_data="plat_prime")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("¡Hola! Selecciona la plataforma que deseas ver:", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("Selecciona la plataforma que deseas ver:", reply_markup=reply_markup)
    return CHOOSING_PLATFORM

async def platform_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    plataforma = query.data.split('_')[1]
    context.user_data['plataforma'] = plataforma

    if plataforma == 'netflix':

        keyboard = []
        # Disponible para todos los usuarios autorizados
        keyboard.append([InlineKeyboardButton("Código de inicio de sesión", callback_data="act_login")])
            
        keyboard.extend([
            [InlineKeyboardButton("Estoy de viaje", callback_data="act_travel")],
            [InlineKeyboardButton("Actualizar hogar", callback_data="act_home")],
            [InlineKeyboardButton("Código de 6 dígitos", callback_data="act_6digits")],
            [InlineKeyboardButton("🔙 Volver", callback_data="back_to_start")]
        ])
        await query.edit_message_text(
            text=f"Has seleccionado Netflix. Ahora, elige el tipo de código:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSING_ACTION
    else:
        # Disney y Prime van directo a pedir correo
        context.user_data['accion'] = 'unique'
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_to_start")]]
        await query.edit_message_text(
            text=f"Has seleccionado {plataforma.capitalize()}.\n\nPor favor, envíame el correo de la cuenta:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TYPING_EMAIL

async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_start":
        return await start(update, context)
        
    accion = query.data.split('_')[1]
    
    # El acceso de inicio de sesión ahora es público para la lista blanca
        
    context.user_data['accion'] = accion
    
    nombres = {'login': 'Código de inicio de sesión', 'travel': 'Estoy de viaje', 'home': 'Actualizar hogar', 'unique': 'Código único', '6digits': 'Código de 6 dígitos'}
    nombre = nombres.get(accion, accion)
    plat = context.user_data.get('plataforma').capitalize()
    
    await query.edit_message_text(text=f"Vas a solicitar: {nombre} para {plat}.\n\nPor favor, envíame el correo de la cuenta:")
    return TYPING_EMAIL

async def get_code_sdnetpanel(email: str, accion: str, panel_user_param: str = None, panel_pass_param: str = None) -> str:
    from playwright.async_api import async_playwright
    import os
    import re
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            # Login
            panel_user = "Gianpierrre@gmail.com"
            panel_pass = "Gianpierrre"
            
            # Cuentas que usan el segundo panel
            cuentas_panel_2 = ["stephaney_kv19021997@hotmail.com"]
            if email.lower() in cuentas_panel_2:
                panel_user = "Gianpierrre02@gmail.com"
                
            await page.goto("https://sdnetpanel.com/login", timeout=30000)
            await page.wait_for_selector("input[type='email'], input[type='text']")
            inputs = page.locator("input")
            await inputs.nth(0).fill(panel_user)
            await inputs.nth(1).fill(panel_pass)
            await page.locator("button:has-text('Login'), button:has-text('Ingresar'), button:has-text('Iniciar sesión'), button[type='submit']").first.click()
            
            # Seleccionar Netflix
            await page.wait_for_selector("text='Netflix'", timeout=20000)
            await page.locator("text='Netflix'").first.click()
            
            # Mapeo de accion
            if accion == 'login':
                opcion_text = 'Códigos de inicio de sesión'
            elif accion == 'travel':
                opcion_text = 'Tu código de acceso temporal'
            elif accion == 'home':
                opcion_text = 'Actualizar Hogar'
            elif accion == '6digits':
                opcion_text = 'Codigo de Verificacion de Inicio de seccion'
            else:
                opcion_text = 'Códigos de inicio de sesión'
                
            await page.wait_for_selector(f"text='{opcion_text}'", timeout=10000)
            await page.locator(f"text='{opcion_text}'").first.click()
            
            # Modal de busqueda
            await page.wait_for_selector("input", timeout=10000)
            
            # Llenar el correo visible
            inputs = page.locator("input")
            count = await inputs.count()
            for i in range(count):
                if await inputs.nth(i).is_visible():
                    await inputs.nth(i).fill(email)
                    break
                    
            # Click Buscar
            await page.locator("button:has-text('Buscar')").click()
            
            # Esperar respuesta: puede tardar hasta 2 minutos según la captura
            # Buscaremos que aparezca texto "De:" o algo que indique que cargó el correo
            try:
                await page.wait_for_selector("text='De:'", timeout=120000) 
            except:
                # Si falla esperamos un poco mas por si acaso
                await page.wait_for_timeout(5000)
                
            await page.wait_for_timeout(2000)
            
            # Extraer el texto del modal
            modal = page.locator(".modal-content, div[role='dialog']").first
            if await modal.is_visible():
                texto = await modal.inner_text()
            else:
                texto = await page.locator("body").inner_text()

            import re
            
            # Buscar código de 6 dígitos
            matches_6 = re.findall(r'\b\d\s*\d\s*\d\s*\d\s*\d\s*\d\b', texto)
            if matches_6:
                codigo = matches_6[0].replace(" ", "")
                return f"🔑 Aquí tienes el código extraído:\n\n`{codigo}`"
                
            # Buscar código de 4 dígitos (excluyendo años comunes del texto)
            matches_4 = re.findall(r'\b\d\s*\d\s*\d\s*\d\b', texto)
            for m in matches_4:
                codigo = m.replace(" ", "")
                if codigo not in ("2023", "2024", "2025", "2026", "2027", "2028"):
                    return f"🔑 Aquí tienes el código extraído:\n\n`{codigo}`"
                    
            # Si la acción fue Actualizar Hogar y Netflix envió un botón/enlace en lugar de un código
            if accion != 'login':
                hrefs = []
                for frame in page.frames:
                    try:
                        frame_hrefs = await frame.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
                        hrefs.extend(frame_hrefs)
                    except:
                        pass
                
                try:
                    html_content = await page.content()
                    for frame in page.frames:
                        try: html_content += await frame.content()
                        except: pass
                    
                    import re as regex_mod
                    # Evitar warning de escape sequence
                    regex_urls = regex_mod.findall(r'https?://[^\s"\'<>]+', html_content)
                    hrefs.extend(regex_urls)
                except:
                    pass

                ignore_list = ['help.netflix.com', 'TermsOfUse', 'privacy', '/browse', 'netflix.com/es/']
                
                for href in hrefs:
                    if 'netflix.com' in href:
                        if not any(ign in href for ign in ignore_list):
                            return f"🔗 Aquí tienes el enlace de Netflix:\n\n{href}"

            # Fallback a captura SOLO si el texto/enlace no se pudo extraer
            path = os.path.join(os.getcwd(), "resultado_sdnetpanel.png")
            if await modal.is_visible():
                await modal.screenshot(path=path)
            else:
                await page.screenshot(path=path)
            return f"SCREENSHOT:{path}"
            
        except Exception as e:
            print(f"Error SDNetPanel: {e}", flush=True)
            return f"❌ Hubo un error al buscar en SDNetPanel. Detalle:\n\n{str(e)}"
        finally:
            await browser.close()

async def get_code_codeflix(email: str, accion: str, panel_user_param: str = None, panel_pass_param: str = None) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://codeflix.cc")
            await page.locator("text='Iniciar sesión'").first.click()
            await page.wait_for_selector("input[type='text']", timeout=5000)
            await page.locator("input[type='text']").fill(WEB_USER)
            await page.locator("input[type='password']").fill(WEB_PASS)
            await page.locator("text='Iniciar sesión'").last.click()
            
            await page.wait_for_selector("text='Buscar código'", timeout=10000)
            await page.wait_for_timeout(2000)
            
            if accion == '6digits':
                # Lógica especial: Ir a la Bandeja
                await page.locator("text='Bandeja'").first.click()
                await page.wait_for_selector("input[placeholder*='Filtrar']", timeout=10000)
                await page.locator("input[placeholder*='Filtrar']").first.fill(email)
                await page.wait_for_timeout(4000) # Dar tiempo a que filtre
                
                texto_bandeja = await page.locator("body").inner_text()
                
                # Tomamos captura por seguridad
                path = os.path.join(os.getcwd(), "resultado_codeflix_bandeja.png")
                await page.screenshot(path=path)
                
                import re
                matches = re.findall(r'\b(\d{6})\b', texto_bandeja)
                if matches:
                    tiempos_min = re.findall(r'hace\s+(\d+)\s+min', texto_bandeja.lower())
                    es_reciente = False
                    if tiempos_min:
                        if int(tiempos_min[0]) <= 15:
                            es_reciente = True
                    elif "justo ahora" in texto_bandeja.lower() or "segundos" in texto_bandeja.lower():
                        es_reciente = True
                        
                    if es_reciente:
                        return f"🔑 Aquí tienes el código de 6 dígitos extraído de la Bandeja:\n\n`{matches[0]}`"
                    else:
                        return f"❌ Se encontró el código `{matches[0]}` en la bandeja, pero tiene MÁS de 15 minutos y ya caducó.\n\nRevisa la captura de la bandeja adjunta:\nSCREENSHOT:{path}"
                else:
                    return f"❌ No se encontró ningún código de 6 dígitos reciente en la Bandeja para este correo.\n\nSCREENSHOT:{path}"

            # Lógica normal para el resto de acciones (4 dígitos, viaje, hogar)
            html_content = (await page.content()).lower()
            
            if email.lower() not in html_content:
                return f"❌ El correo {email} NO se encuentra en la lista de cuentas autorizadas en nuestra base de datos."

            await page.locator("text='Buscar código'").first.click()
            await page.locator("#search-email").fill(email)
            
            if accion == 'login':
                await page.locator("button:has-text('Código de inicio')").first.click()
            elif accion == 'travel':
                await page.locator("button:has-text('Estoy de viaje')").first.click()
            elif accion == 'home':
                await page.locator("button:has-text('Actualizar hogar')").first.click()
                
            try:
                # Esperar a que aparezca la caja de resultados (CodeFlix hace auto-polling, damos 15s)
                await page.wait_for_selector("#search-result .code-box", timeout=15000)
                
                # Validar la fecha (15 mins)
                meta_text = await page.locator("#search-result .code-meta").first.inner_text()
                import re
                from datetime import datetime
                match_date = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4}),\s*(\d{1,2}):(\d{2}):(\d{2})', meta_text)
                if match_date:
                    day, month, year, hour, minute, second = map(int, match_date.groups())
                    dt = datetime(year, month, day, hour, minute, second)
                    diff = (datetime.now() - dt).total_seconds() / 60
                    if diff > 15:
                        return "❌ El último código encontrado tiene más de 15 minutos de antigüedad, por lo tanto ya no es válido."
                
                if accion == 'login':
                    code_val = await page.locator("#search-result .code-value").first.inner_text()
                    return f"🔑 Aquí tienes el código extraído:\n\n`{code_val}`"
                else:
                    link_val = await page.locator("#search-result a").first.get_attribute("href")
                    return f"🔗 Aquí tienes el enlace extraído:\n\n{link_val}"
                    
            except Exception as e:
                print(f"Error extrayendo de CodeFlix: {e}", flush=True)
                
            # Si no se pudo extraer texto exacto, tomar captura
            screenshot_path = os.path.join(os.getcwd(), "resultado.png")
            await page.screenshot(path=screenshot_path)
            return f"SCREENSHOT:{screenshot_path}"
            
        except Exception as e:
            print(f"Error CodeFlix: {e}", flush=True)
            return f"Hubo un error en el sistema. Detalle para depuración:\n\n{str(e)}"
        finally:
            await browser.close()

async def get_code_royplay(email: str, plataforma: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://reseller.royplay.com")
            
            # Esperamos que cargue el titulo para asegurarnos de que la página renderizó
            await page.wait_for_selector("text='Gestión de Códigos'", timeout=15000)
            
            # Buscamos exclusivamente los inputs que NO sean ocultos (hidden)
            visible_inputs = page.locator("input:not([type='hidden'])")
            count = await visible_inputs.count()
            if count >= 2:
                await visible_inputs.nth(0).fill(ROYPLAY_CODE)
                await visible_inputs.nth(1).fill(email)
            else:
                return "❌ No se encontraron los campos visibles en el sistema."
                
            if plataforma == 'disney':
                await page.locator("select#tipo_codigo").select_option("disney")
            else:
                await page.locator("select#tipo_codigo").select_option("amazon_code")
                
            await page.locator("button#searchBtn").click(no_wait_after=True)
            
            try:
                # Esperar a que la lista de emails se pueble
                await page.wait_for_selector("#emailList li", timeout=20000)
            except:
                return "❌ No se encontraron códigos recientes para este correo en la base de datos."
            
            await page.wait_for_timeout(1000)
            
            try:
                # Clic exacto y seguro en el primer correo
                await page.locator("#emailList li").first.click()
            except Exception as e:
                print("Error click:", e, flush=True)
                
            try:
                # Esperar a que el modal se abra
                await page.wait_for_selector("#emailModal.open", timeout=5000)
            except:
                return "❌ No se pudo abrir el mensaje con el código."
            
            modal = page.locator("#emailModal")
            try:
                # Extraer la fecha del HTML nativo del modal
                fecha_text = await page.locator("p:has-text('Fecha')").locator("xpath=following-sibling::p").first.inner_text()
                is_valid, msg = check_15_mins(fecha_text)
                if not is_valid:
                    return msg
            except Exception as e:
                print("Error verificando fecha:", e, flush=True)
                
            texto_email = ""
            try:
                # Extraer el cuerpo del correo desde el div asignado
                div_contenido = page.locator("p:has-text('Contenido')").locator("xpath=following-sibling::div").first
                if await div_contenido.count() > 0:
                    texto_email = await div_contenido.inner_text()
                    await div_contenido.evaluate("el => el.scrollTop = el.scrollHeight")
                else:
                    texto_email = await modal.inner_text()
                    
                await page.wait_for_timeout(1000) 
                
                import re
                match = re.search(r'\b(\d{6})\b', texto_email)
                if match:
                    codigo = match.group(1)
                    return f"🔑 Aquí tienes el código extraído:\n\n`{codigo}`"
                    
            except Exception as e:
                print("Error extrayendo texto:", e, flush=True)
            
            if await modal.count() == 0:
                modal = page
                
            path = os.path.join(os.getcwd(), "resultado_royplay.png")
            await modal.screenshot(path=path)
            return f"SCREENSHOT:{path}"
            
        except Exception as e:
            print(f"Error royplay: {e}", flush=True)
            return f"Hubo un error de conexión con el sistema. Detalle para depuración:\n\n{str(e)}"
        finally:
            await browser.close()



async def get_code_cpanel_imap(email_cuenta: str, password: str, servidor: str) -> str:
    try:
        return await asyncio.wait_for(asyncio.to_thread(_get_code_cpanel_imap_sync, email_cuenta, password, servidor), timeout=25.0)
    except Exception as e:
        return f"❌ Hubo un error de red o timeout al leer {email_cuenta}." 

def _get_code_cpanel_imap_sync(email_cuenta: str, password: str, servidor: str) -> str:
    import imaplib
    import email
    import re
    from datetime import datetime, timezone, timedelta

    try:
        # Intentar conectar al servidor IMAP de cPanel
        mail = imaplib.IMAP4_SSL(servidor, timeout=15)
        mail.login(email_cuenta, password)
        mail.select("inbox")
        
        status, messages = mail.search(None, '(FROM "disneyplus")')
        if status != "OK" or not messages[0]:
            return f"❌ No se encontraron códigos recientes para {email_cuenta}."
            
        email_ids = messages[0].split()
        for e_id in reversed(email_ids[-5:]):
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    date_tuple = email.utils.parsedate_tz(msg.get('Date'))
                    if date_tuple:
                        local_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple), timezone.utc)
                        now = datetime.now(timezone.utc)
                        diff = now - local_date
                        if diff > timedelta(minutes=15):
                            continue
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                try:
                                    body = part.get_payload(decode=True).decode('utf-8', 'ignore')
                                    break
                                except:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode('utf-8', 'ignore')
                        except:
                            pass
                            
                    if not body:
                        continue
                        
                    texto_limpio = re.sub(r'<style.*?>.*?</style>', ' ', body, flags=re.DOTALL | re.IGNORECASE)
                    texto_limpio = re.sub(r'<[^>]+>', ' ', texto_limpio)
                    matches = re.findall(r'(?<!#)\b(\d{6})\b', texto_limpio)
                    codigos_reales = [m for m in matches if m not in ('707070', '000000', 'ffffff')]
                    
                    if codigos_reales:
                        mail.logout()
                        return f"🔑 Aquí tienes el código extraído:\n\n`{codigos_reales[0]}`"

        mail.logout()
        return f"❌ Se encontraron correos para {email_cuenta}, pero ninguno en los últimos 15 min."
        
    except Exception as e:
        print(f"Error IMAP Cpanel para {email_cuenta}: {e}", flush=True)
        return f"❌ Hubo un error de conexión al buzón de {email_cuenta}."


import asyncio
async def get_code_gmail(email_cuenta: str, app_password: str) -> str:
    try:
        return await asyncio.wait_for(asyncio.to_thread(_get_code_gmail_sync, email_cuenta, app_password), timeout=25.0)
    except Exception as e:
        return f"❌ Hubo un error de red o timeout al leer {email_cuenta}." 

def _get_code_gmail_sync(email_cuenta: str, app_password: str) -> str:
    import imaplib
    import email
    from email.header import decode_header
    import re
    from datetime import datetime, timezone, timedelta

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=15)
        mail.login(email_cuenta, app_password.replace(" ", ""))
        mail.select("inbox")

        status, messages = mail.search(None, '(FROM "disneyplus")')
        if status != "OK" or not messages[0]:
            return f"❌ No se encontraron correos de Disney en {email_cuenta}."

        email_ids = messages[0].split()
        for e_id in reversed(email_ids[-5:]):
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    date_tuple = email.utils.parsedate_tz(msg.get('Date'))
                    if date_tuple:
                        local_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple), timezone.utc)
                        now = datetime.now(timezone.utc)
                        diff = now - local_date
                        if diff > timedelta(minutes=15):
                            continue
                            
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                try:
                                    body = part.get_payload(decode=True).decode('utf-8', 'ignore')
                                    break
                                except:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode('utf-8', 'ignore')
                        except:
                            pass
                            
                    if not body:
                        continue

                    texto_limpio = re.sub(r'<style.*?>.*?</style>', ' ', body, flags=re.DOTALL | re.IGNORECASE)
                    texto_limpio = re.sub(r'<[^>]+>', ' ', texto_limpio)
                    matches = re.findall(r'(?<!#)\b(\d{6})\b', texto_limpio)
                    codigos_reales = [m for m in matches if m not in ('707070', '000000', 'ffffff')]
                    
                    if codigos_reales:
                        mail.logout()
                        return f"🔑 Aquí tienes el código extraído de {email_cuenta}:\n\n`{codigos_reales[0]}`"

        mail.logout()
        return "❌ Se encontraron correos de Disney, pero ninguno reciente con un código válido (15 min)."

    except Exception as e:
        print(f"Error IMAP Gmail para {email_cuenta}: {e}", flush=True)
        return f"❌ Hubo un error de conexión al leer {email_cuenta}."

async def get_code_mttmail(email_cliente: str) -> str:
    from playwright.async_api import async_playwright
    import re
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto("https://mttmail.net/", timeout=15000)
            
            # Iniciar sesión si lo pide
            if await page.locator("#usuario").count() > 0:
                await page.locator("#usuario").fill("fstflix")
                await page.locator("#password").fill("12345678")
                await page.locator(".login-submit").click()
                
            # Esperar a que cargue el buscador
            await page.wait_for_selector("#correo", timeout=10000)
            
            # Buscar el correo
            await page.locator("#correo").fill(email_cliente)
            await page.locator(".mail-query-button").click()
            
            # Esperar a que carguen los resultados o el estado de "vacío"
            await page.wait_for_selector(".mail-workspace", timeout=10000)
            
            # Si dice que está vacío
            if await page.locator(".mail-list-empty").is_visible():
                await browser.close()
                return "❌ No hay mensajes recientes (en los últimos 15 minutos) para esta cuenta."
                
            # Intentar extraer el código directo del atributo de copiado que tiene el panel
            botones_codigo = await page.locator("[data-mail-copy-code]").count()
            if botones_codigo > 0:
                codigo = await page.locator("[data-mail-copy-code]").first.get_attribute("data-mail-copy-code")
                if codigo:
                    await browser.close()
                    return f"🔑 Aquí tienes el código extraído:\n\n`{codigo}`"
                    
            # Plan B: Si no hay botón, entrar al primer mensaje y usar nuestra lógica de regex
            links = await page.locator("[data-mail-message-link]").count()
            if links > 0:
                await page.locator("[data-mail-message-link]").first.click()
                await page.wait_for_selector(".mail-reader-panel", timeout=5000)
                
                # Darle 1 segundo al contenido para renderizarse
                await page.wait_for_timeout(1000)
                cuerpo = await page.locator(".mail-reader-panel").inner_html()
                
                texto_limpio = re.sub(r'<style.*?>.*?</style>', ' ', cuerpo, flags=re.DOTALL | re.IGNORECASE)
                texto_limpio = re.sub(r'<[^>]+>', ' ', texto_limpio)
                
                matches = re.findall(r'(?<!#)\b(\d{6})\b', texto_limpio)
                codigos_reales = [m for m in matches if m not in ('707070', '000000', 'ffffff')]
                
                await browser.close()
                if codigos_reales:
                    return f"🔑 Aquí tienes el código extraído:\n\n`{codigos_reales[0]}`"
            
            await browser.close()
            return "❌ Se encontraron mensajes, pero no se pudo extraer el código PIN."
    except Exception as e:
        print(f"Error MTTMail Playwright: {e}", flush=True)
        return "❌ Hubo un error de conexión al buscar en el panel secundario."

async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text
    plataforma = context.user_data.get('plataforma')
    accion = context.user_data.get('accion')
    
    # Registro de uso
    try:
        with open("historial_uso.txt", "a", encoding="utf-8") as f:
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            u = update.effective_user
            nombre = u.username or u.first_name or "Desconocido"
            f.write(f"[{fecha}] Usuario: @{nombre} (ID: {u.id}) | Plataforma: {plataforma} | Acción: {accion} | Correo: {email}\n")
    except:
        pass
        
    msg = await update.message.reply_text("Buscando tu respuesta en la plataforma, espera unos segundos... ⏳")
    
    email_low = email.lower()
    
    # 🧠 Mapeo maestro de contraseñas
    cuentas_data = cargar_cuentas()
    gmail_passwords = cuentas_data.get("gmail_passwords", {})
    cpanel_accounts = cuentas_data.get("cpanel_accounts", {})
    sdnet_emails = cuentas_data.get("sdnet_emails", [])


    # Filtro de Alias Automatico para correos
    base_email = email_low
    if '+' in email_low and email_low.endswith('@gmail.com'):
        base_email = email_low.split('+')[0] + '@gmail.com'

    if plataforma == 'netflix':

        if email_low in sdnet_emails:
            resultado = await get_code_sdnetpanel(email_low, accion)
        else:
            resultado = await get_code_codeflix(email, accion)
    elif plataforma == 'prime':
        resultado = await get_code_royplay(email, plataforma)
    elif plataforma == 'disney' and email_low in cpanel_accounts:
        acc = cpanel_accounts[email_low]
        resultado = await get_code_cpanel_imap(email_low, acc['pass'], acc['server'])
    elif plataforma == 'disney' and base_email in gmail_passwords:
        # El bot va directo al Gmail base usando la contraseña exacta
        resultado = await get_code_gmail(base_email, gmail_passwords[base_email])
    elif email_low.endswith('@mttplay.net') or email_low.endswith('@mttpe.com'):
        resultado = await get_code_mttmail(email_low)
    else:
        resultado = await get_code_royplay(email, plataforma)
    
    if resultado.startswith("SCREENSHOT:"):
        path = resultado.split("SCREENSHOT:")[1]
        try:
            caption_text = "✅ No encontré el texto exacto, pero aquí tienes la captura:"
            await update.message.reply_photo(photo=open(path, 'rb'), caption=caption_text)
        except Exception:
            pass
        await msg.delete()
    else:
        await update.message.reply_text(f"✅ ¡Respuesta obtenida!\n\n{resultado}")
        await msg.delete()
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operación cancelada. Escribe /start para empezar.")
    return ConversationHandler.END



async def add_sdnet(update, context):
    if update.effective_user.id != 5190513736: return
    try:
        email = context.args[0].lower()
        data = cargar_cuentas()
        if email not in data["sdnet_emails"]:
            data["sdnet_emails"].append(email)
            guardar_cuentas(data)
            await update.message.reply_text(f"✅ {email} agregado a SDNetPanel.")
        else:
            await update.message.reply_text("⚠️ El correo ya existía en SDNetPanel.")
    except:
        await update.message.reply_text("📝 Uso correcto: /add_sdnet correo@ejemplo.com")


async def add_sdnet2(update, context):
    if update.effective_user.id != 5190513736: return
    try:
        email = context.args[0].lower()
        data = cargar_cuentas()
        
        # Guardarlo en la lista general para saber que es de SDNetPanel
        if email not in data["sdnet_emails"]:
            data["sdnet_emails"].append(email)
            
        # Y guardarlo en la lista específica del panel 2
        if "sdnet_emails_panel2" not in data:
            data["sdnet_emails_panel2"] = []
            
        if email not in data["sdnet_emails_panel2"]:
            data["sdnet_emails_panel2"].append(email)
            guardar_cuentas(data)
            await update.message.reply_text(f"✅ {email} agregado a SDNetPanel (Acceso Nuevo: Gianpierrre02).")
        else:
            await update.message.reply_text("⚠️ El correo ya existía en el panel nuevo.")
    except:
        await update.message.reply_text("📝 Uso correcto: /add_sdnet2 correo@ejemplo.com")

async def add_gmail(update, context):
    if update.effective_user.id != 5190513736: return
    try:
        email = context.args[0].lower()
        password = context.args[1]
        data = cargar_cuentas()
        data["gmail_passwords"][email] = password
        guardar_cuentas(data)
        await update.message.reply_text(f"✅ {email} agregado a Gmail IMAP.")
    except:
        await update.message.reply_text("📝 Uso correcto: /add_gmail correo@gmail.com pass_de_app")

async def add_cpanel(update, context):
    if update.effective_user.id != 5190513736: return
    try:
        email = context.args[0].lower()
        password = context.args[1]
        server = context.args[2]
        data = cargar_cuentas()
        data["cpanel_accounts"][email] = {"pass": password, "server": server}
        guardar_cuentas(data)
        await update.message.reply_text(f"✅ {email} agregado a cPanel IMAP.")
    except:
        await update.message.reply_text("📝 Uso correcto: /add_cpanel correo@dominio.com password servidor.com")

async def comandos(update, context):
    if update.effective_user.id != 5190513736: return
    texto = """
🛠 <b>COMANDOS DE ADMINISTRADOR</b> 🛠

👥 Gestión de Usuarios:
/agregar [ID] - Autoriza a un usuario
/quitar [ID] - Revoca acceso
/lista - Muestra usuarios autorizados
/mi_id - Muestra el ID del usuario

📊 Estadísticas:
/stats - Uso total
/historial - Descargar historial TXT

⚙️ Gestión de Cuentas (Correos):
/add_sdnet [correo] - Enruta a SDNetPanel (Acceso 1)
/add_sdnet2 [correo] - Enruta a SDNetPanel (Acceso 2)
/add_gmail [correo] [pass_app] - Agrega Gmail (IMAP)
/add_cpanel [correo] [pass] [server] - Agrega cPanel (IMAP)

Nota: Los correos que no agregues con estos comandos irán por defecto a CodeFlix.
"""
    await update.message.reply_text(texto)

def main():
    app = Application.builder().token(TOKEN).connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30).build()
    app.add_handler(CommandHandler("mi_id", mi_id))
    app.add_handler(CommandHandler("agregar", agregar_usuario))
    app.add_handler(CommandHandler("quitar", quitar_usuario))
    app.add_handler(CommandHandler("lista", lista_usuarios))
    app.add_handler(CommandHandler("stats", stats_uso))
    app.add_handler(CommandHandler("historial", ver_historial))
    app.add_handler(CommandHandler("add_sdnet", add_sdnet))
    app.add_handler(CommandHandler("add_sdnet2", add_sdnet2))
    app.add_handler(CommandHandler("add_gmail", add_gmail))
    app.add_handler(CommandHandler("add_cpanel", add_cpanel))
    app.add_handler(CommandHandler("comandos", comandos))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_PLATFORM: [CallbackQueryHandler(platform_handler, pattern="^plat_")],
            CHOOSING_ACTION: [CallbackQueryHandler(action_handler, pattern="^act_|^back_to_start$")],
            TYPING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email),
                CallbackQueryHandler(action_handler, pattern="^back_to_start$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    print("Bot con fix de inputs ocultos iniciado...", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()
