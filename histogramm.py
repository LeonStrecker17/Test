import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from fitter import Fitter

# ==========================================
# 1. CONFIGURATION
# ==========================================

# Standard distributions commonly found in manufacturing data
COMMON_DISTRIBUTIONS = [
    'norm', 'lognorm', 'gamma', 'beta', 'weibull_min', 'pareto', 
    't', 'expon'
]

# SPC Limits (Traffic light definitions for STAB index)
LIMITS_SIGMA_STAB = {'target': 1.0, 'warn': 1.2, 'alarm': 1.5}
LIMITS_MU_STAB    = {'target': 0.0, 'warn': 0.3, 'alarm': 0.5}


# ==========================================
# 2. CORE LOGIC: Distribution & Metrics
# ==========================================

def get_robust_sigma_and_mu(data, fit_distribution=True, use_abs_values=False):
    """
    Calculates Median (mu) and Equivalent Sigma (sigma) from data.
    
    Args:
        data (array): Input data array.
        fit_distribution (bool): 
            True = Runs full 'fitter' process (accurate, slower).
            False = Uses empirical quantiles of raw data (fast, for timeline).
        use_abs_values (bool):
            True = Converts all data to absolute values (fixes sign errors).
            
    Returns:
        dict: Contains sigma_equiv, median, limits, distribution_object, etc.
    """
    # 1. Handle Sign/Absolute Values (if measurement error is known)
    if use_abs_values:
        data = np.abs(data)
    
    # 2. Case A: Exact Fit (for Snapshot / Histogram)
    if fit_distribution:
        # Run Fitter
        f = Fitter(data, distributions=COMMON_DISTRIBUTIONS, timeout=10)
        plt.ioff() # Suppress internal fitter plots
        f.fit()
        plt.ion()
        
        # Get best distribution based on Sum of Square Errors
        best_name = list(f.get_best(method='sumsquare_error').keys())[0]
        best_params = f.fitted_param[best_name]
        
        # Create Scipy distribution object
        dist = getattr(stats, best_name)(*best_params)
        
        # Calculate exact quantiles of the fitted curve (0.135% to 99.865%)
        lsl = dist.ppf(0.00135)
        usl = dist.ppf(0.99865)
        median = dist.ppf(0.5)
        
        return {
            'sigma_equiv': (usl - lsl) / 6.0,
            'median': median,
            'lsl': lsl, 
            'usl': usl,
            'dist_obj': dist,
            'dist_name': best_name,
            'data_used': data
        }
        
    # 3. Case B: Fast Estimation (for rolling Timeline)
    else:
        # Handle empty window case
        if len(data) == 0:
            return {'sigma_equiv': np.nan, 'median': np.nan, 'lsl': np.nan, 'usl': np.nan, 'data_used': data}

        # Use percentiles on raw data
        lsl = np.nanquantile(data, 0.00135)
        usl = np.nanquantile(data, 0.99865)
        median = np.nanmedian(data)
        
        return {
            'sigma_equiv': (usl - lsl) / 6.0,
            'median': median,
            'lsl': lsl, 
            'usl': usl,
            'dist_obj': None,
            'dist_name': 'empirical',
            'data_used': data
        }


