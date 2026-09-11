"""
Converts the game's stripped-down raw Opus stream (40-byte custom header +
repeating [4-byte BE length][4 unused bytes][opus packet]) into a standard
Ogg Opus (.ogg/.opus) file playable by any normal player.

Usage:
    python3 opus_decode.py input.opus output.ogg
"""
import sys, struct, zlib

# ---------- Ogg CRC-32 (non-reflected, poly 0x04c11db7, init 0, no final xor) ----------
def _make_ogg_crc_table():
    table = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04c11db7) & 0xFFFFFFFF if (crc & 0x80000000) else (crc << 1) & 0xFFFFFFFF
        table.append(crc)
    return table

_OGG_CRC_TABLE = _make_ogg_crc_table()

def ogg_crc32(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = ((crc << 8) ^ _OGG_CRC_TABLE[((crc >> 24) ^ b) & 0xFF]) & 0xFFFFFFFF
    return crc

# ---------- Opus TOC parsing (for accurate granule-position accounting) ----------
def opus_packet_samples(packet: bytes, fs=48000) -> int:
    if not packet:
        return 0
    toc = packet[0]
    config = toc >> 3
    if config < 12:
        dur_ms = [10, 20, 40, 60][config % 4]
    elif config < 16:
        dur_ms = [10, 20][config % 2]
    else:
        dur_ms = [2.5, 5, 10, 20][(config - 16) % 4]
    samples_per_frame = int(dur_ms * fs / 1000)
    code = toc & 3
    if code == 0:
        frame_count = 1
    elif code in (1, 2):
        frame_count = 2
    else:  # code 3: arbitrary count in next byte
        frame_count = packet[1] & 0x3F if len(packet) > 1 else 1
    return samples_per_frame * frame_count

# ---------- Ogg page writer ----------
def make_ogg_page(serial, seq, granule, packets, header_type=0):
    """packets: list of bytes objects to pack into ONE page (segment table max 255 entries)."""
    seg_data = b''.join(packets)
    lacing = []
    for p in packets:
        remaining = len(p)
        while remaining >= 255:
            lacing.append(255)
            remaining -= 255
        lacing.append(remaining)
    assert len(lacing) <= 255, "too many segments for one page"
    header = b'OggS'
    header += bytes([0])                      # version
    header += bytes([header_type])
    header += struct.pack('<q', granule)
    header += struct.pack('<I', serial)
    header += struct.pack('<I', seq)
    header += struct.pack('<I', 0)             # checksum placeholder
    header += bytes([len(lacing)])
    header += bytes(lacing)
    page = header + seg_data
    crc = ogg_crc32(page)
    page = page[:22] + struct.pack('<I', crc) + page[26:]
    return page

def build_opus_head(channels, pre_skip, input_sample_rate, output_gain=0, mapping_family=0):
    return (b'OpusHead' + bytes([1, channels]) +
            struct.pack('<H', pre_skip) +
            struct.pack('<I', input_sample_rate) +
            struct.pack('<h', output_gain) +
            bytes([mapping_family]))

def build_opus_tags(vendor=b'github.com/z4ke/vibe-th06nc-toolkit'):
    return b'OpusTags' + struct.pack('<I', len(vendor)) + vendor + struct.pack('<I', 0)

# ---------- Raw-format parser ----------
def parse_raw_packets(data: bytes, header_size: int):
    pos = header_size
    packets = []
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos+4], 'big')
        if length == 0 or pos + 8 + length > len(data):
            break
        packets.append(data[pos+8:pos+8+length])
        pos += 8 + length
    return packets

def convert(in_path, out_path, header_size=40, channels=None, pre_skip=32, sample_rate=48000, serial=0x1234ABCD):
    data = open(in_path, 'rb').read()
    if channels is None:
        # byte 9 of the header is the confirmed channel-count field (game
        # requires it to be 1 or 2) -- read it instead of assuming stereo,
        # or mono tracks would come out as garbled/wrong-channel audio.
        channels = data[9]
        if channels not in (1, 2):
            raise ValueError(f"header byte 9 = {channels}, expected 1 or 2 -- "
                              f"wrong header_size, or not this file format?")
    packets = parse_raw_packets(data, header_size)
    if not packets:
        raise ValueError("no valid packets parsed - wrong header_size?")

    out = bytearray()
    out += make_ogg_page(serial, 0, 0, [build_opus_head(channels, pre_skip, sample_rate)], header_type=0x02)
    out += make_ogg_page(serial, 1, 0, [build_opus_tags()], header_type=0x00)

    granule = 0
    for i, p in enumerate(packets):
        granule += opus_packet_samples(p, 48000)
        is_last = (i == len(packets) - 1)
        out += make_ogg_page(serial, 2 + i, granule, [p], header_type=(0x04 if is_last else 0x00))

    with open(out_path, 'wb') as f:
        f.write(out)
    return len(packets), granule

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('usage: opus_decode.py input.opus output.ogg')
        sys.exit(1)
    n, granule = convert(sys.argv[1], sys.argv[2])
    print(f'wrote {n} packets, {granule} samples ({granule/48000:.2f}s)')
