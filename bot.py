import os
import asyncio
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from playwright.async_api import async_playwright

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
WEB_USER = os.getenv("WEB_USER", "Gianpierre")
WEB_PASS = os.getenv("WEB_PASS", "gianpier21")
ROYPLAY_CODE = "GIANPI4869"

CHOOSING_PLATFORM, CHOOSING_ACTION, TYPING_EMAIL = range(3)

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
        keyboard = [
            [InlineKeyboardButton("Código de inicio de sesión", callback_data="act_login")],
            [InlineKeyboardButton("Estoy de viaje", callback_data="act_travel")],
            [InlineKeyboardButton("Actualizar hogar", callback_data="act_home")],
            [InlineKeyboardButton("🔙 Volver", callback_data="back_to_start")]
        ]
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
    context.user_data['accion'] = accion
    
    nombres = {'login': 'Código de inicio de sesión', 'travel': 'Estoy de viaje', 'home': 'Actualizar hogar', 'unique': 'Código único'}
    nombre = nombres.get(accion, accion)
    plat = context.user_data.get('plataforma').capitalize()
    
    await query.edit_message_text(text=f"Vas a solicitar: {nombre} para {plat}.\n\nPor favor, envíame el correo de la cuenta:")
    return TYPING_EMAIL

async def get_code_codeflix(email: str, accion: str) -> str:
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
                
            await page.locator("button#searchBtn").click()
            
            try:
                # Esperar a que la lista de emails se pueble
                await page.wait_for_selector("#emailList li", timeout=10000)
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

async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text
    plataforma = context.user_data.get('plataforma')
    accion = context.user_data.get('accion')
    
    msg = await update.message.reply_text("Buscando tu respuesta en la plataforma, espera unos segundos... ⏳")
    
    if plataforma == 'netflix':
        resultado = await get_code_codeflix(email, accion)
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
        await update.message.reply_text(f"✅ ¡Respuesta obtenida!\n\n{resultado}", parse_mode="Markdown")
        await msg.delete()
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operación cancelada. Escribe /start para empezar.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30).build()
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
