import os
import json
import psycopg2
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from app.models import BackupSettings  # Import your BackupSettings model
from threading import Thread
from datetime import datetime
import openpyxl
import time

# Database credentials
db_name = 'postgres'
db_user = 'postgres'
db_password = 'sai@123'
db_host = 'localhost'
db_port = '5432'

def backup(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        id_value = data.get('idValue')
        confirm_value = data.get('confirm')
        date_back = data.get('backup_date')
        print('Your changed id values are:', id_value, confirm_value, date_back)

        # Update the existing BackupSettings instance
        backup_setting = get_object_or_404(BackupSettings, id=id_value)
        backup_setting.backup_date = date_back
        backup_setting.confirm_backup = confirm_value
        backup_setting.save()

        # Create a new BackupSettings instance after 2 seconds
        Thread(target=create_new_backup_setting, args=(date_back, confirm_value)).start()

        return JsonResponse({'status': 'success', 'message': 'Backup settings updated and new entry will be created! and backup also saved in your downloads!'})

    return render(request, 'app/home.html')


def create_new_backup_setting(existing_backup_date, confirm_value):
    if confirm_value == 'True':  # Check if the backup is confirmed
        time.sleep(2)  # Delay for 2 seconds

        # Parse the existing backup date (ensure the input format is correct)
        existing_date = datetime.strptime(existing_backup_date, '%d-%m-%Y %I:%M:%S %p')

        # Call the backup function to save to .xlsx format
        backup_database_to_xlsx()

        # Calculate new backup date (same day, next month)
        new_month = existing_date.month + 1 if existing_date.month < 12 else 1
        new_year = existing_date.year if existing_date.month < 12 else existing_date.year + 1

        # Replace with the new month and year, keeping other components the same
        new_backup_date = existing_date.replace(month=new_month, year=new_year)

        # Format the new backup date to the desired format (dd-mm-yy hh:mm:ss AM/PM)
        formatted_new_backup_date = new_backup_date.strftime('%d-%m-%Y %I:%M:%S %p')

        # Print the new formatted backup date
        print('Your new backup_date is this:', formatted_new_backup_date)

        # Create a new BackupSettings record with the new date and confirm_backup set to False
        BackupSettings.objects.create(
            backup_date=formatted_new_backup_date,  # Save the formatted date
            confirm_backup=False  # Set confirm_backup to False for the new record
        )

def backup_database_to_xlsx():
    # Create a main backup directory if it doesn't exist
    main_backup_folder = os.path.join(os.path.expanduser('~/Downloads'), 'backup')
    os.makedirs(main_backup_folder, exist_ok=True)

    # Create a timestamp for the current backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_folder = os.path.join(main_backup_folder, f'backup_{timestamp}')
    os.makedirs(backup_folder, exist_ok=True)

    # Connect to the PostgreSQL database
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        cursor = conn.cursor()

        # Create a new Excel workbook
        workbook = openpyxl.Workbook()

        # Specify the models (tables) you want to back up
        models = [
            "app_probe_calibrations",
            "app_tableonedata",
            "app_tabletwodata",
            "app_tablethreedata",
            "app_tablefourdata",
            "app_tablefivedata",
            "app_comport_settings",
            "app_master_settings",
            "app_parameter_settings",
            "app_measurementdata",
            "app_masterintervalsettings",
            "app_shiftsettings",
            "app_measure_data",
            "app_customerdetails",
            "app_userlogin",
            "app_consolidate_with_srno",
            "app_consolidate_without_srno",
            "app_parameterwise_report",
            "app_jobwise_report",
            "app_resetcount",
            "app_x_bar_chart",
            "app_x_bar_r_chart",
            "app_x_bar_s_chart",
            "app_histogram_chart",
            "app_pie_chart",
            "app_backupsettings",
        ]

        for model in models:
            # Query the table data
            cursor.execute(f'SELECT * FROM "{model}" ORDER BY id ASC;')
            rows = cursor.fetchall()

            # Get column names
            column_names = [desc[0] for desc in cursor.description]

            # Create a new worksheet for each model
            worksheet = workbook.create_sheet(title=model.strip('"'))

            # Write the header
            worksheet.append(column_names)

            # Write the data
            for row in rows:
                # Convert any timezone-aware datetime to naive datetime
                row = [
                    value.replace(tzinfo=None) if isinstance(value, datetime) and value.tzinfo else value
                    for value in row
                ]
                worksheet.append(row)

        # Save the workbook to the backup folder with a timestamp in the filename
        xlsx_file_path = os.path.join(backup_folder, f'database_backup_{timestamp}.xlsx')
        workbook.save(xlsx_file_path)
        print(f"Backup saved to {xlsx_file_path}")

    except Exception as e:
        print(f"An error occurred while backing up the database: {e}")

    finally:
        # Clean up
        cursor.close()
        conn.close()
