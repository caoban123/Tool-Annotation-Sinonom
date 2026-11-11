"""Persistent JSON-lines VietOCR worker, run in its own Torch environment."""
import base64
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import traceback
from urllib.request import urlopen

WEIGHTS_SHA256 = '380512193a8b6cbf6fad80deacdc9b6939d10d473d199892fc6408d13775ea59'


def recognize_batch(images, process_input, translate, model, vocab, torch, device, batch_size):
    results = [None] * len(images)
    buckets = {}
    for index, image in enumerate(images):
        tensor = process_input(image, 32, 32, 1024)
        buckets.setdefault(tensor.shape[-1], []).append((index, tensor))
    for bucket in buckets.values():
        for start in range(0, len(bucket), batch_size):
            batch = bucket[start:start + batch_size]
            tensor = torch.cat([t for _, t in batch]).to(device)
            tokens, probabilities = translate(tensor, model, max_seq_length=512)
            for (index, _), sequence, probability in zip(batch, tokens.tolist(), probabilities):
                if 2 not in sequence:
                    results[index] = dict(error='VietOCR exceeded 512 tokens without EOS', code='token_limit')
                    continue
                text = vocab.decode(sequence)
                results[index] = dict(text=text, confidence=float(probability) if text.strip() else 0.0)
    return results


def main():
    protocol = sys.stdout
    # Libraries sometimes print downloads/model diagnostics to stdout.
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        import yaml
        from PIL import Image
        # Predictor imports the obsolete gdown/pkg_resources downloader even
        # for local weights. We download/verify weights ourselves, so use the
        # inference API directly and avoid that unnecessary import chain.
        from vietocr.tool.translate import build_model, process_input, translate
        options = json.loads(sys.argv[1])
        device = options['device'].replace('gpu:', 'cuda:')
        if device.startswith('cuda:') and (not torch.cuda.is_available() or
                int(device.split(':')[1]) >= torch.cuda.device_count()):
            raise RuntimeError('VietOCR: requested CUDA device unavailable')
        torch.set_num_threads(2)
        folder = Path(__file__).resolve().parents[1] / 'configs/vietocr'
        config = yaml.safe_load((folder / 'base.yml').read_text(encoding='utf-8'))
        config.update(yaml.safe_load((folder / 'vgg-transformer.yml').read_text(encoding='utf-8')))
        config['device'] = device
        config['cnn']['pretrained'] = False  # OCR checkpoint supplies the entire backbone.
        destination = Path(options['weights_dir']) / 'vgg_transformer.pth'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file():
            temporary = destination.with_suffix('.download')
            try:
                with urlopen(config['weights'], timeout=60) as source, temporary.open('wb') as target:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != WEIGHTS_SHA256:
                    raise RuntimeError('VietOCR download checksum mismatch; rerun to download again')
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        weights_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
        if weights_hash != WEIGHTS_SHA256:
            raise RuntimeError(f'Invalid VietOCR weights checksum. Remove {destination} and rerun.')
        model, vocab = build_model(config)
        model.load_state_dict(torch.load(destination, map_location=torch.device(device), weights_only=True))
        model.eval()
    print(json.dumps({'ready': True, 'weights_sha256': weights_hash,
                      'torch_version': torch.__version__}), file=protocol, flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.ExitStack() as stack, contextlib.redirect_stdout(sys.stderr), torch.inference_mode():
                images = [stack.enter_context(Image.open(io.BytesIO(base64.b64decode(encoded))))
                          for encoded in request['images']]
                recognize = lambda crops: recognize_batch(crops, process_input, translate, model, vocab,
                                                          torch, device, options.get('batch_size', 16))
                results = recognize(images)
                from OCR.utils.vietocr_lines import recover_line
                for index, result in enumerate(results):
                    if result.get('code') == 'token_limit':
                        results[index] = recover_line(images[index], recognize, result)
            response = {'results': results}
        except Exception:
            response = {'error': traceback.format_exc()}
        print(json.dumps(response, ensure_ascii=False, allow_nan=False), file=protocol, flush=True)


if __name__ == '__main__':
    main()
