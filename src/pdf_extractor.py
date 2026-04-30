import fitz
import re
import io
import requests
import logging

logger = logging.getLogger(__name__)

def download_and_extract_pdf_text(pdf_url):
    """
    指定されたPDFのURLからファイルをダウンロードし、PyMuPDFを用いて全文テキストを抽出する。
    """
    logger.info(f"Downloading PDF from: {pdf_url}")
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        pdf_bytes = response.content
    except Exception as e:
        logger.error(f"Failed to download PDF: {e}")
        return ""

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n"
        
    # References以降のノイズ削減
    ref_match = re.search(r'\n(References|REFERENCES|Bibliography)\s*\n', full_text)
    if ref_match:
        full_text = full_text[:ref_match.start()]
        
    return full_text
