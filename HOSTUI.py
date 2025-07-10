import os
import dbus

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea, QListWidgetItem
from PyQt6.QtWidgets import QGridLayout
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QTextBrowser
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtWidgets import QTabWidget
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QComboBox

from test_automation.UI.Backend_lib.Linux.filewatcher import BluezLogger
# from test_automation.UI.Backend_lib.Linux.bluez_utils import BluezLogger
from test_automation.UI.UI_lib.controller_lib import Controller
from test_automation.UI.logger import Logger
from test_automation.UI.Backend_lib.Linux.a2dp_profile import A2DPManager
from test_automation.UI.Backend_lib.Linux.opp_profile import OPPManager
from test_automation.UI.Backend_lib.Linux.daemons import BluezServices


class Controller:
    """
    Represents the local Bluetooth controller.

    Stores HCI version, manufacturer details, address, and link policies.
    """

    def __init__(self):
        self.name = None
        self.bd_address = None
        self.link_mode = None
        self.link_policy = None
        self.hci_version = None
        self.lmp_version = None
        self.manufacturer = None


class TestApplication(QWidget):
    """
    Main GUI class for the Bluetooth Test Host.

    Handles Bluetooth discovery, pairing, connection (BR/EDR & LE), A2DP streaming,
    and media control operations using BlueZ and PulseAudio.
    """

    def __init__(self, interface=None, log_path=None, back_callback=None):
        """
        Initialize the TestApplication widget.

        Args:
            interface (str): Bluetooth adapter interface (e.g., hci0).
            log_path (str): Path to the log file for capturing events.
            back_callback (callable): Optional callback to trigger on back action.

        returns:
            None
        """
        super().__init__()
        self.log = Logger("UI")
        self.log_path = log_path
        self.bluez_logger = BluezLogger(self.log_path)
        self.interface = interface
        self.discovery_active = False
        self.back_callback = back_callback
        self.controller = Controller()
        self.test_application_clicked()
        self.bluetooth_device_manager = BluezServices(interface=self.interface)
        self.a2dp_manager = A2DPManager(interface=self.interface)
        self.opp_manager = OPPManager()
        self.device_address_source = None
        self.device_address_sink = None
        # self.defer_log_start()

    def defer_log_start(self):
        QTimer.singleShot(100, self.start_logs)

    def start_logs(self):
        self.bluez_logger.start_bluetoothd_logs(self.bluetoothd_log_text_browser)
        self.bluez_logger.start_pulseaudio_logs(self.pulseaudio_log_text_browser)
        # self.bluez_logger.start_dump_logs(
        #   interface=self.interface,
        #  log_text_browser=self.hci_dump_log_text_browser)

    def set_discoverable_on(self):
        """
        Set the local Bluetooth device to discoverable mode.
        Starts a timeout if specified in the UI input.

        args: None
        returns: None
        """
        print("Discoverable is set to ON")
        self.set_discoverable_on_button.setEnabled(False)
        self.set_discoverable_off_button.setEnabled(True)
        self.bluetooth_device_manager.set_discoverable_on()
        timeout = int(self.discoverable_timeout_input.text())
        if timeout > 0:
            self.discoverable_timeout_timer = QTimer()
            self.discoverable_timeout_timer.timeout.connect(self.set_discoverable_off)
            self.discoverable_timeout_timer.start(timeout * 1000)

    def set_discoverable_off(self):
        """
        Disable discoverable mode on the Bluetooth adapter.
        Stops any active discoverable timer.

        args: None
        returns: None
        """
        print("Discoverable is set to OFF")
        self.set_discoverable_on_button.setEnabled(True)
        self.set_discoverable_off_button.setEnabled(False)
        self.bluetooth_device_manager.set_discoverable_off()
        if hasattr(self, 'discoverable_timeout_timer'):
            self.discoverable_timeout_timer.stop()

    def inquiry(self):
        """Function for Inquiry"""

    def set_discovery_on(self):
        """
        Start device discovery.
        If a timeout is specified, stops discovery and shows results after the timeout.

        args: None
        returns: None
        """
        print("Discovery has started")
        self.inquiry_timeout = int(self.inquiry_timeout_input.text()) * 1000
        if self.inquiry_timeout == 0:
            self.set_discovery_on_button.setEnabled(False)
            self.set_discovery_off_button.setEnabled(True)
            self.bluetooth_device_manager.start_discovery()
        else:
            self.timer = QTimer()
            self.timer.timeout.connect(self.show_discovery_table_timeout)
            self.timer.timeout.connect(lambda: self.set_discovery_off_button.setEnabled(False))
            self.timer.start(self.inquiry_timeout)
            self.set_discovery_on_button.setEnabled(False)
            self.set_discovery_off_button.setEnabled(True)
            self.bluetooth_device_manager.start_discovery()

    def show_discovery_table_timeout(self):
        """Function to show the discovery table when timeout is over

        args: None
        returns: None
        """
        self.timer.stop()
        self.bluetooth_device_manager.stop_discovery()
        self.show_discovery_table()

    def set_discovery_off(self):
        """Function for Stop Discovery

        args: None
        returns: None
        """

        print("Discovery has stopped")
        self.set_discovery_off_button.setEnabled(False)
        self.timer = QTimer()
        if self.inquiry_timeout == 0:
            self.bluetooth_device_manager.stop_discovery()
            self.show_discovery_table()
        else:
            self.timer.stop()
            self.bluetooth_device_manager.stop_discovery()
            self.show_discovery_table()
            self.set_discovery_off_button.setEnabled(False)

    def show_discovery_table(self):
        """
        Display discovered devices in a table with options to pair or connect (BR/EDR, LE).
        """
        self.timer.stop()
        bold_font = QFont()
        bold_font.setBold(True)
        bus = dbus.SystemBus()
        om = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = om.GetManagedObjects()
        devices = [path for path, interfaces in objects.items() if "org.bluez.Device1" in interfaces]
        self.table_widget = QTableWidget(len(devices), 3)
        self.table_widget.setHorizontalHeaderLabels(["DEVICE NAME", "BD_ADDR", "PROCEDURES"])
        self.table_widget.setFont(bold_font)
        self.table_widget.setFixedSize(475, 180)

        for i, device_path in enumerate(devices):
            device = dbus.Interface(bus.get_object("org.bluez", device_path), dbus_interface="org.bluez.Device1")
            device_props = dbus.Interface(bus.get_object("org.bluez", device_path),
                                          dbus_interface="org.freedesktop.DBus.Properties")
            device_address = device_props.Get("org.bluez.Device1", "Address")
            device_name = device_props.Get("org.bluez.Device1", "Alias")
            self.table_widget.setItem(i, 0, QTableWidgetItem(device_name))
            self.table_widget.setItem(i, 1, QTableWidgetItem(device_address))
            self.table_widget.horizontalHeader().setStretchLastSection(True)
            button_widget = QWidget()
            button_layout = QHBoxLayout()
            pair_button = QPushButton("PAIR")
            pair_button.setFont(bold_font)
            pair_button.setStyleSheet("color:green")
            pair_button.setMinimumSize(30, 20)
            button_layout.addWidget(pair_button)

            br_edr_connect_button = QPushButton("BR_EDR_CONNECT")
            br_edr_connect_button.setFont(bold_font)
            br_edr_connect_button.setStyleSheet("color:green")
            br_edr_connect_button.setMinimumSize(30, 20)
            button_layout.addWidget(br_edr_connect_button)

            le_connect_button = QPushButton("LE_CONNECT")
            le_connect_button.setFont(bold_font)
            le_connect_button.setStyleSheet("color:green")
            le_connect_button.setMinimumSize(30, 20)
            button_layout.addWidget(le_connect_button)

            button_widget.setLayout(button_layout)
            self.table_widget.setCellWidget(i, 2, button_widget)
            self.gap_methods_layout.addWidget(self.table_widget)
            pair_button.clicked.connect(
                lambda checked, address=device_address: self.handle_device_action('pair', address))
            br_edr_connect_button.clicked.connect(
                lambda checked, address=device_address: self.handle_device_action('br_edr_connect', address))
            le_connect_button.clicked.connect(
                lambda checked, address=device_address: self.handle_device_action('le_connect', address))
        self.table_widget.show()
        self.set_discovery_off_button.setEnabled(False)

    def handle_device_action(self, action, address):
        """
        Handle user-selected action (pair/BR-EDR/LE connect) for a device.

        Args:
            action (str): Action to perform.
            address (str): Bluetooth device address.

        returns:
            None
        """

        self.device_address = address
        if action == 'pair':
            self.pair(address)
        elif action == 'br_edr_connect':
            self.br_edr_connect(address)
        elif action == 'le_connect':
            self.le_connect(address)

    def pair(self, device_address):
        """
        Attempt to pair with the given Bluetooth device.

        Args:
            device_address (str): Bluetooth MAC address.
        """
        print(f"Attempting to pair with {device_address}")

        # Check if already paired
        if self.bluetooth_device_manager.is_device_paired(device_address):
            QMessageBox.information(self, "Already Paired", f"{device_address} is already paired.")
            self.add_device(device_address)
            return

        # This will block until confirmation is handled
        success = self.bluetooth_device_manager.pair(device_address)

        if success:
            QMessageBox.information(self, "Pairing Result", f"Pairing with {device_address} was successful.")
            self.add_device(device_address)
        else:
            QMessageBox.critical(self, "Pairing Failed", f"Pairing with {device_address} failed.")

    def br_edr_connect(self, device_address):
        """
        Connect to a device using BR/EDR.

        Args:
            device_address (str): Bluetooth MAC address.
        returns:
            None
        """

        print(f"Attempting BR/EDR connect with {device_address}")
        success = self.bluetooth_device_manager.br_edr_connect(device_address)
        if success:
            self.add_device(device_address)
            QMessageBox.information(self, "Connection Result", f"Connection with {device_address} was successful.")
        else:
            QMessageBox.critical(self, "Connection Failed", f"Connection with {device_address} failed.")

    def le_connect(self, device_address):
        """
        Connect to a device using LE (Low Energy).

        Args:
            device_address (str): Bluetooth MAC address.
        returns:
            None
        """

        print("LE_Connect is ongoing ")
        self.bluetooth_device_manager.le_connect(device_address)
        self.add_device(device_address)

    def refresh(self):
        """
        Refresh and clear the device discovery table.

        args: None
        returns: None
        """

        print("Refresh Button is pressed")
        if hasattr(self, 'table_widget') and self.table_widget:
            self.gap_methods_layout.removeWidget(self.table_widget)
            self.table_widget.deleteLater()
            self.table_widget = None
            self.inquiry_timeout_input.setText("0")
            self.refresh_button.setEnabled(False)
            self.set_discovery_on_button.setEnabled(True)
            self.set_discovery_off_button.setEnabled(False)
            self.refresh_button.setEnabled(True)

    def refresh_discoverable(self):
        """
        Reset discoverable timeout input to default (0).

        args: None
        returns: None
        """
        print("Discoverable refresh button is pressed")
        self.discoverable_timeout_input.setText("0")

    def add_device(self, device_address):
        """
        Adds a device address below the GAP item in the profile list if not already present.
        Args:
            device_address (str): The paired/connected device MAC address (e.g., 20:32:C6:7B:91:1C)
        """
        # Find GAP index
        for i in range(self.profiles_list_widget.count()):
            if self.profiles_list_widget.item(i).text().strip() == "GAP":
                gap_index = i
                break
        else:
            return  # GAP not found

        # Check if device is already added
        for i in range(self.profiles_list_widget.count()):
            if self.profiles_list_widget.item(i).text().strip() == device_address:
                return  # Already added

        # Add device address as a new list item
        device_item = QListWidgetItem(device_address)
        device_item.setFont(QFont("Arial", 10))
        device_item.setForeground(Qt.GlobalColor.black)

        self.profiles_list_widget.insertItem(gap_index + 1, device_item)


    def profile_selected(self):
        """
        Handles profile or device selection from the list.
        Dynamically shows GAP methods or A2DP role-based tabs.
        """
        selected_text = self.profiles_list_widget.currentItem().text().strip()
        bold_font = QFont()
        bold_font.setBold(True)

        # Clear dynamic widget layout
        for i in reversed(range(self.profile_methods_layout.count())):
            item = self.profile_methods_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        # Case 1: GAP selected
        if selected_text == "GAP":
            self.profile_description_text_browser.clear()
            self.profile_description_text_browser.setFont(bold_font)
            self.profile_description_text_browser.append("GAP Profile Selected")
            self.profile_description_text_browser.append("Use the below methods as required:")
            self.show_gap_ui()
            return

        # Case 2: Device (MAC address) selected
        if self.is_valid_bd_address(selected_text):
            device_address = selected_text
            self.device_address_source = device_address
            self.device_address_sink = device_address

            self.profile_description_text_browser.clear()
            self.profile_description_text_browser.setFont(bold_font)
            self.profile_description_text_browser.append(f"Device: {device_address}")
            self.profile_description_text_browser.append("Supported Profiles: A2DP")

            self.a2dp_tab_widget = QTabWidget()
            self.a2dp_tab_widget.setFont(bold_font)
            self.a2dp_tab_widget.setStyleSheet("color:black;")

            role = self.get_a2dp_role_for_device(device_address)

            if role == "sink":
                self.a2dp_tab_widget.addTab(QWidget(), "A2DP Source")
            elif role == "source":
                self.a2dp_tab_widget.addTab(QWidget(), "A2DP Sink")
            elif role == "both":
                self.a2dp_tab_widget.addTab(QWidget(), "A2DP Source")
                self.a2dp_tab_widget.addTab(QWidget(), "A2DP Sink")
            else:
                self.profile_description_text_browser.append("⚠️ No A2DP role detected.")
                return

            self.a2dp_tab_widget.currentChanged.connect(self.on_profile_tab_changed)
            self.profile_methods_layout.addWidget(self.a2dp_tab_widget)


    def show_gap_ui(self):
        """
        Displays the GAP profile UI with Discoverable and Inquiry controls.
        """
        bold_font = QFont()
        bold_font.setBold(True)

        self.gap_methods_layout = QVBoxLayout()

        # Discoverable Section
        set_discoverable_label = QLabel("SetDiscoverable:")
        set_discoverable_label.setFont(bold_font)
        set_discoverable_label.setStyleSheet("color:black")
        self.gap_methods_layout.addWidget(set_discoverable_label)

        set_discoverable_timeout_layout = QHBoxLayout()
        timeout_label = QLabel("SetDiscoverable Timeout:")
        timeout_label.setFont(bold_font)
        timeout_label.setStyleSheet("color:blue;")
        set_discoverable_timeout_layout.addWidget(timeout_label)
        self.discoverable_timeout_input = QLineEdit("0")
        set_discoverable_timeout_layout.addWidget(self.discoverable_timeout_input)
        self.gap_methods_layout.addLayout(set_discoverable_timeout_layout)

        discoverable_buttons_layout = QHBoxLayout()
        self.set_discoverable_on_button = QPushButton("ON")
        self.set_discoverable_on_button.setFont(bold_font)
        self.set_discoverable_on_button.setStyleSheet("color:green;")
        self.set_discoverable_on_button.clicked.connect(self.set_discoverable_on)
        discoverable_buttons_layout.addWidget(self.set_discoverable_on_button)

        self.set_discoverable_off_button = QPushButton("OFF")
        self.set_discoverable_off_button.setFont(bold_font)
        self.set_discoverable_off_button.setStyleSheet("color:red;")
        self.set_discoverable_off_button.clicked.connect(self.set_discoverable_off)
        self.set_discoverable_on_button.setEnabled(True)
        self.set_discoverable_off_button.setEnabled(False)
        discoverable_buttons_layout.addWidget(self.set_discoverable_off_button)
        self.gap_methods_layout.addLayout(discoverable_buttons_layout)

        refresh_button_layout_discoverable = QVBoxLayout()
        self.refresh_button_discoverable = QPushButton("REFRESH")
        self.refresh_button_discoverable.setEnabled(True)
        self.refresh_button_discoverable.clicked.connect(self.refresh_discoverable)
        self.refresh_button_discoverable.setFont(bold_font)
        self.refresh_button_discoverable.setStyleSheet("color:green;")
        refresh_button_layout_discoverable.addWidget(self.refresh_button_discoverable)
        self.gap_methods_layout.addLayout(refresh_button_layout_discoverable)

        # Inquiry Section
        inquiry_label = QLabel("Inquiry:")
        inquiry_label.setFont(bold_font)
        inquiry_label.setStyleSheet("color:black")
        self.gap_methods_layout.addWidget(inquiry_label)

        inquiry_timeout_layout = QHBoxLayout()
        inquiry_timeout_label = QLabel("Inquiry Timeout:")
        inquiry_timeout_label.setFont(bold_font)
        inquiry_timeout_label.setStyleSheet("color:blue;")
        inquiry_timeout_layout.addWidget(inquiry_timeout_label)
        self.inquiry_timeout_input = QLineEdit("0")
        inquiry_timeout_layout.addWidget(self.inquiry_timeout_input)
        self.gap_methods_layout.addLayout(inquiry_timeout_layout)

        discovery_buttons_layout = QHBoxLayout()
        self.set_discovery_on_button = QPushButton("START")
        self.set_discovery_on_button.setFont(bold_font)
        self.set_discovery_on_button.setStyleSheet("color:green;")
        self.set_discovery_on_button.clicked.connect(self.set_discovery_on)
        discovery_buttons_layout.addWidget(self.set_discovery_on_button)

        self.set_discovery_off_button = QPushButton("STOP")
        self.set_discovery_off_button.setFont(bold_font)
        self.set_discovery_off_button.setStyleSheet("color:red;")
        self.set_discovery_off_button.clicked.connect(self.set_discovery_off)
        self.set_discovery_off_button.setEnabled(False)
        discovery_buttons_layout.addWidget(self.set_discovery_off_button)
        self.gap_methods_layout.addLayout(discovery_buttons_layout)

        refresh_button_layout = QVBoxLayout()
        self.refresh_button = QPushButton("REFRESH")
        self.refresh_button.setFont(bold_font)
        self.refresh_button.setStyleSheet("color:green;")
        self.refresh_button.clicked.connect(self.refresh)
        refresh_button_layout.addWidget(self.refresh_button)
        self.gap_methods_layout.addLayout(refresh_button_layout)

        # Set final layout
        gap_methods_widget = QWidget()
        gap_methods_widget.setLayout(self.gap_methods_layout)
        self.profile_methods_layout.addWidget(gap_methods_widget)


    def on_profile_tab_changed(self, index):
        tab_text = self.a2dp_tab_widget.tabText(index)
        current_widget = self.a2dp_tab_widget.widget(index)

        if current_widget.layout():
            return

        if tab_text == "A2DP Source":
            widget = self.build_a2dp_source_tab(self.device_address_source)
        elif tab_text == "A2DP Sink":
            widget = self.build_a2dp_sink_tab(self.device_address_sink)
        else:
            return

        layout = QVBoxLayout()
        layout.addWidget(widget)
        current_widget.setLayout(layout)


    def get_a2dp_role_for_device(self, device_address):
        sinks = self.a2dp_manager.get_connected_a2dp_sink_devices()
        sources = self.a2dp_manager.get_connected_a2dp_source_devices()

        if device_address in sinks and device_address in sources:
            return "both"
        elif device_address in sinks:
            return "sink"
        elif device_address in sources:
            return "source"
        return None


    def test_application_clicked(self):
        """
           Create and display the main testing application GUI.

           This interface consists of:
           - A profile selection list
           - Bluetooth controller details
           - A dynamic area for profile-specific UI (e.g., GAP, A2DP)
           - Three log viewers: Bluetoothd, PulseAudio, and HCI Dump
           - A back button to return to the previous window

           args: None
           returns: None
        """

        # Create the main grid
        self.main_grid_layout = QGridLayout()

        # Grid 1 Up : List of Profiles
        bold_font = QFont()
        bold_font.setBold(True)
        self.profiles_list_widget = QListWidget()
        profiles_list_label = QLabel("List of Profiles:")
        profiles_list_label.setFont(bold_font)
        profiles_list_label.setStyleSheet("color:black")
        self.main_grid_layout.addWidget(profiles_list_label, 0, 0)
        self.profiles_list_widget.addItem("GAP")
        self.profiles_list_widget.setFont(bold_font)
        self.profiles_list_widget.setStyleSheet("border: 3px solid black;color: black;background: transparent;")
        self.profiles_list_widget.itemSelectionChanged.connect(self.profile_selected)
        self.profiles_list_widget.setFixedWidth(350)
        self.main_grid_layout.addWidget(self.profiles_list_widget, 1, 0, 2, 2)

        # Grid 1 Down : Controller Details
        controller_details_widget = QWidget()
        controller_details_layout = QVBoxLayout()
        controller_details_widget.setStyleSheet("border: 2px solid black;color: black;background: transparent;")
        controller_details_widget.setFont(bold_font)
        self.main_grid_layout.addWidget(controller_details_widget, 3, 0, 8, 2)
        controller_details_layout.setContentsMargins(0, 0, 0, 0)
        controller_details_layout.setSpacing(0)

        self.bluez_logger.get_controller_details(interface=self.interface)

        self.controller.name = self.bluez_logger.name
        self.controller.bd_address = self.bluez_logger.bd_address
        self.controller.link_policy = self.bluez_logger.link_policy
        self.controller.lmp_version = self.bluez_logger.lmp_version
        self.controller.link_mode = self.bluez_logger.link_mode
        self.controller.hci_version = self.bluez_logger.hci_version
        self.controller.manufacturer = self.bluez_logger.manufacturer

        controller_details_label = QLabel("Controller Details:")
        controller_details_label.setFont(bold_font)
        controller_details_layout.addWidget(controller_details_label)

        # Controller Info Fields
        info_fields = [
            ("Controller Name:", self.controller.name),
            ("Controller Address:", self.controller.bd_address),
            ("Link Mode:", self.controller.link_mode),
            ("Link Policy:", self.controller.link_policy),
            ("HCI Version:", self.controller.hci_version),
            ("LMP Version:", self.controller.lmp_version),
            ("Manufacturer:", self.controller.manufacturer)
        ]

        for label, value in info_fields:
            layout = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFont(bold_font)
            layout.addWidget(lbl)
            val = QLabel(value)
            layout.addWidget(val)
            controller_details_layout.addLayout(layout)

        controller_details_widget.setLayout(controller_details_layout)
        controller_details_widget.setFixedWidth(350)

        # Profile UI Placeholder (for GAP/A2DP tabs)
        self.profile_methods_layout = QHBoxLayout()
        self.profile_methods_widget = QWidget()
        self.profile_methods_widget.setLayout(self.profile_methods_layout)
        self.main_grid_layout.addWidget(self.profile_methods_widget, 2, 2, 8, 2)

        # Grid3: HCI Dump Logs
        dump_logs_label = QLabel("Dump Logs:")
        dump_logs_label.setFont(bold_font)
        dump_logs_label.setStyleSheet("color: black;")
        self.main_grid_layout.addWidget(dump_logs_label, 0, 4)
        self.dump_logs_text_browser = QTabWidget()
        self.main_grid_layout.addWidget(self.dump_logs_text_browser, 1, 4, 10, 2)
        self.dump_logs_text_browser.setStyleSheet("border: 2px solid black;color: black; background-color: lightblue;")
        self.dump_logs_text_browser.setFixedWidth(400)

        self.bluetoothd_log_text_browser = QTextEdit()
        self.bluetoothd_log_text_browser.setFont(bold_font)
        self.bluetoothd_log_text_browser.setReadOnly(True)

        self.pulseaudio_log_text_browser = QTextEdit()
        self.pulseaudio_log_text_browser.setFont(bold_font)
        self.pulseaudio_log_text_browser.setReadOnly(True)

        self.hci_dump_log_text_browser = QTextEdit()
        self.hci_dump_log_text_browser.setFont(bold_font)
        self.hci_dump_log_text_browser.setReadOnly(True)

        self.dump_logs_text_browser.addTab(self.bluetoothd_log_text_browser, "Bluetoothd_Logs")
        self.dump_logs_text_browser.addTab(self.pulseaudio_log_text_browser, "Pulseaudio_Logs")
        self.dump_logs_text_browser.addTab(self.hci_dump_log_text_browser, "HCI_Dump_Logs")

        self.bluez_logger.start_bluetoothd_logs(self.bluetoothd_log_text_browser)
        self.bluez_logger.start_pulseaudio_logs(self.pulseaudio_log_text_browser)
        self.bluez_logger.start_dump_logs(interface=self.interface, log_text_browser=self.hci_dump_log_text_browser)

        # Back Button
        back_button = QPushButton("Back")
        back_button.setStyleSheet("font-size: 16px; padding: 6px;")
        back_button.clicked.connect(self.back_callback)
        back_button_layout = QHBoxLayout()
        back_button_layout.addWidget(back_button)
        back_button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_grid_layout.addLayout(back_button_layout, 11, 0, 1, 1)

        self.setLayout(self.main_grid_layout)


    def start_streaming(self):
        audio_path = self.audio_location_input.text().strip()
        if not audio_path or not os.path.exists(audio_path):
            QMessageBox.warning(self, "Invalid Audio File", "Please select a valid audio file to stream.")
            return

        if not self.device_address_source:
            QMessageBox.warning(self, "No Device", "Device address not available for streaming.")
            return

        print(f"A2DP streaming started with file: {audio_path} on device: {self.device_address_source}")

        self.start_streaming_button.setEnabled(False)
        self.stop_streaming_button.setEnabled(True)

        success = self.a2dp_manager.start_streaming(self.device_address_source, audio_path)

        if not success:
            QMessageBox.critical(self, "Streaming Failed", "Failed to start streaming.")
            self.start_streaming_button.setEnabled(True)
            self.stop_streaming_button.setEnabled(False)

    def stop_streaming(self):
        print("A2DP streaming stopped")
        self.start_streaming_button.setEnabled(True)
        self.stop_streaming_button.setEnabled(False)
        self.a2dp_manager.stop_streaming()
        if hasattr(self, 'streaming_timer'):
            self.streaming_timer.stop()

    def play(self):
        print("Play button has been pressed")
        if self.device_address_sink:
            self.a2dp_manager.play(self.device_address_sink)
        else:
            QMessageBox.warning(self, "No Device", "Sink device address not available.")

    def pause(self):
        print("Pause button has been pressed")
        if self.device_address_sink:
            self.a2dp_manager.pause(self.device_address_sink)
        else:
            QMessageBox.warning(self, "No Device", "Sink device address not available.")

    def next(self):
        print("Next button pressed")
        if self.device_address_sink:
            self.a2dp_manager.next(self.device_address_sink)
        else:
            QMessageBox.warning(self, "No Device", "Sink device address not available.")

    def previous(self):
        print("Previous button pressed")
        if self.device_address_sink:
            self.a2dp_manager.previous(self.device_address_sink)
        else:
            QMessageBox.warning(self, "No Device", "Sink device address not available.")

    def rewind(self):
        print("Rewind button pressed")
        if self.device_address_sink:
            self.a2dp_manager.rewind(self.device_address_sink)
        else:
            QMessageBox.warning(self, "No Device", "Sink device address not available.")

    def browse_audio_file(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(None, "Select Audio File", "",
                                                   "Audio Files (*.mp3 *.wav *.ogg *.flac);;All Files (*)")
        if file_path:
            self.audio_location_input.setText(file_path)

    def build_a2dp_source_tab(self):
        bold_font = QFont()
        bold_font.setBold(True)

        layout = QVBoxLayout()
        label = QLabel("A2DP Streaming:")
        label.setFont(bold_font)
        layout.addWidget(label)

        # Audio file selection
        audio_layout = QHBoxLayout()
        audio_label = QLabel("Audio Location:")
        audio_label.setFont(bold_font)
        audio_layout.addWidget(audio_label)
        self.audio_location_input = QLineEdit()
        self.audio_location_input.setReadOnly(True)
        audio_layout.addWidget(self.audio_location_input)
        browse_button = QPushButton("Browse")
        browse_button.setFont(bold_font)
        browse_button.clicked.connect(self.browse_audio_file)
        audio_layout.addWidget(browse_button)
        layout.addLayout(audio_layout)

        # Start/Stop buttons
        button_layout = QHBoxLayout()
        self.start_streaming_button = QPushButton("Start Streaming")
        self.start_streaming_button.setFont(bold_font)
        self.start_streaming_button.clicked.connect(self.start_streaming)
        button_layout.addWidget(self.start_streaming_button)

        self.stop_streaming_button = QPushButton("Stop Streaming")
        self.stop_streaming_button.setFont(bold_font)
        self.stop_streaming_button.clicked.connect(self.stop_streaming)
        self.stop_streaming_button.setEnabled(False)
        button_layout.addWidget(self.stop_streaming_button)

        layout.addLayout(button_layout)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def build_a2dp_sink_tab(self):
        bold_font = QFont()
        bold_font.setBold(True)

        layout = QVBoxLayout()
        label = QLabel("Media Control:")
        label.setFont(bold_font)
        layout.addWidget(label)

        control_buttons = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setFont(bold_font)
        self.play_button.clicked.connect(self.play)
        control_buttons.addWidget(self.play_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setFont(bold_font)
        self.pause_button.clicked.connect(self.pause)
        control_buttons.addWidget(self.pause_button)

        self.next_button = QPushButton("Next")
        self.next_button.setFont(bold_font)
        self.next_button.clicked.connect(self.next)
        control_buttons.addWidget(self.next_button)

        self.previous_button = QPushButton("Previous")
        self.previous_button.setFont(bold_font)
        self.previous_button.clicked.connect(self.previous)
        control_buttons.addWidget(self.previous_button)

        self.rewind_button = QPushButton("Rewind")
        self.rewind_button.setFont(bold_font)
        self.rewind_button.clicked.connect(self.rewind)
        control_buttons.addWidget(self.rewind_button)

        layout.addLayout(control_buttons)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def on_device_selected_for_a2dp(self, device_address):
        self.device_address_source = device_address
        print(f"Selected device address for streaming: {self.device_address_source}")

    def on_device_selected_for_a2dp_sink(self, device_address):
        self.device_address_sink = device_address
        print(f"Selected sink device address for media control: {self.device_address_sink}")
    #------TEST
    ##APPLICTION
    #CLICKED - ----------------------------

