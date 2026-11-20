#!/bin/bash
# Finish a partially downloaded file using parallel HTTP range requests (DBLP throttles per connection).
# Usage: scripts/fetch_parallel.sh URL FILE TOTAL_SIZE [JOBS]
set -euo pipefail
url=$1; file=$2; total=$3; jobs=${4:-16}
chunk=$((10*1024*1024))
have=$(stat -f %z "$file" 2>/dev/null || stat -c %s "$file")
parts="$file.parts"; mkdir -p "$parts"
n=0; : > "$parts/list"
for ((s=have; s<total; s+=chunk)); do
  e=$((s+chunk-1)); ((e>=total)) && e=$((total-1))
  printf "%05d %d %d\n" $n $s $e >> "$parts/list"; n=$((n+1))
done
fetch() {
  local id=$1 s=$2 e=$3 url=$4 parts=$5 want=$(( $3 - $2 + 1 ))
  for try in $(seq 1 60); do
    local got=$(stat -f %z "$parts/$id" 2>/dev/null || echo 0)
    ((got>=want)) && return 0
    curl -sS --speed-limit 2000 --speed-time 30 -r $((s+got))-$e "$url" >> "$parts/$id" 2>/dev/null || true
  done
  echo "chunk $id failed" >&2; return 1
}
export -f fetch
xargs -P "$jobs" -L 1 bash -c 'fetch "$0" "$1" "$2" "'"$url"'" "'"$parts"'"' < "$parts/list"
while read id s e; do cat "$parts/$id" >> "$file"; done < "$parts/list"
rm -rf "$parts"
ls -la "$file"
