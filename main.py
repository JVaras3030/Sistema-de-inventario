import os
import sys
import pandas as pd
import qrcode
import shutil
from datetime import datetime
import bcrypt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QStackedWidget, QFormLayout, QMessageBox, QDialog, QComboBox, 
    QMenu, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCharts import (
    QChart, QChartView, QPieSeries, QPieSlice, 
    QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
)
import re

# Primero, definir constantes y configuraciones globales mejoradas
SYSTEM_CONFIG = {
    "APP": {
        "name": "Sistema de Gestión de Máquinas",
        "version": "2.0",
        "company": "Punto Ticket",
        "theme": "modern"  # modern, classic, dark
    },
    "COLORES": {
        "primario": "#8c42f4",
        "secundario": "#6b32b8",
        "fondo": "#f8f9fa",
        "texto": "#202124",
        "exito": "#34a853",
        "error": "#ea4335",
        "advertencia": "#fbbc05",
        "hover_primario": "#7535d4",
        "hover_exito": "#2d8f45",
        "fila_alerta": "#ffcccc",
        "fila_activa": "#e8f5e9",
        "dark_primary": "#1e1e1e",
        "dark_secondary": "#252525"
    },
    "RUTAS": {
        "data": "data",
        "qr": "qr_codes",
        "logs": "logs",
        "backups": "backups",
        "reports": "reports",
        "templates": "templates"
    },
    "ARCHIVOS": {
        "maquinas": os.path.join("data", "maquinas.csv"),
        "prestamos": os.path.join("data", "prestamos.csv"),
        "supervisores": os.path.join("data", "supervisores.csv"),
        "usuarios": os.path.join("data", "users.csv"),
        "historial": os.path.join("data", "historial.csv"),
        "mantenimiento": os.path.join("data", "mantenimiento.csv")
    },
    "INTERVALOS": {
        "actualizacion_dashboard": 10000,  # 10 segundos
        "actualizacion_prestamos": 5000,   # 5 segundos
        "backup_automatico": 3600000,      # 1 hora
        "timeout_sesion": 1800000,         # 30 minutos
        "notificaciones": 300000
    },
    "LIMITES": {
        "max_prestamos_supervisor": 10,
        "dias_alerta_prestamo": 30,
        "max_intentos_login": 3,
        "max_dias_mantenimiento": 90,
        "min_caracteres_password": 8
    },
    "EMAIL": {
        "enabled": True,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "sistema@puntoticket.com",
        "notification_events": [
            "prestamo_nuevo",
            "prestamo_vencido",
            "devolucion",
            "mantenimiento_requerido"
        ]
    },
    "ROLES": {
        "admin": {
            "nombre": "Administrador",
            "permisos": ["all"]
        },
        "supervisor": {
            "nombre": "Supervisor",
            "permisos": [
                "ver_inventario",
                "prestar",
                "devolver",
                "ver_reportes"
            ]
        },
        "tecnico": {
            "nombre": "Técnico",
            "permisos": [
                "ver_inventario",
                "registrar_mantenimiento",
                "ver_reportes"
            ]
        }
    }
}

# Mejoras en el manejo de excepciones
class SistemaError(Exception):
    """Clase base para excepciones del sistema"""
    pass

class DataBaseError(SistemaError):
    """Error en operaciones con archivos CSV"""
    pass

class ValidationError(SistemaError):
    """Error en validación de datos"""
    pass

# Clase para manejo de logs
class Logger:
    def __init__(self, log_file="sistema.log"):
        self.log_file = log_file
        
    def log(self, mensaje, tipo="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} [{tipo}] {mensaje}\n")

# Clase para manejo de base de datos
class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.logger = Logger()
        self.create_data_directory()
        
    def create_data_directory(self):
        """Crear estructura de directorios necesaria"""
        os.makedirs("data", exist_ok=True)
        os.makedirs(self.config["ARCHIVOS"]["qr_codes"], exist_ok=True)
        
    def init_database(self):
        """Inicializar archivos CSV si no existen"""
        try:
            for archivo, ruta in self.config["ARCHIVOS"].items():
                if archivo != "qr_codes" and not os.path.exists(ruta):
                    self.create_empty_csv(archivo)
            self.logger.log("Base de datos inicializada correctamente")
        except Exception as e:
            self.logger.log(f"Error al inicializar base de datos: {str(e)}", "ERROR")
            raise DataBaseError(f"Error al inicializar base de datos: {str(e)}")
    
    def create_empty_csv(self, tipo):
        """Crear archivos CSV vacíos con sus columnas correspondientes"""
        columnas = {
            "maquinas": ["ID", "Nombre", "Estado", "Ubicacion", "Ultima_Actualizacion", "Categoria", "Notas"],
            "prestamos": ["ID_Maquina", "Supervisor", "Fecha_Prestamo", "Fecha_Devolucion", "Status", "Ubicacion", "Notas"],
            "supervisores": ["Supervisor", "Telefono", "Email", "Departamento", "Fecha_Registro", "Estado", "Notas"],
            "usuarios": ["username", "password_hash", "role", "ultimo_acceso"]
        }
        
        pd.DataFrame(columns=columnas[tipo]).to_csv(self.config["ARCHIVOS"][tipo], index=False)

# Clase para manejo de sesión
class SessionManager:
    def __init__(self):
        self.session_data = {}
        self.last_activity = datetime.now()
        
    def update_activity(self):
        self.last_activity = datetime.now()
        
    def is_session_expired(self, timeout):
        return (datetime.now() - self.last_activity).total_seconds() * 1000 > timeout

