export const msalConfig = {
  auth: {
    clientId: "a35f3d1a-4240-4503-b393-b31e7c7e771d",
    authority: "https://login.microsoftonline.com/9a3bb301-12fd-4106-a7f7-563f72cfdf69",
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  }
};

export const loginRequest = {
  scopes: ["User.Read"]
};
