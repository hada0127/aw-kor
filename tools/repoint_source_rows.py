"""Resolve every live ROM fragment belonging to a repointed source row."""


def fragments(message, key):
    """Return bounded spans, accepting legacy manifests with one span per row."""
    first = message.get('line_spans', {}).get(key)
    if first is None:
        return None
    parts = message.get('source_line_fragments', {}).get(key, [first])
    size = int(message['new_len'])
    if (not parts or parts[0] != first or any(
            not isinstance(pair, (list, tuple)) or len(pair) != 2
            or type(pair[0]) is not int or type(pair[1]) is not int
            or pair[0] < 0 or pair[1] <= 0 or pair[0] + pair[1] > size
            for pair in parts)):
        raise ValueError(f'invalid repoint source fragments: {message["msg"]} {key}')
    return parts


def row_bytes(rom, message, key):
    """Join split display lines at their authored fullwidth-space boundary."""
    parts = fragments(message, key)
    if parts is None:
        return None
    target = int(message['new_addr'], 16)
    if target < 0 or target + int(message['new_len']) > len(rom):
        raise ValueError(f'repoint target outside ROM: {message["msg"]}')
    joins=message.get('source_fragment_joiners', {}).get(key, ['8140']*(len(parts)-1))
    if (not isinstance(joins,list) or len(joins)!=len(parts)-1
            or any(not isinstance(j,str) or j not in ('','8140') for j in joins)):
        raise ValueError(f'invalid repoint fragment separators: {message["msg"]} {key}')
    result=bytearray()
    for i,(off,length) in enumerate(parts):
        if i:result.extend(bytes.fromhex(joins[i-1]))
        result.extend(rom[target+off:target+off+length])
    return bytes(result)
