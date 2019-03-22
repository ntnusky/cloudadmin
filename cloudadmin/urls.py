from django.conf.urls import include, url

from cloudadmin.views import main

urlpatterns = [
  url(r'^$', main.index, name="index"),
  url(r'^login/$', main.loginPage, name="login"),
  url(r'^logout/$', main.logoutPage, name="logout"),
  url(r'^debug/$', main.debug, name="debug"),

  #url(r'^host/', include('host.urls')),
]
