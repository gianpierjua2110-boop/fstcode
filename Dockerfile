FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc en el disco
ENV PYTHONDONTWRITEBYTECODE 1
# Evitar que Python almacene buffers en memoria (útil para logs)
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Copiar primero el requirements para aprovechar la caché de Docker
COPY requirements.txt .

# Instalar las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar el navegador Chromium de Playwright y sus dependencias de sistema
RUN playwright install chromium --with-deps

# Copiar el resto del código
COPY . .

# Comando para ejecutar el bot
CMD ["python", "bot.py"]
