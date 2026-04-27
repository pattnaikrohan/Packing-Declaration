import React from 'react';
import { useMsal } from "@azure/msal-react";
import { loginRequest } from "../authConfig";

const LoginPage = () => {
  const { instance } = useMsal();

  const handleLogin = () => {
    instance.loginPopup(loginRequest).catch(e => {
      console.error(e);
    });
  };

  return (
    <div className="neural-login-container">
      <div className="login-bg-effects">
        <div className="neural-grid-floor" />
        <div className="login-glow-orb orb-1" />
        <div className="login-glow-orb orb-2" />
      </div>

      <div className="login-card-v2">
        <div className="card-top-accent" />
        <div className="login-header">
          <div className="login-logo-container">
            <img src="/aaw.png" alt="AAW Logo" className="login-logo-img" />
          </div>
          <h1>Packing Declaration Validator</h1>
          <p classDashboardName="login-subtitle">DAFF COMPLIANCE · AUDIT INTERFACE</p>
        </div>

        <div className="login-body">
          <div className="access-status">
            <span className="status-dot pulsing" />
            SYSTEM_UPLINK_PENDING
          </div>

          <button className="ms-login-btn" onClick={handleLogin}>
            <div className="ms-logo">
              <div className="ms-tile tile-red" />
              <div className="ms-tile tile-green" />
              <div className="ms-tile tile-blue" />
              <div className="ms-tile tile-yellow" />
            </div>
            <span className="btn-text">SECURE LOGIN WITH MICROSOFT</span>
            <div className="btn-hover-glow" />
          </button>

          <div className="login-footer-meta">
            <div className="meta-item">ENCRYPTION: AES_256_GCM</div>
            <div className="meta-item">SECURE_TUNNEL: ACTIVE</div>
          </div>
        </div>
      </div>

      <style>{`
        .neural-login-container {
          position: fixed; inset: 0; background: #010105;
          display: flex; align-items: center; justify-content: center;
          font-family: 'Outfit', sans-serif; overflow: hidden;
        }

        .login-bg-effects { position: absolute; inset: 0; z-index: 0; }
        .neural-grid-floor {
          position: absolute; inset: 0;
          background-image: 
            linear-gradient(rgba(34, 211, 238, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(34, 211, 238, 0.05) 1px, transparent 1px);
          background-size: 60px 60px;
          transform: perspective(1000px) rotateX(60deg) translateY(100px);
          opacity: 0.5;
        }
        .login-glow-orb { position: absolute; width: 600px; height: 600px; border-radius: 50%; filter: blur(150px); opacity: 0.15; }
        .orb-1 { background: var(--accent); top: -200px; right: -200px; }
        .orb-2 { background: var(--accent-cyan); bottom: -200px; left: -200px; }

        .login-card-v2 {
          width: 480px; background: rgba(2, 2, 10, 0.8);
          backdrop-filter: blur(40px); border: 1px solid rgba(255,255,255,0.08);
          border-radius: 32px; position: relative; z-index: 10;
          box-shadow: 0 40px 100px rgba(0,0,0,0.8);
          animation: card-uplink 0.8s cubic-bezier(0.2, 0, 0.2, 1);
        }
        @keyframes card-uplink {
          from { opacity: 0; transform: translateY(40px) scale(0.95); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .card-top-accent {
          position: absolute; top: 0; left: 100px; right: 100px; height: 3px;
          background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
          box-shadow: 0 0 20px var(--accent-cyan);
        }

        .login-header { padding: 60px 40px 30px; text-align: center; }
        .login-logo-container { position: relative; width: 120px; height: auto; margin: 0 auto 30px; display: flex; align-items: center; justify-content: center; }
        .login-logo-img { width: 100%; height: auto; object-fit: contain; filter: drop-shadow(0 0 15px rgba(34, 211, 238, 0.3)); }

        .login-header h1 { font-size: 1.8rem; font-weight: 900; color: #fff; margin-bottom: 10px; letter-spacing: -0.5px; }
        .login-subtitle { font-size: 0.7rem; font-weight: 900; letter-spacing: 0.3em; color: rgba(255,255,255,0.3); }

        .login-body { padding: 0 60px 60px; display: flex; flex-direction: column; align-items: center; }
        
        .access-status {
          display: flex; align-items: center; gap: 10px; margin-bottom: 40px;
          font-size: 0.65rem; font-weight: 900; letter-spacing: 0.15em; color: rgba(255,255,255,0.4);
        }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; background: #facc15; }
        .status-dot.pulsing { animation: pulse-yellow 2s infinite; }
        @keyframes pulse-yellow { 0%,100%{opacity:1;box-shadow:0 0 5px #facc15} 50%{opacity:0.3;box-shadow:0 0 15px #facc15} }

        .ms-login-btn {
          width: 100%; height: 64px; background: #fff; border: none; border-radius: 12px;
          display: flex; align-items: center; justify-content: center; gap: 20px;
          cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          position: relative; overflow: hidden;
        }
        .ms-login-btn:hover { transform: translateY(-5px); box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
        
        .ms-logo { display: grid; grid-template-columns: 1fr 1fr; gap: 2px; }
        .ms-tile { width: 9px; height: 9px; }
        .tile-red { background: #f35325; }
        .tile-green { background: #81bc06; }
        .tile-blue { background: #05a6f0; }
        .tile-yellow { background: #ffba08; }

        .btn-text { font-size: 0.8rem; font-weight: 800; color: #1a1a1a; letter-spacing: 0.05em; }

        .login-footer-meta {
          margin-top: 50px; width: 100%; display: flex; justify-content: space-between;
          border-top: 1px solid rgba(255,255,255,0.05); padding-top: 25px;
        }
        .meta-item { font-size: 0.55rem; font-weight: 900; color: rgba(255,255,255,0.2); letter-spacing: 0.1em; }
      `}</style>
    </div>
  );
};

export default LoginPage;
