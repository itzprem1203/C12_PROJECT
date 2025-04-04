import asyncio
import serial
import json
import threading
import time
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
import sys

class SerialConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'serial_group'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        self.serial_connections = {}  # Dictionary to store COM port connections
        self.serial_threads = {}  # Dictionary to store threads for each COM port
        self.previous_data = {}  # Dictionary to store previous data for each COM port
        self.printed_lines = {}  # Dictionary to track printed lines for each COM port

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        command = data.get('command')

        if command in ['start_serial', 'start_communication']:
            await self.start_serial_communication(data)

    async def start_serial_communication(self, data):
        com_port = data.get('com_port')
        baud_rate = data.get('baud_rate')
        parity = data.get('parity')
        stopbits = data.get('stopbit')
        bytesize = data.get('databit')
        self.card = data.get("card")

        if com_port in self.serial_connections:
            print(f"{com_port} is already running.")
            return

        if await self.configure_serial_port(com_port, baud_rate, parity, stopbits, bytesize):
            command_message = "MMMMMMMMMM"  # Example command to send
            self.serial_connections[com_port].write(command_message.encode('ASCII'))
            
            serial_thread = threading.Thread(target=self.serial_read_thread, args=(com_port,), daemon=True)
            self.serial_threads[com_port] = serial_thread
            serial_thread.start()

    async def configure_serial_port(self, com_port, baud_rate, parity, stopbits, bytesize):
        try:
            if not all([com_port, baud_rate, parity, stopbits, bytesize]):
                print("Missing parameters.")
                return False

            ser = serial.Serial(
                port=com_port,
                baudrate=int(baud_rate),
                bytesize=int(bytesize),
                timeout=None,
                stopbits=float(stopbits),
                parity=parity[0].upper()
            )
            self.serial_connections[com_port] = ser
            print(f"Connected to {com_port}.")
            return True
        except (ValueError, serial.SerialException) as e:
            print(f"Error opening {com_port}: {e}")
            return False

    def serial_read_thread(self, com_port):
        try:
            ser = self.serial_connections[com_port]
            accumulated_data = ""

            while True:
                if ser.is_open and ser.in_waiting > 0:
                    received_data = ser.read(ser.in_waiting).decode('ASCII')
                    accumulated_data += received_data

                    if '\r' in accumulated_data:
                        messages = accumulated_data.split('\r')
                        accumulated_data = messages.pop()

                        # Combine and process all messages
                        for message in messages:
                            message = message.strip()
                            if message:
                                length = len(message)

                                # Check if the data has changed
                                if self.previous_data.get(com_port) != message:
                                    self.previous_data[com_port] = message

                                    # Print data on a separate line for each COM port
                                    self.print_com_port_data(com_port, message, length)
                                    
                                    # Send data through WebSocket
                                    async_to_sync(self.channel_layer.group_send)(self.group_name, {
                                        'type': 'serial_message',
                                        'message': message,
                                        'com_port': com_port,
                                        'length': length
                                    })

                time.sleep(0.1)  # Adjust sleep as necessary to reduce CPU usage
        except Exception as e:
            print(f"❌ Error in serial read thread for {com_port}: {str(e)}")
        finally:
            if ser and ser.is_open:
                ser.close()
            self.serial_connections.pop(com_port, None)
            self.serial_threads.pop(com_port, None)

    def print_com_port_data(self, com_port, message, length):
        """
        This function will print the data on a separate line for each COM port
        and ensure that only the specific COM port's line is updated.
        """
        if com_port not in self.printed_lines:
            # Print the data for the first time on a new line for this COM port
            print(f"{com_port}: {message} (Length: {length})")
            self.printed_lines[com_port] = True
        else:
            # To ensure proper line update without overwriting other COM ports' data
            # We print an empty line first, then print the updated data
            print(f"\n{com_port}: {message} (Length: {length})", end="")

        sys.stdout.flush()  # Ensure the output is printed immediately

    async def serial_message(self, event):
        await self.send(text_data=json.dumps({
            'com_port': event['com_port'],
            'message': event['message'],
            'length': event['length']
        }))

# communicate with plc using RS48

import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from pymodbus.client import ModbusSerialClient



