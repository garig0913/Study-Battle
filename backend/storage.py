import os
import uuid
import tempfile
from typing import List, Dict, Tuple, Optional
import pdfplumber
from docx import Document as DocxDocument
from pptx import Presentation
from PIL import Image
import io
import re


UPLOAD_DIR = tempfile.gettempdir()
MAX_FILE_SIZE = 20 * 1024 * 1024


class TextExtractor:
    
    @staticmethod
    def extract_from_pdf(file_path: str) -> List[Dict]:
        pages = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append({
                        "page_number": i + 1,
                        "text": text,
                        "char_start": sum(len(p["text"]) for p in pages),
                    })
        except Exception as e:
            print(f"Error extracting PDF: {e}")
        return pages
    
    @staticmethod
    def extract_from_docx(file_path: str) -> List[Dict]:
        pages = []
        try:
            doc = DocxDocument(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            text = "\n".join(full_text)
            pages.append({
                "page_number": 1,
                "text": text,
                "char_start": 0,
            })
        except Exception as e:
            print(f"Error extracting DOCX: {e}")
        return pages
    
    @staticmethod
    def extract_from_pptx(file_path: str) -> List[Dict]:
        pages = []
        try:
            prs = Presentation(file_path)
            char_offset = 0
            for i, slide in enumerate(prs.slides):
                slide_text = []
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        slide_text.append(shape.text)
                text = "\n".join(slide_text)
                pages.append({
                    "page_number": i + 1,
                    "text": text,
                    "char_start": char_offset,
                })
                char_offset += len(text)
        except Exception as e:
            print(f"Error extracting PPTX: {e}")
        return pages
    
    @staticmethod
    def extract_from_txt(file_path: str) -> List[Dict]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            return [{
                "page_number": 1,
                "text": text,
                "char_start": 0,
            }]
        except Exception as e:
            print(f"Error extracting TXT: {e}")
            return []
    
    @staticmethod
    def extract_from_image(file_path: str) -> List[Dict]:
        return [{
            "page_number": 1,
            "text": "[Image file - OCR not available in this demo]",
            "char_start": 0,
        }]
    
    @classmethod
    def extract(cls, file_path: str, file_name: str) -> List[Dict]:
        ext = os.path.splitext(file_name)[1].lower()
        
        if ext == ".pdf":
            return cls.extract_from_pdf(file_path)
        elif ext == ".docx":
            return cls.extract_from_docx(file_path)
        elif ext == ".pptx":
            return cls.extract_from_pptx(file_path)
        elif ext == ".txt":
            return cls.extract_from_txt(file_path)
        elif ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
            return cls.extract_from_image(file_path)
        else:
            return cls.extract_from_txt(file_path)


class TextChunker:
    
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4
    
    def chunk_text(
        self, 
        text: str, 
        doc_id: str, 
        file_name: str, 
        page_number: int,
        base_char_offset: int = 0
    ) -> List[Dict]:
        chunks = []
        
        text = re.sub(r'\s+', ' ', text).strip()
        
        if not text:
            return chunks
        
        words = text.split(' ')
        current_chunk = []
        current_char_start = base_char_offset
        char_position = base_char_offset
        
        for word in words:
            current_chunk.append(word)
            
            chunk_text = ' '.join(current_chunk)
            if self._estimate_tokens(chunk_text) >= self.chunk_size:
                chunk_id = str(uuid.uuid4())
                chunk_end = char_position + len(word)
                
                chunks.append({
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "page_number": page_number,
                    "chunk_id": chunk_id,
                    "char_start": current_char_start,
                    "char_end": chunk_end,
                    "text": chunk_text,
                })
                
                overlap_words = int(len(current_chunk) * (self.overlap / self.chunk_size))
                if overlap_words > 0:
                    current_chunk = current_chunk[-overlap_words:]
                    overlap_text = ' '.join(current_chunk)
                    current_char_start = chunk_end - len(overlap_text)
                else:
                    current_chunk = []
                    current_char_start = chunk_end + 1
            
            char_position += len(word) + 1
        
        if current_chunk:
            chunk_id = str(uuid.uuid4())
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                "doc_id": doc_id,
                "file_name": file_name,
                "page_number": page_number,
                "chunk_id": chunk_id,
                "char_start": current_char_start,
                "char_end": char_position,
                "text": chunk_text,
            })
        
        return chunks


class FileStorage:
    
    def __init__(self):
        self.courses: Dict[str, Dict] = {}
        self.chunker = TextChunker()
    
    async def save_and_process_files(
        self, 
        files: List[Tuple[str, bytes, str]]
    ) -> Tuple[str, List[str], List[Dict]]:
        course_id = str(uuid.uuid4())
        processed_files = []
        all_chunks = []
        
        for file_name, file_content, content_type in files:
            if len(file_content) > MAX_FILE_SIZE:
                continue
            
            doc_id = str(uuid.uuid4())
            
            temp_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{file_name}")
            with open(temp_path, "wb") as f:
                f.write(file_content)
            
            try:
                pages = TextExtractor.extract(temp_path, file_name)
                
                for page in pages:
                    chunks = self.chunker.chunk_text(
                        text=page["text"],
                        doc_id=doc_id,
                        file_name=file_name,
                        page_number=page["page_number"],
                        base_char_offset=page["char_start"],
                    )
                    all_chunks.extend(chunks)
                
                processed_files.append(file_name)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        self.courses[course_id] = {
            "course_id": course_id,
            "files": processed_files,
            "chunks": all_chunks,
        }
        
        return course_id, processed_files, all_chunks
    
    def get_course_chunks(self, course_id: str) -> List[Dict]:
        if course_id in self.courses:
            return self.courses[course_id].get("chunks", [])
        return []
    
    def get_course_info(self, course_id: str) -> Optional[Dict]:
        return self.courses.get(course_id)


file_storage = FileStorage()
