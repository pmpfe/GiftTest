from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QLineEdit, QLabel, 
                               QPushButton, QAbstractItemView, QComboBox)
from PyQt6.QtCore import Qt

class QuestionBrowser(QDialog):
    def __init__(self, parent, questions):
        super().__init__(parent)
        self.questions = questions
        self.parent_app = parent
        self.setWindowTitle("Explorador de Perguntas")
        self.resize(1100, 700)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Search bar and filters
        search_layout = QHBoxLayout()
        
        # Category filter
        search_layout.addWidget(QLabel("Categoria:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("Todas")
        categories = sorted(list(set(q.category for q in self.questions if q.category)))
        self.category_combo.addItems(categories)
        self.category_combo.currentTextChanged.connect(self.apply_filters)
        search_layout.addWidget(self.category_combo)
        
        search_layout.addSpacing(20)
        
        # Text search
        search_layout.addWidget(QLabel("Pesquisar:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Digite para filtrar por texto, respostas ou número...")
        self.search_input.textChanged.connect(self.apply_filters)
        search_layout.addWidget(self.search_input)
        
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "Categoria", "Pergunta", "Respostas"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        
        layout.addWidget(self.table)
        
        # Help text
        help_lbl = QLabel("Duplo clique numa linha para ver a explicação / detalhes.")
        help_lbl.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(help_lbl)
        
        self.populate_table()
        
    def populate_table(self):
        self.table.setRowCount(len(self.questions))
        for i, q in enumerate(self.questions):
            # ID
            item_id = QTableWidgetItem(str(q.number))
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, item_id)
            
            # Category
            self.table.setItem(i, 1, QTableWidgetItem(q.category))
            
            # Text (truncated)
            text = q.text.replace("\n", " ")
            if len(text) > 100:
                text = text[:100] + "..."
            self.table.setItem(i, 2, QTableWidgetItem(text))
            
            # Answers (concatenated)
            answers = "; ".join([opt['text'] for opt in q.options])
            if len(answers) > 100:
                answers = answers[:100] + "..."
            self.table.setItem(i, 3, QTableWidgetItem(answers))
            
            # Store full question object in user data of first item
            item_id.setData(Qt.ItemDataRole.UserRole, q)

    def apply_filters(self):
        text = self.search_input.text().lower()
        category = self.category_combo.currentText()
        
        for row in range(self.table.rowCount()):
            show = True
            
            # Filter by category
            item_cat = self.table.item(row, 1)
            if category != "Todas" and item_cat.text() != category:
                show = False
            
            # Filter by text (if still showing)
            if show and text:
                match = False
                for col in range(4):
                    item = self.table.item(row, col)
                    if item and text in item.text().lower():
                        match = True
                        break
                if not match:
                    show = False
            
            self.table.setRowHidden(row, not show)

    def on_row_double_clicked(self, index):
        # Get question from the first column's user data
        item = self.table.item(index.row(), 0)
        question = item.data(Qt.ItemDataRole.UserRole)
        if question:
            self.parent_app.explain_question(question_obj=question)
