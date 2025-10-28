"""
The collection of analysis methods for deeper evaluation and assessment of algorithms used.
E.g., the best threshold for coordinator discovery, sensitivity to missing coordinators....
"""
import copy
import logging
import math
import os
import secrets
from collections import defaultdict, Counter
from enum import Enum
from typing import List
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from cj_process import cj_visualize as cjviz

from cj_process import cj_analysis as als

def analyze_coordinator_detection(cjtxs: dict, tx_list: dict, coords: List):
    # Transform dictionary to {'coord': [cjtxs]} format
    tx_list_t = defaultdict(list)
    for key, value in tx_list.items():
        tx_list_t[value].append(key)

    # For given coordinator, compute statistics for all its transactions
    intercoord_ratios = {}
    for coord in coords:
        intercoord_ratios[coord] = {}
        # Compute ratio of in-coordinator remixes
        # For each remixed input, check if it is coming form the same coordinator
        for txid in tx_list_t[coord]:
            if txid in cjtxs['coinjoins'].keys():
                remix_inputs = [index for  index in cjtxs['coinjoins'][txid]['inputs'].keys() if cjtxs['coinjoins'][txid]['inputs'][index]['mix_event_type'] == 'MIX_REMIX']
                remix_outputs = [index for  index in cjtxs['coinjoins'][txid]['outputs'].keys() if cjtxs['coinjoins'][txid]['outputs'][index]['mix_event_type'] == 'MIX_REMIX']

                # Number of remixed inputs/outputs from the same coordinator
                same_coord_inputs_txids = [(txid, cjtxs['coinjoins'][txid]['inputs'][index].get('burn_time', 0)) for index in remix_inputs
                                             if 'spending_tx' in cjtxs['coinjoins'][txid]['inputs'][index]
                                             and tx_list.get(als.extract_txid_from_inout_string(cjtxs['coinjoins'][txid]['inputs'][index]['spending_tx'])[0], '-') == coord]
                num_same_coord_inputs = len(same_coord_inputs_txids)
                num_same_coord_inputs_burntime_sum = sum([math.log10(burn_time) for txid, burn_time in same_coord_inputs_txids])
                same_coord_outputs_txids = [(txid, cjtxs['coinjoins'][txid]['outputs'][index].get('burn_time', 0)) for index in remix_outputs
                                              if 'spend_by_tx' in cjtxs['coinjoins'][txid]['outputs'][index]
                                              and tx_list.get(als.extract_txid_from_inout_string(cjtxs['coinjoins'][txid]['outputs'][index]['spend_by_tx'])[0], '-') == coord]
                num_same_coord_outputs = len(same_coord_outputs_txids)
                num_same_coord_outputs_burntime_sum = sum([math.log10(burn_time) for txid, burn_time in same_coord_outputs_txids])

                # Number of inputs from the other most common (!= same coord)
                input_coords_txids = [(tx_list.get(als.extract_txid_from_inout_string(cjtxs['coinjoins'][txid]['inputs'][index]['spending_tx'])[0], '-'),
                                       cjtxs['coinjoins'][txid]['inputs'][index].get('burn_time', 0)) for index in remix_inputs
                                             if 'spending_tx' in cjtxs['coinjoins'][txid]['inputs'][index]]
                output_coords_txids = [(tx_list.get(als.extract_txid_from_inout_string(cjtxs['coinjoins'][txid]['outputs'][index]['spend_by_tx'])[0], '-'),
                                        cjtxs['coinjoins'][txid]['outputs'][index].get('burn_time', 0)) for index in remix_outputs
                                             if 'spend_by_tx' in cjtxs['coinjoins'][txid]['outputs'][index]]
                # get the highest count (0 if no valid coordinators remain)
                input_coords_counts = Counter([coord for coord, burntime in input_coords_txids])
                input_coords_others_filtered = {k: v for k, v in input_coords_counts.items() if k not in ('-', coord)}
                input_max_count = max(input_coords_others_filtered.values(), default=0)
                output_coords_counts = Counter([coord for coord, burntime in output_coords_txids])
                output_coords_others_filtered = {k: v for k, v in output_coords_counts.items() if k not in ('-', coord)}
                output_max_count = max(output_coords_others_filtered.values(), default=0)

                # Store result
                intercoord_ratios[coord][txid] = {'broadcast_time': cjtxs['coinjoins'][txid]['broadcast_time'],
                                                 'in_ratio': num_same_coord_inputs / len(remix_inputs) if len(remix_inputs) > 0 else 0,
                                                 'out_ratio': num_same_coord_outputs / len(remix_outputs) if len(remix_outputs) > 0 else 0,
                                                 'in_ratio_second': input_max_count / len(remix_inputs) if len(remix_inputs) > 0 else 0,
                                                 'out_ratio_second': output_max_count / len(remix_outputs) if len(remix_outputs) > 0 else 0}

    return intercoord_ratios


