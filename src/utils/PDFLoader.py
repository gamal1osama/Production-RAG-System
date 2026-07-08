"""
utils/PDFLoader.py

Drop-in replacement for ``langchain_community.document_loaders.PyMuPDFLoader``.

The public API (``load()``) returns the same ``List[langchain_core.documents.Document]``
structure that ``PyMuPDFLoader`` produces, so the rest of the pipeline
(``ProcessController``, ``split_file_content``, Celery tasks) requires zero changes.

Internal pipeline per page

1. ``segment_page(page_num)`` classifies every block on the page as
   either a **text** block or an **image** block using PyMuPDF's
   ``get_text("dict")`` + ``get_image_info()``.
2. Native text blocks → text extracted directly (zero OCR cost).
3. Image blocks        → rendered to a PIL Image → sent to the configured
   ``OCRProvider`` → returned text.
4. All text is cleaned through ``TextCleaner.clean()``.
5. All block texts are joined in reading order to form the final page string.
6. The page string is wrapped in a ``langchain_core.documents.Document``
   with the same metadata keys that ``PyMuPDFLoader`` produces.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24 uses 'pymupdf' as the module name
except ImportError:
    import fitz  # Fallback for older installations that still ship as 'fitz'
from langchain_core.documents import Document

from utils.CleanText import TextCleaner

logger = logging.getLogger("uvicorn.error")

# Minimum character count for a text block to be considered "has real content".
# Blocks with only whitespace/punctuation below this threshold are ignored.
_MIN_TEXT_LENGTH = 2

# PyMuPDF block type constants
_BLOCK_TYPE_TEXT = 0
_BLOCK_TYPE_IMAGE = 1


class PDFLoader:
    """
    PDF document loader with block-level OCR for image regions.

    Intended as a **drop-in replacement** for
    ``langchain_community.document_loaders.PyMuPDFLoader``.

    The only method the existing pipeline calls is ``load()``, which returns
    a ``List[Document]`` — one element per page — exactly like PyMuPDFLoader.

    Additional public methods (``segment_page``, ``get_text_for_block``,
    ``get_image_for_block``, ``get_page_count``, ``get_page_metadata``) are
    provided for completeness and direct use when finer-grained control is
    needed.
    """

    def __init__(self, file_path: str, provider: Optional[str] = None):
        """
        Args:
            file_path: Absolute or relative path to the PDF file.
            provider:  Optional OCR provider override (``"gemini"`` or
                       ``"mistral"``).  If *None*, the value of the
                       ``OCR_PROVIDER`` environment variable is used.
        """
        self.file_path = file_path
        self._provider_override = provider

        # Lazy-loaded: only created when the first image block is encountered.
        self._ocr_provider = None
        self._ocr_provider_attempted = False

        self._cleaner = TextCleaner()

        # Open the document once; keep it alive for the lifetime of this loader.
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDFLoader: file not found at '{file_path}'")

        self.doc: fitz.Document = fitz.open(file_path)
        logger.info(
            f"PDFLoader: opened '{os.path.basename(file_path)}' "
            f"({self.doc.page_count} page(s))."
        )

    # Primary public method - LangChain compatibility

    def load(self) -> List[Document]:
        """
        Process all pages and return a list of LangChain Documents.

        Each ``Document`` contains:
        - ``page_content``: merged, cleaned text for the page (native + OCR).
        - ``metadata``:     same keys as ``PyMuPDFLoader`` produces.

        Returns:
            ``List[Document]`` — one document per page.
        """
        documents: List[Document] = []
        total_pages = self.doc.page_count

        for page_num in range(total_pages):
            try:
                page_text = self._process_page(page_num)
                metadata = self.get_page_metadata(page_num)
                documents.append(
                    Document(page_content=page_text, metadata=metadata)
                )
            except Exception as exc:
                logger.error(
                    f"PDFLoader.load(): error processing page {page_num} "
                    f"of '{self.file_path}': {exc}"
                )
                # Append an empty document for the failed page so page
                # numbering remains consistent downstream.
                documents.append(
                    Document(
                        page_content="",
                        metadata=self.get_page_metadata(page_num),
                    )
                )

        logger.info(
            f"PDFLoader.load(): completed — {len(documents)} page(s) loaded "
            f"from '{os.path.basename(self.file_path)}'."
        )
        return documents

    # Page-level helpers

    def get_page_count(self) -> int:
        """Return the total number of pages in the document."""
        return self.doc.page_count

    def get_page_metadata(self, page_num: int) -> dict:
        """
        Build the metadata dict for a page, matching ``PyMuPDFLoader``'s output.

        Keys produced by the original loader (verified from LangChain source):
        ``source``, ``file_path``, ``page``, ``total_pages``,
        ``format``, ``title``, ``author``, ``subject``, ``keywords``,
        ``creator``, ``producer``, ``creationDate``, ``modDate``, ``trapped``.
        """
        meta = self.doc.metadata or {}
        return {
            "source": self.file_path,
            "file_path": self.file_path,
            "page": page_num,
            "total_pages": self.doc.page_count,
            "format": meta.get("format", ""),
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "creationDate": meta.get("creationDate", ""),
            "modDate": meta.get("modDate", ""),
            "trapped": meta.get("trapped", ""),
        }

    # Block-level API

    def segment_page(self, page_num: int) -> List[dict]:
        """
        Segment a PDF page into typed blocks.

        Each block dict has the following keys:

        - ``bbox``       (tuple[float, float, float, float]):
                         Bounding box ``(x0, y0, x1, y1)`` in page coordinates.
        - ``type``       (str): ``"text"`` or ``"image"``.
        - ``content``    (str | None): Extracted text for text blocks; ``None``
                         for image blocks (retrieve via ``get_image_for_block``).
        - ``_page_num``  (int): Stored so ``get_image_for_block`` can render
                         the correct page without extra arguments.

        Blocks are sorted by their top-left y coordinate (reading order).

        Args:
            page_num: Zero-based page index.

        Returns:
            Sorted list of block dicts.
        """
        page: fitz.Page = self.doc[page_num]
        blocks: List[dict] = []

        # Text blocks via get_text("dict")
        text_data = page.get_text("dict")
        for raw_block in text_data.get("blocks", []):
            block_type = raw_block.get("type", -1)

            if block_type == _BLOCK_TYPE_TEXT:
                # Concatenate all spans in all lines of this block
                text_parts = []
                for line in raw_block.get("lines", []):
                    for span in line.get("spans", []):
                        text_parts.append(span.get("text", ""))
                raw_text = " ".join(text_parts)

                if len(raw_text.strip()) >= _MIN_TEXT_LENGTH:
                    blocks.append(
                        {
                            "bbox": tuple(raw_block["bbox"]),
                            "type": "text",
                            "content": raw_text,
                            "_page_num": page_num,
                        }
                    )

            elif block_type == _BLOCK_TYPE_IMAGE:
                # Image block reported by get_text("dict")
                blocks.append(
                    {
                        "bbox": tuple(raw_block["bbox"]),
                        "type": "image",
                        "content": None,
                        "_page_num": page_num,
                    }
                )

        # Additional image blocks via get_image_info() 
        # get_text("dict") may miss some embedded images; cross-reference with
        # get_image_info() to avoid silent omissions.
        try:
            for img_info in page.get_image_info(xrefs=True):
                img_bbox = tuple(img_info.get("bbox", ()))
                if not img_bbox or len(img_bbox) != 4:
                    continue

                # Skip if already covered by a block from get_text("dict")
                if not _bbox_already_covered(img_bbox, blocks):
                    blocks.append(
                        {
                            "bbox": img_bbox,
                            "type": "image",
                            "content": None,
                            "_page_num": page_num,
                        }
                    )
        except Exception as exc:
            logger.warning(
                f"PDFLoader.segment_page(): get_image_info() failed on page "
                f"{page_num}: {exc}. Continuing with blocks from get_text()."
            )

        # Sort by y0 then x0 (top-to-bottom, left-to-right)
        blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        return blocks

    def get_text_for_block(self, block: dict) -> str:
        """
        Return the native text content of a text block.

        Args:
            block: A block dict produced by ``segment_page()``.

        Returns:
            The ``content`` field for text blocks, or ``""`` for image blocks.
        """
        if block.get("type") != "text":
            return ""
        return block.get("content") or ""

    def get_image_for_block(self, block: dict) -> Any:
        """
        Render the region described by *block* as a PIL Image.

        Uses ``page.get_pixmap(clip=bbox)`` to rasterise only the block's
        bounding box at 2× scale for better OCR accuracy.

        Args:
            block: A block dict produced by ``segment_page()``.

        Returns:
            A ``PIL.Image.Image`` instance, or ``None`` on failure.
        """
        if block.get("type") != "image":
            return None

        try:
            from PIL import Image
            import io as _io

            page_num = block["_page_num"]
            bbox = fitz.Rect(block["bbox"])
            page: fitz.Page = self.doc[page_num]

            # 2× scale matrix for better OCR quality
            matrix = fitz.Matrix(2.0, 2.0)
            pixmap = page.get_pixmap(matrix=matrix, clip=bbox)

            img_bytes = pixmap.tobytes("png")
            return Image.open(_io.BytesIO(img_bytes)).convert("RGB")

        except Exception as exc:
            logger.error(f"PDFLoader.get_image_for_block() failed: {exc}")
            return None

    # Internal pipeline

    def _process_page(self, page_num: int) -> str:
        """
        Process a single page: segment → extract / OCR → clean → merge.

        Args:
            page_num: Zero-based page index.

        Returns:
            Merged, cleaned text string for the page.
        """
        blocks = self.segment_page(page_num)
        text_parts: List[str] = []

        text_block_count = 0
        image_block_count = 0

        for block in blocks:
            if block["type"] == "text":
                text_block_count += 1
                raw = self.get_text_for_block(block)
                cleaned = self._cleaner.clean(raw)
                if cleaned:
                    text_parts.append(cleaned)

            elif block["type"] == "image":
                image_block_count += 1
                ocr_text = self._run_ocr_on_block(block)
                if ocr_text:
                    text_parts.append(ocr_text)

        logger.debug(
            f"PDFLoader._process_page(page={page_num}): "
            f"{text_block_count} text block(s), {image_block_count} image block(s)."
        )

        return "\n".join(text_parts)

    def _run_ocr_on_block(self, block: dict) -> str:
        """
        OCR a single image block and return cleaned text.

        Lazy-initialises the OCR provider on the first image block encountered.
        Subsequent calls reuse the same provider instance.

        Args:
            block: An image-type block dict from ``segment_page()``.

        Returns:
            Cleaned OCR text, or ``""`` on failure / missing provider.
        """
        provider = self._get_ocr_provider()
        if provider is None:
            logger.warning(
                "PDFLoader._run_ocr_on_block(): no OCR provider available; "
                "image block will produce no text."
            )
            return ""

        try:
            pil_image = self.get_image_for_block(block)
            if pil_image is None:
                return ""

            raw_ocr = provider.extract_text_from_image(pil_image)
            return self._cleaner.clean(raw_ocr)

        except Exception as exc:
            logger.error(
                f"PDFLoader._run_ocr_on_block(): OCR call failed: {exc}"
            )
            return ""

    def _get_ocr_provider(self):
        """
        Lazy-load and cache the OCR provider.

        The provider is only instantiated when the first image block is
        encountered. If the PDF is text-only, this method is never called
        and no API client is ever created.
        """
        if self._ocr_provider is not None:
            return self._ocr_provider

        if self._ocr_provider_attempted:
            # Already tried and failed — don't retry on every block.
            return None

        self._ocr_provider_attempted = True
        try:
            from stores.ocr.OCRProviderFactory import OCRProviderFactory

            self._ocr_provider = OCRProviderFactory.get_provider(
                self._provider_override
            )
            logger.info(
                f"PDFLoader: OCR provider '{self._ocr_provider.get_provider_name()}' "
                f"initialised."
            )
        except Exception as exc:
            logger.error(
                f"PDFLoader._get_ocr_provider(): failed to create OCR provider: {exc}. "
                f"Image blocks will produce no text."
            )
            self._ocr_provider = None

        return self._ocr_provider

    # Context manager support (mirrors fitz.Document behaviour)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the underlying fitz document and release file handles."""
        if self.doc:
            try:
                self.doc.close()
            except Exception:
                pass


# Module-level helpers

def _bbox_already_covered(bbox: tuple, existing_blocks: List[dict]) -> bool:
    """
    Return True if *bbox* substantially overlaps with any existing block's bbox.

    Used to avoid double-counting images that appear in both ``get_text("dict")``
    and ``get_image_info()``.
    """
    x0, y0, x1, y1 = bbox
    area = max((x1 - x0) * (y1 - y0), 1e-6)

    for block in existing_blocks:
        bx0, by0, bx1, by1 = block["bbox"]
        # Intersection
        ix0 = max(x0, bx0)
        iy0 = max(y0, by0)
        ix1 = min(x1, bx1)
        iy1 = min(y1, by1)
        if ix1 > ix0 and iy1 > iy0:
            intersection = (ix1 - ix0) * (iy1 - iy0)
            if intersection / area > 0.5:  # > 50% overlap → already covered
                return True
    return False
