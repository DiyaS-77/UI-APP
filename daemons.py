import dbus
import dbus.service
import dbus.mainloop.glib
import os
import subprocess
import time


class BluezServices:
    """
    A wrapper around BlueZ D-Bus interfaces to manage Bluetooth operations
    such as pairing, discovery, connection, and audio streaming.
    """

    def __init__(self, interface=None):
        """
        Initializes the BluezServices class.

        Args:
            interface (str): Name of the Bluetooth interface (e.g., 'hci0').
        returns:
            None
        """
        self.interface = interface
        self.bus = dbus.SystemBus()
        self.object_manager_proxy = self.bus.get_object('org.bluez', '/')
        self.object_manager = dbus.Interface(self.object_manager_proxy, 'org.freedesktop.DBus.ObjectManager')
        self.adapter_path = f'/org/bluez/{self.interface}'
        self.adapter_proxy = self.bus.get_object('org.bluez', self.adapter_path)
        self.adapter = dbus.Interface(self.adapter_proxy, 'org.bluez.Adapter1')
        self.stream_process = None
        self.device_path = None
        self.device_address = None
        self.device_sink = None
        self.devices = {}
        self.last_session_path = None
        self.opp_process = None

    def start_discovery(self):
        """Starts Bluetooth device discovery.

        args: None
        returns: None
        """
        self.adapter.StartDiscovery()

    def stop_discovery(self):
        """Stops Bluetooth device discovery.

        args: None
        returns: None
        """
        self.adapter.StopDiscovery()

    def inquiry(self, timeout):
        """
        Performs Bluetooth device inquiry for a specified timeout.

        Args:
            timeout (int): Time in seconds to run discovery.
        returns:
            None
        """
        self.start_discovery()
        time.sleep(timeout)
        self.stop_discovery()

        devices = []
        objects = self.object_manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                devices.append(path)

        for device_path in devices:
            device_props = dbus.Interface(
                self.bus.get_object("org.bluez", device_path),
                dbus_interface="org.freedesktop.DBus.Properties"
            )
            address = device_props.Get("org.bluez.Device1", "Address")
            name = device_props.Get("org.bluez.Device1", "Alias")
            print("Device Address:", address)
            print("Device Name:", name)

    def pair(self, address):
        """
        Attempts to pair with a Bluetooth device.

        Args:
            address (str): Bluetooth MAC address.

        Returns:
            bool: True if pairing is successful, else False.
        """
        device_path = self.find_device_path(address)
        if not device_path:
            print("Device path not found for pairing")
            return False

        try:
            device = dbus.Interface(
                self.bus.get_object("org.bluez", device_path),
                dbus_interface="org.bluez.Device1"
            )
            print(f"Initiating pairing with {device_path}")
            device.Pair()

            props = dbus.Interface(
                self.bus.get_object("org.bluez", device_path),
                "org.freedesktop.DBus.Properties"
            )

            for _ in range(20):  # Wait for up to 10 seconds
                if props.Get("org.bluez.Device1", "Paired"):
                    print("Pairing is successful")
                    return True
                time.sleep(0.5)

            print("Pairing attempted but not confirmed")
            return False

        except dbus.exceptions.DBusException as e:
            print(f"Pairing failed: {e.get_dbus_message()}")
            return False
        except Exception as e:
            print(f"Unexpected error during pairing: {e}")
            return False


    def disconnect(self, address):
        """
        Initiates BR/EDR (Classic Bluetooth) disconnection.

        Args:
            address (str): Bluetooth MAC address.

        Returns:
            bool: True if connected, else False.
        """
        device_path = self.find_device_path(address)
        if not device_path:
            print("Device path not found for connection")
            return False


        device = dbus.Interface(
                self.bus.get_object("org.bluez", device_path),
                dbus_interface="org.bluez.Device1"
            )
        device.Disconnect()
        return True


    def unpair_device(self, address):
        """
        Initiates BR/EDR (Classic Bluetooth) disconnection.

        Args:
            address (str): Bluetooth MAC address.

        Returns:
            bool: True if connected, else False.
        """
        device_path = self.find_device_path(address)
        if not device_path:
            print("Device path not found for connection")
            return False



        device = dbus.Interface(
                self.bus.get_object("org.bluez", device_path),
                dbus_interface="org.bluez.Device1"
            )
        self.adapter.RemoveDevice(device_path)
        return True

    def br_edr_connect(self, address):
        """
        Initiates BR/EDR (Classic Bluetooth) connection.

        Args:
            address (str): Bluetooth MAC address.

        Returns:
            bool: True if connected, else False.
        """
        device_path = self.find_device_path(address)
        if not device_path:
            print("Device path not found for connection")
            return False

        try:
            device = dbus.Interface(
                self.bus.get_object("org.bluez", device_path),
                dbus_interface="org.bluez.Device1"
            )
            device.Connect()

            props = dbus.Interface(
                self.bus.get_object("org.bluez", device_path),
                "org.freedesktop.DBus.Properties"
            )
            if props.Get("org.bluez.Device1", "Connected"):
                print("Connection is successful")
                return True
            else:
                print("Connection attempted but not confirmed")
                return False

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def le_connect(self, address):
        """
        Initiates Low Energy (LE) connection using a specific profile.

        Args:
            address (str): Bluetooth MAC address.
        returns:
            None
        """
        device_path = self.find_device_path(address)
        if device_path:
            try:
                device = dbus.Interface(
                    self.bus.get_object("org.bluez", device_path),
                    dbus_interface="org.bluez.Device1"
                )
                device.ConnectProfile('0000110e-0000-1000-8000-00805f9b34fb')  # HID Profile
            except Exception as e:
                print("LE Connection has failed:", e)

    def set_discoverable_on(self):
        """
        Makes the Bluetooth device discoverable.

        args: None
        return: None
        """
        print("Setting Bluetooth device to be discoverable...")
        command = f"hciconfig {self.interface} piscan"
        subprocess.run(command, shell=True)
        print("Bluetooth device is now discoverable.")

    def set_discoverable_off(self):
        """
        Makes the Bluetooth device non-discoverable.

        args: None
        return: None
        """
        print("Setting Bluetooth device to be non-discoverable...")
        command = f"hciconfig {self.interface} noscan"
        subprocess.run(command, shell=True)
        print("Bluetooth device is now non-discoverable.")

    def is_device_paired(self, device_address):
        """
        Checks if the specified device is paired.

        Args:
            device_address (str): Bluetooth MAC address.

        Returns:
            bool: True if paired, False otherwise.
        """
        device_path = self.find_device_path(device_address)
        if not device_path:
            return False

        props = dbus.Interface(
            self.bus.get_object("org.bluez", device_path),
            "org.freedesktop.DBus.Properties"
        )
        try:
            return props.Get("org.bluez.Device1", "Paired")
        except dbus.exceptions.DBusException:
            return False

    def is_device_connected(self, device_address):
        """
        Checks if the specified device is connected.

        Args:
            device_address (str): Bluetooth MAC address.

        Returns:
            bool: True if connected, False otherwise.
        """
        device_path = self.find_device_path(device_address)
        if not device_path:
            return False

        props = dbus.Interface(
            self.bus.get_object("org.bluez", device_path),
            "org.freedesktop.DBus.Properties"
        )
        try:
            return props.Get("org.bluez.Device1", "Connected")
        except dbus.exceptions.DBusException:
            return False

    def set_device_address(self, address):
        """
        Sets the current Bluetooth device for media streaming/control.

        Args:
            address (str): Bluetooth MAC address.
        returns:
            None
        """
        self.device_address = address
        self.device_path = self.find_device_path(address)
        self.device_sink = self.get_sink_for_device(address)

    def get_sink_for_device(self, address):
        """
        Finds the PulseAudio sink associated with a Bluetooth device.

        Args:
            address (str): Bluetooth MAC address.

        Returns:
            str | None: Sink name if found, else None.
        """
        try:
            sinks_output = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
            address_formatted = address.replace(":", "_").lower()
            for line in sinks_output.splitlines():
                if address_formatted in line.lower():
                    return line.split()[1]
        except Exception as e:
            print(f"Error getting sink for device: {e}")
        return None

    def _get_device_path(self):
        """
        Constructs a DBus path from the device's MAC address.

        args : None
        Returns:
            str: Full device object path.

        Raises:
            Exception: If device address is not set.
        """
        if not self.device_address:
            raise Exception("Device address not set")
        formatted_address = self.device_address.replace(":", "_")
        return f"/org/bluez/{self.interface}/dev_{formatted_address}"

    def find_device_path(self, address):
        """
        Finds the DBus path for a device with the given Bluetooth address.

        Args:
            address (str): Bluetooth MAC address.

        Returns:
            str | None: Object path if found, else None.
        """
        objects = self.object_manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                props = interfaces["org.bluez.Device1"]
                if props.get("Address") == address:
                    return path
        return None

    def refresh_device_list(self):
        """
        Updates the internal device list with currently available devices.

        args: None
        returns: None
        """
        self.devices.clear()
        objects = self.object_manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                props = interfaces["org.bluez.Device1"]
                address = props.get("Address")
                name = props.get("Name", "Unknown")
                uuids = props.get("UUIDs", [])
                connected = props.get("Connected", False)
                if address:
                    self.devices[address] = {
                        "Name": name,
                        "UUIDs": uuids,
                        "Connected": connected,
                    }
    '''
    def get_paired_devices(self):
        """
        Retrieves a dictionary of currently paired Bluetooth devices for the active interface.

        Returns:
            dict: Mapping of device addresses to names.
        """
        paired = {}
        objects = self.object_manager.GetManagedObjects()
        controller_path = f"/org/bluez/{self.interface}"

        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces and path.startswith(controller_path):
                props = interfaces["org.bluez.Device1"]
                if props.get("Paired", False):
                    address = props.get("Address")
                    name = props.get("Name", "Unknown")
                    paired[address] = name
        return paired

    def get_connected_devices(self):
        """
        Retrieves a dictionary of currently connected Bluetooth devices for the active interface.

        Returns:
            dict: Mapping of device addresses to names.
        """
        connected = {}
        objects = self.object_manager.GetManagedObjects()
        controller_path = f"/org/bluez/{self.interface}"

        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces and path.startswith(controller_path):
                props = interfaces["org.bluez.Device1"]
                if props.get("Connected", False):
                    address = props.get("Address")
                    name = props.get("Name", "Unknown")
                    connected[address] = name
        return connected
    '''

    def get_paired_devices(self):
        """
        Retrieves a dictionary of currently connected Bluetooth devices.

        args : None
        Returns:
            dict: Mapping of device addresses to names.
        """
        connected = {}
        objects = self.object_manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                props = interfaces["org.bluez.Device1"]
                if props.get("Paired", False):
                    address = props.get("Address")
                    name = props.get("Name", "Unknown")
                    connected[address] = name
        return connected

    def get_connected_devices(self):
        """
        Retrieves a dictionary of currently connected Bluetooth devices.

        args : None
        Returns:
            dict: Mapping of device addresses to names.
        """
        connected = {}
        objects = self.object_manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                props = interfaces["org.bluez.Device1"]
                if props.get("Connected", False):
                    address = props.get("Address")
                    name = props.get("Name", "Unknown")
                    connected[address] = name
        return connected
