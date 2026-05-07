from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def slot_template(request):
    return HttpResponse("DeliverySlots")