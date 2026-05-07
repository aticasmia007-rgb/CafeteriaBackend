from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def probando(request):
    return HttpResponse("Auth!")