import os
import psutil
import time
from pymodbus.client import ModbusSerialClient

# Define Modbus RTU connection parameters
com_port = "COM4"
baudrate = 9600
parity = 'N'   # None
databits = 8
stopbits = 1
slave_id = 1   # Change this if needed

# Function to check and kill the process using COM6
def kill_com_port(port):
    for proc in psutil.process_iter(attrs=['pid', 'name', 'open_files']):
        try:
            files = proc.info['open_files']
            if files:
                for file in files:
                    if port in file.path:
                        print(f"Killing process {proc.info['name']} (PID: {proc.info['pid']}) using {port}")
                        os.kill(proc.info['pid'], 9)  # Force kill the process
                        time.sleep(2)  # Wait for the port to be released
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

# Kill any process using COM6 before connecting
kill_com_port(com_port)

# Create Modbus RTU client
client = ModbusSerialClient(
    port=com_port,
    baudrate=baudrate,
    parity=parity,
    bytesize=databits,
    stopbits=stopbits,
    timeout=1
)

# Connect to PLC
if client.connect():
    print("Connected to PLC successfully!")

    # Write value 1 to address 4101 (Modbus address offset by -1 for pymodbus)
    write_address = 4101 - 1
    response = client.write_register(write_address, 1, unit=slave_id)

    if response.isError():
        print(f"Failed to write to address {4101}")
    else:
        print(f"Successfully wrote value 1 to address {4101}")

    # Read value from address 4106 continuously
    read_address = 4106 - 1

    while True:
        response = client.read_holding_registers(read_address, 1, unit=slave_id)
        if not response.isError():
            print(f"Read value from address {4106}: {response.registers[0]}")
        else:
            print(f"Failed to read from address {4106}")

        time.sleep(1)  # Delay to avoid excessive polling

else:
    print("Failed to connect to PLC. Check your connection settings.")

# Close the connection when done (not reached due to infinite loop)
client.close()
