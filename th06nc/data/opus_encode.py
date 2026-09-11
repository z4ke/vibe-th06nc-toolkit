"""
Converts a standard Ogg Opus file back into the game's stripped custom
format (40-byte header + repeating [4-byte BE length][4 zero bytes][packet]).

Preserves the original Opus packets bit-exact (no decode/re-encode), by
demuxing the Ogg container directly.

Header layout (confirmed via disassembly of the game's actual header-parse
function, sub_14007EA60):
  bytes  0- 3: magic constant, MUST be exactly 0x80000001 (checked, rejects otherwise)
  bytes  4- 8: unreferenced by the parser -- unknown, copied from template
  byte      9: channel count (1 or 2)                    -> checked, must be 1 or 2
  bytes 10-11: a per-encode "delay" value; meaning not fully pinned down -- copied from template
  bytes 12-15: sample rate, MUST be exactly 48000 (checked, rejects otherwise)
  bytes 16-19: header_size - 8, i.e. MUST be exactly 32 for this 40-byte-header
               format (a fixed constant, not per-file data -- this is NOT
               pre-skip, despite an earlier guess; the game's decode path
               never appears to apply any pre-skip trim to the output)
  bytes 20-31: unreferenced by the parser -- unknown, copied from template
  bytes 32-35: second magic constant, MUST be exactly 0x80000004 (checked, rejects otherwise)
  bytes 36-39: total sample count (confirmed exact match to the runtime struct's +0x58 field)

So bytes 4-8 and 20-31 are the only genuinely-unknown parts left, and this
tool still copies those from a template file for safety. Every other byte
is now set correctly and precisely rather than guessed.

Usage:
    python3 opus_encode.py input.ogg output.opus --template original_extracted_track.opus
    python3 opus_encode.py input.ogg output.opus --default
"""
import sys, struct, argparse

# A real, fully valid 40-byte header captured from th06_02. Used only as a
# fallback if no --template is given -- only its unknown regions (bytes
# 4-8, 20-31) actually get used; every other byte is overwritten below.
DEFAULT_HEADER = bytes.fromhex(
    '01000080180000000002e80180bb0000200000000000000000000000780000000400008048ac2400'
)

def parse_ogg_packets(data: bytes):
    """Returns (opus_head_bytes, list_of_packet_bytes) from a raw Ogg file."""
    pos = 0
    packets = []
    pending = bytearray()
    opus_head = None
    n = len(data)
    while pos < n:
        if data[pos:pos+4] != b'OggS':
            raise ValueError(f'lost Ogg page sync at offset {pos}')
        nseg = data[pos+26]
        seg_table = data[pos+27:pos+27+nseg]
        body_pos = pos + 27 + nseg
        for seg_len in seg_table:
            pending += data[body_pos:body_pos+seg_len]
            body_pos += seg_len
            if seg_len < 255:
                pkt = bytes(pending)
                pending = bytearray()
                if opus_head is None and pkt[:8] == b'OpusHead':
                    opus_head = pkt
                elif pkt[:8] == b'OpusTags':
                    pass
                else:
                    packets.append(pkt)
        pos = body_pos
    return opus_head, packets

def parse_opus_head(head: bytes):
    channels = head[9]
    sample_rate = struct.unpack_from('<I', head, 12)[0]
    return channels, sample_rate

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
    else:
        frame_count = packet[1] & 0x3F if len(packet) > 1 else 1
    return samples_per_frame * frame_count

def build_raw_opus(ogg_path: str, out_path: str, header_template: bytes):
    data = open(ogg_path, 'rb').read()
    opus_head, packets = parse_ogg_packets(data)
    if opus_head is None:
        raise ValueError('no OpusHead packet found -- is this really an Ogg Opus file?')
    channels, sample_rate = parse_opus_head(opus_head)
    if channels not in (1, 2):
        raise ValueError(f'unsupported channel count {channels} -- game only accepts mono/stereo')
    if sample_rate != 48000:
        print(f'warning: input sample rate is {sample_rate}, but the game requires 48000 '
              f'in the header -- writing 48000 regardless (make sure your encoder actually '
              f'ran at 48kHz, or the audio will sound wrong)')

    total_samples = sum(opus_packet_samples(p) for p in packets)

    header = bytearray(header_template)
    assert len(header) == 40, 'header template must be exactly 40 bytes'
    struct.pack_into('<I', header, 0, 0x80000001)   # confirmed fixed magic
    header[9] = channels                             # confirmed field
    struct.pack_into('<I', header, 12, 48000)         # confirmed fixed field
    struct.pack_into('<I', header, 16, 32)            # confirmed: header_size(40) - 8
    struct.pack_into('<I', header, 32, 0x80000004)    # confirmed fixed magic
    struct.pack_into('<I', header, 36, total_samples) # confirmed field

    out = bytearray(header)
    for p in packets:
        out += struct.pack('>I', len(p))
        out += b'\x00\x00\x00\x00'   # 4 unidentified bytes -- zero-filled
        out += p

    with open(out_path, 'wb') as f:
        f.write(out)
    return dict(channels=channels, sample_rate=sample_rate,
                n_packets=len(packets), total_samples=total_samples)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('input_ogg')
    ap.add_argument('output_opus')
    ap.add_argument('--template', help='path to a real extracted original raw-format file, to fill in the still-unknown header bytes (4-8, 20-31)')
    ap.add_argument('--default', action='store_true', help='use the built-in default header instead of a template')
    args = ap.parse_args()

    if args.template:
        template_header = open(args.template, 'rb').read()[:40]
    elif args.default:
        template_header = DEFAULT_HEADER
    else:
        print('error: pass either --template <file> or --default')
        sys.exit(1)

    info = build_raw_opus(args.input_ogg, args.output_opus, template_header)
    print(info)
