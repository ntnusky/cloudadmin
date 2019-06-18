from datetime import timedelta
import string
from random import choice

from django.contrib.auth.models import Group, User
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from cloudadmin.exceptions import InsufficientQuotaException, \
        UsageTooHighException
from cloudadmin.utils import machineReadable, humanReadable

# A class representing a certain project.
class Project(models.Model):
  """ The Project class represent a cloudadmin project

  The cloudadmin-projects are allowed to create openstack prjects (within their
  own quotas), and manage access to these openstack projects.
  """

  name          = models.CharField(max_length=50)
  description   = models.TextField()
  projectprefix = models.CharField(max_length=50)
  parent        = models.ForeignKey('Project', null=True, default=None, 
                                      on_delete=models.PROTECT)
  quota         = models.ForeignKey('Quota', on_delete=models.PROTECT)
  usage         = models.ForeignKey('Usage', on_delete=models.PROTECT)
  groups        = models.ManyToManyField(Group)

  def __str__(self):
    return "%s (%s)" % (self.name, self.projectprefix)

  def asDict(self):
    """ Returns the object as a dict which can be passed to a user as JSON.
    """

    # Try to retrieve the ID of the parent.
    try:
      parentid = self.parent.id
    except AttributeError:
      parentid = 0

    # Create a dict with the base properties.
    data = {
      'id':            self.id,
      'name':          self.name,
      'description':   self.description,
      'projectprefix': self.projectprefix,
      'parent_id':     parentid,
      'parent_name':   self.getParentName(),
      'quota':         self.quota.asDict(),
      'usage':         self.usage.asDict(),
      'free':          self.getFree().asDict(), 
      'groups':        []
    }

    # For each group that can manage the cloudadmin project, retrieve the ID and
    # name.
    for g in self.groups.all():
      data['groups'].append({
        'id':   g.id,
        'name': g.name,
      })

    return data

  def getParentName(self):
    """ Method which returns the name of the parent project.

    If the project dont have a parent, an empty string will be returned
    """

    if(self.parent):
      if(self.parent.parent):
        return "%s - %s" % (self.parent.getParentName(), self.parent.name)
      else:
        return self.parent.name
    else:
      return ""

  def updateQuota(self, quota):
    """ Updates the cloudadmin-project's quota
    
    (and the parents quota, if applicable).
    """

    elements = self.usage.getQuotaElements()
    diff = self.quota.getDiff(quota)

    # Make sure the quotas are 0 or a positive integer, and that they are
    # higher than the current usage.
    for element in elements:
      use = getattr(self.usage, element)
      new = getattr(quota, element)

      if(new < 0):
        raise ValueError('Cannot use negative values as quota')

      if(use > new):
        raise UsageTooHighException(
            'Cannot reduce %s to %d as %d is currently in use' % (
             element, new, use))

    # Make sure that the parent project have sufficient room in its quota
    if(self.parent and not self.parent.haveRoom(diff)):
      raise InsufficientQuotaException(
          'Cannot increase the quota, as the parent quota is too small')

    # If there is a parent project, add the diff of the old and new quota to the
    # parents usage.
    if(self.parent):
      self.parent.addUsage(diff)

    # Update this poroject's quota
    for element in elements:
      new = getattr(quota, element)
      setattr(self.quota, element, new)
      self.quota.save()

  def changeParent(self, newParent):
    """ Change a project's parent, and update relevand usage-structs """

    # If there is no change, simply return.
    if(self.parent == newParent):
      return 

    # If there is a new parent, make sure there is room for the parent-change.
    if(newParent and not newParent.haveRoom(self.quota)):
      raise InsufficientQuotaException('New parent does not have enough quota')

    # Raise an error if a project is set to be its own parent.
    if(self == newParent):
      raise ValueError('A project cannot be its own parent')
    
    # If the project currently belongs to another project, reduce the current
    # parents usage with the amount this project have.
    if(self.parent):
      oldusage = self.parent.usage
      oldusage.subtract(self.quota)
      oldusage.save()

    # If there is a new parent, add the project's quotas to the new parents
    # usage.
    if(newParent):
      newusage = newParent.usage
      newusage.add(self.quota)
      newusage.save()

    # Change parent, and save.
    self.parent = newParent
    self.save()
  
  def updateQuotaParent(self, quota, parent):
    """ Update the quota of both the current project, and its parent's quota. """
    try:
      self.updateQuota(quota)
    except InsufficientQuotaException:
      self.changeParent(parent)
      self.updateQuota(quota)
    else:
      self.changeParent(parent)

  def getFree(self):
    """ Returns a QuotaInformation representing the free resources
    
    Basicly calculates quota-usage
    """
    q = QuotaInformation()
    q.add(self.quota)
    q.subtract(self.usage)
    return q

  def addUsage(self, usage):
    """ Adds a QuotaInformation to the current usage. """

    self.usage.add(usage)
    self.usage.save()

  def haveRoom(self, quota):
    """ Returns a boolean if there is room in the current project for the quota
    
    This method recieves a QuotaInformation object, and returns True if there is
    room for the quota in the current project, and False otherwise. """

    return self.getFree().haveRoom(quota)

  def removeUsage(self, usage):
    """ Subtracts a quotaInformation from the current usage """

    self.usage.subtract(usage)
    self.usage.save()

  @receiver(pre_delete)
  def deleting(sender, instance, **kwargs):
    """ If a project is deleted, update the parent's quota """

    if(sender == Project):
      if(instance.parent):
        parentUsage = instance.parent.usage
        parentUsage.subtract(instance.quota)
        parentUsage.save()