class DROP_TYPE(Enum):
    RANDOM_ANY = 'RANDOM_ANY'
    RANDOM_SINGLE = 'RANDOM_SINGLE'
    TAIL = 'TAIL'
    FRONT = 'FRONT'

class COORD_DISCOVERY_ANALYSIS_CFG:
    threshold_range = []
    intermix_threshold = 0.4
    drop_ratio_range = []
    drop_type = DROP_TYPE.TAIL
    experiment_name = 'unset'

    def __init__(self, threshold_range: list, drop_ratio_range: list, repeat_range: list, drop_type: DROP_TYPE):
        self.threshold_range = threshold_range
        self.drop_ratio_range = drop_ratio_range
        self.repeat_range = repeat_range
        self.drop_type = drop_type


# Kill internal thread storms in child processes
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# --- GLOBALS to be shared (read-only) ---
_CJTXS = None
_SORTED_CJTXS = None
_GROUND_TRUTH = None
_INITIAL_KNOWN_TXS = None
_ALL_TXS = None
_TARGET_PATH = None  # only for saving JSON (safe)
_EXPERIMENT_BASE_NAME = None

def _init_globals_from_parent(cjtxs, sorted_cjtxs, ground_truth, initial_known, all_txs, target_path, experiment_base_name):
    """Called in parent (POSIX fork will COW-share these)."""
    global _CJTXS, _SORTED_CJTXS, _GROUND_TRUTH, _INITIAL_KNOWN_TXS, _ALL_TXS, _TARGET_PATH, _EXPERIMENT_BASE_NAME
    _CJTXS = cjtxs
    _SORTED_CJTXS = sorted_cjtxs
    _GROUND_TRUTH = ground_truth
    _INITIAL_KNOWN_TXS = initial_known
    _ALL_TXS = all_txs
    _TARGET_PATH = target_path
    _EXPERIMENT_BASE_NAME = experiment_base_name


def _spawn_initializer(target_path, sorted_cjtxs, initial_known_serial):
    """
    Windows / non-POSIX fallback: load heavy data once per process.
    We avoid passing megabyte dicts per task.
    """
    global _CJTXS, _SORTED_CJTXS, _GROUND_TRUTH, _INITIAL_KNOWN_TXS, _ALL_TXS, _TARGET_PATH
    _TARGET_PATH = target_path

    # Recompute heavy-but-shared state once per process
    _CJTXS = als.load_coinjoins_from_file(target_path, None, True)["coinjoins"]
    _SORTED_CJTXS = sorted_cjtxs

    _GROUND_TRUTH = als.load_coordinator_mapping_from_file(os.path.join(target_path, 'txid_coord.json'), 'crawl')

    # initial_known_serial carries the pre-sorted lists (small enough)
    _INITIAL_KNOWN_TXS = initial_known_serial
    _ALL_TXS = {txid: None for coord in _INITIAL_KNOWN_TXS for txid in _INITIAL_KNOWN_TXS[coord]}


# --- helpers (unchanged semantics) ---
def drop_random_fraction_dict(initial_data: dict, percent: int):
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    keep_prob = 1 - percent / 100
    return {x: None for x in initial_data
            if secrets.randbelow(10000) < int(10000 * keep_prob)}


def drop_part_fraction_dict(initial_data: dict, percent: int, coord_to_drop: None, from_end: bool = True):
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    for coord in list(initial_data.keys()):
        if coord_to_drop is not None and coord != coord_to_drop:
            continue
        keep_len = int((1 - percent / 100) * len(initial_data[coord]))
        if from_end:
            # Drop ending transactions
            initial_data[coord] = initial_data[coord][0:keep_len]
        else:
            # Drop front transactions
            initial_data[coord] = initial_data[coord][len(initial_data[coord]) - keep_len : ]
    return initial_data


