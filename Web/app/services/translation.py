"""Azure text translation. Credentials never leave the backend."""
import os
import httpx
from fastapi import HTTPException

ENDPOINT = 'https://api.cognitive.microsofttranslator.com'


def translate_han(text: str) -> str:
    key = os.getenv('AZURE_TRANSLATOR_KEY', '').strip()
    if not key:
        raise HTTPException(503, 'Chưa cấu hình Azure Translator. Điền KEY trong Web/.env rồi khởi động lại web.')
    endpoint = os.getenv('AZURE_TRANSLATOR_ENDPOINT', ENDPOINT).strip().rstrip('/')
    # Only the documented global Text Translation endpoint is supported here.
    # Refuse typos/other hosts rather than sending credentials to them.
    if endpoint != ENDPOINT:
        raise HTTPException(503, 'AZURE_TRANSLATOR_ENDPOINT phải là https://api.cognitive.microsofttranslator.com')
    headers = {'Ocp-Apim-Subscription-Key': key}
    region = os.getenv('AZURE_TRANSLATOR_REGION', '').strip()
    if region and region.lower() != 'global':
        headers['Ocp-Apim-Subscription-Region'] = region
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False) as client:
            response = client.post(endpoint + '/translate',
                params={'api-version': '3.0', 'from': 'lzh', 'to': 'vi', 'textType': 'plain'},
                headers=headers, json=[{'Text': text}])
    except httpx.TimeoutException:
        raise HTTPException(504, 'Azure dịch quá lâu. Bạn có thể thử lại sau; chưa lưu bản dịch.') from None
    except httpx.RequestError:
        raise HTTPException(502, 'Không kết nối được Azure Translator. Kiểm tra mạng rồi thử lại.') from None
    if response.status_code in (401, 403):
        raise HTTPException(502, 'Azure từ chối truy cập. Kiểm tra KEY, Region và quyền tài nguyên trong Web/.env.')
    if response.status_code == 429:
        raise HTTPException(429, 'Azure đã giới hạn lượt gọi hoặc hết hạn mức. Chờ rồi thử lại, hoặc kiểm tra quota F0.')
    if response.status_code != 200:
        raise HTTPException(502, 'Azure chưa dịch được nội dung này. Thử lại sau; chưa lưu bản dịch.')
    try:
        translations = response.json()[0]['translations']
        result = next(t['text'] for t in translations if t['to'] == 'vi')
        if not isinstance(result, str) or not result.strip():
            raise ValueError('Empty translation')
        return result
    except (ValueError, KeyError, IndexError, TypeError, StopIteration):
        raise HTTPException(502, 'Azure trả kết quả không hợp lệ; chưa lưu bản dịch.') from None
