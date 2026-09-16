export const environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8000/api/v1',
  realtimeUrl: 'http://localhost:4000',
  googleClientId: '',

  /**
   * Web push config. Copy these from the Firebase console (Project settings →
   * General → Your apps → Web app) and paste the Web Push certificate key pair
   * into `vapidKey`. Leave `apiKey` blank to disable push in the browser.
   */
  firebase: {
    apiKey: '',
    authDomain: '',
    projectId: '',
    messagingSenderId: '',
    appId: '',
    vapidKey: '',
  },
};
