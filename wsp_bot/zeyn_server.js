const express = require('express');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

const PORT = process.env.ZEYN_PORT || 3002;
const ZEYN_OFFICIAL_NUMBER = '977788810';

let sock = null;
let isConnected = false;
const msgStore = new Map();

function extractMessageText(msg) {
    if (!msg) return '';
    let m = msg.update?.message || msg.message || msg;

    // Desempaquetar capas anidadas de Baileys / WhatsApp
    let depth = 0;
    while (m && depth < 10) {
        depth++;
        if (m.ephemeralMessage?.message) {
            m = m.ephemeralMessage.message;
        } else if (m.viewOnceMessage?.message) {
            m = m.viewOnceMessage.message;
        } else if (m.viewOnceMessageV2?.message) {
            m = m.viewOnceMessageV2.message;
        } else if (m.documentWithCaptionMessage?.message) {
            m = m.documentWithCaptionMessage.message;
        } else if (m.editedMessage?.message) {
            m = m.editedMessage.message;
        } else {
            break;
        }
    }

    if (!m) return '';

    return m.conversation || 
           m.extendedTextMessage?.text || 
           m.interactiveMessage?.body?.text ||
           m.interactiveResponseMessage?.body?.text ||
           m.templateMessage?.hydratedTemplate?.hydratedContentText ||
           m.templateButtonReplyMessage?.selectedDisplayText || 
           m.buttonsResponseMessage?.selectedDisplayText ||
           m.listResponseMessage?.title ||
           m.imageMessage?.caption ||
           m.videoMessage?.caption ||
           '';
}

function isZeynOrderMessage(msg, text) {
    if (!text) return false;

    const low = text.toLowerCase();

    // Marcadores estructurales de pedidos de Zeyn
    const hasOrderMarker = low.includes('nuevo pedido') || 
                           low.includes('pedido renovado') || 
                           low.includes('zeyn.digital');

    const hasDetailMarker = low.includes('perfil') || 
                            low.includes('asiento:') || 
                            low.includes('stock restante') || 
                            low.includes('vencimiento') || 
                            low.includes('vence:');

    if (!hasOrderMarker || !hasDetailMarker) {
        return false;
    }

    const key = msg?.key || msg?.update?.key;
    const remoteJid = key?.remoteJid || '';
    const participant = key?.participant || '';
    const fromMe = Boolean(key?.fromMe);

    // Válido si proviene de Zeyn (+51 977 788 810), de uno mismo para pruebas, o contiene el enlace a zeyn.digital (LID)
    const isFromZeynNumber = remoteJid.includes(ZEYN_OFFICIAL_NUMBER) || 
                             participant.includes(ZEYN_OFFICIAL_NUMBER) || 
                             fromMe;
    const hasZeynDomain = low.includes('zeyn.digital');

    return isFromZeynNumber || hasZeynDomain;
}

async function procesarPedidoZeynEnLaravel(texto) {
    const laravelUrl = process.env.LARAVEL_API_URL || 'https://fstflix.com';
    const botToken = process.env.BOT_API_TOKEN || 'fstflix_super_secret_bot_token_2026';

    try {
        console.log('[ZEYN] 🔔 Mensaje de pedido Zeyn detectado. Enviando a Laravel...');
        const response = await fetch(`${laravelUrl}/api/bot/procesar-pedido-zeyn`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${botToken}`
            },
            body: JSON.stringify({
                mensaje: texto,
                origen: 'whatsapp_zeyn'
            })
        });

        const data = await response.json();
        console.log(`[ZEYN] 📋 Respuesta Laravel (HTTP ${response.status}): ${JSON.stringify(data)}`);
        if (response.ok && data.success) {
            console.log(`[ZEYN] ✅ Pedido procesado: ${data.message}`);
        } else {
            console.error(`[ZEYN] ⚠️ Laravel respondió con error: ${data.message || JSON.stringify(data)}`);
        }
    } catch (err) {
        console.error(`[ZEYN] ❌ Error conectando con Laravel API:`, err.message);
    }
}

function processIncomingMessage(msg) {
    if (!msg) return;
    const key = msg.key || msg.update?.key;

    const text = extractMessageText(msg).trim();
    if (!text) return;

    const sender = key?.remoteJid || 'desconocido';
    console.log(`[ZEYN WSP ENTRANTE de ${sender}]: ${text.replace(/\r?\n/g, ' ').substring(0, 75)}...`);

    if (isZeynOrderMessage(msg, text)) {
        console.log('[ZEYN] 🔔 ¡Detectado pedido de Zeyn! Texto completo:');
        console.log('--- INICIO TEXTO ---');
        console.log(text);
        console.log('--- FIN TEXTO ---');
        procesarPedidoZeynEnLaravel(text);
    }
}

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('zeyn_auth_info');

    sock = makeWASocket({
        auth: state,
        logger: pino({ level: 'silent' }),
        browser: ['Fstflix Zeyn Bot', 'Chrome', '1.0.0'],
        getMessage: async (key) => {
            return msgStore.get(key.id) || undefined;
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log("\n==================================================================");
            console.log("ESCANEÁ ESTE CÓDIGO QR CON TU WHATSAPP DE ZEYN (+51 982 409 360):");
            console.log("==================================================================\n");
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('[ZEYN BOT] Conexión cerrada. Reconectando...', shouldReconnect);
            isConnected = false;
            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 3000);
            }
        } else if (connection === 'open') {
            console.log('✅ ¡WhatsApp de ZEYN Conectado exitosamente (+51 982 409 360)!');
            isConnected = true;
        }
    });

    sock.ev.on('messages.upsert', async ({ messages }) => {
        for (const msg of messages) {
            if (msg.key?.id && msg.message) {
                msgStore.set(msg.key.id, msg.message);
                if (msgStore.size > 200) {
                    const firstKey = msgStore.keys().next().value;
                    msgStore.delete(firstKey);
                }
            }
            processIncomingMessage(msg);
        }
    });

    // Escuchar actualizaciones (reintentos de descifrado posterior tras Bad MAC / prekeys)
    sock.ev.on('messages.update', async (updates) => {
        for (const update of updates) {
            const rawMsg = update.update?.message || update.message || (update.key?.id ? msgStore.get(update.key.id) : null);
            if (update.key?.id && rawMsg) {
                msgStore.set(update.key.id, rawMsg);
            }
            processIncomingMessage({
                key: update.key,
                message: rawMsg,
                update: update.update
            });
        }
    });
}

app.get('/status', (req, res) => {
    res.json({ service: 'zeyn-listener', connected: isConnected, phone: '+51 982 409 360' });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Zeyn Bot Server] Escuchando en puerto ${PORT}...`);
    connectToWhatsApp();
});
