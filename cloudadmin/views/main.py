from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test 
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseBadRequest, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect
from django.utils.datastructures import MultiValueDictKeyError

from cloudadmin.settings import parser
from cloudadmin.utils import createContext, requireSuperuser, rolenames
from cloudadmin.openstack import getOpenstackConnection, getOpenstackProject, getAndVerifyAccessToOpenstackProject

@login_required
def index(request):
  """ View for the application root. Redirects to the webpage's frontpage. """

  return redirect('web.overview')

@login_required
def overview(request):
  """ A view displaying the os-projects a user currently is a member of. """

  context = createContext(request)
  return render(request, 'cloudadmin/index.html', context) 

@login_required
def openstack(request):
  """ A view where a user can manage the openstack-projects it have access to.
  """

  context = createContext(request)
  return render(request, 'cloudadmin/openstack.html', context) 

@login_required
def openstackproject(request, projectid):
  """ A view where a user can manage access to an openstack project.
  """
  context = createContext(request)

  connection = getOpenstackConnection()
  context['rolenames'] = rolenames

  try:
    context['project'] = getAndVerifyAccessToOpenstackProject(connection,
        projectid, request.user)
  except LookupError:
    raise Http404

  if(context['project']['write']):
    return render(request, 'cloudadmin/openstackproject.html', context) 
  else:
    raise PermissionDenied('Missing read access')

@user_passes_test(requireSuperuser)
def administrative(request):
  """ A view where superusers can manage cloudadmin projects """

  context = createContext(request)
  context['groups'] = Group.objects.order_by('name').all()
  return render(request, 'cloudadmin/administrative.html', context) 

@login_required
def debug(request):
  """ A debug-view showing information about a logged in user """

  context = createContext(request)
  return render(request, 'cloudadmin/debug.html', context) 

def loginPage(request):
  """ The view creating a login-page, and handling login requests. """
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
        return redirect(reverse('web.index'))
    else:
      context['message'] = "Your credentials are not valid."

  return render(request, 'cloudadmin/login.html', context) 

@login_required
def logoutPage(request):
  """ A view handling a logout-request. """
  logout(request)
  return redirect(reverse('web.login'))
