from django.contrib.auth.models import Group
from django.http import JsonResponse

from cloudadmin.decorators import apiauth_superuser

@apiauth_superuser
def list(request):
  """ API view - Lists all groups

  A simple view listing up all groups cloudadmin knows about. Only superusers
  are allowed to use this endpoint.
  """

  data = {}
  data['groups'] = []

  for g in Group.objects.order_by('name').all():
    data['groups'].append({
      'id':   g.id,
      'name': g.name,
    })

  return JsonResponse(data) 
