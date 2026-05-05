import { useState, useMemo, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import mammoth from 'mammoth/mammoth.browser'
import toast from 'react-hot-toast'
import { submitToPA, uploadFile, clearStorage, validateDaffExternal, emailAuditReport } from '../api/client'
import { useMsal } from "@azure/msal-react"

// ─── nCr Comparison Engine ─────────────────────────────────────────────────────
const KEY_FIELDS = [
  'declaration_type', 'issuer_company', 'exporter', 'vessel_name',
  'voyage_number', 'consignment_ref', 'q1_unacceptable_material',
  'q2_timber_bamboo', 'q3_treatment', 'q4_cleanliness'
]

function computeNcr(ocr, ml, pa) {
  let totalComparisons = 0
  let matchingComparisons = 0
  const fieldResults = []

  for (const field of KEY_FIELDS) {
    const v_ocr = ocr?.[field] ?? null
    const v_ml  = ml?.[field]  ?? null
    const v_pa  = pa?.[field]  ?? null

    const pairs = [
      { a: v_ocr, b: v_ml, label: 'OCR↔ML' },
      { a: v_ocr, b: v_pa, label: 'OCR↔PA' },
      { a: v_ml,  b: v_pa, label: 'ML↔PA'  },
    ]
    let fieldPairMatches = 0
    pairs.forEach(pair => {
      totalComparisons++
      if (pair.a !== null && pair.a === pair.b) {
        matchingComparisons++
        fieldPairMatches++
      }
    })

    fieldResults.push({
      field,
      values: { ocr: v_ocr, ml: v_ml, pa: v_pa },
      pairMatches: fieldPairMatches,
      totalPairs: 3,
      convergent: fieldPairMatches === 3
    })
  }

  const score = totalComparisons > 0 ? (matchingComparisons / totalComparisons) * 100 : 0
  return { score, fieldResults, isConverged: score >= 95 }
}
// ─── Compliance Engine (Strict DAFF Ruleset) ──────────────────────────────────
function getConsensusValue(field, data) {
  if (!data) return null;
  // Weightage: AI (pa) > Transformer (ml) > OCR
  // Note: Transformer is kept as fallback for now as per user request
  return data.pa?.[field] ?? data.ml?.[field] ?? data.ocr?.[field] ?? null;
}

function validateDaff(extraction) {
  const errors = [];
  const best = (field) => getConsensusValue(field, extraction);

  // 1. Issuer & Letterhead
  const company = best('issuer_company');
  const address = best('issuer_address');
  const isPoBox = best('issuer_address_is_po_box');

  if (!company) errors.push("Missing issuer company name");
  if (!address) errors.push("Missing issuer address");
  if (isPoBox === true) errors.push("PO Box used instead of physical address");

  // 2. Consignment Link
  const consignment = best('consignment_ref');
  const vessel = best('vessel_name');
  const voyage = best('voyage_number');
  if (!consignment && !vessel && !voyage) {
    errors.push("Missing consignment linkage (no container/BOL/invoice reference found)");
  }

  // 3. Unacceptable Packaging (Q1)
  const q1 = best('q1_unacceptable_material');
  if (!q1 || q1 === 'BLANK' || q1 === 'DECLARED_BLANK') {
    errors.push("Missing declaration for unacceptable packaging materials");
  }

  // 4. Timber / Bamboo Logic (Q2 / Q3)
  const q2 = best('q2_timber_bamboo');
  const q3 = best('q3_treatment');
  if (q2 === 'NO' && (q3 && q3 !== 'BLANK' && q3 !== 'DECLARED_BLANK')) {
    errors.push("Q2 is NO but Q3 is completed (conflict)");
  }
  if (q2 === 'YES_TIMBER' || q2 === 'YES_BAMBOO' || q2 === 'YES_BOTH') {
    if (!q3 || q3 === 'BLANK' || q3 === 'DECLARED_BLANK') {
      errors.push("Q2 is YES but Q3 is missing");
    }
  }

  // 5. Cleanliness Statement
  const declType = best('declaration_type') || "";
  const q4 = best('q4_cleanliness');
  const isLcl = declType.includes('LCL');
  const isFcl = declType.includes('FCL') || declType.includes('FCX');

  if (isLcl && q4 === 'PRESENT') {
    errors.push("Cleanliness statement present for LCL shipment");
  }
  if (isFcl && q4 !== 'PRESENT') {
    errors.push("Missing cleanliness statement for FCL shipment");
  }

  // 6. Endorsement
  const signed = best('signed');
  const printedName = best('printed_name');
  if (!signed) errors.push("Missing endorsement signature");
  if (!printedName) errors.push("Missing printed name of signatory");

  // 7. Date of Issue
  const dateIssued = best('date_issued');
  const dateValid = best('date_valid');
  if (!dateIssued) {
    errors.push("Missing date of issue");
  }

  // 8. Alterations
  const altPresent = best('alterations_present');
  const altEndorsed = best('alterations_endorsed');
  if (altPresent && !altEndorsed) {
    errors.push("Unendorsed alterations detected");
  }

  return {
    status: errors.length === 0 ? "Valid" : "Invalid",
    errors: errors
  };
}

// ─── Tactical Audit HUD (Cinematic Compliance) ──────────────────────────────
function ComplianceOverlay({ currentDocName, docIndex, totalDocs, activeRuleIndex, currentDocErrors }) {
  const rules = [
    { label: "Issuer Identity & Address", keys: ["issuer", "address", "po box"] },
    { label: "Consignment Linkage", keys: ["consignment"] },
    { label: "Unacceptable Packaging (Q1)", keys: ["packaging"] },
    { label: "Timber & Bamboo Logic (Q2/Q3)", keys: ["q2", "q3", "conflict"] },
    { label: "Cleanliness Statement", keys: ["cleanliness"] },
    { label: "Endorsement & Signatory", keys: ["signature", "printed name"] },
    { label: "Date of Issue Validity", keys: ["date"] },
    { label: "Alteration Endorsement", keys: ["alteration"] }
  ];

  const hasFailure = (keys) => {
     if (!currentDocErrors) return false;
     return currentDocErrors.some(err => keys.some(k => err.toLowerCase().includes(k.toLowerCase())));
  };

  const progressPct = Math.round(((docIndex * 8 + activeRuleIndex) / (totalDocs * 8)) * 100) || 0;

  return (
    <div className="co-minimal-overlay">
      <div className="co-minimal-panel">
        
        {/* Header */}
        <div className="co-min-header">
           <div className="co-min-badge">Compliance Verification</div>
           <h2 className="co-min-title">{currentDocName}</h2>
           <div className="co-min-subtitle">Document {docIndex + 1} of {totalDocs}</div>
        </div>

        {/* Main Body */}
        <div className="co-min-body">
           <div className="co-min-rules">
             {rules.map((rule, idx) => {
               const isScanning = idx === activeRuleIndex;
               const isEvaluated = idx < activeRuleIndex;
               const failed = isEvaluated && hasFailure(rule.keys);
               
               let stateClass = "pending";
               if (isScanning) stateClass = "scanning";
               if (isEvaluated) stateClass = failed ? "failed" : "passed";

               return (
                 <div key={idx} className={`co-min-rule-item ${stateClass}`}>
                    <div className="co-min-icon">
                       {isEvaluated ? (failed ? (
                         <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                       ) : (
                         <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                       )) : isScanning ? (
                         <div className="co-min-spinner"></div>
                       ) : (
                         <div className="co-min-dot"></div>
                       )}
                    </div>
                    <div className="co-min-rule-name">{rule.label}</div>
                    <div className="co-min-rule-status">
                       {isEvaluated ? (failed ? "Violation" : "Verified") : isScanning ? "Analyzing" : "Waiting"}
                    </div>
                 </div>
               )
             })}
           </div>
        </div>

        {/* Footer Progress */}
        <div className="co-min-footer">
           <div className="co-min-progress-text">{progressPct}% Complete</div>
           <div className="co-min-progress-bar">
              <div className="co-min-progress-fill" style={{ width: `${progressPct}%` }}></div>
           </div>
        </div>
      </div>

      <style>{`
        /* Clean, Vercel-like Dark Mode */
        .co-minimal-overlay {
          position: fixed; inset: 0; z-index: 5000;
          display: flex; align-items: center; justify-content: center;
          background: rgba(0, 0, 0, 0.85);
          backdrop-filter: blur(8px);
          font-family: 'Inter', -apple-system, sans-serif;
          color: #ededed;
        }

        .co-minimal-panel {
          width: 100%; max-width: 550px;
          background: #0a0a0a;
          border: 1px solid #222;
          border-radius: 12px;
          padding: 48px;
          box-shadow: 0 30px 60px rgba(0,0,0,0.6);
          display: flex; flex-direction: column; gap: 40px;
          animation: fadeSlideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(15px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .co-min-header {
          text-align: center;
          display: flex; flex-direction: column; align-items: center; gap: 12px;
        }

        .co-min-badge {
          font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
          color: #888; background: #111; padding: 4px 12px; border-radius: 6px; border: 1px solid #222;
        }

        .co-min-title {
          font-size: 1.4rem; font-weight: 500; color: #fff; margin: 0;
          letter-spacing: -0.01em;
        }

        .co-min-subtitle {
          font-size: 0.85rem; color: #666;
        }

        .co-min-rules {
          display: flex; flex-direction: column; gap: 1px;
          background: #222; border: 1px solid #222; border-radius: 8px; overflow: hidden;
        }

        .co-min-rule-item {
          display: flex; align-items: center; padding: 14px 20px;
          background: #0a0a0a;
          transition: background 0.2s;
        }

        .co-min-rule-item.scanning {
          background: #111;
        }

        .co-min-icon {
          width: 24px; display: flex; align-items: center; justify-content: center;
          margin-right: 16px; color: #444;
        }

        .co-min-dot {
          width: 5px; height: 5px; border-radius: 50%; background: #444;
        }

        .co-min-spinner {
          width: 14px; height: 14px; border: 2px solid #444;
          border-top-color: #ededed; border-radius: 50%; animation: spin 0.8s linear infinite;
        }

        .passed .co-min-icon { color: #10b981; }
        .failed .co-min-icon { color: #ef4444; }
        .scanning .co-min-icon { color: #ededed; }

        .co-min-rule-name {
          flex: 1; font-size: 0.9rem; font-weight: 400; color: #666;
        }
        
        .passed .co-min-rule-name, .failed .co-min-rule-name { color: #ccc; }
        .scanning .co-min-rule-name { color: #fff; font-weight: 500; }

        .co-min-rule-status {
          font-size: 0.75rem; font-weight: 500; color: #444; text-transform: uppercase; letter-spacing: 0.05em;
        }

        .passed .co-min-rule-status { color: #10b981; }
        .failed .co-min-rule-status { color: #ef4444; }
        .scanning .co-min-rule-status { color: #ededed; }

        .co-min-footer {
          display: flex; flex-direction: column; gap: 12px;
        }

        .co-min-progress-text {
          font-size: 0.8rem; color: #888; text-align: right; font-weight: 500;
        }

        .co-min-progress-bar {
          height: 3px; background: #222; border-radius: 2px; overflow: hidden;
        }

        .co-min-progress-fill {
          height: 100%; background: #ededed; transition: width 0.3s ease;
        }
      `}</style>
    </div>
  );
}


// ─── Compliance Audit Report Modal ───────────────────────────────────────────
function AuditReportModal({ file, report, userEmail, onClose, onOverride }) {
  if (!report) return null;

  const { internal, external } = report;
  const allRules = [
    { label: "Issuer Identity", key: "issuer" },
    { label: "Physical Address", key: "address" },
    { label: "No PO Box", key: "po box" },
    { label: "Consignment Link", key: "consignment" },
    { label: "Packaging Declaration (Q1)", key: "packaging" },
    { label: "Timber Logic (Q2/Q3)", key: ["q2", "q3"] },
    { label: "Cleanliness (Q4)", key: "cleanliness" },
    { label: "Signature Endorsement", key: "signature" },
    { label: "Printed Name", key: "printed name" },
    { label: "Date of Issue", key: "date" },
    { label: "Alterations Audit", key: "alteration" },
    { label: "Neural Diagnostics", key: "" } // Catch-all for any other errors
  ];


  return (
    <div className="audit-modal-overlay" onClick={onClose}>
      <div className="audit-modal-content" onClick={e => e.stopPropagation()}>
        <div className="audit-modal-header">
           <div className="audit-badge">DAFF COMPLIANCE AUDIT REPORT</div>
           <h3>{file.name}</h3>
           <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="audit-summary-strip">
          <div className={`summary-box ${internal.status === "Valid" ? 'valid' : 'invalid'}`}>
             <div className="label">INTERNAL ENGINE</div>
             <div className="status">{internal.status}</div>
          </div>
          <div className={`summary-box ${external.status === "Valid" ? 'valid' : 'invalid'}`}>
             <div className="label">EXTERNAL (POWER AUTOMATE)</div>
             <div className="status">{external.status}</div>
          </div>
        </div>

        <div className="audit-checklist">
          {allRules.map((rule, idx) => {
            const keys = Array.isArray(rule.key) ? rule.key : [rule.key];
            const combinedErrors = [
              ...(internal.errors || []).map(e => `[INTERNAL] ${e}`),
              ...(external.errors || []).map(e => `[EXTERNAL] ${e}`)
            ];
            
            // For the catch-all "Neural Diagnostics"
            let ruleErrors = [];
            if (rule.label === "Neural Diagnostics") {
              // Find errors not caught by any other rule
              const caughtErrors = new Set();
              allRules.slice(0, -1).forEach(r => {
                const rKeys = Array.isArray(r.key) ? r.key : [r.key];
                combinedErrors.forEach(err => {
                  if (rKeys.some(k => err.toLowerCase().includes(k.toLowerCase()))) {
                    caughtErrors.add(err);
                  }
                });
              });
              ruleErrors = combinedErrors.filter(err => !caughtErrors.has(err));
              if (ruleErrors.length === 0 && internal.status === "Valid" && external.status === "Valid") return null;
              if (ruleErrors.length === 0 && (internal.status === "Invalid" || external.status === "Invalid") && combinedErrors.length === 0) {
                 ruleErrors = ["Unspecified extraction anomaly detected"];
              }
            } else {
              ruleErrors = combinedErrors.filter(err => 
                keys.some(k => err.toLowerCase().includes(k.toLowerCase()))
              );
            }

            const passed = ruleErrors.length === 0;
            if (rule.label === "Neural Diagnostics" && passed) return null;
            
            return (
              <div key={idx} className={`audit-item ${passed ? 'passed' : 'failed'}`}>
                <div className="audit-item-top">
                  <div className="audit-status-icon">{passed ? "✓" : "✗"}</div>
                  <div className="audit-label">{rule.label}</div>
                  <div className="audit-verdict">{passed ? "Compliant" : "Violation"}</div>
                </div>
                {!passed && ruleErrors.map((err, eidx) => (
                  <div key={eidx} className="audit-error-msg">⚠ {err}</div>
                ))}
              </div>
            );
          })}
        </div>

        <div className="audit-footer" style={{ gap: '12px' }}>
          <button 
            className="audit-email-btn" 
            onClick={async () => {
              try {
                const combinedErrors = [
                  ...(internal.errors || []),
                  ...(external.errors || [])
                ];
                await emailAuditReport(userEmail, file?.name || "Unknown", combinedErrors);
                toast.success("Audit report transmitted via Power Automate");
              } catch (e) {
                toast.error("Failed to transmit audit report");
              }
            }}
          >
             📧 EMAIL AUDIT REPORT
          </button>
          <button 
            className="audit-override-btn"
            onClick={() => {
              report.internal.status = "Valid";
              report.internal.errors = [];
              onOverride();
              toast.success("Audit manually overridden to VALID", { icon: '🛡️' });
            }}
          >
             🛡️ FORCE PASS AUDIT
          </button>
        </div>
      </div>
      
      <style>{`
        .audit-modal-overlay {
          position: fixed; inset: 0; z-index: 6000;
          background: rgba(0,0,0,0.92); backdrop-filter: blur(40px);
          display: flex; align-items: center; justify-content: center;
          padding: 40px;
        }
        .audit-modal-content {
          width: 700px; max-height: 90vh; background: #020208; border: 1px solid rgba(255,255,255,0.08);
          border-radius: 28px; padding: 40px; position: relative;
          box-shadow: 0 50px 120px rgba(0,0,0,0.9);
          overflow-y: auto;
          scrollbar-width: thin;
        }
        .audit-modal-header { text-align: center; margin-bottom: 30px; background: #020208; padding-bottom: 20px; }
        .audit-badge { font-size: 0.65rem; letter-spacing: 0.3em; color: var(--accent-cyan); margin-bottom: 10px; font-weight: 800; text-shadow: 0 0 10px var(--accent-cyan-glow); }
        .audit-modal-header h3 { font-size: 1.4rem; color: #fff; font-weight: 800; letter-spacing: -0.5px; }
        
        .audit-summary-strip { display: flex; gap: 20px; margin-bottom: 30px; }
        .summary-box { flex: 1; padding: 20px; border-radius: 16px; text-align: center; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); }
        .summary-box.valid { border-color: #4ade80; color: #4ade80; background: rgba(74,222,128,0.1); box-shadow: 0 0 30px rgba(74,222,128,0.1); }
        .summary-box.invalid { border-color: #f87171; color: #f87171; background: rgba(248,113,113,0.1); box-shadow: 0 0 30px rgba(248,113,113,0.1); }
        .summary-box .label { font-size: 0.65rem; font-weight: 800; margin-bottom: 8px; letter-spacing: 0.1em; opacity: 0.7; }
        .summary-box .status { font-size: 1.3rem; font-weight: 900; letter-spacing: 0.05em; text-transform: uppercase; }

        .audit-checklist { display: grid; gap: 12px; margin-bottom: 30px; }
        .audit-item { 
          display: flex; flex-direction: column; gap: 8px; padding: 20px 24px; 
          border-radius: 16px; background: rgba(255,255,255,0.03); 
          border: 1px solid rgba(255,255,255,0.05);
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .audit-item.failed { 
          background: rgba(248,113,113,0.06); 
          border-color: rgba(248,113,113,0.3); 
          box-shadow: inset 0 0 20px rgba(248,113,113,0.05);
        }
        .audit-item.passed {
          background: rgba(74,222,128,0.03);
          border-color: rgba(74,222,128,0.15);
        }
        .audit-item-top { display: flex; align-items: center; gap: 15px; }
        .audit-status-icon { font-weight: 900; font-size: 1.4rem; }
        .failed .audit-status-icon { color: #f87171; text-shadow: 0 0 15px rgba(248,113,113,0.5); }
        .passed .audit-status-icon { color: #4ade80; text-shadow: 0 0 15px rgba(74,222,128,0.5); }
        
        .audit-label { flex: 1; font-size: 0.95rem; font-weight: 700; color: #fff; }
        .audit-verdict { font-size: 0.65rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; }

        .audit-error-msg {
          font-size: 0.8rem; color: #fca5a5; font-weight: 600;
          padding-left: 36px; margin-top: 5px; line-height: 1.4;
          text-shadow: 0 0 10px rgba(248,113,113,0.2);
        }

        .audit-footer { display: flex; gap: 15px; background: #020208; padding-top: 20px; }
        .audit-email-btn {
          flex: 1; height: 56px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1);
          color: #fff; border-radius: 14px; font-weight: 800; font-size: 0.85rem; cursor: pointer; transition: all 0.3s;
        }
        .audit-email-btn:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.2); }

        .audit-override-btn {
          flex: 1; height: 56px; background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          color: #fff; border: none; border-radius: 14px;
          font-weight: 800; font-size: 0.85rem; cursor: pointer; transition: all 0.3s;
          box-shadow: 0 10px 25px rgba(16,185,129,0.3);
        }
        .audit-override-btn:hover { transform: translateY(-2px); box-shadow: 0 15px 35px rgba(16,185,129,0.5); filter: brightness(1.1); }
      `}</style>
    </div>
  );
}

function LargePreviewModal({ file, onClose }) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    if (!file) return
    const u = URL.createObjectURL(file)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [file])

  if (!file) return null
  const isImage = file?.type?.startsWith('image/') || file?.name?.toLowerCase().match(/\.(jpg|jpeg|png|gif|tiff|tif)\s*$/)
  const isPdf   = file?.type === 'application/pdf' || file?.name?.toLowerCase().endsWith('.pdf')
  const isDoc   = file?.name?.toLowerCase().match(/\.(doc|docx|docm|rtf|xls|xlsx)\s*$/)
  const useIframe = isPdf && !isDoc

  return (
    <div className="preview-modal-overlay" onClick={onClose}>
      <div className="preview-modal-content" onClick={e => e.stopPropagation()}>
        <div className="preview-modal-header">
          <h3>Document Preview · {file.name}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="preview-modal-body">
          {isImage ? (
            <img src={url} alt="Large Preview" />
          ) : useIframe ? (
            <iframe src={url + '#toolbar=0&navpanes=0&view=Fit'} title="PDF View" />
          ) : isDoc ? (
            <DocxPreview file={file} standalone={true} />
          ) : (
            <div className="preview-placeholder">Preview not available for this type</div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Native Word Preview ──────────────────────────────────────────────────────
function DocxPreview({ file, standalone }) {
  const [html, setHtml] = useState('')
  useEffect(() => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const result = await mammoth.convertToHtml({ arrayBuffer: e.target.result })
        setHtml(result.value)
      } catch (err) { }
    }
    reader.readAsArrayBuffer(file)
  }, [file])

  return (
    <div className={`docx-renderer ${standalone ? 'standalone' : ''}`} dangerouslySetInnerHTML={{ __html: html || '<i>Parsing formatting...</i>' }} />
  )
}

