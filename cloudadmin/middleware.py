from django.http import HttpResponseForbidden
from django.middleware.csrf import CsrfViewMiddleware
from django.contrib.auth.models import User

from cloudadmin.models import Token

class CloudadminCsrfViewMiddleware(CsrfViewMiddleware):
  """ Custom CSRF middleware modified to be used in front of an API

  This class is simply an extension of django's CsrfViewMiddleware. The purpose
  of the extension is to allow having certain API endpoints being available
  through normal web-access, while others could be available for scripts and
  similar. It differs from the original middleware-class in that it looks for
  a variable named 'api_key' delivered as a POST parameter. There are three
  paths through the middleware:
    1. If the api_key is not present, it simply calles the original CSRF-check
    2. If the api_key is present, but invalid (ie: non-existant or expired) a
       HttpResponseForbidden will be returned.
    3. If the api_key is present and vaild, the requested view will be executed.
  """

  def process_view(self, request, view, view_args, view_kwargs):
    request.token = None
    if request.POST.get('api_key'):
      try:
        request.token = Token.objects.get(value=request.POST['api_key'])
      except:
        return HttpResponseForbidden('Invalid API key')

      if(request.token.isValid()):
        request.user = request.token.user 
        return view(request, *view_args, **view_kwargs)
      else:
        return HttpResponseForbidden('Invalid API key')
    else:
      return super().process_view(request, view, view_args, view_kwargs)
