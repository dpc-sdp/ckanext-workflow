# This file contains some helper methods for use in the "Workflow" CKAN extension

import ckan.authz as authz
import json
from ckan.common import config

#
def load_workflow_settings():
    '''
    Load some config info from a json file

    CACHING of Org structure:
    https://docs.pylonsproject.org/projects/pylons-webframework/en/latest/caching.html

    @cache_region('short_term', 'search_func')
    def get_results(search_param):
        # do something to retrieve data
        data = get_data(search_param)
        return data

    results = get_results('gophers')
    '''
    path = config.get('ckan.workflow.json_config', '/usr/lib/ckan/default/src/ckanext-workflow/ckanext/workflow/settings.json')
    with open(path) as json_data:
        d = json.load(json_data)
        return d

def role_in_org(owner_org, user_name):
    return authz.users_role_for_group_or_org(owner_org, user_name)

def get_workflow_status_options(workflows, current_workflow_status):
    if current_workflow_status in workflows:
        return workflows[current_workflow_status]
    return workflows['draft']

def get_workflow_status_options_for_role(roles, role):
    if role in roles:
        return roles[role]['workflow_status_options']
    return ['draft']

# Workflow Status options are dictated by the current workflow status of
# a package, and the role of the user performing the action
def get_available_workflow_statuses(current_workflow_status, owner_org, user):
    settings = load_workflow_settings()
    role = role_in_org(owner_org, user)

    workflow_options = get_workflow_status_options(settings['workflows'], current_workflow_status)
    user_workflow_options = get_workflow_status_options_for_role(settings['roles'], role)

    return list(set(workflow_options).intersection(user_workflow_options))
