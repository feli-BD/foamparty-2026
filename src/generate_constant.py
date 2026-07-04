import os

def create_momentum_transport_sa(case_dir):
    constant_dir = os.path.join(case_dir, "constant")
    os.makedirs(constant_dir, exist_ok=True)
    
    # Using double curly braces {{ }} to escape them inside the Python f-string
    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  13
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
    location    "constant";
    object      momentumTransport;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

simulationType  RAS;

RAS
{{
    model           SpalartAllmaras;
    turbulence      on;
    printCoeffs     on;
}}

// ************************************************************************* //
"""
    
    dict_path = os.path.join(constant_dir, "momentumTransport")
    with open(dict_path, "w") as f:
        f.write(content)
        
    return dict_path

def generate_physical_properties(case_dir, nu_value=1.5e-5):
    """
    Generates a physicalProperties file for incompressible flow.
    """
    constant_dir = os.path.join(case_dir, "constant")
    
    file_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:      https://openfoam.org
    \\\\  /    A nd           | Version:      13
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
    location    "constant";
    object      physicalProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

viscosityModel  constant;

nu              [0 2 -1 0 0 0 0] {nu_value};

// ************************************************************************* //
"""
    
    file_path = os.path.join(constant_dir, "physicalProperties")
    with open(file_path, "w") as f:
        f.write(file_content)

def generate_0_directory(case_dir, u_freestream, rho_freestream, nu=1.5e-5):
    """
    Generates initial and boundary condition field files in the 0/ directory 
    for an OpenFOAM 13 incompressible Spalart-Allmaras airfoil simulation.
    """
    zero_dir = os.path.join(case_dir, "0")
    os.makedirs(zero_dir, exist_ok=True)
    
    # --- Turbulence Math for Spalart-Allmaras Freestream values ---
    # Standard guideline: nuTilda_freestream is 3 to 5 times kinematic viscosity
    nu_tilda_freestream = 3.0 * nu
    
    # Calculate initial nut from nuTilda using the SA model formulation
    cv1 = 7.1
    chi = nu_tilda_freestream / nu
    fv1 = (chi**3) / (chi**3 + cv1**3)
    nut_freestream = nu_tilda_freestream * fv1
    
    print(f"[+] Physical Constants & Computed Freestream Targets:")
    print(f"    - Inflow Velocity: {u_freestream} m/s")
    print(f"    - Freestream Density: {rho_freestream} kg/m³ (Used for reference/forces)")
    print(f"    - Kinematic Viscosity (nu): {nu} m²/s")
    print(f"    - Freestream nuTilda: {nu_tilda_freestream:.2e} m²/s")
    print(f"    - Freestream nut: {nut_freestream:.2e} m²/s\n")

    # -------------------------------------------------------------
    # 1. Field: U (Velocity Field)
    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # Velocity (U)
    # -------------------------------------------------------------
    u_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    class       volVectorField;
    location    "0";
    object      U;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform ({u_freestream} 0 0);

boundaryField
{{
    farfield
    {{
        type            freestream;
        freestreamValue uniform ({u_freestream} 0 0);
    }}

    airfoil
    {{
        type            noSlip;
    }}

    frontAndBack
    {{
        type            empty;
    }}
}}

// ************************************************************************* //
"""

    # -------------------------------------------------------------
    # Kinematic Pressure (p = P_physical / rho)
    # -------------------------------------------------------------
    p_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    class       volScalarField;
    location    "0";
    object      p;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    farfield
    {{
        type            freestreamPressure;
        freestreamValue uniform 0;
    }}

    airfoil
    {{
        type            zeroGradient;
    }}

    frontAndBack
    {{
        type            empty;
    }}
}}

// ************************************************************************* //
"""

    # -------------------------------------------------------------
    # Modified Turbulent Viscosity (nuTilda)
    # -------------------------------------------------------------
    nutilda_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    class       volScalarField;
    location    "0";
    object      nuTilda;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 2 -1 0 0 0 0];

internalField   uniform {nu_tilda_freestream};

boundaryField
{{
    farfield
    {{
        type            freestream;
        freestreamValue uniform {nu_tilda_freestream};
    }}

    airfoil
    {{
        type            fixedValue;
        value           uniform 0;
    }}

    frontAndBack
    {{
        type            empty;
    }}
}}

// ************************************************************************* //
"""

    # -------------------------------------------------------------
    # Turbulent Kinematic Viscosity (nut)
    # -------------------------------------------------------------
    nut_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    class       volScalarField;
    location    "0";
    object      nut;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 2 -1 0 0 0 0];

internalField   uniform {nut_freestream};

boundaryField
{{
    farfield
    {{
        type            calculated;
        value           uniform {nut_freestream};
    }}

    airfoil
    {{
        type            nutUSpaldingWallFunction;
        value           uniform 0;
    }}

    frontAndBack
    {{
        type            empty;
    }}
}}

// ************************************************************************* //
"""

    # Write files to disk
    fields = {"U": u_content, "p": p_content, "nuTilda": nutilda_content, "nut": nut_content}
    for field_name, script_content in fields.items():
        file_path = os.path.join(zero_dir, field_name)
        with open(file_path, "w") as f:
            f.write(script_content)

# generate_0_directory("openfoam_naca", u_freestream, rho_freestream)