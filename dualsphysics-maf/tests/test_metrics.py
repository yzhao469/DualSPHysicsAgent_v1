import pytest

from mcp_server.tools.metrics import compute_metrics

pytestmark = pytest.mark.unit


def test_compute_metrics_returns_no_ground_truth(tmp_path, write_measuretool_csv):
    result_csv = write_measuretool_csv(
        "result.csv",
        ["Time", "Velocity"],
        [[0.0, 1.0], [1.0, 2.0]],
    )

    metrics = compute_metrics(str(result_csv), str(tmp_path / "missing.csv"))

    assert metrics == {"status": "no_ground_truth"}


def test_compute_metrics_interpolates_to_ground_truth_grid(write_measuretool_csv):
    result_csv = write_measuretool_csv(
        "result.csv",
        ["Time", "Velocity"],
        [[0.0, 0.0], [2.0, 4.0]],
    )
    ground_truth_csv = write_measuretool_csv(
        "ground_truth.csv",
        ["Time", "Velocity"],
        [[0.0, 0.0], [1.0, 2.0], [2.0, 4.0]],
    )

    metrics = compute_metrics(str(result_csv), str(ground_truth_csv))

    assert metrics["status"] == "ok"
    assert metrics["num_timesteps"] == 3
    assert metrics["num_probes"] == 1
    assert metrics["rmse"] == 0.0
    assert metrics["max_error"] == 0.0
    assert metrics["correlation"] == 1.0
    assert metrics["rmse_per_col"] == {"Velocity": 0.0}


def test_compute_metrics_reports_missing_time_column(write_measuretool_csv):
    result_csv = write_measuretool_csv(
        "result.csv",
        ["Step", "Velocity"],
        [[0.0, 1.0], [1.0, 2.0]],
    )
    ground_truth_csv = write_measuretool_csv(
        "ground_truth.csv",
        ["Time", "Velocity"],
        [[0.0, 1.0], [1.0, 2.0]],
    )

    metrics = compute_metrics(str(result_csv), str(ground_truth_csv))

    assert metrics["status"] == "error"
    assert metrics["message"] == "No 'Time' column found in one or both CSVs"
