from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from cloudadmin.utils import createContext
from cloudadmin.openstack import getOpenstackConnection, \
    getAndVerifyAccessToOpenstackProject

@login_required
def openstackprojectinfo(request, projectid):
  """ A view displaying the information of an openstack project.

  This is a partial page, intended to be ajax-loaded.
  """

  context = createContext(request)
  connection = getOpenstackConnection()

  try:
    context['project'] = getAndVerifyAccessToOpenstackProject(connection,
        projectid, request.user)
  except LookupError:
    raise Http404

  return render(request, 'cloudadmin/parts/openstackprojectinfo.html', context) 
