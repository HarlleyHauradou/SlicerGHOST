import os
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import *
import numpy as np

class LPG(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "Lattice Phantom Generate"
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
            spacingValue = float(self.ui.spacingLineEdit.text)
        except ValueError:
            slicer.util.errorDisplay("Please enter a valid number for spacing.")
            return

        # Reamostrar o volume usando o módulo de Reamostragem
        resampledVolumeNode = self.resampleVolume(volumeNode, spacingValue)

        segmentationNode = slicer.util.getNode('Segmentation')
        if not segmentationNode:
            slicer.util.errorDisplay("Segmentation not find.")
            return

        saveDirectory = qt.QFileDialog.getExistingDirectory(None, "Select the directory to save the phantom.inp.")
        if not saveDirectory:
            slicer.util.errorDisplay("No directories selected.")
            return

        voxelArray, segmentNames = self.getVoxelData(segmentationNode, resampledVolumeNode)
        filePath = os.path.join(saveDirectory, 'phantom.inp')

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
            "outputPixelSpacing": f"{spacingValue*10},{spacingValue*10},{spacingValue*10}", 
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
            voxelArray[labelmapArray > 0] = i + 1

        return voxelArray, segmentNames



    def saveAsMCNPLattice(self, voxelArray, segmentNames, file_path, spacingValue):
        # Carregar materiais do arquivo materials.txt
        materials_dict = self.load_materials(self.resourcePath('database/materials.txt'))

       
        with open(file_path, 'w') as file:
            # Cabeçalho e definição da célula lattice
            file.write("c --- Phantom Generated by LPG 3D Slicer Plugin ---\n")
            file.write("c ---       Developed by Harlley Hauradou       ---\n")
            file.write("c --- Cell Cards ---\n")
            file.write("1000 0 -501 502 -503 504 -505 506 lat=1 u=999 imp:p=1 imp:e=1\n")
            file.write(f"     fill=0:{voxelArray.shape[0]-1} 0:{voxelArray.shape[1]-1} 0:{voxelArray.shape[2]-1}\n")
            
            # Escrever a matriz voxel slice por slice
            file.write("c --- Lattice Filling ---\n")
            for z in range(voxelArray.shape[2]):
                for x in range(voxelArray.shape[0]):
                    line = self.compress_line(voxelArray[x, :, z])
                    file.write(line + "\n")
            
            # Definição de materiais e células
            file.write("c --- Universe Definitions ---\n")
            file.write("1 1 -1.225e-3 -501 502 -503 504 -505 506 u=1 IMP:P=1 IMP:E=1 $ Air surrounding the phantom\n")
            
            for idx, segmentName in enumerate(segmentNames, start=2):
                material_info = materials_dict.get(segmentName)
                if material_info:
                    density = material_info['density']
                    file.write(f"{idx} like 1 but mat={idx} rho=-{density:.6f} u={idx} IMP:P=1 IMP:E=1 $ {segmentName}\n")
                else:
                    print(f'Material for segment {segmentName} not found in materials.txt')
            
            file.write("\n")
            file.write("c --- Surface Cards ---\n")
            file.write('c\n')
            file.write('c --- Voxel Resolution ---\n')
            file.write('c\n')
            file.write(f'501 px {spacingValue}\n')
            file.write(f'502 px 0\n')
            file.write(f'503 px {spacingValue}\n')
            file.write(f'504 px 0\n')
            file.write(f'505 px {spacingValue}\n')
            file.write(f'506 px 0\n')
            file.write("c \n")

            # Adicionar as definições dos materiais no final            
            file.write("c --- Material Definitions ---\n")
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
                            file.write("        " + line + '\n')  # Adiciona 8 espaços em branco nas linhas subsequentes
                            file.write('c\n')
            file.write("c \n")

        
            file.write("c --- Data Cards ---\n")
            file.write("mode p e\n")
            
            file.write("\n")
            file.write("c --- End of File ---\n")

    def compress_line(self, row):
        """
        Substitui 0 por 1 e comprime a linha para o formato `valor nr`, onde n é o número de repetições.
        """
        compressed = []
        current_value = 1 if row[0] == 0 else row[0]
        count = 1
        
        for value in row[1:]:
            value = 1 if value == 0 else value
            if value == current_value:
                count += 1
            else:
                if count > 1:
                    compressed.append(f"{current_value} {count}r")
                else:
                    compressed.append(str(current_value))
                current_value = value
                count = 1
        
        # Append the last value
        if count > 1:
            compressed.append(f"{current_value} {count}r")
        else:
            compressed.append(str(current_value))
        
        return ' '.join(compressed)
    

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

                if line.startswith('c '):  # Indica o início de um novo material
                    if current_material is not None:
                        materials[current_material] = {
                            'density': density,
                            'data': material_data
                        }
                    current_material = line.split(' ')[1]  # Nome do material
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
