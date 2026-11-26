const express = require('express');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

const PORT = 3001;
// JID del bot de WhatsApp proveedor (Garu TV)
const TARGET_BOT_JID = '51924746824@s.whatsapp.net';
const ZEYN_OFFICIAL_NUMBER = '977788810';

let sock = null;
let isConnected = false;

// Conjunto de JIDs reconocidos de Garu TV (incluye números directos y LIDs)
const knownGaruJids = new Set([
    '51924746824@s.whatsapp.net',
    TARGET_BOT_JID
]);

// Mapa para gestionar solicitudes en espera: email -> resolve function
const pendingRequests = new Map();
// Caché en memoria para reintentos de descifrado de Baileys
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

function extractCodeOrLink(text) {
    if (!text) return null;

    // Limpiar caracteres invisibles de WhatsApp (LTR, RTL, zero-width, non-breaking space)
    const cleanText = text.replace(/[\u200B-\u200D\uFEFF\u200E\u200F\u00A0]/g, ' ').trim();

    // 1. Si contiene un enlace (ej. confirmación de hogar, viaje, o inicio de sesión de Netflix)
    const matchUrl = cleanText.match(/https?:\/\/[^\s<>"`]+/i);
    if (matchUrl) {
        return {
            tipo: 'link',
            valor: matchUrl[0].trim().replace(/[),.;]+$/, '')
        };
    }

    // 2. Patrón Disney / Garu TV: "Tu código de acceso para Disney+ es 123456"
    const matchDisney = cleanText.match(/(?:c[óo]digo|acceso|disney)[^0-9\n\r]*[\r\n\s:]+([0-9]{4,8})/i);
    if (matchDisney) {
        return {
            tipo: 'codigo',
            valor: matchDisney[1].trim()
        };
    }

    // 3. Coincidencia explícita con CÓDIGO, CODIGO, CODE, PIN, CLAVE o LINK/CODE
    const matchExplicit = cleanText.match(/(?:LINK\/CODE|C[ÓO]DIGO|CODE|PIN|CLAVE)\s*[:=-]?\s*[`*'"\s]*([0-9]{4,8})[`*'"\s]*/i);
    if (matchExplicit) {
        return {
            tipo: 'codigo',
            valor: matchExplicit[1].trim()
        };
    }

    // 4. Coincidencia con emojis de llave o candado seguidos de un número
    const matchEmoji = cleanText.match(/(?:[🔐🔑])\s*[`*'"\s]*([0-9]{4,8})[`*'"\s]*/);
    if (matchEmoji) {
        return {
            tipo: 'codigo',
            valor: matchEmoji[1].trim()
        };
    }

    // 5. Bloques de 6 dígitos que no sean años (2024..2027)
    const matches6 = cleanText.match(/\b([0-9]{6})\b/g);
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

    // 6. Bloques de 4 a 8 dígitos en líneas separadas o tras dos puntos
    const matchLoose = cleanText.match(/(?:^|[\r\n:])\s*([0-9]{4,8})\s*(?:$|[\r\n])/m);
    if (matchLoose) {
        const val = matchLoose[1].trim();
        if (!['2024', '2025', '2026', '2027'].includes(val)) {
            return {
                tipo: 'codigo',
                valor: val
            };
        }
    }

    return null;
}

function isFromTargetBot(msg, text) {
    const key = msg.key || msg.update?.key;
    if (key?.fromMe) return false;

    const remoteJid = key?.remoteJid || '';
    const participant = key?.participant || '';

    // Si coincide con JIDs conocidos de Garu TV
    if (knownGaruJids.has(remoteJid) || knownGaruJids.has(participant)) {
        return true;
    }

    if (remoteJid.includes('51924746824') || participant.includes('51924746824')) {
        if (remoteJid) knownGaruJids.add(remoteJid);
        return true;
    }

    const low = text.toLowerCase();

    // Si coincide con algún correo actualmente en espera
    for (const email of pendingRequests.keys()) {
        if (low.includes(email.toLowerCase())) {
            if (remoteJid) knownGaruJids.add(remoteJid);
            return true;
        }
    }

    // Marcadores característicos del formato del proveedor (Garu TV / Netflix / Disney)
    if (low.includes('buscando correo') || 
        low.includes('ok, buscando') ||
        low.includes('link/code') || 
        low.includes('código') || 
        low.includes('codigo') || 
        low.includes('acceso') ||
        low.includes('disney') ||
        low.includes('netflix') ||
        low.includes('pin:') || 
        low.includes('clave:') ||
        low.includes('email:') ||
        low.includes('asunto:') ||
        low.includes('hubo un error') ||
        low.includes('sin resultado') ||
        low.includes('no se encontr')) {
        if (pendingRequests.size > 0 && remoteJid) {
            knownGaruJids.add(remoteJid);
        }
        return true;
    }

    // Si hay peticiones en espera y el mensaje contiene un código o enlace
    if (pendingRequests.size > 0 && (extractCodeOrLink(text) || low.includes('error'))) {
        if (remoteJid) knownGaruJids.add(remoteJid);
        return true;
    }

    return false;
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

    // Válido si proviene de Zeyn (+51 977 788 810), de uno mismo para pruebas, o contiene el enlace a zeyn.digital
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
                origen: 'whatsapp_server'
            })
        });

        const data = await response.json();
        if (response.ok && data.success) {
            console.log(`[ZEYN] ✅ Pedido procesado con éxito en Fstflix:\n${data.message}`);
        } else {
            console.error(`[ZEYN] ⚠️ Laravel respondió con error:\n${data.message || JSON.stringify(data)}`);
        }
    } catch (err) {
        console.error(`[ZEYN] ❌ Error conectando con Laravel API:`, err.message);
    }
}

