from django.shortcuts import render
import serial 
import serial.tools.list_ports
import os, base64
import shutil

def fun_decode(pathdir):
    basefolder, filename = os.path.split(pathdir)
    print('your basefolder and file name is:',basefolder, filename)
    
    # Get the current file's directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print('your base_dir is :',base_dir)
    
    # Construct absolute paths for reading and writing files
    file_path = os.path.join(base_dir, "templates", "Temp", pathdir)
    print('your html pth you have now:',file_path)
    output_html = os.path.join(base_dir, "templates", basefolder, filename)
    print('your output html is:',output_html)
    
    # Read the encoded file content
    with open(file_path, "r") as file_obj:
        text = file_obj.read()
    
    encoded_string = text.encode("utf-8")
    string_bytes = base64.b64decode(encoded_string)
    
    # Write the decoded content to a new file
    with open(output_html, "wb") as f5:
        f5.write(string_bytes)
    
    return os.path.join(basefolder, filename)