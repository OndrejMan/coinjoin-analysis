#!/bin/bash

PERFLOGFILE="/home/xsvenda/btc/memlog.csv"
OPERATIONFILE="/home/xsvenda/btc/operation.txt"
INTERVAL=1

# Remove previous log file
if [ -s "$PERFLOGFILE" ]; then
    rm $PERFLOGFILE
    echo removing $PERFLOGFILE
fi 

# Write CSV header if file is empty
if [ ! -s "$PERFLOGFILE" ]; then
    echo "timestamp,used_MB,free_MB,available_MB,cpu_percent,operation" >> "$PERFLOGFILE"
fi

# Function to read CPU counters
get_cpu_stats() {
    awk '/^cpu / {print $2, $3, $4, $5, $6, $7, $8, $9, $10}' /proc/stat
}

# Initial read
read -r user nice system idle iowait irq softirq steal guest guestnice < <(get_cpu_stats)

while true; do
    sleep "$INTERVAL"

    # Second read
    read -r user2 nice2 system2 idle2 iowait2 irq2 softirq2 steal2 guest2 guestnice2 < <(get_cpu_stats)

    # Compute deltas
    idle_delta=$((idle2 - idle))
    total_delta=$(( (user2-user) + (nice2-nice) + (system2-system) + (idle2-idle) \
                    + (iowait2-iowait) + (irq2-irq) + (softirq2-softirq) + (steal2-steal) ))

    # CPU utilization (%)
    cpu_usage=$(awk -v idle="$idle_delta" -v total="$total_delta" \
                'BEGIN { if (total==0) print 0; else print (100*(total-idle)/total) }')

    # Update baseline for next loop
    user=$user2; nice=$nice2; system=$system2; idle=$idle2
    iowait=$iowait2; irq=$irq2; softirq=$softirq2; steal=$steal2

    # Memory from free -m
    read _ total used free shared buff_cache available < <(free -m | grep Mem)

    # Operation text (single-line, no commas)
    operation=$(tr -d '\n' < "$OPERATIONFILE" | sed 's/,/;/g')

    # Timestamp
    ts=$(date +"%Y-%m-%d %H:%M:%S")

    # CSV row
    echo "$ts,$used,$free,$available,$cpu_usage,$operation" >> "$PERFLOGFILE"
done
