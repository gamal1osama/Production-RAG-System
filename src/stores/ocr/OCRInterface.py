from abc import ABC, abstractmethod
from typing import Any


class OCRProvider(ABC):
    """
    Abstract base class (Strategy interface) for OCR providers.

    All concrete providers must implement these two methods so that the rest of
    the pipeline can remain provider-agnostic.
    """

    @abstractmethod
    def extract_text_from_image(self, image: Any, language_hint: str = "ar") -> str:
        """
        Extract text from a raster image.

        Args:
            image:         A PIL.Image.Image instance or raw image bytes.
            language_hint: BCP-47 language tag hinting at the document language
                           (e.g. "ar" for Arabic, "en" for English).
                           Providers may ignore this if their API handles it
                           automatically.

        Returns:
            Extracted text as a string. Returns an empty string on failure
            rather than raising (error is logged by the concrete implementation).
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return a human-readable identifier for this provider."""
        pass
