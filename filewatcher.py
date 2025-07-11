    def controller_ui(self):
        """
        Constructs the main UI layout, including the command tree,
        input fields, dump log viewer, and back button.

        args: None
        returns: None

        """
        main_layout = QGridLayout(self) # Pass self to the QGridLayout
        main_layout.setColumnStretch(0, 1)
        main_layout.setColumnStretch(1, 1)
        main_layout.setColumnStretch(2, 1)

        # Left column: Command tree
        vertical_layout = QGridLayout()
        self.commands_list_tree_widget = QTreeWidget()
        self.commands_list_tree_widget.setHeaderLabels(["HCI Commands"])
        self.commands_list_tree_widget.setStyleSheet(ss.cmd_list_widget_style_sheet)

        items = []
        for item in list(hci.hci_commands.keys()):
            _item = QTreeWidgetItem([item])
            for value in list(getattr(hci, item.lower().replace(' ', '_')).keys()):
                child = QTreeWidgetItem([value])
                _item.addChild(child)
            items.append(_item)

        self.commands_list_tree_widget.insertTopLevelItems(0, items)
        self.commands_list_tree_widget.clicked.connect(self.run_hci_cmd)

        vertical_layout.addWidget(self.commands_list_tree_widget, 0, 0)
        vertical_layout.setRowStretch(0, 1)
        vertical_layout.setRowStretch(1, 1)
        main_layout.addLayout(vertical_layout, 0, 0)

        # Middle column: Input area for selected command parameters
        self.command_input_layout = QVBoxLayout()
        self.empty_list = QListWidget()
        self.empty_list.setStyleSheet("background: transparent; border: 2px solid black;")
        self.command_input_layout.addWidget(self.empty_list)
        main_layout.addLayout(self.command_input_layout, 0, 1)

        # Right column: Dump logs
        self.logs_layout = QVBoxLayout()
        logs_label = QLabel("DUMP LOGS")
        logs_label.setStyleSheet("border: 2px solid black; color: black; font-size:18px; font-weight: bold;")
        logs_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.logs_layout.addWidget(logs_label)

        self.dump_log_output = QTextEdit()
        # Remove setMaximumWidth(700) as it can restrict the width of the log output
        #self.dump_log_output.setMaximumWidth(700) 
        self.dump_log_output.setReadOnly(True)
        self.dump_log_output.setStyleSheet("background: transparent;color: black;border: 2px solid black;")

        # Start HCI dump logging
        self.bluez_logger.start_dump_logs(interface=self.controller.interface,log_text_browser=self.dump_log_output)
        self.bluez_logger.logfile_fd = open(self.bluez_logger.hcidump_log_name,'r')
        if self.bluez_logger.logfile_fd:
            content = self.bluez_logger.logfile_fd.read()
            self.dump_log_output.append(content)
            self.bluez_logger.file_position = self.bluez_logger.logfile_fd.tell()
            self.logs_layout.addWidget(self.dump_log_output)

        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.addPath(self.bluez_logger.hcidump_log_name)
        self.file_watcher.fileChanged.connect(self.update_log)

        # Add the logs_layout to the main_layout in column 2, row 0
        main_layout.addLayout(self.logs_layout, 0, 2) 

        # Back button
        back_button = QPushButton("Back")
        back_button.setFixedSize(100, 40)
        back_button.setStyleSheet("""
                    QPushButton {
                        background-color: black;
                        color: white;
                        border: 2px solid gray;
                        padding: 6px;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #333333;
                    }
                """)
        back_button.clicked.connect(self.back_callback)
        
        # Create a horizontal layout for the back button and align it to the right
        button_layout = QHBoxLayout()
        button_layout.addStretch(1) # This will push the button to the right
        button_layout.addWidget(back_button)

        # Add the button_layout to the main_layout.
        # Place it in the last column (column 2), spanning to the end.
        # Use Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom to align it to the bottom right
        main_layout.addLayout(button_layout, 1, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        
        # Set a row stretch for the row containing the main content to push the button to the bottom
        main_layout.setRowStretch(0, 1) # Give all vertical space to the content
        main_layout.setRowStretch(1, 0) # The row with the button takes minimal space


        self.setLayout(main_layout)
