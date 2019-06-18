import datetime
import openstack
import re

from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import Group, User
from rgwadmin.exceptions import NoSuchUser

from cloudadmin.ceph import getRGWConnection, getRGWUserQuota, getRGWUserUsage
from cloudadmin.exceptions import UsageTooHighException
from cloudadmin.models import Project, QuotaInformation
from cloudadmin.settings import parser
from cloudadmin.utils import humanReadable

def getOpenstackConnection():
  """ This method returns a valid, and initialized openstack connection object
  """

  connection = openstack.connect(
    region = parser.get('openstack', 'region'), 
    auth = {
      'auth_url':         parser.get('openstack', 'auth_url'),
      'domain_name':      parser.get('openstack', 'domain_name'), 
      'password':         parser.get('openstack', 'password'),
      'project_name':     parser.get('openstack', 'project_name'),
      'user_domain_name': parser.get('openstack', 'user_domain_name'),
      'username':         parser.get('openstack', 'username'),
    },
  )

  return connection

def getOpenstackProjectQuota(connection, project_id):
  """ Queries the openstack-API for project_quotas

  This method queries the openstack-API for the supplied project_id's project
  quotas, and returns the quotas in a dict. The dict have the following
  data-member:
  { 'compute': { 'instances', 'cpu', 'ram_mb', 'ram_human'},
    'network': {'subnet', 'network', 'security_group_rule', 'security_group',
                'floatingip', 'router', 'port', 'loadbalancer' },
    'volumes': {'gigabytes', 'gigabytes_human', 'volumes', 'types'}
  }
  """

  compute = connection.get_compute_quotas(project_id)
  network = connection.get_network_quotas(project_id)
  volumes = connection.get_volume_quotas(project_id)

  quota = {}
  quota['compute'] = {
    'instances': compute['instances'],
    'cpu': compute['cores'],
    'ram_mb': compute['ram'],
    'ram_human': '%sB' % humanReadable(compute['ram'], 'm'),
  }
  quota['network'] = {
    'subnet': network['subnet'],
    'network': network['network'],
    'security_group_rule': network['security_group_rule'],
    'security_group': network['security_group'],
    'floatingip': network['floatingip'],
    'router': network['router'],
    'port': network['port'],
    'loadbalancer': network['loadbalancer'],
  }
  quota['volumes'] = {
    'gigabytes': volumes['gigabytes'],
    'gigabytes_human': '%sB' % humanReadable(volumes['gigabytes'], 'g'),
    'volumes': volumes['volumes'],
    'types': {
      'Slow': volumes['volumes_Slow'] != 0,
      'Normal': volumes['volumes_Normal'] != 0,
      'Fast': volumes['volumes_Fast'] != 0,
      'VeryFast': volumes['volumes_VeryFast'] != 0,
      'Unlimited': volumes['volumes_Unlimited'] != 0,
    }
  }
  
  return quota

def getOpenstackUser(connection, username, domain_id):
  """ Queries the openstack-API for a certain user.

  Returns Null in the event of an error.
  """
  try:
    users = connection.list_users(domain_id=domain_id, name=username)
  except:
    return None

  user = None
  for u in users:
    if(u.name == username):
      user = u

  return user

def getOpenstackGroup(connection, groupname, domain_id):
  """ Queries the openstack-API for a certain group.
  
  Returns Null in the event of an error.
  """
  try:
    groups = connection.search_groups(groupname, domain_id=domain_id)
  except:
    return None

  group = None
  for g in groups:
    if(g.name == groupname):
      group = g

  return group

