import sys, time
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config
_cfg = Config(); _cfg.max_connection_pool_size = 20
_pool = ConnectionPool()
assert _pool.init([("127.0.0.1", 9669)], _cfg), "cannot connect to graphd"

def sess():
    s = _pool.get_session("root", "nebula")
    r = s.execute("USE tx"); assert r.is_succeeded(), r.error_msg()
    return s
def ok(s, q): return s.execute(q).is_succeeded()
def age(s, vid):
    r = s.execute('FETCH PROP ON person "%s" YIELD properties(vertex).age AS age' % vid)
    if not r.is_succeeded(): return "ERR"
    return r.row_values(0)[0].as_int() if r.row_size() else None
def ins(s, vid, a): return ok(s, 'INSERT VERTEX person(name, age) VALUES "%s":("%s", %d)' % (vid, vid, a))
def nrows(s, q):
    r = s.execute(q); return r.row_size() if r.is_succeeded() else "ERR"

def run(checks, title):
    res = []
    for g, cid, desc, fn in checks:
        try: p = bool(fn())
        except Exception as e: p = False; desc += "  (exception: %s)" % str(e)[:80]
        res.append((g, p)); print("[%s] %s %s" % ("PASS" if p else "FAIL", cid, desc)); sys.stdout.flush()
    n = sum(1 for _, p in res if p)
    groups = {}
    for g, p in res: groups.setdefault(g, [0, 0]); groups[g][1] += 1; groups[g][0] += p
    print(); [print("  group %-22s %d/%d" % (g, a, b)) for g, (a, b) in groups.items()]
    print("RESULT %s: %d passed, %d failed (of %d)" % (title, n, len(res) - n, len(res)))
    print("ALL PASS" if n == len(res) else "NOT DONE")