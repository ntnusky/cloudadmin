from django.contrib.auth.models import User, Group

from django_python3_ldap.utils import format_search_filters

from cloudadmin.settings import LDAP_AUTH_GROUP_RELATIONS
from cloudadmin.settings import LDAP_AUTH_GROUP_ATTRS
from cloudadmin.settings import LDAP_AUTH_MEMBER_OF_ATTRIBUTE
from cloudadmin.settings import LDAP_AUTH_GROUP_RELATIONS

def custom_sync_user_relations(user, ldap_attributes):
  """ Custom function to sync group-membershipt from LDAP

  This method lists which groups a user is member of in LDAP, and syncs them
  into the django-database. It updated a users relation every time the user logs
  in.
  """

  # REtrieve a lit of groups
  group_memberships = frozenset(ldap_attributes[LDAP_AUTH_MEMBER_OF_ATTRIBUTE])

  # Sync user model boolean attrs. Currently it is the superuser attribute.
  # Staff attribute can also be relevant.
  for group_id, attr_name in LDAP_AUTH_GROUP_ATTRS.items():
    setattr(user, attr_name, group_id in group_memberships)
  user.save()

  # Make sure all the groups the user is in also exists in django 
  o = list(group_memberships)
  o.sort()
  ingroups = []
  for adname in o:
    if Group.objects.filter(name=adname).count() == 0:
      g = Group(name=adname)
      g.save()
    ingroups.append(adname)
  
  # Create a list of the groups which the user should not be in.
  allgroupnames = [ \
      value['name'] for value in \
      Group.objects.filter(name__startswith = 'CN').values('name')
  ]
  notin = [name for name in allgroupnames if name not in ingroups]

  # Sync user model groups.
  user.groups.add(*Group.objects.filter(name__in=ingroups))
  user.groups.remove(*Group.objects.filter(name__in=notin))

  return
