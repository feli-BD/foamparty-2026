# convergence_study.py
import argparse
import os
import numpy as np
from matplotlib import pyplot as plt
import math
from pathlib import Path
import subprocess
import pandas as pd
import json
# Import your functions from the src package
from src.generate_constant import (
    create_momentum_transport_sa,
    generate_physical_properties,
    generate_0_directory
)

from src.mesh_solver import generate_naca4, curiosityFluidsAirfoilMesher

from src.control_dict import create_control_dict
# Note: You will also import your mesh_solver functions here (e.g., setup_and_run_case)

def main():
    # 1. Set up the command-line interface argument parser
    parser = argparse.ArgumentParser(
        description="Run a reproducible Mesh Convergence Study for a NACA Airfoil using OpenFOAM."
    )
    
    # 2. Define the customizable inputs with sensible defaults
    parser.add_argument("--airfoil", type=str, default="8412", 
                        help="4-digit NACA airfoil designation string (default: 8412)")
    parser.add_argument("--u_freestream", type=float, default=30.0, 
                        help="Freestream velocity U in m/s (default: 30.0)")
    parser.add_argument("--rho_freestream", type=float, default=1.225, 
                        help="Freestream density rho in kg/m³ (default: 1.225)")
    parser.add_argument("--nu", type=float, default=1.5e-5, 
                        help="Kinematic viscosity nu in m²/s (default: 1.5e-5)")
    parser.add_argument("--endtime", type=float, default=0.6, 
                        help="Simulation end time in seconds (default: 0.6)")
    parser.add_argument("--steady", action="store_true",
                        help="Run the simulation in steady-state mode (default: False)")
    parser.add_argument("--chord_length", type=float, default=1.0,
                        help="Chord length of the airfoil in meters (default: 1.0)")

    # 3. Parse the arguments provided by the user in the terminal
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
    
    case_name = "openfoam_naca"
    point_options = [10, 20, 40, 80, 160]
    results = []

    airfoil_code = args.airfoil
    chord_length = args.chord_length

    print(f"====================================================")
    print(f" Launching Mesh Convergence Study via CLI Context   ") 
    print(f" Target Profile: NACA {airfoil_code}")
    print(f" Velocity Field: {args.u_freestream} m/s")
    print(f"====================================================")

    # 4. Run the grid resolution convergence study loop
    for pts in point_options:
        print(f"\n[!] Evaluation Setup for Grid Size: {pts} Surface Points")
        
        # Structure the case directories cleanly inside the loop iteration
        os.makedirs(os.path.join(case_name, "system"), exist_ok=True)
        os.makedirs(os.path.join(case_name, "constant"), exist_ok=True)

        discretized_surface_points = generate_naca4(airfoil_code, chord=chord_length, points=pts)

        # ax = plt.subplots(1, 1, figsize=(10, 5))[1]

        # ax.plot(discretized_surface_points[:, 0], discretized_surface_points[:, 1], 'o-', label=f'NACA {airfoil_code}')
        # ax.set_aspect("equal")
        # plt.show()

        curiosityFluidsAirfoilMesher(discretized_surface_points)

        create_control_dict(case_name, rho_inf=args.rho_freestream, u_inf=args.u_freestream)

        subprocess.run(foam_cmd("blockMesh", "-case", case_name))
        #checkMesh
        subprocess.run(foam_cmd("checkMesh", "-case", case_name))
        
        # Call your generative source functions dynamically utilizing the parsed inputs!
        create_momentum_transport_sa(case_name)
        generate_physical_properties(case_name, nu_value=args.nu)
        generate_0_directory(case_name, u_freestream=args.u_freestream, rho_freestream=args.rho_freestream, nu=args.nu)
        
        # --- Run Solver & Collect Outputs ---
        # Here you would call your blockMesh / checkMesh / foamRun execution engine 
        # success, cd, cl = run_openfoam_solver_pipeline(case_name, points=pts, end_time=args.endtime)
        subprocess.run(foam_cmd("foamRun", "-case", case_name))

        forcecoeffs_file = f"{case_name}/postProcessing/computeLiftDrag/0/forceCoeffs.dat"
        df = pd.read_csv(forcecoeffs_file, sep=r'\s+', comment='#', header=None)

        n = len(df)
        tail = df.iloc[int(n * 0.8):]
        time = tail[0].mean()
        cd = tail[2].mean()
        cl = tail[3].mean()
        results.append({'points': pts, 'Cd': cd, 'Cl': cl, 'Time': time})
        results_path = "convergence_results.json"
        with open(results_path, "w") as f:
            json.dump({"airfoil": airfoil_code, "results": results}, f, indent=2)
        print(f"\n[+] Raw results saved to {results_path}")


    if results:
        plt.close('all')
        results_sorted = sorted(results, key=lambda r: r['points'])
        pts_axis = np.array([r['points'] for r in results_sorted])

        cl_ref = results_sorted[-1]['Cl']
        cd_ref = results_sorted[-1]['Cd']

        cl_err = np.array([abs(r['Cl'] - cl_ref) / abs(cl_ref) for r in results_sorted[:-1]])
        cd_err = np.array([abs(r['Cd'] - cd_ref) / abs(cd_ref) for r in results_sorted[:-1]])
        pts_err_axis = pts_axis[:-1]  

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.loglog(pts_err_axis, cl_err, 'o-', label='Cl relative error')
        ax.loglog(pts_err_axis, cd_err, 's-', label='Cd relative error')

        ax.set_xlabel('Number of Surface Discretization Points')
        ax.set_ylabel('Relative Error vs. Finest Mesh')
        ax.set_title(f'Grid Convergence Study — NACA {airfoil_code}')
        ax.grid(True, which='both', linestyle='--', alpha=0.5)
        ax.legend()

        fig.tight_layout()
        plot_path = "convergence_error_plot.png"
        plt.savefig(plot_path)
        print(f"[+] Convergence error plot saved to {plot_path}")
        plt.show()
    else:
        print("\n[-] Error: No data points were calculated successfully. Plot skipped.")
            

if __name__ == "__main__":
    main()