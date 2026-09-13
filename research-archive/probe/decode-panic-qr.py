#!/usr/bin/env python3
"""Analysis-only QR decoding of local webcam photos. Never follow decoded URLs."""
import sys
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import zxingcpp

for path in sys.argv[1:]:
    source = Image.open(path)
    crops = [source, source.crop((710, 130, 1230, 650))]
    for crop in crops:
        gray = ImageOps.grayscale(crop)
        candidates = [crop, gray, ImageOps.autocontrast(gray)]
        for size in (1, 2, 3):
            for candidate in candidates:
                if size != 1:
                    candidate = candidate.resize((candidate.width*size, candidate.height*size))
                for result in zxingcpp.read_barcodes(candidate, formats=zxingcpp.BarcodeFormat.QRCode,
                                                    try_rotate=True, try_downscale=True, try_invert=True):
                    if result.valid:
                        print("PANIC_QR_BEGIN", path)
                        print(result.text)
                        print("PANIC_QR_END")
                        raise SystemExit(0)
    print("NO_READABLE_QR", path)
raise SystemExit(1)
