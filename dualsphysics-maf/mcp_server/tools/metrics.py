"""Compute RMSE and other metrics comparing simulation output vs ground truth."""
import os


def compute_metrics(result_csv: str, ground_truth_csv: str) -> dict:
    """Compare result CSV against ground truth CSV.

    Args:
        result_csv:       Path to MeasureTool output CSV.
        ground_truth_csv: Path to the reference/ground-truth CSV.

    Returns dict with status and metric values.
    """
    if not os.path.isfile(ground_truth_csv):
        return {"status": "no_ground_truth"}

    try:
        import numpy as np
        import pandas as pd
    except ImportError as e:
        return {"status": "error", "message": f"Missing dependency: {e}"}

    def _load_measuretool_csv(path: str) -> "pd.DataFrame":
        """Load a MeasureTool CSV, skipping the 3-line position header."""
        with open(path, "r") as fh:
            lines = fh.readlines()
        # Skip lines starting with ' ;' (position metadata rows)
        data_lines = [l for l in lines if not l.startswith(" ;")]
        import io
        return pd.read_csv(io.StringIO("".join(data_lines)), sep=";", engine="python")

    try:
        # MeasureTool CSVs use ';' separator and have a 3-line position header
        # before the data rows.  We skip those header lines (they start with ' ;').
        result_df = _load_measuretool_csv(result_csv)
        gt_df = _load_measuretool_csv(ground_truth_csv)
    except Exception as e:
        return {"status": "error", "message": f"Failed to load CSVs: {e}"}

    # Identify the time column (case-insensitive)
    def find_time_col(df):
        for c in df.columns:
            if c.strip().lower() == "time":
                return c
        return None

    result_time_col = find_time_col(result_df)
    gt_time_col = find_time_col(gt_df)

    if result_time_col is None or gt_time_col is None:
        return {"status": "error", "message": "No 'Time' column found in one or both CSVs"}

    # Numeric columns excluding time
    result_numeric = [c for c in result_df.columns
                      if c != result_time_col and pd.api.types.is_numeric_dtype(result_df[c])]
    gt_numeric = [c for c in gt_df.columns
                  if c != gt_time_col and pd.api.types.is_numeric_dtype(gt_df[c])]

    # Common columns
    common_cols = [c for c in result_numeric if c in gt_numeric]
    if not common_cols:
        return {"status": "error", "message": "No common numeric columns between result and ground truth"}

    # Interpolate result onto ground-truth time grid
    gt_times = gt_df[gt_time_col].values
    result_times = result_df[result_time_col].values

    rmse_per_col = {}
    corr_per_col = {}
    max_err_per_col = {}

    for col in common_cols:
        gt_vals = gt_df[col].values.astype(float)
        result_vals = result_df[col].values.astype(float)

        # Interpolate result onto ground-truth time points
        interp_vals = np.interp(gt_times, result_times, result_vals)

        diff = interp_vals - gt_vals
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        max_err = float(np.max(np.abs(diff)))

        # Correlation
        if np.std(interp_vals) > 0 and np.std(gt_vals) > 0:
            corr = float(np.corrcoef(interp_vals, gt_vals)[0, 1])
        else:
            corr = float("nan")

        rmse_per_col[col] = rmse
        corr_per_col[col] = corr
        max_err_per_col[col] = max_err

    mean_rmse = float(np.mean(list(rmse_per_col.values())))
    mean_corr_vals = [v for v in corr_per_col.values() if not np.isnan(v)]
    mean_corr = float(np.mean(mean_corr_vals)) if mean_corr_vals else float("nan")
    mean_max_err = float(np.mean(list(max_err_per_col.values())))

    return {
        "status": "ok",
        "rmse": mean_rmse,
        "correlation": mean_corr,
        "max_error": mean_max_err,
        "num_timesteps": int(len(gt_times)),
        "num_probes": int(len(common_cols)),
        "rmse_per_col": rmse_per_col,
    }
