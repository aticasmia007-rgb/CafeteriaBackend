from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def initiate_payment(request):
    return HttpResponse("Payments!")