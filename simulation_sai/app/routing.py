from django.urls import re_path
from app.consumers import SerialConsumer,PLCConsumer



websocket_urlpatterns = [
    re_path(r'ws/comport/$', SerialConsumer.as_asgi()),
    re_path(r'ws/index/$', SerialConsumer.as_asgi()),
    re_path(r'ws/measurement/$',PLCConsumer.as_asgi())
    
]
