import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from fitter import Fitter
from copy import copy
import os

from inspection_characteristics.preprocessing import outlier_cleaning
from inspection_characteristics.analysis import calculate_median_and_sigma_estimates, calculate_cpk

COMMON_DISTRIBUTIONS = ['norm', 'lognorm', 'gamma', 'beta', 'weibull_min', 'pareto', 't', 'expon']
LIMITS_SIGMA_STAB = {'target': 1.0, 'warn': 1.2, 'alarm': 1.5}
LIMITS_MU_STAB    = {'target': 0.0, 'warn': 0.3, 'alarm': 0.5}

def get_robust_sigma_and_mu(data, fit_distribution=True, use_abs_values=False):
    if use_abs_values: data = np.abs(data)
    data = data[~np.isnan(data)]

    if fit_distribution and len(data) > 10:
        f = Fitter(data, distributions=COMMON_DISTRIBUTIONS, timeout=10)
        plt.ioff(); f.fit(); plt.ion()
        
        best_name = list(f.get_best(method='sumsquare_error').keys())[0]
        best_params = f.fitted_param[best_name]
        dist = getattr(stats, best_name)(*best_params)
        
        lsl, usl, median = dist.ppf(0.00135), dist.ppf(0.99865), dist.ppf(0.5)
        
        return {
            'sigma_equiv': (usl - lsl) / 6.0,
            'median': median,
            'lsl': lsl, 'usl': usl,
            'dist_obj': dist, 'dist_name': best_name,
            'data_used': data
        }
    else:
        if len(data) == 0: return {'sigma_equiv': np.nan}
        lsl, usl = np.nanquantile(data, 0.00135), np.nanquantile(data, 0.99865)
        return {
            'sigma_equiv': (usl - lsl) / 6.0,
            'median': np.nanmedian(data),
            'lsl': lsl, 'usl': usl,
            'dist_obj': None, 'dist_name': 'empirical',
            'data_used': data
        }

def plot_histogramm(df, feature_name, hist_sigma_ref, save_folder, suffix="", use_abs=False):
    """
    Creates the histogram with Fit, LSL/USL lines and info box.
    """
    raw_data = df['value'].dropna().values
    if len(raw_data) < 5: return

    res = get_robust_sigma_and_mu(raw_data, fit_distribution=True, use_abs_values=use_abs)
    plot_data = res['data_used']
    
    sigma_stab = res['sigma_equiv'] / hist_sigma_ref if hist_sigma_ref else 0
    
    # Mu STAB Berechnung
    group_size = 5
    num_groups = len(plot_data) // group_size
    if num_groups > 1:
        grps = plot_data[:num_groups*group_size].reshape(-1, group_size)
        sigma_mu = np.std(np.median(grps, axis=1), ddof=1)
        mu_stab = sigma_mu / hist_sigma_ref if hist_sigma_ref else 0
    else:
        mu_stab = 0

    plt.figure(figsize=(10, 6))
    
    sns.histplot(plot_data, stat="density", bins=30, alpha=0.4, color="grey", label="Used Data")
    if use_abs:
         sns.histplot(raw_data, stat="density", bins=30, alpha=0.1, color="red", label="Raw (with signs)")
    
    x = np.linspace(min(plot_data), max(plot_data)*1.1, 1000)
    if use_abs or res['dist_name'] in ['lognorm', 'gamma', 'pareto', 'weibull_min']:
        x = x[x > 0]
        
    if res['dist_obj']:
        plt.plot(x, res['dist_obj'].pdf(x), 'r-', lw=3, label=f"Fit: {res['dist_name']}")
    
    plt.axvline(res['lsl'], color='blue', linestyle='--', label=f"LSL: {res['lsl']:.2f}")
    plt.axvline(res['usl'], color='blue', linestyle='--', label=f"USL: {res['usl']:.2f}")
    plt.axvline(res['median'], color='green', lw=2, label=f"Median: {res['median']:.2f}")
    
    info = (f"STAB ANALYSIS ({suffix})\n"
            f"σ-STAB: {sigma_stab:.2f} (Ref: {hist_sigma_ref:.2f})\n"
            f"μ-STAB: {mu_stab:.2f}\n"
            f"Dist: {res['dist_name']}")
            
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    plt.gca().text(0.02, 0.95, info, transform=plt.gca().transAxes, 
                   verticalalignment='top', bbox=props)
    
    plt.legend(loc='upper right', framealpha=0.9)
    plt.title(f"Histogramm: {feature_name} ({suffix})")
    plt.tight_layout()
    
    # Filename mit Suffix (Zeitraum)
    filename = os.path.join(save_folder, f"hist_{feature_name}_{suffix}.png")
    plt.savefig(filename)
    plt.close()
    print(f"-> Histogramm saved: {filename}")


