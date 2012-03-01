# coding: utf-8

# This Source Code is subject to the terms of the Mozilla Public License
# version 2.0 (the "License"). You can obtain a copy of the License at
# http://mozilla.org/MPL/2.0/.

import MySQLdb, hashlib, sys, os, re
from time import time
from email.utils import parseaddr
from sitescripts.utils import get_config, get_template, setupStderr
from sitescripts.reports.utils import getReports, getReportSubscriptions, calculateReportSecret, getDigestPath
import sitescripts.subscriptions.subscriptionParser as subscriptionParser

def updateDigests(dir):
  global currentTime
  
  subs = subscriptionParser.readSubscriptions()
  defname, defemail = parseaddr(get_config().get('reports', 'defaultSubscriptionRecipient'))

  subscriptions = {}
  emails = {}
  emails[defemail] = []
  for subscription in subs.values():
    for title, url, complete in subscription.variants:
      subscriptions[url] = subscription
    name, email = parseaddr(subscription.email)
    if email != '':
      emails[email] = []
      
  startTime = currentTime - get_config().getint('reports', 'digestDays') * 24*60*60
  for dbreport in getReports(startTime):
    report = {
      'guid': dbreport['guid'],
      'status': dbreport['status'],
      'url': get_config().get('reports', 'urlRoot') + dbreport['guid'] + '#secret=' + calculateReportSecret(dbreport['guid']),
      'site': dbreport['site'],
      'comment': dbreport['comment'],
      'type': dbreport['type'],
      'subscriptions': [],
      'contact': dbreport['contact'],
      'hasscreenshot': dbreport['hasscreenshot'],
      'knownIssues': dbreport['knownissues'],
      'time': dbreport['ctime'],
    }

    recipients = set()
    reportSubscriptions = getReportSubscriptions(dbreport['guid'])

    if dbreport['type'] == 'false positive' or dbreport['type'] == 'false negative':
      for subscription in reportSubscriptions:
        subscriptionID = subscription.get('url', 'unknown')
        # Send false negatives to all subscription authors, false positives
        # only to subscriptions with matching filters
        if subscriptionID in subscriptions and (dbreport['type'] == 'false negative' or subscription.get('hasmatches', 0) > 0):
          name, email = parseaddr(subscriptions[subscriptionID].email)
          if email and not email in recipients:
            recipients.add(email)
            emails[email].append(report)
          report['subscriptions'].append(getSubscriptionInfo(subscriptions[subscriptionID]))
    else:
      for subscription in reportSubscriptions:
        subscriptionID = subscription.get('url', 'unknown')
        report['subscriptions'].append(getSubscriptionInfo(subscriptions[subscriptionID]))
      recipients.add(defemail)
      emails[defemail].append(report)
      
  # Generate new digests
  digests = set()
  for email, reports in emails.iteritems():
    if len(reports) == 0:
      continue
    file = getDigestPath(dir, email)
    template = get_template(get_config().get('reports', 'htmlDigestTemplate'))
    template.stream({'email': email, 'reports': reports}).dump(file, encoding='utf-8')
    digests.add(file)
  
  # Remove not updated digests which are more then 2 weeks old
  for filename in os.listdir(dir):
    file = os.path.join(dir, filename)
    if os.path.isfile(file) and file not in digests and re.match(r'^[\da-f]{32}\.html$', filename) and os.stat(file).st_mtime < currentTime - 14*24*60*60:
      os.remove(file)

def getSubscriptionInfo(subscription):
  sub = {
    'name': subscription.name,
    'type': subscription.type
  }
  return sub

if __name__ == '__main__':
  setupStderr()
  currentTime = time()
  updateDigests(get_config().get('reports', 'digestPath'))