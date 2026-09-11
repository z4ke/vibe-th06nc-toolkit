"""
PKGL archive extractor — Touhou 6 (EoSD) "New Classic" remake / 2026 patch format.
Windows/cross-platform version (uses the `zstandard` pip package instead of ctypes).

Install once:
    pip install zstandard

Usage:
    python pkgl_extract_win.py CM.DAT th06CM ./output_dir
    (second arg = the archive's own on-disk filename, minus path and extension)
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

def zstd_decompress(data: bytes, out_size: int) -> bytes:
    dctx = zstandard.ZstdDecompressor()
    return dctx.decompress(data, max_output_size=out_size)

def extract_pkgl(path: str, archive_key_name: str, outdir: str):
    data = open(path, 'rb').read()
    assert data[:4] == b'PKGL', 'not a PKGL archive'
    table_size = struct.unpack_from('<I', data, 4)[0]
    table_key = zlib.crc32(archive_key_name.encode('ascii')) & 0xFFFFFFFF
    table = pkgl_xor(data[8:8+table_size], table_key)

    entries, pos = [], 0
    while pos + 32 <= len(table):
        f0, f1, f2, f3, f4, namelen = struct.unpack_from('<HIQQQH', table, pos)
        name = table[pos+32:pos+32+namelen]
        if b'\x00' in name or namelen == 0 or namelen > 260:
            break
        entries.append(dict(compressed=bool(f0), key=f1, decsize=f2, size=f3,
                             offset=f4, name=name.decode('shift_jis', 'replace')))
        pos += 32 + namelen

    os.makedirs(outdir, exist_ok=True)
    for e in entries:
        raw = data[e['offset']: e['offset'] + e['size']]
        dec = pkgl_xor(raw, e['key'])
        out = zstd_decompress(dec, e['decsize']) if e['compressed'] else dec
        ok = len(out) == e['decsize']
        with open(os.path.join(outdir, e['name']), 'wb') as f:
            f.write(out)
        print(f"{e['name']:20s} {'OK' if ok else 'SIZE MISMATCH'} ({len(out)} bytes)")
    return entries

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('usage: pkgl_extract_win.py <archive.dat> <key_name_no_ext> <outdir>')
        print("  key_name_no_ext = the archive's own on-disk filename, minus path and extension")
        print('  e.g. for th06CM.dat, key_name_no_ext = th06CM')
        sys.exit(1)
    extract_pkgl(sys.argv[1], sys.argv[2], sys.argv[3])
