from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QHeaderView, QLineEdit, QLabel,
                               QPushButton, QAbstractItemView, QComboBox, QWidget,
                               QRadioButton, QButtonGroup, QMessageBox)
from PySide6.QtCore import Qt


class QuestionAnswerDialog(QDialog):
    """Dialog for answering a question before seeing the explanation."""

    def __init__(self, parent, question):
        super().__init__(parent)
        self.question = question
        self.selected_answer = None
        self.setWindowTitle(f"Responder: {question.number}")
        self.resize(600, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Question text
        question_label = QLabel(self.question.text)
        question_label.setWordWrap(True)
        question_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(question_label)

        # Options
        self.button_group = QButtonGroup(self)
        for i, opt in enumerate(self.question.options):
            radio = QRadioButton(opt['text'])
            radio.setStyleSheet("padding: 5px;")
            self.button_group.addButton(radio, i)
            layout.addWidget(radio)

        layout.addStretch()

        # Submit button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        submit_btn = QPushButton("Ver Explicação")
        submit_btn.clicked.connect(self.submit_answer)
        btn_layout.addWidget(submit_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def submit_answer(self):
        selected_id = self.button_group.checkedId()
        if selected_id == -1:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma resposta.")
            return
        self.selected_answer = selected_id
        self.accept()

    def get_selected_answer_text(self):
        if self.selected_answer is not None:
            return self.question.options[self.selected_answer]['text']
        return None

    def is_correct(self):
        if self.selected_answer is not None:
            return self.question.options[self.selected_answer].get('is_correct', False)
        return False

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
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "Categoria", "Pergunta", "Respostas", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_row_double_clicked)

        layout.addWidget(self.table)

        # Help text
        help_lbl = QLabel("🔍 = Ver explicação  |  ❓ = Responder primeiro e depois ver explicação  |  Duplo clique = Ver explicação")
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

            # Action buttons column
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 0, 2, 0)
            actions_layout.setSpacing(4)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Question mark button - answer first, then explain
            answer_btn = QPushButton("❓")
            answer_btn.setToolTip("Responder primeiro e depois ver explicação")
            answer_btn.setFixedSize(28, 28)
            answer_btn.setStyleSheet("QPushButton { font-size: 14px; }")
            answer_btn.clicked.connect(lambda checked, question=q: self.on_answer_then_explain(question))
            actions_layout.addWidget(answer_btn)

            # Magnifying glass button - direct explanation
            explain_btn = QPushButton("🔍")
            explain_btn.setToolTip("Ver explicação")
            explain_btn.setFixedSize(28, 28)
            explain_btn.setStyleSheet("QPushButton { font-size: 14px; }")
            explain_btn.clicked.connect(lambda checked, question=q: self.on_explain(question))
            actions_layout.addWidget(explain_btn)

            self.table.setCellWidget(i, 4, actions_widget)

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

    def on_explain(self, question):
        """Direct explanation without answering first."""
        self.parent_app.explain_question(question_obj=question)

    def on_answer_then_explain(self, question):
        """Show question dialog, then explanation with user's answer."""
        dialog = QuestionAnswerDialog(self, question)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            user_answer = dialog.get_selected_answer_text()
            is_correct = dialog.is_correct()
            # Pass user's answer to the explanation
            self.parent_app.explain_question(
                question_obj=question,
                user_answer=user_answer,
                user_was_correct=is_correct
            )
