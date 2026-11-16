export const environment = {
  production: true,
  // Same-origin API when the SPA is served by Django / Render.
  // `npm run build:render` may overwrite this from FRONTEND_API_BASE_URL.
  apiBaseUrl: '/api/v1',
  realtimeUrl: '',
  googleClientId: '',
  features: { horses: false },

  firebase: {
    apiKey: '',
    authDomain: '',
    projectId: '',
    messagingSenderId: '',
    appId: '',
    vapidKey: '',
  },
};