class PLCConsumer(AsyncWebsocketConsumer):
    read_addresses = [4106, 4107, 4108]  # Read addresses
    write_queue = asyncio.Queue()
    
    async def connect(self):
        """WebSocket connection handler."""
        await self.accept()
        print("✅ WebSocket connection established.")

        # Initialize PLC client
        self.client = None
        self.reading_task = None
        self.writing_task = None

    async def disconnect(self, close_code):
        """WebSocket disconnection handler."""
        print("❌ WebSocket connection closed.")
        
        if self.reading_task:
            self.reading_task.cancel()
        
        if self.writing_task:
            self.writing_task.cancel()
        
        if self.client:
            self.client.close()

    async def receive(self, text_data):
        """Handles incoming WebSocket messages."""
        data = json.loads(text_data)

        if data.get("command") == "start_PLC":
            # Extract parameters
            com_port = data.get("com_port")
            baud_rate = int(data.get("baud_rate"))
            bytesize = int(data.get("databit"))
            stopbits = float(data.get("stopbit"))
            parity = data.get("parity").upper()

            if com_port:
                if not self.client or not self.client.connected:
                    await self.connect_to_plc(com_port, baud_rate, bytesize, stopbits, parity)
                else:
                    print("✅ Already connected to PLC.")
                    await self.send(json.dumps({"status": "success", "message": "Already connected to PLC."}))
            else:
                await self.send(json.dumps({"status": "error", "message": "Invalid PLC parameters."}))

        elif data.get("action") == "write":
            address = data["address"]  # No offset subtraction
            value = data["value"]
            await self.write_queue.put((address, value))

        elif data.get("action") == "read":
            address = data["address"]
            read_data = await self.read_from_plc(address)
            response = {"status": "success" if read_data is not None else "error", "address": address, "value": read_data}
            await self.send(json.dumps(response))

    async def connect_to_plc(self, com_port, baud_rate, bytesize, stopbits, parity):
        """Connect to the PLC dynamically."""
        print(f"🔄 Connecting to PLC on {com_port} at {baud_rate} baud...")

        self.client = ModbusSerialClient(
            port=com_port,
            baudrate=baud_rate,
            stopbits=stopbits,
            bytesize=bytesize,
            parity=parity,
            timeout=1
        )

        if self.client.connect():
            print("✅ PLC connected successfully!")
            await self.send(json.dumps({"status": "success", "message": "PLC connected successfully."}))

            # Start read & write tasks
            self.reading_task = asyncio.create_task(self.read_loop())
            self.writing_task = asyncio.create_task(self.process_write_queue())
        else:
            print("❌ Failed to connect to PLC.")
            await self.send(json.dumps({"status": "error", "message": "Failed to connect to PLC."}))

    async def process_write_queue(self):
        """Processes the write queue and writes data to the PLC."""
        while True:
            address, value = await self.write_queue.get()
            
            if not self.client or not self.client.connected:
                print(f"❌ Write failed: PLC not connected. Address: {address}, Value: {value}")
                continue  # Skip writing if not connected

            try:
                print(f"📝 Writing - Address: {address}, Value: {value}")
                result = self.client.write_register(address, value)

                if result.isError():
                    print(f"⚠️ Write failed at address {address}")
                else:
                    print(f"✅ Write successful at address {address}")

            except Exception as e:
                print(f"❌ Error writing to PLC: {e}")

    async def read_from_plc(self, address):
        """Reads data from the PLC at the given address."""
        if not self.client or not self.client.connected:
            print(f"❌ Cannot read: PLC not connected. Address: {address}")
            return None

        try:
            result = self.client.read_holding_registers(address, count=1)
            
            if result.isError():
                print(f"⚠️ Read failed at address {address}")
                return None

            return result.registers[0]  # Return the read value
        except Exception as e:
            print(f"❌ Error reading PLC address {address}: {e}")
            return None

            

    async def read_loop(self):
        """Continuously reads specified addresses from the PLC."""
        while True:
            if not self.client.connected:
                print("❌ PLC not connected for reading. Retrying...")
                await asyncio.sleep(2)
                continue

            for address in self.read_addresses:
                try:
                    result = self.client.read_holding_registers(address, count=1)
                    if result.isError():
                        print(f"⚠️ Address {address} not ready. Skipping...")
                        continue

                    read_data = result.registers[0]
                    await self.send(json.dumps({
                        "status": "success",
                        "address": address,
                        "value": read_data
                    }))
                    print(f"📡 Read Address {address}: {read_data}")

                except Exception as e:
                    print(f"❌ Error reading from PLC at address {address}: {e}")

                await asyncio.sleep(1)
