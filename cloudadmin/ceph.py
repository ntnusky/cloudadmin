""" Utility methods to aid the interaction with ceph rgw's

This module contains methods designed to aid the interaction with the ceph rados
gateways. The ceph rgw's are responsible for our swift and S3 api's.
"""

from rgwadmin import RGWAdmin
from rgwadmin.exceptions import NoSuchUser

from cloudadmin.utils import humanReadable
from cloudadmin.settings import parser

def getRGWConnection():
  """ Creates a connection-object to ceph-rgw

  This method collects keys and endpoint from the configuration-file and creates
  a RGWAdmin connection-object which can be used to interact with the ceph RGW.

  Returns:
    A RGWAdmin object
  """

  connection = RGWAdmin(
    access_key = parser.get('ceph-admin', 'access_key'),
    secret_key = parser.get('ceph-admin', 'secret_key'),
    server = parser.get('ceph-admin', 'server'), 
  ) 

  return connection

def getRGWUserQuota(uid):
  """ Retrieves a certain user's quota from the ceph rgw's

  This method queries the ceph RGW for a certain users quota. Human-readable
  values of the quota is also generated.

  Args:
    uid: A string representing the ceph userid.

  Returns:
    A dict containing the users quota-information.
  """

  quota = {}
  rgw = getRGWConnection()

  try:
    quota['bucket'] = rgw.get_quota(uid, quota_type = 'bucket')
    quota['user']   = rgw.get_quota(uid, quota_type = 'user')
    quota['in_use'] = True
  except NoSuchUser:
    quota['in_use'] = False
    return quota
  
  for qtype in ['bucket', 'user']:
    for value in ['max_size', 'max_objects']:
      if(quota[qtype][value] < 0):
        quota[qtype]['%s_human' % value] = "Undefined"
      else:
        quota[qtype]['%s_human' % value] = humanReadable(quota[qtype][value])

    if(quota[qtype]['max_size'] >= 0):
      quota[qtype]['max_size_gb'] = quota[qtype]['max_size'] / (1024**3)
    else:
      quota[qtype]['max_size_gb'] = 0 

    if(quota[qtype]['max_objects'] < 0):
      quota[qtype]['max_objects'] = 0 

  return quota

def getRGWUserUsage(uid):
  """ Retrieves a certain user's usage from the ceph rgw's

  This method queries the ceph RGW for a certain users usage. Human-readable
  values of the usage, and the utilization of the quota is also generated.

  Args:
    uid: A string representing the ceph userid.

  Returns:
    A dict containing the users usage-information.
  """

  usage = {'bytes': 0, 'objects': 0}
  rgw = getRGWConnection()

  for bucket in rgw.get_bucket(uid=uid, stats=True):
    for gw in bucket['usage']:
      usage['bytes'] += bucket['usage'][gw]['size']
      usage['objects'] += bucket['usage'][gw]['num_objects']

  usage['bytes_human'] = "%sB" % humanReadable(usage['bytes'])
  usage['objects_human'] = humanReadable(usage['objects'])

  try:
    quota = rgw.get_quota(uid, quota_type = 'user')
  except:
    quota = {'enabled': False}

  if(quota['enabled']):
    try:
      usage['bytes_percent'] = int(usage['bytes'] * 100 / quota['max_size'])
      usage['objects_percent'] = int(usage['objects'] * 100 / quota['max_objects'])
    except ZeroDivisionError:
      usage['bytes_percent'] = 100
      usage['objects_percent'] = 100
  else:
    usage['bytes_percent'] = 0
    usage['objects_percent'] = 0

  return usage