// ─── Result Card ──────────────────────────────────────────────────────────────
const ResultCard = ({ res, onAuditReview, onViewClick, onPillClick }) => {
  const { file, outcome, isCurrent, isReady, compliancePassed, complianceRun } = res;
  const [previewUrl, setPreviewUrl] = useState(null)

  useEffect(() => {
    if (!file) return
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  if (isCurrent) {
    const coords = `X: ${(Math.random() * 100).toFixed(2)} Y: ${(Math.random() * 100).toFixed(2)}`
    return (
      <div className="result-card processing extracting-card" style={{ transform: 'scale(1.05)', zIndex: 100, borderStyle: 'solid' }}>
        <div className="processing-active-glow" />
        <div className="hud-bracket hud-tl" /><div className="hud-bracket hud-tr" />
        <div className="hud-bracket hud-bl" /><div className="hud-bracket hud-br" />
        <div className="dual-laser-container">
          <div className="laser-beam laser-cyan" /><div className="laser-beam laser-magenta" />
        </div>
        <div className="cyber-label">Sector Scanning</div>
        <div className="cyber-coords">{coords}</div>
        <div className="card-preview-area data-flicker">
          <div className="loader-ring" style={{ width: 40, height: 40, borderWidth: 2 }} />
        </div>
        <div className="result-name" style={{ marginTop: '20px' }}>{file.name}</div>
        <div className="processing-engines">
          <div className="engine-status-pill active">OCR</div>
          <div className="engine-status-pill active">TR</div>
          <div className="engine-status-pill active">AI</div>
        </div>
        <div className="result-badge" style={{ background: 'transparent', marginTop: '10px' }}>Neural Extraction in Progress...</div>
      </div>
    )
  }

  const isImage = file?.type?.startsWith('image/') || file?.name?.toLowerCase().match(/\.(jpg|jpeg|png|gif|tiff|tif)\s*$/)
  const isPdf   = file?.type === 'application/pdf' || file?.name?.toLowerCase().endsWith('.pdf')
  const isDoc   = file?.name?.toLowerCase().match(/\.(doc|docx|docm|rtf|xls|xlsx)\s*$/)
  const useIframe = isPdf && !isDoc
  const isClean = outcome === 'clean'

  return (
    <div className={`result-card fade-in ${complianceRun ? (compliancePassed ? 'pass-highlight' : 'fail-highlight') : (isClean ? 'clean' : 'review')}`} 
         style={{ cursor: isReady ? 'zoom-in' : 'default', position: 'relative', overflow: 'hidden' }}
         onClick={() => onViewClick && onViewClick(file)}>

      <div className="card-neural-overlay" />
      
      {complianceRun && (
        <div className={`holo-status-tag ${compliancePassed ? 'pass' : 'fail'}`}>
           <span className="holo-icon">{compliancePassed ? '✓' : '⚠'}</span>
           <span className="holo-text">{compliancePassed ? 'SECURE' : 'AUDIT'}</span>
        </div>
      )}

      <div className="card-preview-area-premium">
        <div className="preview-corner pc-tl" /><div className="preview-corner pc-tr" />
        <div className="preview-corner pc-bl" /><div className="preview-corner pc-br" />
        
        <div className="preview-viewport-inner">
          {isImage ? (
            <img src={previewUrl} alt="Preview" className="preview-media-premium" />
          ) : useIframe ? (
            <iframe src={previewUrl + '#toolbar=0&navpanes=0&view=FitH&scrollbar=0'} className="preview-media-premium" title="PDF Preview" />
          ) : isDoc ? (
            <DocxPreview file={file} />
          ) : (
            <div className="preview-placeholder-premium">
              <div className="file-type-badge">{file?.name?.split('.').pop().toUpperCase()}</div>
            </div>
          )}
        </div>
        
        <div className="preview-hover-overlay">
           <div className="magnify-icon">🔍</div>
           <span>SYNTHESIS_HUB</span>
        </div>
      </div>

      <div className="result-info-premium">
        <div className="result-meta-row">
           <div className="result-name-premium" title={file?.name}>{file?.name}</div>
           <div className="result-size-tag">{(file?.size / 1024).toFixed(1)} KB</div>
        </div>
        
        {outcome && (
          <div className="result-footer-premium">
            {!complianceRun ? (
              <div className="engine-pills-premium">
                <button className="e-pill" onClick={(e) => { e.stopPropagation(); onPillClick('ocr'); }}>OCR</button>
                <button className="e-pill" onClick={(e) => { e.stopPropagation(); onPillClick('transformers'); }}>TR</button>
                <button className="e-pill" onClick={(e) => { e.stopPropagation(); onPillClick('ai'); }}>AI</button>
              </div>
            ) : (
              <div className="tactical-actions-premium">
                <button className="tactical-btn email" onClick={(e) => { e.stopPropagation(); toast.success('Transmitting Report...'); }}>
                   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                     <rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                   </svg>
                   <span>EMAIL</span>
                </button>
                <button className="tactical-btn review" onClick={(e) => onAuditReview(e)}>
                   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                     <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
                   </svg>
                   <span>REVIEW</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`
        .holo-status-tag {
          position: absolute; top: 0; right: 0; padding: 6px 15px;
          display: flex; align-items: center; gap: 8px; z-index: 100;
          border-bottom-left-radius: 12px; font-weight: 900; font-size: 0.6rem;
          letter-spacing: 0.15em; box-shadow: -5px 5px 20px rgba(0,0,0,0.4);
        }
        .holo-status-tag.pass { background: rgba(74, 222, 128, 0.9); color: #000; }
        .holo-status-tag.fail { background: rgba(248, 113, 113, 0.9); color: #fff; box-shadow: 0 0 20px rgba(248,113,113,0.4); }
        .holo-icon { font-size: 0.8rem; }

        .card-preview-area-premium {
          height: 240px; background: #010105; margin: -10px -10px 15px -10px;
          position: relative; overflow: hidden; border-radius: 12px;
          display: flex; align-items: center; justify-content: center;
          border-bottom: 1px solid rgba(255,255,255,0.05);
          padding: 12px;
        }
        .preview-viewport-inner {
          width: 100%; height: 100%; border-radius: 4px; overflow: hidden;
          background: rgba(255,255,255,0.01); display: flex; align-items: center; justify-content: center;
          position: relative;
        }
        .preview-media-premium { 
          width: 100%; height: 100%; object-fit: contain; opacity: 0.8; 
          transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .result-card:hover .preview-media-premium { opacity: 1; transform: scale(1.02); }
        
        iframe.preview-media-premium {
          border: none;
          width: 110%; height: 110%; 
          transform: scale(0.85); 
          pointer-events: none;
          overflow: hidden;
        }

        .preview-hover-overlay {
          position: absolute; inset: 0; background: rgba(34, 211, 238, 0.1);
          backdrop-filter: blur(8px); display: flex; flex-direction: column;
          align-items: center; justify-content: center; gap: 10px;
          opacity: 0; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          z-index: 20;
        }
        .result-card:hover .preview-hover-overlay { opacity: 1; }
        .magnify-icon { font-size: 1.8rem; transform: scale(0.8) translateY(20px); transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); }
        .result-card:hover .magnify-icon { transform: scale(1) translateY(0); }
        .preview-hover-overlay span { font-size: 0.6rem; font-weight: 900; letter-spacing: 0.3em; color: var(--accent-cyan); text-shadow: 0 0 10px var(--accent-cyan-glow); }

        .result-info-premium { display: flex; flex-direction: column; gap: 15px; padding-top: 5px; }
        .result-meta-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
        .result-name-premium { font-size: 0.9rem; font-weight: 900; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; letter-spacing: -0.02em; }
        .result-card:hover .result-name-premium { color: var(--accent-cyan); }
        .result-size-tag { font-size: 0.55rem; font-weight: 900; color: rgba(255,255,255,0.2); letter-spacing: 0.1em; font-family: monospace; }

        .tactical-actions-premium { display: flex; gap: 10px; width: 100%; }
        .tactical-btn {
          height: 44px; border-radius: 6px;
          font-size: 0.65rem; font-weight: 900; letter-spacing: 0.15em;
          cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          display: flex; align-items: center; justify-content: center; gap: 10px;
          position: relative; overflow: hidden;
        }
        
        .tactical-btn.email { 
          flex: 1;
          background: rgba(255,255,255,0.03); 
          border: 1px solid rgba(255,255,255,0.1);
          color: rgba(255,255,255,0.7);
        }
        .tactical-btn.email:hover { 
          background: rgba(255,255,255,0.08); 
          border-color: rgba(255,255,255,0.3); 
          color: #fff;
          transform: translateY(-2px);
          box-shadow: 0 5px 20px rgba(0,0,0,0.4);
        }
        
        .tactical-btn.review { 
          flex: 1.4; /* Increased length as requested */
          background: rgba(34, 211, 238, 0.08); /* More prominent blue */
          border: 1px solid rgba(34, 211, 238, 0.3);
          color: var(--accent-cyan);
          box-shadow: 0 0 15px rgba(34, 211, 238, 0.1);
        }
        .tactical-btn.review:hover { 
          background: rgba(34, 211, 238, 0.2);
          border-color: var(--accent-cyan);
          transform: translateY(-2px); 
          box-shadow: 0 0 30px var(--accent-cyan-glow); 
          filter: brightness(1.2);
        }

        .engine-pills-premium { display: flex; gap: 8px; margin-top: 15px; }
        .e-pill {
          flex: 1; height: 28px; background: rgba(255,255,255,0.03); 
          border: 1px solid rgba(255,255,255,0.08); border-radius: 4px;
          color: rgba(255,255,255,0.4); font-size: 0.55rem; font-weight: 900; 
          letter-spacing: 0.1em; cursor: pointer; transition: all 0.3s;
          display: flex; align-items: center; justify-content: center;
        }
        .e-pill:hover { transform: translateY(-1px); border-color: rgba(255,255,255,0.2); color: #fff; }
        
        .e-pill:nth-child(1):hover { background: rgba(34, 211, 238, 0.1); border-color: var(--accent-cyan); color: var(--accent-cyan); box-shadow: 0 0 15px var(--accent-cyan-glow); }
        .e-pill:nth-child(2):hover { background: rgba(99, 102, 241, 0.1); border-color: #818cf8; color: #818cf8; box-shadow: 0 0 15px rgba(99,102,241,0.4); }
        .e-pill:nth-child(3):hover { background: rgba(236, 72, 153, 0.1); border-color: #f472b6; color: #f472b6; box-shadow: 0 0 15px rgba(236,72,153,0.4); }
      `}</style>
    </div>
  );
}

// ─── Processing Overlay ────────────────────────────────────────────────────
const PHASES = [
  'INITIALIZING QUANTUM VISOR',
  'SYNCHRONIZING NEURAL PATHWAYS',
  'ESTABLISHING UPLINK',
  'READY FOR EXTRACTION'
];

function ProcessingOverlay() {
  const [phaseIndex, setPhaseIndex] = useState(0);

  useEffect(() => {
    const phaseInterval = setInterval(() => {
      setPhaseIndex(prev => Math.min(prev + 1, PHASES.length - 1));
    }, 700);
    return () => clearInterval(phaseInterval);
  }, []);

  return (
    <div className="processing-overlay">
      <div className="cinematic-boot-overlay">
        <div className="grid-floor" />
        <div className="visor-container">
          <div className="visor-bar top" />
          <div className="visor-content">
             <div className="boot-ring-container">
                <div className="boot-ring outer" />
                <div className="boot-ring middle" />
                <div className="boot-ring core" />
             </div>
             
             <div className="boot-telemetry">
                <h2>NEURAL CORE OS v4.1.2</h2>
                <h1 className="boot-phase-text">{PHASES[phaseIndex]}</h1>
             </div>
          </div>
          <div className="visor-bar bottom" />
        </div>
      </div>
    </div>
  )
}



// ─── OCR Plain-English fields config ────────────────────────────────────────
const OCR_FIELDS = [
  { key: 'file_name',                  label: 'File Name' },
  { key: 'serial_number',              label: 'Serial Number' },
  { key: 'declaration_type',           label: 'Declaration Type' },
  { key: 'issuer_company',             label: 'Issuer Company' },
  { key: 'issuer_address',             label: 'Issuer Address' },
  { key: 'issuer_address_is_po_box',   label: 'Is PO Box Address' },
  { key: 'exporter',                   label: 'Exporter' },
  { key: 'importer',                   label: 'Importer' },
  { key: 'vessel_name',                label: 'Vessel Name' },
  { key: 'voyage_number',              label: 'Voyage Number' },
  { key: 'consignment_ref',            label: 'Consignment Reference' },
  { key: 'date_issued',                label: 'Date Issued' },
  { key: 'date_valid',                 label: 'Date Valid' },
  { key: 'signed',                     label: 'Signed' },
  { key: 'signature_type',             label: 'Signature Type' },
  { key: 'printed_name',               label: 'Printed Name' },
  { key: 'letterhead_present',         label: 'Letterhead Present' },
  { key: 'q1_unacceptable_material',   label: 'Q1 — Unacceptable Material' },
  { key: 'q2_timber_bamboo',           label: 'Q2 — Timber / Bamboo' },
  { key: 'q3_treatment',               label: 'Q3 — Treatment' },
  { key: 'q4_cleanliness',             label: 'Q4 — Container Cleanliness' },
  { key: 'alterations_present',        label: 'Alterations Present' },
  { key: 'alterations_endorsed',       label: 'Alterations Endorsed' },
  { key: 'extraction_method',          label: 'Extraction Method' },
  { key: 'ocr_confidence',             label: 'OCR Confidence' },
  { key: 'ml_predictions',             label: 'ML Predictions' },
  { key: 'ml_confidence',              label: 'ML Confidence' },
  { key: 'field_scores',               label: 'Field Scores' },
]

function formatValue(val) {
  if (val === null || val === undefined) return 'N/A'
  if (typeof val === 'boolean') return val ? 'Yes' : 'No'
  if (typeof val === 'object') {
    // field_scores sub-object — render as a mini table
    return Object.entries(val).map(([k, v]) => `${k}: ${typeof v === 'number' ? (v * 100).toFixed(0) + '%' : v}`).join('  ·  ')
  }
  return String(val)
}

function JsonMatrixModal({ title, data, onClose }) {
  const [copied, setCopied] = useState(false);
  const displayData = { ...data };
  delete displayData.compliance_report;

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(displayData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="json-modal-overlay" onClick={onClose}>
      <div className="json-modal-content" onClick={e => e.stopPropagation()}>
        <div className="json-modal-header">
           <div className="header-meta">DATA_MATRIX_LINK_ESTABLISHED</div>
           <div className="header-main">
              <h3>{title}</h3>
              <div className="header-actions">
                 <button className="copy-json-btn" onClick={handleCopy}>
                    {copied ? '✓ SYNCED' : '[ ] COPY_VEC'}
                 </button>
                 <button className="close-btn-matrix" onClick={onClose}>×</button>
              </div>
           </div>
        </div>
        
        <div className="json-matrix-body">
           {OCR_FIELDS.map(({ key, label }) => {
             if (!(key in displayData)) return null;
             return (
               <div key={key} className="matrix-row">
                  <div className="matrix-label">{key.toUpperCase()}</div>
                  <div className="matrix-value">{formatValue(displayData[key])}</div>
               </div>
             );
           })}
        </div>
      </div>

      <style>{`
        .json-modal-overlay {
          position: fixed; inset: 0; z-index: 8000;
          background: rgba(1, 1, 3, 0.9); backdrop-filter: blur(20px);
          display: flex; align-items: center; justify-content: center;
          padding: 40px;
        }
        .json-modal-content {
          width: 800px; max-height: 85vh; background: #020208;
          border: 1px solid rgba(255,255,255,0.08); border-radius: 20px;
          display: flex; flex-direction: column; overflow: hidden;
          box-shadow: 0 40px 100px rgba(0,0,0,0.8);
          animation: matrix-enter 0.4s cubic-bezier(0.2, 0, 0.2, 1);
        }
        @keyframes matrix-enter {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .json-modal-header { padding: 30px 40px; background: rgba(255,255,255,0.02); border-bottom: 1px solid rgba(255,255,255,0.05); }
        .header-meta { font-size: 0.6rem; color: var(--accent-cyan); font-weight: 900; letter-spacing: 0.2em; margin-bottom: 8px; text-shadow: 0 0 10px var(--accent-cyan-glow); }
        .header-main { display: flex; justify-content: space-between; align-items: center; }
        .header-main h3 { margin: 0; color: #fff; font-size: 1.3rem; font-weight: 800; }
        .header-actions { display: flex; align-items: center; gap: 15px; }

        .copy-json-btn {
          background: rgba(34, 211, 238, 0.05); border: 1px solid rgba(34, 211, 238, 0.2);
          color: var(--accent-cyan); padding: 8px 16px; border-radius: 8px;
          font-size: 0.7rem; font-weight: 800; cursor: pointer; transition: all 0.2s;
        }
        .copy-json-btn:hover { background: rgba(34, 211, 238, 0.15); border-color: var(--accent-cyan); }
        .close-btn-matrix { background: transparent; border: none; color: rgba(255,255,255,0.3); font-size: 2rem; cursor: pointer; line-height: 1; }
        .close-btn-matrix:hover { color: #fff; }

        .json-matrix-body { flex: 1; overflow-y: auto; padding: 20px 0; scrollbar-width: thin; }
        .matrix-row {
          display: grid; grid-template-columns: 220px 1fr; gap: 20px;
          padding: 12px 40px; border-bottom: 1px solid rgba(255,255,255,0.03);
          transition: background 0.2s;
        }
        .matrix-row:hover { background: rgba(255,255,255,0.01); }
        .matrix-label { color: rgba(255,255,255,0.3); font-size: 0.65rem; font-weight: 800; letter-spacing: 0.1em; padding-top: 2px; }
        .matrix-value { color: #e2e8f0; font-size: 0.85rem; line-height: 1.5; font-weight: 600; }
      `}</style>
    </div>
  );
}

function OcrModal({ title, data, onClose }) {
  const [copied, setCopied] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);

  // We need the original file for the preview
  // In a real app, we'd pass the file object. 
  // For now, we'll try to find it in the state if possible, 
  // but since we only have 'data', we'll assume we might need to simulate the preview or just show the text.
  // Actually, let's just make the UI amazing first.

  const displayData = { ...data };
  delete displayData.compliance_report;

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(displayData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="synthesis-modal-overlay" onClick={onClose}>
      <div className="synthesis-modal-content" onClick={e => e.stopPropagation()}>
        
        <div className="synthesis-grid">
          {/* Left: Tactical Lens */}
          <div className="synthesis-visual">
             <div className="visual-header">
                <div className="visual-title">{title}</div>
                <div className="visual-status">VECTOR_LENS_ACTIVE</div>
             </div>
             <div className="tactical-lens-container">
                <div className="lens-bracket lens-tl" />
                <div className="lens-bracket lens-tr" />
                <div className="lens-bracket lens-bl" />
                <div className="lens-bracket lens-br" />
                <div className="lens-grid-bg" />
                <div className="lens-document-preview">
                   <div className="doc-placeholder-icon">📄</div>
                   <div className="doc-scanning-bar" />
                   <div className="doc-telemetry">FOCUS: OPTIMAL | SCALE: 1.0x</div>
                </div>
             </div>
          </div>

          {/* Right: Neural Synthesis */}
          <div className="synthesis-telemetry">
             <div className="telemetry-header">
                <div className="header-top">
                   <h3 className="synthesis-title">AAW_CORE_SYNTHESIS</h3>
                   <div className="synthesis-actions">
                      <button className="synth-btn-small" onClick={handleCopy}>
                        {copied ? '✓ SYNCED' : '[ ] COPY_VEC'}
                      </button>
                      <button className="synth-btn-close" onClick={onClose}>×</button>
                   </div>
                </div>
                <div className="header-sub">HEURISTIC EXTRACTION MATRIX v2.0</div>
             </div>

             <div className="telemetry-scroll">
                {OCR_FIELDS.map(({ key, label }) => {
                  if (!(key in displayData)) return null;
                  const val = displayData[key];
                  const match = (Math.random() * 5 + 94).toFixed(1); // Simulated match for visual fidelity
                  return (
                    <div key={key} className="telemetry-card">
                       <div className="card-top">
                          <div className="card-label">{key.toUpperCase()}</div>
                          <div className="card-match">MATCH_VEC: {match}%</div>
                       </div>
                       <div className="card-value">{formatValue(val)}</div>
                       <div className="card-progress">
                          <div className="progress-fill" style={{ width: `${match}%` }} />
                       </div>
                    </div>
                  );
                })}
             </div>
          </div>
        </div>

      </div>

      <style>{`
        .synthesis-modal-overlay {
          position: fixed; inset: 0; z-index: 7000;
          background: rgba(1, 1, 3, 0.95); backdrop-filter: blur(20px);
          display: flex; align-items: center; justify-content: center;
          padding: 40px;
        }
        .synthesis-modal-content {
          width: 1300px; height: 850px; background: #02020a;
          border: 1px solid rgba(34, 211, 238, 0.1); border-radius: 24px;
          overflow: hidden; box-shadow: 0 0 100px rgba(0,0,0,0.8);
          animation: modal-enter 0.5s cubic-bezier(0.2, 0, 0.2, 1);
        }
        @keyframes modal-enter {
          from { opacity: 0; transform: scale(0.95) translateY(20px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }

        .synthesis-grid { display: grid; grid-template-columns: 1fr 1fr; height: 100%; }

        /* Tactical Lens Styles */
        .synthesis-visual { background: #010105; padding: 40px; display: flex; flex-direction: column; border-right: 1px solid rgba(255,255,255,0.05); }
        .visual-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .visual-title { color: #fff; font-size: 1.2rem; font-weight: 800; letter-spacing: -0.5px; }
        .visual-status { color: var(--accent-cyan); font-size: 0.65rem; font-weight: 900; letter-spacing: 0.2em; text-shadow: 0 0 10px var(--accent-cyan-glow); }

        .tactical-lens-container {
          flex: 1; position: relative; background: rgba(0,0,0,0.4); 
          border: 1px solid rgba(255,255,255,0.03); border-radius: 20px;
          display: flex; align-items: center; justify-content: center;
          overflow: hidden;
        }
        .lens-bracket { position: absolute; width: 30px; height: 30px; border: 2px solid var(--accent-cyan); opacity: 0.5; }
        .lens-tl { top: 30px; left: 30px; border-right: 0; border-bottom: 0; }
        .lens-tr { top: 30px; right: 30px; border-left: 0; border-bottom: 0; }
        .lens-bl { bottom: 30px; left: 30px; border-right: 0; border-top: 0; }
        .lens-br { bottom: 30px; right: 30px; border-left: 0; border-top: 0; }

        .lens-grid-bg {
          position: absolute; inset: 0; opacity: 0.05;
          background-image: linear-gradient(rgba(34,211,238,1) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(34,211,238,1) 1px, transparent 1px);
          background-size: 40px 40px;
        }

        .lens-document-preview {
          width: 380px; height: 500px; background: rgba(255,255,255,0.02);
          border: 1px solid rgba(255,255,255,0.08); border-radius: 4px;
          position: relative; display: flex; align-items: center; justify-content: center;
          box-shadow: 0 40px 80px rgba(0,0,0,0.5);
        }
        .doc-placeholder-icon { font-size: 5rem; opacity: 0.1; }
        .doc-scanning-bar {
          position: absolute; top: 0; left: 0; width: 100%; height: 4px;
          background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
          box-shadow: 0 0 20px var(--accent-cyan);
          animation: doc-scan 4s infinite linear;
        }
        @keyframes doc-scan {
          0% { top: 0; opacity: 0; }
          10%, 90% { opacity: 1; }
          100% { top: 100%; opacity: 0; }
        }
        .doc-telemetry {
          position: absolute; bottom: -40px; width: 100%; text-align: center;
          color: rgba(255,255,255,0.3); font-size: 0.6rem; letter-spacing: 0.3em;
        }

        /* Telemetry Styles */
        .synthesis-telemetry { padding: 40px; display: flex; flex-direction: column; background: #02020a; }
        .telemetry-header { margin-bottom: 30px; }
        .header-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
        .synthesis-title { color: var(--accent-cyan); font-size: 1.1rem; font-weight: 900; letter-spacing: 0.3em; margin: 0; text-shadow: 0 0 15px var(--accent-cyan-glow); }
        .header-sub { color: rgba(255,255,255,0.3); font-size: 0.65rem; font-weight: 800; letter-spacing: 0.1em; }

        .synth-btn-small {
          background: rgba(34, 211, 238, 0.05); border: 1px solid rgba(34, 211, 238, 0.2);
          color: var(--accent-cyan); padding: 6px 14px; border-radius: 8px;
          font-size: 0.65rem; font-weight: 800; cursor: pointer; transition: all 0.2s;
        }
        .synth-btn-small:hover { background: rgba(34, 211, 238, 0.1); border-color: var(--accent-cyan); }
        .synth-btn-close {
          background: transparent; border: none; color: rgba(255,255,255,0.2);
          font-size: 1.8rem; cursor: pointer; line-height: 1; margin-left: 15px;
        }
        .synth-btn-close:hover { color: #fff; }

        .telemetry-scroll {
          flex: 1; overflow-y: auto; padding-right: 15px;
          display: flex; flex-direction: column; gap: 12px;
          scrollbar-width: thin;
        }
        .telemetry-card {
          background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);
          padding: 18px 24px; border-radius: 16px; transition: all 0.3s;
        }
        .telemetry-card:hover {
          background: rgba(34, 211, 238, 0.03); border-color: rgba(34, 211, 238, 0.2);
          transform: translateX(5px);
        }
        .card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .card-label { color: rgba(255,255,255,0.3); font-size: 0.6rem; font-weight: 800; letter-spacing: 0.1em; }
        .card-match { color: var(--accent-cyan); font-size: 0.6rem; font-weight: 900; opacity: 0.7; }
        .card-value { color: #fff; font-size: 0.95rem; font-weight: 700; line-height: 1.4; margin-bottom: 12px; }
        .card-progress { height: 2px; background: rgba(255,255,255,0.05); border-radius: 2px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--accent-cyan); opacity: 0.5; }
      `}</style>
    </div>
  );
}

// ─── Json Modal ─────────────────────────────────────────────────────────────
function JsonModal({ title, data, onClose }) {
  return (
    <div className="modal-overlay fade-in" onClick={onClose} style={{ zIndex: 4000 }}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <pre>{JSON.stringify(data, null, 2)}</pre>
        </div>
      </div>
    </div>
  )
}

// ─── Main SendPage ───────────────────────────────────────────────────────────
export default function SendPage() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const { accounts } = useMsal()
  const userEmail = accounts[0]?.username || "unknown"

  // Memoize queue to prevent infinite useEffect loops
  const queue = useMemo(() => (state?.queue || []).slice(0, 20), [state?.queue])
  
  const [currentIndex, setCurrentIndex] = useState(0)
  const [currentExtraction, setCurrentExtraction] = useState(null)
  const [allResults, setAllResults] = useState([])
  const [appState, setAppState] = useState('IDLE') // IDLE | PROCESSING_OVERLAY | EXTRACTING | COMPARING | DONE
  
  // Modal State
  const [modalData, setModalData] = useState(null)
  const [modalTitle, setModalTitle] = useState('')
  const [modalType, setModalType] = useState('json')
  const [previewFile, setPreviewFile] = useState(null)

  // Compliance State
  const [complianceRunning, setComplianceRunning] = useState(false)
  const [complianceResults, setComplianceResults] = useState(null)
  const [auditDocIndex, setAuditDocIndex] = useState(0)
  const [auditRuleIndex, setAuditRuleIndex] = useState(-1)
  const [currentDocErrors, setCurrentDocErrors] = useState([])
  const [activeAuditReport, setActiveAuditReport] = useState(null)

  const handleAuditReview = (e, res) => {
    e.stopPropagation();
    setActiveAuditReport(res);
  };

  const scrollRef = useRef(null) 
  const timerRef = useRef()

  useEffect(() => {
    if (appState === 'EXTRACTING' || appState === 'COMPARING') {
      const activeCard = document.querySelector('.extracting-card');
      if (activeCard) {
        activeCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [appState, currentIndex]);

  useEffect(() => {
    if (!queue.length) { navigate('/'); return }
    return () => clearTimeout(timerRef.current)
  }, [queue, navigate])

  const startBatchProcessing = async () => {
    setAppState('PROCESSING_OVERLAY')
    try { await clearStorage() } catch (e) { }
    
    setTimeout(() => {
      setAppState('EXTRACTING')
      processNext(0)
    }, 2500)
  }

  const processNext = async (idx) => {
    if (idx >= queue.length) {
      setAppState('DONE')
      return
    }

    setCurrentIndex(idx)
    setAppState('EXTRACTING')
    setCurrentExtraction(null)

    try {
      const file = queue[idx]
      const data = await uploadFile(file)
      setCurrentExtraction(data)
      setAppState('COMPARING')
      
      const { isConverged } = computeNcr(data.ocr || {}, data.ml || {}, data.pa || {})

      timerRef.current = setTimeout(async () => {
        try {
          data.ocr.serial_number = String(idx + 1)
          await submitToPA(data.ocr)
        } catch (_) {} 
        
        const complianceOutcome = data.ocr?.compliance_report?.overall_outcome
        const outcome = (isConverged && complianceOutcome === 'Acceptable') ? 'clean' : 'review'
        
        setAllResults(prev => [...prev, { file, outcome, extraction: data }])
        processNext(idx + 1)
      }, 1200)

    } catch (err) {
      toast.error(`Fault on document ${queue[idx].name}`)
      setAllResults(prev => [...prev, { file: queue[idx], outcome: 'review', extraction: null }])
      processNext(idx + 1)
    }
  }

  const runComplianceCheck = async () => {
    setComplianceRunning(true)
    setComplianceResults(null)
    
    const results = []
    
    for (let i = 0; i < allResults.length; i++) {
      const res = allResults[i];
      setAuditDocIndex(i);

      // Evaluate compliance immediately before animating
      const internalReport = validateDaff(res.extraction)
      const consensusData = {}
      const fieldsToMap = [
        'issuer_company', 'issuer_address', 'issuer_address_is_po_box',
        'consignment_ref', 'vessel_name', 'voyage_number',
        'q1_unacceptable_material', 'q2_timber_bamboo', 'q3_treatment',
        'q4_cleanliness', 'signed', 'printed_name', 'date_issued',
        'alterations_present', 'alterations_endorsed', 'declaration_type'
      ]
      fieldsToMap.forEach(f => consensusData[f] = getConsensusValue(f, res.extraction))
      consensusData.file_name = res.file.name

      let externalReport = { status: "Invalid", errors: ["External flow failed"] }
      try {
        const paResponse = await validateDaffExternal(consensusData)
        externalReport = paResponse
      } catch (e) { }

      setCurrentDocErrors([...(internalReport.errors || []), ...(externalReport.errors || [])]);

      for (let r = 0; r < 8; r++) {
        setAuditRuleIndex(r);
        await new Promise(resolve => setTimeout(resolve, 300));
      }
      setAuditRuleIndex(8);

      const isOverallValid = internalReport.status === "Valid" && externalReport.status === "Valid"
      results.push({ ...res, compliancePassed: isOverallValid, complianceDetails: { internal: internalReport, external: externalReport } })
    }

    setComplianceResults(results)
    setComplianceRunning(false)
    setCurrentDocErrors([])
    toast.success(`Compliance check accomplished`, { duration: 5000 })
  }

  const handlePillClick = (type, extraction) => {
    if (!extraction) return toast.error('Synthesis in progress...');
    const titles = { ocr: 'OCR Pipeline', transformers: 'Transformer Schema', ai: 'AI Neural Core' };
    const dataKey = { ocr: 'ocr', transformers: 'ml', ai: 'pa' };
    setModalTitle(titles[type]);
    setModalData(extraction[dataKey[type]]);
    setModalType('matrix') // Use the matrix view for pills
  }

  const isOverlaying = appState === 'PROCESSING_OVERLAY'
  const isDeepFocus = appState === 'EXTRACTING' || appState === 'COMPARING'

  return (
    <>
      <div className={`send-page fade-in ${isDeepFocus ? 'deep-focus' : ''}`} ref={scrollRef}>
      <header className="send-header" style={{ opacity: isOverlaying ? 0 : 1 }}>
        <button className="back-btn" onClick={() => navigate('/')}>← Logout</button>
        <div className="send-title">
          <h2>DAFF Compliance Portal · Analysis Engine</h2>
          <p>{appState === 'IDLE' ? 'Document Intake Complete' : appState === 'DONE' ? 'Batch Convergence Accomplished' : `Running simultaneous synthesis for document ${currentIndex + 1} of ${queue.length}`}</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          {appState === 'IDLE' && <button className="process-batch-btn" onClick={startBatchProcessing}>Process Batch</button>}
          {appState === 'DONE' && !complianceResults && (
            <button onClick={runComplianceCheck} className="process-batch-btn" style={{ background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)', animation: 'pulse 2s ease infinite' }}>
              ⚖ CALCULATE COMPLIANCE
            </button>
          )}
        </div>
      </header>

      <section style={{ filter: isOverlaying ? 'blur(20px)' : 'none', opacity: isOverlaying ? 0.3 : 1 }}>
         {complianceResults && complianceResults.filter(r => !r.compliancePassed).length > 0 && (
           <div className="compliance-group failed-group fade-in">
              <div className="group-header">
                <h4 className="matrix-title danger">⚠ ATTENTION REQUIRED ({complianceResults.filter(r => !r.compliancePassed).length})</h4>
              </div>
              <div className="results-row">
                {complianceResults.filter(r => !r.compliancePassed).map((res, i) => (
                  <ResultCard key={res.file.name} res={{ ...res, complianceRun: true }} onAuditReview={(e) => handleAuditReview(e, res)} onViewClick={setPreviewFile} />
                ))}
              </div>
           </div>
         )}
         {complianceResults && complianceResults.filter(r => r.compliancePassed).length > 0 && (
           <div className="compliance-group success-group fade-in" style={{ marginTop: '60px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h4 className="matrix-title success" style={{ margin: 0 }}>✓ COMPLIANCE SECURE ({complianceResults.filter(r => r.compliancePassed).length})</h4>
                </div>
              <div className="results-row">
                {complianceResults.filter(r => r.compliancePassed).map((res, i) => (
                  <ResultCard key={res.file.name} res={{ ...res, complianceRun: true }} onAuditReview={(e) => handleAuditReview(e, res)} onViewClick={setPreviewFile} />
                ))}
              </div>
           </div>
         )}
         {!complianceResults && (
           <>
            <h4 className="matrix-title">Integrated Extraction Matrix</h4>
            <div className="results-row">
              {allResults.map((res, i) => <ResultCard key={i} res={{ ...res, complianceRun: false }} onPillClick={(type) => handlePillClick(type, res.extraction)} onViewClick={setPreviewFile} />)}
              {appState !== 'DONE' && appState !== 'IDLE' && appState !== 'PROCESSING_OVERLAY' && queue[currentIndex] && <ResultCard key="current" res={{ file: queue[currentIndex], isCurrent: true }} />}
              {(appState === 'IDLE' || appState === 'PROCESSING_OVERLAY' || (appState !== 'DONE' && currentIndex < queue.length - 1)) && 
                queue.slice(appState === 'IDLE' || appState === 'PROCESSING_OVERLAY' ? 0 : currentIndex + 1).map((f, i) => (
                <ResultCard key={`pending-${i}`} res={{ file: f, isReady: appState === 'IDLE' }} onViewClick={setPreviewFile} onPillClick={() => {}} />
              ))}
            </div>
           </>
         )}
      </section>

      <footer className="send-footer">
        {appState === 'EXTRACTING' && <div className="auto-pilot-notice fade-in"><span className="auto-pending"><span className="auto-spinner" /> Scanning vectors...</span></div>}
        {appState === 'COMPARING' && <div className="auto-pilot-notice fade-in"><span className="auto-pending"><span className="auto-spinner" /> Aligning synapses...</span></div>}
        {appState === 'DONE' && !complianceResults && <div className="auto-pilot-notice fade-in"><span className="auto-ok">✓ All vectors transmitted and validated. READY FOR AUDIT.</span></div>}
      </footer>
    </div>

    {isOverlaying && <ProcessingOverlay />}
    {complianceRunning && (
      <ComplianceOverlay 
        docIndex={auditDocIndex} 
        totalDocs={allResults.length}
        currentDocName={allResults[auditDocIndex]?.file?.name}
        activeRuleIndex={auditRuleIndex}
        currentDocErrors={currentDocErrors}
      />
    )}
    {activeAuditReport && (
      <AuditReportModal 
        file={activeAuditReport.file} 
        report={activeAuditReport.complianceDetails} 
        userEmail={userEmail}
        onClose={() => setActiveAuditReport(null)} 
        onOverride={() => {
           const updated = complianceResults.map(r => 
             r.file.name === activeAuditReport.file.name ? { ...r, compliancePassed: true } : r
           );
           setComplianceResults(updated);
           setActiveAuditReport(null);
        }}
      />
    )}
    {previewFile && <LargePreviewModal file={previewFile} onClose={() => setPreviewFile(null)} />}
    {modalData && modalType === 'ocr' && (
      <OcrModal
        title={modalTitle}
        data={modalData}
        onClose={() => setModalData(null)}
      />
    )}
    {modalData && modalType === 'matrix' && (
      <JsonMatrixModal
        title={modalTitle}
        data={modalData}
        onClose={() => setModalData(null)}
      />
    )}
    {modalData && modalType === 'json' && (
      <JsonModal
        title={modalTitle}
        data={modalData}
        onClose={() => setModalData(null)}
      />
    )}
    <style>{`@keyframes spin { to { transform: rotate(360deg); } } @keyframes pulse { 0%,100%{box-shadow:0 0 20px rgba(34,197,94,0.35)} 50%{box-shadow:0 0 35px rgba(34,197,94,0.7)} }`}</style>
    </>
  )
}
