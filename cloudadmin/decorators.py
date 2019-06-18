from functools import wraps

from django.http import HttpResponseForbidden

def apiauth(view_function):
  """ A decorator similar to @login_required, but it does not redirect users

  This decorator simply makes sure that the requesting user is authenticated. If
  it is not, the decorator will return a HttpResponseForbidden.
  """

  @wraps(view_function)
  def decorator(request, *args, **kwargs):
    if(request.user.is_authenticated()):
      return view_function(request, *args, **kwargs)
    else:
      return HttpResponseForbidden('Authentication required')
  return decorator

def apiauth_superuser(view_function):
  """ A decorator ensuring that the requesting user is a superuser. 

  This decorator simply makes sure that the requesting user is authenticated,
  and that he is a superuser. If it is not, the decorator will return a
  HttpResponseForbidden.
  """

  @wraps(view_function)
  def decorator(request, *args, **kwargs):
    if(request.user.is_authenticated() and request.user.is_superuser):
      return view_function(request, *args, **kwargs)
    else:
      return HttpResponseForbidden('Authentication required')
  return decorator
