import datetime
import re

from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponse, HttpResponseBadRequest, \
    HttpResponseForbidden, JsonResponse, QueryDict
from django.utils.datastructures import MultiValueDictKeyError

from cloudadmin.decorators import apiauth
from cloudadmin.exceptions import UsageTooHighException
from cloudadmin.models import Project, QuotaInformation
from cloudadmin.openstack import createOpenstackProject, \
  getAndVerifyAccessToOpenstackProject, getOpenstackConnection, \
  getOpenstackGroup, getOpenstackUser, updateOpenstackProject, validateFormData
from cloudadmin.settings import parser
from cloudadmin.utils import rolenames

@apiauth
def index(request):
  """ API View - Lists or creates openstack projects.

  This view can be called using the following methods:
    POST: Creates an openstack project
    GET:  Lists all the openstack projects the user have access to.

  Creating an openstack project:
    To create an openstack project a POST request should be sent, with the
    following parameters:
      parentid:      An integer representing the ID of the cloudadmin project
                     which the new openstack project should be associated to.
      name:          A string representing the name of the new project.
      description:   A string describing the new openstack project.
      expiry:        A string of the format "YYYY-MM-DD" representing the
                     expiry-date of the new openstack project. 
      volumetypeid:  An integer representing how fast cinder-volumes the project
                     is allowed to create. 0=Slow, 1=Normal, 2=Fast, 3=VeryFast,
                     4=Unlimited. The project can create volume of a certain
                     speed or slower. A '3' would thus indicate Slow, Normal,
                     Fast or Veryfast.
      cpu_cores:
      ram_gb:
      cinder_gb:
      cinder_volumes:
      switft_gb:
      swift_objects: All 6 parameters are integers representing the requested
                     quotas for the new openstack project.
    If all the parameters are assigned, the view will retrieve the
    cloudadmin-project, make sure that the user have admin-rights in it, create
    the openstack-project, update the cloudadmin project usage, and return to
    the caller.
    Returns: A readable message and a status-code:
      200: All OK
      401: If any of the parameters represents objects the user dont have access
           to.
      400: If anything else in the requested parameters are impossible to
           fullfill.

  Listing openstack projects:
    If a GET request is perfomed the openstack projects the user have access to
    will be collected, and returned as a large JSON blob. The JSON blob will at
    the top level contain three lists:
      - projects:   The openstack-projects you have access to manage
      - unmanaged:  If you are a superuser, this list will contain the openstack
                    projects currently not managed by cloudadmin. 
      - readaccess: The openstack-projects you have access to use, but not
                    manage.
  """

  # If it is a 'POST' request, we should create a new openstack project.
  if(request.method == 'POST'):
    # Validate form-data
    try:
      validated = validateFormData(request.POST)
    except ValueError as e:
      return HttpResponseBadRequest(str(e))
    except MultiValueDictKeyError:
      return HttpResponseBadRequest('Not enough parameters supplied')

    # Determine that the user making the request actually have access to the
    # cloud-admin project he would like to create an openstack project for.
    if(not validated['caproject'] or (not validated['caproject'].groups. \
        filter(user=request.user).count() and not request.user.is_superuser )):
      return HttpResponseForbidden(
        'You do not have access to the provided CloudAdmin project')

    # Verify that the expiry-date is within set limits
    today = datetime.date.today()
    expiry = validated['expiry_datetime'] 

    try:
      projectlength = parser.getint('limits', 'openstack_project_days')
    except:
      projectlength = 185

    try:
      projectslength = parser.getint('limits', 'openstack_project_superuser_days')
    except:
      projectslength = 370

    if(request.user.is_superuser):
      maxlength = today + datetime.timedelta(days=projectslength)
    else:
      maxlength = today + datetime.timedelta(days=projectlength)

    if(expiry < today or expiry > maxlength):
      return HttpResponseBadRequest(
        'The expiry date must be between today and %s'% str(maxlength))

    # Make sure the cloud-admin project have room.
    freeQuota = validated['caproject'].getFree()
    if(not freeQuota.haveRoom(validated['quota'])):
      return HttpResponseBadRequest(
          'The cloudadmin-project have insuficcient quota')

    # Make sure only superusers can allow projects to create fast volumes.
    if(validated['volumetypeid'] > 1 and not request.user.is_superuser):
      return HttpResponseBadRequest('Invalid volume-type selection')

    # Try to create an openstack project
    try:
      connection = getOpenstackConnection()
      osproject = createOpenstackProject(
        connection     = connection,
        name           = validated['name'],
        description    = validated['description'],
        domain         = parser.get('openstack', 'default_project_domain_id'),
        expiry         = validated['expiry'],
        cpu            = validated['quota'].cpu_cores,
        ram_mb         = validated['quota'].ram_gb * 1024,
        cinder_gb      = validated['quota'].cinder_gb,
        cinder_volumes = validated['quota'].cinder_volumes,
        cinder_types   = validated['volumetypes'], 
        swift_objects  = validated['quota'].swift_objects,
        swift_gb       = validated['quota'].swift_gb,
      )

    # If a name or value-error is raised, return the message to the user as a
    # warning.
    except (NameError, ValueError) as e:
      return HttpResponseBadRequest(str(e))

    # If a lookup-error is raised, the user has done something illigal, and is
    # warned with a danger message
    except LookupError as e:
      return HttpResponseForbidden(str(e))

    # If everything goes well:
    else:
      # Tag the new project with the right CloudAdmin project ID
      osproject = connection.identity.get_project(osproject['id'])
      osproject.add_tag(connection.identity, 
          'CloudAdminProject=%d' % validated['caproject'].id)

      # Update the cloudadmin project's usage: 
      usage = validated['caproject'].usage
      usage.add(validated['quota'])
      usage.save()
      return HttpResponse('Project created') 

  # If the request is a get request, we return a list over the project the user
  # have access to.
  elif(request.method == 'GET'):
    domains = {}
    data = {}

    userprojects = []
    adminaccess = []

    projects = {}
    readaccess = {}
    unmanaged = {}

    conn = getOpenstackConnection()
    carole = conn.identity.find_role('cloudadmin')
    osuser = getOpenstackUser(conn, request.user.username, 
        parser.get('openstack', 'default_project_domain_id'))

    if(osuser):
      for ra in conn.list_role_assignments(filters={'user':osuser.id}):
        if('project' in ra):
          userprojects.append(ra.project)
          if(ra.id == carole.id):
            adminaccess.append(ra.project)

    for project in conn.identity.projects():
      access = False

      # Retrieve basic parameters
      p = {
        'name': project.name,
        'id': project.id,
        'infourl': reverse('web.openstack.projectinfo', args=[project.id]),
        'adminurl': reverse('web.openstack.project', args=[project.id]),
      }

      # Get domain-name (and cache the responses to avoid too many requests to
      # the openstack API.)
      try:
        p['domain'] = domains[project.domain_id]
      except KeyError:
        domain = conn.identity.get_domain(project.domain_id)
        domains[project.domain_id] = domain.name 
        p['domain'] = domains[project.domain_id]

      # Determine if the openstack-project is associated with a cloudadmin
      # project.
      for tag in project.tags:
        m = re.match(r'^CloudAdminProject=(.*)', tag)
        if m:
          p['CloudAdminProject'] = int(m.group(1))

          if(p['id'] in adminaccess or 
              (m and Project.objects.filter(pk=m.group(1), groups__in = \
              Group.objects.filter(user=request.user).all()).count()) or
              request.user.is_superuser):
            access = True
        elif(tag == 'DELETABLE'):
          p['deletable'] = True 

      # check that the openstack project is managed, and in that case if the
      # user have access.
      if('CloudAdminProject' in p and access):
        projects[p['name']] = p

      elif('CloudAdminProject' in p and p['id'] in userprojects):
        readaccess[p['name']] = p

      # Superusers should be able to see unmanaged projects as well.
      elif(request.user.is_superuser):
        unmanaged[p['name']] = p

    # Return the project-lists sorted by name.
    data['projects'] = []
    for name in sorted(projects.keys()):
      data['projects'].append(projects[name])
    data['unmanaged'] = []
    for name in sorted(unmanaged.keys()):
      data['unmanaged'].append(unmanaged[name])
    data['readaccess'] = []
    for name in sorted(readaccess.keys()):
      data['readaccess'].append(readaccess[name])

    return JsonResponse(data) 

  # If the request is someting else than a GET or a POST, return an error.
  else:
    return HttpResponseBadRequest('Method %s not implemented' % request.method)

