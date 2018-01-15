# This file contains some helper methods for use in the "Workflow" CKAN extension

import ckan.authz as authz
import ckan.logic as logic
import ckan.model as model
import ckan.plugins.toolkit as toolkit
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


def apply_editor_workflow_status_rules(current_workflow_status, workflow_status):
    # editor can do the following:
    # draft > ready_for_approval
    # ready_for_approval > draft
    # published > draft
    # published > archived
    # archived > draft
    if current_workflow_status == 'published' and workflow_status != 'archived':
        workflow_status = 'draft'
    elif current_workflow_status == 'draft' and workflow_status != 'draft':
        workflow_status = 'ready_for_approval'
    elif current_workflow_status == 'ready_for_approval' and workflow_status != 'ready_for_approval':
        workflow_status = 'draft'
    elif current_workflow_status == 'archived' and workflow_status != 'draft':
        workflow_status = 'draft'

    return workflow_status


def apply_admin_workflow_status_rules(current_workflow_status, workflow_status):
    # admin can do the following:
    # draft > ready_for_approval
    # ready_for_approval > published
    # ready_for_approval > draft
    # published > draft
    # published > archived
    # archived > draft
    if not current_workflow_status == workflow_status:
        if current_workflow_status == 'draft' and workflow_status != 'draft':
            workflow_status = 'ready_for_approval'
        elif current_workflow_status == 'ready_for_approval' and workflow_status != 'published':
            workflow_status = 'draft'
        elif current_workflow_status == 'published' and workflow_status != 'archived':
            workflow_status = 'draft'
        elif current_workflow_status == 'archived' and workflow_status != 'draft':
            workflow_status = 'draft'

    return workflow_status


def get_workflow_status_for_role(current_workflow_status, workflow_status, user_name, owner_org_id):
    user = toolkit.c.userobj
    role = role_in_org(owner_org_id, user.name)

    # Sysadmin can do whatever they like..
    if not authz.is_sysadmin(user.name):
        # Validate the workflow_status in context of the user's role
        if role == 'editor':
            workflow_status = apply_editor_workflow_status_rules(current_workflow_status, workflow_status)
        elif role == 'admin':
            workflow_status = apply_admin_workflow_status_rules(current_workflow_status, workflow_status)
        else:
            workflow_status = 'draft'

    return workflow_status


def get_member_list(context, data_dict=None):
    '''This is a copy of the function `logic.action.get.member_list` - with the _check_access call removed for DATAVIC-55

    :param id: the id or name of the group
    :type id: string
    :param object_type: restrict the members returned to those of a given type,
      e.g. ``'user'`` or ``'package'`` (optional, default: ``None``)
    :type object_type: string
    :param capacity: restrict the members returned to those with a given
      capacity, e.g. ``'member'``, ``'editor'``, ``'admin'``, ``'public'``,
      ``'private'`` (optional, default: ``None``)
    :type capacity: string

    :rtype: list of (id, type, capacity) tuples

    :raises: :class:`ckan.logic.NotFound`: if the group doesn't exist

    '''
    model = context['model']

    group = model.Group.get(logic.get_or_bust(data_dict, 'id'))
    if not group:
        raise NotFound

    obj_type = data_dict.get('object_type', None)
    capacity = data_dict.get('capacity', None)

    # User must be able to update the group to remove a member from it
    # DATAVIC-55: Do not check access because it will fail under the default permissions for users with `editor` role
    #logic.check_access('group_show', context, data_dict)

    q = model.Session.query(model.Member).\
        filter(model.Member.group_id == group.id).\
        filter(model.Member.state == "active")

    if obj_type:
        q = q.filter(model.Member.table_name == obj_type)
    if capacity:
        q = q.filter(model.Member.capacity == capacity)

    trans = authz.roles_trans()

    def translated_capacity(capacity):
        try:
            return trans[capacity]
        except KeyError:
            return capacity

    return [(m.table_id, m.table_name, translated_capacity(m.capacity))
            for m in q.all()]


def get_admin_users_for_org(owner_org):
    '''

    :param owner_org:
    :return: A list of admin user details (name & email) for the supplied group ID
    '''
    admin_users = []

    member_list = get_member_list(
        {'model': model},
        {
            'id': owner_org,
            'object_type': 'user',
            'capacity': 'admin'
        })

    for member in member_list:
        user = model.User.get(member[0])
        if user:
            admin_users.append(user.email)

    return admin_users


def load_notification_template(template):
    import os

    path = os.path.dirname(os.path.realpath(__file__)) + template

    try:
        fp = open(path, 'rb')
        notification_template = fp.read()
        fp.close()

        return notification_template
    except IOError as error:
        log1.error(error)
        raise


def send_notification_email(to, subject, msg):
    import smtplib
    from email.mime.text import MIMEText

    me = config.get('smtp.mail_from')

    # Create the container (outer) email message.
    msg = MIMEText(msg, 'plain')

    msg['To'] = to
    msg['From'] = me
    msg['Subject'] = subject

    # Send the email via our own SMTP server.
    s = smtplib.SMTP('localhost')
    s.sendmail(me, to, msg.as_string())
    s.quit()


def get_package_edit_url(package_name):
    from ckan.common import config
    return config.get('ckan.site_url', None) + toolkit.url_for(
        controller='package',
        action='edit',
        id=package_name
    )


def mail_merge(msg, dict):

    if 'organization' in dict:
        msg = msg.replace('[[ORGANIZATION]]', dict['organization'])

    if 'user' in dict:
        msg = msg.replace('[[USER]]', dict['user'])

    if 'url' in dict:
        msg = msg.replace('[[URL]]', dict['url'])

    if 'email' in dict:
        msg = msg.replace('[[EMAIL]]', dict['email'])

    if 'name' in dict:
        msg = msg.replace('[[NAME]]', dict['name'])

    if 'notes' in dict and dict['notes'] is not None:
        msg = msg.replace('[[NOTES]]', '\nThe reviewer added the following notes:\n\n' + dict['notes'] + '\n')
    else:
        msg = msg.replace('[[NOTES]]', '')

    return msg


def notify_admin_users(owner_org, user_name, package_name):
    admin_users = get_admin_users_for_org(owner_org)

    if admin_users:
        org = model.Group.get(owner_org)

        msg = load_notification_template('/templates/email/notification-admin.txt')

        msg = mail_merge(msg, {
            'organization': org.name,
            'user': user_name,
            'url': get_package_edit_url(package_name)
        })

        for user in admin_users:
            send_notification_email(
                user,
                "Workflow status change",
                msg
            )


def notify_creator(package_name, creator_user_id, notes=None):
    user = logic.action.get.user_show({'model': model}, {'id': creator_user_id})

    if user:
        msg = load_notification_template('/templates/email/notification-creator.txt')

        send_notification_email(
            user['email'],
            'Dataset workflow changed to Draft',
            mail_merge(
                msg,
                {
                    'name': user['name'],
                    'email': user['email'],
                    'url': get_package_edit_url(package_name),
                    'notes': notes
                }))
    return
