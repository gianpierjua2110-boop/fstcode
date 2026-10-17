from cuentas_manager import cargar_cuentas, guardar_cuentas
from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import sys
import os

from bot import get_code_sdnetpanel, get_code_codeflix

app = Flask(__name__)
# Permite peticiones desde cualquier dominio (Hostinger)
CORS(app)

def correr_scraping(email):
    cuentas_data = cargar_cuentas()
    sdnet_emails = cuentas_data.get('sdnet_emails', [])
    
    # Creamos un nuevo loop asincrono para aislar este hilo del resto
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    email_low = email.lower()
    try:
        # Aquí forzamos siempre la accion "travel" ("Estoy de viaje")
        if email_low in sdnet_emails:
            resultado = loop.run_until_complete(get_code_sdnetpanel(email_low, 'travel'))
        else:
            resultado = loop.run_until_complete(get_code_codeflix(email_low, 'travel'))
        return resultado
    except Exception as e:
        return f"❌ Error interno: {str(e)}"
    finally:
        loop.close()

@app.route('/api/get_code', methods=['GET'])
def api_get_code():
    email = request.args.get('email', '').strip()
    if not email:
        return jsonify({'status': 'error', 'message': 'Falta el correo electrónico.'})

    import re
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return jsonify({'status': 'error', 'message': '⚠️ Por favor ingresa un correo electrónico válido (ejemplo: usuario@correo.com).'})
        
    resultado = correr_scraping(email)
    
    # Si el bot devuelve un error
    if "❌" in resultado or "Error" in resultado or "NO se encuentra" in resultado:
        return jsonify({'status': 'error', 'message': resultado})
        
    import re
    # Buscar si hay un enlace en la respuesta
    link_match = re.search(r'https?://[^\s"\'<>]+', resultado)
    if link_match:
        link = link_match.group(0)
        return jsonify({'status': 'ok', 'link': link})
        
    # Buscar si hay un código numérico (4 o 6 dígitos)
    code_match = re.search(r'\b\d{4,6}\b', resultado)
    if code_match:
        return jsonify({'status': 'ok', 'code': code_match.group(0)})
        
    # Si el bot devuelve una imagen
    if resultado.startswith("SCREENSHOT:"):
        path = resultado.split("SCREENSHOT:")[1].strip()
        try:
            import base64
            with open(path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            img_html = f"No encontré el texto exacto, pero aquí tienes la captura de lo que llegó al correo:<br><br><img src='data:image/png;base64,{encoded_string}' style='max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);'>"
            return jsonify({'status': 'error', 'message': img_html})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Se generó una captura pero no se pudo leer el archivo: {e}'})
            
    # Si devuelve otro error de texto
    return jsonify({'status': 'error', 'message': resultado})

if __name__ == '__main__':
    # Correr en todas las interfaces en el puerto 8080
    app.run(host='0.0.0.0', port=8080)
