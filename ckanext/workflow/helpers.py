# This file contains some helper methods for use in the "Workflow" CKAN extension

import ckan.authz as authz
import ckan.model as model
import json
import logging
from ckan.common import config

log1 = logging.getLogger(__name__)


def is_private_site_and_user_not_logged_in():
    private_site = config.get('ckan.victheme.internal_protected_site_read', True)
    if private_site and not authz.auth_is_loggedin_user():
        return True
    return False

#
def load_workflow_settings():
    '''
    Load some config info from a json file
    '''
    path = config.get('ckan.workflow.json_config', '/usr/lib/ckan/default/src/ckanext-workflow/ckanext/workflow/example.settings.json')
    with open(path) as json_data:
        d = json.load(json_data)
        return d


def role_in_org(organization_id, user_name):
    return authz.users_role_for_group_or_org(organization_id, user_name)


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

    # SysAdmin users may not have a role in the organisation, so we don't need to filter their workflow status options
    if authz.is_sysadmin(user):
        return list(workflow_options)

    user_workflow_options = get_workflow_status_options_for_role(settings['roles'], role)

    return list(set(workflow_options).intersection(user_workflow_options))


def get_organization_id(data_dict, fq):
    organization_id = None
    if 'owner_org:' in fq:
        owner_org = ' '.join(p for p in fq.split() if 'owner_org:' in p)
        organization_id = owner_org.split(':')[1].replace('"', '')
    else:
        # Unable to determine Organization ID (this should not occur, but needs to be trapped)
        import sys
        sys.exit(['Unable to determine Organization ID', data_dict])

    return organization_id

def get_user_organizations(username):
    user = model.User.get(username)
    return user.get_groups('organization')


def is_user_in_parent_organization(organization, user_organizations):
    log1.debug("*** CHECKING: PARENTS...")
    parents = organization.get_parent_groups('organization')

    return find_match_in_list(parents, user_organizations)


def is_user_in_child_organization(organization, user_organizations):
    log1.debug("*** CHECKING: CHILDREN...")
    children = organization.get_children_groups('organization')
    return find_match_in_list(children, user_organizations)


def is_user_in_family_organization(organization, user_organizations):
    log1.debug("*** CHECKING: FAMILY...")
    ancestors = organization.get_parent_group_hierarchy('organization')
    if find_match_in_list(ancestors, user_organizations):
        return True
    else:
        descendants = organization.get_children_group_hierarchy('organization')
        if find_match_in_list(descendants, user_organizations):
            return True
    return False


def find_match_in_list(list_1, list_2):
    for list_1_item in list_1:
        log1.debug("Checking: %s | %s", list_1_item.id, list_1_item.name)
        for list_2_item in list_2:
            if list_2_item.id == list_1_item.id:
                log1.debug("Match found: %s | %s", list_2_item.id, list_2_item.name)
                return True
    return False


def get_organization_relationships_for_user(organization, user_organizations):
    relationships = []

    # PARENT
    if is_user_in_parent_organization(organization, user_organizations):
        relationships.append('parent')

    # CHILDREN
    if is_user_in_child_organization(organization, user_organizations):
        relationships.append('child')

    # FAMILY
    if is_user_in_family_organization(organization, user_organizations):
        relationships.append('family')

    return relationships


def big_separator(output=False):
    str = "= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = ="
    return separator(output, str)

def separator(output=False, str=None):
    if str is None:
        str = '- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -'
    if output:
        print("\n" + str + "\n")
    return str
