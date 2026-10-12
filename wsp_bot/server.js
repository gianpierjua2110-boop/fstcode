const express = require('express');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

const PORT = 3001;
// Número del Bot Garu Tv en formato internacional JID de WhatsApp
const TARGET_BOT_JID = '51924746824@s.whatsapp.net';

let sock = null;
let isConnected = false;

// Mapa para gestionar solicitudes en espera: email -> resolve function
const pendingRequests = new Map();

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('wsp_auth_info');

    sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        logger: pino({ level: 'silent' }),
        browser: ['Fstflix Code Bot', 'Chrome', '1.0.0']
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log("\n=======================================================");
            console.log("ESCANEÁ ESTE CÓDIGO QR DESDE TU WHATSAPP (+51 974 140 091):");
            console.log("=======================================================\n");
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('Conexión con WhatsApp cerrada. Reconectando...', shouldReconnect);
            isConnected = false;
            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 3000);
            }
        } else if (connection === 'open') {
            console.log('✅ ¡WhatsApp Conectado exitosamente como +51 974 140 091!');
            isConnected = true;
        }
    });

    // Escuchar mensajes entrantes de WhatsApp
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        for (const msg of messages) {
            if (!msg.message) continue;

            const sender = msg.key.remoteJid || '';
            // Solo nos interesan los mensajes que vienen del Bot Garu Tv
            if (!sender.includes('51924746824')) continue;

            // Extraer el texto del mensaje desenvolviendo mensajes anidados
            let m = msg.message;
            if (m.ephemeralMessage) m = m.ephemeralMessage.message;
            if (m.viewOnceMessage) m = m.viewOnceMessage.message;
            if (m.viewOnceMessageV2) m = m.viewOnceMessageV2.message;

            const text = m.conversation || 
                         m.extendedTextMessage?.text || 
                         m.templateButtonReplyMessage?.selectedDisplayText || 
                         m.buttonsResponseMessage?.selectedDisplayText || '';

            if (!text) continue;

            // Ignorar el mensaje intermedio de "Ok, buscando correo..."
            if (text.includes("Ok, buscando correo") || text.includes("buscando correo")) {
                console.log(`[WSP] Mensaje intermedio de carga recibido: "${text.trim()}" (ignorando...)`);
                continue;
            }

            console.log(`[WSP BOT RESPUESTA RECIBIDA]:\n${text}`);

            // Buscar si hay una petición en espera que coincida
            for (const [email, resolver] of pendingRequests.entries()) {
                const matchesEmail = text.toLowerCase().includes(email.toLowerCase());
                
                // Si contiene el email o hay exactamente 1 solicitud pendiente
                if (matchesEmail || pendingRequests.size === 1) {
                    // Extraer CÓDIGO o PIN de la respuesta
                    // Formato: 🔐 CÓDIGO: 266561 o 🔑 PIN: 7216 o 6 dígitos
                    let match = text.match(/(?:C[ÓO]DIGO|PIN):\s*([0-9]{4,8})/i);
                    let codigo = null;
                    if (match) {
                        codigo = match[1];
                    } else {
                        // Buscar cualquier bloque de 4 a 6 dígitos en el mensaje
                        const fallbackDigits = text.match(/\b([0-9]{4,6})\b/);
                        if (fallbackDigits) {
                            codigo = fallbackDigits[1];
                        }
                    }

                    if (codigo) {
                        resolver({
                            success: true,
                            codigo: codigo,
                            raw: text
                        });
                        pendingRequests.delete(email);
                        break;
                    } else if (text.toLowerCase().includes("no se encontr") || 
                               text.toLowerCase().includes("sin c") || 
                               text.toLowerCase().includes("no registrado") ||
                               text.toLowerCase().includes("sin resultado")) {
                        resolver({
                            success: false,
                            error: text.trim()
                        });
                        pendingRequests.delete(email);
                        break;
                    }
                }
            }
        }
    });
}

// Endpoint HTTP para que el bot de Python o Laravel pidan el código
app.post('/api/wsp/get-code', async (req, res) => {
    const { email } = req.body;
    if (!email) {
        return res.status(400).json({ success: false, error: 'Falta el correo electrónico' });
    }

    if (!isConnected || !sock) {
        return res.status(503).json({ success: false, error: 'WhatsApp no está conectado aún en el servidor.' });
    }

    const emailNorm = email.toLowerCase().trim();

    try {
        console.log(`[WSP] Enviando comando para: net ${emailNorm}`);
        // Enviar el comando al Bot Garu Tv
        await sock.sendMessage(TARGET_BOT_JID, { text: `net ${emailNorm}` });

        // Esperar la respuesta (hasta 25 segundos)
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Tiempo de espera agotado (25s) sin respuesta de Bot Garu Tv.')), 25000)
        );

        const responsePromise = new Promise((resolve) => {
            pendingRequests.set(emailNorm, resolve);
        });

        const resultado = await Promise.race([responsePromise, timeoutPromise]);
        return res.json(resultado);

    } catch (err) {
        pendingRequests.delete(emailNorm);
        return res.status(500).json({ success: false, error: err.message });
    }
});

app.get('/status', (req, res) => {
    res.json({ connected: isConnected });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`[WSP Server] Escuchando en puerto ${PORT}...`);
    connectToWhatsApp();
});