class BackupManager:
    def __init__(self, config):
        self.config = config
        self.backup_dir = config["ARCHIVOS"]["backups"]
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def crear_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)
        
        for nombre, ruta in self.config["ARCHIVOS"].items():
            if nombre not in ["qr_codes", "logs", "backups"]:
                if os.path.exists(ruta):
                    shutil.copy2(ruta, os.path.join(backup_path, f"{nombre}.csv"))
        
        return backup_path

    def restaurar_backup(self, backup_path):
        for nombre, ruta in self.config["ARCHIVOS"].items():
            if nombre not in ["qr_codes", "logs", "backups"]:
                backup_file = os.path.join(backup_path, f"{nombre}.csv")
                if os.path.exists(backup_file):
                    shutil.copy2(backup_file, ruta)

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.users_file = "users.csv"
        self.setWindowTitle("Login")
        self.setFixedSize(300, 200)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        self.usuario = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        
        btn_login = QPushButton("Ingresar")
        btn_login.clicked.connect(self.verificar_login)
        
        layout.addWidget(QLabel("Usuario:"))
        layout.addWidget(self.usuario)
        layout.addWidget(QLabel("Contraseña:"))
        layout.addWidget(self.password)
        layout.addWidget(btn_login)
        
        self.setLayout(layout)
    
    def verificar_login(self):
        username = self.usuario.text().strip()
        password = self.password.text().encode('utf-8')
        
        if not os.path.exists(self.users_file):
            QMessageBox.critical(self, "Error", "No hay usuarios registrados.")
            return
        
        try:
            df = pd.read_csv(self.users_file)
            user = df[df['username'] == username]
            
            if user.empty:
                QMessageBox.warning(self, "Error", "Usuario no encontrado.")
                return
                
            stored_hash = user.iloc[0]['password_hash'].encode('utf-8')
            
            if bcrypt.checkpw(password, stored_hash):
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Contraseña incorrecta.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error de autenticación: {str(e)}")

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistema de Gestión")
        self.setMinimumSize(1270,720)
        
        # Inicializar archivos CSV y estructuras de datos
        self.init_archivos()
        
        # Configurar la interfaz de usuario
        self.initUI()
        
        # Configurar temporizadores para actualizaciones
        self.init_timers()
        
    def init_archivos(self):
        """Inicializa los archivos CSV necesarios"""
        self.archivo_maquinas = "maquinas.csv"
        self.archivo_prestamos = "prestamos.csv"
        self.archivo_supervisores = "supervisores.csv"
        
        # Crear archivos si no existen
        if not os.path.exists(self.archivo_prestamos):
            pd.DataFrame(columns=[
                'ID_Maquina', 'Supervisor', 'Fecha_Prestamo', 
                'Fecha_Devolucion', 'Status', 'Ubicacion', 'Notas'
            ]).to_csv(self.archivo_prestamos, index=False)
        
        if not os.path.exists(self.archivo_supervisores):
            pd.DataFrame(columns=[
                'Supervisor', 'Telefono', 'Email', 'Departamento',
                'Fecha_Registro', 'Estado'
            ]).to_csv(self.archivo_supervisores, index=False)
            
        if not os.path.exists(self.archivo_maquinas):
            pd.DataFrame(columns=[
                'ID', 'Nombre', 'Estado', 'Ubicacion', 
                'Ultima_Actualizacion', 'Categoria', 'Notas'
            ]).to_csv(self.archivo_maquinas, index=False)
            
    def init_timers(self):
        """Inicializa los temporizadores para actualizaciones automáticas"""
        # Timer para actualizar dashboard
        self.timer_dashboard = QTimer(self)
        self.timer_dashboard.timeout.connect(self.actualizar_dashboard)
        self.timer_dashboard.start(10000)  # Actualizar cada 10 segundos
        
        # Timer para actualizar préstamos
        self.timer_prestamos = QTimer(self)
        self.timer_prestamos.timeout.connect(self.actualizar_prestamos_activos)
        self.timer_prestamos.start(5000)  # Actualizar cada 5 segundos

    def initUI(self):
        # Configuración principal
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Layout principal con margen reducido
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Barra lateral mejorada
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(250)
        self.sidebar.setStyleSheet(f"""
            QWidget {{
                background-color: {SYSTEM_CONFIG['COLORES']['primario']};
                border-right: 1px solid {SYSTEM_CONFIG['COLORES']['secundario']};
            }}
            QPushButton {{
                text-align: left;
                padding: 15px;
                padding-left: 20px;
                border: none;
                border-radius: 0;
                color: white;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {SYSTEM_CONFIG['COLORES']['hover_primario']};
            }}
            QPushButton:pressed {{
                background-color: {SYSTEM_CONFIG['COLORES']['secundario']};
            }}
        """)
        
        # Layout de la barra lateral
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # Logo o título
        logo_label = QLabel("Sistema de Gestión")
        logo_label.setStyleSheet("""
            color: white;
            font-size: 18px;
            font-weight: bold;
            padding: 20px;
            background-color: #5d2aa8;
        """)
        
        # Botones de navegación mejorados
        self.btn_dashboard = QPushButton("🏠 Dashboard")
        self.btn_inventario = QPushButton("📦 Inventario")
        self.btn_prestamos = QPushButton("↗️ Préstamos")
        self.btn_devoluciones = QPushButton("↙️ Devoluciones")
        self.btn_supervisores = QPushButton("👥 Supervisores")
        
        # Usuario actual y cerrar sesión
        user_frame = QWidget()
        user_layout = QVBoxLayout(user_frame)
        self.label_usuario = QLabel("👤 Admin")
        self.btn_cerrar_sesion = QPushButton("🚪 Cerrar Sesión")
        self.btn_cerrar_sesion.clicked.connect(self.cerrar_sesion)
        
        user_frame.setStyleSheet("""
            QLabel {
                color: white;
                padding: 10px;
                font-size: 12px;
            }
            QPushButton {
                color: #ffcccc;
            }
        """)
        
        user_layout.addWidget(self.label_usuario)
        user_layout.addWidget(self.btn_cerrar_sesion)
        
        # Agregar elementos a la barra lateral
        sidebar_layout.addWidget(logo_label)
        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(self.btn_dashboard)
        sidebar_layout.addWidget(self.btn_inventario)
        sidebar_layout.addWidget(self.btn_prestamos)
        sidebar_layout.addWidget(self.btn_devoluciones)
        sidebar_layout.addWidget(self.btn_supervisores)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(user_frame)
        
        # Área de contenido mejorada
        content_frame = QWidget()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Barra superior
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        
        # Título de la sección actual
        self.titulo_seccion = QLabel("Dashboard")
        self.titulo_seccion.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #333;
        """)
        
        # Búsqueda global
        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText("🔍 Buscar...")
        self.busqueda.setFixedWidth(300)
        self.busqueda.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        self.busqueda.textChanged.connect(self.buscar_global)
        
        top_bar_layout.addWidget(self.titulo_seccion)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.busqueda)
        
        # Área de contenido principal
        self.content_area = QStackedWidget()
        
        # Agregar elementos al layout de contenido
        content_layout.addWidget(top_bar)
        content_layout.addWidget(self.content_area)
        
        # Agregar todo al layout principal
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(content_frame)
        
        # Inicializar páginas
        self.init_dashboard()
        self.init_inventario()
        self.init_prestamos()
        self.init_devoluciones()
        self.init_supervisores()
        
        # Conectar botones con actualización de título
        self.btn_dashboard.clicked.connect(lambda: self.cambiar_seccion(0, "Dashboard"))
        self.btn_inventario.clicked.connect(lambda: self.cambiar_seccion(1, "Inventario"))
        self.btn_prestamos.clicked.connect(lambda: self.cambiar_seccion(2, "Préstamos"))
        self.btn_devoluciones.clicked.connect(lambda: self.cambiar_seccion(3, "Devoluciones"))
        self.btn_supervisores.clicked.connect(lambda: self.cambiar_seccion(4, "Supervisores"))

    def cambiar_seccion(self, index, titulo):
        """Cambia la sección actual y actualiza el título"""
        self.content_area.setCurrentIndex(index)
        self.titulo_seccion.setText(titulo)
        if index == 2:  # Si es la sección de préstamos
            self.actualizar_tabla_disponibles()
        elif index == 3:  # Si es la sección de devoluciones
            self.actualizar_prestamos_activos()

    def buscar_global(self, texto):
        """Implementa la búsqueda global en todas las tablas"""
        # Implementar la lógica de búsqueda según la sección actual
        current_index = self.content_area.currentIndex()
        if current_index == 1:  # Inventario
            self.buscar_en_inventario(texto)
        elif current_index == 2:  # Préstamos
            self.buscar_en_prestamos(texto)
        elif current_index == 3:  # Devoluciones
            self.buscar_en_devoluciones(texto)
        elif current_index == 4:  # Supervisores
            self.buscar_en_supervisores(texto)

    def cerrar_sesion(self):
        """Cierra la sesión actual y vuelve al login"""
        reply = QMessageBox.question(
            self, 'Confirmar',
            '¿Está seguro que desea cerrar sesión?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
            login = LoginWindow()
            if login.exec() == QDialog.DialogCode.Accepted:
                self.show()

    def init_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Gráfico de estado de máquinas
        self.chart_estado = QChart()
        self.series_estado = QPieSeries()
        self.chart_estado.addSeries(self.series_estado)
        self.chart_estado.setTitle("Estado de Máquinas")
        
        chart_view_estado = QChartView(self.chart_estado)
        chart_view_estado.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Gráfico de préstamos por supervisor
        self.chart_prestamos = QChart()
        self.series_prestamos = QBarSeries()
        self.chart_prestamos.addSeries(self.series_prestamos)
        self.chart_prestamos.setTitle("Préstamos por Supervisor")
        
        chart_view_prestamos = QChartView(self.chart_prestamos)
        chart_view_prestamos.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Tabla de últimas actividades
        self.tabla_actividades = QTableWidget()
        self.tabla_actividades.setColumnCount(3)
        self.tabla_actividades.setHorizontalHeaderLabels(["Fecha", "Máquina", "Acción"])
        self.tabla_actividades.verticalHeader().setVisible(False)
        
        # ---------------------------
        # Diseño final
        # ---------------------------
        layout.addWidget(chart_view_estado, 40)
        layout.addWidget(chart_view_prestamos, 40)
        layout.addWidget(QLabel("📋 Últimas Actividades:"))
        layout.addWidget(self.tabla_actividades, 20)
        
        self.content_area.addWidget(page)
        
        # Actualizar datos del dashboard
        self.actualizar_dashboard()

    def actualizar_dashboard(self):
        try:
            # Actualizar gráfico de estado de máquinas
            df_maquinas = pd.read_csv(self.archivo_maquinas)
            disponibles = df_maquinas[df_maquinas['Estado'] == 'Disponible'].shape[0]
            prestadas = df_maquinas[df_maquinas['Estado'] == 'Prestado'].shape[0]
            mantenimiento = df_maquinas[df_maquinas['Estado'] == 'Mantenimiento'].shape[0]
            
            self.series_estado.clear()
            self.series_estado.append("Disponibles", disponibles)
            self.series_estado.append("Prestadas", prestadas)
            self.series_estado.append("Mantenimiento", mantenimiento)
            
            # Actualizar gráfico de préstamos por supervisor
            df_prestamos = pd.read_csv(self.archivo_prestamos)
            prestamos_activos = df_prestamos[df_prestamos['Status'] == 'Prestado']
            prestamos_por_supervisor = prestamos_activos['Supervisor'].value_counts()

            # Limpiar gráfico existente
            self.chart_prestamos.removeAllSeries()
            for axis in self.chart_prestamos.axes():
                self.chart_prestamos.removeAxis(axis)

            # Crear nueva serie de barras
            self.series_prestamos = QBarSeries()
            bar_set = QBarSet("Préstamos")
            bar_set.append(prestamos_por_supervisor.values.tolist())
            self.series_prestamos.append(bar_set)
            self.chart_prestamos.addSeries(self.series_prestamos)

            # Configurar ejes
            axis_x = QBarCategoryAxis()
            axis_x.append(prestamos_por_supervisor.index.tolist())
            
            axis_y = QValueAxis()
            axis_y.setRange(0, prestamos_por_supervisor.max() + 1 if not prestamos_por_supervisor.empty else 1)

            # Añadir ejes al gráfico
            self.chart_prestamos.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            self.chart_prestamos.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

            # Conectar ejes con la serie
            self.series_prestamos.attachAxis(axis_x)
            self.series_prestamos.attachAxis(axis_y)

            # Actualizar tabla de últimas actividades
            df_actividades = pd.concat([
                df_maquinas[['Ultima_Actualizacion', 'ID', 'Estado']].rename(
                    columns={'Ultima_Actualizacion': 'Fecha', 'ID': 'Máquina', 'Estado': 'Acción'}),
                df_prestamos[['Fecha_Prestamo', 'ID_Maquina', 'Status']].rename(
                    columns={'Fecha_Prestamo': 'Fecha', 'ID_Maquina': 'Máquina', 'Status': 'Acción'}),
                df_prestamos[['Fecha_Devolucion', 'ID_Maquina', 'Status']].rename(
                    columns={'Fecha_Devolucion': 'Fecha', 'ID_Maquina': 'Máquina', 'Status': 'Acción'})
            ])
            df_actividades = df_actividades.dropna().sort_values(by='Fecha', ascending=False).head(10)
            
            self.tabla_actividades.setRowCount(len(df_actividades))
            for row_idx, row in df_actividades.iterrows():
                self.tabla_actividades.setItem(row_idx, 0, QTableWidgetItem(row['Fecha']))
                self.tabla_actividades.setItem(row_idx, 1, QTableWidgetItem(row['Máquina']))
                self.tabla_actividades.setItem(row_idx, 2, QTableWidgetItem(row['Acción']))
            
            self.tabla_actividades.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar el dashboard: {str(e)}")

    def init_inventario(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Panel superior con estadísticas
        stats_frame = QWidget()
        stats_layout = QHBoxLayout(stats_frame)
        
        # Estadísticas del inventario
        stats_group = QGroupBox("📊 Estadísticas de Inventario")
        stats_group_layout = QVBoxLayout()
        self.label_total_maquinas = QLabel("Total máquinas: 0")
        self.label_maquinas_disponibles = QLabel("Máquinas disponibles: 0")
        self.label_maquinas_prestadas = QLabel("Máquinas prestadas: 0")
        
        for label in [self.label_total_maquinas, self.label_maquinas_disponibles, self.label_maquinas_prestadas]:
            label.setStyleSheet("font-size: 12px; padding: 5px;")
        
        stats_group_layout.addWidget(self.label_total_maquinas)
        stats_group_layout.addWidget(self.label_maquinas_disponibles)
        stats_group_layout.addWidget(self.label_maquinas_prestadas)
        stats_group.setLayout(stats_group_layout)
        stats_layout.addWidget(stats_group)
        
        # Formulario de registro mejorado
        form_frame = QWidget()
        form_layout = QFormLayout(form_frame)
        
        self.registro_id = QLineEdit()
        self.registro_nombre = QLineEdit()
        self.registro_categoria = QComboBox()
        self.registro_categoria.addItems(['Herramienta', 'Equipo', 'Zebras', 'Impresoras', 'Otro'])
        self.registro_estado = QComboBox()
        self.registro_estado.addItems(['Disponible', 'Mantenimiento', 'Prestado'])
        self.registro_ubicacion = QLineEdit()
        self.registro_notas = QTextEdit()
        self.registro_notas.setMaximumHeight(60)
        
        # Validación en tiempo real para ID
        self.registro_id.textChanged.connect(self.validar_id_en_tiempo_real)
        
        # Botones mejorados
        btn_registrar = QPushButton("➕ Registrar Nueva Máquina")
        btn_registrar.clicked.connect(self.registrar_nueva_maquina)
        btn_registrar.setStyleSheet(self.get_button_style('exito'))
        
        btn_generar_qr = QPushButton("🔲 Generar QR")
        btn_generar_qr.clicked.connect(lambda: self.generar_qr(self.registro_id.text()))
        btn_generar_qr.setStyleSheet(self.get_button_style('primario'))
        
        # Añadir elementos al formulario con iconos
        form_layout.addRow("🔖 ID Único:", self.registro_id)
        form_layout.addRow("🏷️ Nombre:", self.registro_nombre)
        form_layout.addRow("📁 Categoría:", self.registro_categoria)
        form_layout.addRow("🔄 Estado:", self.registro_estado)
        form_layout.addRow("📍 Ubicación:", self.registro_ubicacion)
        form_layout.addRow("📝 Notas:", self.registro_notas)
        form_layout.addRow(btn_registrar)
        form_layout.addRow(btn_generar_qr)
        
        # Tabla de inventario mejorada
        self.tabla_inventario = QTableWidget()
        self.tabla_inventario.setColumnCount(7)
        self.tabla_inventario.setHorizontalHeaderLabels([
            "ID", "Nombre", "Categoría", "Estado", 
            "Ubicación", "Última Actualización", "Notas"
        ])
        self.tabla_inventario.verticalHeader().setVisible(False)
        self.tabla_inventario.setSortingEnabled(True)
        self.tabla_inventario.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_inventario.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla_inventario.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        
        # Botones de filtro
        filtro_frame = QWidget()
        filtro_layout = QHBoxLayout(filtro_frame)
        
        self.filtro_categoria = QComboBox()
        self.filtro_categoria.addItems(['Impresoras', 'Herramienta', 'PC', 'Zebras', 'Otro'])
        self.filtro_estado = QComboBox()
        self.filtro_estado.addItems(['Todos', 'Disponible', 'Prestado', 'Mantenimiento'])
        
        btn_filtrar = QPushButton("🔍 Filtrar")
        btn_filtrar.clicked.connect(self.aplicar_filtros)
        btn_filtrar.setStyleSheet(self.get_button_style('primario'))
        
        btn_exportar = QPushButton("📥 Exportar")
        btn_exportar.clicked.connect(self.exportar_inventario)
        btn_exportar.setStyleSheet(self.get_button_style('primario'))
        
        filtro_layout.addWidget(QLabel("Categoría:"))
        filtro_layout.addWidget(self.filtro_categoria)
        filtro_layout.addWidget(QLabel("Estado:"))
        filtro_layout.addWidget(self.filtro_estado)
        filtro_layout.addWidget(btn_filtrar)
        filtro_layout.addWidget(btn_exportar)
        
        # Layout final
        layout.addWidget(stats_frame)
        layout.addWidget(form_frame)
        layout.addWidget(filtro_frame)
        layout.addWidget(QLabel("📋 Inventario Actual:"))
        layout.addWidget(self.tabla_inventario)
        
        self.content_area.addWidget(page)
        self.actualizar_inventario()
        self.actualizar_estadisticas_inventario()

    def get_button_style(self, tipo):
        return f"""
            QPushButton {{
                background-color: {SYSTEM_CONFIG['COLORES'][tipo]};
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: darker({SYSTEM_CONFIG['COLORES'][tipo]}, 110%); }}
        """

    def actualizar_estadisticas_inventario(self):
        try:
            df = pd.read_csv(self.archivo_maquinas)
            total = len(df)
            disponibles = len(df[df['Estado'] == 'Disponible'])
            prestadas = len(df[df['Estado'] == 'Prestado'])
            
            self.label_total_maquinas.setText(f"Total máquinas: {total}")
            self.label_maquinas_disponibles.setText(f"Máquinas disponibles: {disponibles}")
            self.label_maquinas_prestadas.setText(f"Máquinas prestadas: {prestadas}")
        except Exception as e:
            print(f"Error al actualizar estadísticas: {str(e)}")

    def aplicar_filtros(self):
        try:
            df = pd.read_csv(self.archivo_maquinas)
            categoria = self.filtro_categoria.currentText()
            estado = self.filtro_estado.currentText()
            
            if (categoria != 'Todas'):
                df = df[df['Categoria'] == categoria]
            if (estado != 'Todos'):
                df = df[df['Estado'] == estado]
                
            self.actualizar_tabla_con_df(df)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al aplicar filtros: {str(e)}")

    def actualizar_tabla_con_df(self, df):
        self.tabla_inventario.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                if col_idx == 3:  # Columna de estado
                    if value == 'Prestado':
                        item.setBackground(QColor('#ffcccc'))
                    elif value == 'Mantenimiento':
                        item.setBackground(QColor('#ffffcc'))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tabla_inventario.setItem(row_idx, col_idx, item)
        
        self.tabla_inventario.resizeColumnsToContents()

    def exportar_inventario(self):
        try:
            df = pd.read_csv(self.archivo_maquinas)
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"inventario_{fecha}.xlsx"
            
            df.to_excel(nombre_archivo, index=False, sheet_name='Inventario')
            QMessageBox.information(self, "Éxito", f"Inventario exportado como {nombre_archivo}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar: {str(e)}")

    def validar_id_en_tiempo_real(self):
        id = self.registro_id.text()
        if not re.match(r'^[A-Z0-9-]{5,}$', id):
            self.registro_id.setStyleSheet("border: 2px solid red;")
        else:
            self.registro_id.setStyleSheet("border: 2px solid green;")

    def registrar_nueva_maquina(self):
        id = self.registro_id.text().strip()
        nombre = self.registro_nombre.text().strip()
        estado = self.registro_estado.currentText()
        ubicacion = self.registro_ubicacion.text().strip()
        
        # Validación avanzada
        if not all([id, nombre, ubicacion]):
            QMessageBox.warning(self, "Error", "🚨 Todos los campos son obligatorios")
            return
        
        if not re.match(r'^[A-Z0-9-]{5,}$', id):
            QMessageBox.warning(self, "Error", 
                "Formato de ID inválido:\n"
                "• Mínimo 5 caracteres\n"
                "• Solo mayúsculas, números y guiones")
            return
        
        try:
            # Verificar unicidad del ID
            df = pd.read_csv(self.archivo_maquinas)
            if id in df['ID'].values:
                QMessageBox.warning(self, "Error", "⚠️ Este ID ya está registrado")
                return
            
            # Registrar nueva máquina
            nueva_maquina = pd.DataFrame([{
                'ID': id,
                'Nombre': nombre,
                'Estado': estado,
                'Ubicacion': ubicacion,
                'Ultima_Actualizacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            
            nueva_maquina.to_csv(self.archivo_maquinas, mode='a', header=False, index=False)
            
            # Generar QR y limpiar campos
            self.generar_qr(id)
            self.limpiar_formulario()
            self.actualizar_inventario()
            
            QMessageBox.information(self, "Éxito", 
                f"✅ Máquina registrada:\n"
                f"ID: {id}\n"
                f"QR generado en: /qr_codes/{id}.png")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"🔥 Error crítico: {str(e)}")

    def limpiar_formulario(self):
        self.registro_id.clear()
        self.registro_nombre.clear()
        self.registro_ubicacion.clear()
        self.registro_estado.setCurrentIndex(0)

    def generar_qr(self, id_maquina):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4  # Corregido: eliminado los dos puntos
        )
        qr.add_data(id_maquina)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        os.makedirs("qr_codes", exist_ok=True)
        img.save(f"qr_codes/{id_maquina}.png")

    def validar_id_maquina(self, id_maquina):
        # Validación de formato
        if not re.match(r'^[A-Z0-9-]{5,}$', id_maquina):
            raise ValidationError("ID inválido: Use mayúsculas, números y guiones (mínimo 5 caracteres)")
        
        # Verificar duplicados
        df = pd.read_csv(self.archivo_maquinas)
        if id_maquina in df['ID'].values:
            raise ValidationError("Este ID ya está registrado")
        
        return True

    def validar_prestamo(self, supervisor, id_maquina):
        df_prestamos = pd.read_csv(self.archivo_prestamos)
        
        # Verificar límite de préstamos por supervisor
        prestamos_activos = df_prestamos[
            (df_prestamos['Supervisor'] == supervisor) & 
            (df_prestamos['Status'] == 'Prestado')
        ]
        
        if len(prestamos_activos) >= SYSTEM_CONFIG["LIMITES"]["max_prestamos_supervisor"]:
            raise ValidationError(f"El supervisor ha alcanzado el límite de préstamos ({SYSTEM_CONFIG['LIMITES']['max_prestamos_supervisor']})")
        
        # Verificar disponibilidad de la máquina
        df_maquinas = pd.read_csv(self.archivo_maquinas)
        maquina = df_maquinas[df_maquinas['ID'] == id_maquina]
        
        if maquina.empty:
            raise ValidationError("Máquina no encontrada")
        
        if maquina.iloc[0]['Estado'] != 'Disponible':
            raise ValidationError("La máquina no está disponible")
        
        return True
    def init_prestamos(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Formulario de préstamo
        form_frame = QWidget()
        form_layout = QFormLayout(form_frame)
        
        self.prestamo_supervisor = QComboBox()
        self.cargar_supervisores()
        self.prestamo_ubicacion = QLineEdit()
        self.prestamo_ids = QLineEdit()
        self.prestamo_ids.setPlaceholderText("Ingrese IDs separados por comas")
        
        # Botón con estilo personalizado
        btn_prestar = QPushButton("Registrar Préstamo")
        btn_prestar.clicked.connect(self.registrar_prestamo)
        btn_prestar.setStyleSheet(f"""
            QPushButton {{
                background-color: {SYSTEM_CONFIG['COLORES']['exito']};
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2d8f45; }}
        """)
        
        # Añadir elementos al formulario
        form_layout.addRow("Supervisor:", self.prestamo_supervisor)
        form_layout.addRow("Ubicación:", self.prestamo_ubicacion)
        form_layout.addRow("IDs de Máquinas:", self.prestamo_ids)
        form_layout.addRow(btn_prestar)
        
        # Tabla de máquinas disponibles
        self.tabla_disponibles = QTableWidget()
        self.tabla_disponibles.setColumnCount(5)
        self.tabla_disponibles.setHorizontalHeaderLabels([
            "ID", "Nombre", "Estado", "Ubicación", "Última Actualización"
        ])
        self.tabla_disponibles.verticalHeader().setVisible(False)
        self.tabla_disponibles.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_disponibles.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.actualizar_tabla_disponibles()
        
        # ---------------------------
        # Diseño final
        # ---------------------------
        layout.addWidget(form_frame)
        layout.addWidget(QLabel("📋 Máquinas Disponibles:"))
        layout.addWidget(self.tabla_disponibles)
        
        self.content_area.addWidget(page)

    def cargar_supervisores(self):
        try:
            df_supervisores = pd.read_csv(self.archivo_supervisores)
            self.prestamo_supervisor.clear()
            self.prestamo_supervisor.addItems(df_supervisores['Supervisor'].tolist())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar supervisores: {str(e)}")

    def actualizar_tabla_disponibles(self):
        try:
            df = pd.read_csv(self.archivo_maquinas)
            disponibles = df[df['Estado'] == 'Disponible']
            self.tabla_disponibles.setRowCount(len(disponibles))
            
            for row_idx, row in disponibles.iterrows():
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.tabla_disponibles.setItem(row_idx, col_idx, item)
            
            self.tabla_disponibles.resizeColumnsToContents()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar inventario: {str(e)}")

    def registrar_prestamo(self):
        supervisor = self.prestamo_supervisor.currentText().strip()
        ubicacion = self.prestamo_ubicacion.text().strip()
        ids = self.prestamo_ids.text().strip().split(',')
        
        if not supervisor or not ubicacion or not ids:
            QMessageBox.warning(self, "Advertencia", "Todos los campos son obligatorios")
            return
        
        try:
            maquinas = pd.read_csv(self.archivo_maquinas)
            prestamos = pd.read_csv(self.archivo_prestamos)
            
            for id_maquina in ids:
                id_maquina = id_maquina.strip()
                if not id_maquina:
                    continue
                
                mask_maquina = maquinas['ID'] == id_maquina
                if not mask_maquina.any():
                    QMessageBox.warning(self, "Error", f"ID {id_maquina} no encontrado en inventario")
                    continue
                
                maquinas.loc[mask_maquina, 'Estado'] = 'Prestado'
                maquinas.loc[mask_maquina, 'Ubicacion'] = ubicacion
                
                nuevo_prestamo = pd.DataFrame([{
                    'ID_Maquina': id_maquina,
                    'Supervisor': supervisor,
                    'Fecha_Prestamo': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Fecha_Devolucion': '',
                    'Status': 'Prestado'
                }])
                
                prestamos = pd.concat([prestamos, nuevo_prestamo], ignore_index=True)
            
            maquinas.to_csv(self.archivo_maquinas, index=False)
            prestamos.to_csv(self.archivo_prestamos, index=False)
            
            # Actualizaciones en tiempo real
            self.actualizar_prestamos_activos()
            self.actualizar_tabla_disponibles()
            self.actualizar_dashboard()
            
            QMessageBox.information(self, "Éxito", "Préstamos registrados correctamente")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al registrar préstamo: {str(e)}")

    def init_devoluciones(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Panel superior con estadísticas mejorado
        stats_frame = QWidget()
        stats_layout = QHBoxLayout(stats_frame)
        
        # Estadísticas detalladas
        stats_group = QGroupBox("📊 Estadísticas de Préstamos")
        stats_group_layout = QVBoxLayout()
        self.label_total_prestamos = QLabel("Total préstamos activos: 0")
        self.label_prestamos_hoy = QLabel("Préstamos de hoy: 0")
        self.label_prestamos_vencidos = QLabel("Préstamos vencidos: 0")
        
        for label in [self.label_total_prestamos, self.label_prestamos_hoy, self.label_prestamos_vencidos]:
            label.setStyleSheet("font-size: 12px; padding: 5px;")
        
        stats_group_layout.addWidget(self.label_total_prestamos)
        stats_group_layout.addWidget(self.label_prestamos_hoy)
        stats_group_layout.addWidget(self.label_prestamos_vencidos)
        stats_group.setLayout(stats_group_layout)
        stats_layout.addWidget(stats_group)
        
        # Formulario de devolución mejorado
        form_frame = QWidget()
        form_layout = QFormLayout(form_frame)
        
        self.devolucion_supervisor = QComboBox()
        self.devolucion_supervisor.setStyleSheet("padding: 5px;")
        self.devolucion_id = QLineEdit()
        self.devolucion_id.setPlaceholderText("Escanee o ingrese el ID")
        self.devolucion_ubicacion = QLineEdit()
        self.devolucion_ubicacion.setPlaceholderText("Ubicación final")
        self.devolucion_notas = QTextEdit()
        self.devolucion_notas.setPlaceholderText("Observaciones de la devolución")
        self.devolucion_notas.setMaximumHeight(60)
        
        # Botones mejorados
        btn_devolver = QPushButton("📦 Registrar Devolución")
        btn_devolver.clicked.connect(self.procesar_devolucion)
        btn_devolver.setStyleSheet(f"""
            QPushButton {{
                background-color: {SYSTEM_CONFIG['COLORES']['exito']};
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2d8f45; }}
        """)
        
        btn_cargar_prestadas = QPushButton("🔄 Cargar Máquinas Prestadas")
        btn_cargar_prestadas.clicked.connect(self.cargar_maquinas_prestadas)
        btn_cargar_prestadas.setStyleSheet(f"""
            QPushButton {{
                background-color: {SYSTEM_CONFIG['COLORES']['primario']};
                color: white;
                padding: 10px;
                border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: #7535d4; }}SSS
        """)
        
        # Información detallada del préstamo
        self.info_prestamo = QTextEdit()
        self.info_prestamo.setReadOnly(True)
        self.info_prestamo.setMaximumHeight(100)
        self.info_prestamo.setStyleSheet("background-color: #f8f9fa; border-radius: 5px;")
        
        # Agregar elementos al formulario
        form_layout.addRow("👤 Supervisor:", self.devolucion_supervisor)
        form_layout.addRow("🔖 ID de Máquina:", self.devolucion_id)
        form_layout.addRow("📍 Ubicación:", self.devolucion_ubicacion)
        form_layout.addRow("📝 Notas:", self.devolucion_notas)
        form_layout.addRow("ℹ️ Información del préstamo:", self.info_prestamo)
        form_layout.addRow(btn_devolver)
        form_layout.addRow(btn_cargar_prestadas)
        
        # Tabla de préstamos activos mejorada
        self.tabla_prestamos = QTableWidget()
        self.tabla_prestamos.setColumnCount(7)
        self.tabla_prestamos.setHorizontalHeaderLabels([
            "ID Máquina", "Supervisor", "Fecha Préstamo", 
            "Ubicación", "Estado", "Días Prestado", "Prioridad"
        ])
        self.tabla_prestamos.verticalHeader().setVisible(False)
        self.tabla_prestamos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_prestamos.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla_prestamos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_prestamos.itemClicked.connect(self.mostrar_info_prestamo)
        self.tabla_prestamos.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        # Layout final
        layout.addWidget(stats_frame)
        layout.addWidget(form_frame)
        layout.addWidget(QLabel("📋 Préstamos Activos:"))
        layout.addWidget(self.tabla_prestamos)
        
        self.content_area.addWidget(page)
        
        # Configuración inicial
        self.cargar_supervisores_con_prestamos()
        self.actualizar_prestamos_activos()
        
        # Actualización automática
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.actualizar_prestamos_activos)
        self.timer.start(5000)

    def mostrar_info_prestamo(self, item):
        try:
            row = item.row()
            id_maquina = self.tabla_prestamos.item(row, 0).text()
            supervisor = self.tabla_prestamos.item(row, 1).text()
                    
            # Cargar información detallada
            df_prestamos = pd.read_csv(self.archivo_prestamos)
            df_maquinas = pd.read_csv(self.archivo_maquinas)
            
            prestamo = df_prestamos[(df_prestamos['ID_Maquina'] == id_maquina) & 
                                   (df_prestamos['Status'] == 'Prestado')].iloc[0]
            maquina = df_maquinas[df_maquinas['ID'] == id_maquina].iloc[0]
                                    
            info = f"""Préstamo activo:
            • Máquina: {maquina['Nombre']} (ID: {id_maquina})
            • Supervisor: {supervisor}
            • Fecha de préstamo: {prestamo['Fecha_Prestamo']}
            • Ubicación actual: {maquina['Ubicacion']}
            • Estado: {maquina['Estado']}
            """
            
            self.info_prestamo.setText(info)
            self.devolucion_id.setText(id_maquina)
            self.devolucion_supervisor.setCurrentText(supervisor)
            self.devolucion_ubicacion.setText(maquina['Ubicacion'])
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al mostrar información: {str(e)}")

    def actualizar_estadisticas(self):
        try:
            df = pd.read_csv(self.archivo_prestamos)
            prestamos_activos = df[df['Status'] == 'Prestado']
            prestamos_hoy = prestamos_activos[
                pd.to_datetime(prestamos_activos['Fecha_Prestamo']).dt.date == datetime.now().date()
            ]
            
            self.label_total_prestamos.setText(f"Total préstamos activos: {len(prestamos_activos)}")
            self.label_prestamos_hoy.setText(f"Préstamos de hoy: {len(prestamos_hoy)}")
        except Exception as e:
            print(f"Error al actualizar estadísticas: {str(e)}")

    def actualizar_prestamos_activos(self):
        try:
            self.actualizar_estadisticas()
            
            df = pd.read_csv(self.archivo_prestamos)
            prestamos_activos = df[df['Status'] == 'Prestado']
            
            self.tabla_prestamos.setRowCount(len(prestamos_activos))
            
            for row_idx, row in prestamos_activos.iterrows():
                # Calcular días prestado
                fecha_prestamo = pd.to_datetime(row['Fecha_Prestamo'])
                dias_prestado = (datetime.now() - fecha_prestamo).days
                                                
                # Llenar la tabla
                self.tabla_prestamos.setItem(row_idx, 0, QTableWidgetItem(str(row['ID_Maquina'])))
                self.tabla_prestamos.setItem(row_idx, 1, QTableWidgetItem(str(row['Supervisor'])))
                self.tabla_prestamos.setItem(row_idx, 2, QTableWidgetItem(str(row['Fecha_Prestamo'])))
                self.tabla_prestamos.setItem(row_idx, 3, QTableWidgetItem(str(row['Ubicacion'])))
                self.tabla_prestamos.setItem(row_idx, 4, QTableWidgetItem(str(row['Status'])))
                self.tabla_prestamos.setItem(row_idx, 5, QTableWidgetItem(str(dias_prestado)))
                
                # Resaltar préstamos largos
                if dias_prestado > 30:
                    for col in range(6):
                        self.tabla_prestamos.item(row_idx, col).setBackground(QColor(255, 200, 200))
            
            self.tabla_prestamos.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar préstamos: {str(e)}")

    def cargar_supervisores_con_prestamos(self):
        try:
            df_prestamos = pd.read_csv(self.archivo_prestamos)
            # Obtener supervisores que tienen préstamos activos
            supervisores_con_prestamos = df_prestamos[df_prestamos['Status'] == 'Prestado']['Supervisor'].unique()
            
            self.devolucion_supervisor.clear()
            # Agregar un item por defecto
            self.devolucion_supervisor.addItem("Seleccione un supervisor")
            # Agregar los supervisores con préstamos activos
            self.devolucion_supervisor.addItems(supervisores_con_prestamos)
            
            # Actualizar la tabla con todos los préstamos activos inicialmente
            self.actualizar_prestamos_activos()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar supervisores con préstamos: {str(e)}")

    def cargar_maquinas_prestadas(self):
        try:
            supervisor = self.devolucion_supervisor.currentText().strip()
            if supervisor == "Seleccione un supervisor":
                QMessageBox.warning(self, "Advertencia", "Seleccione un supervisor")
                return
            
            df_prestamos = pd.read_csv(self.archivo_prestamos)
            df_maquinas = pd.read_csv(self.archivo_maquinas)
            
            # Filtrar préstamos activos del supervisor seleccionado
            prestamos_supervisor = df_prestamos[
                (df_prestamos['Supervisor'] == supervisor) & 
                (df_prestamos['Status'] == 'Prestado')
            ]
            
            self.tabla_prestamos.setRowCount(len(prestamos_supervisor))
            
            for row_idx, row in prestamos_supervisor.iterrows():
                # Obtener información de la máquina
                maquina = df_maquinas[df_maquinas['ID'] == row['ID_Maquina']].iloc[0]
                
                # Calcular días prestado
                fecha_prestamo = pd.to_datetime(row['Fecha_Prestamo'])
                dias_prestado = (datetime.now() - fecha_prestamo).days
                
                # Llenar la tabla
                self.tabla_prestamos.setItem(row_idx, 0, QTableWidgetItem(str(row['ID_Maquina'])))
                self.tabla_prestamos.setItem(row_idx, 1, QTableWidgetItem(str(row['Supervisor'])))
                self.tabla_prestamos.setItem(row_idx, 2, QTableWidgetItem(str(row['Fecha_Prestamo'])))
                self.tabla_prestamos.setItem(row_idx, 3, QTableWidgetItem(str(maquina['Ubicacion'])))
                self.tabla_prestamos.setItem(row_idx, 4, QTableWidgetItem(str(maquina['Estado'])))
                self.tabla_prestamos.setItem(row_idx, 5, QTableWidgetItem(str(dias_prestado)))
                
                # Resaltar préstamos largos
                if dias_prestado > 30:
                    for col in range(6):
                        self.tabla_prestamos.item(row_idx, col).setBackground(QColor(255, 200, 200))
            
            self.tabla_prestamos.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar máquinas prestadas: {str(e)}")

    def procesar_devolucion(self):
        id_maquina = self.devolucion_id.text().strip()
        supervisor = self.devolucion_supervisor.currentText().strip()
        
        if not id_maquina or not supervisor:
            QMessageBox.warning(self, "Error", "Todos los campos son obligatorios")
            return
        
        try:
            # Actualizar máquinas
            maquinas_df = pd.read_csv(self.archivo_maquinas)
            mask_maquina = maquinas_df['ID'] == id_maquina
            
            if maquinas_df.loc[mask_maquina, 'Estado'].values[0] != 'Prestado':
                QMessageBox.warning(self, "Error", "La máquina no está prestada")
                return
                
            maquinas_df.loc[mask_maquina, 'Estado'] = 'Disponible'
            maquinas_df.loc[mask_maquina, 'Ubicacion'] = 'Almacén'
            maquinas_df.to_csv(self.archivo_maquinas, index=False)
            
            # Actualizar préstamos
            prestamos_df = pd.read_csv(self.archivo_prestamos)
            mask_prestamo = (prestamos_df['ID_Maquina'] == id_maquina) & \
                           (prestamos_df['Supervisor'] == supervisor) & \
                           (prestamos_df['Status'] == 'Prestado')
            
            prestamos_df.loc[mask_prestamo, 'Status'] = 'Devuelto'
            prestamos_df.loc[mask_prestamo, 'Fecha_Devolucion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            prestamos_df.to_csv(self.archivo_prestamos, index=False)
            
            # Actualizar UI
            self.devolucion_id.clear()
            self.actualizar_prestamos_activos()
            self.actualizar_inventario()
            QMessageBox.information(self, "Éxito", "Devolución registrada exitosamente")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error en devolución: {str(e)}")

    def actualizar_inventario(self):
        try:
            df = pd.read_csv(self.archivo_maquinas)
            self.tabla_inventario.setRowCount(len(df))
            
            for row_idx, row in df.iterrows():
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    if col_idx == 2 and value == 'Prestado':  # Columna de estado
                        item.setBackground(QColor('#ffcccc'))  # Color de fondo para asignado
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.tabla_inventario.setItem(row_idx, col_idx, item)
            
            self.tabla_inventario.resizeColumnsToContents()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar inventario: {str(e)}")

    def init_ui_modificaciones(self):
        # Habilitar edición en tabla
        self.tabla_inventario.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.tabla_inventario.cellChanged.connect(self.actualizar_datos_desde_tabla)
        
        # Configurar menú contextual
        self.tabla_inventario.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla_inventario.customContextMenuRequested.connect(self.mostrar_menu_contextual)

    def mostrar_menu_contextual(self, pos):
        menu = QMenu()
        eliminar_accion = menu.addAction("🗑️ Eliminar Máquina")
        accion = menu.exec(self.tabla_inventario.viewport().mapToGlobal(pos))
                        
        if accion == eliminar_accion:
            fila_seleccionada = self.tabla_inventario.currentRow()
            self.eliminar_maquina(fila_seleccionada)

    def eliminar_maquina(self, fila):
        id_maquina = self.tabla_inventario.item(fila, 0).text()
        
        confirmacion = QMessageBox.question(
            self, "Confirmar Eliminación",
            f"¿Eliminar permanentemente la máquina {id_maquina}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirmacion == QMessageBox.StandardButton.Yes:
            try:
                # Eliminar de máquinas.csv
                df_maquinas = pd.read_csv(self.archivo_maquinas)
                df_maquinas = df_maquinas[df_maquinas['ID'] != id_maquina]
                df_maquinas.to_csv(self.archivo_maquinas, index=False)
                
                # Eliminar préstamos asociados
                df_prestamos = pd.read_csv(self.archivo_prestamos)
                df_prestamos = df_prestamos[df_prestamos['ID_Maquina'] != id_maquina]
                df_prestamos.to_csv(self.archivo_prestamos, index=False)
                
                # Actualizar UI
                self.actualizar_inventario()
                QMessageBox.information(self, "Éxito", "Máquina eliminada permanentemente")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar: {str(e)}")

    def actualizar_datos_desde_tabla(self, fila, columna):
        try:
            id_maquina = self.tabla_inventario.item(fila, 0).text()
            nuevo_valor = self.tabla_inventario.item(fila, columna).text()
            columna_csv = ['ID', 'Nombre', 'Estado', 'Ubicacion', 'Ultima_Actualizacion'][columna]
                
            # Validar cambios en ubicación y estado
            if columna_csv in ['Ubicacion', 'Estado']:
                self.actualizar_ubicacion_prestamos(id_maquina, nuevo_valor)
                
            # Actualizar CSV
            df = pd.read_csv(self.archivo_maquinas)
            mask = df['ID'] == id_maquina
            df.loc[mask, columna_csv] = nuevo_valor
            df.loc[mask, 'Ultima_Actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df.to_csv(self.archivo_maquinas, index=False)
            
            # Actualizar el dashboard
            self.actualizar_dashboard()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar cambios: {str(e)}")

    def actualizar_ubicacion_prestamos(self, id_maquina, nuevo_valor):
        """Sincroniza la ubicación y el estado en los préstamos activos"""
        try:
            df_prestamos = pd.read_csv(self.archivo_prestamos)
            mask = (df_prestamos['ID_Maquina'] == id_maquina) & (df_prestamos['Status'] == 'Prestado')
            
            if not df_prestamos[mask].empty:
                df_prestamos.loc[mask, 'Ubicacion'] = nuevo_valor
                df_prestamos.to_csv(self.archivo_prestamos, index=False)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar préstamos: {str(e)}")

    def init_supervisores(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Panel superior con estadísticas
        stats_frame = QWidget()
        stats_layout = QHBoxLayout(stats_frame)
        
        # Estadísticas de supervisores
        stats_group = QGroupBox("📊 Estadísticas de Supervisores")
        stats_group_layout = QVBoxLayout()
        self.label_total_supervisores = QLabel("Total supervisores: 0")
        self.label_supervisores_activos = QLabel("Supervisores con préstamos: 0")
        
        for label in [self.label_total_supervisores, self.label_supervisores_activos]:
            label.setStyleSheet("font-size: 12px; padding: 5px;")
        
        stats_group_layout.addWidget(self.label_total_supervisores)
        stats_group_layout.addWidget(self.label_supervisores_activos)
        stats_group.setLayout(stats_group_layout)
        stats_layout.addWidget(stats_group)
        
        # Formulario de registro mejorado
        form_frame = QWidget()
        form_layout = QFormLayout(form_frame)
        
        self.supervisor_nombre = QLineEdit()
        self.supervisor_telefono = QLineEdit()
        self.supervisor_email = QLineEdit()
        self.supervisor_departamento = QComboBox()
        self.supervisor_departamento.addItems(['Producción', 'Mantenimiento', 'Logística', 'Calidad', 'Otro'])
        self.supervisor_notas = QTextEdit()
        self.supervisor_notas.setMaximumHeight(60)
        
        # Botón con estilo mejorado
        btn_registrar = QPushButton("➕ Registrar Supervisor")
        btn_registrar.clicked.connect(self.registrar_supervisor)
        btn_registrar.setStyleSheet(f"""
            QPushButton {{
                background-color: {SYSTEM_CONFIG['COLORES']['exito']};
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2d8f45; }}
        """)
        
        # Añadir elementos al formulario con iconos
        form_layout.addRow("👤 Nombre:", self.supervisor_nombre)
        form_layout.addRow("📞 Teléfono:", self.supervisor_telefono)
        form_layout.addRow("📧 Email:", self.supervisor_email)
        form_layout.addRow("🏢 Departamento:", self.supervisor_departamento)
        form_layout.addRow("📝 Notas:", self.supervisor_notas)
        form_layout.addRow(btn_registrar)
        
        # Tabla de supervisores mejorada
        self.tabla_supervisores = QTableWidget()
        self.tabla_supervisores.setColumnCount(7)
        self.tabla_supervisores.setHorizontalHeaderLabels([
            "Nombre", "Teléfono", "Email", "Departamento", 
            "Fecha Registro", "Préstamos Activos", "Estado"
        ])
        self.tabla_supervisores.verticalHeader().setVisible(False)
        self.tabla_supervisores.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_supervisores.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_supervisores.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        # Botones de filtro y acciones
        filtro_frame = QWidget()
        filtro_layout = QHBoxLayout(filtro_frame)
        
        self.filtro_departamento = QComboBox()
        self.filtro_departamento.addItems(['Todos', 'Producción', 'Mantenimiento', 'Logística', 'Calidad', 'Otro'])
        
        btn_filtrar = QPushButton("🔍 Filtrar")
        btn_filtrar.clicked.connect(self.filtrar_supervisores)
        
        btn_exportar = QPushButton("📥 Exportar Lista")
        btn_exportar.clicked.connect(self.exportar_supervisores)
        
        filtro_layout.addWidget(QLabel("Departamento:"))
        filtro_layout.addWidget(self.filtro_departamento)
        filtro_layout.addWidget(btn_filtrar)
        filtro_layout.addWidget(btn_exportar)
        
        # Layout final
        layout.addWidget(stats_frame)
        layout.addWidget(form_frame)
        layout.addWidget(filtro_frame)
        layout.addWidget(QLabel("📋 Lista de Supervisores:"))
        layout.addWidget(self.tabla_supervisores)
        
        self.content_area.addWidget(page)
        self.actualizar_tabla_supervisores()
        self.actualizar_estadisticas_supervisores()

    def registrar_supervisor(self):
        nombre = self.supervisor_nombre.text().strip()
        telefono = self.supervisor_telefono.text().strip()
        email = self.supervisor_email.text().strip()
        departamento = self.supervisor_departamento.currentText()
        notas = self.supervisor_notas.toPlainText().strip()
        
        if not nombre:
            QMessageBox.warning(self, "Advertencia", "El nombre es obligatorio")
            return
        
        try:
            # Validar email
            if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                QMessageBox.warning(self, "Error", "Email inválido")
                return
            
            df_supervisores = pd.read_csv(self.archivo_supervisores)
            
            # Verificar si ya existe
            if nombre in df_supervisores['Supervisor'].values:
                QMessageBox.warning(self, "Error", "Este supervisor ya está registrado")
                return
            
            nuevo_supervisor = pd.DataFrame([{
                'Supervisor': nombre,
                'Telefono': telefono,
                'Email': email,
                'Departamento': departamento,
                'Fecha_Registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Estado': 'Activo',
                'Notas': notas
            }])
            
            df_supervisores = pd.concat([df_supervisores, nuevo_supervisor], ignore_index=True)
            df_supervisores.to_csv(self.archivo_supervisores, index=False)
            
            # Limpiar formulario
            self.supervisor_nombre.clear()
            self.supervisor_telefono.clear()
            self.supervisor_email.clear()
            self.supervisor_notas.clear()
            self.supervisor_departamento.setCurrentIndex(0)
            
            # Actualizar UI
            self.actualizar_tabla_supervisores()
            self.actualizar_estadisticas_supervisores()
            self.cargar_supervisores()
            
            QMessageBox.information(self, "Éxito", "Supervisor registrado correctamente")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al registrar supervisor: {str(e)}")

    def actualizar_tabla_supervisores(self):
        try:
            df_supervisores = pd.read_csv(self.archivo_supervisores)
            df_prestamos = pd.read_csv(self.archivo_prestamos)
            
            # Contar préstamos activos por supervisor
            prestamos_por_supervisor = df_prestamos[df_prestamos['Status'] == 'Prestado']['Supervisor'].value_counts()
            
            self.tabla_supervisores.setRowCount(len(df_supervisores))
            
            for row_idx, row in df_supervisores.iterrows():
                prestamos_activos = prestamos_por_supervisor.get(row['Supervisor'], 0)
                
                self.tabla_supervisores.setItem(row_idx, 0, QTableWidgetItem(str(row['Supervisor'])))
                self.tabla_supervisores.setItem(row_idx, 1, QTableWidgetItem(str(row['Telefono'])))
                self.tabla_supervisores.setItem(row_idx, 2, QTableWidgetItem(str(row['Email'])))
                self.tabla_supervisores.setItem(row_idx, 3, QTableWidgetItem(str(row['Departamento'])))
                self.tabla_supervisores.setItem(row_idx, 4, QTableWidgetItem(str(row['Fecha_Registro'])))
                self.tabla_supervisores.setItem(row_idx, 5, QTableWidgetItem(str(prestamos_activos)))
                self.tabla_supervisores.setItem(row_idx, 6, QTableWidgetItem(str(row['Estado'])))
                
                # Resaltar supervisores con préstamos activos
                if prestamos_activos > 0:
                    for col in range(7):
                        self.tabla_supervisores.item(row_idx, col).setBackground(QColor('#e8f5e9'))
            
            self.tabla_supervisores.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar tabla de supervisores: {str(e)}")

    def actualizar_estadisticas_supervisores(self):
        try:
            df_supervisores = pd.read_csv(self.archivo_supervisores)
            df_prestamos = pd.read_csv(self.archivo_prestamos)
            
            total_supervisores = len(df_supervisores)
            supervisores_activos = len(df_prestamos[df_prestamos['Status'] == 'Prestado']['Supervisor'].unique())
            
            self.label_total_supervisores.setText(f"Total supervisores: {total_supervisores}")
            self.label_supervisores_activos.setText(f"Supervisores con préstamos: {supervisores_activos}")
            
        except Exception as e:
            print(f"Error al actualizar estadísticas de supervisores: {str(e)}")

    def filtrar_supervisores(self):
        try:
            departamento = self.filtro_departamento.currentText()
            df_supervisores = pd.read_csv(self.archivo_supervisores)
            
            if (departamento != 'Todos'):
                df_supervisores = df_supervisores[df_supervisores['Departamento'] == departamento]
                
            self.actualizar_tabla_con_df_supervisores(df_supervisores)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al filtrar supervisores: {str(e)}")

    def exportar_supervisores(self):
        try:
            df_supervisores = pd.read_csv(self.archivo_supervisores)
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"supervisores_{fecha}.xlsx"
            
            df_supervisores.to_excel(nombre_archivo, index=False, sheet_name='Supervisores')
            QMessageBox.information(self, "Éxito", f"Lista exportada como {nombre_archivo}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar lista: {str(e)}")

    def exportar_reporte(self, tipo="inventario"):
        try:
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"reporte_{tipo}_{fecha}.xlsx"
            writer = pd.ExcelWriter(nombre_archivo, engine='xlsxwriter')
            
            if tipo == "inventario":
                df = pd.read_csv(self.archivo_maquinas)
                df.to_excel(writer, sheet_name='Inventario', index=False)
                
                # Agregar estadísticas
                workbook = writer.book
                stats_sheet = workbook.add_worksheet('Estadísticas')
                stats_sheet.write('A1', 'Estadísticas de Inventario')
                stats_sheet.write('A2', f'Total máquinas: {len(df)}')
                stats_sheet.write('A3', f'Disponibles: {len(df[df["Estado"] == "Disponible"])}')
                stats_sheet.write('A4', f'Prestadas: {len(df[df["Estado"] == "Prestado"])}')
                
            elif tipo == "prestamos":
                df_prestamos = pd.read_csv(self.archivo_prestamos)
                df_prestamos.to_excel(writer, sheet_name='Préstamos', index=False)
                
                # Agregar análisis
                df_analisis = df_prestamos[df_prestamos['Status'] == 'Prestado'].groupby('Supervisor').size()
                df_analisis.to_excel(writer, sheet_name='Análisis')
            
            writer.close()
            return nombre_archivo
            
        except Exception as e:
            raise Exception(f"Error al exportar reporte: {str(e)}")

    def handle_error(self, error, titulo="Error"):
        """Manejo centralizado de errores"""
        if isinstance(error, ValidationError):
            QMessageBox.warning(self, titulo, str(error))
        elif isinstance(error, DataBaseError):
            QMessageBox.critical(self, titulo, f"Error de base de datos: {str(error)}")
        else:
            QMessageBox.critical(self, titulo, f"Error inesperado: {str(error)}")
        
        # Registrar error en el log
        self.logger.log(f"{titulo}: {str(error)}", "ERROR")

def crear_usuario_inicial():
    if not os.path.exists("users.csv"):
        # Hash de contraseña
        password = "admin123".encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password, salt)
        
        df = pd.DataFrame([{
            'username': 'admin',
            'password_hash': hashed.decode('utf-8'),
            'role': 'admin'
        }])
        
        df.to_csv("users.csv", index=False)

if __name__ == "__main__":
    crear_usuario_inicial()
    app = QApplication(sys.argv)
    login = LoginWindow()
    if login.exec() == QDialog.DialogCode.Accepted:
        main_window = MainApp()
        main_window.show()
        sys.exit(app.exec())
