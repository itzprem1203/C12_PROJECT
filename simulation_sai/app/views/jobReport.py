from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import render
import pandas as pd
from weasyprint import CSS, HTML
from django.template.loader import get_template
import os
from app.models import MeasurementData, jobwise_report,CustomerDetails,parameter_settings

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from django.http import JsonResponse
import re
from io import BytesIO

# Function to remove HTML tags
def strip_html_tags(text):
    # Check if text is a string, then remove HTML tags
    if isinstance(text, str):
        return re.sub(r'<.*?>', '', text)
    return text

# Function to replace <br> with \n for multi-line headers
def replace_br_with_newline(text):
    if isinstance(text, str):
        return text.replace('<br>', '\n')
    return text

def jobReport(request):
    if request.method == 'GET':
        jobwise_values = jobwise_report.objects.all()
        part_model = jobwise_report.objects.values_list('part_model', flat=True).distinct().get()
        print("part_model:", part_model)

        # Handling the case when no email exists
        email_1 = CustomerDetails.objects.values_list('primary_email', flat=True).first() or 'No primary email'
        print('your primary mail id from server to front end now:', email_1)

        email_2 = CustomerDetails.objects.values_list('secondary_email', flat=True).first() or 'No secondary email'
        print('your secondary mail id from server to front end now:', email_2)

        job_no = jobwise_report.objects.values_list('job_no', flat=True).get()
        print("job_no:", job_no)

        hidden_parameters = parameter_settings.objects.filter(hide_checkbox=True, model_id=part_model).values_list('parameter_name', flat=True)
        # Filter MeasurementData objects based on part_model and job_no
        job_number_value = MeasurementData.objects.filter(part_model=part_model, comp_sr_no=job_no).exclude(parameter_name__in=hidden_parameters).order_by('id')

        if not job_number_value:
            # Handle case where no comp_sr_no values are found
            context = {
                'no_results': True  # Flag to indicate no results found
            }
            return render(request, 'app/reports/jobReport.html', context)
        # Initialize lists to store operator and shift values
        operators = []
        shifts = []
        part_status = []

        data_dict = {
            'Date':[],
            'Parameter Name': [],
            'Limits':[],
            'Readings': [],
            
        }

        # Iterate through queryset and append parameter_name, readings, and status_cell to data_dict
        for measurement_data in job_number_value:
            print(measurement_data.__dict__)
            print("parameter_name:", measurement_data.parameter_name)
            print("readings:", measurement_data.readings)
            print("status_cell:", measurement_data.status_cell)
            operators.append(measurement_data.operator)
            shifts.append(measurement_data.shift)
            part_status.append(measurement_data.part_status)

            print(operators,shifts,part_status)

           # If you want unique values, you can convert them to sets
            unique_operators = set(operators)
            unique_shifts = set(shifts)
            unique_part_status = set(part_status)

            # Convert sets to lists and join elements into a single string
            operators_values = ' '.join(list(unique_operators))
            shifts_values = ' '.join(list(unique_shifts))
            part_status_values = ' '.join(list(unique_part_status))

            # Print the values as space-separated strings
            print(operators_values, shifts_values, part_status_values)
            print("date",measurement_data.date)

            formatted_date = measurement_data.date.strftime("%d-%m-%Y %I:%M:%S %p")
            parameter_values = f"{measurement_data.usl} / {measurement_data.lsl}"
            

            data_dict['Date'].append(formatted_date)
            data_dict['Parameter Name'].append(measurement_data.parameter_name)
            data_dict['Limits'].append(parameter_values)
            if measurement_data.readings is None or measurement_data.readings == '':
                # If `readings` is None or empty, display the `status_cell` value instead
                if measurement_data.status_cell == 'ACCEPT':
                    readings_html = f'<span style="background-color: #00ff00; padding: 2px;">ACCEPT</span>'
                elif measurement_data.status_cell == 'REWORK':
                    readings_html = f'<span style="background-color: yellow; padding: 2px;">REWORK</span>'
                elif measurement_data.status_cell == 'REJECT':
                    readings_html = f'<span style="background-color: red; padding: 2px;">REJECT</span>'
                else:
                    readings_html = '<span style="padding: 2px;">N/A</span>'
            else:
                # If `readings` is not None, use the actual readings
                if measurement_data.status_cell == 'ACCEPT':
                    readings_html = f'<span style="background-color: #00ff00; padding: 2px;">{measurement_data.readings}</span>'
                elif measurement_data.status_cell == 'REWORK':
                    readings_html = f'<span style="background-color: yellow; padding: 2px;">{measurement_data.readings}</span>'
                elif measurement_data.status_cell == 'REJECT':
                    readings_html = f'<span style="background-color: red; padding: 2px;">{measurement_data.readings}</span>'
                else:
                    readings_html = f'<span style="padding: 2px;">{measurement_data.readings}</span>'

            data_dict['Readings'].append(readings_html)

            

        df = pd.DataFrame(data_dict)
        df.index = df.index + 1  # Shift index by 1 to start from 1

        table_html = df.to_html(index=True, escape=False, classes='table table-striped')

        context = {
            'table_html': table_html,
            'jobwise_values':jobwise_values,
            'operators_values':operators_values,
            'shifts_values':shifts_values,
            'part_status_values':part_status_values,
            'email_1': email_1,
            'email_2': email_2
        }

        request.session['data_dict'] = data_dict  # Save data_dict to the session for POST request
        request.session['operators_values'] = operators_values
        request.session['shifts_values'] = shifts_values
        request.session['part_status_values'] = part_status_values

        return render(request, 'app/reports/jobReport.html', context)
    
    elif request.method == 'POST':
        export_type = request.POST.get('export_type')
        recipient_email = request.POST.get('recipient_email')
        data_dict = request.session.get('data_dict')
        operators_values = request.session.get('operators_values')
        shifts_values = request.session.get('shifts_values')
        part_status_values = request.session.get('part_status_values')

        if data_dict is None or operators_values is None or shifts_values is None or part_status_values is None:
            return HttpResponse("No data available for export", status=400)

        df = pd.DataFrame(data_dict)
        df.index = df.index + 1

        if export_type == 'pdf' or export_type == 'send_mail':
            template = get_template('app/reports/jobReport.html')
            context = {
                'table_html': df.to_html(index=True, escape=False, classes='table table-striped table_data'),
                'jobwise_values': jobwise_report.objects.all(),
                'operators_values': operators_values,
                'shifts_values': shifts_values,
                'part_status_values': part_status_values,
            }
            html_string = template.render(context)

            # CSS for scaling down the content to fit a single PDF page
            css = CSS(string='''
                @page {
                    size: A4; /* Landscape mode to fit more content horizontally */
                    margin: 0.5cm; /* Adjust margin as needed */
                }
                body {
                    margin: 0; /* Give body some margin to prevent overflow */
                    transform: scale(0.8); /* Scale down the entire content */
                    transform-origin: 0 0; /* Ensure the scaling starts from the top-left corner */
                }
                
                table {
                    table-layout: fixed; /* Fix the table layout */
                    font-size: 20px; /* Increase font size */
                    border-collapse: collapse; /* Collapse table borders */
                }
                table, th, td {
                    border: 1px solid black; /* Add border to table */
                }
                th, td {
                    word-wrap: break-word; /* Break long words */
                }
                .no-pdf {
                    display: none;
                }
            ''')

            pdf = HTML(string=html_string).write_pdf(stylesheets=[css])

            # Get the Downloads folder path
            target_folder = r"C:\Program Files\Gauge_Logic\pdf_files"

            # Ensure the target folder exists
            os.makedirs(target_folder, exist_ok=True)
            pdf_filename = f"jobReport_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
            pdf_file_path = os.path.join(target_folder, pdf_filename)

            # Save the PDF file in the Downloads folder
            with open(pdf_file_path, 'wb') as pdf_file:
                pdf_file.write(pdf)


            if export_type == 'pdf':
                response = HttpResponse(pdf, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                  # Pass success message to the context to show on the front end
                success_message = "PDF generated successfully!"
                context['success_message'] = success_message
                return render(request, 'app/reports/jobReport.html', context)

            elif export_type == 'send_mail':
                pdf_filename = f"jobReport_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
                # Send the PDF as an email attachment
                send_mail_with_pdf(pdf, recipient_email, pdf_filename)
                success_message = "PDF generated and email sent successfully!"
                return render(request, 'app/reports/jobReport.html', {'success_message': success_message, **context})
            
        elif request.method == 'POST' and export_type == 'excel':

            template = get_template('app/reports/jobReport.html')
            context = {
                'table_html': df.to_html(index=True, escape=False, classes='table table-striped table_data'),
                'jobwise_values': jobwise_report.objects.all(),
                'operators_values': operators_values,
                'shifts_values': shifts_values,
                'part_status_values': part_status_values,
            }
            # Remove HTML tags from the DataFrame before exporting
            df = df.applymap(strip_html_tags)

            # Replace <br> with newline in column headers to make them multi-line in Excel
            df.columns = [replace_br_with_newline(col) for col in df.columns]

            # Create a new DataFrame for parameterwise_values
            jobwise_values = jobwise_report.objects.all()
            jobwise_data = []

            for data in jobwise_values:
                jobwise_data.append({
                    'PARTMODEL': data.part_model,
                    'JOB NO': data.job_no,
                    'CURRENT DATE': data.current_date_time,
                    'OPERATORS_VALUES': operators_values,
                    'SHIFTS_VALUES': shifts_values,
                    'PART_STATUS_VALUES': part_status_values,
                })

            jobwise_df = pd.DataFrame(jobwise_data)

            # Create an Excel writer object using BytesIO as a file-like object
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                # Write parameterwise_df to the Excel sheet first
                jobwise_df.to_excel(writer, sheet_name='jobReport', index=False, startrow=0)

                # Write the original DataFrame to the same sheet below the parameterwise data
                df.to_excel(writer, sheet_name='jobReport', index=True, startrow=len(jobwise_df) + 2)

                # Get access to the workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['jobReport']

                # Format for multi-line header
                header_format = workbook.add_format({
                    'text_wrap': True,  # Enable text wrap
                    'valign': 'top',    # Align to top
                    'align': 'center',  # Center align the text
                    'bold': True        # Make the headers bold
                })

                # Apply formatting to the headers of the parameterwise data
                for col_num, value in enumerate(jobwise_df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

                # Apply formatting to the headers of the main DataFrame (startrow=len(parameterwise_df)+2)
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(len(jobwise_df) + 2, col_num + 1, value, header_format)

            # Get the Downloads folder path
            target_folder = r"C:\Program Files\Gauge_Logic\xlsx_files"

            # Ensure the target folder exists
            os.makedirs(target_folder, exist_ok=True)
            excel_filename = f"jobReport_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
            excel_file_path = os.path.join(target_folder, excel_filename)

            # Save the Excel file in the Downloads folder
            with open(excel_file_path, 'wb') as excel_file:
                excel_file.write(excel_buffer.getvalue())

            # Return the Excel file for download
            response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{excel_filename}"'
            
            success_message = "Excel file generated successfully!"
            
            # Render success message in the frontend
            return render(request, 'app/reports/jobReport.html', {'success_message': success_message ,**context})

        return HttpResponse("Unsupported request method", status=405)    


def send_mail_with_pdf(pdf_content, recipient_email, pdf_filename):
    sender_email = "gaugelogic.report@gmail.com"
    sender_password = "tdkd cfkj ahsa qril"
    subject = "JobReport PDF"
    body = "Please find the attached PDF report."

    # Setup email parameters
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Attach the email body
    msg.attach(MIMEText(body, 'plain'))

    # Attach the PDF file
    attachment = MIMEBase('application', 'octet-stream')
    attachment.set_payload(pdf_content)
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', f'attachment; filename="{pdf_filename}"')
    msg.attach(attachment)

    # Send the email using SMTP
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")


