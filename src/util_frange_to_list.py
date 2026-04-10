#!/usr/bin/env python3
'''
Given a frame range, return a list of frames in that range.
Some examples of frame ranges are:
- "1" -> [1]
- "1-5" -> [1, 2, 3, 4, 5]
- "1,3,5" -> [1, 3, 5]
- "1-3,5" -> [1, 2, 3, 5]
- "1-3,5-7" -> [1, 2, 3, 5, 6, 7]
'''

import re


def frange_to_list(frange: str) -> list[int]:
    if not re.fullmatch(r'[\d,\-]+', frange):
        raise ValueError(f"Invalid frame range (only digits, '-', and ',' are allowed): {frange!r}")

    frames: list[int] = []
    for token in frange.split(','):
        token = token.strip()
        if '-' in token:
            parts = token.split('-')
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(f"Invalid range token: {token!r}")
            start, end = int(parts[0]), int(parts[1])
            if start > end:
                raise ValueError(f"Range start must be <= end: {token!r}")
            frames.extend(range(start, end + 1))
        else:
            frames.append(int(token))
    return frames