def getOpenstackProjectUsage(connection, project_id):
  """ Queries the openstack API for a projects current usage.
  
  The method also calculates a percentage of the used projects. If the quota for
  a resource is 0, the percentage is set to 100.
  """

  quota = {}

  # Determine the compute-usage
  compute = connection.get_compute_limits(project_id)
  quota['compute'] = {
    'instances': compute['total_instances_used'],
    'cpu': compute['total_cores_used'],
    'ram_mb': compute['total_ram_used'],
    'ram_human': '%sB' % humanReadable(compute['total_ram_used'], 'm'),
  }

  try:
    quota['compute']['instances_percent'] = int(
        (compute['total_instances_used'] * 100) / 
        compute['max_total_instances']
    )
  except ZeroDivisionError:
    quota['compute']['instances_percent'] = 100

  try:
    quota['compute']['cpu_percent'] = int(
        (compute['total_cores_used'] * 100) / compute['max_total_cores'])
  except ZeroDivisionError:
    quota['compute']['cpu_percent'] = 100

  try:
    quota['compute']['ram_percent'] = int(
        (compute['total_ram_used'] * 100) / compute['max_total_ram_size'])
  except ZeroDivisionError:
    quota['compute']['ram_percent'] = 100


  # Determine cinder usage
  volumequota = connection.get_volume_quotas(project_id)
  quota['volumes'] = {
    'gigabytes': 0, 
    'volumes': 0, 
  }

  # For each volume belonging to project, sum up the size and number of volumes
  for volume in connection.volume.volumes(**{
      'all_projects': True, 'project_id': project_id}):
    quota['volumes']['gigabytes'] += volume.size
    quota['volumes']['volumes'] += 1 

  # Calculate human readable and percentages.
  quota['volumes']['gigabytes_human'] = '%sB' % \
      humanReadable(quota['volumes']['gigabytes'], 'g')

  try:
    quota['volumes']['gigabytes_percent'] = int(
        (quota['volumes']['gigabytes'] * 100) / volumequota['gigabytes'])
  except ZeroDivisionError:
    quota['volumes']['gigabytes_percent'] = 100

  try:
    quota['volumes']['volumes_percent'] = int(
        (quota['volumes']['volumes'] * 100) / volumequota['volumes'])
  except ZeroDivisionError:
    quota['volumes']['volumes_percent'] = 100
  
  return quota

def getOpenstackRoleAssignments(connection, project_id):
  """ Queries the openstack API for all roles present in a certain project
  
  Returns a dict populated with two dicts, each representing the users/groups
  roles int the project.
  """

  users = {}
  groups = {}

  roles = {}
  domains = {}

  # For each role-assignment in openstack:
  for ra in connection.identity.role_assignments(scope_project_id=project_id):
    # Retrieve the role-name, if the role-name is not already in the cache.
    if(ra.role['id'] not in roles):
      roles[ra.role['id']] = connection.identity.get_role(ra.role['id']).name

    # If the role-assignment is for a user:
    if(ra.user):
      # Retrieve the user in question from openstack, if it is not already
      # collected.
      if(ra.user['id'] not in users):
        try:
          user = connection.identity.get_user(ra.user['id'])
        except openstack.exceptions.ResourceNotFound:
          continue

        if(user.domain_id not in domains):
          domains[user.domain_id] = connection.get_domain(user.domain_id).name

        users[ra.user['id']] = {
          'username': user.name,
          'email': user.email,
          'domain': domains[user.domain_id],
          'roles': [],
        }

      # Add the current role to the user.
      users[ra.user['id']]['roles'].append(roles[ra.role['id']])

    # If the role-assignment is for a group.
    if(ra.group):
      # Retrieve the group in question from openstack, if it is not already
      # collected.
      if(ra.group['id'] not in groups):
        try:
          group = connection.identity.get_group(ra.group['id'])
        except openstack.exceptions.ResourceNotFound:
          continue

        if(group.domain_id not in domains):
          domains[group.domain_id] = connection.get_domain(group.domain_id).name

        groups[ra.group['id']] = {
          'name': group.name,
          'domain': domains[group.domain_id],
          'roles': []
        }

      # Add the current role to the group
      groups[ra.group['id']]['roles'].append(roles[ra.role['id']])

  # Return the users and groups dicts in a parent dict.
  return {
    'users': users,
    'groups': groups,
  }