# --- worker uses ONLY GLOBALS; nothing heavy in args ---
def _eval_drop_attributions_single_coord(coord_to_test, cfg: COORD_DISCOVERY_ANALYSIS_CFG):
    print(f"[coord={coord_to_test}] pid={os.getpid()} START")

    baseline_coord_txs_named_sorted = {}
    results = {}
    for drop_fraction in [0] + cfg.drop_ratio_range:  # Iterate over fraction of known mappings to drop. Always add 0 as baseline
        print(f"[coord={coord_to_test}] drop={drop_fraction}")
        coord_names = list(_INITIAL_KNOWN_TXS.keys()) + ['unattributed']
        results[drop_fraction] = {
            coord_name: {'fp': [], 'fn': [], 'fp_ratio': [], 'fn_ratio': []}
            for coord_name in coord_names
        }

        for _ in cfg.repeat_range:  # Iterate specified number of times (to compute )
            # Prepare structures for modification (dropping certain attributions)
            drop_ground_truth_known_coord_txs = copy.deepcopy(_GROUND_TRUTH)
            drop_initial_known_txs = copy.deepcopy(_INITIAL_KNOWN_TXS)

            if cfg.drop_type == DROP_TYPE.RANDOM_ANY:
                # Dropping random attributed txs
                to_keep_txs = drop_random_fraction_dict(_ALL_TXS, drop_fraction)
                for coord_name in list(drop_initial_known_txs.keys()):
                    for i in range(len(drop_initial_known_txs[coord_name]) - 1, -1, -1):
                        if drop_initial_known_txs[coord_name][i] not in to_keep_txs:
                            drop_initial_known_txs[coord_name].pop(i)
            elif cfg.drop_type == DROP_TYPE.RANDOM_SINGLE:
                # Dropping random attributed txs for specific coordinator
                to_keep_txs = drop_random_fraction_dict(drop_initial_known_txs[coord_to_test], drop_fraction)
                for i in range(len(drop_initial_known_txs[coord_to_test]) - 1, -1, -1):
                    if drop_initial_known_txs[coord_to_test][i] not in to_keep_txs:
                        drop_initial_known_txs[coord_to_test].pop(i)
            elif cfg.drop_type == DROP_TYPE.TAIL:
                # Dropping tail attributed txs
                drop_initial_known_txs = drop_part_fraction_dict(
                    drop_initial_known_txs, drop_fraction, coord_to_drop=coord_to_test, from_end=True
                )
            elif cfg.drop_type == DROP_TYPE.FRONT:
                # Dropping tail attributed txs
                drop_initial_known_txs = drop_part_fraction_dict(
                    drop_initial_known_txs, drop_fraction, coord_to_drop=coord_to_test, from_end=False
                )
            else:
                assert False, 'Invalid drop type'

            # Core detection (READS globals)
            _, _, _, coord_txs_named_sorted = als.run_coordinator_detection(
                _CJTXS, _SORTED_CJTXS, drop_ground_truth_known_coord_txs, drop_initial_known_txs,
                False, cfg.intermix_threshold
            )

            # For baseline, store initial state with no modifications and ignore these values for FP and FN computation
            # Rationale: we do not have complete ground truth for whole inspected interval => missing txs classified
            #   as FP even for the no-modifications case (drop_fraction == 0). We therefore substract these specific
            #   transactions when computing FP and FN stats
            if drop_fraction == 0:
                for coord_name in _INITIAL_KNOWN_TXS.keys():
                    baseline_coord_txs_named_sorted[coord_name] = {}
                    gt = set(_INITIAL_KNOWN_TXS.get(coord_name, []))  # ground truth
                    pred = set(coord_txs_named_sorted.get(coord_name, []))  # predictions
                    baseline_coord_txs_named_sorted[coord_name]['fp_list'] = pred - gt
                    baseline_coord_txs_named_sorted[coord_name]['fn_list'] = gt - pred

            # Compute false positives and false negatives for current experiment
            for coord_name in _INITIAL_KNOWN_TXS.keys():
                gt = set(_INITIAL_KNOWN_TXS.get(coord_name, []))  # ground truth
                pred = set(coord_txs_named_sorted.get(coord_name, []))  # predictions
                FP = pred - gt
                FN = gt - pred
                # Correct for unattributed transactions from "drop_fraction == 0" case
                FP = [txid for txid in FP if txid not in baseline_coord_txs_named_sorted[coord_name]['fp_list']]
                FN = [txid for txid in FP if txid not in baseline_coord_txs_named_sorted[coord_name]['fn_list']]
                denom = max(1, len(_INITIAL_KNOWN_TXS[coord_name]))
                # Now compute and store results
                results[drop_fraction][coord_name]['fp'].append(len(FP))
                results[drop_fraction][coord_name]['fn'].append(len(FN))
                results[drop_fraction][coord_name]['fp_ratio'].append((len(FP) / denom) * 100)
                results[drop_fraction][coord_name]['fn_ratio'].append((len(FN) / denom) * 100)

            # Compute synthetic result for unattributed transactions
            unattr = len(coord_txs_named_sorted.get('unattributed', []))
            results[drop_fraction]['unattributed']['fp'].append(unattr)
            results[drop_fraction]['unattributed']['fn'].append(0)
            results[drop_fraction]['unattributed']['fp_ratio'].append((unattr / len(_CJTXS.keys())) * 100)
            results[drop_fraction]['unattributed']['fn_ratio'].append(0)

        # periodic save
        if drop_fraction % 10 == 0:
            als.save_json_to_file_pretty(
                os.path.join(_TARGET_PATH, f"{coord_to_test}_{cfg.experiment_name}_{drop_fraction}.json"),
                results
            )

    # final save
    als.save_json_to_file_pretty(
        os.path.join(_TARGET_PATH, f"{coord_to_test}_{cfg.experiment_name}.json"),
        results
    )

    print(f"[coord={coord_to_test}] pid={os.getpid()} DONE")
    return coord_to_test, results


