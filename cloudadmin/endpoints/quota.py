from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest, \
    HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404

from cloudadmin.decorators import apiauth
from cloudadmin.models import Project, QuotaTemplate

@apiauth
def index(request):
  """ API View - List and create quota-templates.
  
  This method implements the listing and creation of quota-templates. The method
  implements the following functions:
    GET:  Lists all the quota-templates the requesting user hav access to (ie:
          all global ones, and those belonging to projects the user is member
          to). Superusers get all. 
          Returns a JSON blob.
    POST: Creates a new quota-template. Requires the following parameters:
      name:     A string representing the name of the quota-template.
      project:  An integer representing the ID of the project which the template
                should belong to. If it is set to '0' a global template will be
                created (if the user is a superuser).
      cpu_cores:
      ram_gb:
      cinder_gb:
      cinder_volumes:
      switft_gb:
      swift_objects: All 6 parameters are integers representing the quotas
  """

  if(request.method == 'GET'):
    # Create a base-query including all objects:
    query = QuotaTemplate.objects

    # If the requesting user is not a superuser, filter the query to only
    # include projectless templates (ie: the global ones) and thoese templates
    # where the requesting user have access.
    if(not request.user.is_superuser):
      query = query.filter( \
        Q(project = None) | Q(project__groups__user = request.user))

    # Iterate through the templates, and store as regular Dict's.
    templates = []
    for template in query.all():
      t = template.asDict()
      if(template.project):
        t['project_name'] = template.project.name
      else:
        t['project_name'] = 'Global'
      templates.append(t)

    # Return the collected templates as a JSON response
    return JsonResponse({'templates': templates}) 

  # If it is a post-request, a querydict should be created:
  elif(request.method == 'POST'):
    # Create an empty template
    qt = QuotaTemplate()
    # Read quota-information from POST
    qt.fromDict(request.POST)

    # If a name is set, store it.
    if(len(request.POST['name'])):
      qt.name = request.POST['name'] 
    # If a name is not set, return an error
    else:
      return HttpResponseBadRequest('Missing content in the parameter \'name\'')

    # If a project is not selected, and the user is not a superuser (since its
    # only superusers thats allowed to create global templates), return a
    # message requiring a project to be set.
    if(request.POST['project'] == '0' and not request.user.is_superuser):
      return HttpResponseBadRequest('A project must be selected')

    # IF a project is not selected, and the user are a superuser; set the
    # project to be pythons 'None'.
    elif(request.POST['project'] == '0'):
      project = None

    # Otherwise, a project is selected. In that case, try to retrieve it from
    # the database; and return an error if the project is not found.
    else:
      try:
        project = Project.objects.get(pk=int(request.POST['project']))
      except Project.DoesNotExist:
        return HttpResponseBadRequest('A valid project must be selected')

    # If the user is a superuser, or if the user have access to the project,
    # save the new template to the database.
    if(request.user.is_superuser or 
        project.groups.filter(user = request.user).count()):
      qt.project = project
      qt.save()
      return HttpResponse('Template created')
    else:
      return HttpResponseBadRequest(
          'You does not have access to the selected project.')

  # If an unimplemented method is used, return an error message.
  else:
    return HttpResponseBadRequest('Method %s not implemented' % request.method)

@apiauth
def single(request, id):
  """ API view - Retrieve, update or delete a quota template

  The follwing API-point implemnts these methods:
  GET:    Return the quota-template as JSON.
  POST:   Updates a quota-template
  DELETE: Deletes a quota-template.

  """

  # Retrieve the quota-template from the database
  template = get_object_or_404(QuotaTemplate, pk=id)

  # If the template is assigned to a project (ie: it is not global), make sure
  # the user have access to the project. If not, return a 404 (No forbidden, to
  # avoid saying if an ID exists or not)
  if(template.project and 
      not template.project.groups.filter(user = request.user).count() and 
      not request.user.is_superuser):
    raise Http404

  # If it is a get-request, return the template as a dict.
  if(request.method == 'GET'):
    return JsonResponse({'template': template.asDict()}) 

  # If it is a delete-request:
  elif(request.method == 'DELETE'):
    # Return a 403 if a regular user tries to delete a global template 
    if(not request.user.is_superuser and not template.project):
      return HttpResponseForbidden(
          'Only superusers can delete global templates')
  
    # Delete the template
    template.delete()

    # Retrun a message stating that the template is deleted.
    return HttpResponse('Template is deleted')

  # If it is a post-request, a template should be updated.
  elif(request.method == 'POST'):
    # Return a 403 if a regular user tries to update a global template 
    if(not request.user.is_superuser and not template.project):
      return HttpResponseForbidden(
          'Only superusers can update global templates')
  
    # If a project is selected for the template:
    if(int(request.POST['project'])):
      try:
        # Try to retrieve the requested project
        newProject = Project.objects.get(pk=int(request.POST['project']))

        # If the requesting user is not a superuser; Grab the first group in
        # that project where the requesting user is member. This will throw an
        # exception if there are no groups where the requesting user is member.
        if(not request.user.is_superuser):
          newProject.groups.filter(user = u2)[0]
      except:
        return HttpResponseForbidden(
          'You cannot create templates for projects where you dont have access'
        )

    # It a project is not selected:
    else:
      # Superusers can create global templates
      if(request.user.is_superuser):
        newProject = None
      # Other users must select a valid template!
      else:
        return HttpResponseForbidden(
            'You must select a project for the template!')
    
    template.project = newProject
    template.name = request.POST['name']
    template.fromDict(request.POST)
    template.save()

    return HttpResponse('Template is updated')

  # If an unimplemented method is used, return an error message.
  else:
    return HttpResponseBadRequest('Method %s not implemented' % request.method)
