def bytesto(size_bytes, to, bsize=1024):
    """convert bytes to megabytes, etc"""
    a = {"k": 1, "m": 2, "g": 3, "t": 4, "p": 5, "e": 6}
    r = float(size_bytes)
    for _ in range(a[to]):
        r = r / bsize
    return r
