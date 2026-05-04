import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
// ── MSAL disabled temporarily (re-enable when redirect URI is configured) ──
// import { PublicClientApplication } from "@azure/msal-browser"
// import { MsalProvider } from "@azure/msal-react"
// import { msalConfig } from "./authConfig"
import App from './App'
import './index.css'

// const msalInstance = new PublicClientApplication(msalConfig);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* <MsalProvider instance={msalInstance}> */}
      <BrowserRouter>
        <App />
        <Toaster
          position="top-right"
          toastOptions={{
            className: 'toast-dark',
            duration: 4000,
            style: {
              background: '#1a2235',
              color: '#f1f5f9',
              border: '1px solid rgba(255,255,255,0.08)',
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
            },
          }}
        />
      </BrowserRouter>
    {/* </MsalProvider> */}
  </React.StrictMode>
)
