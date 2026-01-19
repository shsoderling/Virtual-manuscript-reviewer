"""Desktop GUI application for Virtual Manuscript Reviewer."""

import sys
import os
from pathlib import Path
from typing import Optional
import threading
import queue

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QSpinBox,
    QCheckBox,
    QProgressBar,
    QGroupBox,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent


class WorkerSignals(QObject):
    """Signals for the worker thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


class ReviewWorker(threading.Thread):
    """Background worker for running reviews."""

    def __init__(self, pdf_path: str, num_rounds: int, pubmed: bool, mentor: bool, signals: WorkerSignals):
        super().__init__()
        self.pdf_path = pdf_path
        self.num_rounds = num_rounds
        self.pubmed = pubmed
        self.mentor = mentor
        self.signals = signals
        self.daemon = True

    def run(self):
        try:
            # Import here to avoid slow startup
            from virtual_manuscript_reviewer.manuscript import Manuscript
            from virtual_manuscript_reviewer.run_review import run_review
            from virtual_manuscript_reviewer.prompts import BIOMEDICAL_REVIEW_CRITERIA

            self.signals.progress.emit("Loading manuscript...")
            manuscript = Manuscript.from_pdf(self.pdf_path)

            self.signals.progress.emit(f"Analyzing: {manuscript.title[:50]}...")

            # Generate save name
            safe_title = "".join(c if c.isalnum() or c in "- " else "_" for c in manuscript.title[:50])
            save_name = f"{safe_title}_{manuscript.version_hash}"

            # Output to Downloads folder
            output_dir = Path.home() / "Downloads" / "VMR_Reviews"
            output_dir.mkdir(parents=True, exist_ok=True)

            self.signals.progress.emit("Generating specialized reviewers...")

            # Run review
            summary = run_review(
                manuscript=manuscript,
                review_type="panel",
                save_dir=output_dir,
                save_name=save_name,
                review_criteria=BIOMEDICAL_REVIEW_CRITERIA,
                num_rounds=self.num_rounds,
                pubmed_search=self.pubmed,
                return_summary=True,
                auto_generate_reviewers=True,
                generate_pdf=True,
                run_mentor=self.mentor,
            )

            self.signals.finished.emit(str(output_dir))

        except Exception as e:
            self.signals.error.emit(str(e))


class DropZone(QFrame):
    """Drag-and-drop zone for PDF files."""

    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)
        self.setStyleSheet("""
            QFrame {
                border: 3px dashed #aaa;
                border-radius: 10px;
                background-color: #f8f9fa;
            }
            QFrame:hover {
                border-color: #007bff;
                background-color: #e7f1ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("📄")
        icon_label.setFont(QFont("Arial", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        text_label = QLabel("Drag & Drop PDF Here\nor click to browse")
        text_label.setFont(QFont("Arial", 14))
        text_label.setStyleSheet("color: #666;")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)

        self.file_label = QLabel("")
        self.file_label.setFont(QFont("Arial", 11))
        self.file_label.setStyleSheet("color: #28a745; font-weight: bold;")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if url.toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction()
                self.setStyleSheet("""
                    QFrame {
                        border: 3px dashed #28a745;
                        border-radius: 10px;
                        background-color: #d4edda;
                    }
                """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                border: 3px dashed #aaa;
                border-radius: 10px;
                background-color: #f8f9fa;
            }
            QFrame:hover {
                border-color: #007bff;
                background-color: #e7f1ff;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("""
            QFrame {
                border: 3px dashed #aaa;
                border-radius: 10px;
                background-color: #f8f9fa;
            }
        """)

        url = event.mimeData().urls()[0]
        file_path = url.toLocalFile()
        if file_path.lower().endswith('.pdf'):
            self.file_label.setText(f"✓ {Path(file_path).name}")
            self.file_dropped.emit(file_path)

    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Manuscript PDF",
            str(Path.home()),
            "PDF Files (*.pdf)"
        )
        if file_path:
            self.file_label.setText(f"✓ {Path(file_path).name}")
            self.file_dropped.emit(file_path)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.pdf_path: Optional[str] = None
        self.worker: Optional[ReviewWorker] = None
        self.signals = WorkerSignals()

        self.setWindowTitle("Virtual Manuscript Reviewer")
        self.setMinimumSize(600, 700)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:enabled {
                background-color: #007bff;
                color: white;
                border: none;
            }
            QPushButton:enabled:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)

        # Connect signals
        self.signals.progress.connect(self.on_progress)
        self.signals.finished.connect(self.on_finished)
        self.signals.error.connect(self.on_error)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Virtual Manuscript Reviewer")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1a365d;")
        layout.addWidget(title)

        subtitle = QLabel("AI-Powered Scientific Manuscript Review")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.on_file_selected)
        layout.addWidget(self.drop_zone)

        # Options group
        options_group = QGroupBox("Review Options")
        options_layout = QVBoxLayout(options_group)

        # Discussion rounds
        rounds_layout = QHBoxLayout()
        rounds_label = QLabel("Discussion Rounds:")
        rounds_label.setFont(QFont("Arial", 12))
        self.rounds_spinner = QSpinBox()
        self.rounds_spinner.setRange(1, 5)
        self.rounds_spinner.setValue(1)
        self.rounds_spinner.setFixedWidth(60)
        rounds_layout.addWidget(rounds_label)
        rounds_layout.addWidget(self.rounds_spinner)
        rounds_layout.addStretch()
        options_layout.addLayout(rounds_layout)

        # Checkboxes
        self.pubmed_checkbox = QCheckBox("Enable PubMed Literature Search")
        self.pubmed_checkbox.setChecked(True)
        self.pubmed_checkbox.setFont(QFont("Arial", 12))
        options_layout.addWidget(self.pubmed_checkbox)

        self.mentor_checkbox = QCheckBox("Generate Scientific Mentor Report")
        self.mentor_checkbox.setChecked(True)
        self.mentor_checkbox.setFont(QFont("Arial", 12))
        options_layout.addWidget(self.mentor_checkbox)

        layout.addWidget(options_group)

        # Progress
        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Arial", 11))
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("color: #666;")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Run button
        self.run_button = QPushButton("🔬 Start Review")
        self.run_button.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.run_button.setMinimumHeight(50)
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.start_review)
        layout.addWidget(self.run_button)

        # Status/Log
        log_group = QGroupBox("Status")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Courier", 10))
        self.log_text.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ddd;")
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        # Footer
        footer = QLabel("Powered by OpenAI GPT • Reviews saved to Downloads/VMR_Reviews")
        footer.setFont(QFont("Arial", 10))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #999;")
        layout.addWidget(footer)

    def on_file_selected(self, path: str):
        self.pdf_path = path
        self.run_button.setEnabled(True)
        self.log(f"Selected: {Path(path).name}")

    def log(self, message: str):
        self.log_text.append(message)
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def start_review(self):
        if not self.pdf_path:
            return

        # Check for API key
        if not os.environ.get("OPENAI_API_KEY"):
            QMessageBox.warning(
                self,
                "API Key Required",
                "Please set your OPENAI_API_KEY environment variable.\n\n"
                "On Mac, add this to your ~/.zshrc or ~/.bash_profile:\n"
                "export OPENAI_API_KEY='your-key-here'\n\n"
                "Then restart the application."
            )
            return

        self.run_button.setEnabled(False)
        self.progress_bar.show()
        self.log("Starting review process...")

        self.worker = ReviewWorker(
            pdf_path=self.pdf_path,
            num_rounds=self.rounds_spinner.value(),
            pubmed=self.pubmed_checkbox.isChecked(),
            mentor=self.mentor_checkbox.isChecked(),
            signals=self.signals,
        )
        self.worker.start()

    def on_progress(self, message: str):
        self.progress_label.setText(message)
        self.log(message)

    def on_finished(self, output_dir: str):
        self.progress_bar.hide()
        self.progress_label.setText("Review complete!")
        self.run_button.setEnabled(True)
        self.log(f"\n✓ Review complete!")
        self.log(f"Output saved to: {output_dir}")

        # Show success dialog
        reply = QMessageBox.information(
            self,
            "Review Complete",
            f"Your manuscript review is complete!\n\n"
            f"Files saved to:\n{output_dir}\n\n"
            f"Would you like to open the output folder?",
            QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close
        )

        if reply == QMessageBox.StandardButton.Open:
            import subprocess
            subprocess.run(["open", output_dir])

    def on_error(self, error: str):
        self.progress_bar.hide()
        self.progress_label.setText("Error occurred")
        self.run_button.setEnabled(True)
        self.log(f"\n❌ Error: {error}")

        QMessageBox.critical(
            self,
            "Error",
            f"An error occurred during review:\n\n{error}"
        )


def main():
    """Main entry point for the GUI application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
