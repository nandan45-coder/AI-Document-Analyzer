import difflib
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import fitz
import numpy as np

from app.services.govt_ocr_service import govt_ocr_service
from app.utils.govt_common import PDF_RENDER_ZOOM, normalize_ocr_spacing

logger = logging.getLogger("govt_document_intelligence")

# pyzbar gives reliable TYPE classification (QR vs 1D barcode) in addition to
# decoding. Optional - falls back to OpenCV QRCodeDetector-only behavior.
try:
    from pyzbar.pyzbar import decode as zbar_decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    logger.warning(
        "pyzbar not installed - QR/barcode TYPE classification will rely on "
        "OpenCV only, which cannot reliably distinguish a 1D barcode from a "
        "QR code."
    )

DIGITAL_SIGNATURE_PATTERNS = [
    r"digitally signed",
    r"digital signature",
    r"e-?sign(ed)?",
    r"signature valid",
]

VERIFICATION_URL_PATTERN = (
    r"(https?://[^\s]+|www\.[^\s]+|[a-z0-9\-]+\.maharashtra\.gov\.in[^\s]*)"
)

SIGNATURE_VALIDATION_PATTERNS = [
    r"valid(ity)? of (this )?(digital )?signature",
    r"signature (is )?valid",
    r"authenticated (copy|document)",
]

# Positive / pending verification-text keyword sets used by the rule-based
# confidence engine. Matched both exactly and fuzzily (OCR-corrupted text
# tolerant) via _extract_verification_text().
POSITIVE_TEXT_KEYWORDS = [
    "verified", "verification successful", "signature valid",
    "digitally signed", "valid",
]

PENDING_TEXT_KEYWORDS = [
    "pending verification", "verification pending", "under process",
    "awaiting verification",
]

CONTEXT_TEXT_KEYWORDS = [
    "government of maharashtra", "authority",
]

FUZZY_MATCH_CUTOFF = 0.72

# Whole-page fallback search is capped to this max dimension for speed.
MAX_SEARCH_DIMENSION = 2000

# Feature-matching templates are upscaled/downscaled to this max dimension -
# larger than the 40x40 template-matching version, since ORB/AKAZE/SIFT need
# more pixels to find usable keypoints on simple flat-color icon graphics.
FEATURE_TEMPLATE_MAX_DIM = 220


