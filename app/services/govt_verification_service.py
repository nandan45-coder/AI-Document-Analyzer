import logging
import os
from typing import Any, Dict, Optional, Tuple

import cv2
import fitz
import numpy as np

from app.utils.govt_common import PDF_RENDER_ZOOM, normalize_ocr_spacing
import re

logger = logging.getLogger("govt_document_intelligence")

# pyzbar gives reliable TYPE classification (QR vs 1D barcode) in addition to
# decoding. This is what fixes the earlier bug where a linear barcode was
# being reported as a detected QR code. OpenCV's QRCodeDetector is still used
# as a secondary confirmation path, but is no longer trusted to distinguish
# barcode-vs-QR on its own.
try:
    from pyzbar.pyzbar import decode as zbar_decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    logger.warning(
        "pyzbar not installed - QR/barcode TYPE classification will rely on "
        "OpenCV only, which cannot reliably distinguish a 1D barcode from a "
        "QR code. Install pyzbar (and the system libzbar0 library) for "
        "accurate barcode detection."
    )

# Text phrases that indicate a digital signature / verification block on
# Maharashtra certificates. Matched against OCR text case-insensitively.
DIGITAL_SIGNATURE_PATTERNS = [
    r"digitally signed",
    r"digital signature",
    r"e-?sign(ed)?",
    r"signature valid",
]

# Matched against BOTH the raw OCR text and a punctuation-normalized version
# (spaces stripped from around ':', '/', '.'), since OCR very commonly
# fragments URLs with stray spaces on scanned government certificates.
VERIFICATION_URL_PATTERN = (
    r"(https?://[^\s]+|www\.[^\s]+|[a-z0-9\-]+\.maharashtra\.gov\.in[^\s]*)"
)

SIGNATURE_VALIDATION_PATTERNS = [
    r"valid(ity)? of (this )?(digital )?signature",
    r"signature (is )?valid",
    r"authenticated (copy|document)",
]

# Full-page symbol search is capped to this max dimension (longer side) for
# speed - template matching cost grows with image area, and certificate
# scans/renders can be very large at 3x PDF zoom.
MAX_SEARCH_DIMENSION = 2000


