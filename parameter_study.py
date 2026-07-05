# parameter_study.py
import argparse
import os
import shutil
import numpy as np
from matplotlib import pyplot as plt
from pathlib import Path
import subprocess
import pandas as pd
import json
import time

from src.generate_constant import (
    create_momentum_transport_sa,
    generate_physical_properties,
    generate_0_directory
)
from src.mesh_solver import generate_naca4, curiosityFluidsAirfoilMesher
from src.control_dict import create_control_dict
from src.generate_openfoam_fv  import generate_openfoam_fvschemes_fvsolution

def main():
    parser = argparse.ArgumentParser(
        description="Parameter study: effect of NACA camber (M) on Cl and Cd, "
                     "using a fixed, previously-validated mesh resolution and end time."
    )

    parser.add_argument("--points", type=int, default=320,
                        help="Surface discretization points (from the mesh convergence "
                             "study) to use for every camber case (default: 160)")
    parser.add_argument("--endtime", type=float, default=0.4,
                        help="Simulation end time in seconds -- IMPORTANT: set this to "
                             "the value validated by the time-convergence study, not the "
                             "default (default: 0.6)")
    parser.add_argument("--camber_position", type=int, default=4,
                        help="NACA 'P' digit: position of max camber in tenths of chord, "
                             "held fixed across the sweep (default: 4)")
    parser.add_argument("--thickness", type=int, default=12,
                        help="NACA thickness (last two digits), held fixed across the "
                             "sweep (default: 12)")
    parser.add_argument("--camber_min", type=int, default=0,
                        help="Minimum camber M (default: 0)")
    parser.add_argument("--camber_max", type=int, default=8,
                        help="Maximum camber M, inclusive (default: 8)")
    parser.add_argument("--camber_step", type=int, default=1,
                        help="Step size for camber M sweep (default: 1)")
    parser.add_argument("--u_freestream", type=float, default=30.0,
                        help="Freestream velocity U in m/s (default: 30.0)")
    parser.add_argument("--rho_freestream", type=float, default=1.225,
                        help="Freestream density rho in kg/m^3 (default: 1.225)")
    parser.add_argument("--nu", type=float, default=1.5e-5,
                        help="Kinematic viscosity nu in m^2/s (default: 1.5e-5)")
    parser.add_argument("--steady", action="store_true",
                        help="Run in steady-state mode (default: False)")
    parser.add_argument("--chord_length", type=float, default=1.0,
                        help="Chord length of the airfoil in meters (default: 1.0)")

    args = parser.parse_args()

    OPENFOAM_IMAGE = "microfluidica/openfoam:13"
    PROJECT_DIR = Path.cwd().resolve()

    def foam_cmd(*args, workdir="/work"):
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{PROJECT_DIR}:/work",
            "-w",
            workdir,
            OPENFOAM_IMAGE,
            *args,
        ]

    camber_values = list(range(args.camber_min, args.camber_max + 1, args.camber_step))
    results = []

    results_path = "parameter_study_results.json"

    # Resume from a previous run if results already exist
    results = []
    already_done = set()
    if os.path.exists(results_path):
        with open(results_path) as f:
            existing = json.load(f)
        results = existing.get("results", [])
        already_done = {r['m'] for r in results}
        if already_done:
            print(f"[+] Resuming: found existing results for M = {sorted(already_done)}")

    print("====================================================")
    print(" Parameter Study: Effect of Camber (M) on Cl and Cd ")
    print(f" Fixed: P={args.camber_position}, T={args.thickness}, "
          f"{args.points} pts, endtime={args.endtime}s")
    print(f" Sweeping M = {camber_values}")
    print("====================================================")

    for m in camber_values:
        if m in already_done:
            print(f"\n[!] M={m} already computed, skipping")
            continue

        airfoil_code = f"{m}{args.camber_position}{args.thickness:02d}"
        print(f"\n[!] Evaluation Setup for Camber M={m} -- NACA {airfoil_code}")

        case_name = f"openfoam_naca_camber_{airfoil_code}"

        # Start every case completely fresh -- avoids resuming from a stale
        # time directory left over from a previous run of the same case name
        if os.path.exists(case_name):
            for attempt in range(5):
                try:
                    shutil.rmtree(case_name)
                    break
                except PermissionError:
                    print(f"[!] {case_name} locked, retrying in 2s (attempt {attempt+1}/5)")
                    time.sleep(2)
            else:
                print(f"[-] Could not remove {case_name} after retries, skipping M={m}")
                continue

        os.makedirs(os.path.join(case_name, "system"), exist_ok=True)
        os.makedirs(os.path.join(case_name, "constant"), exist_ok=True)

        discretized_surface_points = generate_naca4(
            airfoil_code, chord=args.chord_length, points=args.points
        )
        curiosityFluidsAirfoilMesher(
            discretized_surface_points,
            path_to_blockdict=f"{case_name}/system/blockMeshDict"
        )

        create_control_dict(
            case_name,
            rho_inf=args.rho_freestream,
            u_inf=args.u_freestream,
            end_time=args.endtime,
        )
        generate_openfoam_fvschemes_fvsolution(case_name, steady_state=args.steady)

        result_bm = subprocess.run(foam_cmd("blockMesh", "-case", case_name))
        if result_bm.returncode != 0:
            print(f"[-] blockMesh failed for NACA {airfoil_code}, skipping")
            continue

        result_cm = subprocess.run(foam_cmd("checkMesh", "-case", case_name))
        if result_cm.returncode != 0:
            print(f"[-] checkMesh failed for NACA {airfoil_code}, skipping")
            continue

        create_momentum_transport_sa(case_name)
        generate_physical_properties(case_name, nu_value=args.nu)
        generate_0_directory(
            case_name,
            u_freestream=args.u_freestream,
            rho_freestream=args.rho_freestream,
            nu=args.nu,
        )

        result_run = subprocess.run(foam_cmd("foamRun", "-case", case_name))
        if result_run.returncode != 0:
            print(f"[-] foamRun failed for NACA {airfoil_code}, skipping")
            continue

        forcecoeffs_file = f"{case_name}/postProcessing/computeLiftDrag/0/forceCoeffs.dat"
        if not os.path.exists(forcecoeffs_file):
            print(f"[-] No forceCoeffs.dat found for NACA {airfoil_code}, skipping")
            continue

        df = pd.read_csv(forcecoeffs_file, sep=r'\s+', comment='#', header=None)
        if df.empty:
            print(f"[-] forceCoeffs.dat is empty for NACA {airfoil_code}, skipping")
            continue

        # Average over the last 20% of timesteps -- assumes --endtime is long
        # enough for Cl/Cd to have actually flattened out (validated separately
        # by the time-convergence study, not by this script)
        n = len(df)
        tail = df.iloc[int(n * 0.8):]
        cd = tail[2].mean()
        cl = tail[3].mean()
        results.append({'m': m, 'airfoil': airfoil_code, 'Cd': cd, 'Cl': cl})
        print(f"    -> Cd={cd:.5f}, Cl={cl:.5f}")

        results_path = "results/parameter_study_results.json"
        with open(results_path, "w") as f:
            json.dump({
                "camber_position": args.camber_position,
                "thickness": args.thickness,
                "points": args.points,
                "endtime": args.endtime,
                "results": results,
            }, f, indent=2)
        print(f"[+] Raw results saved to {results_path}")

    if results:
        plt.close('all')
        results_sorted = sorted(results, key=lambda r: r['m'])
        m_axis = np.array([r['m'] for r in results_sorted])
        cl_axis = np.array([r['Cl'] for r in results_sorted])
        cd_axis = np.array([r['Cd'] for r in results_sorted])

        fig, ax1 = plt.subplots(figsize=(9, 6))

        ax1.set_xlabel('Camber M (% chord)')
        ax1.set_ylabel('Lift Coefficient (Cl)', color='blue')
        ax1.plot(m_axis, cl_axis, 'o-', color='blue', linewidth=2, label='Cl')
        ax1.tick_params(axis='y', labelcolor='blue')
        ax1.grid(True, linestyle='--', alpha=0.5)

        ax2 = ax1.twinx()
        ax2.set_ylabel('Drag Coefficient (Cd)', color='red')
        ax2.plot(m_axis, cd_axis, 's-', color='red', linewidth=2, label='Cd')
        ax2.tick_params(axis='y', labelcolor='red')

        plt.title(f"Effect of Camber on Cl and Cd -- NACA X{args.camber_position}"
                  f"{args.thickness:02d}, {args.points} pts, endtime={args.endtime}s")
        fig.tight_layout()

        plot_path = "results/plots/camber_parameter_study_plot_steady.png"
        plt.savefig(plot_path)
        print(f"\n[+] Camber parameter study plot saved to {plot_path}")
        plt.show()
    else:
        print("\n[-] Error: No data points were calculated successfully. Plot skipped.")

    print("\n[+] Parameter study finished.")

if __name__ == "__main__":
    main()