#!/usr/bin/env bash


# Prepare expected environment
BASE_PATH=$HOME
source $BASE_PATH/btc/coinjoin-analysis/scripts/activate_env.sh

echo "###############################################" >> $BASE_PATH/btc/summary.log

#
# Extract Dumplings results
#
# Remove previous temporary directory
rm -rf $TMP_DIR/
# Create new temporary directory
mkdir $TMP_DIR/
# Unzip processed dumplings files
#unzip $BASE_PATH/btc/dumplings.zip -d $TMP_DIR/
unzip $BASE_PATH/dumplings.zip -d $TMP_DIR/



#
# Process Wasabi 2.0
#
$BASE_PATH/btc/coinjoin-analysis/scripts/process_ww2.sh

#
# Process Whirlpool Ashigaru
#
$BASE_PATH/btc/coinjoin-analysis/scripts/process_aw.sh

#
# Process Wasabi 1.0 
#
$BASE_PATH/btc/coinjoin-analysis/scripts/process_ww1.sh

#
# Process Samourai Whirlpool 
#
$BASE_PATH/btc/coinjoin-analysis/scripts/process_sw.sh


#
# Process JoinMarket 
# Note: Needs to come after Wasabi 1.0 and Wasabi 2.0 for false positives restoration 
#
$BASE_PATH/btc/coinjoin-analysis/scripts/process_jm.sh



#
# Visualize processed coinjoins
#
$BASE_PATH/btc/coinjoin-analysis/scripts/visualize_ww2.sh
$BASE_PATH/btc/coinjoin-analysis/scripts/visualize_aw.sh
$BASE_PATH/btc/coinjoin-analysis/scripts/visualize_jm.sh
$BASE_PATH/btc/coinjoin-analysis/scripts/visualize_ww1.sh
$BASE_PATH/btc/coinjoin-analysis/scripts/visualize_sw.sh



#
# Run check for created files
#
source $BASE_PATH/btc/coinjoin-analysis/venv/bin/activate 
cd $BASE_PATH/btc/coinjoin-analysis/src
python3 -m cj_process.file_check $TMP_DIR/Scanner/  | tee parse_dumplings.py.log

# Summary of executed analysis
echo "{\"date\":\"$(date +%d-%m-%Y)\",\"lastProcessedBlockHeight\":\"$(cat $TMP_DIR/Scanner/LastProcessedBlockHeight.txt)\"}" > $TMP_DIR/Scanner/summary.json


#
# Backup outputs
#
BASE_BACKUP_PATH=/mnt
DEST_DIR="$BASE_BACKUP_PATH/data/dumplings_archive/results_$(date +%Y%m%d)"
echo $DEST_DIR 

# Get the absolute paths of source and destination
SOURCE_DIR=$(realpath "$TMP_DIR")
DEST_DIR=$(realpath "$DEST_DIR")

# Use find to locate all .json files except info_*.json and copy them while preserving structure
find "$TMP_DIR" -type f \( -name "*.json" -o -name "*.pdf" -o -name "*.png" -o -name "*.html" -o -name "coinjoin_results_check_summary.txt" \) ! -name "coinjoin_tx_info*.json" ! -name "*_events.json" ! -name "*_false_filtered_cjtxs.json" | while read -r file; do
    # Compute relative path
    REL_PATH="${file#$SOURCE_DIR/}"
    # Create target directory if it does not exist
    mkdir -p "$DEST_DIR/$(dirname "$REL_PATH")"
    # Copy file
    cp "$file" "$DEST_DIR/$REL_PATH"
    #echo "Copying $file to $DEST_DIR/$REL_PATH"
done
echo "Selected files archived to: $DEST_DIR"


#
# Compute aggregated liquidity statistics from many previous daily runs
#
for dir in zksnacks kruw gingerwallet opencoordinator wasabicoordinator coinjoin_nl wasabist dragonordnance mega btip; do
    python $BASE_PATH/btc/coinjoin-analysis/src/cj_process/scan_results_plot.py $BASE_BACKUP_PATH/data/dumplings_archive/ liquidity_summary_wasabi2_$dir