# ==========================================
# 3. PART A: SNAPSHOT PLOT (Histogram)
# ==========================================
def plot_snapshot_analysis(df, feature_name, hist_sigma_ref, use_abs=False):
    """
    Generates the histogram with fitted curve and current STAB values.
    Ensures legend and text box do not overlap.
    """
    print(f"\n--- Creating Snapshot for {feature_name} ---")
    
    raw_data = df['values'].dropna().values
    
    # 1. Run Analysis
    res = get_robust_sigma_and_mu(raw_data, fit_distribution=True, use_abs_values=use_abs)
    plot_data = res['data_used']
    
    # 2. Calculate STAB Values
    sigma_stab = res['sigma_equiv'] / hist_sigma_ref
    
    # mu STAB (Calculate variation of group medians)
    group_size = 5
    num_groups = len(plot_data) // group_size
    if num_groups > 1:
        grps = plot_data[:num_groups*group_size].reshape(-1, group_size)
        # Note: If use_abs=True, medians are calculated on positive data
        sigma_mu = np.std(np.median(grps, axis=1), ddof=1)
        mu_stab = sigma_mu / hist_sigma_ref
    else:
        mu_stab = 0

    # 3. Plotting
    plt.figure(figsize=(10, 6))
    
    # Histogram
    sns.histplot(plot_data, stat="density", bins=30, alpha=0.4, color="grey", label="Used Data")
    if use_abs:
        sns.histplot(raw_data, stat="density", bins=30, alpha=0.1, color="red", label="Raw (with signs)")
    
    # Fitted Curve
    x = np.linspace(min(plot_data), max(plot_data)*1.1, 1000)
    # Clip at 0 for strictly positive distributions
    if use_abs or res['dist_name'] in ['lognorm', 'gamma', 'pareto', 'weibull_min']:
        x = x[x > 0]
        
    plt.plot(x, res['dist_obj'].pdf(x), 'r-', lw=3, label=f"Fit: {res['dist_name']}")
    
    # Limits (LSL/USL)
    plt.axvline(res['lsl'], color='blue', linestyle='--', label=f"LSL: {res['lsl']:.2f}")
    plt.axvline(res['usl'], color='blue', linestyle='--', label=f"USL: {res['usl']:.2f}")
    plt.axvline(res['median'], color='green', lw=2, label=f"Median: {res['median']:.2f}")
    
    # Info Textbox (Top Left)
    info = (f"STAB ANALYSIS\n"
            f"σ-STAB: {sigma_stab:.2f} (Ref: {hist_sigma_ref:.2f})\n"
            f"μ-STAB: {mu_stab:.2f}\n"
            f"Dist: {res['dist_name']}")
            
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    plt.gca().text(0.02, 0.95, info, transform=plt.gca().transAxes, 
                   verticalalignment='top', bbox=props)
    
    # Legend (Forced to Top Right to avoid overlap with Textbox)
    plt.legend(loc='upper right', framealpha=0.9)
    
    plt.title(f"Snapshot Analysis: {feature_name} (AbsMode={use_abs})")
    plt.tight_layout()
    plt.savefig(f"SPC_Snapshot_{feature_name}.png")
    print(f"Snapshot saved: SPC_Snapshot_{feature_name}.png")
    plt.close()


