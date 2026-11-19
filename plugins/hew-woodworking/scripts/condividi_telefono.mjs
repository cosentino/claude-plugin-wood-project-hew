// Carica un .hew sul relay di app.hew3d.com e stampa il link per aprirlo dal telefono.
// Stesso protocollo di "File > Open on Phone" nell'app (shells/tauri/src-tauri/src/relay_client.rs,
// app/src/panels/PhoneShareDialog.tsx): file cifrato AES-256-GCM in locale ([IV 12 byte][cifrato+tag]),
// PUT /relay/drop -> {"token"}, link https://app.hew3d.com/#recv=<token>.<chiave base64url>.<nome>.
// La chiave resta nel frammento del link: il server non può leggere il modello. Il deposito è temporaneo.
// Uso: node condividi_telefono.mjs <file.hew> <nome>
import { readFileSync } from 'node:fs';
import { webcrypto as c } from 'node:crypto';
const [file, name] = process.argv.slice(2);
const bytes = readFileSync(file);
const raw = c.getRandomValues(new Uint8Array(32));
const key = await c.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt']);
const iv = c.getRandomValues(new Uint8Array(12));
const ct = new Uint8Array(await c.subtle.encrypt({ name: 'AES-GCM', iv }, key, bytes));
const body = new Uint8Array(12 + ct.length); body.set(iv); body.set(ct, 12);
const res = await fetch('https://app.hew3d.com/relay/drop', { method: 'PUT', headers: { 'Content-Type': 'application/octet-stream' }, body });
const text = await res.text();
if (!res.ok) { console.error('HTTP', res.status, text); process.exit(1); }
const { token } = JSON.parse(text);
const b64u = Buffer.from(raw).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
console.log(`https://app.hew3d.com/#recv=${token}.${b64u}.${encodeURIComponent(name)}`);
const head = await fetch(`https://app.hew3d.com/relay/drop/${token}`, { method: 'HEAD' });
console.error('verifica HEAD:', head.status);