def plot_timeline_analysis(df, feature_name, hist_sigma_ref, save_folder, suffix="", window_size=50, use_abs=False):
    """ Creates the trend graph for Sigma-STAB and Mu-STAB """
    df_sorted = df.sort_values('date').set_index('date')
    vals = df_sorted['value']
    
    sigma_stab_list = []
    mu_stab_list = []
    dates = []
    
    step = 5
    for i in range(window_size, len(vals), step):
        window_data = vals.iloc[i-window_size : i].values
        current_date = vals.index[i]
        
        res = get_robust_sigma_and_mu(window_data, fit_distribution=False, use_abs_values=use_abs)
        plot_data = res['data_used']
        
        if np.isnan(res['sigma_equiv']): continue

        s_stab = res['sigma_equiv'] / hist_sigma_ref if hist_sigma_ref else 0
        
        group_size = 5
        n_groups = len(plot_data) // group_size
        if n_groups > 2:
            grps = plot_data[:n_groups*group_size].reshape(-1, group_size)
            sigma_mu = np.std(np.median(grps, axis=1), ddof=1)
            m_stab = sigma_mu / hist_sigma_ref if hist_sigma_ref else 0
        else:
            m_stab = 0
            
        sigma_stab_list.append(s_stab)
        mu_stab_list.append(m_stab)
        dates.append(current_date)
        
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    ax1.plot(dates, sigma_stab_list, color='blue', lw=2)
    ax1.set_title(f"Dispersion Stability ($\sigma$-STAB): {feature_name} ({suffix})")
    ax1.set_ylabel("Index (1.0 = Ref)")
    ax1.axhline(LIMITS_SIGMA_STAB['target'], color='green', ls='-', alpha=0.5, label='Target')
    ax1.axhline(LIMITS_SIGMA_STAB['warn'], color='orange', ls='--', label='Warning')
    ax1.axhline(LIMITS_SIGMA_STAB['alarm'], color='red', ls='--', label='Alarm')
    ax1.fill_between(dates, 0, LIMITS_SIGMA_STAB['warn'], color='green', alpha=0.1)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    ax2.plot(dates, mu_stab_list, color='purple', lw=2)
    ax2.set_title(f"Location Stability ($\mu$-STAB): {feature_name} ({suffix})")
    ax2.set_ylabel("Index (near 0 = Stable)")
    ax2.axhline(LIMITS_MU_STAB['target'], color='green', ls='-', alpha=0.5)
    ax2.axhline(LIMITS_MU_STAB['warn'], color='orange', ls='--', label='Warning')
    ax2.axhline(LIMITS_MU_STAB['alarm'], color='red', ls='--', label='Alarm')
    ax2.fill_between(dates, 0, LIMITS_MU_STAB['warn'], color='green', alpha=0.1)
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    filename = os.path.join(save_folder, f"timeline_{feature_name}_{suffix}.png")
    plt.savefig(filename)
    plt.close()
    print(f"-> Timeline saved: {filename}")