# --- worker uses ONLY GLOBALS; nothing heavy in args ---
def _eval_detection_threshold_single_coord(coord_to_test, cfg: COORD_DISCOVERY_ANALYSIS_CFG):
    print(f"[coord={coord_to_test}] pid={os.getpid()} START")

    # default baseline threshold value established based on intermix ratios of ground truth transactions
    BASELINE_INTERMIX_THRESHOLD = 0.4

    baseline_coord_txs_named_sorted = {}
    results = {}
    base_num_unattr_txs = 0
    for intermix_threshold in [BASELINE_INTERMIX_THRESHOLD] + cfg.threshold_range:
        print(f"[coord={coord_to_test}] intermix threshold={intermix_threshold}")
        coord_names = list(_INITIAL_KNOWN_TXS.keys()) + ['unattributed']
        results[intermix_threshold] = {
            coord_name: {'fp': [], 'fn': [], 'fp_ratio': [], 'fn_ratio': []}
            for coord_name in coord_names
        }

        # Core detection (READS globals)
        _, _, _, coord_txs_named_sorted = als.run_coordinator_detection(
            _CJTXS, _SORTED_CJTXS, _GROUND_TRUTH, _INITIAL_KNOWN_TXS, False, intermix_threshold
        )

        # For baseline, store initial state with no modifications and ignore these values for FP and FN computation
        # Rationale: we do not have complete ground truth for whole inspected interval => missing txs classified
        #   as FP even for the no-modifications case (intermix_threshold == BASELINE_INTERMIX_THRESHOLD). We therefore substract these specific
        #   transactions when computing FP and FN stats
        if intermix_threshold == BASELINE_INTERMIX_THRESHOLD:
            for coord_name in _INITIAL_KNOWN_TXS.keys():
                baseline_coord_txs_named_sorted[coord_name] = {}
                gt = set(_INITIAL_KNOWN_TXS.get(coord_name, []))  # ground truth
                pred = set(coord_txs_named_sorted.get(coord_name, []))  # predictions
                baseline_coord_txs_named_sorted[coord_name]['fp_list'] = pred - gt
                baseline_coord_txs_named_sorted[coord_name]['fn_list'] = gt - pred

        # Compute false positives and false negatives for current experiment
        for coord_name in _INITIAL_KNOWN_TXS.keys():
            gt = set(_INITIAL_KNOWN_TXS.get(coord_name, []))  # ground truth
            pred = set(coord_txs_named_sorted.get(coord_name, []))  # predictions
            FP = pred - gt
            FN = gt - pred
            # Correct for unattributed transactions from "intermix_threshold == BASELINE_INTERMIX_THRESHOLD" case
            FP = [txid for txid in FP if txid not in baseline_coord_txs_named_sorted[coord_name]['fp_list']]
            FN = [txid for txid in FN if txid not in baseline_coord_txs_named_sorted[coord_name]['fn_list']]
            denom = max(1, len(_INITIAL_KNOWN_TXS[coord_name]))
            # Now compute and store results
            results[intermix_threshold][coord_name]['fp'].append(len(FP))
            results[intermix_threshold][coord_name]['fn'].append(len(FN))
            results[intermix_threshold][coord_name]['fp_ratio'].append((len(FP) / denom) * 100)
            results[intermix_threshold][coord_name]['fn_ratio'].append((len(FN) / denom) * 100)

        # Compute synthetic result for unattributed transactions
        unattr = len(coord_txs_named_sorted.get('unattributed', []))
        results[intermix_threshold]['unattributed']['fp'].append(unattr)
        results[intermix_threshold]['unattributed']['fn'].append(0)
        results[intermix_threshold]['unattributed']['fp_ratio'].append((unattr / len(_CJTXS.keys())) * 100)
        results[intermix_threshold]['unattributed']['fn_ratio'].append(0)

        # periodic save
        als.save_json_to_file_pretty(
            os.path.join(_TARGET_PATH, f"{coord_to_test}_{_EXPERIMENT_BASE_NAME}_{intermix_threshold}.json"),
            results
        )

    # final save per coord
    als.save_json_to_file_pretty(
        os.path.join(_TARGET_PATH, f"{coord_to_test}_{_EXPERIMENT_BASE_NAME}.json"),
        results
    )

    print(f"[coord={coord_to_test}] pid={os.getpid()} DONE")
    return coord_to_test, results


