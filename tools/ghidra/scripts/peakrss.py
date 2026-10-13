import os, subprocess, sys, time
out = sys.argv[1]; cmd = sys.argv[2:]
t0 = time.time(); p = subprocess.Popen(cmd); peak = 0
def tree(pid):
    kids = [pid]
    try:
        for t in os.listdir(f'/proc/{pid}/task'):
            with open(f'/proc/{pid}/task/{t}/children') as f:
                for c in f.read().split(): kids += tree(int(c))
    except OSError: pass
    return kids
while p.poll() is None:
    rss = 0
    for q in set(tree(p.pid)):
        try:
            for l in open(f'/proc/{q}/status'):
                if l.startswith('VmRSS:'): rss += int(l.split()[1])
        except OSError: pass
    peak = max(peak, rss); time.sleep(0.5)
with open(out, 'a') as f:
    f.write(f'{time.strftime("%F %T")} rc={p.returncode} wall={time.time()-t0:.1f}s peak_rss={peak/1024:.0f}MiB cmd={" ".join(cmd[-6:])}\n')
sys.exit(p.returncode)
