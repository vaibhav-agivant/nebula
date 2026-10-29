import sys, time, subprocess
sys.path.insert(0, "/work")
from txnlib import *
S = sess()
def ddl(q):
    for _ in range(40):
        if ok(S, q): return True
        time.sleep(2)
    return False
ddl("CREATE EDGE IF NOT EXISTS road(cost double)")
for _ in range(40):
    if ok(S, "DESCRIBE EDGE road"): break
    time.sleep(2)
time.sleep(4)
for s,d,w in [("a","f",50.0),("a","e",10.0),("e","f",10.0),("a","b",1.0),("b","c",1.0),("c","f",1.0),("t1","t2",1.0),("t2","t4",1.0)]:
    ddl('INSERT VERTEX person(name, age) VALUES "%s":("%s",1), "%s":("%s",1)' % (s,s,d,d)); ddl('INSERT EDGE road(cost) VALUES "%s"->"%s":(%r)' % (s,d,w))
time.sleep(2)
C = ["/work/nebula-console", "-addr", "127.0.0.1", "-port", "9669", "-u", "root", "-p", "nebula", "-e"]
for q in ['FIND WEIGHTED SHORTEST PATH FROM "a", "t1" TO "f", "t4" OVER road WEIGHT BY cost YIELD path AS p, cost AS c',
          'GO FROM "a" OVER road YIELD dst(edge) AS id | FIND WEIGHTED SHORTEST PATH FROM $-.id TO "f" OVER road WEIGHT BY cost YIELD path AS p, cost AS c']:
    out = subprocess.run(C + ["USE tx; " + q], capture_output=True, text=True).stdout
    print("QUERY>>", q); print("\n".join(l for l in out.splitlines() if l.strip() and not l.startswith(("Bye","(root","Welcome")) and "CST" not in l))