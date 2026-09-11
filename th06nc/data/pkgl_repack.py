"""
PKGL archive packer — Windows/cross-platform version (uses `zstandard` pip
package instead of ctypes+libzstd). For modding Touhou 6 New Classic / the
2026 patch's PKGL archives.

NOTE on the per-entry checksum/key field: see pkgl_extract_win.py's docstring
and the accompanying writeup — nothing observed in the game's load path
re-validates this field against the file data, it's only used as the
decrypt key, so this packer is free to assign it deterministically
(crc32 of the stored bytes). Flag if you run into load issues in-game.

Install once:
    pip install zstandard

Usage:
    python pkgl_pack_win.py <input_dir> <output.dat> <archive_key_name>
    (archive_key_name = the archive's own on-disk filename, minus path/extension,
     e.g. "th06CM" for th06CM.dat)

Workflow for modding:
    1. python pkgl_extract_win.py th06CM.dat th06CM ./th06CM_extracted
    2. edit/replace files inside ./th06CM_extracted
    3. python pkgl_pack_win.py ./th06CM_extracted th06CM.dat th06CM
       (back up the original first!)
"""
import sys, os, zlib, struct
import zstandard

MASK64 = (1 << 64) - 1

def _splitmix64_round(z: int) -> int:
    z &= MASK64
    z ^= (z >> 30); z = (z * 0xBF58476D1CE4E5B9) & MASK64
    z ^= (z >> 27); z = (z * 0x94D049BB133111EB) & MASK64
    z ^= (z >> 31)
    return z & MASK64

def pkgl_keystream(key32: int) -> bytes:
    key32 &= 0xFFFFFFFF
    rax = (key32 << 32) & MASK64
    seed0 = (((key32 * 0x9E3779B1) & MASK64) + 1) & MASK64
    seed0 ^= rax
    seed0 = (seed0 + 0x9E3779B97F4A7C15) & MASK64
    out1 = _splitmix64_round(seed0)
    state2 = (seed0 + 0x9E3779B97F4A7C15) & MASK64
    out2 = _splitmix64_round(state2)
    return out1.to_bytes(8, 'little') + out2.to_bytes(8, 'little')

def pkgl_xor(data: bytes, key32: int) -> bytes:
    ks = pkgl_keystream(key32)
    return bytes(b ^ ks[i % 16] for i, b in enumerate(data))

def pack_pkgl(input_dir: str, output_path: str, archive_key_name: str,
              compress_min_ratio: float = 0.95, level: int = 19):
    cctx = zstandard.ZstdCompressor(level=level)
    filenames = sorted(os.listdir(input_dir))
    entries = []
    for name in filenames:
        path = os.path.join(input_dir, name)
        if not os.path.isfile(path):
            continue
        plain = open(path, 'rb').read()
        compressed = cctx.compress(plain)
        if len(compressed) < len(plain) * compress_min_ratio:
            flag, stored = 1, compressed
        else:
            flag, stored = 0, plain
        key = zlib.crc32(stored) & 0xFFFFFFFF
        enc = pkgl_xor(stored, key)
        entries.append(dict(flag=flag, key=key, decsize=len(plain),
                             storedsize=len(stored), data=enc, name=name))

    table_key = zlib.crc32(archive_key_name.encode('ascii')) & 0xFFFFFFFF

    def build_table(offsets):
        t = bytearray()
        for e, off in zip(entries, offsets):
            t += struct.pack('<HIQQQH', e['flag'], e['key'], e['decsize'],
                              e['storedsize'], off, len(e['name'].encode('ascii')))
            t += e['name'].encode('ascii')
        return t

    dummy_table = build_table([0] * len(entries))
    header_size = 8
    data_start = header_size + len(dummy_table)
    if data_start % 16:
        data_start += 16 - (data_start % 16)

    pos = data_start
    offsets = []
    for e in entries:
        offsets.append(pos)
        pos += e['storedsize']
        if pos % 16:
            pos += 16 - (pos % 16)

    table_plain = build_table(offsets)
    enc_table = pkgl_xor(bytes(table_plain), table_key)

    out = bytearray()
    out += b'PKGL' + struct.pack('<I', len(enc_table))
    out += enc_table
    out += bytes(data_start - len(out))

    for e, off in zip(entries, offsets):
        assert len(out) == off, f"offset drift on {e['name']}: {len(out)} != {off}"
        out += e['data']
        out += bytes(-len(out) % 16)

    with open(output_path, 'wb') as f:
        f.write(out)
    return len(entries)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('usage: pkgl_pack_win.py <input_dir> <output.dat> <archive_key_name>')
        sys.exit(1)
    n = pack_pkgl(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f'packed {n} files into {sys.argv[2]}')
