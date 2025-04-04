import json
import socket
import uuid
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from app.models import CustomerDetails, MasterIntervalSettings,ParameterFactor, ShiftSettings, BackupSettings, TableOneData, parameter_settings
from datetime import datetime
from dateutil.relativedelta import relativedelta  # To handle month addition smoothly
from django.db.models import Q


def get_ip_address():
    try:
        # Get the local IP address
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except Exception as e:
        return f"Error retrieving IP address: {e}"

def get_mac_address():
    try:
        # Get the MAC address
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                        for elements in range(0, 2*6, 2)][::-1])
        return mac
    except Exception as e:
        return f"Error retrieving MAC address: {e}"

@csrf_exempt
def utility(request):
    try:
        ip_address = get_ip_address()
        mac_address = get_mac_address()
        print(f"IP Address: {ip_address}")
        print(f"MAC Address: {mac_address}")

        if request.method == 'POST':
            data = json.loads(request.body)
            form_id = data.get('id')
            part_model = data.get('part_model')
            print("this is the part model for you",part_model)

            if form_id == 'backup_date':
                # Get the backup date from the request data
                backup_date = data.get('backup_data')
                confirm_backup = data.get('confirm_backup')  # Retrieve checkbox value

                
                print("Backup Date Settings:")
                print("id_value:", form_id)
                print("backup_date:", backup_date)  # Print the received backup date
                print("Confirm Backup Checkbox:", confirm_backup)  # Print checkbox value


                BackupSettings.objects.create(
                    backup_date=backup_date,
                    confirm_backup=confirm_backup  # Save the checkbox state
                )

                return JsonResponse({'status': 'success'})

            elif form_id == 'master_interval':
                timewise = data.get('timewise')
                componentwise = data.get('componentwise')
                hour = data.get('hour')
                minute = data.get('minute')
                component_no = data.get('component_no')

                print("Master Interval Settings:")
                print("id_value:", form_id)
                print("timewise:", timewise)
                print("componentwise:", componentwise)
                print("hour:", hour)
                print("minute:", minute)
                print("component_no:", component_no)
                hour = int(hour) if hour else None
                minute = int(minute) if minute else None
                component_no = int(component_no) if component_no else None

                interval_settings, created = MasterIntervalSettings.objects.get_or_create(id=1)
                interval_settings.timewise = timewise
                interval_settings.componentwise = componentwise
                interval_settings.hour = hour
                interval_settings.minute = minute
                interval_settings.component_no = component_no
                interval_settings.save()

                print("Master Interval Settings saved:", interval_settings)

            elif form_id == 'shift_settings':
                shift = data.get('shift')
                shift_time = data.get('shift_time')

                print("Shift Settings:")
                print("id_value:", form_id)
                print("shift:", shift)
                print("shift_time:", shift_time)

                existing_shift = ShiftSettings.objects.filter(shift=shift).first()

                if existing_shift:
                    existing_shift.shift_time = shift_time
                    existing_shift.save()
                else:
                    shift_settings_obj = ShiftSettings.objects.create(shift=shift, shift_time=shift_time)
                    shift_settings_obj.save()
                    
            elif form_id == 'customer_details':
                customer_name = data.get('customer_name')
                primary_contact_person = data.get('primary_contact_person')
                secondary_contact_person = data.get('secondary_contact_person')
                primary_email = data.get('primary_email')
                secondary_email = data.get('secondary_email')
                primary_phone_no = data.get('primary_phone_no')
                secondary_phone_no = data.get('secondary_phone_no')

                primary_dept = data.get('primary_dept')
                secondary_dept = data.get('secondary_dept')
                mac_address = data.get('mac_address')
                ip_address = data.get('ip_address')
                address = data.get('address')

                print("customer_details:", customer_name, primary_contact_person, secondary_contact_person,
                      primary_email, secondary_email, primary_phone_no, secondary_phone_no, primary_dept,secondary_dept, mac_address, ip_address, address)

                try:
                    customer_details = CustomerDetails.objects.get(id=1)
                except CustomerDetails.DoesNotExist:
                    customer_details = CustomerDetails(id=1)

                customer_details.customer_name = customer_name
                customer_details.primary_contact_person = primary_contact_person
                customer_details.secondary_contact_person = secondary_contact_person
                customer_details.primary_email = primary_email
                customer_details.secondary_email = secondary_email
                customer_details.primary_phone_no = primary_phone_no
                customer_details.secondary_phone_no = secondary_phone_no
                customer_details.primary_dept = primary_dept
                customer_details.secondary_dept = secondary_dept
                customer_details.mac_address = mac_address
                customer_details.ip_address = ip_address
                customer_details.address = address
                customer_details.save()

            elif form_id == 'parameter_factor':
                part_model = data.get('part_model')
                parameter_name = data.get('parameter_name')
                method = data.get('method')
                value = data.get('value')

                 # Check if a ParameterFactor record already exists with the same part_model and parameter_name
                probe_factor, created = ParameterFactor.objects.update_or_create(
                    part_model=part_model,
                    parameter_name=parameter_name,
                    defaults={'method': method, 'value': value}  # Update method and value if exists
                )


               
       
             # Fetch parameter data and exclude specific conditions
            parameter_names = parameter_settings.objects.filter(
                model_id=part_model
            ).exclude( Q(attribute=True)
            ).values_list('parameter_name', flat=True).order_by('id')
            print("parameter_data",parameter_names)



            response_data = {
                'status': 'success',
                'parameter_names': list(parameter_names)
                
            }

            return JsonResponse(response_data)

        elif request.method == 'GET':
            try:
                master_interval_settings = MasterIntervalSettings.objects.all()
                shift_settings = ShiftSettings.objects.all().order_by('id')
                customer_details = CustomerDetails.objects.all()
                backup_date = BackupSettings.objects.order_by('-id').first()
                print('your values are:',backup_date)
                part_model_values = TableOneData.objects.order_by('id').values_list('part_model', flat=True).distinct()
                print('your data is this part_model_values:',part_model_values)


                context = {
                    'master_interval_settings': master_interval_settings,
                    'backup_date': backup_date,
                    'shift_settings': shift_settings,
                    'customer_details': customer_details,
                    'ip_address': ip_address,  # Pass IP address to context
                    'mac_address': mac_address,  # Pass MAC address to contex
                    'part_model_values': part_model_values
                }

                return render(request, 'app/utility.html', context)

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)

    except json.JSONDecodeError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return render(request, 'app/utility.html')