def wasabi_detect_coordinators_evaluation_parallel(target_path, worker_name, worker_config: COORD_DISCOVERY_ANALYSIS_CFG, experiment_base_name: str):
    """
    Parallel version with memory-friendly sharing:
    - POSIX: 'fork' -> copy-on-write sharing of big read-only dicts.
    - Non-POSIX: 'spawn' -> per-process init (no per-task copies). Memory heavy.
    """
    # Precompute once in parent
    cjtxs = als.load_coinjoins_from_file(target_path, None, True)["coinjoins"]
    ordering = als.compute_cjtxs_relative_ordering(cjtxs)
    sorted_cjtxs = sorted(ordering, key=ordering.get)

    ground_truth_known_coord_txs = als.load_coordinator_mapping_from_file(os.path.join(target_path, 'txid_coord.json'), 'crawl')

    # Build {'coord': [txids]} with deterministic ordering
    transformed_dict = defaultdict(list)
    for txid, coord in ground_truth_known_coord_txs.items():
        transformed_dict[coord].append(txid)
    order_map = {v: i for i, v in enumerate(sorted_cjtxs)}
    for coord in transformed_dict.keys():
        txs_sorted = sorted(
            enumerate(transformed_dict[coord]),
            key=lambda t: (0, order_map[t[1]]) if t[1] in order_map else (1, t[0])
        )
        transformed_dict[coord] = [v for _, v in txs_sorted]
    initial_known_txs = dict(transformed_dict)

    all_txs = {txid: None for coord in initial_known_txs for txid in initial_known_txs[coord]}

    # Initialize globals in parent (used by fork)
    _init_globals_from_parent(
        cjtxs, sorted_cjtxs, ground_truth_known_coord_txs, initial_known_txs, all_txs, target_path, experiment_base_name
    )

    coordinators_names = list(initial_known_txs.keys())
    combined_results_all = {}
    # Choose best context for memory
    if os.name == "posix":
        # Fork gives true COW sharing of already-loaded globals
        ctx = mp.get_context("fork")
        initializer = None
        initargs = ()
    else:
        # Windows / others: no COW. Load once per process via initializer.
        ctx = mp.get_context("spawn")
        initializer = _spawn_initializer
        # Pass only light args; child reloads heavy data from disk one time
        initargs = (target_path, sorted_cjtxs, initial_known_txs)

    for intermix_threshold in worker_config.threshold_range:  # Iterate over provided range of intermix thresholds (detection parameter)
        # Prepare specific detection threshold
        experiment_name_th = f'{experiment_base_name}_intermix_threshold__{intermix_threshold}'
        worker_config.intermix_threshold = intermix_threshold
        worker_config.experiment_name = experiment_name_th

        combined_results = {}  # Results for all examined coordinators

        with ProcessPoolExecutor(
                mp_context=ctx,
                max_workers=os.cpu_count(),
                initializer=initializer,
                initargs=initargs
        ) as ex:
            futures = [ex.submit(worker_name, coord, worker_config) for coord in coordinators_names]
            for fut in as_completed(futures):
                k, res = fut.result()
                combined_results[k] = res

        combined_results_all[f'intermix_threshold__{intermix_threshold}'] = combined_results

        # Plot results
        for coord in coordinators_names:
            file_path = os.path.join(target_path, f"{coord}_{experiment_name_th}.json")
            if os.path.exists(file_path):
                results_all = als.load_json_from_file(file_path)
                results = results_all
                #results = results_all['intermix_threshold_0.4']
                cjviz.plot_coord_attribution_stats(results, target_path, "fp", "fn",
                                                   f"{coord}_{experiment_name_th}_nominal.png")
                cjviz.plot_coord_attribution_stats(results, target_path, "fp_ratio",
                                                       "fn_ratio", f"{coord}_{experiment_name_th}_ratio.png")
            else:
                logging.warning(f'File {file_path} does not exists')

    # Save combined results
    als.save_json_to_file_pretty(
        os.path.join(_TARGET_PATH, f"all_{experiment_base_name}.json"),
        combined_results_all
    )

    return combined_results_all

