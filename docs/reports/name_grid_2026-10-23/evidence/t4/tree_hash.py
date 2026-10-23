import hashlib, json, os, sys
root, out = sys.argv[1], sys.argv[2]; res = {}
for d, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(d, f)
        if os.path.islink(p): res[os.path.relpath(p, root)] = 'link:' + os.readlink(p); continue
        res[os.path.relpath(p, root)] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
json.dump(res, open(out, 'w'), indent=0, sort_keys=True); print(len(res), hashlib.sha256(json.dumps(res, sort_keys=True).encode()).hexdigest())
