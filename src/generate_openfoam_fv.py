import os

def generate_openfoam_fvschemes_fvsolution(case_dir, steady_state=True):
    """
    Generates fvSchemes and fvSolution files tailored for OpenFOAM 13's
    modular framework (incompressibleFluid) with the Spalart-Allmaras model.
    """
    system_dir = os.path.join(case_dir, "system")
    
    # Determine schemes based on time-dependence
    ddt_scheme = "steadyState" if steady_state else "Euler"
    
    # -------------------------------------------------------------
    # 1. Define fvSchemes Content
    # -------------------------------------------------------------
    fv_schemes = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  13
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{{
    default         {ddt_scheme};
}}

gradSchemes
{{
    default         Gauss linear;
    grad(U)         Gauss linear;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linearUpwind grad(U);
    div(phi,nuTilda) Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

wallDist
{{
    method          meshWave;
}}

// ************************************************************************* //
"""

    # -------------------------------------------------------------
    # 2. Define fvSolution Content
    # -------------------------------------------------------------
    n_outer_correctors = 1 if steady_state else 2
    
    # Relaxation factors are critical for numerical stability in steady-state runs
    relaxation_factors = """relaxationFactors
{
    fields
    {
        p               0.3;
    }
    equations
    {
        U               0.7;
        nuTilda         0.7;
    }
}""" if steady_state else ""

    fv_solution = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  13
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSolution;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{{
    p
    {{
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
    }}

    pFinal
    {{
        $p;
        tolerance       1e-06;
        relTol          0;
    }}

    "(U|nuTilda)"
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-05;
        relTol          0.1;
    }}

    "(U|nuTilda)Final"
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-05;
        relTol          0;
    }}
}}

PIMPLE
{{
    nOuterCorrectors {n_outer_correctors};
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
}}

{relaxation_factors}

// ************************************************************************* //
"""

    # Write files out to the system folder
    with open(os.path.join(system_dir, "fvSchemes"), "w") as f:
        f.write(fv_schemes)

    with open(os.path.join(system_dir, "fvSolution"), "w") as f:
        f.write(fv_solution)