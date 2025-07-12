import sys
import sqlite3
import hashlib
import os
import pydicom
import cv2
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QMessageBox, QFileDialog, QSlider, QTabWidget,
                            QComboBox, QTableWidget, QTableWidgetItem, QRadioButton,
                            QButtonGroup, QGroupBox)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import scipy.io
import pandas as pd

class DatabaseManager:          # Clase principal para gestionar la conexión y operaciones con la base de datos
    def __init__(self):
        self.conn = sqlite3.connect('biomed.db')              # Conexión SQLite con detección automática de esquema
        self.create_tables()                       # Asegura que las tablas existan al iniciar
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                user_type TEXT NOT NULL  -- 'imagen' o 'senal'
            )
        ''')
        cursor.execute('''                       #  Tabla para metadatos DICOM (relacionada con usuarios via user_id)
            CREATE TABLE IF NOT EXISTS dicom_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                patient_name TEXT,
                study_date TEXT,
                modality TEXT,
                dicom_path TEXT,
                nifti_path TEXT,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS image_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                analysis_type TEXT,
                parameters TEXT,
                result TEXT,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                signal_type TEXT,  -- 'MAT' o 'CSV'
                analysis_type TEXT,
                parameters TEXT,
                result TEXT,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        self.conn.commit()
    
    def register_user(self, username, password, user_type):
        try:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            cursor = self.conn.cursor()
            cursor.execute('INSERT INTO users VALUES (NULL, ?, ?, ?)', 
                         (username, hashed, user_type))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def login_user(self, username, password):
        hashed = hashlib.sha256(password.encode()).hexdigest()
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, user_type FROM users WHERE username=? AND password=?', 
                      (username, hashed))
        return cursor.fetchone()

    def save_dicom_analysis(self, patient_id, patient_name, dicom_path, nifti_path, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO dicom_files 
            (patient_id, patient_name, dicom_path, nifti_path, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (patient_id, patient_name, dicom_path, nifti_path, user_id))
        self.conn.commit()

    def save_image_analysis(self, file_path, analysis_type, params, result, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO image_analysis 
            (file_path, analysis_type, parameters, result, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_path, analysis_type, str(params), str(result), user_id))
        self.conn.commit()

    def save_signal_analysis(self, file_path, signal_type, analysis_type, params, result, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO signal_analysis 
            (file_path, signal_type, analysis_type, parameters, result, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (file_path, signal_type, analysis_type, str(params), str(result), user_id))
        self.conn.commit()

class LoginWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.main_window = None
        self.setup_ui()
    
    def setup_ui(self):         #  Configuración inicial de la UI (ejecutado en __init__)
        self.setWindowTitle("BioMed Login")
        self.setFixedSize(350, 500)
        
        self.setStyleSheet("""       # Estilo CSS para componentes (QSS)
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 12px;
                color: #333;
            }
            QLineEdit {
                border: 1px solid #ddd;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            QRadioButton {
                padding: 5px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("BioMed Analyzer")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title, alignment=Qt.AlignCenter)
        
        layout.addWidget(QLabel("Usuario:"))
        self.username = QLineEdit()
        layout.addWidget(self.username)
        
        layout.addWidget(QLabel("Contraseña:"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password)
        
        self.user_type_group = QGroupBox("Tipo de Usuario")           #  Grupo de radio buttons para selección de rol
        type_layout = QVBoxLayout()
        self.btn_imagen = QRadioButton("Experto en Imágenes")
        self.btn_senal = QRadioButton("Experto en Señales")
        self.btn_imagen.setChecked(True)
        
        type_layout.addWidget(self.btn_imagen)
        type_layout.addWidget(self.btn_senal)
        self.user_type_group.setLayout(type_layout)
        layout.addWidget(self.user_type_group)
                
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("Ingresar")
        self.btn_register = QPushButton("Registrarse")
        
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_register)
        layout.addLayout(btn_layout)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        self.btn_login.clicked.connect(self.handle_login)            #  Conexión de señales (eventos)
        self.btn_register.clicked.connect(self.handle_register)
    
    def handle_login(self):          #  Valida credenciales contra la base de datos
        username = self.username.text()       # Elimina espacios en blanco
        password = self.password.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Por favor complete todos los campos")
            return
            
        user = self.db.login_user(username, password)                   # Consulta la base de datos (DatabaseManager)
        if user:
            self.hide()
            if self.main_window is None:
                self.main_window = MainWindow(user[0], user[1], self.db)
            self.main_window.show()
        else:
            QMessageBox.warning(self, "Error", "Credenciales incorrectas")
    
    def handle_register(self):
        username = self.username.text()
        password = self.password.text()
        user_type = 'imagen' if self.btn_imagen.isChecked() else 'senal'
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Por favor complete todos los campos")
            return
            
        if self.db.register_user(username, password, user_type):
            QMessageBox.information(self, "Éxito", "Registro exitoso")
        else:
            QMessageBox.warning(self, "Error", "El usuario ya existe")

class ImageExpertWindow(QMainWindow):
    def __init__(self, user_id, db):
        super().__init__()
        self.user_id = user_id
        self.db = db
        self.current_image = None
        self.dicom_volume = None
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("BioMed Analyzer - Experto en Imágenes")
        self.setGeometry(100, 100, 1000, 700)
        
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTabBar::tab {
                padding: 8px;
                background: #e0e0e0;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
            }
            QPushButton {
                padding: 6px;
                min-width: 80px;
            }
        """)
        
        self.tabs = QTabWidget()
        self.setup_dicom_tab()
        self.setup_image_analysis_tab()
        
        self.setCentralWidget(self.tabs)
    
    def setup_dicom_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.fig_dicom = Figure(figsize=(10, 4))
        self.canvas_dicom = FigureCanvas(self.fig_dicom)
        self.axes_dicom = self.fig_dicom.subplots(1, 3)
        layout.addWidget(self.canvas_dicom)
        
        slider_layout = QHBoxLayout()
        self.slider_axial = QSlider(Qt.Horizontal)
        self.slider_coronal = QSlider(Qt.Horizontal)
        self.slider_sagital = QSlider(Qt.Horizontal)
        
        for slider, label in zip([self.slider_axial, self.slider_coronal, self.slider_sagital], 
                                ["Axial", "Coronal", "Sagital"]):
            slider_layout.addWidget(QLabel(label))
            slider_layout.addWidget(slider)
            slider.setEnabled(False)
            slider.valueChanged.connect(self.update_dicom_view)
        
        layout.addLayout(slider_layout)
        
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("Cargar DICOM")
        btn_convert = QPushButton("Convertir a NIfTI")
        btn_view = QPushButton("Visualizar NIfTI")
        
        btn_load.clicked.connect(self.load_dicom)
        btn_convert.clicked.connect(self.convert_to_nifti)
        btn_view.clicked.connect(self.view_nifti)
        
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_convert)
        btn_layout.addWidget(btn_view)
        layout.addLayout(btn_layout)
        
        self.patient_info = QLabel("No hay datos cargados")
        self.patient_info.setStyleSheet("color: #555;")
        layout.addWidget(self.patient_info)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "DICOM/NIfTI")
    
    def setup_image_analysis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.fig_img = Figure()
        self.canvas_img = FigureCanvas(self.fig_img)
        self.ax_img = self.fig_img.add_subplot(111)
        layout.addWidget(self.canvas_img)
        
        controls_layout = QHBoxLayout()
        
        morph_layout = QVBoxLayout()
        morph_label = QLabel("Operaciones Morfológicas:")
        self.morph_op = QComboBox()
        self.morph_op.addItems(["Apertura", "Cierre", "Gradiente"])
        self.morph_kernel = QComboBox()
        self.morph_kernel.addItems(["3x3", "5x5", "7x7"])
        btn_morph = QPushButton("Aplicar")
        
        morph_layout.addWidget(morph_label)
        morph_layout.addWidget(self.morph_op)
        morph_layout.addWidget(self.morph_kernel)
        morph_layout.addWidget(btn_morph)
        
        cell_layout = QVBoxLayout()
        btn_count = QPushButton("Contar Células")
        self.cell_count = QLabel("Células detectadas: -")
        
        cell_layout.addWidget(btn_count)
        cell_layout.addWidget(self.cell_count)
        
        controls_layout.addLayout(morph_layout)
        controls_layout.addLayout(cell_layout)
        layout.addLayout(controls_layout)
        
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("Cargar Imagen")
        btn_save = QPushButton("Guardar Análisis")
        
        btn_load.clicked.connect(self.load_image)
        btn_save.clicked.connect(self.save_analysis)
        btn_morph.clicked.connect(self.apply_morphological)
        btn_count.clicked.connect(self.count_cells)
        
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Análisis de Imágenes")
    
    def load_dicom(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta DICOM")
        if dir_path:
            try:
                files = [f for f in os.listdir(dir_path) if f.endswith('.dcm')]
                slices = [pydicom.dcmread(os.path.join(dir_path, f)) for f in files]
                slices.sort(key=lambda x: float(x.ImagePositionPatient[2]))
                
                self.dicom_volume = np.stack([s.pixel_array for s in slices])
                
                for slider, dim in zip([self.slider_axial, self.slider_coronal, self.slider_sagital], 
                                     self.dicom_volume.shape):
                    slider.setMaximum(dim - 1)
                    slider.setValue(dim // 2)
                    slider.setEnabled(True)
                
                first_slice = slices[0]
                info = f"Paciente: {getattr(first_slice, 'PatientName', 'N/A')} | ID: {getattr(first_slice, 'PatientID', 'N/A')}"
                self.patient_info.setText(info)
                
                self.db.save_dicom_analysis(
                    getattr(first_slice, 'PatientID', ''),
                    str(getattr(first_slice, 'PatientName', '')),
                    dir_path,
                    "",
                    self.user_id
                )
                
                self.update_dicom_view()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cargar DICOM: {str(e)}")
    
    def update_dicom_view(self):
        if hasattr(self, 'dicom_volume'):
            slices = [
                self.dicom_volume[self.slider_axial.value(), :, :],
                self.dicom_volume[:, self.slider_coronal.value(), :],
                self.dicom_volume[:, :, self.slider_sagital.value()]
            ]
            
            titles = ["Axial", "Coronal", "Sagital"]
            for ax, img, title in zip(self.axes_dicom, slices, titles):
                ax.clear()
                ax.imshow(img, cmap='gray')
                ax.set_title(f"{title} - Slice {getattr(self, f'slider_{title.lower()}').value()}")
                ax.axis('off')
            
            self.canvas_dicom.draw()
    
    def convert_to_nifti(self):
        if hasattr(self, 'dicom_volume'):
            try:
                nifti_img = nib.Nifti1Image(self.dicom_volume, np.eye(4))
                filepath, _ = QFileDialog.getSaveFileName(self, "Guardar NIfTI", "", "NIfTI (*.nii)")
                if filepath:
                    nib.save(nifti_img, filepath)
                    QMessageBox.information(self, "Éxito", "Archivo NIfTI guardado")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al convertir: {str(e)}")
    
    def view_nifti(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Abrir NIfTI", "", "NIfTI (*.nii *.nii.gz)")
        if filepath:
            try:
                img = nib.load(filepath)
                self.dicom_volume = img.get_fdata()
                
                for slider, dim in zip([self.slider_axial, self.slider_coronal, self.slider_sagital], 
                                     self.dicom_volume.shape):
                    slider.setMaximum(dim - 1)
                    slider.setValue(dim // 2)
                    slider.setEnabled(True)
                
                self.update_dicom_view()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cargar NIfTI: {str(e)}")
    
    def load_image(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Cargar Imagen", "", "Imágenes (*.jpg *.png *.tif)")
        if filepath:
            self.current_image = cv2.imread(filepath)
            self.current_image_path = filepath
            self.show_image()
    
    def show_image(self):
        self.ax_img.clear()
        if len(self.current_image.shape) == 2:
            self.ax_img.imshow(self.current_image, cmap='gray')
        else:
            self.ax_img.imshow(cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB))
        self.ax_img.axis('off')
        self.canvas_img.draw()
    
    def apply_morphological(self):
        if self.current_image is not None:
            try:
                op_map = {
                    "Apertura": cv2.MORPH_OPEN,
                    "Cierre": cv2.MORPH_CLOSE,
                    "Gradiente": cv2.MORPH_GRADIENT
                }
                op = op_map[self.morph_op.currentText()]
                
                kernel_size = int(self.morph_kernel.currentText().split('x')[0])
                kernel = np.ones((kernel_size, kernel_size), np.uint8)
                
                if len(self.current_image.shape) == 3:
                    gray = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = self.current_image
                
                result = cv2.morphologyEx(gray, op, kernel)
                self.current_image = result
                self.show_image()                
                params = {
                    'operation': self.morph_op.currentText(),
                    'kernel_size': kernel_size
                }
                self.db.save_image_analysis(
                    self.current_image_path,
                    'morphological',
                    params,
                    'success',
                    self.user_id
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error en operación: {str(e)}")
    
    def count_cells(self):
        if self.current_image is not None:
            try:
                if len(self.current_image.shape) == 3:
                    gray = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = self.current_image                
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                kernel = np.ones((3,3), np.uint8)
                opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
                num_labels, labels = cv2.connectedComponents(opening)                
                self.ax_img.clear()
                self.ax_img.imshow(labels, cmap='jet')
                self.ax_img.set_title(f"Células detectadas: {num_labels - 1}")
                self.ax_img.axis('off')
                self.canvas_img.draw()                
                self.cell_count.setText(f"Células detectadas: {num_labels - 1}")                
                self.db.save_image_analysis(
                    self.current_image_path,
                    'cell_count',
                    {'method': 'connected_components'},
                    str(num_labels - 1),
                    self.user_id
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error en conteo: {str(e)}")
    
    def save_analysis(self):
        if self.current_image is not None and hasattr(self, 'current_image_path'):
            try:
                filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Imagen", "", "PNG (*.png);;JPEG (*.jpg)")
                if filepath:
                    if len(self.current_image.shape) == 2:
                        cv2.imwrite(filepath, self.current_image)
                    else:
                        cv2.imwrite(filepath, cv2.cvtColor(self.current_image, cv2.COLOR_RGB2BGR))
                    QMessageBox.information(self, "Éxito", "Imagen guardada")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al guardar: {str(e)}")

class SignalExpertWindow(QMainWindow):
    def __init__(self, user_id, db):
        super().__init__()
        self.user_id = user_id
        self.db = db
        self.mat_data = None
        self.df = None
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("BioMed Analyzer - Experto en Señales")
        self.setGeometry(100, 100, 1000, 700)
        
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTabBar::tab {
                padding: 8px;
                background: #e0e0e0;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #2196F3;
                color: white;
            }
            QPushButton {
                padding: 6px;
                min-width: 80px;
            }
            QTableWidget {
                gridline-color: #ddd;
            }
        """)
        
        self.tabs = QTabWidget()
        self.setup_mat_tab()
        self.setup_csv_tab()
        
        self.setCentralWidget(self.tabs)
    
    def setup_mat_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.fig_signal = Figure()
        self.canvas_signal = FigureCanvas(self.fig_signal)
        self.ax_signal = self.fig_signal.add_subplot(111)
        layout.addWidget(self.canvas_signal)
        
        self.signal_combo = QComboBox()
        
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("Cargar .mat")
        btn_plot = QPushButton("Graficar")
        btn_analyze = QPushButton("Analizar")
        
        btn_load.clicked.connect(self.load_mat)
        btn_plot.clicked.connect(self.plot_signal)
        btn_analyze.clicked.connect(self.analyze_signal)
        
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_plot)
        btn_layout.addWidget(btn_analyze)
        
        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("Señal:"))
        layout.addWidget(self.signal_combo)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Señales MAT")
    
    def setup_csv_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.table_csv = QTableWidget()
        self.table_csv.setColumnCount(0)
        self.table_csv.setRowCount(0)
        layout.addWidget(self.table_csv)
        
        control_layout = QHBoxLayout()
        
        column_layout = QVBoxLayout()
        column_layout.addWidget(QLabel("Eje X:"))
        self.csv_x = QComboBox()
        column_layout.addWidget(self.csv_x)
        
        column_layout.addWidget(QLabel("Eje Y:"))
        self.csv_y = QComboBox()
        column_layout.addWidget(self.csv_y)
        
        control_layout.addLayout(column_layout)
        
        btn_layout = QVBoxLayout()
        btn_load = QPushButton("Cargar CSV")
        btn_plot = QPushButton("Graficar")
        btn_analyze = QPushButton("Analizar")
        
        btn_load.clicked.connect(self.load_csv)
        btn_plot.clicked.connect(self.plot_csv)
        btn_analyze.clicked.connect(self.analyze_csv)
        
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_plot)
        btn_layout.addWidget(btn_analyze)
        
        control_layout.addLayout(btn_layout)
        layout.addLayout(control_layout)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Señales CSV")
    
    def load_mat(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Cargar .mat", "", "MATLAB (*.mat)")
        if filepath:
            try:
                self.mat_data = scipy.io.loadmat(filepath)
                self.signal_combo.clear()
                self.signal_combo.addItems([k for k in self.mat_data if not k.startswith('__')])
                
                self.db.save_signal_analysis(
                    filepath,
                    'MAT',
                    'load',
                    {},
                    'success',
                    self.user_id
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cargar .mat: {str(e)}")
    
    def plot_signal(self):
        if hasattr(self, 'mat_data') and self.signal_combo.currentText():
            try:
                data = self.mat_data[self.signal_combo.currentText()]
                self.ax_signal.clear()
                
                if data.ndim == 1:
                    self.ax_signal.plot(data)
                elif data.ndim == 2:
                    self.ax_signal.plot(data.T)
                
                self.ax_signal.set_title(self.signal_combo.currentText())
                self.ax_signal.grid(True)
                self.canvas_signal.draw()                                
                self.db.save_signal_analysis(
                    "",
                    'MAT',
                    'plot',
                    {'signal': self.signal_combo.currentText()},
                    'success',
                    self.user_id                )                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al graficar: {str(e)}")    
    def analyze_signal(self):
        if hasattr(self, 'mat_data') and self.signal_combo.currentText():
            try:
                data = self.mat_data[self.signal_combo.currentText()]                                
                mean_val = np.mean(data)
                std_val = np.std(data)
                max_val = np.max(data)
                min_val = np.min(data)                
                result = f"Media: {mean_val:.2f}\nDesviación: {std_val:.2f}\nMáximo: {max_val:.2f}\nMínimo: {min_val:.2f}"
                
                QMessageBox.information(self, "Análisis", result)                
                self.db.save_signal_analysis(
                    "",
                    'MAT',
                    'basic_analysis',
                    {'signal': self.signal_combo.currentText()},
                    result,
                    self.user_id
                )                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error en análisis: {str(e)}")    
    def load_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Cargar CSV", "", "CSV (*.csv)")
        if filepath:
            try:
                self.df = pd.read_csv(filepath)                
                self.table_csv.setColumnCount(len(self.df.columns))
                self.table_csv.setRowCount(len(self.df))
                self.table_csv.setHorizontalHeaderLabels(self.df.columns)                
                for i in range(len(self.df)):
                    for j in range(len(self.df.columns)):
                        self.table_csv.setItem(i, j, QTableWidgetItem(str(self.df.iloc[i, j])))                
                self.csv_x.clear()
                self.csv_y.clear()
                self.csv_x.addItems(self.df.columns)
                self.csv_y.addItems(self.df.columns)                
                self.db.save_signal_analysis(
                    filepath,
                    'CSV',
                    'load',
                    {'columns': list(self.df.columns)},
                    'success',
                    self.user_id
                )                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cargar CSV: {str(e)}")
    
    def plot_csv(self):
        if hasattr(self, 'df') and self.csv_x.currentText() and self.csv_y.currentText():
            try:
                x = self.df[self.csv_x.currentText()]
                y = self.df[self.csv_y.currentText()]
                
                fig = Figure()
                ax = fig.add_subplot(111)
                
                if np.issubdtype(x.dtype, np.number) and np.issubdtype(y.dtype, np.number):
                    ax.scatter(x, y)
                else:
                    ax.plot(y)
                
                ax.set_xlabel(self.csv_x.currentText())
                ax.set_ylabel(self.csv_y.currentText())
                ax.set_title(f"{self.csv_y.currentText()} vs {self.csv_x.currentText()}")
                ax.grid(True)
                
                self.win = QMainWindow()
                self.win.setWindowTitle("Gráfico de Señal")
                canvas = FigureCanvas(fig)
                self.win.setCentralWidget(canvas)
                self.win.resize(800, 600)
                self.win.show()               
                self.db.save_signal_analysis(
                    "",
                    'CSV',
                    'plot',
                    {'x_axis': self.csv_x.currentText(), 'y_axis': self.csv_y.currentText()},
                    'success',
                    self.user_id
                )                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al graficar: {str(e)}")
    
    def analyze_csv(self):
        if hasattr(self, 'df') and self.csv_y.currentText():
            try:
                col = self.df[self.csv_y.currentText()]
                
                if np.issubdtype(col.dtype, np.number):                    
                    mean_val = col.mean()
                    std_val = col.std()
                    max_val = col.max()
                    min_val = col.min()
                    
                    result = f"Análisis de {self.csv_y.currentText()}:\n"
                    result += f"Media: {mean_val:.2f}\n"
                    result += f"Desviación: {std_val:.2f}\n"
                    result += f"Máximo: {max_val:.2f}\n"
                    result += f"Mínimo: {min_val:.2f}\n"
                    result += f"Cantidad: {len(col)}"
                else:                   
                    counts = col.value_counts()
                    result = f"Conteo de valores para {self.csv_y.currentText()}:\n"
                    result += counts.to_string()                
                QMessageBox.information(self, "Análisis", result)                
                self.db.save_signal_analysis(
                    "",
                    'CSV',
                    'basic_analysis',
                    {'column': self.csv_y.currentText()},
                    result,
                    self.user_id
                )                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error en análisis: {str(e)}")
class MainWindow:
    def __new__(cls, user_id, user_type, db):
        """Factory method para crear la ventana adecuada según el tipo de usuario"""
        if user_type == 'imagen':
            return ImageExpertWindow(user_id, db)
        else:
            return SignalExpertWindow(user_id, db)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    db = DatabaseManager()        
    if not db.login_user("admin_img", "admin123"):
        db.register_user("admin_img", "admin123", "imagen")
    if not db.login_user("admin_sig", "admin123"):
        db.register_user("admin_sig", "admin123", "senal")    
    login = LoginWindow(db)
    login.show()
    sys.exit(app.exec_())
