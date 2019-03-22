from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test 
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import render, redirect
from django.utils.datastructures import MultiValueDictKeyError

from cloudadmin.settings import parser
from cloudadmin.utils import createContext, requireSuperuser

@login_required
def index(request):
  context = createContext(request)
  return render(request, 'cloudadmin/index.html', context) 

@login_required
def debug(request):
  context = createContext(request)
  return render(request, 'cloudadmin/debug.html', context) 

def loginPage(request):
  context = {}

  context['horizonurl'] = parser.get('openstack', 'horizon') 

  try:
    context['next'] = request.GET['next']
  except MultiValueDictKeyError:
    context['next'] = None

  if('username' in request.POST):
    user = authenticate(
        username=request.POST['username'],
        password=request.POST['password'],
    )

    if(user):
      login(request, user)
      if(context['next']):
        return redirect(context['next'])
      else:
        return redirect(reverse('index'))
    else:
      context['message'] = "Your credentials are not valid."

  return render(request, 'cloudadmin/login.html', context) 

#@user_passes_test(requireSuperuser)
@login_required
def logoutPage(request):
  logout(request)
  return redirect(reverse('login'))
