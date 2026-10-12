const express = require('express');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

const PORT = 3001;
// JID del bot de WhatsApp proveedor
const TARGET_BOT_JID = '51924746824@s.whatsapp.net';

let sock = null;
let isConnected = false;

// Mapa para gestionar solicitudes en espera: email -> resolve function
const pendingRequests = new Map();

function extractMessageText(msg) {
    if (!msg) return '';
    let m = msg.message || msg;
    if (m.ephemeralMessage) m = m.ephemeralMessage.message;
    if (m.viewOnceMessage) m = m.viewOnceMessage.message;
    if (m.viewOnceMessageV2) m = m.viewOnceMessageV2.message;
    if (m.documentWithCaptionMessage) m = m.documentWithCaptionMessage.message;

    return m.conversation || 
           m.extendedTextMessage?.text || 
           m.templateButtonReplyMessage?.selectedDisplayText || 
           m.buttonsResponseMessage?.selectedDisplayText ||
           m.listResponseMessage?.title ||
           m.imageMessage?.caption ||
           m.videoMessage?.caption ||
           '';
}

function extractCodeOrLink(text) {
    if (!text) return null;

    // 1. Si contiene un enlace (ej. confirmación de hogar, viaje, o inicio de sesión de Netflix)
    const matchUrl = text.match(/https?:\/\/[^\s<>"`]+/i);
    if (matchUrl) {
        return {
            tipo: 'link',
            valor: matchUrl[0].trim()
        };
    }

    // 2. Coincidencia explícita con CÓDIGO, CODIGO, PIN o CLAVE (permitiendo comillas, backticks, asteriscos, espacios)
    // Ej: 🔑 PIN: `3096` | 🔐 CÓDIGO: 266561 | CÓDIGO: `123456` | PIN: 7216
    const matchExplicit = text.match(/(?:C[ÓO]DIGO|PIN|CLAVE)\s*[:=-]?\s*[`*'"\s]*([0-9]{4,8})[`*'"\s]*/i);
    if (matchExplicit) {
        return {
            tipo: 'codigo',
            valor: matchExplicit[1].trim()
        };
    }

    // 3. Coincidencia con emojis de llave 🔑 o candado 🔐 seguidos de un número
    const matchEmoji = text.match(/(?:[🔐🔑])\s*[`*'"\s]*([0-9]{4,8})[`*'"\s]*/);
    if (matchEmoji) {
        return {
            tipo: 'codigo',
            valor: matchEmoji[1].trim()
        };
    }

    // 4. Bloques de 6 dígitos que no sean años (2024, 2025, 2026, 2027)
    const matches6 = text.match(/\b([0-9]{6})\b/g);
    if (matches6) {
        for (const candidate of matches6) {
            if (!['2024', '2025', '2026', '2027'].includes(candidate.substring(0, 4))) {
                return {
                    tipo: 'codigo',
                    valor: candidate.trim()
                };
            }
        }
    }

    // 5. Bloques de 4 dígitos que no sean años (2024..2027)
    const matches4 = text.match(/\b([0-9]{4})\b/g);
    if (matches4) {
        for (const candidate of matches4) {
            if (!['2024', '2025', '2026', '2027'].includes(candidate)) {
                return {
                    tipo: 'codigo',
                    valor: candidate.trim()
                };
            }
        }
    }

    return null;
}

function isFromTargetBot(msg, text) {
    if (msg.key?.fromMe) return false;

    const remoteJid = msg.key?.remoteJid || '';
    const participant = msg.key?.participant || '';

    if (remoteJid.includes('51924746824') || participant.includes('51924746824')) {
        return true;
    }

    // Marcadores característicos del formato del proveedor
    const low = text.toLowerCase();
    if (low.includes('buscando correo') || 
        low.includes('código:') || 
        low.includes('codigo:') || 
        low.includes('pin:') || 
        low.includes('hubo un error con este correo')) {
        return true;
    }

    return false;
}

function processIncomingMessage(msg) {
    if (!msg) return;
    if (msg.key?.fromMe) return;

    const text = extractMessageText(msg).trim();
    if (!text) return;

    if (!isFromTargetBot(msg, text)) return;

    console.log(`[WSP RESPUESTA RECIBIDA]:\n${text}`);

    // Si es el mensaje temporal de búsqueda, ignorarlo
    if (text.toLowerCase().includes('buscando correo') || text.toLowerCase().includes('ok, buscando')) {
        console.log('[WSP] Notificación de búsqueda en proceso (esperando resultado final)...');
        return;
    }

    if (pendingRequests.size === 0) {
        console.log('[WSP] No hay peticiones esperando esta respuesta.');
        return;
    }

    const item = extractCodeOrLink(text);

    for (const [email, resolver] of pendingRequests.entries()) {
        const matchesEmail = text.toLowerCase().includes(email.toLowerCase());

        // Si coincide el email o solo hay una petición pendiente en curso
        if (matchesEmail || pendingRequests.size === 1) {
            if (item) {
                console.log(`[WSP] ✅ ${item.tipo.toUpperCase()} extraído: ${item.valor} para ${email}`);
                resolver({
                    success: true,
                    tipo: item.tipo,
                    codigo: item.valor,
                    raw: text
                });
            } else {
                console.log(`[WSP] ⚠️ Respuesta recibida sin código para ${email}`);
                let errorMsg = text;
                if (text.toLowerCase().includes('hubo un error con este correo')) {
                    errorMsg = 'Hubo un error con este correo en el proveedor. Contacta a soporte.';
                } else if (text.toLowerCase().includes('sin resultado') || text.toLowerCase().includes('no se encontr')) {
                    errorMsg = 'Sin resultados ni códigos recientes para este correo.';
                }
                resolver({
                    success: false,
                    error: errorMsg
                });
            }
            pendingRequests.delete(email);
            break;
        }
    }
}

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

    // Escuchar mensajes nuevos
    sock.ev.on('messages.upsert', async ({ messages }) => {
        for (const msg of messages) {
            processIncomingMessage(msg);
        }
    });

    // Escuchar actualizaciones/descifrado posterior de mensajes
    sock.ev.on('messages.update', async (updates) => {
        for (const update of updates) {
            processIncomingMessage(update);
        }
    });
}

// Endpoint HTTP para consultar código
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
        console.log(`[WSP] Enviando comando: net ${emailNorm}`);
        await sock.sendMessage(TARGET_BOT_JID, { text: `net ${emailNorm}` });

        // Esperar la respuesta (hasta 40 segundos)
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Tiempo de espera agotado (40s) sin respuesta del proveedor.')), 40000)
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
