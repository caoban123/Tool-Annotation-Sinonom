import hashlib
import threading
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..db import get_db
from ..models import Segment, SegmentTranslation
from ..services.translation import translate_han

router = APIRouter(prefix='/api/translations', tags=['translations'])
# Bounded locks coalesce repeated requests in the local, single-process web app.
_locks = [threading.Lock() for _ in range(64)]


class TranslationRequest(BaseModel):
    revision: int = Field(ge=1)


@router.post('/{project_id}/{segment_id}')
def translate_segment(project_id: str, segment_id: str, payload: TranslationRequest,
                      request: Request, db: Session = Depends(get_db)):
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        raise HTTPException(403, 'Chỉ được yêu cầu dịch từ chính web đang mở.')
    lock_index = int(hashlib.sha256(segment_id.encode()).hexdigest()[:8], 16) % len(_locks)
    with _locks[lock_index]:
        segment = db.query(Segment).filter_by(id=segment_id, project_id=project_id, active=True).first()
        if not segment:
            raise HTTPException(404, 'Không tìm thấy ô đang hoạt động trong dự án.')
        if segment.language != 'han':
            raise HTTPException(400, 'Dịch tham khảo chỉ áp dụng cho ô Hán.')
        if segment.revision != payload.revision:
            raise HTTPException(409, 'Ô đã thay đổi. Tải lại dữ liệu trước khi dịch.')
        source = segment.clean_text
        if not source.strip():
            raise HTTPException(400, 'Ô không có nội dung để dịch.')
        if len(source) > 5000:
            raise HTTPException(400, 'Ô dài quá 5.000 ký tự. Tách ô trước khi dịch tham khảo.')
        cache_id = hashlib.sha256(f'azure:lzh:vi:{segment_id}:{source}'.encode()).hexdigest()
        cached = db.get(SegmentTranslation, cache_id)
        if cached:
            return _result(segment, cached.translated_text, True)
        # Release the read transaction while waiting for Azure; do not block edits.
        db.rollback()
        translated = translate_han(source)
        db.expire_all()
        current = db.query(Segment).filter_by(id=segment_id, project_id=project_id, active=True).first()
        if not current or current.revision != payload.revision or current.clean_text != source:
            raise HTTPException(409, 'Ô đã được sửa hoặc xóa trong lúc dịch. Tải lại rồi dịch nội dung mới.')
        result = _result(current, translated, False)
        db.add(SegmentTranslation(id=cache_id, segment_id=segment_id, translated_text=translated))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Another process may have populated the same cache in the meantime.
            existing = db.get(SegmentTranslation, cache_id)
            if not existing:
                raise HTTPException(409, 'Dữ liệu đã thay đổi trong lúc lưu bản dịch. Tải lại rồi thử lại.') from None
            result.update(translated_text=existing.translated_text, cached=True)
        return result


def _result(segment, translated, cached):
    return dict(segment_id=segment.id, revision=segment.revision, source_text=segment.clean_text,
                source_language='lzh', target_language='vi', provider='azure',
                translated_text=translated, cached=cached)
