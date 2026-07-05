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

from src.generate_openfoam_fv import generate_openfoam_fvschemes_fvsolution

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
    parser.add_argument("--time_study_endtime", type=float, default=2.0,
                        help="Generous end time for the Part 2 run; the full history is ")
    parser.add_argument("--time_study", type=bool, default=True,
                        help="Whether to run the time convergence study (default: True)")
    parser.add_argument("--skip_mesh_study", action="store_true",
                        help="Skip Part 1 (mesh convergence study) and use --time_study_points directly (default: False)")
    parser.add_argument("--time_study_points", type=int, default=None,
                        help="Number of surface discretization points to use for the time convergence study (default: None, which uses the finest successful mesh from Part 1)")

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
    
   
    point_options = [20,40,80, 160,320,640, 1280]
    results = []

    airfoil_code = args.airfoil
    chord_length = args.chord_length

    print(f"====================================================")
    print(f" Launching Mesh Convergence Study") 
    print(f" Target Profile: NACA {airfoil_code}")
    print(f" Velocity Field: {args.u_freestream} m/s")
    print(f"====================================================")

    # 4. Run the grid resolution convergence study loop
    if not args.skip_mesh_study:
        for pts in point_options:
            print(f"\n[!] Evaluation Setup for Grid Size: {pts} Surface Points")

            case_name = f"openfoam_naca_{pts}pts"
            
            # Structure the case directories cleanly inside the loop iteration
            os.makedirs(os.path.join(case_name, "system"), exist_ok=True)
            os.makedirs(os.path.join(case_name, "constant"), exist_ok=True)

            discretized_surface_points = generate_naca4(airfoil_code, chord=chord_length, points=pts)

            curiosityFluidsAirfoilMesher(discretized_surface_points, path_to_blockdict=f"{case_name}/system/blockMeshDict")

            create_control_dict(case_name, end_time=args.endtime, rho_inf=args.rho_freestream, u_inf=args.u_freestream)
            generate_openfoam_fvschemes_fvsolution(case_name, steady_state=args.steady)

            result = subprocess.run(foam_cmd("blockMesh", "-case", case_name))
            if result.returncode != 0:
                print(f"[-] blockMesh failed for case {case_name} -- skipping this resolution")
                continue
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
            results_path = "results/convergence_results.json"
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
            plot_path = "results/plots/convergence_error_plot.png"
            plt.savefig(plot_path)
            print(f"[+] Convergence error plot saved to {plot_path}")
            plt.show()
        else:
            print("\n[-] Error: No data points were calculated successfully. Plot skipped.")
    else:
        print("\n[!] Skipping Part 1 (mesh convergence study) -- using --time_study_points directly")
    

    ################################################################
    #
    #       Part 2: Verification of simulation time for lift 
    #         and drag coefficients and residual convergence
    # 
    ###############################################################

    # Pick which surface-point resolution to use for the time study:
    # default to the finest resolution that produced results in Part 1
    if results:
        finest_success_pts = max(r['points'] for r in results)
    else:
        finest_success_pts = point_options[-1]

    time_study_points = args.time_study_points if args.time_study_points else finest_success_pts
 
    print("\n====================================================")
    print(" Part 2: Time / Residual Convergence Study           ")
    print(f" Using {time_study_points} surface points (from Part 1)")
    print(f" End time requested: {args.time_study_endtime} s")
    print("====================================================")
 
    time_case_name = f"openfoam_naca_timeconv_{time_study_points}pts"
    os.makedirs(os.path.join(time_case_name, "system"), exist_ok=True)
    os.makedirs(os.path.join(time_case_name, "constant"), exist_ok=True)
 
    time_discretized_surface_points = generate_naca4(
        airfoil_code, chord=chord_length, points=time_study_points
    )
    curiosityFluidsAirfoilMesher(time_discretized_surface_points, path_to_blockdict=f"{time_case_name}/system/blockMeshDict")
 
    create_control_dict( time_case_name, end_time=args.time_study_endtime,rho_inf=args.rho_freestream,u_inf=args.u_freestream)
    generate_openfoam_fvschemes_fvsolution(time_case_name, steady_state=args.steady)
 
    subprocess.run(foam_cmd("blockMesh", "-case", time_case_name))
    subprocess.run(foam_cmd("checkMesh", "-case", time_case_name))
 
    create_momentum_transport_sa(time_case_name)
    generate_physical_properties(time_case_name, nu_value=args.nu)
    generate_0_directory(time_case_name, u_freestream=args.u_freestream, rho_freestream=args.rho_freestream, nu=args.nu)
 
    subprocess.run(foam_cmd("foamRun", "-case", time_case_name))
 
   # --- Read the full forceCoeffs time history (not just the tail average) ---
    forcecoeffs_file = f"{time_case_name}/postProcessing/computeLiftDrag/0/forceCoeffs.dat"
    coeffs = pd.read_csv(forcecoeffs_file, sep=r'\s+', comment='#', header=None)
 
    # --- Read the residuals time history ---
    # Requires a `residuals` functionObject in controlDict, e.g.:
    #   residuals { type residuals; libs (fieldFunctionObjects);
    #               fields (U p nuTilda); executeControl timeStep;
    #               executeInterval 1; writeControl timeStep; writeInterval 1; }
    residuals_file = f"{time_case_name}/postProcessing/residuals/0/residuals.dat"
    residuals = pd.read_csv(residuals_file, sep=r'\s+', comment='#', header=None)
 
    if coeffs is None or coeffs.empty:
        print("[-] Missing forceCoeffs output -- check functionObject config, skipping Part 2 plot")
    else:
        time_col = 0
        cd_col = 2
        cl_col = 3
 
        time_arr = np.asarray(coeffs[time_col], dtype=float)
        cd_arr = np.asarray(coeffs[cd_col], dtype=float)
        cl_arr = np.asarray(coeffs[cl_col], dtype=float)
 
        rel_tol = 1e-3
        window_frac = 0.1
 
        # --- Find the time after which Cd stays within rel_tol of its final value ---
        cd_conv_t = None
        if len(cd_arr) > 0 and cd_arr[-1] != 0:
            final_cd = cd_arr[-1]
            window = max(int(len(cd_arr) * window_frac), 5)
            if window < len(cd_arr):
                for i in range(len(cd_arr) - window):
                    segment = cd_arr[i:]
                    if np.all(np.abs(segment - final_cd) / abs(final_cd) < rel_tol):
                        cd_conv_t = float(time_arr[i])
                        break
 
        # --- Find the time after which Cl stays within rel_tol of its final value ---
        cl_conv_t = None
        if len(cl_arr) > 0 and cl_arr[-1] != 0:
            final_cl = cl_arr[-1]
            window = max(int(len(cl_arr) * window_frac), 5)
            if window < len(cl_arr):
                for i in range(len(cl_arr) - window):
                    segment = cl_arr[i:]
                    if np.all(np.abs(segment - final_cl) / abs(final_cl) < rel_tol):
                        cl_conv_t = float(time_arr[i])
                        break
 
        # --- Persist the raw time-series so this can be replotted without rerunning ---
        time_results_path = "results/time_convergence_results.json"
        time_payload = {
            "airfoil": airfoil_code,
            "points": time_study_points,
            "time": time_arr.tolist(),
            "cd": cd_arr.tolist(),
            "cl": cl_arr.tolist(),
            "cd_convergence_time": cd_conv_t,
            "cl_convergence_time": cl_conv_t,
        }
        if residuals is not None and not residuals.empty:
            time_payload["residual_time"] = residuals[0].tolist()
            time_payload["residual_fields"] = {
                "Ux": residuals[1].tolist(),
                "Uy": residuals[2].tolist(),
                "p": residuals[3].tolist(),
            }
        with open(time_results_path, "w") as f:
            json.dump(time_payload, f, indent=2)
        print(f"[+] Raw time-convergence results saved to {time_results_path}")
 
        # --- Plot Cl/Cd vs time (top) and residuals vs time (bottom) ---
        plt.close('all')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
 
        ax1.plot(time_payload["time"], time_payload["cd"], label="Cd", color="red")
        ax1.plot(time_payload["time"], time_payload["cl"], label="Cl", color="blue")
        ax1.set_ylabel("Force Coefficient")
        ax1.set_title(f"Cl / Cd vs. Simulation Time — NACA {airfoil_code}, {time_study_points} pts")
        ax1.legend()
        ax1.grid(True, alpha=0.4)
 
        for t, label, color in [(cd_conv_t, "Cd converged", "red"), (cl_conv_t, "Cl converged", "blue")]:
            if t is not None:
                ax1.axvline(t, linestyle="--", color=color, alpha=0.6)
                ax1.text(t, ax1.get_ylim()[1] * 0.95, f" {label}\n t={t:.3f}s", color=color, fontsize=8)
 
        if "residual_fields" in time_payload:
            for col, values in time_payload["residual_fields"].items():
                ax2.semilogy(time_payload["residual_time"], values, label=col)
            ax2.axhline(1e-4, linestyle=":", color="gray", label="1e-4 threshold")
            ax2.legend(fontsize=8)
        else:
            ax2.text(0.5, 0.5, "No residuals functionObject data available",
                     ha="center", va="center", transform=ax2.transAxes)
 
        x_label = "Iteration" if args.steady else "Time (s)"
        ax2.set_xlabel(x_label)
        ax2.set_ylabel("Residual (log scale)")
        ax2.grid(True, which="both", alpha=0.4)
 
        fig.tight_layout()
        time_plot_path = "results/plots/time_convergence_study.png"
        fig.savefig(time_plot_path)
        print(f"[+] Time convergence plot saved to {time_plot_path}")
        plt.show()
 
        print("\n--- Convergence Summary ---")
        print(f"Cd stabilizes at t ≈ {cd_conv_t}")
        print(f"Cl stabilizes at t ≈ {cl_conv_t}")
        recommended = max(cd_conv_t or time_payload['time'][-1], cl_conv_t or time_payload['time'][-1])
        print(f"Recommended --endtime: {recommended:.3f}s (add margin for residual decay -- "
              f"check the residuals subplot)")



if __name__ == "__main__":
    main()