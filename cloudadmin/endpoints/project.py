from django.contrib.auth.models import Group
from django.http import Http404, HttpResponse, HttpResponseBadRequest, \
    HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404

from cloudadmin.decorators import apiauth
from cloudadmin.exceptions import InsufficientQuotaException
from cloudadmin.models import Project, Usage, Quota, QuotaInformation

@apiauth
def index(request):
  """ API View - Display existing or create new cloudadmin project

  The following view implements the functionality needed to create new, or
  list existing cloudadmin projects that a certain user have access to.

  The view implemets the following methods:
  GET:  Returns a list of the cloudadmin-projects a use have access to. The list
        is formatted in JSON.
  POST: 
      name:           A string representing the name of the cloudadmin project.
      description:    A string describing the cloudadmin project. 
      projectprefix:  A string which will be prepended to all openstack project
                      created within this cloudadmin project.
      projectGroups:  A list of integers representing the ID's of the groups
                      which should be allowed to administer the cloudadmin
                      project. 
      cpu_cores:
      ram_gb:
      cinder_gb:
      cinder_volumes:
      switft_gb:
      swift_objects: All 6 parameters are integers representing the requested
                     quotas for the new cloudadmin project.

  """

  # If it is a GET request:
  if(request.method == 'GET'):
    # Start a query for all projects, ordered by paren_ID and name
    query = Project.objects.order_by('parent_id', 'name')

    # If the requesting user is not a superuser, only include the projects the
    # user have access to
    if(not request.user.is_superuser):
      query = query.filter(groups__in = request.user.groups.all())

    # Create a dictionary containing a list where all the projects can be added.
    data = {'projects': []}
    for project in query.all():
      data['projects'].append(project.asDict())

    # Return the list to the users.
    return JsonResponse(data) 

  # If it is a post-request, a new cloudadmin-project should be created.
  elif(request.method == 'POST'):
    # If the requesting user is not a superuser, return a permission denied.
    if(not request.user.is_superuser):
      return HttpResponseForbidden('You cannot create cloudadmin projects')

    # Load the quota-information from POST
    inputQuota = QuotaInformation()
    inputQuota.fromDict(request.POST)

    # Create and save empty usage and quota objects
    usage = Usage()
    usage.save()
    quota = Quota()
    quota.save()

    # Create a new project, and assign the fresh quota and usage projects to it.
    project = Project() 
    project.usage = usage
    project.quota = quota

    # Try to retrieve the supplied parent project. Of this fails, there should
    # not be a parent.
    try:
      parent = get_object_or_404(Project, name=request.POST['parent'])
    except:
      parent = None

    # Add the supplied name, description and projectprefix to the cloudadmin
    # project.
    project.name = request.POST['name']
    project.description = request.POST['description']
    project.projectprefix = request.POST['projectprefix']

    # Save the new quotas, and if applicable update the parent's usage with the
    # new quotas. This can create two exception-types:
    #   ValueError:                 Impossible quotas; for instance with negative 
    #                               values
    #   InsufficientQuotaException: If the new quota exceeds the parent 
    #                               project's quota.
    try:
      project.updateQuotaParent(inputQuota, parent)
    except (ValueError, InsufficientQuotaException) as e:
      return HttpResponseBadRequest(e.args[0])

    # Save the new project.
    project.save()

    # Add the supplied groups to the projects list of administrators.
    for group in Group.objects.\
        filter(id__in=request.POST.getlist('projectGroups')).all():
      project.groups.add(group)

    return HttpResponse('Project is created')

  # If an unimplemented method is used, return an error message.
  else:
    return HttpResponseBadRequest('Method %s not implemented' % request.method)

@apiauth
def single(request, id):
  """ API View - Display, update or delete a single cloudadmin project.  

  The following view implements the functionality needed to show, update or
  delete a cloudadmin project. 

  The view implemets the following methods:
  GET:  Returns the complete details about a certain cloudadmin project. 
  POST: 
      name:           A string representing the name of the cloudadmin project.
      description:    A string describing the cloudadmin project. 
      projectprefix:  A string which will be prepended to all openstack project
                      created within this cloudadmin project.
      projectGroups:  A list of integers representing the ID's of the groups
                      which should be allowed to administer the cloudadmin
                      project. 
      cpu_cores:
      ram_gb:
      cinder_gb:
      cinder_volumes:
      switft_gb:
      swift_objects: All 6 parameters are integers representing the requested
                     quotas for the new cloudadmin project.
  DELETE: Deletes the project.
  """

  # Try to retrieve the cloudadmin project
  project = get_object_or_404(Project, pk=id)

  # A GET request means "display information about project"
  if(request.method == 'GET'):
    # If the user have access to the cloudadmin-project, or if the user is a
    # superuser, return the project as JSON. 
    if(project.groups.filter(user=request.user).count() or
        request.user.is_superuser):
      return JsonResponse(project.asDict(), safe=False) 
    # If the user dont have access, return a 404.
    else:
      raise Http404

  # A POST request means "Update the project".
  elif(request.method == 'POST'):
    if(not request.user.is_superuser):
      return HttpResponseForbidden(
          'Only superusers can update cloudadmin projects')

    # Read the quotas in the request.
    inputQuota = QuotaInformation()
    inputQuota.fromDict(request.POST)

    # If a parent-id is provided, try to retrieve the parent.
    try:
      parent = get_object_or_404(Project, name=request.POST['parent'])
    except:
      parent = None

    # Add the new name, description and prefix
    project.name = request.POST['name']
    project.description = request.POST['description']
    project.projectprefix = request.POST['projectprefix']

    # Update the quotas in both the current project, and the parent project (if
    # applicable).
    try:
      project.updateQuotaParent(inputQuota, parent)
    except (ValueError, InsufficientQuotaException) as e:
      return HttpResponseBadRequest(e.args[0]) 

    # Save the project
    project.save()
    
    # Add groups in the request to the project.
    for group in Group.objects.\
        filter(id__in=request.POST.getlist('projectGroups')).all():
      project.groups.add(group)

    # Remove groups not listed in the request.
    for group in Group.objects.\
        exclude(id__in=request.POST.getlist('projectGroups')).all():
      project.groups.remove(group)

    # Return a status OK and a message to the user.
    return HttpResponse('Project is updated') 

  # A delete-request should let superusers delete the cloudadmin project. 
  elif(request.method == 'DELETE'):
    if(not request.user.is_superuser):
      return HttpResponseForbidden(
          'Only superusers can delete cloudadmin projects')

    project.delete()
    return HttpResponse('The object is deleted')

  # If an unimplemented method is used, return an error message.
  else:
    return HttpResponseBadRequest('Method %s not implemented' % request.method)
