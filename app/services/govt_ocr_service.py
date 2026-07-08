import logging
import os
from typing import Any, Dict, List, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
import easyocr

from app.utils.govt_common import PDF_RENDER_ZOOM

logger = logging.getLogger("govt_document_intelligence")

# Tesseract is an OPTIONAL fallback engine. EasyOCR remains primary as
# required. If pytesseract / the tesseract binary isn't installed on the
# host, we simply skip the fallback instead of crashing.
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning(
        "pytesseract not installed - fallback OCR engine disabled. "
        "EasyOCR will be used exclusively."
    )

# Confidence below this triggers the Tesseract fallback attempt (if available).
LOW_CONFIDENCE_THRESHOLD = 0.45

# PDF_RENDER_ZOOM now lives in app/utils/govt_common.py so this service and
# govt_verification_service.py always rasterize the same PDF at the same
# resolution. 3.0 ~= 216 DPI, a reliable floor for EasyOCR on scanned
# government certificates.


class GovtOCRService:

    def __init__(self):
        # English + Hindi + Marathi (Marathi and Hindi both use Devanagari
        # script and are compatible with English in the same EasyOCR reader).
        self.reader = easyocr.Reader(
            ['en', 'hi', 'mr'],
            gpu=False
        )

    # ==========================================
    # Public OCR Function
    # ==========================================

    def extract_text(self, file_path: str) -> Dict[str, Any]:

        try:
            extension = os.path.splitext(file_path)[1].lower()

            if extension == ".pdf":
                text, confidence, engine = self.extract_pdf(file_path)
            else:
                text, confidence, engine = self.extract_image(file_path)

            cleaned = self.clean_text(text)

            return {
                "success": True,
                "raw_text": text,
                "clean_text": cleaned,
                "total_characters": len(cleaned),
                "ocr_confidence": round(confidence * 100, 2),
                "ocr_engine": engine,
                "lines": [
                    line.strip()
                    for line in cleaned.split("\n")
                    if line.strip()
                ],
            }

        except Exception as e:
            logger.exception("OCR extraction failed for %s", file_path)
            return {
                "success": False,
                "error": str(e),
            }

    # ==========================================
    # OCR for Images
    # ==========================================

    def extract_image(self, image_path: str) -> Tuple[str, float, str]:

        image = cv2.imread(image_path)

        if image is None:
            raise Exception("Unable to read image.")

        processed = self.preprocess_image(image)

        text, confidence = self.run_easyocr(processed)

        engine = "easyocr"

        if TESSERACT_AVAILABLE and confidence < LOW_CONFIDENCE_THRESHOLD:
            logger.info(
                "EasyOCR confidence %.2f below threshold, trying Tesseract fallback.",
                confidence,
            )
            fallback_text = self.run_tesseract(processed)

            if fallback_text and len(fallback_text.strip()) > len(text.strip()):
                text = fallback_text
                engine = "tesseract_fallback"

        return text, confidence, engine

    # ==========================================
    # OCR for PDF
    # ==========================================

    def extract_pdf(self, pdf_path: str) -> Tuple[str, float, str]:

        document = fitz.open(pdf_path)

        complete_text = ""
        confidences: List[float] = []
        engine = "easyocr"

        matrix = fitz.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM)

        for page in document:

            pix = page.get_pixmap(matrix=matrix)

            img = np.frombuffer(pix.samples, dtype=np.uint8)
            img = img.reshape(pix.height, pix.width, pix.n)

            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            elif pix.n == 1:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            processed = self.preprocess_image(img)

            text, page_confidence = self.run_easyocr(processed)

            if TESSERACT_AVAILABLE and page_confidence < LOW_CONFIDENCE_THRESHOLD:
                fallback_text = self.run_tesseract(processed)
                if fallback_text and len(fallback_text.strip()) > len(text.strip()):
                    text = fallback_text
                    engine = "tesseract_fallback"

            complete_text += text + "\n"
            confidences.append(page_confidence)

        document.close()

        overall_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )

        return complete_text, overall_confidence, engine

    # ==========================================
    # EasyOCR Execution (with confidence capture)
    # ==========================================

    def run_easyocr(self, image: np.ndarray) -> Tuple[str, float]:

        results = self.reader.readtext(image, detail=1)

        if not results:
            return "", 0.0

        lines = []
        confidences = []

        for _bbox, text, conf in results:
            lines.append(text)
            confidences.append(conf)

        avg_confidence = sum(confidences) / len(confidences)

        return "\n".join(lines), avg_confidence

    # ==========================================
    # Tesseract Fallback Execution
    # ==========================================

    def run_tesseract(self, image: np.ndarray) -> str:

        if not TESSERACT_AVAILABLE:
            return ""

        try:
            # eng+hin+mar language packs must be installed on the host for
            # this to use all three; pytesseract degrades to whichever of
            # these are actually available.
            return pytesseract.image_to_string(image, lang="eng+hin+mar")
        except Exception:
            logger.exception("Tesseract fallback OCR failed.")
            return ""

    # ==========================================
    # Region-Based OCR
    # ==========================================

    def extract_region(
        self,
        image: np.ndarray,
        top_pct: float,
        bottom_pct: float,
        left_pct: float,
        right_pct: float,
    ) -> str:
        """
        Runs OCR on a specific rectangular region of an already-loaded image,
        expressed as percentages of width/height. Useful for isolating a
        known field zone (e.g. certificate number block) from surrounding
        header/footer noise.
        """

        height, width = image.shape[:2]

        top = int(height * top_pct)
        bottom = int(height * bottom_pct)
        left = int(width * left_pct)
        right = int(width * right_pct)

        region = image[top:bottom, left:right]

        if region.size == 0:
            return ""

        processed = self.preprocess_image(region)
        text, _confidence = self.run_easyocr(processed)

        return text

    # ==========================================
    # Image Enhancement Pipeline
    # ==========================================

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Order matters here. Thresholding must happen LAST - running adaptive
        threshold before sharpening (as in the previous implementation)
        binarizes the image first and then sharpens jagged edges, which
        degrades OCR accuracy instead of improving it.
        """

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        gray = self.deskew_image(gray)

        # Upscale for small certificate text
        gray = cv2.resize(
            gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC
        )

        # Denoise
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # Contrast enhancement (CLAHE handles uneven scan lighting better
        # than a flat contrast stretch)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Sharpen BEFORE thresholding, while the image still has gradients
        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ])
        gray = cv2.filter2D(gray, -1, kernel)

        # Adaptive threshold last, once contrast/sharpness are optimized
        gray = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

        return gray

    # ==========================================
    # Deskew Correction
    # ==========================================

    def deskew_image(self, gray: np.ndarray) -> np.ndarray:
        """
        Detects and corrects small rotation skew common in phone-scanned
        certificates, using the minimum-area bounding rectangle of dark
        (text/ink) pixels.
        """

        try:
            inverted = cv2.bitwise_not(gray)

            thresh = cv2.threshold(
                inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
            )[1]

            coords = cv2.findNonZero(thresh)

            if coords is None or len(coords) < 50:
                return gray

            angle = cv2.minAreaRect(coords)[-1]

            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            # Skip correction for negligible or clearly-wrong angles
            if abs(angle) < 0.5 or abs(angle) > 20:
                return gray

            (h, w) = gray.shape[:2]
            center = (w // 2, h // 2)

            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

            rotated = cv2.warpAffine(
                gray,
                matrix,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

            return rotated

        except Exception:
            logger.exception("Deskew step failed, continuing with original image.")
            return gray

    # ==========================================
    # Text Cleaning
    # ==========================================

    def clean_text(self, text: str) -> str:

        lines = []

        for line in text.split("\n"):
            line = line.strip()

            # Collapse repeated whitespace left by OCR spacing artifacts
            line = " ".join(line.split())

            # Drop lines that are pure OCR noise (single stray symbols)
            if len(line) <= 1 and not line.isalnum():
                continue

            if line:
                lines.append(line)

        return "\n".join(lines)


govt_ocr_service = GovtOCRService()