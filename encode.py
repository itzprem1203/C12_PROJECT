import base64
import os

def encode_html_to_base64(file_path):
    # Open and read the HTML file in binary mode
    with open(file_path, 'rb') as file:
        file_content = file.read()

    # Encode the content using base64
    encoded_content = base64.b64encode(file_content)

    # Convert the bytes to string for easier handling
    encoded_string = encoded_content.decode('utf-8')
    
    return encoded_string

# Path to the HTML file

html_file_path = r"C:\Users\itzpr.DESKTOP-EUQC32B\Desktop\simulation_sai\simulation_sai\app\templates\app\measurement.html"

# Encode the HTML file
encoded_html = encode_html_to_base64(html_file_path)

# Print the encoded Base64 string
print(encoded_html)

# Optionally, you can write the encoded content to a file if needed
with open('encoded_probe_html.txt', 'w') as encoded_file:
    encoded_file.write(encoded_html)
