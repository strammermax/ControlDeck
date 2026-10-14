"""Shared validation for uploaded application icons."""
import base64
import binascii
import struct
import zlib

def validate_icon(value):
    """Accept small, structurally valid PNG images only; never remote or active content."""
    if not isinstance(value, str) or not value.startswith("data:image/png;base64,") or len(value) > 44000:
        raise ValueError("Gebruik een PNG-icoon van maximaal 32 KiB.")
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        if len(raw) > 32768 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError()
        offset, chunks, compressed = 8, [], b""
        while offset < len(raw):
            length = struct.unpack(">I", raw[offset:offset + 4])[0]
            kind = raw[offset + 4:offset + 8]
            content = raw[offset + 8:offset + 8 + length]
            checksum = struct.unpack(">I", raw[offset + 8 + length:offset + 12 + length])[0]
            if zlib.crc32(kind + content) != checksum:
                raise ValueError()
            chunks.append(kind)
            if kind == b"IHDR":
                width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", content)
                if not (1 <= width <= 256 and 1 <= height <= 256) or depth != 8 or color not in (2, 6) or (compression, filtering, interlace) != (0, 0, 0):
                    raise ValueError()
            elif kind == b"IDAT":
                compressed += content
            offset += length + 12
        if chunks[0] != b"IHDR" or chunks.count(b"IHDR") != 1 or chunks[-1] != b"IEND" or length != 0 or offset != len(raw):
            raise ValueError()
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(compressed, 262401)
        if not decoder.eof or decoder.unused_data or len(pixels) != height * (1 + width * (4 if color == 6 else 3)):
            raise ValueError()
    except (ValueError, IndexError, struct.error, binascii.Error, zlib.error):
        raise ValueError("Ongeldig PNG-icoon. Upload de afbeelding opnieuw.") from None
    return value
