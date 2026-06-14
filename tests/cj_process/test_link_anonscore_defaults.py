from cj_process.cj_analysis import compute_link_between_inputs_and_outputs


def test_linker_defaults_missing_output_anon_score_before_propagation():
    coinjoins = {
        "txA": {
            "inputs": {
                0: {"address": "funding-a", "value": 100000},
            },
            "outputs": {
                0: {"address": "remix-a", "value": 40000},
            },
        },
        "txB": {
            "inputs": {
                0: {"address": "remix-a", "value": 40000},
            },
            "outputs": {
                0: {"address": "destination-b", "value": 39000},
            },
        },
    }

    compute_link_between_inputs_and_outputs(coinjoins, ["txA", "txB"])

    assert coinjoins["txA"]["outputs"][0]["anon_score"] == 1.0
    assert coinjoins["txB"]["inputs"][0]["anon_score"] == 1.0

