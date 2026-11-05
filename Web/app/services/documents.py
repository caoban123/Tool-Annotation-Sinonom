"""Immutable input snapshots and verified OCR page references."""
import hashlib
import json
from pathlib import Path
from ..models import Document, Segment


def current_document(db, project_id, language):
    return db.query(Document).filter_by(project_id=project_id, language=language, active=True).first()


def raw_snapshot(document):
    if document is None:
        return None
    data = document.raw_bytes
    if data is None:
        provenance = json.loads(document.provenance or '{}')
        path = Path(provenance.get('raw_storage_path') or '__missing_snapshot__')
        if path.is_file():
            data = path.read_bytes()
    return data if data is not None and hashlib.sha256(data).hexdigest() == document.raw_sha256 else None


def attach_page_metadata(db, document, metadata):
    if not isinstance(metadata, dict) or metadata.get('complete') is False:
        raise ValueError('Metadata không đầy đủ hoặc sai định dạng')
    pages = metadata.get('pages')
    if not isinstance(pages, list) or not pages:
        raise ValueError('Metadata thiếu pages')
    text = (raw_snapshot(document) or b'').decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    full_text = metadata.get('full_text')
    if not isinstance(full_text, str) or text.strip() != full_text.replace('\r\n', '\n').strip():
        raise ValueError('Metadata không khớp text gốc của tài liệu')
    previous, position, references = 0, 0, []
    for page in pages:
        number, content = page.get('page_number'), page.get('text')
        if type(number) is not int or number <= previous or not isinstance(content, str):
            raise ValueError('Metadata có số trang hoặc text không hợp lệ')
        previous = number
        if not content:
            continue
        offset = text.find(content, position)
        if offset < 0:
            raise ValueError('Nội dung trang không khớp text gốc')
        references.append((offset, offset + len(content), str(number)))
        position = offset + len(content)
    from .segmentation import split_sentences_han, split_sentences_viet
    splitter = split_sentences_han if document.language == 'han' else split_sentences_viet
    originals = splitter(text)
    segments = db.query(Segment).filter_by(document_id=document.id).order_by(Segment.order_index).all()
    if any(s.revision != 1 or not s.active or json.loads(s.parent_ids or '[]') for s in segments) or len(originals) != len(segments):
        raise ValueError('Chỉ gắn metadata trang ngay sau import, trước khi biên tập')
    position = 0
    for segment, original in zip(segments, originals):
        offset = text.find(original, position)
        if offset < 0:
            raise ValueError('Không khớp phân đoạn gốc')
        end = offset + len(original)
        segment.page_ref = ','.join(ref for left, right, ref in references if left < end and right > offset)
        position = end
    provenance = json.loads(document.provenance or '{}')
    provenance['pages'] = [dict(page_number=p['page_number'], method=p.get('method')) for p in pages]
    provenance['ocr_source_file'] = metadata.get('source_file')
    provenance['ocr_engine_info'] = metadata.get('engine_info', {})
    document.provenance = json.dumps(provenance, ensure_ascii=False)
