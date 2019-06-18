import ipaddress
import re

from django.core.urlresolvers import reverse

from cloudadmin.settings import parser

rolenames = {
  '_member_':         'Project member',
  'heat_stack_owner': 'Heat access',
  'cloudadmin':       'Project admin',
}

def humanReadable(number, factor = '', divisor = 1024, limit = 1024):
  """ Method which converts a large int to a human-readable string.

  10480 = 10K, for instance.

  The method needs 4 arguments:
    number:  The int to convert
    factor:  K|M|G|T|P if the number is given in Kilo, Mega, Giga, Terra or Peta.
    divisor: Number of K in an M for instance. Default 1024, also common with
             1000.
    limit:   Numbers smaller than the limit will not be converted.
  """

  factors = ['', 'K', 'M', 'G', 'T', 'P']

  try:
    start = factors.index(factor.upper())
  except:
    raise ValueError('factor needs to be one of %s' % str(factors))

  while number > limit:
    number = number / divisor
    start += 1

  if(number == int(number)):
    return "%d%s" % (number, factors[start])
  else:
    return "%.2f%s" % (number, factors[start])

def machineReadable(number, divisor = 1024):
  """ Method which converts a human-readable number to an int

  It takes an argument on the format "10K" and returns an int (ex: 10485760).
  The method allows numbers with two decimal-places as input (ie: 10.04G).

  Returns:
    An integer

  Raises:
    ValueError: If the number is given in a wrong format.
  """

  units = ['', 'K', 'M', 'G', 'T', 'P']

  # Check if the number is in the correct format
  match = re.match(r'^([0-9]+)(\.([0-9]{2}))?\s?([kmgtpKMGTP]?)[bB]?$', number)
  if match:
    value, unused, decimals, unit = match.groups()
    unit = unit.upper()

    # Determine a factor which one have to multiply the value with to get the
    # correct result.
    factor = divisor**units.index(unit)

    if(decimals):
      return factor * (int(value) + int(decimals) / 100)
    else:
      return factor * int(value)

  # Raise a ValueError if the number is in the wrong format
  else:
    raise ValueError('The supplied number "%s" is invalid' % str(number))
  

def populateMenu(request):
  """ Creates a dict suitable to populate the menu """

  menu = []
  
  m = {}
  m['name'] = 'Overview' 
  m['url'] = reverse('web.overview')
  menu.append(m)

  if(request.user.is_superuser):
    m = {}
    m['name'] = 'Administrative' 
    m['url'] = reverse('web.administrative')
    menu.append(m)

  m = {}
  m['name'] = 'Openstack projects' 
  m['url'] = reverse('web.openstack')
  menu.append(m)

  #m = {}
  #m['name'] = 'Select project' 
  #m['url'] = '#'
  #m['subentries'] = [
  #  ('IMT3003', '#'),
  #  ('UB',      '#'),
  #]
  #menu.append(m)

  m = {}
  m['name'] = 'Log out' 
  m['url'] = reverse('web.logout') 
  menu.append(m)

  return menu

def createContext(request):
  """ Creates common elements for the web-pages """

  context = {}
  context['menu'] = populateMenu(request)

  return context

def requireSuperuser(user):
    return user.is_superuser