@apiauth
def single(request, projectid):
  """ API View - Displays, updates or deletes an openstack project

  This API view can display an openstack project, update it or delete it. The
  view recieves an openstack project ID through the URL (the second parameter of
  the python method, 'projectid').

  Requests:
    GET: Simply returns the specified project as a JSON blob.
    POST: Updates an existing cloudadmin project. There are multiple parameters
          needed to perform a POST request. If any of the parameters differs
          from what the project already have, the project will be updated.
      parentid:      An integer representing the ID of the cloudadmin project
                     which the openstack project should be associated to.
      name:          A string representing the name of the project.
      description:   A string describing the openstack project.
      expiry:        A string of the format "YYYY-MM-DD" representing the
                     expiry-date of the openstack project. 
      volumetypeid:  An integer representing how fast cinder-volumes the project
                     is allowed to create. 0=Slow, 1=Normal, 2=Fast, 3=VeryFast,
                     4=Unlimited. The project can create volume of a certain
                     speed or slower. A '3' would thus indicate Slow, Normal,
                     Fast or Veryfast.
      cpu_cores:
      ram_gb:
      cinder_gb:
      cinder_volumes:
      switft_gb:
      swift_objects: All 6 parameters are integers representing the requested
                     quotas for the new openstack project.
    DELETE: Marks an openstack-project for deletion, removes all users and stops
            all virtual machines.

   Return codes:
     200: Request OK
     400: Parameter problems. Wrong format, invalid values etc.
     403: No access to the project
     404: Project not found
  """

  conn = getOpenstackConnection()

  try:
    data = getAndVerifyAccessToOpenstackProject(conn, projectid, request.user)
  except LookupError:
    raise Http404

  data['adminurl'] = reverse('web.openstack.project', args=[data['id']])
  data['infourl']  = reverse('web.openstack.projectinfo', args=[data['id']])

  # If it is a GET-request, one should simply return information about the
  # openstack-project as JSON.
  if(request.method == 'GET'):
    return JsonResponse(data)

  # If it is a POST request, one should update the openstack-project before
  # returning the updated openstack project as JSON
  elif(request.method == 'POST'):
    if not data['write']:
      return HttpResponseForbidden('No write access to project')

    # Validate form-data
    try:
      validated = validateFormData(request.POST)
    except ValueError as e:
      return HttpResponseBadRequest('Invalid data provided: %s' % str(e))

    # Determine that the user making the request actually have access to the
    # cloud-admin project he would like to move the openstack project to.
    if(not validated['caproject'] or (not validated['caproject'].groups. \
        filter(user=request.user).count() and not request.user.is_superuser )):
      return HttpResponseForbidden('No access to cloudadmin-project')

    # Verify that the expiry-date is within set limits
    today = datetime.date.today()
    expiry = validated['expiry_datetime'] 

    try:
      projectlength = parser.getint('limits', 'openstack_project_days')
    except:
      projectlength = 185

    try:
      projectslength = parser.getint('limits', 'openstack_project_superuser_days')
    except:
      projectslength = 370

    if(request.user.is_superuser):
      maxlength = today + datetime.timedelta(days=projectslength)
    else:
      maxlength = today + datetime.timedelta(days=projectlength)

    if(expiry < today or expiry > maxlength):
      return HttpResponseBadRequest(
        'The expiry date must be between today and %s' % str(maxlength))

    # Calculate the size of the new quotas, and the difference between the
    # existing and the new.
    old = QuotaInformation()
    old.fromDict(data['quota'])
    diff = QuotaInformation()
    diff.add(validated['quota'])
    diff.subtract(old)

    # If the openstack-project is already managed by cloudadmin, and it should
    # not change which project it belongs to; verify that the cloud-admin
    # project have room for the diff.:
    freeQuota = validated['caproject'].getFree()
    if('CloudAdminProject' in data and 
        int(data['CloudAdminProject']) == validated['caproject'].id):
      change = diff
    # If the openstack-project should be assigned to a new cloud-admin project,
    # make sure the new cloud-admin project have room for the whole openstack
    # project.
    else:
      change = validated['quota']

    if(not freeQuota.haveRoom(change)):
      return HttpResponseBadRequest("There is no room for the new quotas")

    # Make sure only superusers can allow projects to create fast volumes.
    if(validated['volumetypeid'] > 1 and not request.user.is_superuser):
      return HttpResponseBadRequest("Invalid volume-type selection")

    # Try to update the openstack project
    try:
      connection = getOpenstackConnection()
      osproject = updateOpenstackProject(
        connection     = connection,
        openstack_id   = data['id'],
        name           = validated['name'],
        description    = validated['description'],
        expiry         = validated['expiry'],
        cpu            = validated['quota'].cpu_cores,
        ram_mb         = validated['quota'].ram_gb * 1024,
        cinder_gb      = validated['quota'].cinder_gb,
        cinder_volumes = validated['quota'].cinder_volumes,
        cinder_types   = validated['volumetypes'], 
        swift_objects  = validated['quota'].swift_objects,
        swift_gb       = validated['quota'].swift_gb,
      )

    # If a name or value-error is raised, return the message to the user as a
    # warning.
    except (NameError, ValueError, UsageTooHighException) as e:
      return HttpResponseBadRequest(str(e))

    # If a lookup-error is raised, the user has done something illigal, and is
    # warned with a danger message
    except LookupError as e:
      return HttpResponseForbidden(str(e))

    # If everything goes well:
    else:
      osproject = connection.identity.get_project(osproject['id'])
      # If active cloud-admin project should change; remove the old tag, and
      # reduce that projects usage correspondingly
      if('CloudAdminProject' in data and 
          int(data['CloudAdminProject']) != validated['caproject'].id):
        osproject.remove_tag(connection.identity, 
            'CloudAdminProject=%d' % int(data['CloudAdminProject']))
        oldca = Project.objects.get(pk=int(data['CloudAdminProject'])) 
        olduse = oldca.usage
        olduse.subtract(validated['quota'])
        olduse.save()

      usage = validated['caproject'].usage
      # If there is a new (or changed) cloud-admin project; add the new tag
      # and increase the cloud-admin project's usage accordingly
      if('CloudAdminProject' not in data or 
          int(data['CloudAdminProject']) != validated['caproject'].id):
        osproject.add_tag(connection.identity, 
            'CloudAdminProject=%d' % validated['caproject'].id)

        usage.add(validated['quota'])
      else:
        usage.add(diff)
      usage.save()

    return JsonResponse(data)

  elif request.method == 'DELETE':
    if not data['write']:
      return HttpResponseForbidden('No write access to project')

    osproject = conn.identity.get_project(data['id'])
    roles = {}

    # Remove all users from the project
    roleAssignments = conn.list_role_assignments(filters={'project':data['id']})
    for ra in roleAssignments:
      if(ra['id'] not in roles):
        roles[ra['id']] = conn.identity.get_role(ra['id'])

      if('user' in ra):
        user = conn.identity.get_user(ra['user'])
        osproject.unassign_role_from_user(conn.identity, user,
            roles[ra['id']])
      if('group' in ra):
        group = conn.identity.get_group(ra['group'])
        osproject.unassign_role_from_group(conn.identity, group, 
            roles[ra['id']])

    # Stop all VM's in the project
    for server in conn.list_servers(all_projects=True, 
        filters={'project_id': data['id']}):
      conn.compute.stop_server(server['id'])

    # Mark the project for deletion
    osproject.add_tag(conn.identity, 'DELETABLE')
    osproject.description = "DELETABLE: %s" % osproject.description
    osproject.commit(conn.identity)

    # If the openstack-project was associated with a caproject; decrease the
    # caproject's usage according to what the project's quotas.
    if('CloudAdminProject' in data):
      osproject.remove_tag(conn.identity, 
          'CloudAdminProject=%d' % int(data['CloudAdminProject']))
      caproject = Project.objects.get(pk=int(data['CloudAdminProject'])) 
      osuse = QuotaInformation()
      osuse.fromDict(data['quota'])
      caproject.removeUsage(osuse)

    return HttpResponse("Project marked for deletion") 

  # If it is neither a GET nor a POST or a DELETE request; return an error
  else:
    return HttpResponseBadRequest('Method %s not implemented' % request.method)

