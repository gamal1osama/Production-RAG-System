from ..OCRInterface import OCRProvider

import base64
import io
import logging
import time
from typing import Any

logger = logging.getLogger("uvicorn.error")


class GeminiProvider(OCRProvider):
    """
    OCR provider backed by Google Gemini multimodal API.

    Uses the `google-generativeai` SDK to send image content to a Gemini
    vision-capable model and extract text from it.
    """

    PROMPT = (
        "Extract all text from this image exactly as it appears. "
        "Preserve the original reading order and layout. "
        "Return only the extracted text with no additional commentary."
    )

    def __init__(self, api_key: str, model_name: str = "gemini-flash-latest"):
        """
        Initialise the Gemini OCR provider.

        Args:
            api_key:    Google Gemini API key.
            model_name: Gemini model identifier that supports vision input.
        """
        import google.generativeai as genai

        if not api_key:
            logger.warning("GeminiProvider: GEMINI_API_KEY is not set. OCR calls will fail.")

        self.model_name = model_name
        self._api_key = api_key

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name=model_name)

        logger.info(f"GeminiProvider initialised with model: {model_name}")

    # ------------------------------------------------------------------
    # OCRProvider interface
    # ------------------------------------------------------------------

    def get_provider_name(self) -> str:
        return f"gemini/{self.model_name}"

    def extract_text_from_image(self, image: Any, language_hint: str = "ar") -> str:
        """
        Send *image* to Gemini and return the extracted text.

        Args:
            image:         PIL.Image.Image or raw PNG/JPEG bytes.
            language_hint: Ignored by Gemini (it auto-detects language), kept
                           for interface compatibility.

        Returns:
            Extracted text string, or "" on any error.
        """
        try:
            import google.generativeai as genai

            pil_image = self._to_pil(image)
            if pil_image is None:
                logger.error("GeminiProvider: could not convert input to a PIL image.")
                return ""

            start = time.perf_counter()
            response = self._model.generate_content([self.PROMPT, pil_image])
            elapsed = time.perf_counter() - start

            if not response or not response.text:
                logger.warning("GeminiProvider: received an empty response from the API.")
                return ""

            logger.debug(
                f"GeminiProvider: OCR call completed in {elapsed:.2f}s "
                f"({len(response.text)} chars extracted)."
            )
            return response.text

        except Exception as exc:
            logger.error(f"GeminiProvider.extract_text_from_image() failed: {exc}")
            return ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_pil(image: Any):
        """Convert *image* (PIL Image or bytes) to a PIL.Image.Image."""
        try:
            from PIL import Image

            if isinstance(image, Image.Image):
                return image

            if isinstance(image, (bytes, bytearray)):
                return Image.open(io.BytesIO(image)).convert("RGB")

            # If it's already a file-like object
            if hasattr(image, "read"):
                return Image.open(image).convert("RGB")

            logger.error(f"GeminiProvider._to_pil: unsupported image type: {type(image)}")
            return None

        except Exception as exc:
            logger.error(f"GeminiProvider._to_pil conversion failed: {exc}")
            return None
