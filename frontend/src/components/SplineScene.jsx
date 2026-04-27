import { Suspense, lazy } from 'react';

const Spline = lazy(() => import('@splinetool/react-spline'));

/**
 * SplineScene — lazy-loaded Spline wrapper.
 * Covers the "Built with Spline" watermark in the top-right corner.
 */
export default function SplineScene({ scene, className = '', onLoad }) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Suspense
        fallback={
          <div className="spline-fallback">
            <div className="spline-loader" />
          </div>
        }
      >
        <Spline
          scene={scene}
          className={className}
          onLoad={onLoad}
          style={{ width: '100%', height: '100%' }}
        />
      </Suspense>

      {/* ── TOP-RIGHT watermark blocker ─────────────────────────────────
          The Spline "Built with Spline" badge sits in the top-right.
          We cover it with a background-matching gradient patch.        */}
      <div
        aria-hidden="true"
        style={{
          position:      'absolute',
          top:           0,
          right:         0,
          width:         '200px',
          height:        '60px',
          background:    'linear-gradient(to bottom left, #050510 55%, transparent)',
          pointerEvents: 'none',
          zIndex:        30,
        }}
      />

      <style>{`
        .spline-fallback {
          display: flex;
          width: 100%;
          height: 100%;
          align-items: center;
          justify-content: center;
          background: transparent;
        }
        .spline-loader {
          width: 40px;
          height: 40px;
          border: 3px solid rgba(255,255,255,0.08);
          border-top-color: #8b5cf6;
          border-radius: 50%;
          animation: spline-spin 0.8s linear infinite;
        }
        @keyframes spline-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
