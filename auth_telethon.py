import os
import asyncio
from telethon import TelegramClient

API_ID = int(os.getenv("TELEGRAM_API_ID", 33736577))
API_HASH = os.getenv("TELEGRAM_API_HASH", "44b2c837add09429129c81f9910d68ef")
SESSION_NAME = "telethon_session"

async def main():
    print("="*50)
    print("INICIANDO AUTENTICACIÓN TELETHON CON TU CUENTA")
    print("="*50)
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    
    me = await client.get_me()
    print("\n" + "="*50)
    print(f"¡CONECTADO CON ÉXITO COMO: {me.first_name} (ID: {me.id})!")
    print("El archivo de sesión ha sido guardado.")
    print("="*50)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
