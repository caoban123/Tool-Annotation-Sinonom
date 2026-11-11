"""Bounded retries for non-terminating VietOCR lines; never accept truncated text."""
import numpy as np


def split_line(image):
    """Split at a low-ink column near the middle, preserving all source pixels."""
    if image.width < 64 or image.height < 4:
        return None
    pixels = np.asarray(image.convert('L'))
    ink = (pixels < 180).mean(axis=0)
    left, right = int(image.width * .35), int(image.width * .65)
    candidates = np.arange(left, right)
    # Prefer whitespace; distance breaks ties so blank crops split in the middle.
    costs = ink[left:right] + .01 * abs(candidates - image.width / 2) / image.width
    cut = int(candidates[np.argmin(costs)])
    return cut


def recover_line(image, recognize, initial, max_depth=3):
    """recognize([images]) returns per-line results, including token-limit errors."""
    def visit(crop, result, depth, offset):
        if not result.get('error'):
            return [result], []
        if result.get('code') != 'token_limit':
            return [], [dict(error=result['error'], bbox=[offset, 0, offset + crop.width, crop.height])]
        cut = split_line(crop) if depth < max_depth else None
        if cut is None:
            return [], [dict(error=result['error'], bbox=[offset, 0, offset + crop.width, crop.height])]
        children = [crop.crop((0, 0, cut, crop.height)), crop.crop((cut, 0, crop.width, crop.height))]
        try:
            responses = recognize(children)
            if len(responses) != 2:
                raise ValueError('VietOCR split retry returned wrong result count')
            texts, errors = [], []
            for child, response, x in zip(children, responses, (offset, offset + cut)):
                accepted, failed = visit(child, response, depth + 1, x)
                texts.extend(accepted); errors.extend(failed)
            return texts, errors
        finally:
            for child in children: child.close()
    accepted, errors = visit(image, initial, 0, 0)
    return dict(text=' '.join(r['text'] for r in accepted if r['text'].strip()),
                confidence=min((r['confidence'] for r in accepted), default=0.0),
                split_retry=True, errors=errors)
