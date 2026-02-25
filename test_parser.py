import re

def analyzeFile(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    is_lattice = re.search(r'\blat=[12]\b', content, re.IGNORECASE) is not None
    info = {'is_lattice': is_lattice, 'dimensions': (0,0,0), 'spacing': (0,0,0), 'materials': {}}
    if is_lattice:
        fill_match = re.search(r'\bfill\s*=\s*(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)', content, re.IGNORECASE)
        if fill_match:
            info['dimensions'] = (int(fill_match.group(1))+1, int(fill_match.group(2))+1, int(fill_match.group(3))+1)
        if not fill_match:
            bounds_match = re.search(r'(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)\s+(?:-?\d+):(\d+)', content, re.IGNORECASE)
            if bounds_match:
                info['dimensions'] = (int(bounds_match.group(1))+1, int(bounds_match.group(2))+1, int(bounds_match.group(3))+1)
    return info

def _parseFillLine(line_data, voxel_list):
    line_data = line_data.split('$')[0].strip()
    tokens = line_data.split()
    for token in tokens:
        token = token.lower()
        if token.endswith('r'):
             try:
                 repeats = int(token[:-1])
                 if len(voxel_list) > 0:
                     last_val = voxel_list[-1]
                     voxel_list.extend([last_val] * repeats)
             except ValueError:
                 pass
        elif token.isdigit():
             voxel_list.append(int(token))

def parseLattice(file_path):
    info = analyzeFile(file_path)
    nx, ny, nz = info['dimensions']
    total_voxels = nx * ny * nz
    voxel_list = []
    materials = {}
    fill_reading_active = False
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for idx, line in enumerate(f):
            raw_line = line
            line = line.strip()
            if not line or line.startswith('c '):
                continue
                
            mat_match = re.search(r'mat=(\d+).*u=\d+.*?(?:\$|c\s)(.+)$', line, re.IGNORECASE)
            if mat_match:
                mat_id = int(mat_match.group(1))
                mat_name = mat_match.group(2).strip()
                materials[mat_id] = mat_name
                
            # The regex from my fix:
            fill_match = re.search(r'\bfill\s*=\s*(-?\d+:\d+(?:\s+-?\d+:\d+){2})', line, re.IGNORECASE)
            if fill_match:
                print(f"L{idx+1}: MATCHED FILL BLOCK")
                fill_reading_active = True
                voxel_list.clear() # Added in my last fix
                bounds_str = fill_match.group(1)
                parts = line[fill_match.end():].strip()
                if parts:
                    print(f"  Reading inline fill '{parts}'")
                    _parseFillLine(parts, voxel_list)
                    print(f"  Current len after inline = {len(voxel_list)}")
                continue
                
            if fill_reading_active:
                if re.match(r'^[a-zA-Z]', line) or line.startswith('u='):
                     print(f"L{idx+1}: STOPPED FILL READING on '{line}'")
                     fill_reading_active = False
                     
                if fill_reading_active and len(voxel_list) < total_voxels:
                     print(f"L{idx+1}: Reading continuation '{line}'")
                     prev_len = len(voxel_list)
                     _parseFillLine(line, voxel_list)
                     print(f"  Added {len(voxel_list) - prev_len} elements. Total={len(voxel_list)}")
                     
    print(f"Final read: {len(voxel_list)} expected: {total_voxels}")

parseLattice('/home/harlley/Documentos/github/Doutorado/SlicerGHOST/test_lattice.inp')
