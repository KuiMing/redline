#!/usr/bin/env python3
"""由 static/war_title.png 產生 1024×1024 的 macOS 圓角方形圖示（不修改來源圖）。

    generate_icon.py <來源 PNG> <輸出 PNG>

只取「逆」字的紅色筆畫，不要灰色陰影與深色底，縮到 16px 時才看得清楚。內容區與留白比例
採 macOS 圖示格線（1024 畫布上 824 內容區），四周保持透明。需要打包環境的 pyobjc。
"""

from __future__ import annotations

import sys

import AppKit
import Foundation

SIZE = 1024
CONTENT = 824
MARGIN = (SIZE - CONTENT) / 2
CORNER_RADIUS = 185
# 「逆」字紅色筆畫在來源圖的範圍（左上原點）；右界切在下一個字「統」之前。
GLYPH_BOX = (380, 420, 790, 815)
GLYPH_HEIGHT = 600


def rgba_rep(width: int, height: int):
    return AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, width, height, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, width * 4, 32
    )


def extract_glyph(source_path: str):
    """把來源圖畫進已知格式的 bitmap，再只保留紅色像素。"""
    source = AppKit.NSImage.alloc().initWithContentsOfFile_(source_path)
    if source is None:
        raise SystemExit(f"cannot read {source_path}")
    left, top, right, bottom = GLYPH_BOX
    width, height = right - left, bottom - top
    source_height = source.representations()[0].pixelsHigh()
    source_width = source.representations()[0].pixelsWide()
    source.setSize_((source_width, source_height))

    rep = rgba_rep(width, height)
    context = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(context)
    source.drawInRect_fromRect_operation_fraction_(
        Foundation.NSMakeRect(0, 0, width, height),
        Foundation.NSMakeRect(left, source_height - bottom, width, height),
        AppKit.NSCompositingOperationCopy,
        1.0,
    )
    AppKit.NSGraphicsContext.restoreGraphicsState()

    pixels = rep.bitmapData()
    for offset in range(0, width * height * 4, 4):
        red, green = pixels[offset], pixels[offset + 1]
        # 紅色筆畫 R 明顯高於 G；灰色陰影與深色底 R≈G。
        strength = max(0, min(255, (red - green - 40) * 4))
        if strength == 0:
            pixels[offset:offset + 4] = b"\0\0\0\0"
        else:
            # NSBitmapImageRep 預設為 premultiplied alpha。
            pixels[offset] = 232 * strength // 255
            pixels[offset + 1] = 44 * strength // 255
            pixels[offset + 2] = 44 * strength // 255
            pixels[offset + 3] = strength
    image = AppKit.NSImage.alloc().initWithSize_((width, height))
    image.addRepresentation_(rep)
    return image, width, height


def compose(glyph, glyph_width: int, glyph_height: int):
    rep = rgba_rep(SIZE, SIZE)
    context = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(context)
    context.setImageInterpolation_(AppKit.NSImageInterpolationHigh)

    tile = Foundation.NSMakeRect(MARGIN, MARGIN + 10, CONTENT, CONTENT)
    path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(tile, CORNER_RADIUS, CORNER_RADIUS)

    # macOS 圖示慣用的柔和投影，落在透明留白內。
    AppKit.NSGraphicsContext.saveGraphicsState()
    shadow = AppKit.NSShadow.alloc().init()
    shadow.setShadowColor_(AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.35))
    shadow.setShadowOffset_((0, -10))
    shadow.setShadowBlurRadius_(24)
    shadow.set()
    AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.05, 0.06, 0.08, 1.0).setFill()
    path.fill()
    AppKit.NSGraphicsContext.restoreGraphicsState()

    top = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.17, 0.21, 1.0)
    bottom = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.04, 0.05, 0.07, 1.0)
    AppKit.NSGradient.alloc().initWithStartingColor_endingColor_(top, bottom).drawInBezierPath_angle_(path, 270)

    scale = GLYPH_HEIGHT / glyph_height
    width, height = glyph_width * scale, glyph_height * scale
    target = Foundation.NSMakeRect((SIZE - width) / 2, MARGIN + 10 + (CONTENT - height) / 2, width, height)
    glyph.drawInRect_fromRect_operation_fraction_(target, Foundation.NSZeroRect, AppKit.NSCompositingOperationSourceOver, 1.0)

    AppKit.NSGraphicsContext.restoreGraphicsState()
    return rep


def verify(rep) -> None:
    pixels = rep.bitmapData()
    alpha = lambda x, y: pixels[(y * SIZE + x) * 4 + 3]  # noqa: E731
    if alpha(0, 0) != 0 or alpha(SIZE - 1, 0) != 0 or alpha(0, SIZE - 1) != 0 or alpha(SIZE - 1, SIZE - 1) != 0:
        raise SystemExit("icon corners must be transparent")
    if alpha(SIZE // 2, SIZE // 2) != 255:
        raise SystemExit("icon tile must be opaque")


def main() -> int:
    source, output = sys.argv[1:3]
    glyph, width, height = extract_glyph(source)
    rep = compose(glyph, width, height)
    verify(rep)
    data = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
    if not data.writeToFile_atomically_(output, True):
        raise SystemExit(f"cannot write {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