def getOpenstackProject(connection, project_id):
  """ Retrieves information about an openstack-project from the openstack API

  The information is returned in a large dict
  """

  try:
    osproject = connection.identity.get_project(project_id)
  except:
    raise LookupError('Could not retrieve openstack project')

  data = {}
  data['id'] = osproject.id
  data['name'] = osproject.name
  data['description'] = osproject.description
  data['domain_id'] = osproject.domain_id
  data['domain_name'] = connection.identity.get_domain(osproject.domain_id).name

  data['quota'] = getOpenstackProjectQuota(connection, data['id'])
  data['quota']['swift'] = getRGWUserQuota('%s$%s' % (data['id'], data['id'])) 
  data['usage'] = getOpenstackProjectUsage(connection, data['id'])
  data['usage']['swift'] = getRGWUserUsage('%s$%s' % (data['id'], data['id']))
  
  # Iterate tags, and store them as values in the dict. The tag DELETABLE is a
  # bit special, and is stored a boolean.
  for tag in osproject.tags:
    m = re.match(r'^([^=]*)=(.*)', tag)
    if m:
      data[m.group(1)] = m.group(2)
    elif(tag == 'DELETABLE'):
      data['deletable'] = True

  # If there is not an Expiry-date set, try to read the old-style
  # expiry-parameter. If that parameter is found, set the expiry in the new
  # tag-format.
  if('Expire' not in data):
    oldstyleproject = connection.get_project(project_id)
    try:
      m = re.match(r'^([0-9]{2})\.([0-9]{2})\.([0-9]{4})$', oldstyleproject.expiry)
    except:
      m = None

    if m:
      data['Expire'] = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
      osproject.add_tag(connection.identity, 'Expire=%s' % data['Expire'])

  # If the openstack project is managed by cloudadmin, retrieve the cloudadmin
  # project from the database, and update the name/prefix.
  if('CloudAdminProject' in data):
    caproject = Project.objects.get(pk=int(data['CloudAdminProject']))
    data['name_prefix'] = caproject.projectprefix
    pre, sep, post = data['name'].partition('_')
    if(pre == data['name_prefix']):
      data['name'] = post 

  # Retrieve the role-assignments for the project.
  data.update(getOpenstackRoleAssignments(connection, project_id))

  return data

def getAndVerifyAccessToOpenstackProject(connection, project_id, user):
  """ Retrieve an openstack-project from the openstack API, and verify that the
  supplied user have access to the openstack project.

  This method adds a new data-member 'write', which is True if the calling user
  is allowed to update the openstack project.
  """

  # Try to recieve openstack-rpoject. Raises a LookupError if the project does
  # not exist.
  osproject = getOpenstackProject(connection, project_id)
  osproject['write'] = False
  
  # If the requesting user is a superuser, return the project:
  if user.is_superuser:
    osproject['write'] = True
    return osproject

  # If the user have access to the cloudadmin-project, return the project
  if('CloudAdminProject' in osproject and
    Project.objects.filter(pk=int(osproject['CloudAdminProject']), groups__in =
    Group.objects.filter(user=user).all()).count()
  ):
    osproject['write'] = True
    return osproject

  # If the requesting user have the "cloudadmin" role in openstack for this
  # project, return the project:
  osuser = getOpenstackUser(connection, user.username, 
      parser.get('openstack', 'default_project_domain_id'))
  if(osuser):
    access = False
    carole = connection.identity.find_role('cloudadmin')
    for ra in connection.list_role_assignments(filters = {
        'user': osuser.id, 'project': osproject['id']}):
      access = True
      if(ra.id == carole.id):
        osproject['write'] = True

    if(access):
      return osproject

  # Otherwise, raise a permission-denied error. 
  raise PermissionDenied('No access to project')

