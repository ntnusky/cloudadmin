from django.contrib.auth.models import User, Group

from django_python3_ldap.utils import format_search_filters

from cloudadmin.settings import LDAP_AUTH_GROUP_RELATIONS
from cloudadmin.settings import LDAP_AUTH_GROUP_ATTRS
from cloudadmin.settings import LDAP_AUTH_MEMBER_OF_ATTRIBUTE
from cloudadmin.settings import LDAP_AUTH_GROUP_RELATIONS


def custom_format_search_filters(ldap_fields):
  # custom search filter (e.g. check "memberOf" against configured value)
  ldap_fields[LDAP_AUTH_MEMBER_OF_ATTRIBUTE] = LDAP_AUTH_GROUP_MEMBER_OF
  search_filters = format_search_filters(ldap_fields)
  # All done!
  return search_filters


def custom_sync_user_relations(user, ldap_attributes):
  group_memberships = frozenset(ldap_attributes[LDAP_AUTH_MEMBER_OF_ATTRIBUTE])
  # Sync user model boolean attrs.
  for group_id, attr_name in LDAP_AUTH_GROUP_ATTRS.items():
    setattr(user, attr_name, group_id in group_memberships)
  user.save()

  # Create a list of all groups, and make sure there exists django-groups with
  # this name.
  allgroupnames = set(LDAP_AUTH_GROUP_RELATIONS.values()) 
  for group in allgroupnames:
    if Group.objects.filter(name=group).count() == 0:
      g = Group(name=group)
      g.save()

  # Create a list of groups the user should be in.
  o = list(group_memberships)
  o.sort()
  activegroupnames = []
  for adname in o:
    if adname in LDAP_AUTH_GROUP_RELATIONS:
      activegroupnames.append(LDAP_AUTH_GROUP_RELATIONS[adname])
  
  # Create a list of the groups which the user should not be in.
  notin = [name for name in allgroupnames if name not in activegroupnames]

  # Sync user model groups.
  user.groups.add(*Group.objects.filter(name__in=activegroupnames))
  user.groups.remove(*Group.objects.filter(name__in=notin))

  return
