import re
import unicodedata
import logging

logger = logging.getLogger("uvicorn.error")


class TextCleaner:
    """
    Normalises and cleans extracted text (both native PDF text and OCR output).

    Pipeline:
        1. Strip non-printable / control characters (except standard whitespace).
        2. Unicode NFC normalisation – consolidates combining characters so that
           Arabic diacritics are correctly composed rather than left as stray marks.
        3. Remove stray combining diacritical marks that remain after NFC
           (e.g. isolated tatweel, stray harakat outside word context).
        4. Collapse runs of whitespace (spaces, tabs, newlines) → single space.
        5. Strip leading / trailing whitespace.
    """

    # Regex: match any character that is a control character but is NOT
    # a standard whitespace character (\t, \n, \r, \x0b, \x0c).
    _CONTROL_CHARS_RE = re.compile(r"[^\S\t\n\r\x0b\x0c\x20-\x7e\u0080-\uFFFF]")

    # Regex: collapse runs of any whitespace (incl. newlines) to a single space.
    _WHITESPACE_RE = re.compile(r"\s+")

    # Unicode categories that represent combining / modifier characters
    # we want to strip after NFC normalisation.
    _UNWANTED_CATEGORIES = {"Cf"}  # Format characters (e.g. zero-width joiner remnants)

    def clean(self, text: str) -> str:
        """
        Clean and normalise *text*.

        Args:
            text: Raw string from PDF extraction or OCR provider.

        Returns:
            A cleaned, normalised single-line string.
            Returns an empty string if *text* is None or empty.
        """
        if not text:
            return ""

        try:
            # Step 1: NFC normalisation (Arabic diacritics, ligatures, etc.)
            text = unicodedata.normalize("NFC", text)

            # Step 2: Remove non-printable control characters
            text = self._CONTROL_CHARS_RE.sub("", text)

            # Step 3: Remove stray Unicode format characters (Cf category)
            text = "".join(
                ch for ch in text
                if unicodedata.category(ch) not in self._UNWANTED_CATEGORIES
                or ch in ("\t", "\n", "\r")  # keep standard whitespace
            )

            # Step 4: Collapse all whitespace → single space
            text = self._WHITESPACE_RE.sub(" ", text)

            # Step 5: Strip edges
            return text.strip()

        except Exception as exc:
            logger.warning(f"TextCleaner.clean() encountered an error: {exc}")
            # Graceful degradation: return the stripped original
            return text.strip() if isinstance(text, str) else ""
