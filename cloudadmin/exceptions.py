""" Custom exceptions for cloudadmin """

class InsufficientQuotaException(Exception):
  """ An Exception raised if a quota is too small

  This Exception is raised if a user performs a request which would increase the
  users resource-usage to a level above its quotas.
  """

  pass

class UsageTooHighException(Exception):
  """ An Exception raised if a usage is too large

  This Exception is raised if a user performs a request which would decrease the
  quotas to a level belov the current usage
  """

  pass