done
# Copy resulting files to the folder of a current day
cp -p $BASE_BACKUP_PATH/data/dumplings_archive/*.png "$DEST_DIR/Scanner/"

#
# Create montage from multiple selected images
#
DEST_DIR="$BASE_BACKUP_PATH/data/dumplings_archive/results_$(date +%Y%m%d)"

# Wasabi2
image_list=""
for pool in others kruw gingerwallet opencoordinator coinjoin_nl wasabicoordinator wasabist dragonordnance mega btip; do
    pool_PATH="$DEST_DIR/Scanner/wasabi2_$pool/wasabi2_${pool}_cummul_values_norm.png"
    image_list="$image_list $pool_PATH"
done
montage $image_list -tile 2x -geometry +2+2 $DEST_DIR/Scanner/wasabi2/wasabi2_tiles_all_cummul_values_norm.png

# Ashigaru + JoinMarket
image_list=""
for pool in whirlpool_ashigaru_2_5M whirlpool_ashigaru_25M joinmarket_all; do
    pool_PATH="$DEST_DIR/Scanner/$pool/${pool}_cummul_values_norm.png"
    image_list="$image_list $pool_PATH"
done
montage $image_list -tile 2x -geometry +2+2 $DEST_DIR/Scanner/ashigaru_joinmarket_all_cummul_values_norm.png

# Multi-days stats for relevant coordinators
image_list=""
for pool in kruw gingerwallet opencoordinator coinjoin_nl; do
    pool_PATH="$DEST_DIR/Scanner/liquidity_summary_wasabi2_${pool}_metrics_stacked.png"
    image_list="$image_list $pool_PATH"
done
montage $image_list -tile 2x -geometry +2+2 $DEST_DIR/Scanner/liquidity_multiday_summary.png



#
# Summary montage
#
# Whole wasabi2 + JoinMarket 
image_list=(
  "$DEST_DIR/Scanner/wasabi2/wasabi2_cummul_values_norm.png"
  "$DEST_DIR/Scanner/joinmarket_all/joinmarket_all_cummul_values_norm.png"
  "$DEST_DIR/Scanner/wasabi1/wasabi1_cummul_values_norm.png"
)

# Ashigaru pools
for pool in whirlpool_ashigaru_2_5M whirlpool_ashigaru_25M; do
    image_list+=("$DEST_DIR/Scanner/$pool/${pool}_cummul_values_norm.png")
done

# wasabi2 pools
for pool in others kruw gingerwallet opencoordinator coinjoin_nl; do
    image_list+=("$DEST_DIR/Scanner/wasabi2_$pool/wasabi2_${pool}_cummul_values_norm.png")
done

montage "${image_list[@]}" -tile 2x -geometry +2+2 $DEST_DIR/Scanner/summary_tiles_all_cummul_values_norm.png

# Last months of selected pools
image_list=()
LAST_INTERVAL="$(date +%Y-%m)-01 00-00-00--$(date -d "$(date +%Y-%m-01) +1 month" +%Y-%m)-01 00-00-00_unknown-static-100-1utxo" 
echo $LAST_INTERVAL
for pool in wasabi2_kruw wasabi2_gingerwallet wasabi2_opencoordinator wasabi2_coinjoin_nl whirlpool_ashigaru_2_5M joinmarket_all; do
    image_list+=("$DEST_DIR/Scanner/$pool/${LAST_INTERVAL}/${pool}_input_types_values_norm.png")
done

montage "${image_list[@]}" \
  -geometry 1600x1600+2+2 \
  -tile 3x \
  -strip -define png:compression-level=9 \
  "$DEST_DIR/Scanner/summary2_tiles_all_cummul_values_norm.png"


# all wasabi2 pools
image_list=()
for pool in others kruw gingerwallet opencoordinator coinjoin_nl wasabicoordinator wasabist mega btip unknown_2024; do
    image_list+=("$DEST_DIR/Scanner/wasabi2_$pool/wasabi2_${pool}_cummul_values_norm.png")
done

montage "${image_list[@]}" -tile 2x -geometry +2+2 $DEST_DIR/Scanner/summary_tiles_ww2_cummul_values_norm.png


#
# Upload selected files (separate scripts, can be configured based on desired upload service)
#
$BASE_PATH/btc/coinjoin-analysis/scripts/upload_results.sh

echo "###############################################" >> $BASE_PATH/btc/summary.log


