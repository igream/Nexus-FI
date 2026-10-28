import io
from abc import ABC, abstractmethod
from typing import Optional

class BaseOCREngine(ABC):
    @abstractmethod
    def extract_text_from_bytes(self, image_bytes: bytes) -> str:
        """Extrae texto desde los bytes de una imagen (PNG/JPEG)."""
        pass

class LocalRapidOCREngine(BaseOCREngine):
    """Motor de OCR local basado en RapidOCR ONNX."""
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()

    def extract_text_from_bytes(self, image_bytes: bytes) -> str:
        try:
            result, _ = self.engine(image_bytes)
            if not result:
                return ""
            lines = [line[1] for line in result if len(line) > 1 and line[1].strip()]
            return "\n".join(lines)
        except Exception as e:
            print(f"[OCR Local Error]: {e}")
            return ""

class AWSTextractOCREngine(BaseOCREngine):
    """Motor de OCR cloud basado en AWS Textract DetectDocumentText."""
    def __init__(self, region_name: str = "us-east-1"):
        import boto3
        self.client = boto3.client("textract", region_name=region_name)

    def extract_text_from_bytes(self, image_bytes: bytes) -> str:
        try:
            response = self.client.detect_document_text(
                Document={"Bytes": image_bytes}
            )
            lines = [
                block["Text"] 
                for block in response.get("Blocks", []) 
                if block.get("BlockType") == "LINE"
            ]
            return "\n".join(lines)
        except Exception as e:
            print(f"[AWS Textract Error]: {e}")
            return ""

def get_ocr_engine(provider: str = "local", region: str = "us-east-1") -> BaseOCREngine:
    """Factory para instanciar el motor OCR seleccionado."""
    if provider == "aws_textract":
        return AWSTextractOCREngine(region_name=region)
    return LocalRapidOCREngine()
