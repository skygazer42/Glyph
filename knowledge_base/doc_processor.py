"""
Document processor for handling policy documents.
"""

import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import PyPDF2
import re

from ..agents.base.types import PolicyDocument


class DocumentProcessor:
    """Processor for various document formats."""

    def __init__(self):
        """Initialize the document processor."""
        self.supported_formats = {'.pdf', '.docx', '.txt', '.md'}

    def process_directory(self, directory_path: str) -> List[PolicyDocument]:
        """Process all supported documents in a directory."""
        documents = []

        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext in self.supported_formats:
                    try:
                        doc = self.process_file(file_path)
                        if doc:
                            documents.append(doc)
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")

        return documents

    def process_file(self, file_path: str) -> Optional[PolicyDocument]:
        """Process a single file."""
        ext = os.path.splitext(file_path)[1].lower()

        # Extract content based on file type
        if ext == '.pdf':
            content = self._extract_pdf_content(file_path)
        elif ext == '.docx':
            content = self._extract_docx_content(file_path)
        elif ext in ['.txt', '.md']:
            content = self._extract_text_content(file_path)
        else:
            return None

        if not content:
            return None

        # Extract metadata
        metadata = self._extract_metadata(file_path, content)

        # Create policy document
        return PolicyDocument(
            id=str(uuid.uuid4()),
            title=metadata.get('title', os.path.basename(file_path)),
            content=content,
            source=metadata.get('source', self._infer_source(file_path)),
            doc_type=metadata.get('doc_type', 'policy'),
            publish_date=metadata.get('publish_date'),
            relevant_departments=metadata.get('departments', []),
            policy_type=metadata.get('policy_type', self._infer_policy_type(content))
        )

    def _extract_pdf_content(self, file_path: str) -> str:
        """Extract text from PDF file."""
        content = []

        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                content.append(text)

        return '\n'.join(content)

    def _extract_docx_content(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        doc = Document(file_path)
        content = []

        for paragraph in doc.paragraphs:
            content.append(paragraph.text)

        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    content.append(cell.text)

        return '\n'.join(content)

    def _extract_text_content(self, file_path: str) -> str:
        """Extract text from plain text file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    def _extract_metadata(self, file_path: str, content: str) -> Dict[str, Any]:
        """Extract metadata from file path and content."""
        metadata = {}

        # Extract from filename
        filename = os.path.basename(file_path)

        # Try to extract title from first few lines
        lines = content.split('\n')[:10]
        for line in lines:
            line = line.strip()
            if len(line) > 10 and len(line) < 100:
                # Check if it looks like a title
                if any(keyword in line for keyword in ['方案', '通知', '办法', '实施细则', '政策']):
                    metadata['title'] = line
                    break

        # Extract date
        date_patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{4}-\d{1,2}-\d{1,2})',
            r'(20\d{2}年\d{1,2}月)',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, content[:500])
            if match:
                metadata['publish_date'] = match.group(1)
                break

        # Extract departments
        dept_patterns = [
            r'(山东省[^，。\n]+厅)',
            r'(山东省[^，。\n]+局)',
            r'(济南市[^，。\n]+厅)',
            r'(济南市[^，。\n]+局)',
            r'([^，。\n]+委员会)',
            r'([^，。\n]+办公室)',
        ]

        departments = []
        for pattern in dept_patterns:
            matches = re.findall(pattern, content)
            departments.extend(matches)

        metadata['departments'] = list(set(departments))  # Remove duplicates

        # Extract policy type
        if '补贴' in content:
            metadata['policy_type'] = 'subsidy'
        elif '以旧换新' in content:
            metadata['policy_type'] = 'replacement'
        elif '消费券' in content:
            metadata['policy_type'] = 'voucher'
        elif '实施细则' in filename or '实施细则' in content:
            metadata['policy_type'] = 'implementation'
        else:
            metadata['policy_type'] = 'general'

        return metadata

    def _infer_source(self, file_path: str) -> str:
        """Infer source from file path."""
        path_parts = file_path.split(os.sep)

        for part in path_parts:
            if '山东' in part:
                return '山东省政府'
            elif '济南' in part:
                return '济南市政府'

        return '未知来源'

    def _infer_policy_type(self, content: str) -> str:
        """Infer policy type from content."""
        content_lower = content.lower()

        if '以旧换新' in content_lower:
            return 'replacement'
        elif '消费券' in content_lower or '消费补贴' in content_lower:
            return 'subsidy'
        elif '汽车' in content_lower:
            return 'automotive'
        elif '家电' in content_lower:
            return 'appliance'
        elif '实施细则' in content_lower:
            return 'implementation'
        elif '通知' in content_lower:
            return 'notice'
        else:
            return 'policy'

    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove page numbers
        text = re.sub(r'第\s*\d+\s*页', '', text)

        # Fix common OCR errors
        text = text.replace(' ', '')

        return text.strip()