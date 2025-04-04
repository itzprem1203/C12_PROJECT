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
    async def connect(self):
        await self.accept()
        print("✅ WebSocket connection established.")

        # Start continuous reading in the background
        asyncio.create_task(self.continuous_read())

    async def disconnect(self, close_code):
        print("❌ WebSocket connection closed.")

    async def receive(self, text_data):
        data = json.loads(text_data)

        # Modbus Write Address
        write_address = 2   # 400001 in 0-based Modbus
        value_to_write = 0 

        print(f"🔄 Attempting to connect to PLC on COM4...")
        plc_connected = await self.check_plc_connection()

        if plc_connected:
            print("✅ PLC is connected.")

            # Step 1: Write Value to PLC
            success = await self.write_to_plc(write_address, value_to_write)

            if success:
                await self.send(json.dumps({"status": "success", "message": f"Data written to address 400001"}))
            else:
                await self.send(json.dumps({"status": "error", "message": "Failed to write to PLC"}))
        else:
            print("❌ Failed to connect to PLC.")
            await self.send(json.dumps({"status": "error", "message": "PLC not connected"}))

    async def continuous_read(self):
        """Continuously reads from Modbus register 400023 every second."""
        read_address = 22  # 400023 in 0-based Modbus

        while True:
            read_data = await self.read_from_plc(read_address)
            print('your data from this port is this:',read_data)

            if read_data is not None:
                print(f"📡 Live PLC Data {read_address + 1}: {read_data}")  # Print to terminal
            else:
                print("⚠️ Failed to read from PLC at .")

            await asyncio.sleep(1)  # Wait for 1 second before reading again

    async def check_plc_connection(self):
        """Check if PLC is connected"""
        client = ModbusSerialClient(
            port="COM4", 
            baudrate=9600, 
            stopbits=1, 
            bytesize=8, 
            parity="E", 
            timeout=1
        )

        if client.connect():
            client.close()
            return True
        else:
            return False

    async def write_to_plc(self, address, value):
        """Writes a value to the specified Modbus register"""
        client = ModbusSerialClient(
            port="COM6", 
            baudrate=9600, 
            stopbits=1, 
            bytesize=8, 
            parity="N", 
            timeout=1
        )

        try:
            if not client.connect():
                print("❌ Failed to connect to PLC for writing.")
                return False

            print(f"📝 Sending Write Request - Address: {address}, Value: {value}")

            result = client.write_register(address, value)

            if result.isError():
                print(f"⚠️ Error writing to PLC at address {address}")
                return False

            print(f"✅ Write Successful - Address: {address}, Value: {value}")
            return True

        except Exception as e:
            print(f"❌ Error writing to PLC: {e}")
            return False

        finally:
            client.close()

    async def read_from_plc(self, address):
        """Reads a value from the specified Modbus register"""
        client = ModbusSerialClient(
            port="COM6", 
            baudrate=9600, 
            stopbits=1, 
            bytesize=8, 
            parity="N", 
            timeout=1
        )

        try:
            if not client.connect():
                print("❌ Failed to connect to PLC for reading.")
                return None

            print(f"🔍 Sending Read Request - Address: {address}")

            result = client.read_holding_registers(address, count=1)

            if result.isError():
                print(f"⚠️ Error reading from PLC at Address: {address}")
                return None

            data = result.registers[0] if result.registers else None
            print(f"✅ Read Successful -  Data: {data}")
            return data

        except Exception as e:
            print(f"❌ Error reading from PLC: {e}")
            return None

        finally:
            client.close()