# The resources we are tracking, quota-wise.
class QuotaInformation(models.Model):
  """ Quota-information objects represents a set of resources which we track"""

  cpu_cores      = models.IntegerField(default = 0)
  ram_gb         = models.IntegerField(default = 0)
  cinder_gb      = models.IntegerField(default = 0)
  cinder_volumes = models.IntegerField(default = 0)
  swift_gb       = models.IntegerField(default = 0)
  swift_objects  = models.IntegerField(default = 0)
  
  class Meta:
    """ Do not store this in the database on its own.

    Other classes inherit from this class to store information in the database.
    """

    abstract = True

  def __str__(self):
    """ Returns a summary of the quotas as a string """

    return "%d CPUs, %sB RAM, %sB in %d volumes, %sB and %s objects in swift" % (
        self.cpu_cores, humanReadable(self.ram_gb, 'g'), 
        humanReadable(self.cinder_gb, 'g'), self.cinder_volumes,
        humanReadable(self.swift_gb, 'g'), humanReadable(self.swift_objects)
    )

  def getQuotaElements(self = None):
    """ Returns a list of the data-members of this class """

    return [
      'cpu_cores', 'ram_gb', 
      'cinder_gb', 'cinder_volumes', 
      'swift_gb', 'swift_objects',
    ]

  def add(self, diff):
    """ Add the supplied QuotaInformation to this object's information """

    for element in self.getQuotaElements():
      setattr(self, element, getattr(self, element) + getattr(diff, element))

  def copy(self, original):
    """ Copy the elements from the supplied object to this object """

    for element in self.getQuotaElements():
      setattr(self, element, getattr(original, element))

  def haveRoom(self, quota):
    """ Check if a quota can fit within the current quota 
    
    Return False id any of the supplied quota-elements is larger than the
    current class's quota-element. Return True otherwise.
    """

    for element in self.getQuotaElements():
      if getattr(self, element) < getattr(quota, element):
        return False
    return True

  def subtract(self, diff):
    """ Subtract the supplied QuotaInformation from this object's information """
    
    for element in self.getQuotaElements():
      setattr(self, element, getattr(self, element) - getattr(diff, element))

  def update(self, new):
    """ Updates the current quota-elements to the values supplied. """

    for element in self.getQuotaElements():
      setattr(self, element, getattr(diff, element))

  def asDict(self):
    """ Return the current quota-elements as a dict. """

    data = {}
    for element in self.getQuotaElements():
      data[element] = getattr(self, element)

    # Calculate human-readable values
    data['cpu_human'] = '%s' % humanReadable(data['cpu_cores'])
    data['ram_human'] = '%sB' % humanReadable(data['ram_gb'], 'g')
    data['cinder_human'] = '%sB' % humanReadable(data['cinder_gb'], 'g')
    data['cinder_volumes_human'] = '%s' % \
        humanReadable(data['cinder_volumes'])
    data['swift_human'] = '%sB' % humanReadable(data['swift_gb'], 'g')
    data['swift_objects_human'] = '%s' % \
        humanReadable(data['swift_objects'])

    return data

  def fromDict(self, data):
    """ Read quota-values from a dict.

    The supplied dict can be in one of two formats. Either it is a
    two-dimensional dict with the following structure:
      { 'compute': {'cpu', 'ram_mb'},
        'volumes': {'gigabytes', 'volumes'},
        'swift': {'user': {'max_size', 'max_objects'}}}
    or it is a single dict with the following structure:
      { 'cpu_cores', 'ram_gb', 'cinder_gb', 'cinder_volumes', 'swift_gb', 
        'swift_objects' }
    """

    # If the key 'compute' is found in the supplied data, expect the supplied
    # data to be in the two-dimensional format.
    if('compute' in data):
      elements = {
        'compute': {'cpu': 'cpu_cores', 'ram_mb': 'ram_gb'},
        'volumes': {'gigabytes': 'cinder_gb', 'volumes': 'cinder_volumes'},
      }
      for top in elements:
        for element in elements[top]:
          try:
            setattr(self, elements[top][element], 
                machineReadable(data[top][element]))
          except TypeError:
            setattr(self, elements[top][element], int(data[top][element]))
          except KeyError:
            setattr(self, elements[top][element], 0)
      self.ram_gb = int(self.ram_gb / 1024)

      try:
        self.swift_gb = \
            machineReadable(data['swift']['user']['max_size']) / 1024**3
      except TypeError:
        self.swift_gb = int(data['swift']['user']['max_size']) / 1024**3
      except KeyError:
        self.swift_gb = 0 

      try:
        self.swift_objects = \
            machineReadable(data['swift']['user']['max_objects'])
      except TypeError:
        self.swift_objects = int(data['swift']['user']['max_objects'])
      except KeyError:
        self.swift_objects = 0 

    # If the key 'compute' is not present in the supplied dict, expect the
    # standard one-level dict.
    else:
      for element in self.getQuotaElements():
        try:
          setattr(self, element, machineReadable(data[element]))
        except TypeError:
          setattr(self, element, int(data[element]))
        except KeyError:
          setattr(self, element, 0)

  def getDiff(self, other):
    """ Calculates the difference between the supplied object and the current.

    Basicly returns other-self.
    """

    diff = QuotaInformation()
    diff.add(other)
    diff.subtract(self)
    return diff

