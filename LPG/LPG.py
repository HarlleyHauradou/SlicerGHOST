import os
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import *
import numpy as np

class LPG(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "LPG"
        parent.categories = ["MCNP"]
        parent.dependencies = []
        parent.contributors = ["Harlley Haurado, Pala Salvatice, Mirta Berdeguez e Ademir da Silva"] # Substitua pelo seu nome
        parent.helpText = """This plugin generate a mash phantom from a 3D imagem for MCNP code called phantom.inp"""
        parent.acknowledgementText = """""" # Deixe vazio ou adicione créditos

# class LPGWidget(ScriptedLoadableModuleWidget):
#     def setup(self):
#         ScriptedLoadableModuleWidget.setup(self)

#         uiWidget = slicer.util.loadUI(self.resourcePath('UI/LPG.ui'))
#         self.layout.addWidget(uiWidget)
#         self.ui = slicer.util.childWidgetVariables(uiWidget)
#         self.ui.generateButton.connect('clicked(bool)', self.onGenerateButtonClicked)

#     def resourcePath(self, filename):
#         return os.path.join(os.path.dirname(__file__), 'Resources', filename)

#     def onGenerateButtonClicked(self):
#         segmentationNode = slicer.util.getNode('Segmentation')
#         if not segmentationNode:
#             slicer.util.errorDisplay("Segmentação não encontrada.")
#             return

#         saveDirectory = qt.QFileDialog.getExistingDirectory(None, "Selecione o diretório para salvar o arquivo phantom.inp")
#         if not saveDirectory:
#             slicer.util.errorDisplay("Nenhum diretório selecionado.")
#             return

#         voxelArray, segmentNames = self.getVoxelData(segmentationNode)
#         filePath = os.path.join(saveDirectory, 'phantom.inp')
#         self.saveAsMCNPLattice(voxelArray, segmentNames, filePath)

#         slicer.util.infoDisplay(f"Arquivo salvo com sucesso em: {filePath}")

#     def getVoxelData(self, segmentationNode):
#         """
#         Extrai os dados voxel da segmentação como uma matriz numpy e obtém os nomes dos segmentos.
#         """
#         segmentation = segmentationNode.GetSegmentation()
#         segmentIds = slicer.vtkStringArray()
#         segmentation.GetSegmentIDs(segmentIds)

#         # Obter o número de segmentos
#         numSegments = segmentIds.GetNumberOfValues()
        
#         # Inicializar a matriz voxel e dicionário para os nomes dos segmentos
#         voxelArray = None
#         segmentNames = {}

#         for i in range(numSegments):
#             segmentId = segmentIds.GetValue(i)
#             segmentName = segmentation.GetSegment(segmentId).GetName()
#             binaryLabelMap = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId)

#             if voxelArray is None:
#                 voxelArray = np.zeros_like(binaryLabelMap, dtype=np.uint16)

#             # Atribui um valor único para cada segmento na matriz voxel
#             voxelArray[binaryLabelMap > 0] = i + 1  # segmentId as integer

#             # Salva o nome do segmento correspondente ao índice
#             segmentNames[i + 1] = segmentName

#         return voxelArray, segmentNames

#     def saveAsMCNPLattice(self, voxelArray, segmentNames, outputFilePath):
#         """
#         Converte os dados voxel da segmentação para o formato lattice cell do MCNP, com materiais nomeados.
#         """
#         dimensions = voxelArray.shape

#         with open(outputFilePath, 'w') as f:
#             f.write("c MCNP lattice cell generated from Slicer segmentation\n")
#             f.write(f"c Dimensions: {dimensions}\n")

#             # Escrever a definição de cada célula lattice
#             f.write("c Material Definitions\n")
#             for segmentId, segmentName in segmentNames.items():
#                 f.write(f"c mat={segmentId} {segmentName}\n")

#             f.write("\n")
#             f.write("c Lattice cells\n")

#             for z in range(dimensions[0]):
#                 for y in range(dimensions[1]):
#                     for x in range(dimensions[2]):
#                         voxelValue = voxelArray[z, y, x]
#                         if voxelValue > 0:  # Se o valor for maior que 0, é um material
#                             # Escreve a definição da célula lattice
#                             f.write(f"{x} {y} {z} {voxelValue}\n")



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
        segmentationNode = slicer.util.getNode('Segmentation')
        if not segmentationNode:
            slicer.util.errorDisplay("Segmentação não encontrada.")
            return

        saveDirectory = qt.QFileDialog.getExistingDirectory(None, "Selecione o diretório para salvar o arquivo phantom.inp")
        if not saveDirectory:
            slicer.util.errorDisplay("Nenhum diretório selecionado.")
            return

        voxelArray, segmentNames = self.getVoxelData(segmentationNode)
        filePath = os.path.join(saveDirectory, 'phantom.inp')

        if voxelArray is not None:
            self.saveAsMCNPLattice(voxelArray, segmentNames, filePath)
            slicer.util.infoDisplay(f"Arquivo salvo com sucesso em: {filePath}")
        else:
            slicer.util.errorDisplay("Falha ao gerar a matriz de voxels.")

    def getVoxelData(self, segmentationNode):
        """
        Extrai os dados voxel da segmentação como uma matriz numpy e retorna os nomes dos segmentos.
        """
        segmentIds = vtk.vtkStringArray()  # Cria uma nova instância de vtkStringArray
        segmentationNode.GetSegmentation().GetSegmentIDs(segmentIds)

        segmentNames = []
        voxelArray = None

        print(f"Total de segmentos: {segmentIds.GetNumberOfValues()}")  # Debug

        for i in range(segmentIds.GetNumberOfValues()):
            segmentId = segmentIds.GetValue(i)
            segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
            segmentNames.append(segment.GetName())

            # Converter a segmentação atual para um array numpy
            labelmapArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId)
            print(f"Segmento {i} - Nome: {segment.GetName()}, Shape: {labelmapArray.shape}")  # Debug

            if voxelArray is None:
                voxelArray = np.zeros_like(labelmapArray)

            # Preencher voxelArray com o índice do segmento (i+1) onde o valor da labelmapArray é maior que 0
            voxelArray[labelmapArray > 0] = i + 1

        return voxelArray, segmentNames

    def saveAsMCNPLattice(self, voxelArray, segmentNames, file_path):
        with open(file_path, 'w') as file:
            # Cabeçalho e definição da célula lattice
            file.write("1003 0 -501 502 -503 504 -505 506 lat=1 u=999 imp:p=1 imp:e=1\n")
            file.write("      fill=0:{} 0:{} 0:{}\n".format(
                voxelArray.shape[0]-1,
                voxelArray.shape[1]-1,
                voxelArray.shape[2]-1
            ))
            
            # Preenchimento compactado (exemplo simplificado)
            last_value = voxelArray[0, 0, 0]
            count = 0
            line = "      "
            
            for z in range(voxelArray.shape[2]):
                for y in range(voxelArray.shape[1]):
                    for x in range(voxelArray.shape[0]):
                        current_value = voxelArray[x, y, z]
                        if current_value == last_value:
                            count += 1
                        else:
                            line += f"{last_value} {count}r "
                            if len(line) > 70:
                                file.write(line + "\n")
                                line = "      "
                            last_value = current_value
                            count = 1
            
            # Finaliza o preenchimento
            line += f"{last_value} {count}r "
            file.write(line + "\n")
            
            # Definição de materiais e células
            file.write("\n")
            file.write("255 200 -1.225e-3 -501 502 -503 504 -505 506 u=255 IMP:P = 1 IMP:E =1 $ Ar no entorno do phantom\n")
            
            material_map = {
                1: "Pele",
                2: "Gordura",
                4: "Olhos",
                5: "Lentes dos olhos",
                6: "Músculo",
                7: "Cérebro (encéfalo)",
                # Adicione outros materiais conforme necessário
            }
            
            for material_id, material_name in material_map.items():
                file.write(f"{material_id} like 255 but mat={material_id} rho=-1.09 u={material_id} IMP:P = 1 IMP:E =1 $ {material_name}\n")