class GovtVerificationService:

    def __init__(self):

        self.green_template_path = "app/assets/green_tick.png"
        self.yellow_template_path = "app/assets/yellow_question.png"

        self.match_threshold = 0.75

        # Load templates ONCE instead of on every verify_document() call.
        self.green_template = self._load_template(self.green_template_path, "Green Tick")
        self.yellow_template = self._load_template(self.yellow_template_path, "Yellow Question")

        self.green_gray = cv2.resize(
            cv2.cvtColor(self.green_template, cv2.COLOR_BGR2GRAY), (40, 40)
        )
        self.yellow_gray = cv2.resize(
            cv2.cvtColor(self.yellow_template, cv2.COLOR_BGR2GRAY), (40, 40)
        )

    def _load_template(self, path: str, label: str) -> np.ndarray:
        template = cv2.imread(path)
        if template is None:
            raise Exception(f"{label} template not found at {path}.")
        return template

    # =====================================================
    # Main Verification Function
    # =====================================================

    def verify_document(
        self,
        file_path: str,
        ocr_text: Optional[str] = None,
    ) -> Dict[str, Any]:

        try:
            image = self.load_document(file_path)

            symbol_result = self.detect_verification_symbol(image)

            qr_barcode_result = self.detect_qr_and_barcode(image)

            seal_result = self.detect_seal_or_emblem(image)

            watermark_result = self.detect_watermark(image)

            text_indicators = self.detect_text_indicators(ocr_text)

            quality = self.analyze_document_quality(image)

            authenticity_signals = sum([
                symbol_result.get("verification_symbol") == "Green Tick",
                qr_barcode_result.get("qr_detected", False),
                qr_barcode_result.get("barcode_detected", False),
                seal_result.get("seal_detected", False),
                text_indicators.get("digital_signature_found", False),
                text_indicators.get("verification_url_found", False),
            ])

            result = {
                "success": True,
                **symbol_result,
                "qr_code": qr_barcode_result,
                "seal_or_emblem": seal_result,
                "watermark": watermark_result,
                "text_indicators": text_indicators,
                "document_quality": quality,
                "authenticity_signal_count": authenticity_signals,
            }

            return result

        except Exception as e:
            logger.exception("Verification failed for %s", file_path)
            return {
                "success": False,
                "error": str(e),
            }

    # =====================================================
    # Load PDF / Image
    # Uses the SAME PDF_RENDER_ZOOM as govt_ocr_service.py so verification
    # and OCR are always working off matching resolution - previously this
    # rendered at the default 72 DPI while OCR used 3x zoom, which directly
    # hurt template-matching precision and skewed the document_quality
    # resolution/blur scores.
    # =====================================================

    def load_document(self, file_path: str) -> np.ndarray:

        extension = os.path.splitext(file_path)[1].lower()

        if extension == ".pdf":
            document = fitz.open(file_path)
            page = document.load_page(0)

            matrix = fitz.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM)
            pix = page.get_pixmap(matrix=matrix)

            image = np.frombuffer(pix.samples, dtype=np.uint8)
            image = image.reshape(pix.height, pix.width, pix.n)

            if pix.n == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
            elif pix.n == 1:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

            document.close()
            return image

        image = cv2.imread(file_path)

        if image is None:
            raise Exception("Unable to read document.")

        return image

    # =====================================================
    # Detect Verification Symbol (Green Tick / Yellow Question)
    #
    # Previously this only looked inside a HARDCODED crop box
    # (top 5-32%, right 68-98%). Real certificates place these symbols
    # inconsistently - e.g. a "Signature valid" tick can sit next to the
    # signature block in the middle of the page rather than the top-right
    # corner. This now searches the WHOLE page and reports wherever the
    # best match is found, which fixes false negatives on layouts that
    # don't match the old assumed position.
    # =====================================================

    def detect_verification_symbol(self, image: np.ndarray) -> Dict[str, Any]:

        search_image, scale_factor = self._resize_for_search(image)
        gray_full = cv2.cvtColor(search_image, cv2.COLOR_BGR2GRAY)

        green_score, green_loc, green_size = self._multi_scale_match_with_location(
            gray_full, self.green_gray
        )
        yellow_score, yellow_loc, yellow_size = self._multi_scale_match_with_location(
            gray_full, self.yellow_gray
        )

        green_color_ratio = self._color_ratio_in_window(
            search_image, green_loc, green_size, lower=(40, 40, 40), upper=(90, 255, 255)
        )
        yellow_color_ratio = self._color_ratio_in_window(
            search_image, yellow_loc, yellow_size, lower=(20, 40, 40), upper=(35, 255, 255)
        )

        green_combined = (green_score * 0.7) + (min(green_color_ratio * 5, 1.0) * 0.3)
        yellow_combined = (yellow_score * 0.7) + (min(yellow_color_ratio * 5, 1.0) * 0.3)

        if green_combined > yellow_combined and green_combined >= self.match_threshold:
            return {
                "verification_status": "Verified",
                "verification_symbol": "Green Tick",
                "ready_for_submission": True,
                "confidence": round(green_combined * 100, 2),
                "symbol_location": self._scale_location(green_loc, scale_factor),
            }

        elif yellow_combined > green_combined and yellow_combined >= self.match_threshold:
            return {
                "verification_status": "Verification Pending",
                "verification_symbol": "Yellow Question Mark",
                "ready_for_submission": False,
                "confidence": round(yellow_combined * 100, 2),
                "symbol_location": self._scale_location(yellow_loc, scale_factor),
            }

        return {
            "verification_status": "Unknown",
            "verification_symbol": "Not Detected",
            "ready_for_submission": False,
            "confidence": round(max(green_combined, yellow_combined) * 100, 2),
            "symbol_location": None,
        }

    def _resize_for_search(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        height, width = image.shape[:2]
        longest_side = max(height, width)

        if longest_side <= MAX_SEARCH_DIMENSION:
            return image, 1.0

        scale_factor = MAX_SEARCH_DIMENSION / longest_side
        resized = cv2.resize(
            image, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_AREA
        )
        return resized, scale_factor

    def _scale_location(self, loc: Optional[Tuple[int, int]], scale_factor: float):
        if loc is None:
            return None
        return {"x": int(loc[0] / scale_factor), "y": int(loc[1] / scale_factor)}

    def _color_ratio_in_window(
        self,
        image_bgr: np.ndarray,
        loc: Optional[Tuple[int, int]],
        size: Optional[Tuple[int, int]],
        lower: tuple,
        upper: tuple,
    ) -> float:
        """
        Computes the color-mask ratio inside the specific matched window
        rather than across the whole page. Checking the whole page (as the
        previous implementation did) dilutes the signal - a small green tick
        on a large white page barely moves a page-wide ratio. Checking just
        the matched window makes color a meaningful disambiguator again.
        """

        if loc is None or size is None:
            return 0.0

        x, y = loc
        w, h = size

        window = image_bgr[y: y + h, x: x + w]

        if window.size == 0:
            return 0.0

        hsv = cv2.cvtColor(window, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))

        return float(np.count_nonzero(mask)) / mask.size

    # =====================================================
    # Multi-Scale Template Matching (with best-match location)
    # =====================================================

    def _multi_scale_match_with_location(
        self, image: np.ndarray, template: np.ndarray
    ) -> Tuple[float, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:

        best_score = 0.0
        best_loc = None
        best_size = None

        scales = [0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 2.0, 2.5]

        for scale in scales:
            width = int(template.shape[1] * scale)
            height = int(template.shape[0] * scale)

            if width < 10 or height < 10:
                continue

            resized = cv2.resize(template, (width, height))

            if resized.shape[0] > image.shape[0] or resized.shape[1] > image.shape[1]:
                continue

            result = cv2.matchTemplate(image, resized, cv2.TM_CCOEFF_NORMED)
            _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_size = (width, height)

        return best_score, best_loc, best_size

    # =====================================================
    # QR Code + Barcode Detection
    #
    # Previously, OpenCV's QRCodeDetector could report `qr_detected: true`
    # purely from finding finder-pattern-like points, even with no decoded
    # data - which caused a 1D linear barcode to be misreported as a QR
    # code with null data. Now: pyzbar (when available) is the primary
    # source of TRUTH for both detection and type classification, since it
    # actually distinguishes barcode symbologies from QR codes. OpenCV is
    # only trusted to confirm a QR code when it successfully DECODES data -
    # a bare "points detected, no data" result is now reported separately as
    # an unconfirmed code region rather than a false QR claim.
    # =====================================================

    def detect_qr_and_barcode(self, image: np.ndarray) -> Dict[str, Any]:

        result = {
            "qr_detected": False,
            "qr_data": None,
            "barcode_detected": False,
            "barcode_data": None,
            "unconfirmed_code_region_detected": False,
            "detection_engine": None,
        }

        if PYZBAR_AVAILABLE:
            try:
                decoded_symbols = zbar_decode(image)

                for symbol in decoded_symbols:
                    data = symbol.data.decode("utf-8", errors="ignore")

                    if symbol.type == "QRCODE":
                        result["qr_detected"] = True
                        result["qr_data"] = data or result["qr_data"]
                    else:
                        result["barcode_detected"] = True
                        result["barcode_data"] = data or result["barcode_data"]

                if decoded_symbols:
                    result["detection_engine"] = "pyzbar"

            except Exception:
                logger.exception("Barcode/QR detection via pyzbar failed.")

        # OpenCV as secondary confirmation only - never overrides a
        # pyzbar-confirmed barcode classification.
        try:
            qr_detector = cv2.QRCodeDetector()
            data, points, _ = qr_detector.detectAndDecode(image)

            if points is not None:
                if data:
                    if not result["qr_detected"]:
                        result["qr_detected"] = True
                        result["qr_data"] = data
                        result["detection_engine"] = result["detection_engine"] or "opencv"
                elif not result["qr_detected"] and not result["barcode_detected"]:
                    # A code-like region exists but nothing could be decoded
                    # by either engine - flagged distinctly instead of being
                    # silently claimed as a confirmed QR code.
                    result["unconfirmed_code_region_detected"] = True

        except Exception:
            logger.exception("QR detection via OpenCV failed.")

        return result

    # =====================================================
    # Seal / Emblem / Government Logo Detection
    #
    # The previous Hough Circle pass had no post-filter, so it counted
    # letter loops, dotted borders, and scan noise as "seal candidates"
    # (24 on a document with exactly one visible seal). Each candidate
    # circle is now checked for a plausible ink-density ratio inside it -
    # a real stamped seal has a moderate, textured dark-pixel coverage
    # (from its printed pattern/text), not near-empty or near-solid.
    # =====================================================

    def detect_seal_or_emblem(self, image: np.ndarray) -> Dict[str, Any]:

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, 5)

            height, width = gray.shape[:2]

            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1.2,
                minDist=height / 6,
                param1=120,
                param2=55,
                minRadius=max(20, int(min(height, width) * 0.03)),
                maxRadius=int(min(height, width) / 3),
            )

            if circles is None:
                return {"seal_detected": False, "seal_candidate_count": 0}

            confirmed = []

            for (x, y, r) in np.uint16(np.around(circles[0])):

                mask = np.zeros_like(gray)
                cv2.circle(mask, (int(x), int(y)), int(r), 255, -1)

                region_pixels = gray[mask == 255]

                if region_pixels.size == 0:
                    continue

                dark_ratio = float(np.count_nonzero(region_pixels < 150)) / region_pixels.size

                # A real seal/stamp has visible ink texture: neither
                # near-blank (dark_ratio ~0) nor a solid dark blob
                # (dark_ratio ~1, which is more likely a photo or shadow).
                if 0.05 < dark_ratio < 0.6:
                    confirmed.append((int(x), int(y), int(r)))

            return {
                "seal_detected": len(confirmed) > 0,
                "seal_candidate_count": len(confirmed),
            }

        except Exception:
            logger.exception("Seal/emblem detection failed.")
            return {"seal_detected": False, "seal_candidate_count": 0}

    # =====================================================
    # Watermark Detection
    #
    # The 0.15 page-wide-ratio threshold assumed a watermark covers a large
    # fraction of the entire page. Real watermarks (e.g. a faint slogan
    # printed once near the middle of a certificate) are much smaller and
    # were falling under that bar. Threshold lowered based on observed
    # real-certificate ratios, and the search is now also restricted to a
    # margin-excluded central region to avoid header/footer/seal edges
    # inflating the faint-region count.
    # =====================================================

    def detect_watermark(self, image: np.ndarray) -> Dict[str, Any]:

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            height, width = gray.shape[:2]
            margin_y = int(height * 0.15)
            margin_x = int(width * 0.1)

            central_region = gray[margin_y: height - margin_y, margin_x: width - margin_x]

            if central_region.size == 0:
                central_region = gray

            mean = cv2.blur(central_region.astype(np.float32), (25, 25))
            mean_sq = cv2.blur((central_region.astype(np.float32)) ** 2, (25, 25))
            local_std = np.sqrt(np.maximum(mean_sq - mean ** 2, 0))

            faint_region_ratio = float(
                np.count_nonzero((local_std > 2) & (local_std < 15))
            ) / central_region.size

            watermark_likely = faint_region_ratio > 0.05

            return {
                "watermark_detected": watermark_likely,
                "faint_region_ratio": round(faint_region_ratio, 3),
            }

        except Exception:
            logger.exception("Watermark detection failed.")
            return {"watermark_detected": False, "faint_region_ratio": 0.0}

    # =====================================================
    # Text-Based Indicators (digital signature / verification URL)
    #
    # Now also matches against a punctuation-normalized copy of the OCR
    # text, so URLs fragmented by OCR spacing artifacts
    # ("https :// example . gov . in") are still recognized.
    # =====================================================

    def detect_text_indicators(self, ocr_text: Optional[str]) -> Dict[str, Any]:

        if not ocr_text:
            return {
                "digital_signature_found": False,
                "verification_url_found": False,
                "verification_url": None,
                "signature_validation_text_found": False,
            }

        text_lower = ocr_text.lower()

        digital_signature_found = any(
            re.search(pattern, text_lower) for pattern in DIGITAL_SIGNATURE_PATTERNS
        )

        signature_validation_found = any(
            re.search(pattern, text_lower) for pattern in SIGNATURE_VALIDATION_PATTERNS
        )

        url_match = re.search(VERIFICATION_URL_PATTERN, ocr_text, re.IGNORECASE)

        if not url_match:
            normalized_text = normalize_ocr_spacing(ocr_text)
            url_match = re.search(VERIFICATION_URL_PATTERN, normalized_text, re.IGNORECASE)

        return {
            "digital_signature_found": digital_signature_found,
            "verification_url_found": url_match is not None,
            "verification_url": url_match.group(0) if url_match else None,
            "signature_validation_text_found": signature_validation_found,
        }

    # =====================================================
    # Document Quality Analysis
    # =====================================================

    def analyze_document_quality(self, image: np.ndarray) -> Dict[str, Any]:

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]

        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

        brightness = float(np.mean(gray))

        contrast = float(np.std(gray))

        rotation_angle = self._estimate_rotation(gray)

        median = cv2.medianBlur(gray, 5)
        noise_level = float(np.mean(cv2.absdiff(gray, median)))

        resolution_score = min((width * height) / (1200 * 1600), 1.0) * 100

        readability_score = self._compute_readability_score(
            blur_score, brightness, contrast, noise_level
        )

        return {
            "blur_score": round(float(blur_score), 2),
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "estimated_rotation_degrees": round(rotation_angle, 2),
            "noise_level": round(noise_level, 2),
            "resolution_score": round(resolution_score, 2),
            "readability_score": round(readability_score, 2),
            "overall_quality_label": self._quality_label(readability_score),
        }

    def _estimate_rotation(self, gray: np.ndarray) -> float:
        try:
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=150)

            if lines is None:
                return 0.0

            angles = []
            for line in lines[:50]:
                rho, theta = line[0]
                angle = (theta * 180 / np.pi) - 90
                if -20 <= angle <= 20:
                    angles.append(angle)

            return float(np.median(angles)) if angles else 0.0

        except Exception:
            return 0.0

    def _compute_readability_score(
        self, blur_score: float, brightness: float, contrast: float, noise_level: float
    ) -> float:

        blur_component = min(blur_score / 500.0, 1.0) * 100
        brightness_component = 100 - abs(brightness - 165) / 165 * 100
        contrast_component = min(contrast / 60.0, 1.0) * 100
        noise_component = max(0.0, 100 - noise_level * 5)

        score = (
            blur_component * 0.35
            + max(brightness_component, 0) * 0.2
            + contrast_component * 0.25
            + noise_component * 0.20
        )

        return max(0.0, min(score, 100.0))

    def _quality_label(self, readability_score: float) -> str:
        if readability_score >= 75:
            return "Good"
        if readability_score >= 45:
            return "Fair"
        return "Poor"


govt_verification_service = GovtVerificationService()