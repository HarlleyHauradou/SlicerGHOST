import os
import re
import qt
import slicer
import vtk
import numpy as np
from slicer.ScriptedLoadableModule import *

class GHOSTImporter(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "GHOST Import"
        parent.categories = ["Monte Carlo"]
        parent.dependencies = []
        parent.contributors = ["Harlley Hauradou, Paula Selvatice, Mirta Berdeguez e Ademir da Silva"]
        parent.helpText = """This plugin imports an MCNP Phantom (Lattice or CSG Geometric) into a 3D volume in Slicer."""
        parent.acknowledgementText = """"""

class GHOSTImporterWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        uiWidget = slicer.util.loadUI(self.resourcePath('UI/GHOSTImporter.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Connect signals
        self.ui.inputPathLineEdit.connect('currentPathChanged(QString)', self.onInputFileChanged)
        self.ui.importButton.connect('clicked(bool)', self.onImportButtonClicked)
        
        # Hide CSG settings by default until a CSG phantom is loaded
        self.ui.csgCollapsibleButton.collapsed = True
        self.ui.csgCollapsibleButton.visible = False

        self.mcnp_parser = MCNPParser()
        self.current_phantom_info = None

    def resourcePath(self, filename):
        return os.path.join(os.path.dirname(__file__), 'Resources', filename)

    def onInputFileChanged(self, file_path):
        if not file_path or not os.path.exists(file_path):
            self.ui.importButton.enabled = False
            self.resetPreview()
            return
            
        try:
            self.current_phantom_info = self.mcnp_parser.analyzeFile(file_path)
            self.updatePreview()
            self.ui.importButton.enabled = True
        except Exception as e:
            slicer.util.errorDisplay(f"Error analyzing file: {str(e)}")
            self.ui.importButton.enabled = False
            self.resetPreview()

    def resetPreview(self):
        self.ui.typeLabel.text = "Type: -"
        self.ui.dimensionLabel.text = "Dimensions: -"
        self.ui.spacingLabel.text = "Spacing: -"
        self.ui.csgCollapsibleButton.visible = False
        self.current_phantom_info = None

    def updatePreview(self):
        info = self.current_phantom_info
        if not info:
            return
            
        is_lattice = info.get('is_lattice', False)
        phantom_type = "Lattice" if is_lattice else "Geometric (CSG)"
        
        self.ui.typeLabel.text = f"Type: {phantom_type}"
        
        if is_lattice:
            dims = info.get('dimensions', (0,0,0))
            spacing = info.get('spacing', (0,0,0))
            self.ui.dimensionLabel.text = f"Dimensions: {dims[0]}x{dims[1]}x{dims[2]} voxels"
            self.ui.spacingLabel.text = f"Spacing: {spacing[0]:.3f} x {spacing[1]:.3f} x {spacing[2]:.3f} cm"
            self.ui.csgCollapsibleButton.visible = False
        else:
            self.ui.dimensionLabel.text = "Dimensions: (Determined by bounding box)"
            self.ui.spacingLabel.text = "Spacing: (Define below)"
            self.ui.csgCollapsibleButton.visible = True
            self.ui.csgCollapsibleButton.collapsed = False

    def onImportButtonClicked(self):
        if not self.current_phantom_info:
            return
            
        file_path = self.ui.inputPathLineEdit.currentPath
        
        # Show progress dialog
        progress = qt.QProgressDialog("Importing Phantom...", "Cancel", 0, 100, slicer.util.mainWindow())
        progress.setWindowModality(qt.Qt.WindowModal)
        progress.minimumDuration = 0
        progress.show()
        slicer.app.processEvents()
        
        try:
            if self.current_phantom_info.get('is_lattice'):
                self.importLatticePhantom(file_path, progress)
            else:
                self.importGeometricPhantom(file_path, progress)
                
            progress.setValue(100)
            progress.close()
            progress.deleteLater()
            
            slicer.util.infoDisplay("Phantom imported successfully!")
        except Exception as e:
            progress.close()
            progress.deleteLater()
            import traceback
            traceback.print_exc()
            slicer.util.errorDisplay(f"Failed to import: {str(e)}")

    def importLatticePhantom(self, file_path, progress):
        progress.setValue(10)
        progress.setLabelText("Parsing MCNP file...")
        slicer.app.processEvents()
        
        parsed_data = self.mcnp_parser.parseLattice(file_path)
        if not parsed_data['voxel_array'] is not None:
            raise ValueError("Failed to parse lattice voxel array.")
            
        progress.setValue(60)
        progress.setLabelText("Creating volume in Slicer...")
        slicer.app.processEvents()
        
        self.createVolumeNode(parsed_data, "LatticePhantom")
        progress.setValue(100)

    def importGeometricPhantom(self, file_path, progress):
        try:
            spacing_x = float(self.ui.xSpacingLineEdit.text)
            spacing_y = float(self.ui.ySpacingLineEdit.text)
            spacing_z = float(self.ui.zSpacingLineEdit.text)
        except ValueError:
            raise ValueError("Invalid spacing values. Must be numeric.")
            
        spacing = [spacing_x, spacing_y, spacing_z]
            
        progress.setValue(10)
        progress.setLabelText("Parsing CSG geometry...")
        slicer.app.processEvents()
        
        parsed_data = self.mcnp_parser.parseGeometricAndVoxelize(file_path, spacing, progress)
        
        progress.setValue(80)
        progress.setLabelText("Creating volume in Slicer...")
        slicer.app.processEvents()
        
        self.createVolumeNode(parsed_data, "GeometricPhantom")
        progress.setValue(100)

    def createVolumeNode(self, parsed_data, name_prefix):
        voxel_array = parsed_data['voxel_array']
        spacing_cm = parsed_data['spacing']
        materials = parsed_data.get('materials', {})
        
        # Convert spacing from cm to mm for Slicer
        spacing_mm = [s * 10.0 for s in spacing_cm]
        
        # Create empty LabelMap volume node properly with a display node
        volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", slicer.mrmlScene.GetUniqueNameByString(name_prefix))
        volumeNode.CreateDefaultDisplayNodes()
        
        # Update volume spacing
        volumeNode.SetSpacing(spacing_mm)
        
        # Reorder axes from MCNP (Z, Y, X) to Slicer (K, J, I) convention
        slicer.util.updateVolumeFromArray(volumeNode, voxel_array)
        
        # Create Color Table
        colorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLColorTableNode", slicer.mrmlScene.GetUniqueNameByString(f"{name_prefix}Colors"))
        colorNode.SetTypeToUser()
        colorNode.NamesInitialisedOn()
        colorNode.SetAttribute("Category", "Discrete")
        colorNode.SetNumberOfColors(max(256, np.max(voxel_array) + 1))
        
        # Default empty color
        colorNode.SetColor(0, "Background", 0.0, 0.0, 0.0, 0.0)
        
        # Add random colors for materials
        for mat_id, mat_name in materials.items():
            if mat_id < colorNode.GetNumberOfColors():
                # Generate pseudo-random distinct colors
                r = (mat_id * 50) % 255 / 255.0
                g = (mat_id * 100) % 255 / 255.0
                b = (mat_id * 150) % 255 / 255.0
                colorNode.SetColor(mat_id, mat_name, r, g, b, 1.0)
                
        volumeNode.GetDisplayNode().SetAndObserveColorNodeID(colorNode.GetID())
        
        # Show in slice views and center the view since phantoms might be small
        slicer.util.setSliceViewerLayers(label=volumeNode)
        
        # Reset Slice Views to center the newly created volume
        slicer.util.resetSliceViews()
        
        # Also adjust 3D view if we are displaying blocky volumes
        layoutManager = slicer.app.layoutManager()
        if layoutManager:
            threeDWidget = layoutManager.threeDWidget(0)
            if threeDWidget:
                threeDView = threeDWidget.threeDView()
                threeDView.resetFocalPoint()



class MCNPParser:
    """Parses MCNP input files."""
    
    def analyzeFile(self, file_path):
        """Quickly scans the file to determine if it's lattice or CSG."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Very simple heuristic: if it contains lat=1 or lat=2, it's a lattice.
        is_lattice = re.search(r'\blat=[12]\b', content, re.IGNORECASE) is not None
        
        info = {
            'is_lattice': is_lattice,
            'dimensions': (0,0,0),
            'spacing': (0,0,0),
            'materials': {}
        }
        
        if is_lattice:
            # Try to grab dimensions: fill=0:Nx 0:Ny 0:Nz
            fill_match = re.search(r'\bfill\s*=\s*(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)', content, re.IGNORECASE)
            if fill_match:
                info['dimensions'] = (int(fill_match.group(1))+1, int(fill_match.group(2))+1, int(fill_match.group(3))+1)
                
            # Fallback if fill parameters are split across lines (often true in MCNP):
            if not fill_match:
                # Sometimes bounds are alone on a line after lat=1
                bounds_match = re.search(r'(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)', content, re.IGNORECASE)
                if bounds_match:
                    info['dimensions'] = (int(bounds_match.group(1))+1, int(bounds_match.group(2))+1, int(bounds_match.group(3))+1)
                    
            # Try to grab spacing from px, py, pz surfaces (assumes voxel starts at origin)
            # This is a bit brittle, but serves for preview. 
            # Real parsing happens in parseLattice
            px_match = re.search(r'\bpx\s+([\d\.]+)', content, re.IGNORECASE)
            py_match = re.search(r'\bpy\s+([\d\.]+)', content, re.IGNORECASE)
            pz_match = re.search(r'\bpz\s+([\d\.]+)', content, re.IGNORECASE)
            if px_match and py_match and pz_match:
                info['spacing'] = (float(px_match.group(1)), float(py_match.group(1)), float(pz_match.group(1)))
                
        return info

    def parseLattice(self, file_path):
        """Full parsing of a lattice MCNP file."""
        import copy
        
        info = self.analyzeFile(file_path)
        nx, ny, nz = info['dimensions']
        total_voxels = nx * ny * nz
        
        if total_voxels == 0:
            raise ValueError("Could not determine lattice dimensions from fill= parameter.")

        voxel_list = []
        materials = {}
        
        is_in_cell_block = True
        is_in_surface_block = False
        is_in_data_block = False
        
        fill_reading_active = False
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('c '):
                    continue
                    
                # Detect block boundaries by completely blank lines according to MCNP spec
                # Since we strip(), empty lines denote blocks!
                if not line:
                    if is_in_cell_block:
                        is_in_cell_block = False
                        is_in_surface_block = True
                    elif is_in_surface_block:
                        is_in_surface_block = False
                        is_in_data_block = True
                    continue
                    
                # We can also detect block changes via comments as a fallback
                if 'Surface Cards' in line:
                    is_in_cell_block = False
                    is_in_surface_block = True
                elif 'Data Cards' in line:
                    is_in_surface_block = False
                    is_in_data_block = True

                # --- Material Parsing ---
                # Look for cell defined as "like ... but mat=X ... u=X $ Name"
                mat_match = re.search(r'mat=(\d+).*u=\d+.*?(?:\$|c\s)(.+)$', line, re.IGNORECASE)
                if mat_match:
                    mat_id = int(mat_match.group(1))
                    mat_name = mat_match.group(2).strip()
                    materials[mat_id] = mat_name
                else:
                    # Regular cell definition: cell_id mat_id [density] ... u=X ... $ Name
                    tokens = line.split()
                    if len(tokens) >= 3 and '$' in line and 'u=' in line.lower():
                        try:
                            # It must start with cell_id (int) and mat_id (int)
                            int(tokens[0])
                            mat_id = int(tokens[1])
                            mat_name = line.split('$')[1].strip()
                            if mat_id != 0:
                                materials[mat_id] = mat_name
                        except ValueError:
                            pass

                    
                # --- Fill Parsing ---
                # We strictly look for the lattice fill syntax which includes the bounds, e.g. fill=0:4 0:4 0:4
                fill_match = re.search(r'\bfill\s*=\s*(-?\d+:\d+(?:\s+-?\d+:\d+){2})', line, re.IGNORECASE)
                if fill_match:
                    fill_reading_active = True
                    # Clear voxel list in case we read a previous erroneous fill
                    voxel_list.clear()
                    # The rest of the line might contain fill data!
                    # Get everything after the bounds
                    bounds_str = fill_match.group(1)
                    parts = line[fill_match.end():].strip()
                    if parts:
                        self._parseFillLine(parts, voxel_list)
                    continue

                if fill_reading_active:
                    # Usually continuations in MCNP have 5+ leading spaces or end with &
                    # But since we stripped the line, we just check if it's a valid number
                    # array for the fill card.
                    if re.match(r'^[a-zA-Z]', line) or line.startswith('u='):
                         # If it hits another card (like 'c ---' or 'u=...'), we are done
                         fill_reading_active = False
                    
                    if fill_reading_active and len(voxel_list) < total_voxels:
                         self._parseFillLine(line, voxel_list)

        # Reshape voxel data
        if len(voxel_list) < total_voxels:
             # Fill the rest with 0s or something just in case
             print(f"Warning: Expected {total_voxels} voxels, got {len(voxel_list)}.")
             voxel_list.extend([0] * (total_voxels - len(voxel_list)))
        elif len(voxel_list) > total_voxels:
             print(f"Warning: Expected {total_voxels} voxels, got {len(voxel_list)}. Truncating.")
             voxel_list = voxel_list[:total_voxels]

        # Reshape to 3D. MCNP lattice fill varies typically in order of x, then y, then z
        # But GHOST exported it flattened (already reversed or not).
        # We'll reshape it as [Z, Y, X].
        voxel_array = np.array(voxel_list, dtype=np.uint16).reshape((nz, ny, nx))

        return {
            'voxel_array': voxel_array,
            'spacing': info['spacing'],
            'materials': materials
        }

    def _parseFillLine(self, line_data, voxel_list):
        # Remove in-line comments
        line_data = line_data.split('$')[0].strip()
        tokens = line_data.split()
        for token in tokens:
            token = token.lower()
            if token.endswith('r'):
                 try:
                     # e.g. "5r" means repeat the LAST value 5 more times.
                     repeats = int(token[:-1])
                     if len(voxel_list) > 0:
                         last_val = voxel_list[-1]
                         voxel_list.extend([last_val] * repeats)
                 except ValueError:
                     pass
            elif token.isdigit():
                 voxel_list.append(int(token))

    def parseGeometricAndVoxelize(self, file_path, spacing, progress):
        """
        Parses CSG geometry and voxelizes it.
        """
        cells = []
        surfaces = {}
        materials = {}
        
        is_in_cell_block = True
        is_in_surface_block = False
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('c '):
                    if not line:
                        if is_in_cell_block:
                            is_in_cell_block = False
                            is_in_surface_block = True
                        elif is_in_surface_block:
                            is_in_surface_block = False
                    continue
                    
                line = line.split('$')[0].strip() # Remove inline comments
                
                # Material parsing
                mat_match = re.search(r'm(\d+)\s+', line, re.IGNORECASE)
                if mat_match and not is_in_cell_block and not is_in_surface_block:
                    mat_id = int(mat_match.group(1))
                    materials[mat_id] = f"Material_{mat_id}"
                
                if is_in_cell_block:
                    # Parse cell: id mat density surfaces...
                    tokens = line.split()
                    if len(tokens) >= 3:
                        cell_id = int(tokens[0])
                        mat_id = int(tokens[1])
                        # If mat_id == 0, it's a void cell
                        if mat_id != 0:
                            density = float(tokens[2])
                            geom_tokens = tokens[3:]
                            
                            # Filter out key=value parameters (like imp:p=1, u=2)
                            geom = [t for t in geom_tokens if '=' not in t and ':' not in t]
                            cells.append({'id': cell_id, 'mat': mat_id, 'geom': geom})
                            if mat_id not in materials:
                                materials[mat_id] = f"Material {mat_id}"
                                
                elif is_in_surface_block:
                    # Parse surface: id type params...
                    tokens = line.split()
                    if len(tokens) >= 2:
                        surf_id = int(tokens[0])
                        surf_type = tokens[1].lower()
                        params = [float(p) for p in tokens[2:] if not p.isalpha() and '=' not in p]
                        surfaces[surf_id] = {'type': surf_type, 'params': params}
                        
        if not cells or not surfaces:
            raise ValueError("No cells or surfaces found in CSG file.")
            
        # 1. Compute Bounding Box
        min_x, max_x = -10.0, 10.0
        min_y, max_y = -10.0, 10.0
        min_z, max_z = -10.0, 10.0
        
        for surf_id, surf in surfaces.items():
            typ = surf['type']
            p = surf['params']
            if typ == 'rpp' and len(p) >= 6:
                min_x, max_x = min(min_x, p[0]), max(max_x, p[1])
                min_y, max_y = min(min_y, p[2]), max(max_y, p[3])
                min_z, max_z = min(min_z, p[4]), max(max_z, p[5])
            elif typ in ['px', 'py', 'pz'] and len(p) >= 1:
                val = p[0]
                if typ == 'px':
                    min_x, max_x = min(min_x, val), max(max_x, val)
                elif typ == 'py':
                    min_y, max_y = min(min_y, val), max(max_y, val)
                elif typ == 'pz':
                    min_z, max_z = min(min_z, val), max(max_z, val)
                    
        # Add a small padding to bounding box
        pad = 2.0
        min_x -= pad; max_x += pad
        min_y -= pad; max_y += pad
        min_z -= pad; max_z += pad
        
        # 2. Setup Voxel Grid
        nx = int(np.ceil((max_x - min_x) / spacing[0]))
        ny = int(np.ceil((max_y - min_y) / spacing[1]))
        nz = int(np.ceil((max_z - min_z) / spacing[2]))
        
        if nx <= 0 or ny <= 0 or nz <= 0 or nx*ny*nz > 1e9: # Protect against massive memory allocation (>2GB)
             raise ValueError(f"Calculated dimensions too large or invalid: {nx}x{ny}x{nz}. Check spacing and surfaces.")
             
        voxel_array = np.zeros((nz, ny, nx), dtype=np.uint16)
        
        # 3. Voxelize
        total_slices = nz
        for z_idx in range(nz):
            z = min_z + (z_idx + 0.5) * spacing[2]
            
            # Update progress
            if z_idx % max(1, nz // 20) == 0:
                progress.setValue(10 + int(70 * (z_idx / total_slices)))
                slicer.app.processEvents()
                if progress.wasCanceled:
                    raise UserWarning("Import cancelled by user.")
                    
            for y_idx in range(ny):
                y = min_y + (y_idx + 0.5) * spacing[1]
                for x_idx in range(nx):
                    x = min_x + (x_idx + 0.5) * spacing[0]
                    
                    # Point in cell test
                    for cell in cells:
                        if self._is_point_in_cell(x, y, z, cell['geom'], surfaces):
                            voxel_array[z_idx, y_idx, x_idx] = cell['mat']
                            break # Assume non-overlapping cells
                            
        return {
            'voxel_array': voxel_array,
            'spacing': spacing,
            'materials': materials
        }

    def _is_point_in_cell(self, x, y, z, geom_tokens, surfaces):
        """
        Evaluates the boolean CSG expression for a point.
        Currently supports simple intersections (implicit space between tokens).
        Does not fully support complex unions (:) or complements (#) yet.
        """
        for token in geom_tokens:
            if token in [':', '#']:
                # Advanced boolean ops not fully supported in this basic parser
                continue
                
            try:
                surf_ref = int(token)
                sign = 1 if surf_ref > 0 else -1
                surf_id = abs(surf_ref)
                
                if surf_id not in surfaces:
                    continue # Skip unknown surfaces
                    
                surf = surfaces[surf_id]
                val = self._evaluate_surface(x, y, z, surf['type'], surf['params'])
                
                # If point is on the wrong side of the surface, it's not in the cell
                # Positive sign means val < 0 (inside), negative means val > 0 (outside)
                # Note: MCNP convention says: 
                # For surface equation f(x,y,z) = 0
                # sense is negative if f(x,y,z) < 0.
                # A negative sign on the surface number means we want the negative sense.
                sense = -1 if val < 0 else 1
                if sign != sense:
                    return False
                    
            except ValueError:
                pass
                
        return True
        
    def _evaluate_surface(self, x, y, z, typ, p):
        """Evaluates surface equation f(x,y,z). Returns <0 if inside, >0 if outside."""
        if typ == 'px': return x - p[0]
        if typ == 'py': return y - p[0]
        if typ == 'pz': return z - p[0]
        if typ == 'so': return x**2 + y**2 + z**2 - p[0]**2
        if typ == 's':  return (x-p[0])**2 + (y-p[1])**2 + (z-p[2])**2 - p[3]**2
        if typ == 'sx': return (x-p[0])**2 + y**2 + z**2 - p[1]**2
        if typ == 'sy': return x**2 + (y-p[0])**2 + z**2 - p[1]**2
        if typ == 'sz': return x**2 + y**2 + (z-p[0])**2 - p[1]**2
        if typ == 'cx': return y**2 + z**2 - p[0]**2
        if typ == 'cy': return x**2 + z**2 - p[0]**2
        if typ == 'cz': return x**2 + y**2 - p[0]**2
        if typ == 'rpp':
            # RPP is defined by x_min, x_max, y_min, y_max, z_min, z_max
            # Point is inside if it's within all bounds
            if p[0] <= x <= p[1] and p[2] <= y <= p[3] and p[4] <= z <= p[5]:
                return -1.0 # Inside
            return 1.0 # Outside
            
        # Fallback for unknown surfaces (assume inside to see something)
        return -1.0