class Quota(QuotaInformation):
  """ A class representing a certain project's quota

  Includes a timestamp for last change, which is auto-updated at save-time
  """

  last_updated = models.DateTimeField(auto_now=True)

  def asDict(self):
    data = super(Quota, self).asDict()
    data['last_updated'] = self.last_updated
    return data

class QuotaTemplate(QuotaInformation):
  """ A class representing a quota-template, which can be used when creating new
      projects. """

  name         = models.CharField(max_length=50)
  last_updated = models.DateTimeField(auto_now=True)
  project      = models.ForeignKey('Project', default=None, null=True,
                                     on_delete=models.CASCADE)
  default      = models.BooleanField(default=False)

  def asDict(self):
    """ Returns the quota-template as a dict """

    data = super(QuotaTemplate, self).asDict()

    try:
      projectid = self.project.id
    except AttributeError:
      projectid = 0

    data.update({
      'id':           self.id,
      'name':         self.name,
      'last_updated': self.last_updated,
      'project_id':   projectid,
      'default':      self.default,
    })
    return data

class Usage(QuotaInformation):
  """ A class representing a certain project's resource-usage """
  last_updated = models.DateTimeField(auto_now=True)

  def asDict(self):
    data = super(Usage, self).asDict()
    data['last_updated'] = self.last_updated
    return data

class Token(QuotaInformation):
  """ A class representing API tokens.

  These tokens are used by the API-handlers to ensure that an app have access.
  """

  value     = models.CharField(max_length=32)
  created   = models.DateTimeField(auto_now_add=True)
  last_used = models.DateTimeField(auto_now=True, null=True)
  expiry    = models.DateTimeField()
  user      = models.ForeignKey(User)

  def __str__(self):
    return "Token representing %s expires at %s" % (self.user, self.expiry)

  def generateToken(self):
    """ Generates a new API-token, and sets the validity to 4 hours """

    chars = string.ascii_letters + string.digits
    self.value  = ''.join(choice(chars) for _ in range(30))
    self.expiry = timezone.now() + timedelta(hours=4) 
    self.save()

  def isValid(self):
    """ Returns a boolean if the current API-token is valid """

    return (self.expiry > timezone.now())
