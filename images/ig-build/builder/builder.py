import logging
import os
import random
import requests
import shutil
import string
import subprocess
import sys

from .util  import make_temp_dir, do, send_zulip
from os.path import normpath

GITHUB = 'https://github.com/%(org)s/%(repo)s'
HOSTED_ROOT = os.environ.get('HOSTED_ROOT', 'http://build.fhir.org/ig')

def get_qa_score(build_dir):
  qa_file = os.path.join(build_dir, 'qa.html')
  try:
    with open(qa_file, 'r') as f:
      f.readline()
      f.readline()
      report_line = f.readline()
    return report_line.split("--")[1].strip()
  except:
    return "No QA File"


def build(config):
  temp_dir = make_temp_dir()
  clone_dir = os.path.join(temp_dir, 'repo')
  build_dir = os.path.join(clone_dir, 'output')
  logfile = os.path.join(temp_dir, 'build.log')
  logging.basicConfig(filename=logfile, level=logging.DEBUG)
  logging.info('about to clone!')
  do(['git', 'clone', '--recursive', GITHUB%config, 'repo'], temp_dir)
  do(['wget', '-q', 'http://build.fhir.org/org.hl7.fhir.igpublisher.jar',
        '-O', 'publisher.jar'], temp_dir)

  details = {
    'root': HOSTED_ROOT,
    'org': config['org'],
    'repo': config['repo'],
    'commit': subprocess.check_output(['git', 'log', '-1', '--pretty=%B (%an)'], cwd=clone_dir).strip()
  }

  java_memory = os.environ.get('JAVA_MEMORY', '2g')

  built_exit = do(['java',
         '-Xms%s'%java_memory, '-Xmx%s'%java_memory,
         '-jar', '../publisher.jar',
         '-ig', 'ig.json',
         '-auto-ig-build',
         '-target', 'https://build.fhir.org/ig/%s/%s/'%(details['org'], details['repo']),
         '-out', clone_dir], clone_dir)
  built = (0 == built_exit)
  print built, built_exit

  message = ["**[%(org)s/%(repo)s](https://github.com/%(org)s/%(repo)s)** rebuilt\n",
             "Commit: %(commit)s :%(emoji)s:\n",
             "Details: [build logs](%(root)s/%(org)s/%(repo)s/%(buildlog)s)"]

  if not built:
    print "Build error occurred"
    details['emoji'] = 'thumbs_down'
    details['buildlog'] = 'build.log'
    message += [" | [debug](%(root)s/%(org)s/%(repo)s)"]
    shutil.copy(logfile, clone_dir)
    do(['publish', details['org'], details['repo']], clone_dir, pipe=True)
  else:
    print "Build succeeded"
    details['emoji'] = 'thumbs_up'
    details['buildlog'] = 'build.log'
    message += [" | [published](%(root)s/%(org)s/%(repo)s/index.html)"]
    message += [" | [qa: %s]"%get_qa_score(build_dir), "(%(root)s/%(org)s/%(repo)s/qa.html)"]
    print "Copying logfile"
    shutil.copy(logfile, build_dir)
    print "publishing"
    do(['publish', details['org'], details['repo']], build_dir, pipe=True)
    print "published"

  shutil.rmtree(temp_dir)
  print "cleaned up"
  send_zulip('committers', 'ig-build', "".join(message)%details)
  # sys.exit(0 if built else 1)

if __name__ == '__main__':
  build({
    'org': os.environ.get('IG_ORG', 'test-igs'),
    'repo': os.environ.get('IG_REPO', 'simple'),
  })
