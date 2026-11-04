"""Small, ordered OCR regions for ruled classical texts; no text rewriting."""
import time

from PIL import Image, ImageOps, ImageFilter


class OCRRegionError(RuntimeError):
    """A generation is incomplete and may be retried on a smaller image."""


class GenerationGuard:
    """Stop runaway generation; never treat this stop as a successful EOS."""
    def __init__(self, prompt_length, seconds=90, clock=time.monotonic):
        self.prompt_length = prompt_length
        self.seconds = seconds
        self.clock = clock
        self.started = clock()
        self.reason = None

    def __call__(self, input_ids, scores=None, **kwargs):
        count = input_ids.shape[-1] - self.prompt_length
        if self.clock() - self.started >= self.seconds:
            self.reason = 'time_limit'
            return True
        if count >= 128 and count % 16 == 0:
            tail = input_ids[0, -128:].tolist()
            for size in (8, 16, 32):
                block = tail[-size:]
                if all(tail[-size * (i + 1): -size * i or None] == block for i in range(4)):
                    self.reason = 'repetition'
                    return True
        return False


def _profile(image, vertical):
    preview = ImageOps.grayscale(image)
    preview.thumbnail((1600, 1600))
    binary = preview.point([255 if value < 160 else 0 for value in range(256)])
    projection = binary.resize((preview.width, 1) if vertical else (1, preview.height), Image.Resampling.BOX)
    return [value / 255 for value in getattr(projection, 'get_flattened_data', projection.getdata)()]


def _runs(mask):
    start = None
    for i, active in enumerate(list(mask) + [False]):
        if active and start is None:
            start = i
        elif not active and start is not None:
            yield start, i
            start = None


def _line_profile(image, vertical):
    """Longest continuous ink run, avoiding cuts through dense character columns."""
    preview = ImageOps.grayscale(image)
    preview.thumbnail((1000, 1000))
    binary = preview.point([255 if value < 185 else 0 for value in range(256)])
    binary = binary.filter(ImageFilter.MaxFilter(3))
    if vertical:
        binary = binary.transpose(Image.Transpose.TRANSPOSE)
    values = list(getattr(binary, 'get_flattened_data', binary.getdata)())
    result = []
    for offset in range(0, len(values), binary.width):
        longest = current = gap = 0
        for value in values[offset:offset + binary.width]:
            if value:
                current += gap + 1
                gap = 0
                longest = max(longest, current)
            else:
                gap += 1
                if gap > 2:
                    current = gap = 0
        result.append(longest / binary.width)
    return result


def plan_regions(image, reading_order='rtl_vertical', max_regions=24):
    """Partition the full page at ruling lines or clear gutters, retaining margins.

    Coordinates cover the entire page exactly once. This is a layout heuristic,
    not a learned text detector; crop coordinates are kept for human review.
    """
    vertical = reading_order == 'rtl_vertical'
    lines = _line_profile(image, vertical)
    extent = image.width if vertical else image.height
    cuts = [int((a + b) / 2 * extent / len(lines))
            for a, b in _runs([value >= .30 for value in lines])
            if b - a <= max(3, len(lines) * .04)]
    if len(cuts) < 3:
        profile = _profile(image, vertical)
        cuts = [int((a + b) / 2 * extent / len(profile))
                for a, b in _runs([value < .012 for value in profile])
                if b - a >= 3 and a > len(profile) * .04 and b < len(profile) * .96]
    minimum = max(24, extent // 50)
    filtered = [0]
    for cut in cuts:
        if cut - filtered[-1] >= minimum and extent - cut >= minimum:
            filtered.append(cut)
    filtered.append(extent)
    if len(filtered) - 1 > max_regions:
        filtered = [filtered[round(i * (len(filtered) - 1) / max_regions)]
                    for i in range(max_regions + 1)]
    boxes = [(a, 0, b, image.height) if vertical else (0, a, image.width, b)
             for a, b in zip(filtered, filtered[1:])]
    return list(reversed(boxes)) if vertical else boxes


def split_region(image, bbox, reading_order='rtl_vertical'):
    """Bisect at the least-ink cut near the center, with no overlapping pixels."""
    x0, y0, x1, y1 = bbox
    vertical = reading_order == 'rtl_vertical' and x1 - x0 >= 64
    extent = x1 - x0 if vertical else y1 - y0
    if extent < 64:
        return []
    with image.crop(bbox) as crop:
        profile = _profile(crop, vertical)
    lower, upper = int(len(profile) * .35), int(len(profile) * .65)
    if upper <= lower:
        return []
    index = min(range(lower, upper), key=lambda i: (profile[i], abs(i - len(profile) / 2)))
    cut = max(1, min(extent - 1, round(index / len(profile) * extent)))
    if vertical:
        return [(x0 + cut, y0, x1, y1), (x0, y0, x0 + cut, y1)]
    return [(x0, y0, x1, y0 + cut), (x0, y0 + cut, x1, y1)]
