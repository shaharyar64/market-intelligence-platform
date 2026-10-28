"""PDF text extraction, shared by idea_testing (concept-card PDFs) and
knowledge (research-report PDFs). Deliberately has no dependency on either
package -- each caller decides its own max_chars, since a short concept
card and a full research report have very different reasonable limits.
"""
import io


def extract_pdf_text(data: bytes, max_chars: int | None = None) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if max_chars is not None:
        return text[:max_chars]
    return text