# ==========================================
# 4. PART B: TIMELINE PLOT (Trend & Limits)
# ==========================================
def plot_timeline_analysis(df, feature_name, hist_sigma_ref, window_size=50, use_abs=False):
    """
    Generates the rolling trend chart with traffic light limits.
    """
    print(f"\n--- Creating Timeline for {feature_name} ---")
    
    df = df.sort_values('Date').set_index('Date')
    vals = df['values']
    
    sigma_stab_list = []
    mu_stab_list = []
    dates = []
    
    # Rolling Calculation (Step size 5 for performance)
    step = 5
    for i in range(window_size, len(vals), step):
        window_data = vals.iloc[i-window_size : i].values
        current_date = vals.index[i]
        
        # Fast analysis of the window
        res = get_robust_sigma_and_mu(window_data, fit_distribution=False, use_abs_values=use_abs)
        plot_data = res['data_used']
        
        if np.isnan(res['sigma_equiv']): continue

        # Sigma STAB
        s_stab = res['sigma_equiv'] / hist_sigma_ref
        
        # Mu STAB (Subgroup logic)
        group_size = 5
        n_groups = len(plot_data) // group_size
        if n_groups > 2:
            grps = plot_data[:n_groups*group_size].reshape(-1, group_size)
            sigma_mu = np.std(np.median(grps, axis=1), ddof=1)
            m_stab = sigma_mu / hist_sigma_ref
        else:
            m_stab = 0
            
        sigma_stab_list.append(s_stab)
        mu_stab_list.append(m_stab)
        dates.append(current_date)
        
    # Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # --- PLOT 1: Sigma STAB ---
    ax1.plot(dates, sigma_stab_list, color='blue', lw=2)
    ax1.set_title(f"Dispersion Stability ($\sigma$-STAB): {feature_name}")
    ax1.set_ylabel("Index (1.0 = Ref)")
    
    # Limits
    ax1.axhline(LIMITS_SIGMA_STAB['target'], color='green', ls='-', alpha=0.5, label='Target')
    ax1.axhline(LIMITS_SIGMA_STAB['warn'], color='orange', ls='--', label='Warning')
    ax1.axhline(LIMITS_SIGMA_STAB['alarm'], color='red', ls='--', label='Alarm')
    ax1.fill_between(dates, 0, LIMITS_SIGMA_STAB['warn'], color='green', alpha=0.1)
    
    ax1.legend(loc='upper left', framealpha=0.9) # Legend with background
    ax1.grid(True, alpha=0.3)
    
    # --- PLOT 2: Mu STAB ---
    ax2.plot(dates, mu_stab_list, color='purple', lw=2)
    ax2.set_title(f"Location Stability ($\mu$-STAB): {feature_name}")
    ax2.set_ylabel("Index (near 0 = Stable)")
    
    # Limits
    ax2.axhline(LIMITS_MU_STAB['target'], color='green', ls='-', alpha=0.5)
    ax2.axhline(LIMITS_MU_STAB['warn'], color='orange', ls='--', label='Warning')
    ax2.axhline(LIMITS_MU_STAB['alarm'], color='red', ls='--', label='Alarm')
    ax2.fill_between(dates, 0, LIMITS_MU_STAB['warn'], color='green', alpha=0.1)
    
    ax2.legend(loc='upper left', framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f"SPC_Timeline_{feature_name}.png")
    print(f"Timeline saved: SPC_Timeline_{feature_name}.png")
    plt.close()


# ==========================================
# 5. MAIN (Simulation & Tests)
# ==========================================
if __name__ == "__main__":
    np.random.seed(42)
    
    print("==========================================")
    print("SCENARIO 1: Mirrored Data (Sign Error)")
    print("==========================================")
    
    # Scenario: Target is 2.0, but signs are mixed (+/-)
    true_data = np.random.normal(loc=2.0, scale=0.5, size=600)
    signs = np.random.choice([1, -1], size=600)
    mirrored_values = true_data * signs  # Creates two peaks at -2 and +2
    
    df_mirrored = pd.DataFrame({
        'values': mirrored_values, 
        'Date': pd.date_range("2024-01-01", periods=600, freq="h")
    })
    
    # Reference Sigma (Assumption: clean process has ~0.5 equiv. sigma)
    HIST_REF_MIRRORED = 0.5 
    
    # IMPORTANT: use_abs=True activates the "Correction Mode"
    plot_snapshot_analysis(df_mirrored, "Scen1_SignError", HIST_REF_MIRRORED, use_abs=False)
    plot_timeline_analysis(df_mirrored, "Scen1_SignError", HIST_REF_MIRRORED, window_size=50, use_abs=True)


    print("\n==========================================")
    print("SCENARIO 2: Standard Data (LogNormal, Skewed)")
    print("==========================================")
    
    # Scenario: Skewed distribution, strictly positive (e.g., Roughness)
    standard_values = stats.lognorm.rvs(s=0.7, scale=10, size=600)
    
    df_standard = pd.DataFrame({
        'values': standard_values, 
        'Date': pd.date_range("2024-01-01", periods=600, freq="h")
    })

    # Calculate Reference Sigma from the first 200 values (Baseline)
    baseline_res = get_robust_sigma_and_mu(standard_values[:200], fit_distribution=False)
    HIST_REF_STANDARD = baseline_res['sigma_equiv']
    print(f"Calculated Baseline Sigma for Scenario 2: {HIST_REF_STANDARD:.4f}")

    # Here use_abs=False, because data is physically correct
    plot_snapshot_analysis(df_standard, "Scen2_LogNormal", HIST_REF_STANDARD, use_abs=False)
    plot_timeline_analysis(df_standard, "Scen2_LogNormal", HIST_REF_STANDARD, window_size=50, use_abs=False)
