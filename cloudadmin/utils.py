import ipaddress
import re

from django.core.urlresolvers import reverse

from cloudadmin.settings import parser

def populateMenu(request):
  menu = []
  
  #m = {}
  #m['name'] = 'Hosts' 
  #m['url'] = reverse('hostIndex')
  #m['active'] = request.path.startswith(m['url'])
  #menu.append(m)

  m = {}
  m['name'] = 'Overview' 
  m['url'] = reverse('index')
  menu.append(m)

  m = {}
  m['name'] = 'Select project' 
  m['url'] = '#'
  m['subentries'] = [
    ('IMT3003', '#'),
    ('UB',      '#'),
  ]
  menu.append(m)

  m = {}
  m['name'] = 'Log out' 
  m['url'] = reverse('logout') 
  menu.append(m)

  return menu

def createContext(request):
  context = {}
  context['menu'] = populateMenu(request)

  return context

def requireSuperuser(user):
    return user.is_superuser
