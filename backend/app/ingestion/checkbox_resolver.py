"""
High-Fidelity Checkbox Resolver for DAFF PKDs.
Implements cascading detection logic:
1. Visual Contour Analysis (OpenCV)
2. OCR Symbol Recognition (✓, X, bracket characters)
3. LayoutLM Inference (Future Integration)
"""
import logging
import re
from typing import Dict, Optional, Literal

logger = logging.getLogger(__name__)

class CheckboxResolver:
    @staticmethod
    def resolve_q1(visual: str, text: str, ml: Optional[str] = None) -> str:
        # P0: If text is confidently NO and visual is YES, trust text (likely OCR noise in YES box)
        if text == "NO" and visual == "YES":
            return "NO"
            
        # Precedence: ML (if high conf) > Visual > Text
        if visual and visual not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK"):
            return visual
        if text and text not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK", None):
            return text
        return visual if visual == "DECLARED_BLANK" else "NOT_FOUND"

    @staticmethod
    def resolve_q2(visual: str, text: str, ml: Optional[str] = None) -> str:
        # P1: Visual detection usually identifies the exact box position relative to timber/bamboo labels
        if visual and visual not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK"):
            return visual
        if text and text not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK", None):
            return text
        return visual if visual == "DECLARED_BLANK" else "NOT_FOUND"

    @staticmethod
    def resolve_q3(visual: str, text: str, ml: Optional[str] = None) -> str:
        # Q3 is often more reliable via OCR/ML due to long treatment text strings
        if text and text not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK", None):
            return text
        if visual and visual not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK"):
            return visual
        return visual if visual == "DECLARED_BLANK" else "NOT_FOUND"

    @staticmethod
    def resolve_q4(visual: str, text: str, ml: Optional[str] = None) -> str:
        if visual and visual not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK", "ABSENT"):
            return visual
        if text and text not in ("BLANK", "NOT_FOUND", "DECLARED_BLANK", None):
            return text
        return "ABSENT" if visual in ("DECLARED_BLANK", "ABSENT") else "NOT_FOUND"

    @staticmethod
    def map_resolution(q1_res: str, q2_res: str, q3_res: str, q4_res: str) -> Dict[str, str]:
        """
        Final consistency check before returning results.
        Example: If Q2=NO, Q3 must be BLANK/NOT_FOUND.
        """
        # Logic: If Q2 is definitively NO, we force Q3 to BLANK to prevent noise
        # But we use DECLARED_BLANK to show it was intentionally ignored.
        if q2_res == "NO":
            q3_res = "DECLARED_BLANK"
            
        return {
            "q1": q1_res,
            "q2": q2_res,
            "q3": q3_res,
            "q4": q4_res
        }
