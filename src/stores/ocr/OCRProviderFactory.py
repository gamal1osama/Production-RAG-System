from .OCRInterface import OCRProvider
from .OCREnums import ProviderType
from .providers import GeminiProvider, MistralProvider

from helpers.config import get_settings

import logging

logger = logging.getLogger("uvicorn.error")


class OCRProviderFactory:
    """
    Factory class that creates OCR provider instances.

    Mirrors the pattern of ``LLMProviderFactory`` but uses a static method
    since no per-instance configuration is needed — the factory reads from
    the global ``Settings`` object directly.

    Usage::

        # Uses OCR_PROVIDER from .env
        provider = OCRProviderFactory.get_provider()

        # Explicit override
        provider = OCRProviderFactory.get_provider("mistral")

        text = provider.extract_text_from_image(pil_image)
    """

    @staticmethod
    def get_provider(provider_type: str = None) -> OCRProvider:
        """
        Create and return an ``OCRProvider`` instance.

        Args:
            provider_type: One of ``"gemini"`` or ``"mistral"``.  If *None*,
                           the value of the ``OCR_PROVIDER`` environment
                           variable is used.

        Returns:
            A concrete ``OCRProvider`` ready to call.

        Raises:
            ValueError: If *provider_type* is not a recognised provider name.
        """
        settings = get_settings()
        resolved_type = (provider_type or settings.OCR_PROVIDER or "").lower().strip()

        logger.info(f"OCRProviderFactory: creating provider '{resolved_type}'")

        if resolved_type == ProviderType.GEMINI.value:
            return GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.GEMINI_MODEL_NAME,
            )

        if resolved_type == ProviderType.MISTRAL.value:
            return MistralProvider(
                api_key=settings.MISTRAL_API_KEY,
                model_name=settings.MISTRAL_MODEL_NAME,
            )

        raise ValueError(
            f"OCRProviderFactory: unsupported provider '{resolved_type}'. "
            f"Valid options: {[p.value for p in ProviderType]}"
        )
