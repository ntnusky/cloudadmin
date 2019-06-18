from re import match

from django.core.management.base import BaseCommand

from cloudadmin.openstack import getOpenstackConnection
from cloudadmin.openstack import getOpenstackProject
from cloudadmin.models import Project, QuotaInformation

class Command(BaseCommand):
  def handle(self, *args, **options):
    c = getOpenstackConnection()

    for project in c.identity.projects():
      for tag in project.tags:
        m = match(r'^CloudAdminProject=([0-9]+)$', tag)
        if m:
          # Try to update the quotas for the cloudadmin-project.
          try:
            caproject = Project.objects.get(pk=int(m.group(1)))
            osproject = getOpenstackProject(c, project.id)
            osuse = QuotaInformation()
            osuse.fromDict(osproject['quota'])
            caproject.removeUsage(osuse)
          except:
            pass

          # Remove the cloudadmin tag from the project.
          project.remove_tag(c.identity, tag)
