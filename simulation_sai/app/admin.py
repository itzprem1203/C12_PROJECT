
from django.contrib import admin
from.models import comport_settings,Master_settings,parameter_settings,MeasurementData,MasterIntervalSettings
from.models import probe_calibrations,TableOneData,TableTwoData,TableThreeData,TableFourData,TableFiveData,ShiftSettings,measure_data,UserLogin
# Register your models here.

admin.site.register(probe_calibrations)
admin.site.register(TableOneData)
admin.site.register(TableTwoData)
admin.site.register(TableThreeData)
admin.site.register(TableFourData)
admin.site.register(TableFiveData)
admin.site.register(comport_settings)
admin.site.register(Master_settings)
admin.site.register(parameter_settings)
admin.site.register(MeasurementData)
admin.site.register(MasterIntervalSettings)
admin.site.register(ShiftSettings)
admin.site.register(measure_data)
admin.site.register(UserLogin)