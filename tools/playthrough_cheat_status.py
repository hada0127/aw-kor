#!/usr/bin/env python3
"""Report whether a recorded checkpoint chain is normal play or cheat-tainted.

Cheat-tainted chains (any RAM write via the recorder's cheat/freeze commands, or any
ancestor/run/game save derived from one) must never be counted as normal-play
progress, victories or ending arrival. The flag is sticky and cannot be cleared.
"""
import argparse
import json
from pathlib import Path

from playthrough_capture import checkpoint_cheat_tainted, verify_parent


def status(checkpoint_path, *, verify=True):
    checkpoint_path = Path(checkpoint_path).resolve()
    checkpoint = json.loads(checkpoint_path.read_text())
    if verify:
        verify_parent(checkpoint_path, checkpoint)
    tainted = checkpoint_cheat_tainted(checkpoint)
    return {'checkpoint': str(checkpoint_path), 'cheat_tainted': tainted,
            'normal_play': not tainted, 'verified_chain': bool(verify)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--no-verify', action='store_true', help='Read the flag without re-verifying the frame chain')
    args = parser.parse_args()
    print(json.dumps(status(args.checkpoint, verify=not args.no_verify)))