def updateOpenstackProject(connection, name, description, expiry,
    create = False, openstack_id = None, domain = None, 
    cpu = 0, ram_mb = 0, 
    cinder_gb = 0, cinder_volumes = 0, cinder_types = ['Slow', 'Normal'],
    swift_objects = 0, swift_gb = 0):
  """ A function to update (or create) an openstack-project using the API's.
  """

  # Make sure that the request is not both a 'create' and 'update' request.
  if(not create and not openstack_id):
    raise ValueError('Either the create-flag must be true, or the ID ' + \
        'of an existing openstack-project must be provided')
  if(create and openstack_id):
    raise ValueError('Cannot define the ID when creating a project')
  if(create and not domain):
    raise ValueError('If a project should be created, a domain must be set')
  if(not create and domain):
    raise ValueError('Cannot change the domain of an existing project')

  # If it is a new request, check that the name is unique and create an empty
  # data-structure. If it is an existing project, retrieve the current project
  # from openstack.
  if(create):
    if(connection.get_project(name)):
      raise NameError('There already exists an object with that name')
    
    project = {
      'quota': {
        'compute': {},
        'network': {},
        'volumes': {
          'types': {},
        },
        'swift': {
          'user': {},
          'buckets': {},
        },
      },
    }
  else:
    project = getOpenstackProject(connection, openstack_id)

  # Create an empty set which can contain keywords indicating that certain
  # parts are updated, and thus needs to be saved in the end.
  project['changes'] = set()

  # Check if the name should be changed, and in that case make sure the new name
  # is valid.
  if('name' not in project or project['name'] != name):
    if(not re.match(r'^[a-zA-Z0-9_]+$', name)):
      raise ValueError(
          "The project-name can only contain letters (a-z), numbers and '_'"
      )

    project['name'] = name
    project['changes'].add('project')

  # Update the description.
  if('description' not in project or project['description'] != description):
    # Replace æøå with more safe alternatives.
    project['description'] = description. \
      replace('æ', 'ae').replace('Æ', 'AE'). \
      replace('ø', 'oe').replace('Ø', 'OE'). \
      replace('å', 'aa').replace('Å', 'AA')
    project['changes'].add('project')

  # Make sure the provided expire-date is a real date, if it is changed.
  if('Expire' not in project or project['Expire'] != expiry):
    if(not re.match(r'^(20[0-9]{2})-([0-9]{2})-([0-9]{2})$', expiry)):
      raise ValueError("The expire-date does not look like a date. It should" +
          " be on the format 'YYYY-MM-DD'")

    project['Expire'] = expiry
    project['changes'].add('Expire')

  # Add relevant domain-properties
  if(domain):
    osdomain = connection.identity.find_domain(domain)
    if(osdomain):
      if('domain_name' not in project or 'domain_id' not in project or
          project['domain_name'] != osdomain.name or
          project['domain_id'] != osdomain.id):
        project['domain_name'] = osdomain.name
        project['domain_id'] = osdomain.id
        project['changes'].add('project')
    else:
      raise LookupError('The domain %s could not be found' % domain)

  # Determine if the volume-quotas are correct
  if('gigabytes' not in project['quota']['volumes'] or 
      'volumes' not in project['quota']['volumes'] or
      project['quota']['volumes']['gigabytes'] != cinder_gb or
      project['quota']['volumes']['volumes'] != cinder_volumes):
    project['quota']['volumes']['gigabytes'] = cinder_gb
    project['quota']['volumes']['volumes'] = cinder_volumes
    project['changes'].add('volumequota')

  # Create a set with the volume-types currently granted access to
  current_types = set()
  for t in project['quota']['volumes']['types']:
    if project['quota']['volumes']['types'][t]:
      current_types.add(t)

  # Determine if any volume-types needs to be added or removed
  if(len(current_types.symmetric_difference(set(cinder_types)))):
    for vtype in ['Slow', 'Normal', 'Fast', 'VeryFast', 'Unlimited']:
      project['quota']['volumes']['types'][vtype] = vtype in cinder_types
    project['changes'].add('volumequota')

  # Determine if the compute-quotas needs to be changed
  if('cpu' not in project['quota']['compute'] or
      'ram_mb' not in project['quota']['compute'] or
      project['quota']['compute']['cpu'] != cpu or
      project['quota']['compute']['ram_mb'] != ram_mb):
    project['quota']['compute']['cpu'] = cpu
    project['quota']['compute']['ram_mb'] = ram_mb
    project['changes'].add('computequota')

  # Determine if swift-quotas needs to change
  if('user' not in project['quota']['swift']):
    project['quota']['swift']['user'] = {}
  if('max_size' not in project['quota']['swift']['user'] or
      'max_objects' not in project['quota']['swift']['user'] or
      project['quota']['swift']['user']['max_size'] != swift_gb or
      project['quota']['swift']['user']['max_objects'] != swift_objects):
    project['quota']['swift']['user']['max_size'] = swift_gb
    project['quota']['swift']['user']['max_objects'] = swift_objects
    project['changes'].add('swiftquota')

  # If it is a new openstack project, create it
  if(create):
    created_osproject = connection.create_project(name=project['name'], 
        description=project['description'], domain_id=project['domain_id'])
    osproject = connection.identity.get_project(created_osproject.id)
  # If we are updating an existing project, retrieve it.
  else:
    osproject = connection.identity.get_project(project['id'])

  # If there are scheduled any change of name/description, commit these changes
  # to the openstack API.
  if('project' in project['changes'] and openstack_id):
    osproject.name = project['name']
    osproject.description = project['description']
    osproject.commit(connection.identity)

  # If a new expire-date is set, remove the old one and add the new.
  if('Expire' in project['changes']):
    existing = None
    for tag in osproject.tags:
      if('Expire' in tag):
        existing = tag
        break
    osproject.remove_tag(connection.identity, existing)
    osproject.add_tag(connection.identity, 'Expire=%s' % project['Expire'])

  # If the compute-quota is changed; send the new quota to openstack.
  if('computequota' in project['changes']):
    connection.set_compute_quotas(osproject.id, instances = cpu, cores=cpu, 
        ram=ram_mb)

  # If the volume-quota is changed, send the new quota to openstack.
  if('volumequota' in project['changes']):
    vquota = {
      'volumes': cinder_volumes,
      'gigabytes': cinder_gb,
    }
    for vtype in ['Slow', 'Normal', 'Fast', 'VeryFast', 'Unlimited']:
      if(vtype in cinder_types):
        vquota['volumes_%s' % vtype] = -1
        vquota['gigabytes_%s' % vtype] = -1
      else:
        vquota['volumes_%s' % vtype] = 0
        vquota['gigabytes_%s' % vtype] = 0

    try:
      connection.set_volume_quotas(osproject.id, **vquota)
    except:
      raise UsageTooHighException('Volume-quota can not be set as the use ' +\
          'is higher than the new quotas')

  # If the swift-quota is changed, send the new quota to the radosgw's.
  if('swiftquota' in project['changes']):
    rgw = getRGWConnection()
    rgwid = '%s$%s' % (osproject.id, osproject.id)
    try:
      rgw.get_user(rgwid)
    except NoSuchUser:
      rgw.create_user(rgwid, project['name'], generate_key=False)

    rgw.set_user_quota(rgwid, 'bucket', swift_gb * 1048576, swift_objects, True)
    rgw.set_user_quota(rgwid, 'user', swift_gb * 1048576, swift_objects, True)

  return getOpenstackProject(connection, osproject.id)

