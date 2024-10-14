# GHOST - Generator of High Optimized Simulation Templates

## Overview

**GHOST** (Generator of High Optimized Simulation Templates) is a plugin for the [3D Slicer](https://www.slicer.org/) platform designed to facilitate the creation of voxelized phantoms for Monte Carlo N-Particle (MCNP) simulations. The plugin allows users to convert segmented 3D images into lattice structures compatible with the MCNP code, automatically handling the conversion and generating the necessary input files (`GHOST`) for MCNP simulations.

## Features

- **Voxelized Phantom Creation**: Convert segmented 3D images into MCNP-compatible lattice structures.
- **Customizable Voxel Size**: Specify voxel dimensions to adjust the resolution of the phantom while maintaining the total dimensions of the original image.
- **Material Assignment**: Automatically assigns materials to different segments based on a user-provided materials database.
- **Output to MCNP Format**: Generates the complete basic MCNP input file with correctly formatted lattice structures, material definitions, and other essential cards.

## Installation

To install the GHOST plugin, follow these steps:

1. **Download the Plugin**: Clone the repository from GitHub.

   ```
   git clone https://github.com/HarlleyHauradou/SlicerGHOST.git
   ```

2. **Add the Plugin to 3D Slicer**:

   - Open 3D Slicer.
   - Go to `Edit` -> `Application Settings` -> `Modules`.
   - Add the path to the `GHOST` directory in the `Additional module paths` field.
   - Restart 3D Slicer.

3. **Verify Installation**:

   - After restarting 3D Slicer, the `GHOST` module should appear in the `Modules` drop-down list under the `Monte Carlo` category.

## Usage

1. **Load the Image**:
   - Load your DICOM, NIfTI, MHD or other supported image format into 3D Slicer.
2. **Segment the Image**:
   - Use the `Segment Editor` module to create segmentations for different tissues or materials.
3. **Set Voxel Size**:
   - In the GHOST plugin UI, enter the desired voxel size in the `Spacing for x, y and z in cm for voxel` fields.
4. **Generate MCNP Input File**:
   - Click the `Generate` button to create the MCNP input file (`GHOST`).
   - The generated file will be saved in the directory you specify.
5. **Review and Edit**:
   - Optionally, review the generated `GHOST` file and make any necessary manual adjustments.

## Materials Database

The plugin relies on a materials database (`materials.txt`) to assign proper MCNP material cards to different segments. The database should be located in the `Resources/database` folder within the plugin directory. Each material entry in the database follows this format:

```
c Material Name Density (g/cm3) = density_value
mx         Element1  Fraction1
           Element2  Fraction2
           ...
```

The plugin automatically replaces the placeholder `x` with the appropriate material ID for MCNP.

## Contributions

Contributions are welcome! If you have any suggestions, find a bug, or want to add new features, feel free to fork the repository and submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For any inquiries or issues, please contact Harlley Haurado.