from django.conf.urls import include, url

from cloudadmin.views import main, parts
from cloudadmin.endpoints import auth, group, openstack, project, quota

webapp = [
  url(r'^$',                  main.overview,       name='web.overview'),
  url(r'^administrative/$',   main.administrative, name='web.administrative'),

  url(r'^debug/$',            main.debug,          name='web.debug'),
  url(r'^login/$',            main.loginPage,      name='web.login'),
  url(r'^logout/$',           main.logoutPage,     name='web.logout'),

  url(r'^openstack/$',                    main.openstack, name='web.openstack'),
  url(r'^openstack/([0-9a-z]{32})/$',     main.openstackproject, 
      name='web.openstack.project'),
  url(r'^openstack/([0-9a-z]{32})/info$', parts.openstackprojectinfo, 
      name='web.openstack.projectinfo'),
]

api_v1_openstack = [
  url(r'^$',                  openstack.index,  name='api.v1.openstack'),
  url(r'^([0-9a-z]{32})/$',   openstack.single, name='api.v1.openstack.single'),
  url(r'^([0-9a-z]{32})/assignments$', openstack.assignments),
]

api_v1 = [
  url(r'^auth/$',             auth.auth,      name='api.v1.auth'),
  url(r'^deauth/$',           auth.deauth,    name='api.v1.deauth'),
  url(r'^group/$',            group.list,     name='api.v1.group'),
  url(r'^project/$',          project.index,  name='api.v1.project'),
  url(r'^project/([0-9]+)/$', project.single),
  url(r'^openstack/project/', include(api_v1_openstack)),
  url(r'^quota/$',            quota.index,    name='api.v1.quota'),
  url(r'^quota/([0-9]+)/$',   quota.single),
]

urlpatterns = [
  url(r'^$',       main.index,       name='web.index'),
  url(r'^web/',    include(webapp)),
  url(r'^api/v1/', include(api_v1)),
]
