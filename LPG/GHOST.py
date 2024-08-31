import os
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import *
import numpy as np

class LPG(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "GHOST"
        parent.categories = ["Monte Carlo"]
        parent.dependencies = []
        parent.contributors = ["Harlley Haurado, Pala Salvatice, Mirta Berdeguez e Ademir da Silva"] # Substitua pelo seu nome
        parent.helpText = """This plugin generate a lattice phantom from a 3D imagem for MCNP code called phantom.inp"""
        parent.acknowledgementText = """""" # Deixe vazio ou adicione créditos

class LPGWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        uiWidget = slicer.util.loadUI(self.resourcePath('UI/LPG.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        self.ui.generateButton.connect('clicked(bool)', self.onGenerateButtonClicked)

    def resourcePath(self, filename):
        return os.path.join(os.path.dirname(__file__), 'Resources', filename)

    def onGenerateButtonClicked(self):
        # Obter o primeiro nó que seja um volume de imagem (tipo vtkMRMLScalarVolumeNode)
        volumeNode = None
        for node in slicer.mrmlScene.GetNodesByClass("vtkMRMLScalarVolumeNode"):
            volumeNode = node
            break

        if not volumeNode:
            slicer.util.errorDisplay("Image volume not find.")
            return

        # Captura o valor do campo spacingLineEdit
        try:
            xSpacingValue = float(self.ui.xSpacingLineEdit.text)
            ySpacingValue = float(self.ui.ySpacingLineEdit.text)
            zSpacingValue = float(self.ui.zSpacingLineEdit.text)
        except ValueError:
            slicer.util.errorDisplay("Please enter a valid number for spacing.")
            return
        
        spacingValue = [xSpacingValue, ySpacingValue, zSpacingValue]

        # Reamostrar o volume usando o módulo de Reamostragem
        resampledVolumeNode = self.resampleVolume(volumeNode, spacingValue)

        segmentationNode = slicer.util.getNode('Segmentation')
        if not segmentationNode:
            slicer.util.errorDisplay("Segmentation not find.")
            return

        saveDirectory = qt.QFileDialog.getExistingDirectory(None, "Select the directory to save the GHOST.inp.")
        if not saveDirectory:
            slicer.util.errorDisplay("No directories selected.")
            return

        voxelArray, segmentNames = self.getVoxelData(segmentationNode, resampledVolumeNode)
        filePath = os.path.join(saveDirectory, 'GHOST')

        if voxelArray is not None:
            self.saveAsMCNPLattice(voxelArray, segmentNames, filePath, spacingValue)
            slicer.util.infoDisplay(f"File saved successfully in: {filePath}")
        else:
            slicer.util.errorDisplay("Failed to generate voxel matrix.")


    def resampleVolume(self, inputVolumeNode, spacingValue):
        """
        Reamostra o volume de entrada usando o módulo Resample Scalar Volume.
        """
        # Criar nó de volume de saída
        outputVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "ResampledVolume")

        # Parâmetros de reamostragem
        parameters = {
            "InputVolume": inputVolumeNode.GetID(), 
            "OutputVolume": outputVolumeNode.GetID(),
            "outputPixelSpacing": f"{spacingValue[0]*10},{spacingValue[1]*10},{spacingValue[2]*10}", 
            "interpolationType": "lanczos"  
        }

        # Executar o módulo de reamostragem
        slicer.cli.runSync(slicer.modules.resamplescalarvolume, None, parameters)
        
        # Verificar se a reamostragem foi bem-sucedida
        if not outputVolumeNode.GetImageData():
            slicer.util.errorDisplay("Failed to resample volume.")
            return None

        # Retorna o nó de volume de saída reamostrado
        return outputVolumeNode


    def getVoxelData(self, segmentationNode, resampledVolumeNode):
        """
        Extrai os dados voxel da segmentação como uma matriz numpy e retorna os nomes dos segmentos.
        """
        segmentIds = vtk.vtkStringArray() # Cria uma nova instância de vtkStringArray
        segmentationNode.GetSegmentation().GetSegmentIDs(segmentIds)

        segmentNames = []
        voxelArray = None

        for i in range(segmentIds.GetNumberOfValues()):
            segmentId = segmentIds.GetValue(i)
            segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
            segmentNames.append(segment.GetName())

            # Converter a segmentação atual para um array numpy
            labelmapArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId, resampledVolumeNode)

            if voxelArray is None:
                voxelArray = np.zeros_like(labelmapArray)

            # Preencher voxelArray com o índice do segmento (i+1) onde o valor da labelmapArray é maior que 0
            voxelArray[labelmapArray > 0] = i + 2

        return voxelArray, segmentNames



    def saveAsMCNPLattice(self, voxelArray, segmentNames, file_path, spacingValue):
        # Carregar materiais do arquivo materials.txt
        materials_dict = self.load_materials(self.resourcePath('database/materials.txt'))

       
        with open(file_path, 'w') as file:
            # Cabeçalho e definição da célula lattice
            file.write("c =============================================================================\n")
            file.write("c                    Phantom Generated by GHOST 3D Slicer Plugin\n")
            file.write("c                           Developed by Harlley Hauradou\n")
            file.write("c =============================================================================\n")
            file.write("c    ---------------------------------------------------------------------------\n")
            file.write(f"c     Tamanho da matriz de voxel  : {voxelArray.shape[2]} x {voxelArray.shape[1]} x {voxelArray.shape[0]}\n")
            file.write(f"c     Resolução dos voxels        : {spacingValue[0]/10}mm x {spacingValue[1]/10}mm x {spacingValue[2]/10}mm\n")
            file.write("c    ---------------------------------------------------------------------------\n")
            file.write("c ********************* Cell Cards *********************\n")
            file.write("1000 0 1 -2 3 -4 5 -6 fill=999 imp:p=1 imp:e=1 $ $ cell containing the phantom\n")
            file.write("2000 0 -20 1 -40 3 50 -6 lat=1 u=999 imp:p=1 imp:e=1\n")
            file.write(f"     fill=0:{voxelArray.shape[2]-1} 0:{voxelArray.shape[1]-1} 0:{voxelArray.shape[0]-1}\n")
            
            # Escrever a matriz voxel no formato lattice
            fill_lines = self.create_fill_lines(voxelArray)
            for line in fill_lines:
                file.write(line + "\n")
            file.write('3000 0 #1000 imp:p=1 imp:e=1\n')
            
            # Definição de materiais e células
            file.write("c --- Universe Definitions ---\n")
            file.write("1 1 -1.205e-3 -20 1 -40 3 50 -6 u=1 imp:p=1 imp:e=1 $ Air surrounding the phantom\n")
            file.write('3001 0 #1 u=1 imp:p=1 imp:e=1\n')
            file.write('c \n')

            for idx, segmentName in enumerate(segmentNames, start=2):
                material_info = materials_dict.get(segmentName)
                if material_info:
                    density = material_info['density']
                    file.write(f"{idx} like 1 but mat={idx} rho=-{density:.6f} u={idx} imp:p=1 imp:e=1 $ {segmentName}\n")
                    file.write(f'300{idx} 0 #{idx} u={idx} imp:p=1 imp:e=1\n')
                else:
                    print(f'Material for segment {segmentName} not found in materials.txt')
            
            file.write("\n")
            file.write("c ********************* Surface Cards *********************\n")
            file.write('c\n')
            file.write('c --- Voxel Resolution ---\n')
            file.write('c\n')
            file.write(f'1 px 0\n')
            file.write(f'2 px {spacingValue[0] * voxelArray.shape[2]}\n')
            file.write(f'3 py 0\n') 
            file.write(f'4 py {spacingValue[1] * voxelArray.shape[1]}\n')
            file.write(f'5 pz 0\n') 
            file.write(f'6 pz {spacingValue[2] * voxelArray.shape[0]}\n')
            file.write(f'20 px {spacingValue[0]}\n')
            file.write(f'40 py {spacingValue[1]}\n')
            file.write(f'50 pz {spacingValue[2]}\n')
            file.write("c \n")
            file.write(' \n')

            file.write("c ********************* Data Cards *********************\n")
            file.write("c \n")
            file.write('c --- Source Definition ---\n')
            file.write("mode p e\n")
            file.write('c\n')
            # Adicionar as definições dos materiais no final            
            file.write("c --- Material Definitions ---\n")
            file.write('c\n')
            file.write('c Air (Dry, Near Sea Level) Density (g/cm³) = 0.001205\n')
            file.write('m1       6000.    -0.000124\n') 
            file.write('         7000.    -0.755268\n')
            file.write('         8000.    -0.231781\n')
            file.write('         18000.   -0.012827\n')
            file.write('c\n')
            for idx, segmentName in enumerate(segmentNames, start=2):
                material_info = materials_dict.get(segmentName)
                if material_info:
                    material_data = material_info['data']
                    for i, line in enumerate(material_data):
                        if i == 0:
                            file.write(f'c {segmentName} Density (g/cm³) = {material_info["density"]}\n')
                            file.write(line.replace('mx', f'm{idx}') + '\n')  # Linha com 'mx' sem deslocamento
                        else:
                            file.write("         " + line + '\n')  # Adiciona 9 espaços em branco nas linhas subsequentes
                    file.write('c\n')

            # Adicionar os tally F6 para cada material
            file.write("c --- Tally f6 Energy Deposition ---\n")
            self.addTallyF6(file, segmentNames)

            file.write('nps 1E6\n')

            
            file.write("c --- End of File ---\n")
            file.write('\n')

    def create_fill_lines(self, voxelArray):
        """
        Função que cria linhas compactadas para o preenchimento do FILL de acordo com o formato do MCNP.
        """
        lines = []
        current_line = "     "  # Inicia na coluna 6
        column_count = 6

        # Inverter a ordem das fatias em Z (primeira dimensão)
        voxelArray = voxelArray[::-1, :, :]

        # Flatten the 3D voxel array in order of i, j, k
        flattened_voxels = voxelArray.flatten()

        # Compress the line with MCNP's 'nR' format
        current_value = 1 if flattened_voxels[0] == 0 else flattened_voxels[0]
        count = 0

        for voxel in flattened_voxels:
            voxel = 1 if voxel == 0 else voxel
            if voxel == current_value:
                count += 1
            else:
                if count > 1:
                    part = f"{current_value} {count-1}r"
                else:
                    part = str(current_value)
                if column_count + len(part) > 60:  # Limit to 60 columns
                    lines.append(current_line)
                    current_line = "      " + part
                    column_count = 6 + len(part)
                else:
                    current_line += " " + part
                    column_count += len(part) + 1
                current_value = voxel
                count = 1
        
        # Finalize last part
        if count > 1:
            part = f"{current_value} {count-1}r"
        else:
            part = str(current_value)
        
        if column_count + len(part) > 60:
            lines.append(current_line)
            current_line = "     " + part
        else:
            current_line += " " + part
        
        lines.append(current_line)
        return lines

    

    # Ler o arquivo de materiais e converte em um dicionário
    def load_materials(self, filename):
        materials = {}
        with open(filename, 'r') as file:
            lines = file.readlines()
            current_material = None
            material_data = []
            density = None

            for line in lines:
                line = line.strip()

                if line.startswith('c ') and 'Density' in line:  # Indica o início de um novo material
                    if current_material is not None:
                        materials[current_material] = {
                            'density': density,
                            'data': material_data
                        }
                    current_material = ' '.join(line.split(' ')[1:-4])  # Nome do material
                    density_str = line.split('=')[-1].strip()  # Obtém o valor da densidade
                    density = float(density_str)
                    material_data = []

                elif line.startswith('m') or line:  # Linhas que fazem parte do material
                    material_data.append(line)

                elif line == '':  # Linha em branco indica o fim da definição do material
                    if current_material is not None:
                        materials[current_material] = {
                            'density': density,
                            'data': material_data
                        }
                        current_material = None
                        material_data = []

            if current_material is not None:  # Adiciona o último material ao dicionário
                materials[current_material] = {
                    'density': density,
                    'data': material_data
                }

        return materials

    def addTallyF6(self, file, segmentNames):
            """
            Adiciona as entradas de tally F6 para cada material no arquivo MCNP.
            """
            for idx, segmentName in enumerate(segmentNames, start=2):
                file.write(f"c\n")
                file.write(f"fc{idx}6 {segmentName}\n")
                # Adiciona o tally para todas as células associadas ao material
                cell_numbers = [str(cell_id) for cell_id in range((idx - 1), idx)]
                file.write(f"f{idx}6:p (({' '.join(cell_numbers)}) < {1000})\n")