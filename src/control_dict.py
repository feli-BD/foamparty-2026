# first we need to create the controlDict file

import os

def create_control_dict(case_dir, end_time=0.6, u_inf=30, rho_inf=1.225, z_length=1.0, write_interval=0.05):
    # end_time: for how long the simulation runs
    # u_inf: free-stream velocity
    # rho_inf: free-stream density
    # z_length: extrusion in z-direction
    # these are used to compute lift and drag coefficients

    system_dir = os.path.join(case_dir, "system")
    os.makedirs(system_dir, exist_ok=True)
    area = 1.0 * z_length
    
    # Note: Double curly braces {{ }} are used to escape them in the Python f-string
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
    location    "system";
    object      controlDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     foamRun;
solver          incompressibleFluid;

startFrom       startTime;
startTime       0;

stopAt          endTime;
endTime         {end_time};

deltaT          0.0005; // Set conservative for initialization stability

writeControl    runTime;
writeInterval   {write_interval};

purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{{
    computeLiftDrag
    {{
        type            forceCoeffs;       // Must be an unquoted word
        libs            ("libforces.so");  // Shared libraries CAN be a string list
        writeControl    timeStep;
        writeInterval   1;

        patches         (airfoil);         // Name of your boundary patch in patches/polyMesh
        p               p;                 // Pressure field name
        U               U;                 // Velocity field name
        
        // For incompressible flows (using foamRun with incompressibleFluid module)
        rho             rhoInf;            
        rhoInf          {rho_inf}; // reference density
        
        CofR            (0 0 0);           // Center of Rotation (for moment coefficients)
        
        // Direction vectors (Adjust these based on your coordinate system orientation!)
        liftDir         (0 1 0);           // If lift is pointing up the Y-axis
        dragDir         (1 0 0);           // If drag is pointing along the X-axis
        pitchAxis       (0 0 1);           // Pitch axis (Z-axis)
        
        // Reference values used to normalize forces into Cd and Cl
        magUInf         {u_inf};          // Freestream velocity magnitude
        lRef            1.0;               // Reference length (e.g., chord length of airfoil in meters)
        Aref            {area};            // Planform Area (Chord 1.0m * Span 0.1m)
    }}

    residuals
    {{
        type            residuals;
        libs            ("libutilityFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   1;
        fields          (U p);
    }}
}}

// ************************************************************************* //
"""
    
    dict_path = os.path.join(system_dir, "controlDict")
    with open(dict_path, "w") as f:
        f.write(content)
        
    return dict_path