class GovtVerificationService:

    def __init__(self):

        self.green_template_path = "app/assets/green_tick.png"
        self.yellow_template_path = "app/assets/yellow_question.png"

        self.match_threshold = 0.60

        # Templates are loaded defensively - a missing template file must
        # never crash the whole application at import time. If loading
        # fails, template/feature matching for that symbol is skipped at
        # request time (still returns a graceful "Not Detected" result)
        # rather than raising.
        self.green_template = self._safe_load_template(self.green_template_path, "Green Tick")
        self.yellow_template = self._safe_load_template(self.yellow_template_path, "Yellow Question")

        self.green_gray = self._make_match_template(self.green_template)
        self.yellow_gray = self._make_match_template(self.yellow_template)

        # Feature detectors - created once and reused across requests.
        # Guarded defensively: some OpenCV builds/versions (seen on certain
        # Windows installs) don't expose every detector, e.g. AKAZE_create
        # can be missing depending on build flags. A missing detector must
        # never crash app startup - it's simply skipped at match time.
        try:
            self.orb = cv2.ORB_create(nfeatures=1000)
        except Exception:
            self.orb = None
            logger.warning("cv2.ORB_create unavailable in this OpenCV build - ORB feature matching disabled.")

        try:
            self.akaze = cv2.AKAZE_create()
        except Exception:
            self.akaze = None
            logger.warning("cv2.AKAZE_create unavailable in this OpenCV build - AKAZE feature matching disabled.")

        try:
            self.sift = cv2.SIFT_create()
        except Exception:
            self.sift = None
            logger.info("SIFT not available in this OpenCV build - skipping optional SIFT fallback.")

        self._template_feature_cache: Dict[Tuple[str, str], Tuple[Any, Any]] = {}

        self.green_feature_gray = self._make_feature_template(self.green_template)
        self.yellow_feature_gray = self._make_feature_template(self.yellow_template)

    # ---------------------------------------------------
    # Defensive template loading / preparation
    # ---------------------------------------------------

    def _safe_load_template(self, path: str, label: str) -> Optional[np.ndarray]:
        template = cv2.imread(path)
        if template is None:
            logger.error(
                "%s template not found at %s - symbol detection for this "
                "symbol will be skipped gracefully instead of crashing.",
                label, path,
            )
        return template

    def _make_match_template(self, template: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if template is None:
            return None
        return cv2.resize(cv2.cvtColor(template, cv2.COLOR_BGR2GRAY), (40, 40))

    def _make_feature_template(self, template: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if template is None:
            return None
        gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        return self._resize_max_dim(gray, FEATURE_TEMPLATE_MAX_DIM)

    def _resize_max_dim(self, image: np.ndarray, max_dim: int) -> np.ndarray:
        height, width = image.shape[:2]
        longest = max(height, width)
        if longest <= max_dim:
            return image
        scale = max_dim / longest
        return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

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

            physical_size_cm = self._get_physical_page_size_cm(file_path)

            crop, offset, region_meta = self._get_verification_crop(image, physical_size_cm)

            primary = self._analyze_verification_region(
                crop, offset, region_meta, stage="bottom_right_crop"
            )

            # Secondary whole-document search only runs if the targeted
            # region found neither a symbol nor supporting verification
            # text - keeps the common case fast while staying robust for
            # the minority of documents laid out differently.
            if not primary["symbol_found"] and not primary["verification_text_found"]:
                fallback_meta = {
                    "location": "Full Page (Fallback)",
                    "crop_percentage": {"width": 100.0, "height": 100.0},
                    "bounding_box": [0, 0, image.shape[1], image.shape[0]],
                }
                fallback = self._analyze_verification_region(
                    image, (0, 0), fallback_meta, stage="full_page_fallback"
                )
                if fallback["symbol_found"] or fallback["verification_text_found"]:
                    primary = fallback

            qr_barcode_result = self.detect_qr_and_barcode(image)
            seal_result = self.detect_seal_or_emblem(image)
            watermark_result = self.detect_watermark(image)
            text_indicators = self.detect_text_indicators(ocr_text)
            quality = self.analyze_document_quality(image)

            authenticity_signals = sum([
                primary["symbol_label"] == "Green Tick",
                qr_barcode_result.get("qr_detected", False),
                qr_barcode_result.get("barcode_detected", False),
                seal_result.get("seal_detected", False),
                text_indicators.get("digital_signature_found", False),
                text_indicators.get("verification_url_found", False),
                primary["verification_text_found"],
            ])

            result = {
                "success": True,

                # --- Preserved keys (backward compatible) ---
                "verification_status": primary["verification_status"],
                "verification_symbol": primary["symbol_label"],
                "ready_for_submission": primary["ready_for_submission"],
                "confidence": primary["shape_color_confidence"],

                # --- New/extended keys (additive only) ---
                "detected_symbol": primary["symbol_label"],
                "template_score": primary["template_score"],
                "feature_score": primary["feature_score"],
                "feature_matching_method": primary["feature_matching_method"],
                "verification_text": primary["verification_text"],
                "verification_text_confidence": primary["verification_text_confidence"],
                "region_ocr_confidence": primary["region_ocr_confidence"],
                "detection_region": primary["region_meta"],
                "matching_method": primary["matching_method"],
                "overall_confidence": primary["overall_confidence"],
                "overall_confidence_rule": primary["overall_confidence_rule"],
                "search_stage": primary["search_stage"],
                "symbol_location": primary["symbol_location"],
                "debug_scores": primary["debug_scores"],

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
    # Load PDF / Image (matches govt_ocr_service.py's PDF zoom exactly)
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
    # Adaptive Verification Region Localization
    #
    # Grounded in real-world observation: the verification symbol is almost
    # always in the bottom-right ~14cm x 10cm area. For PDFs we know the
    # actual physical page size, so the crop fraction is computed exactly
    # from that (14cm / page_width_cm, 10cm / page_height_cm). For plain
    # images (scans, mobile photos) physical size is unknown, so we fall
    # back to a fixed percentage (28% width x 22% height) tuned to
    # approximate that same real-world area on a typical A4-ish document -
    # still adaptive to the image's actual pixel dimensions, just not to
    # unknown physical units.
    # =====================================================

    def _get_physical_page_size_cm(self, file_path: str) -> Optional[Tuple[float, float]]:

        if os.path.splitext(file_path)[1].lower() != ".pdf":
            return None

        try:
            document = fitz.open(file_path)
            page = document.load_page(0)
            width_cm = page.rect.width * 2.54 / 72.0
            height_cm = page.rect.height * 2.54 / 72.0
            document.close()
            return width_cm, height_cm
        except Exception:
            logger.exception("Could not read physical PDF page size - falling back to percentage crop.")
            return None

    def _get_verification_crop(
        self,
        image: np.ndarray,
        physical_size_cm: Optional[Tuple[float, float]],
    ) -> Tuple[np.ndarray, Tuple[int, int], Dict[str, Any]]:

        height, width = image.shape[:2]

        if physical_size_cm:
            width_cm, height_cm = physical_size_cm
            crop_w_fraction = min(max(14.0 / max(width_cm, 1.0), 0.15), 0.60)
            crop_h_fraction = min(max(10.0 / max(height_cm, 1.0), 0.15), 0.60)
        else:
            crop_w_fraction = 0.28
            crop_h_fraction = 0.22

        left = int(width * (1 - crop_w_fraction))
        top = int(height * (1 - crop_h_fraction))

        crop = image[top:height, left:width]

        if crop.size == 0:
            crop = image
            left, top = 0, 0

        region_meta = {
            "location": "Bottom Right",
            "crop_percentage": {
                "width": round(crop_w_fraction * 100, 2),
                "height": round(crop_h_fraction * 100, 2),
            },
            "bounding_box": [left, top, width - left, height - top],
        }

        return crop, (left, top), region_meta

    # =====================================================
    # Region Analysis Pipeline
    # (preprocessing -> template match -> feature match -> OCR ->
    #  verification text -> confidence)
    # =====================================================

    def _analyze_verification_region(
        self,
        region_bgr: np.ndarray,
        offset: Tuple[int, int],
        region_meta: Optional[Dict[str, Any]],
        stage: str,
    ) -> Dict[str, Any]:

        enhanced_gray, enhanced_bgr, ocr_ready = self._preprocess_region(region_bgr)

        search_gray, scale_factor = self._resize_for_search(enhanced_gray)
        search_bgr = cv2.resize(
            enhanced_bgr, (search_gray.shape[1], search_gray.shape[0]),
            interpolation=cv2.INTER_AREA,
        )

        # --- Template Matching ---
        green_t_score, green_loc, green_size = self._multi_scale_match_with_location(
            search_gray, self.green_gray
        )
        yellow_t_score, yellow_loc, yellow_size = self._multi_scale_match_with_location(
            search_gray, self.yellow_gray
        )

        green_color_ratio = self._color_ratio_in_window(
            search_bgr, green_loc, green_size, lower=(40, 40, 40), upper=(90, 255, 255)
        )
        yellow_color_ratio = self._color_ratio_in_window(
            search_bgr, yellow_loc, yellow_size, lower=(20, 40, 40), upper=(35, 255, 255)
        )

        # --- Feature Matching (ORB preferred, AKAZE fallback, SIFT optional) ---
        # Scoped to a padded window around each template's own best-match
        # location (not the whole crop) - previously this ran on the entire
        # search region, which diluted real keypoint matches near the true
        # icon with incidental matches to unrelated nearby text/seal edges.
        green_window = self._extract_window_with_padding(search_gray, green_loc, green_size)
        yellow_window = self._extract_window_with_padding(search_gray, yellow_loc, yellow_size)

        green_feature_score, green_feature_method = self._feature_match_score(
            green_window, "green"
        )
        yellow_feature_score, yellow_feature_method = self._feature_match_score(
            yellow_window, "yellow"
        )

        green_capped_color = min(green_color_ratio * 5, 1.0)
        yellow_capped_color = min(yellow_color_ratio * 5, 1.0)

        # Rebalanced weights: template shape (0.50) and exact color presence
        # (0.30) are far more reliable for these flat, single-color icon
        # templates than ORB/AKAZE/SIFT feature counts (0.20), which have
        # very few real keypoints to work with on simple graphics and tend
        # to sit near their structural floor regardless of a true match.
        green_combined = (
            (green_t_score * 0.50) + (green_capped_color * 0.30) + (green_feature_score * 0.20)
        )
        yellow_combined = (
            (yellow_t_score * 0.50) + (yellow_capped_color * 0.30) + (yellow_feature_score * 0.20)
        )

        # Strong-evidence rule: when template shape AND exact color presence
        # are BOTH independently strong, that combination is overwhelming
        # evidence of a genuine match on its own - a weak/noisy feature
        # score (which is expected and normal for flat icon graphics)
        # should not be able to hold a confident detection back. Mirrors
        # the same rule-based-boost approach already used for the
        # overall_confidence engine below.
        STRONG_TEMPLATE_THRESHOLD = 0.55
        STRONG_COLOR_THRESHOLD = 0.65
        STRONG_EVIDENCE_FLOOR = 0.85

        green_strong_evidence = (
            green_t_score >= STRONG_TEMPLATE_THRESHOLD
            and green_capped_color >= STRONG_COLOR_THRESHOLD
        )
        yellow_strong_evidence = (
            yellow_t_score >= STRONG_TEMPLATE_THRESHOLD
            and yellow_capped_color >= STRONG_COLOR_THRESHOLD
        )

        if green_strong_evidence:
            green_combined = max(green_combined, STRONG_EVIDENCE_FLOOR)

        if yellow_strong_evidence:
            yellow_combined = max(yellow_combined, STRONG_EVIDENCE_FLOOR)

        debug_scores = {
            "green_template_score": round(green_t_score, 3),
            "yellow_template_score": round(yellow_t_score, 3),
            "green_color_ratio": round(green_color_ratio, 3),
            "yellow_color_ratio": round(yellow_color_ratio, 3),
            "green_feature_score": round(green_feature_score, 3),
            "yellow_feature_score": round(yellow_feature_score, 3),
            "green_strong_evidence_bonus_applied": green_strong_evidence,
            "yellow_strong_evidence_bonus_applied": yellow_strong_evidence,
            "green_combined": round(green_combined, 3),
            "yellow_combined": round(yellow_combined, 3),
            "match_threshold": self.match_threshold,
            "search_stage": stage,
        }

        symbol_label = "Not Detected"
        symbol_location = None
        shape_color_confidence = round(max(green_combined, yellow_combined) * 100, 2)
        template_score = round(max(green_t_score, yellow_t_score) * 100, 2)
        feature_score = round(max(green_feature_score, yellow_feature_score) * 100, 2)
        feature_method = None
        verification_status = "Unknown"
        ready_for_submission = False

        if green_combined > yellow_combined and green_combined >= self.match_threshold:
            symbol_label = "Green Tick"
            verification_status = "Verified"
            ready_for_submission = True
            shape_color_confidence = round(green_combined * 100, 2)
            symbol_location = self._scale_and_offset_location(green_loc, scale_factor, offset)
            feature_method = green_feature_method

        elif yellow_combined > green_combined and yellow_combined >= self.match_threshold:
            symbol_label = "Yellow Question Mark"
            verification_status = "Verification Pending"
            ready_for_submission = False
            shape_color_confidence = round(yellow_combined * 100, 2)
            symbol_location = self._scale_and_offset_location(yellow_loc, scale_factor, offset)
            feature_method = yellow_feature_method

        symbol_found = symbol_label != "Not Detected"

        # --- OCR on the verification region (binarized, OCR-optimized crop) ---
        region_text, region_ocr_confidence = govt_ocr_service.run_easyocr(ocr_ready)
        region_ocr_confidence = round(region_ocr_confidence * 100, 2)

        matched_keywords, verification_text_confidence = self._extract_verification_text(region_text)
        verification_text_found = len(matched_keywords) > 0

        matched_positive = any(m["keyword"] in POSITIVE_TEXT_KEYWORDS for m in matched_keywords)
        matched_pending = any(m["keyword"] in PENDING_TEXT_KEYWORDS for m in matched_keywords)

        overall_confidence, overall_rule = self._compute_overall_verification_confidence(
            symbol_label=symbol_label,
            shape_feature_score=max(green_combined, yellow_combined),
            ocr_confidence=region_ocr_confidence,
            text_confidence=verification_text_confidence,
            matched_positive=matched_positive,
            matched_pending=matched_pending,
        )

        matching_method_parts = ["template", "color"]
        if feature_method:
            matching_method_parts.append(f"feature({feature_method})")
        if verification_text_found:
            matching_method_parts.append("ocr_text")
        matching_method = "+".join(matching_method_parts)

        return {
            "symbol_label": symbol_label,
            "symbol_found": symbol_found,
            "symbol_location": symbol_location,
            "verification_status": verification_status,
            "ready_for_submission": ready_for_submission,
            "shape_color_confidence": shape_color_confidence,
            "template_score": template_score,
            "feature_score": feature_score,
            "feature_matching_method": feature_method,
            "region_ocr_confidence": region_ocr_confidence,
            "verification_text": [m["keyword"] for m in matched_keywords],
            "verification_text_confidence": verification_text_confidence,
            "verification_text_found": verification_text_found,
            "overall_confidence": overall_confidence,
            "overall_confidence_rule": overall_rule,
            "matching_method": matching_method,
            "region_meta": region_meta,
            "search_stage": stage,
            "debug_scores": debug_scores,
        }

    # =====================================================
    # Region Preprocessing
    # Resize, Grayscale, Contrast Enhancement, Histogram Equalization,
    # Gaussian Blur / Noise Removal, Sharpening, Deskew, Adaptive Threshold.
    #
    # NOTE: template/feature matching and color-ratio checks need continuous
    # tone + color information, so only the OCR-bound copy gets binarized.
    # The matching copy is enhanced but never thresholded.
    # =====================================================

    def _preprocess_region(self, region_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:

        resized_bgr = cv2.resize(
            region_bgr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC
        )

        gray = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2GRAY)

        # Reuse the OCR service's deskew logic instead of duplicating it -
        # keeps skew-correction behavior consistent across the module.
        gray = govt_ocr_service.deskew_image(gray)

        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        equalized = cv2.equalizeHist(denoised)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(equalized)

        blurred = cv2.GaussianBlur(contrast_enhanced, (3, 3), 0)

        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ])
        sharpened = cv2.filter2D(blurred, -1, kernel)

        # Matching copy: enhanced, NOT binarized - preserves gradients
        # needed for template/feature matching.
        enhanced_gray = sharpened

        # OCR copy: binarized last, same order used in govt_ocr_service.py.
        ocr_ready = cv2.adaptiveThreshold(
            sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
        )

        return enhanced_gray, resized_bgr, ocr_ready

    # =====================================================
    # Multi-Scale Template Matching (with best-match location)
    # =====================================================

    def _multi_scale_match_with_location(
        self, image: np.ndarray, template: Optional[np.ndarray]
    ) -> Tuple[float, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:

        if template is None:
            return 0.0, None, None

        best_score = 0.0
        best_loc = None
        best_size = None

        scales = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]

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

    def _scale_and_offset_location(
        self,
        loc: Optional[Tuple[int, int]],
        scale_factor: float,
        offset: Tuple[int, int],
    ):
        if loc is None:
            return None

        off_x, off_y = offset

        return {
            "x": int(loc[0] / scale_factor) + off_x,
            "y": int(loc[1] / scale_factor) + off_y,
        }

    def _extract_window_with_padding(
        self,
        image: np.ndarray,
        loc: Optional[Tuple[int, int]],
        size: Optional[Tuple[int, int]],
        padding_ratio: float = 1.0,
    ) -> np.ndarray:
        """
        Crops a window around a template match location, padded by
        `padding_ratio` x the match size on each side, so feature matching
        gets some surrounding context without diluting into unrelated
        page content far away. Falls back to the full image if no
        template match location is available (e.g. template missing).
        """

        if loc is None or size is None:
            return image

        x, y = loc
        w, h = size

        pad_x = int(w * padding_ratio)
        pad_y = int(h * padding_ratio)

        height, width = image.shape[:2]

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(width, x + w + pad_x)
        y2 = min(height, y + h + pad_y)

        window = image[y1:y2, x1:x2]

        if window.size == 0:
            return image

        return window

    def _color_ratio_in_window(
        self,
        image_bgr: np.ndarray,
        loc: Optional[Tuple[int, int]],
        size: Optional[Tuple[int, int]],
        lower: tuple,
        upper: tuple,
    ) -> float:

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
    # Feature Matching: ORB preferred, AKAZE fallback, SIFT optional
    #
    # Classical feature matching handles rotation, scale, lighting change,
    # and partial visibility better than template matching alone - none of
    # this requires any trained model or dataset.
    # =====================================================

    def _get_template_features(self, symbol: str, detector_name: str):

        cache_key = (symbol, detector_name)
        if cache_key in self._template_feature_cache:
            return self._template_feature_cache[cache_key]

        template_gray = self.green_feature_gray if symbol == "green" else self.yellow_feature_gray

        if template_gray is None:
            self._template_feature_cache[cache_key] = (None, None)
            return None, None

        detector = getattr(self, detector_name, None)

        if detector is None:
            self._template_feature_cache[cache_key] = (None, None)
            return None, None

        try:
            kp, des = detector.detectAndCompute(template_gray, None)
        except Exception:
            logger.exception("Feature template computation failed for %s/%s", symbol, detector_name)
            kp, des = None, None

        self._template_feature_cache[cache_key] = (kp, des)
        return kp, des

    def _feature_match_score(self, region_gray: np.ndarray, symbol: str) -> Tuple[float, Optional[str]]:

        detector_sequence = [("orb", cv2.NORM_HAMMING), ("akaze", cv2.NORM_HAMMING)]
        if self.sift is not None:
            detector_sequence.append(("sift", cv2.NORM_L2))

        for detector_name, norm in detector_sequence:

            if detector_name == "sift" and self.sift is None:
                continue

            detector = getattr(self, detector_name, None)

            if detector is None:
                continue

            kp_t, des_t = self._get_template_features(symbol, detector_name)

            if des_t is None or len(des_t) < 2:
                continue

            try:
                kp_r, des_r = detector.detectAndCompute(region_gray, None)
            except Exception:
                continue

            if des_r is None or len(des_r) < 2:
                continue

            try:
                matcher = cv2.BFMatcher(norm)
                raw_matches = matcher.knnMatch(des_t, des_r, k=2)
            except Exception:
                continue

            good_matches = []
            for pair in raw_matches:
                if len(pair) == 2:
                    m, n = pair
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)

            if not kp_t:
                continue

            score = min(len(good_matches) / len(kp_t), 1.0)

            # A weak score from one detector is still worth trying the next
            # (more robust) detector before giving up entirely.
            if score >= 0.12:
                return score, detector_name

        return 0.0, None

    # =====================================================
    # Verification Text Extraction (exact + fuzzy/OCR-tolerant matching)
    # =====================================================

    def _extract_verification_text(self, region_text: str) -> Tuple[List[Dict[str, Any]], float]:

        if not region_text or not region_text.strip():
            return [], 0.0

        text_lower = region_text.lower()
        lines = [line.strip() for line in text_lower.split("\n") if line.strip()]

        all_keywords = POSITIVE_TEXT_KEYWORDS + PENDING_TEXT_KEYWORDS + CONTEXT_TEXT_KEYWORDS
        matched: List[Dict[str, Any]] = []

        for keyword in all_keywords:

            if keyword in text_lower:
                matched.append({"keyword": keyword, "match_type": "exact", "confidence": 0.95})
                continue

            best_ratio = 0.0
            for line in lines:
                ratio = difflib.SequenceMatcher(None, keyword, line).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio

            if best_ratio >= FUZZY_MATCH_CUTOFF:
                matched.append({
                    "keyword": keyword,
                    "match_type": "fuzzy",
                    "confidence": round(best_ratio, 2),
                })

        if not matched:
            return [], 0.0

        avg_confidence = sum(m["confidence"] for m in matched) / len(matched) * 100
        return matched, round(avg_confidence, 2)

    # =====================================================
    # Confidence Engine
    # Combines template + feature + OCR + verification-text confidence into
    # one overall score, adjusted by the rule-based verification table.
    # =====================================================

    def _compute_overall_verification_confidence(
        self,
        symbol_label: str,
        shape_feature_score: float,
        ocr_confidence: float,
        text_confidence: float,
        matched_positive: bool,
        matched_pending: bool,
    ) -> Tuple[float, str]:

        base = (
            (shape_feature_score * 100 * 0.40)
            + (ocr_confidence * 0.20)
            + (text_confidence * 0.40)
        )

        if symbol_label == "Green Tick" and matched_positive:
            rule = "Green Tick + Verified Text = Very High Confidence"
            final = max(base, 90.0)

        elif symbol_label == "Yellow Question Mark" and matched_pending:
            rule = "Yellow Question + Pending Verification Text = Medium Confidence"
            final = min(max(base, 45.0), 65.0)

        elif symbol_label == "Green Tick" and not matched_positive:
            rule = "Green Tick + No Verification Text = Medium Confidence"
            final = min(max(base, 55.0), 75.0)

        elif symbol_label == "Not Detected" and matched_positive:
            rule = "No Symbol + Verified Text Found = Medium Confidence"
            final = min(max(base, 45.0), 65.0)

        else:
            rule = "No Symbol + No Verification Text = Low Confidence"
            final = min(base, 30.0)

        return round(max(0.0, min(final, 100.0)), 2), rule

    # =====================================================
    # QR Code + Barcode Detection
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
                    result["unconfirmed_code_region_detected"] = True

        except Exception:
            logger.exception("QR detection via OpenCV failed.")

        return result

    # =====================================================
    # Seal / Emblem / Government Logo Detection
    # =====================================================

    def _deduplicate_circles(
        self, circles: List[Tuple[int, int, int]]
    ) -> List[Tuple[int, int, int]]:
        """
        Hough Circle detection commonly returns several near-concentric
        circles (slightly different radii) around the SAME real stamped
        seal, inflating the candidate count. This merges circles whose
        centers are close relative to their radius into a single
        representative (the largest radius in the cluster), so one real
        seal is reported once instead of many times.
        """

        if not circles:
            return []

        remaining = list(circles)
        clusters: List[Tuple[int, int, int]] = []

        while remaining:
            base_x, base_y, base_r = remaining.pop(0)
            cluster = [(base_x, base_y, base_r)]

            still_remaining = []
            for (x, y, r) in remaining:
                distance = ((x - base_x) ** 2 + (y - base_y) ** 2) ** 0.5
                if distance <= max(base_r, r) * 1.2:
                    cluster.append((x, y, r))
                else:
                    still_remaining.append((x, y, r))

            remaining = still_remaining
            clusters.append(max(cluster, key=lambda c: c[2]))

        return clusters

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

                if 0.05 < dark_ratio < 0.6:
                    confirmed.append((int(x), int(y), int(r)))

            deduplicated = self._deduplicate_circles(confirmed)

            return {
                "seal_detected": len(deduplicated) > 0,
                "seal_candidate_count": len(deduplicated),
            }

        except Exception:
            logger.exception("Seal/emblem detection failed.")
            return {"seal_detected": False, "seal_candidate_count": 0}

    # =====================================================
    # Watermark Detection
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
    # Text-Based Indicators (whole-document OCR text: digital signature / URL)
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