def createOpenstackProject(**kwargs):
  """ Creates an openstack project """

  return updateOpenstackProject(create=True, **kwargs)

def validateFormData(arguments):
  """ This method validates tha data in arguments, and makes sure that they
  represent values appropriate for openstack-projects.

  It validates that the quotas are legal values etc. """

  data = {}
  
  # Try to retrieve caproject.
  try:
    data['caproject'] = Project.objects.get(pk=int(arguments['parentid']))
  except:
    data['caproject'] = None

  # Determine full project name, if the project is attached to a caproject with
  # a given prefix.
  if(data['caproject'] and data['caproject'].projectprefix):
    data['name'] = '%s_%s' % (data['caproject'].projectprefix, 
        arguments['name'])
  else:
    data['name'] = arguments['name']

  # Retrieve description, or set blank if missing
  try:
    data['description'] = arguments['description']
  except:
    data['description'] = "" 

  # Validate the date
  m = re.match(r'^(20[0-9]{2})-([0-9]{2})-([0-9]{2})$', arguments['expiry'])
  if(m): 
    y, m, d = m.groups()
    data['expiry'] = arguments['expiry']
    data['expiry_datetime'] = datetime.date(year=int(y), month=int(m), 
        day=int(d))
  else:
    raise ValueError('The expiry date does not look like a date on the format' +
        ' YYYY-MM-DD')

  # Retrieve which volume-types should be allowed, and raise errors if the
  # provided value is invalid. If it is missing, set it to Slow+Normal.
  try:
    data['volumetypeid'] = int(arguments['volumetypeid'])
  except:
    data['volumetypeid'] = 1 
  if(data['volumetypeid'] < 0 or data['volumetypeid'] > 4):
    raise ValueError('The volumetypeid needs to be an integer from 0 to 4')

  # Create an array with the names of the requested volumetypes.
  data['volumetypes'] = []
  index = 0
  for vtype in ['Slow', 'Normal', 'Fast', 'VeryFast', 'Unlimited']:
    if(index <= data['volumetypeid']):
      data['volumetypes'].append(vtype)
      index+=1

  # Retrieve quota-values, or set them to 0 if they are not present
  data['quota'] = QuotaInformation()
  data['quota'].fromDict(arguments)
  
  return data
