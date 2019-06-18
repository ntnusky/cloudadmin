from functools import wraps

from django.contrib.auth import authenticate
from django.http import JsonResponse, HttpResponseForbidden,\
    HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from cloudadmin.decorators import apiauth
from cloudadmin.models import Token

@csrf_exempt
def auth(request):
  """ API view - authenticates a user

  This view authenticates a certain user. It is csrf_exempt, and does not
  require auth, so that anyone can send a request to it.

  It expects two POST parameters:
    username: A string representing the username of the user
    password: A string representing the users password

  If the username and password are valid a token will be generated, and a JSON
  structure will be returned with three elements:
    token: A string which needs to be provided through POST with the key
           "api_key" to use other API endpoints.
    expiry: A UTC time telling when the token expires
    valid: A boolean telling if the token is valid or not.

  The view returns a BadRequest if a valid username and password combination is
  not supplied.
  """

  if('username' in request.POST and 'password' in request.POST):
    user = authenticate(
      username=request.POST['username'],
      password=request.POST['password'],
    )
    if(user):
      token = Token(user = user)
      token.generateToken()
      token.save()
      data = {}
      data['token'] = token.value
      data['expiry'] = token.expiry
      data['valid'] = token.isValid()
      return JsonResponse(data) 
  
  return HttpResponseBadRequest('Username and password must be supplied')

@apiauth
def deauth(request):
  """ API view - destroys an API-token.

  If this view is called using an API-token, this token will be deleted and will
  thus not be accepted anymore.
  """

  if(request.token):
    request.token.delete()
    return JsonResponse({'message': 'Your token is revoked'}) 
  else:
    return HttpResponseBadRequest('It does not make sense to revoke a token ' +
        'if no token are supplied to the request')
