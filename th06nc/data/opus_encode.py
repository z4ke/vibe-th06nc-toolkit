"""
Converts a standard Ogg Opus file back into the game's stripped custom
format (40-byte header + repeating [4-byte BE length][4 zero bytes][packet]).

Preserves the original Opus packets bit-exact (no decode/re-encode), by
demuxing the Ogg container directly.

IMPORTANT CAVEAT: only 2 of the header's 10 fields were confirmed via
disassembly (offset 12 = sample rate, offset 36 = total sample count).
The rest (offsets 0,4,8,16,20,24,28,32) were never traced back to the
game's actual header-parsing code -- we only had guesses for some (e.g.
offset 16 looked like it might be pre-skip, matched a plausible value, but
was never confirmed against the real parser). So this tool works in
TEMPLATE mode: give it a real extracted original file (same "family" if
possible, e.g. another music track from the same archive/game version) and
it copies that file's header verbatim, patching only the two confirmed
fields for your new audio. This is the safe default for modding -- swap
the music, don't reinvent unconfirmed struct fields.

If you don't have a template, pass --default to use a built-in header
captured from a real th06 track (th06_02) -- works, but any semantics we
don't understand (possible loop points, flags, etc.) will carry over from
that unrelated track rather than being correct for yours.

Usage:
    python3 ogg_to_raw_opus.py input.ogg output.opus --template original_extracted_track.opus
    python3 ogg_to_raw_opus.py input.ogg output.opus --default
"""
import sys, struct, argparse

# A real, fully valid 40-byte header captured from th06_02 (see reverse-engineering
# notes). Used only if the user has no better template.
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
        version = data[pos+4]
        header_type = data[pos+5]
        granule = struct.unpack_from('<q', data, pos+6)[0]
        serial = struct.unpack_from('<I', data, pos+14)[0]
        seq = struct.unpack_from('<I', data, pos+18)[0]
        crc = struct.unpack_from('<I', data, pos+22)[0]
        nseg = data[pos+26]
        seg_table = data[pos+27:pos+27+nseg]
        body_start = pos + 27 + nseg
        body_pos = body_start
        for seg_len in seg_table:
            pending += data[body_pos:body_pos+seg_len]
            body_pos += seg_len
            if seg_len < 255:
                # packet complete
                pkt = bytes(pending)
                pending = bytearray()
                if opus_head is None and pkt[:8] == b'OpusHead':
                    opus_head = pkt
                elif pkt[:8] == b'OpusTags':
                    pass  # skip, not an audio packet
                else:
                    packets.append(pkt)
        pos = body_pos
    return opus_head, packets

def parse_opus_head(head: bytes):
    channels = head[9]
    pre_skip = struct.unpack_from('<H', head, 10)[0]
    sample_rate = struct.unpack_from('<I', head, 12)[0]
    return channels, pre_skip, sample_rate

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
    channels, pre_skip, sample_rate = parse_opus_head(opus_head)

    total_samples = sum(opus_packet_samples(p) for p in packets)

    header = bytearray(header_template)
    assert len(header) == 40, 'header template must be exactly 40 bytes'
    struct.pack_into('<I', header, 12, sample_rate)   # confirmed field
    struct.pack_into('<I', header, 36, total_samples) # confirmed field

    out = bytearray(header)
    for p in packets:
        out += struct.pack('>I', len(p))
        out += b'\x00\x00\x00\x00'   # unused 4 bytes -- meaning not identified, zero-filled
        out += p

    with open(out_path, 'wb') as f:
        f.write(out)
    return dict(channels=channels, pre_skip=pre_skip, sample_rate=sample_rate,
                n_packets=len(packets), total_samples=total_samples)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('input_ogg')
    ap.add_argument('output_opus')
    ap.add_argument('--template', help='path to a real extracted original .opus/.anm-style raw file to copy the header from')
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