@apiauth
def assignments(request, projectid):
  """ API View - Adds or removes roles from users in an openstack project

  This view handles role-assignments to openstack projects. To display current
  roles, the view "cloudadmin.endpoints.openstack.single" should be used
  instead. The view implemets the following requests:
    POST:   Adds a new role to an existing user in an existing openstack
            project. The view needs the following parameters:
              access: A string representing the role-name.
              type:   A string describing if the role should be assigned to a
                      'user' or a 'group'
              name:   A string representing a users username or a groups name.
              domain: A string representing the domain a user or a group is a
                      part of.
    DELETE: This view removes a certain role in a project from a user or a
            group. This view needs a single parameter to work:
              id:     A string containing the ID of a user or a group, and the
                      name of the role to be removed in the following format:
                        <user_id|group_id>:<rolename>
  """

  conn = getOpenstackConnection()

  # Retrieve the openstack-project, and make sure that the requesting user have
  # access to it.
  try:
    data = getAndVerifyAccessToOpenstackProject(conn, projectid, request.user)
  except LookupError:
    raise Http404

  # Make sure the requesting user is allowed to change that openstack-project.
  if not data['write']:
    return HttpResponseForbidden('No write access to project')

  # POST means adding a new role to a user.
  if(request.method == 'POST'):
    # Determine that the role-name is supplied, and that it is a role allowed to
    # be managed by cloudadmin.
    if('access' not in request.POST or 
        request.POST['access'] not in rolenames):
      return HttpResponseBadRequest('Invalid role') 

    # Make sure that the role should be assigned to a user OR a group.
    if('type' not in request.POST or (
        request.POST['type'] != 'user' and
        request.POST['type'] != 'group')):
      return HttpResponseBadRequest('Invalid type') 

    # Retrieve the role from openstack
    try:
      role = conn.identity.find_role(request.POST['access'])
    except:
      return HttpResponseBadRequest('Could not find role')

    # Sanitize user input which are free-text:
    # (rolename and type is already sanitized by being checked against a limited
    # set of options).
    domain_name = re.match(r'[a-zA-Z0-9]+', request.POST['domain']).group(0)
    name = re.match(r'[a-zA-Z0-9_\-]+', request.POST['name']).group(0)

    # If name or domain-name is not validated, an error must be returned.
    if(not domain_name or not name):
      return HttpResponseBadRequest('Domain or name was invalid')

    # Retrieve the domain from openstack. 
    try:
      domain = conn.identity.find_domain(domain_name)
    except: 
      return HttpResponseBadRequest('Could not retrieve domain from openstack')
    if not domain:
      return HttpResponseBadRequest('Domain does not exist')

    # If the role should be associated to a useR:
    if(request.POST['type'] == 'user'):
      # Retrieve the user in question from openstack
      user = getOpenstackUser(conn, name, domain.id)
      if not user:
        return HttpResponseBadRequest('Invalid username')

      # Add the role in the project to the user
      try:
        conn.identity.assign_project_role_to_user(data['id'], user, role)
      except:
        return HttpResponseBadRequest('Could not assign role to user')
        
      # Return a status 200 OK
      return HttpResponse('User got role in project') 

    # If the role should be associated to a group:
    if(request.POST['type'] == 'group'):
      #Retrieve the group from openstack
      group = getOpenstackGroup(conn, name, domain.id)
      if not group:
        return HttpResponseBadRequest('Invalid username')

      # Assign the role to the retrieved group
      try:
        conn.identity.assign_project_role_to_group(data['id'], group, role)
      except:
        return HttpResponseBadRequest('Could not assign role to group')
        
      # Return a status 200 OK
      return HttpResponse('Group got role in project.') 

    # If for some reason none of the if's apply, return a generic error. 
    return HttpResponseBadRequest('Generic error')

  # A DELETE request should revoke a role for a user/group in a project.
  elif(request.method == 'DELETE'):
    # Parse the supplied parameters (django does only parse GET and POST, not
    # DELETE).
    parameters = QueryDict(request.body)
    usergroup, rolename = parameters.get('id').split(':')

    # Make sure that the user|group ID is in a valid format (ie: a hex-string).
    if(not re.match(r'^[0-9a-f]+$', usergroup)):
      return HttpResponseBadRequest('The supplied user/grop ID is invalid')

    # Make sure the supplied rolename is a role allowed to be managed by
    # cloudadmin.
    if(rolename not in rolenames):
      return HttpResponseBadRequest('The supplied role is invalid')

    # Retrieve the role in question from openstack.
    try:
      role = conn.identity.find_role(rolename)
    except:
      return HttpResponseBadRequest('Could not find role')

    # Determine if the supplied ID is for a user or for a group by first trying
    # to retrieve a user with that ID, if that fails try to retrieve a group
    # with that ID. If both these steps fails, return an error.
    roletype = None
    try:
      user = conn.identity.get_user(usergroup)
      roletype = 'user'
    except Exception as e:
      try:
        group = conn.identity.get_group(usergroup)
        roletype = 'group'
      except Exception as e:
        return HttpResponseBadRequest('Could not find a user or a group with ' +
            'the supplied ID')

    # If a user should have the role revoked:
    if(roletype == 'user'):
      # Revoke the role
      try:
        conn.identity.unassign_project_role_from_user(data['id'], user, role)
      except Exception as e:
        return HttpResponseBadRequest('Could not revoke %s for %s' % (rolename,
            user.name))

      # Return a message to the user.
      return HttpResponse('Users role revoked from project.') 

    # If it is not a user-id, it have to be a group-id.
    else:
      # Revoke the role
      try:
        conn.identity.unassign_project_role_from_group(data['id'], group, role)
      except Exception as e:
        return HttpResponseBadRequest('Could not revoke %s for %s' % (rolename,
            group.name))

      # Return a confirmation.
      return HttpResponse('Groups role revoked from project.') 

  # If an unsupported method is used, return a 400 BadRequest.
  else:
    return HttpResponseBadRequest('Method %s not implemented' % request.method)