function processIncomingMessage(msg) {
    if (!msg) return;
    const key = msg.key || msg.update?.key;
    if (key?.fromMe) return;

    const text = extractMessageText(msg).trim();
    if (!text) return;

    const remoteJid = key?.remoteJid || '';

    // Log para depuración cuando hay peticiones en espera
    if (pendingRequests.size > 0) {
        console.log(`[WSP INCOMING] De: ${remoteJid} | Msg: ${text.replace(/\r?\n/g, ' ').substring(0, 80)}`);
    }

    // 1. Detección y procesamiento automático de pedidos de Zeyn
    if (isZeynOrderMessage(msg, text)) {
        console.log(`[ZEYN] 🔔 ¡Detectado pedido de Zeyn de ${remoteJid}! Procesando en Laravel...`);
        procesarPedidoZeynEnLaravel(text);
        return;
    }

    // 2. Procesamiento de códigos/enlaces de Garu TV
    if (!isFromTargetBot(msg, text)) return;

    console.log(`[GARU TV RESPUESTA RECIBIDA de ${remoteJid}]:\n${text}`);

    if (text.toLowerCase().includes('buscando correo') || text.toLowerCase().includes('ok, buscando')) {
        console.log('[GARU TV] Búsqueda en proceso (esperando resultado final)...');
        return;
    }

    if (pendingRequests.size === 0) {
        console.log('[GARU TV] No hay peticiones esperando esta respuesta.');
        return;
    }

    const item = extractCodeOrLink(text);

    // Intentar resolver la petición
    let resolved = false;

    // 1. Primero intentar coincidir con el correo exacto
    for (const [email, resolver] of pendingRequests.entries()) {
        if (text.toLowerCase().includes(email.toLowerCase())) {
            resolveRequest(email, resolver, item, text);
            resolved = true;
            break;
        }
    }

    // 2. Si no viene el correo en el mensaje (ej: Disney+ no incluye el correo), resolver la petición más antigua
    if (!resolved && pendingRequests.size > 0) {
        const [firstEmail, firstResolver] = pendingRequests.entries().next().value;
        console.log(`[GARU TV] Asociando respuesta sin correo a la petición activa: ${firstEmail}`);
        resolveRequest(firstEmail, firstResolver, item, text);
    }
}

function resolveRequest(email, resolver, item, text) {
    if (item) {
        console.log(`[GARU TV] ✅ ${item.tipo.toUpperCase()} extraído: ${item.valor} para ${email}`);
        resolver({
            success: true,
            tipo: item.tipo,
            codigo: item.valor,
            raw: text
        });
    } else {
        console.log(`[GARU TV] ⚠️ Respuesta recibida sin código para ${email}`);
        let errorMsg = text;
        const low = text.toLowerCase();
        if (low.includes('hubo un error con este correo') || low.includes('hubo un error desconocido')) {
            errorMsg = 'Hubo un error con este correo en el proveedor Garu TV.';
        } else if (low.includes('sin resultado') || low.includes('no se encontr')) {
            errorMsg = 'Sin resultados ni códigos recientes para este correo en Garu TV.';
        }
        resolver({
            success: false,
            error: errorMsg,
            raw: text
        });
    }
    pendingRequests.delete(email);
}

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('wsp_auth_info');

    sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        logger: pino({ level: 'silent' }),
        browser: ['Fstflix Garu Bot', 'Chrome', '1.0.0'],
        getMessage: async (key) => {
            return msgStore.get(key.id) || undefined;
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log("\n==================================================================");
            console.log("ESCANEÁ ESTE CÓDIGO QR CON TU WHATSAPP DE GARU TV (+51 974 140 091):");
            console.log("==================================================================\n");
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('[GARU TV] Conexión cerrada. Reconectando...', shouldReconnect);
            isConnected = false;
            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 3000);
            }
        } else if (connection === 'open') {
            console.log('✅ ¡WhatsApp de Garu TV Conectado exitosamente (+51 974 140 091)!');
            isConnected = true;
        }
    });

    // Escuchar mensajes nuevos
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

    // Escuchar actualizaciones (reintentos de descifrado, mensajes temporales, etc.)
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

// Endpoint HTTP para consultar código desde Laravel/Telegram
app.post('/api/wsp/get-code', async (req, res) => {
    const { email, plataforma } = req.body;
    if (!email) {
        return res.status(400).json({ success: false, error: 'Falta el correo electrónico' });
    }

    if (!isConnected || !sock) {
        return res.status(503).json({ success: false, error: 'WhatsApp de Garu TV no está conectado en el servidor (+51 974 140 091).' });
    }

    const emailNorm = email.toLowerCase().trim();
    const platNorm = (plataforma || 'netflix').toLowerCase().trim();

    // Prefijo según la plataforma: 'dis' para Disney, 'net' para Netflix
    const prefijo = platNorm.includes('dis') ? 'dis' : 'net';
    const comando = `${prefijo} ${emailNorm}`;

    try {
        console.log(`[GARU TV] Enviando comando: ${comando}`);
        await sock.sendMessage(TARGET_BOT_JID, { text: comando });

        // Esperar la respuesta (hasta 55 segundos)
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Tiempo de espera agotado (55s) sin respuesta de Garu TV.')), 55000)
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
    res.json({ service: 'garu-tv', connected: isConnected, phone: '+51 974 140 091' });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Garu TV Bot Server] Escuchando en puerto ${PORT}...`);
    connectToWhatsApp();
});
