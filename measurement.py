import asyncio
import serial
import json
import threading
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer

class SerialConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'serial_group'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        command = data.get('command')

        if command in ['start_serial', 'start_communication']:
            await self.start_serial_communication(data)

    async def start_serial_communication(self, data):
        self.card = data.get("card")  # Store card type for validation
        com_port = data.get('com_port')
        baud_rate = data.get('baud_rate')
        parity = data.get('parity')
        stopbit = data.get('stopbit')
        databit = data.get('databit')

        if self.configure_serial_port(com_port, baud_rate, parity, stopbit, databit):
            command_message = "MMMMMMMMMM"
            self.ser.write(command_message.encode('ASCII'))

            self.serial_thread = threading.Thread(target=self.serial_read_thread)
            self.serial_thread.daemon = True
            self.serial_thread.start()
            print("serial_thread started:", self.serial_thread)

    def configure_serial_port(self, com_port, baud_rate, parity, stopbits, bytesize):
        try:
            if not all([com_port, baud_rate, parity, stopbits, bytesize]):
                print("Missing parameters.")
                return False

            self.ser = serial.Serial(
                port=com_port,
                baudrate=int(baud_rate),
                bytesize=int(bytesize),
                timeout=None,
                stopbits=float(stopbits),
                parity=parity[0].upper()
            )
            print(f"Connected to {com_port}.")
            return True
        except (ValueError, serial.SerialException) as e:
            print(f"Error opening {com_port}: {e}")
            return False

    def serial_read_thread(self):
        try:
            accumulated_data = ""
            com_data = {}  # Dictionary to store latest received data for each COM port
            previous_data = {}  # Store previous data to check for updates

            while True:
                if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                    received_data = self.ser.read(self.ser.in_waiting).decode('ASCII')
                    accumulated_data += received_data

                    if '\r' in accumulated_data:
                        messages = accumulated_data.split('\r')
                        for message in messages:
                            if message.strip():
                                com_port = self.ser.port  # Get the COM port
                                length = len(message.strip())  # Get length of received data

                                # Validate LVDT 4CH or PIEZO 4CH
                                if hasattr(self, 'card') and self.card in ["LVDT_4CH", "PIEZO_4CH"]:
                                    extracted_values = self.extract_values(message.strip())

                                    if len(extracted_values) > 4:
                                        print(f"❌ Invalid data length ({len(extracted_values)}) received for {self.card}. Ignored!", end="\r")
                                        continue  # Ignore invalid data (less or more than 4 values)

                                    # Process only the new or updated data
                                    if com_port not in previous_data or previous_data[com_port] != message.strip():
                                        previous_data[com_port] = message.strip()

                                        # Store the updated data for each COM port
                                        com_data[com_port] = message.strip()

                                        # Print only the updated data for the specific COM port
                                        output = " | ".join([f"{port}: {data}" for port, data in com_data.items()])
                                        print(f"\r{output}", end="", flush=True)

                                        # Send valid message to WebSocket
                                        async_to_sync(self.channel_layer.group_send)(
                                            self.group_name,
                                            {
                                                'type': 'serial_message',
                                                'message': message.strip(),
                                                'com_port': com_port,
                                                'length': length
                                            }
                                        )
                        accumulated_data = ""  # Reset buffer after processing

        except Exception as e:
            print(f"Error in serial read thread: {str(e)}")
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def extract_values(self, message):
        """
        Extracts values from serial message in format A+260000B+564765C+456345D+675678
        """
        import re
        pattern = r'[A-Za-z][^A-Za-z0-9\s]\d+'
        matches = re.findall(pattern, message)
        return matches

    async def serial_message(self, event):
        await self.send(text_data=json.dumps({
            'com_port': event['com_port'],
            'message': event['message'],
            'length': event['length']
        }))
