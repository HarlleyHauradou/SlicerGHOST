import os
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import *
import numpy as np

class GHOST(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "GHOST"
        parent.categories = ["Monte Carlo"]
        parent.dependencies = []
        parent.contributors = ["Harlley Haurado, Paula Selvatice, Mirta Berdeguez e Ademir da Silva"] # Substitua pelo seu nome
        parent.helpText = """This plugin generate a lattice phantom from a 3D imagem for MCNP code called phantom.inp"""
        parent.acknowledgementText = """""" # Deixe vazio ou adicione créditos

class GHOSTWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        uiWidget = slicer.util.loadUI(self.resourcePath('UI/GHOST.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Conecta os botões ao seus respectivos métodos
        self.ui.generateButton.connect('clicked(bool)', self.onGenerateButtonClicked)
        self.ui.segmentEditorButton.connect('clicked(bool)', self.openSegmentEditor)
        self.ui.loadSegmentationButton.connect('clicked(bool)', self.populateSegmentList and self.populateMaterialComboBox)
        self.ui.renameButton.connect('clicked(bool)', self.renameSegment)
        self.ui.addMaterialButton.clicked.connect(self.showAddMaterialDialog)

        # Preenche a lista de segmentos e materiais
        self.populateSegmentList()
        self.populateMaterialComboBox()

        # Conecta a seleção do segmento ao método para exibir apenas o segmento selecionado
        self.ui.segmentListWidget.currentItemChanged.connect(self.showOnlySelectedSegment)

    def resourcePath(self, filename):
        return os.path.join(os.path.dirname(__file__), 'Resources', filename)

    
    def showAddMaterialDialog(self):
        dialog = AddMaterialDialog(self)
        if dialog.exec_() == qt.QDialog.Accepted:
            self.ui.materialComboBox.clear()
            self.populateMaterialComboBox()        

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
        
        # Leitura das opções dos Tallys
        useGy = self.ui.tallyGyCheckBox.isChecked()
        useMeV = self.ui.tallyMeVCheckBox.isChecked()

        # Leitura do valor de NPS
        npsValue = self.ui.npsLineEdit.text

        # Verificações básicas
        if not useGy and not useMeV:
            slicer.util.errorDisplay("Select one output unit for Tally F6.")
            return

        if not npsValue:
            slicer.util.errorDisplay("Enter a valid value for NPS.")
            return

        voxelArray, segmentNames = self.getVoxelData(segmentationNode, resampledVolumeNode)
        filePath = os.path.join(saveDirectory, 'GHOST')

        if voxelArray is not None:
            self.saveAsMCNPLattice(voxelArray, segmentNames, filePath, spacingValue, useGy, useMeV, npsValue)
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



    def saveAsMCNPLattice(self, voxelArray, segmentNames, file_path, spacingValue, useGy, useMeV, npsValue):
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
            file.write("2000 0 -20 11 -40 13 -50 15 lat=1 u=999 imp:p=1 imp:e=1\n")
            # Escreve o fill de acordo com a paridade do numero de voxels por dimensão
            fill_ranges = []
            for dim_size in voxelArray.shape:
                mid = dim_size // 2
                if dim_size % 2 == 0:  # par
                    fill_range = f"-{mid}:{mid-1}"
                else:  # ímpar
                    fill_range = f"-{mid}:{mid}"
                fill_ranges.append(fill_range)

            file.write(f"     fill={fill_ranges[2]} {fill_ranges[1]} {fill_ranges[0]}\n")



            # file.write(f"     fill=0:{voxelArray.shape[2]-1} 0:{voxelArray.shape[1]-1} 0:{voxelArray.shape[0]-1}\n")
            
            # Escrever a matriz voxel no formato lattice
            fill_lines = self.create_fill_lines(voxelArray)
            for line in fill_lines:
                file.write(line + "\n")
            
            # Definição de materiais e células
            file.write("c --- Universe Definitions ---\n")
            file.write("1 1 -1.205e-3 -20 11 -40 13 -50 15 u=1 imp:p=1 imp:e=1 $ Air surrounding the phantom\n")

            for idx, segmentName in enumerate(segmentNames, start=2):
                material_info = materials_dict.get(segmentName)
                if material_info:
                    density = material_info['density']
                    file.write(f"{idx} like 1 but mat={idx} rho=-{density:.6f} u={idx} imp:p=1 imp:e=1 $ {segmentName}\n")
                else:
                    print(f'Material for segment {segmentName} not found in materials.txt')
            
            file.write('9000 1 -1.205e-3 -90 #1000 imp:p=1 imp:e=1 $ World\n')
            file.write('9999 0 #9000 imp:p =0 imp:e=0 $ Out of World\n')
            
            px_max = spacingValue[0] * voxelArray.shape[2]
            py_max = spacingValue[1] * voxelArray.shape[1]
            pz_max = spacingValue[2] * voxelArray.shape[0]



            file.write("\n")
            file.write("c ********************* Surface Cards *********************\n")
            file.write('c\n')
            file.write('c --- Phantom Dimension ---\n')
            file.write('c\n')
            file.write(f'1 px 0.01\n')
            file.write(f'2 px {px_max - 0.01}\n')
            file.write(f'3 py 0.01\n') 
            file.write(f'4 py {py_max - 0.01}\n')
            file.write(f'5 pz 0.01\n') 
            file.write(f'6 pz {pz_max - 0.01}\n')
            file.write('c --- Voxel Resolution ---\n')
            file.write(f'20 px {spacingValue[0]}\n')
            file.write(f'11 px 0.0\n')
            file.write(f'40 py {spacingValue[1]}\n')
            file.write(f'13 py 0.0\n')
            file.write(f'50 pz {spacingValue[2]}\n')
            file.write(f'15 pz 0.0\n')
            file.write('c --- World ---\n')
            file.write(f'90 rpp -10 {px_max + 10} -10 {py_max + 10} -10 {pz_max + 110}\n')
            file.write("c \n")
            file.write(' \n')

            file.write("c ********************* Data Cards *********************\n")
            file.write("c \n")
            file.write('c --- Source Definition ---\n')
            file.write("mode p e\n")
            file.write('c ----- 10 MeV photon source collimated in a 10cm x 10cm field -----\n')
            file.write(f'SDEF pos=0 0 {pz_max + 100} x=d1 y=d2 z=0 par=p erg=10 axs=0 0 -1 ext=0\n')
            file.write('SI1 -5 5\n') 
            file.write('SP1 0 1\n')
            file.write('SI2 -5 5\n')
            file.write('SP2 0 1\n')
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
            self.addTallyF6(file, segmentNames, useGy, useMeV)

            file.write(f'nps {npsValue}\n')

            
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
        # voxelArray = voxelArray[::-1, :, :]

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

    def addTallyF6(self, file, segmentNames,useGy, useMeV):
            """
            Adiciona as entradas de tally F6 e FM6 para cada material no arquivo MCNP.
            """
            for idx, segmentName in enumerate(segmentNames, start=2):
                file.write(f"c\n")
                file.write(f"fc{idx}6 {segmentName}\n")
                # Adiciona os tallys para todas as células associadas ao material
                cell_numbers = [str(cell_id+1) for cell_id in range((idx - 1), idx)]
                if useGy:
                    file.write(f"f{idx}6:p (({' '.join(cell_numbers)}) < {1000})\n")
                    conversion_factor = 1.602e-10  # Conversão de MeV/g para Gy (J/Kg)
                    file.write(f"fm{idx}6 {conversion_factor} $ Conversão para Gy para {segmentName}\n")   
                if not useGy and useMeV:
                    file.write(f"f{idx}6:p (({' '.join(cell_numbers)}) < {1000})\n")                

    def openSegmentEditor(self):
        """
        Abre o módulo Segment Editor no 3D Slicer.
        """
        slicer.util.selectModule('SegmentEditor')

    def populateSegmentList(self):
        """
        Popula a lista de segmentos no widget.
        """
        segmentationNode = slicer.util.getNode('Segmentation')
        if segmentationNode:
            segmentIds = vtk.vtkStringArray()
            segmentationNode.GetSegmentation().GetSegmentIDs(segmentIds)
            for i in range(segmentIds.GetNumberOfValues()):
                segmentId = segmentIds.GetValue(i)
                segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
                self.ui.segmentListWidget.addItem(segment.GetName())

    def populateMaterialComboBox(self):
        """
        Popula o combobox com os materiais disponíveis no banco de dados.
        """
        materials_dict = self.load_materials(self.resourcePath('database/materials.txt'))
        for material_name in materials_dict.keys():
            self.ui.materialComboBox.addItem(material_name)

    def renameSegment(self):
        """
        Renomeia o segmento selecionado para o nome do material escolhido no combobox.
        """
        selectedSegment = self.ui.segmentListWidget.currentItem()
        if selectedSegment:
            newMaterialName = self.ui.materialComboBox.currentText
            segmentationNode = slicer.util.getNode('Segmentation')
            segmentId = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName(selectedSegment.text())
            segmentationNode.GetSegmentation().GetSegment(segmentId).SetName(newMaterialName)
            selectedSegment.setText(newMaterialName)

    def showOnlySelectedSegment(self):
        """
        Exibe apenas o segmento selecionado e esconde os outros.
        """
        segmentationNode = slicer.util.getNode('Segmentation')
        segmentNames = [self.ui.segmentListWidget.item(i).text() for i in range(self.ui.segmentListWidget.count)]
        selectedSegment = self.ui.segmentListWidget.currentItem()

        if segmentationNode and selectedSegment:
            displayNode = segmentationNode.GetDisplayNode()
            for segmentName in segmentNames:
                segmentId = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
                displayNode.SetSegmentVisibility(segmentId, segmentName == selectedSegment.text())







############# ADD NEW MATERIAL POP-UP ########################
from Resources.database.element_data import element_data

class AddMaterialDialog(qt.QDialog):
    def __init__(self, parent=None):
        super(AddMaterialDialog, self).__init__()

        # Carregar o arquivo .ui
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/newMaterial.ui'))
        self.setLayout(qt.QVBoxLayout())
        self.layout().addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Conectar sinais
        # self.ui.addElementButton.clicked.connect(self.addElement)
        self.ui.createButton.clicked.connect(self.createMaterial)


        # Conectando botões de elementos ao método de adição
        for element, (atomic_number, mass_number) in element_data.items():
            button = getattr(self.ui, element)
            if button:
                button.clicked.connect(lambda checked, el=element: self.add_element(el))

        # Conectar o botão de adicionar o elemento ao memo
        self.ui.addElementButton.clicked.connect(self.add_element_to_memo)

        # Salva novo material no banco dados
        self.ui.createButton.clicked.connect(self.createMaterial)
    

    def add_element(self, element):
        """Adiciona o elemento selecionado na variável `selected_element`"""
        atomic_number, mass_number = element_data[element]
        formatted_element = f"{atomic_number}{mass_number:03d}"
        self.selected_element = formatted_element

    def add_element_to_memo(self):
        """Adiciona o elemento formatado e a fração no memo"""
        fraction = self.ui.fractionLineEdit.text
        if hasattr(self, 'selected_element') and fraction:
            memo_text = f"{self.selected_element}.    {fraction}"
            self.ui.memo.append(memo_text)
            self.ui.fractionLineEdit.clear()
        else:
            print("Erro: Selecione um elemento e insira uma fração.")



    def resourcePath(self, filename):
        return os.path.join(os.path.dirname(__file__), 'Resources', filename)


    def createMaterial(self):
        """
        Salva o material no banco de dados e fecha a janela.
        """
        name = self.ui.nameLineEdit.text
        density = self.ui.densityLineEdit.text
        elements = self.ui.memo.toPlainText()

        # Verificar se os campos estão preenchidos
        if not name or not density or not elements:
            qt.QMessageBox.warning(self, "Erro", "Todos os campos devem ser preenchidos.")
            return

        # Salvar material em materials.txt
        with open(self.resourcePath('database/materials.txt'), 'a') as file:
            file.write(f"\nc {name} Density (g/cm3) = {density}\n")
            lines = elements.split('\n')
            for i, line in enumerate(lines):
                if i == 0:
                    file.write(f"mx       {line.replace(':', ' ')}\n")
                else:
                    file.write(f"         {line.replace(':', ' ')}\n")

        # Fechar a janela
        self.accept()

