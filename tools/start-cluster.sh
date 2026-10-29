#!/bin/bash
# usage: start-cluster.sh "<extra graphd flags>"   (runs inside the container; repo mounted at /work/nebula)
EXTRA="$1"; N=/work/nebula; B=$N/build/bin; R=/work/run; C="/work/nebula-console -addr 127.0.0.1 -port 9669 -u root -p nebula"
pkill -f 'nebula-(metad|storaged|graphd)' 2>/dev/null; rm -rf $R; mkdir -p $R/{meta,storage,graph}/{data,logs,pids}
cp $N/conf/nebula-metad.conf.default $R/meta.conf; cp $N/conf/nebula-storaged.conf.default $R/storage.conf; cp $N/conf/nebula-graphd.conf.default $R/graph.conf
for c in meta storage graph; do sed -i 's#^--local_ip=.*#--local_ip=127.0.0.1#;s#^--meta_server_addrs=.*#--meta_server_addrs=127.0.0.1:9559#' $R/$c.conf; done
sed -i "s#^--pid_file=.*#--pid_file=$R/meta/pids/m.pid#;s#^--log_dir=.*#--log_dir=$R/meta/logs#;s#^--data_path=.*#--data_path=$R/meta/data#" $R/meta.conf
sed -i "s#^--pid_file=.*#--pid_file=$R/storage/pids/s.pid#;s#^--log_dir=.*#--log_dir=$R/storage/logs#;s#^--data_path=.*#--data_path=$R/storage/data#" $R/storage.conf
sed -i "s#^--pid_file=.*#--pid_file=$R/graph/pids/g.pid#;s#^--log_dir=.*#--log_dir=$R/graph/logs#" $R/graph.conf
cd $R; mkdir -p share; ln -sfn $N/resources share/resources
wait_port(){ for i in $(seq 1 $2); do (echo > /dev/tcp/127.0.0.1/$1) 2>/dev/null && return 0; sleep 1; done; return 1; }
echo "[setup] starting metad/storaged"; $B/nebula-metad --flagfile $R/meta.conf --daemonize=true; wait_port 9559 30 || { echo "[setup] metad failed"; exit 1; }
$B/nebula-storaged --flagfile $R/storage.conf --daemonize=true; sleep 2
start_graphd(){ $B/nebula-graphd --flagfile $R/graph.conf --daemonize=true; wait_port 9669 40; }
if [ -n "$EXTRA" ]; then for fl in $EXTRA; do echo "$fl" >> $R/graph.conf; done; fi
if ! start_graphd; then
  if [ -n "$EXTRA" ]; then echo "[setup] graphd did not start with: $EXTRA (flags not implemented?) -> retrying without them"
    pkill -f nebula-graphd; sleep 1; sed -i '/^--txn_/d' $R/graph.conf; touch $R/NOFLAGS; start_graphd || { echo "[setup] graphd failed to start"; tail -5 $R/graph/logs/*.ERROR 2>/dev/null; exit 1; }
  else echo "[setup] graphd failed to start"; tail -5 $R/graph/logs/*.ERROR 2>/dev/null; exit 1; fi
fi
echo "[setup] graphd up; registering storage host"
$C -e 'ADD HOSTS "127.0.0.1":9779' >/dev/null 2>&1
for i in $(seq 1 60); do $C -e 'SHOW HOSTS' 2>&1 | grep -q ONLINE && break; sleep 2; done
$C -e 'CREATE SPACE IF NOT EXISTS tx(vid_type=FIXED_STRING(20), partition_num=3, replica_factor=1)' >/dev/null 2>&1
for i in $(seq 1 60); do $C -e 'USE tx; CREATE TAG IF NOT EXISTS person(name string, age int); CREATE EDGE IF NOT EXISTS knows(w int)' 2>&1 | grep -q 'Execution succeeded' && break; sleep 2; done
for i in $(seq 1 60); do $C -e 'USE tx; DESCRIBE EDGE knows' 2>&1 | grep -q 'w' && break; sleep 2; done
for i in $(seq 1 60); do $C -e 'USE tx; INSERT VERTEX person(name, age) VALUES "probe":("p", 0)' 2>&1 | grep -q 'Execution succeeded' && break; sleep 2; done
$C -e 'USE tx; DELETE VERTEX "probe"' >/dev/null 2>&1
sleep 2; echo "[setup] ready (space tx, tag person(name,age), edge knows(w))"