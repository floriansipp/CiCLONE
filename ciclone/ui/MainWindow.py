import os
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QListWidgetItem,
    QMenu,
    QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from ciclone.controllers.main_controller import MainController
from ciclone.services.processing.tool_config import tool_config
from ciclone.interfaces.view_interfaces import IMainView, IBaseView

from ..forms.MainWindow_ui import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    config_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "config/config.yaml"))
    
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        
        # Check neuroimaging environment before initializing controllers
        self._check_neuroimaging_environment()
        
        # Initialize main controller
        self.main_controller = MainController(self.config_path)
        
        # Connect form controller signals before set_view() to catch initial validation
        form_controller = self.main_controller.get_subject_form_controller()
        form_controller.validation_feedback_ready.connect(self._on_field_validation_changed)
        form_controller.form_state_updated.connect(self._on_form_state_changed)
        form_controller.form_submission_complete.connect(self._on_form_submission_complete)
        
        self._setup_validation_indicators()
        
        # Set view and callbacks
        self.main_controller.set_view(self)
        self.main_controller.set_log_callback(self.add_log_message)
        
        # File menu actions
        self.actionNew_Output_Directory.triggered.connect(self.create_output_directory)
        self.actionOpen_Output_Directory.triggered.connect(self.open_output_directory)
        
        # Directory and subject management
        self.lineEdit_outputDirectory.textChanged.connect(self.on_output_directory_changed)
        self.pushButton_addSubject.clicked.connect(self.add_subject)
        
        # Subject tree view
        self.subjectTreeView.clicked.connect(self.on_tree_item_clicked)
        self.subjectTreeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subjectTreeView.customContextMenuRequested.connect(self.show_context_menu)

        # Browse buttons
        self.browse_Schema.clicked.connect(lambda: self.main_controller.browse_for_form_field("schema", "Schema"))
        self.browse_preCT.clicked.connect(lambda: self.main_controller.browse_for_form_field("pre_ct", "PreCT"))
        self.browse_preMRI.clicked.connect(lambda: self.main_controller.browse_for_form_field("pre_mri", "PreMRI"))
        self.browse_postCT.clicked.connect(lambda: self.main_controller.browse_for_form_field("post_ct", "PostCT"))
        self.browse_postMRI.clicked.connect(lambda: self.main_controller.browse_for_form_field("post_mri", "PostMRI"))
        
        # Form field connections for real-time validation
        self.lineEdit_Name.textChanged.connect(lambda text: self.main_controller.handle_form_field_change("name", text))
        self.lineEdit_Schema.textChanged.connect(lambda text: self.main_controller.handle_form_field_change("schema", text))
        self.lineEdit_preCT.textChanged.connect(lambda text: self.main_controller.handle_form_field_change("pre_ct", text))
        self.lineEdit_preMRI.textChanged.connect(lambda text: self.main_controller.handle_form_field_change("pre_mri", text))
        self.lineEdit_postCT.textChanged.connect(lambda text: self.main_controller.handle_form_field_change("post_ct", text))
        self.lineEdit_postMRI.textChanged.connect(lambda text: self.main_controller.handle_form_field_change("post_mri", text))

        # Processing buttons
        self.runAllStages_PushButton.clicked.connect(self.run_all_stages)
        self.runSelectedStages_pushButton.clicked.connect(self.run_selected_stages)
        self.stopProcessing_pushButton.clicked.connect(self.stop_processing)

        self._setup_stages_ui()
        self.main_controller.connect_worker_state_signal(self.update_processing_ui)
        
        # Verbose mode toggle (Ctrl+V)
        self.verbose_action = QAction("Toggle Verbose Logging", self)
        self.verbose_action.setShortcut("Ctrl+V")
        self.verbose_action.triggered.connect(self.toggle_verbose_mode)
        self.addAction(self.verbose_action)
        
        # Log area context menu
        self.textBrowser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.textBrowser.customContextMenuRequested.connect(self.show_log_context_menu)

    def _check_neuroimaging_environment(self):
        """Check FSL and FreeSurfer environment configuration."""
        print("Checking neuroimaging environment...")
        is_configured, error_messages = tool_config.validate_environment()
        
        if not is_configured:
            error_text = "The following neuroimaging tools are not properly configured:\n\n" + \
                        "\n".join(error_messages) + \
                        "\n\nSome features may not work correctly. " + \
                        "Please ensure these tools are installed and their environment variables are set:\n" + \
                        "- FSL: Set FSLDIR environment variable\n" + \
                        "- FreeSurfer: Set FREESURFER_HOME environment variable"
            
            QMessageBox.warning(
                self,
                "Neuroimaging Environment Warning",
                error_text
            )
    
    def _setup_validation_indicators(self):
        """Map field names to validation indicator widgets from UI file."""
        self.validation_indicators = {
            'name': self.validation_indicator_name,
            'schema': self.validation_indicator_schema,
            'pre_ct': self.validation_indicator_pre_ct,
            'pre_mri': self.validation_indicator_pre_mri,
            'post_ct': self.validation_indicator_post_ct,
            'post_mri': self.validation_indicator_post_mri
        }
        
        for indicator in self.validation_indicators.values():
            indicator.hide()
    
    @property
    def output_directory(self):
        return self.main_controller.get_output_directory()
    
    @output_directory.setter  
    def output_directory(self, value):
        if value:
            self.main_controller.set_output_directory(value)

    def create_output_directory(self):
        """Create new output directory."""
        output_directory = self.main_controller.create_output_directory()
        if output_directory:
            self.output_directory = output_directory
            self.lineEdit_outputDirectory.setText(output_directory)
        
    def open_output_directory(self):
        """Open existing output directory."""
        output_directory = self.main_controller.open_output_directory()
        if output_directory:
            self.output_directory = output_directory
            self.lineEdit_outputDirectory.setText(output_directory)

    def on_output_directory_changed(self):
        """Handle output directory changes."""
        directory_text = self.lineEdit_outputDirectory.text().strip()
        if directory_text:
            self.main_controller.set_output_directory(directory_text)

    def _on_field_validation_changed(self, field: str, valid: bool, error_msg: str, warning_msg: str):
        """Handle field validation feedback using colored indicators."""
        field_widgets = {
            'name': self.lineEdit_Name,
            'schema': self.lineEdit_Schema,
            'pre_ct': self.lineEdit_preCT,
            'pre_mri': self.lineEdit_preMRI,
            'post_ct': self.lineEdit_postCT,
            'post_mri': self.lineEdit_postMRI
        }
        
        field_widget = field_widgets.get(field)
        indicator = self.validation_indicators.get(field)
        
        if field_widget and indicator:
            field_widget.setStyleSheet("")
            
            if not valid and error_msg:
                indicator.setStyleSheet("""
                    QLabel {
                        border-radius: 8px;
                        background-color: #f44336;
                        font-size: 12px;
                        color: #f44336;
                        text-align: center;
                    }
                """)
                indicator.setToolTip(f"Error: {error_msg}")
                indicator.show()
                
            elif warning_msg:
                indicator.setStyleSheet("""
                    QLabel {
                        border-radius: 8px;
                        background-color: #ff9800;
                        font-size: 12px;
                        color: #ff9800;
                        text-align: center;
                    }
                """)
                indicator.setToolTip(f"Warning: {warning_msg}")
                indicator.show()
                
            else:
                if field_widget.text().strip():
                    indicator.setStyleSheet("""
                        QLabel {
                            border-radius: 8px;
                            background-color: #4caf50;
                            font-size: 12px;
                            color: #4caf50;
                            text-align: center;
                        }
                    """)
                    indicator.setToolTip("Valid")
                    indicator.show()
                else:
                    indicator.hide()
                    indicator.setToolTip("")
    
    def _on_form_state_changed(self, is_valid: bool, is_dirty: bool):
        """Handle form state changes."""
        self.pushButton_addSubject.setEnabled(is_valid)
        
        if is_valid:
            self.pushButton_addSubject.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        else:
            self.pushButton_addSubject.setStyleSheet("QPushButton { background-color: #cccccc; color: #666666; }")
    
    def _on_form_submission_complete(self, success: bool):
        """Handle form submission completion."""
        if success:
            self.refresh_subject_tree()
    
    def update_schema_field(self, schema_text: str):
        """Update schema field after browsing."""
        self.lineEdit_Schema.setText(schema_text)
        
        if ',' in schema_text:
            schema_files = [path.strip() for path in schema_text.split(',') if path.strip()]
            file_names = [os.path.basename(path) for path in schema_files]
            tooltip_text = f"Selected {len(schema_files)} file(s):\n" + "\n".join(file_names)
            self.lineEdit_Schema.setToolTip(tooltip_text)
        elif schema_text.strip():
            self.lineEdit_Schema.setToolTip(os.path.basename(schema_text))
    
    def update_field(self, field_name: str, file_path: str):
        """Update form field after browsing."""
        field_widgets = {
            'pre_ct': self.lineEdit_preCT,
            'pre_mri': self.lineEdit_preMRI,
            'post_ct': self.lineEdit_postCT,
            'post_mri': self.lineEdit_postMRI
        }
        
        field_widget = field_widgets.get(field_name)
        if field_widget:
            field_widget.setText(file_path)
    
    def on_form_reset(self):
        """Handle form reset."""
        # Clear form fields
        self.lineEdit_Name.clear()
        self.lineEdit_Schema.clear()
        self.lineEdit_preCT.clear()
        self.lineEdit_preMRI.clear()
        self.lineEdit_postCT.clear()
        self.lineEdit_postMRI.clear()
        
        # Clear field styling and tooltips
        for field_widget in [self.lineEdit_Name, self.lineEdit_Schema, self.lineEdit_preCT, 
                           self.lineEdit_preMRI, self.lineEdit_postCT, self.lineEdit_postMRI]:
            field_widget.setStyleSheet("")
            field_widget.setToolTip("")
        
        # Hide validation indicators
        for indicator in self.validation_indicators.values():
            indicator.hide()
            indicator.setToolTip("")

    def add_subject(self):
        """Add subject using form controller."""
        success = self.main_controller.submit_subject_form()

    def run_all_stages(self):
        """Run all configured stages for selected subjects."""
        subject_list = self._get_selected_subjects()
        if not subject_list:
            QMessageBox.warning(self, "Error", "Please select at least one subject")
            return
        
        success = self.main_controller.run_all_stages(subject_list)

    def run_selected_stages(self):
        """Run selected stages for selected subjects."""
        subject_list = self._get_selected_subjects()
        if not subject_list:
            QMessageBox.warning(self, "Error", "Please select at least one subject")
            return
        
        self._update_stages_selection_from_ui()
        success = self.main_controller.run_selected_stages(subject_list)

    def add_log_message(self, level: str, message: str):
        """Add formatted log message to display."""
        color_map = {
            "debug": "gray",
            "info": "black",
            "success": "green",
            "error": "red",
            "warning": "orange"
        }
        color = color_map.get(level, "black")
        formatted_message = f'<p style="color:{color}"><b>[{level.upper()}]</b> {message}</p>'
        self.textBrowser.append(formatted_message)
        self.textBrowser.ensureCursorVisible()

    def on_tree_item_clicked(self, index):
        """Handle tree item clicks for file preview."""
        file_path = self.main_controller.get_file_path_from_tree_index(index)
        if file_path and self.main_controller.is_previewable_file(file_path):
            self.main_controller.open_file_preview(file_path)

    def show_context_menu(self, position):
        """Show context menu for subject management."""
        index = self.subjectTreeView.indexAt(position)
        if not index.isValid():
            return
            
        selected_indexes = self.subjectTreeView.selectedIndexes()
        if not selected_indexes:
            return
        
        subject_paths = self.main_controller.get_selected_subject_paths_from_tree(selected_indexes)
        if not subject_paths:
            return
        
        context_menu = QMenu(self)
        
        if len(subject_paths) == 1:
            single_path = subject_paths[0]
            
            rename_action = QAction("Rename Subject", self)
            rename_action.triggered.connect(lambda: self.rename_subject(single_path))
            context_menu.addAction(rename_action)
            
            delete_action = QAction("Delete Subject", self)
            delete_action.triggered.connect(lambda: self.delete_subject(single_path))
            context_menu.addAction(delete_action)
        else:
            delete_action = QAction(f"Delete {len(subject_paths)} Subjects", self)
            delete_action.triggered.connect(lambda: self.delete_multiple_subjects(subject_paths))
            context_menu.addAction(delete_action)
        
        context_menu.exec(self.subjectTreeView.mapToGlobal(position))

    def rename_subject(self, subject_path):
        """Rename a subject directory."""
        current_name = os.path.basename(subject_path)
        
        new_name, ok = QInputDialog.getText(
            self, 
            "Rename Subject", 
            f"Enter new name for '{current_name}':",
            text=current_name
        )
        
        if ok and new_name.strip() and new_name != current_name:
            success = self.main_controller.rename_subject(current_name, new_name.strip())
            if success:
                self.refresh_subject_tree()

    def delete_subject(self, subject_path):
        """Delete a single subject."""
        subject_name = os.path.basename(subject_path)
        
        reply = QMessageBox.question(
            self,
            "Delete Subject",
            f"Are you sure you want to delete subject '{subject_name}'?\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.main_controller.delete_subject(subject_name)
            if success:
                self.refresh_subject_tree()

    def delete_multiple_subjects(self, subject_paths):
        """Delete multiple subjects."""
        subject_names = [os.path.basename(path) for path in subject_paths]
        subjects_list = "\n".join(f"• {name}" for name in subject_names)
        
        reply = QMessageBox.question(
            self,
            "Delete Multiple Subjects",
            f"Are you sure you want to delete {len(subject_paths)} subjects?\n\n"
            f"{subjects_list}\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success_count = 0
            for subject_path in subject_paths:
                subject_name = os.path.basename(subject_path)
                if self.main_controller.delete_subject(subject_name):
                    success_count += 1
            
            if success_count > 0:
                self.refresh_subject_tree()
                
            if success_count != len(subject_paths):
                failed_count = len(subject_paths) - success_count
                QMessageBox.warning(
                    self,
                    "Partial Deletion",
                    f"Successfully deleted {success_count} subjects.\n"
                    f"Failed to delete {failed_count} subjects."
                )

    def refresh_subject_tree(self):
        """Refresh subject tree view."""
        self.main_controller.refresh_views()

    def _clear_subject_form(self):
        """Clear subject form fields."""
        self.lineEdit_Name.clear()
        self.lineEdit_Schema.clear()
        self.lineEdit_preCT.clear()
        self.lineEdit_preMRI.clear()
        self.lineEdit_postCT.clear()
        self.lineEdit_postMRI.clear()

    def _setup_stages_ui(self):
        """Initialize stages UI from configuration."""
        try:
            stages = self.main_controller.get_stages_config()
            self.stages_listWidget.clear()
            for stage in stages:
                item = QListWidgetItem(stage.get("name", "Unknown Stage"))
                item.setCheckState(Qt.CheckState.Checked)
                self.stages_listWidget.addItem(item)
        except Exception as e:
            print(f"Error setting up stages UI: {e}")

    def _get_selected_subjects(self) -> list:
        """Get list of selected subjects from tree view."""
        return self.main_controller.get_selected_subjects_from_tree()

    def _update_stages_selection_from_ui(self):
        """Update stages selection based on UI checkboxes."""
        selected_stages = []
        for i in range(self.stages_listWidget.count()):
            item = self.stages_listWidget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_stages.append(item.text())
        
        self.main_controller.update_stage_selection_from_ui(selected_stages)

    def update_processing_ui(self, is_running: bool, progress: int):
        """Update processing UI state."""
        self.progressBar.setVisible(is_running)
        if is_running:
            self.progressBar.setValue(progress)
        
        self.runAllStages_PushButton.setEnabled(not is_running)
        self.runSelectedStages_pushButton.setEnabled(not is_running)
        self.stopProcessing_pushButton.setEnabled(is_running)

    def clear_processing_log(self):
        """Clear processing log display."""
        self.textBrowser.clear()

    def toggle_verbose_mode(self):
        """Toggle verbose logging mode."""
        current_verbose = self.main_controller.is_verbose_mode()
        self.main_controller.set_verbose_mode(not current_verbose)
        level = "verbose" if not current_verbose else "normal"
        self.add_log_message("info", f"Logging mode set to {level}")

    def show_log_context_menu(self, position):
        """Show context menu for log area."""
        context_menu = QMenu(self)
        
        clear_action = QAction("Clear Log", self)
        clear_action.triggered.connect(self.clear_processing_log)
        context_menu.addAction(clear_action)
        
        verbose_action = QAction("Toggle Verbose Mode", self)
        verbose_action.triggered.connect(self.toggle_verbose_mode)
        context_menu.addAction(verbose_action)
        
        context_menu.exec(self.textBrowser.mapToGlobal(position))

    def stop_processing(self):
        """Stop current processing operation."""
        self.main_controller.stop_processing()

    # IMainView Interface Implementation
    def set_output_directory_text(self, directory: str) -> None:
        """Set output directory text field."""
        self.lineEdit_outputDirectory.setText(directory)
    
    def enable_form_controls(self, enabled: bool) -> None:
        """Enable or disable form controls."""
        controls = [
            self.lineEdit_Name, self.lineEdit_Schema, self.lineEdit_preCT,
            self.lineEdit_preMRI, self.lineEdit_postCT, self.lineEdit_postMRI,
            self.browse_Schema, self.browse_preCT, self.browse_preMRI,
            self.browse_postCT, self.browse_postMRI, self.pushButton_addSubject
        ]
        
        for control in controls:
            control.setEnabled(enabled)
    
    def show_status_message(self, message: str, timeout: int = 0) -> None:
        """Show status message."""
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(message, timeout)
    
    def set_field_validation_state(self, field_name: str, is_valid: bool, 
                                 error_message: str = "", warning_message: str = "") -> None:
        """Set validation state for form field."""
        self._on_field_validation_changed(field_name, is_valid, error_message, warning_message)
    
    def set_form_submission_state(self, can_submit: bool) -> None:
        """Set form submission button state."""
        self.pushButton_addSubject.setEnabled(can_submit)
        
        if can_submit:
            self.pushButton_addSubject.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        else:
            self.pushButton_addSubject.setStyleSheet("QPushButton { background-color: #cccccc; color: #666666; }")

    # IBaseView Interface Implementation
    def show_error_message(self, title: str, message: str) -> None:
        """Show error message dialog."""
        QMessageBox.critical(self, title, message)
    
    def show_warning_message(self, title: str, message: str) -> None:
        """Show warning message dialog."""
        QMessageBox.warning(self, title, message)
    
    def show_info_message(self, title: str, message: str) -> None:
        """Show info message dialog."""
        QMessageBox.information(self, title, message)
    
    def set_busy_state(self, busy: bool) -> None:
        """Set application busy state."""
        if busy:
            self.setCursor(Qt.CursorShape.WaitCursor)
        else:
            self.unsetCursor()
    
    def get_widget(self) -> QWidget:
        """Get the main widget."""
        return self
