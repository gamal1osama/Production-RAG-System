from ..OCRInterface import OCRProvider

import base64
import io
import logging
import time
from typing import Any

logger = logging.getLogger("uvicorn.error")


class MistralProvider(OCRProvider):
    """
    OCR provider backed by Mistral AI's vision-capable chat models.

    Uses the `mistralai` SDK to send a base64-encoded image inside a
    multimodal chat message and extract text from the response.
    """

    PROMPT = (
        "Extract all text from this image exactly as it appears. "
        "Preserve the original reading order and layout. "
        "Return only the extracted text with no additional commentary."
    )

    def __init__(self, api_key: str, model_name: str = "mistral-small-latest"):
        """
        Initialise the Mistral OCR provider.

        Args:
            api_key:    Mistral API key.
            model_name: Mistral model identifier that supports vision input.
        """
        from mistralai import Mistral

        if not api_key:
            logger.warning("MistralProvider: MISTRAL_API_KEY is not set. OCR calls will fail.")

        self.model_name = model_name
        self._client = Mistral(api_key=api_key)

        logger.info(f"MistralProvider initialised with model: {model_name}")

    # ------------------------------------------------------------------
    # OCRProvider interface
    # ------------------------------------------------------------------

    def get_provider_name(self) -> str:
        return f"mistral/{self.model_name}"

    def extract_text_from_image(self, image: Any, language_hint: str = "ar") -> str:
        """
        Send *image* to Mistral and return the extracted text.

        Args:
            image:         PIL.Image.Image or raw PNG/JPEG bytes.
            language_hint: Appended to the prompt for language-aware extraction.

        Returns:
            Extracted text string, or "" on any error.
        """
        try:
            b64_image = self._to_base64(image)
            if b64_image is None:
                logger.error("MistralProvider: could not convert input to base64.")
                return ""

            prompt_with_lang = f"{self.PROMPT} The document language is '{language_hint}'."

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": f"data:image/png;base64,{b64_image}",
                        },
                        {
                            "type": "text",
                            "text": prompt_with_lang,
                        },
                    ],
                }
            ]

            start = time.perf_counter()
            response = self._client.chat.complete(
                model=self.model_name,
                messages=messages,
            )
            elapsed = time.perf_counter() - start

            if (
                not response
                or not response.choices
                or not response.choices[0].message
                or not response.choices[0].message.content
            ):
                logger.warning("MistralProvider: received an empty response from the API.")
                return ""

            text = response.choices[0].message.content
            logger.debug(
                f"MistralProvider: OCR call completed in {elapsed:.2f}s "
                f"({len(text)} chars extracted)."
            )
            return text

        except Exception as exc:
            logger.error(f"MistralProvider.extract_text_from_image() failed: {exc}")
            return ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_base64(image: Any) -> str | None:
        """Convert *image* (PIL Image or bytes) to a PNG base64 string."""
        try:
            from PIL import Image

            if isinstance(image, Image.Image):
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode("utf-8")

            if isinstance(image, (bytes, bytearray)):
                return base64.b64encode(image).decode("utf-8")

            if hasattr(image, "read"):
                return base64.b64encode(image.read()).decode("utf-8")

            logger.error(f"MistralProvider._to_base64: unsupported image type: {type(image)}")
            return None

        except Exception as exc:
            logger.error(f"MistralProvider._to_base64 conversion failed: {exc}")
            return None
