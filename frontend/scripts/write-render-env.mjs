/**
 * Writes environment.prod.ts from Render build-time env vars so the static
 * site talks to this Blueprint's API and realtime hostnames.
 */
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const apiBaseUrl = process.env.FRONTEND_API_BASE_URL || "/api/v1";
const realtimeUrl = process.env.FRONTEND_REALTIME_URL || "";

const source = `export const environment = {
  production: true,
  apiBaseUrl: ${JSON.stringify(apiBaseUrl)},
  realtimeUrl: ${JSON.stringify(realtimeUrl)},
  googleClientId: ${JSON.stringify(process.env.FRONTEND_GOOGLE_CLIENT_ID || "")},

  firebase: {
    apiKey: ${JSON.stringify(process.env.FRONTEND_FIREBASE_API_KEY || "")},
    authDomain: ${JSON.stringify(process.env.FRONTEND_FIREBASE_AUTH_DOMAIN || "")},
    projectId: ${JSON.stringify(process.env.FRONTEND_FIREBASE_PROJECT_ID || "")},
    messagingSenderId: ${JSON.stringify(process.env.FRONTEND_FIREBASE_MESSAGING_SENDER_ID || "")},
    appId: ${JSON.stringify(process.env.FRONTEND_FIREBASE_APP_ID || "")},
    vapidKey: ${JSON.stringify(process.env.FRONTEND_FIREBASE_VAPID_KEY || "")},
  },
};
`;

writeFileSync(resolve(root, "src/environments/environment.prod.ts"), source);
console.log(`Wrote production env → ${apiBaseUrl} / ${realtimeUrl}`);