def spc_analysis(master_cfg, global_settings):
    """
    Args:
        master_cfg: holds all configuration information to perform etl and analysis, as well as rendering of the
                    figures. -> maybe this can be a pointer to the db table later? CHECK !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        global_settings: folder and time intervals (things that dont change for different analysis)

    Returns: master_cfg, which all information added
    """
    pathname = master_cfg["pathname"]
    table = pd.read_table(pathname, delimiter='\t', encoding='cp1252', skiprows=4, skip_blank_lines=True)

    table.columns = [c.strip() for c in table.columns]
    table = table[["Strtterm.", "Meßwert", "StPrüfM", "Serialnr"]]
    table.columns = ["date", "value", "characteristic_id", "Serialnr"]

    table["value"] = pd.to_numeric(table["value"].astype(str).str.replace(",", ".").str.replace("E", "e"), errors="coerce")
    table['date'] = pd.to_datetime(table['date'], format='%d.%m.%Y')
    table.sort_values('date', inplace=True)
    table.dropna(subset=['value', 'date'], inplace=True)

    results_folder = global_settings["results_folder"]
    if not os.path.exists(results_folder):
        os.makedirs(results_folder)

    for number, config in master_cfg["inspection_characteristics"].items():
        print(f"\nProcessing {number}")

        reduced_table = copy(table[table["characteristic_id"] == number])
        reduced_table.reset_index(drop=True, inplace=True)

        if len(reduced_table) < 10:
            print("Skipping: Too few samples.")
            continue
            
        try:
            reduced_table, outliers, global_median = outlier_cleaning(reduced_table)
        except Exception:
            pass


        mask = reduced_table["date"] > pd.Timestamp("2024-01-01")
        if mask.any():
            reduced_table = reduced_table[mask].copy()
        
        last_date = reduced_table['date'].max()
        time_intervals = global_settings.get("time_intervals", (3, 12, 36))
        # Globale Sigma-Referenz: wird EINMAL aus ALLEN bereinigten Daten pro Merkmal ermittelt
        global_sigma_res = get_robust_sigma_and_mu(reduced_table['value'].values, fit_distribution=True)
        global_sigma_ref = global_sigma_res['sigma_equiv']

        for months in time_intervals:
            print(f"  > Analyse Zeitraum: Letzte {months} Monate")
            
            start_date = last_date - pd.DateOffset(months=months)
            
            mask = reduced_table["date"] >= start_date
            interval_data = reduced_table[mask].copy()
            
            if len(interval_data) < 10:
                print(f"    Zu wenig Daten für {months} Monate ({len(interval_data)}). Überspringe.")
                continue
            
            # ref_res = get_robust_sigma_and_mu(interval_data['value'].values, fit_distribution=True)
            # current_sigma_ref = ref_res['sigma_equiv']
            # print(f"    Sigma Ref (berechnet): {current_sigma_ref:.4f}")

            suffix = f"{months}M" # Dateiname Suffix

            plot_histogramm(
                df=interval_data, 
                feature_name=str(number), 
                hist_sigma_ref=global_sigma_ref, 
                save_folder=results_folder, 
                suffix=suffix,
                use_abs=False
            )
            
            plot_timeline_analysis(
                df=interval_data, 
                feature_name=str(number), 
                hist_sigma_ref=global_sigma_ref, 
                save_folder=results_folder,
                suffix=suffix,
                window_size=max(20, len(interval_data)//10),
                use_abs=False
            )

    return True

local_data_source = "/srv/spc_project/data/static/zt_qm2_exports/"
source_file = "zt_qm2_152159-1300"  # combine with cfg_154200
#source_file = "zt_qm2_154200"  # combine with cfg_154200
#source_file = "zt_qm2_154301"  # combine with cfg_154200

from dev.spc.static import cfg_kc_muimu, cfg_kc_lcr350b, cfg_kc_lcm300b

# material config
cfg = dict()
cfg["pathname"] = local_data_source + source_file + ".txt"  # shall be deleted for non static etl methods.
cfg["inspection_characteristics"] = cfg_kc_muimu.cfg_152159_1300  # here we find keys: Stammprüfmerkmalsnummer with values: analysis configuration as dict()
#cfg["inspection_characteristics"] = cfg_kc_lcr350b.cfg_154200  # here we find keys: Stammprüfmerkmalsnummer with values: analysis configuration as dict()
#cfg["inspection_characteristics"] = cfg_kc_lcm300b.cfg_154301  # here we find keys: Stammprüfmerkmalsnummer with values: analysis configuration as dict()

settings = dict()
settings["results_folder"] = "/home/strec84/shared-lib/results_histogram"
settings["time_intervals"] = (3, 12, 36)

spc_analysis(cfg, settings)
