import ckan.authz as authz
import ckan.plugins.toolkit as toolkit
import logging

from ckan.logic.auth import get_package_object
from ckan.lib.plugins import get_permission_labels
from ckanext.workflow import helpers

_ = toolkit._
log = logging.getLogger(__name__)


def iar_package_show(context, data_dict):
    user = context.get('user')
    package = get_package_object(context, data_dict)

    # DATAVIC: Apply organisation visibility rules if the dataset is marked private
    if toolkit.asbool(package.private) \
            and package.extras \
            and helpers.user_can_view_private_dataset(package, user):
        return {'success': True}

    # Otherwise: we can use the default rules.
    labels = get_permission_labels()
    user_labels = labels.get_user_dataset_labels(context['auth_user_obj'])
    authorized = any(
        dl in user_labels for dl in labels.get_dataset_labels(package))

    if not authorized:
        return {
            'success': False,
            'msg': _('User %s not authorized to read package %s') % (user, package.id)}
    else:
        return {'success': True}


def organization_create(context, data_dict=None):
    user = toolkit.g.userobj
    # Sysadmin can do anything
    if authz.is_sysadmin(user.name):
        return {'success': True}

    if not authz.auth_is_anon_user(context):
        orgs = helpers.get_user_organizations(user.name)
        for org in orgs:
            role = helpers.role_in_org(org.id, user.name)
            if role == 'admin':
                return {'success': True}

    return {'success': False, 'msg': 'Only user level admin or above can create an organisation.'}


def organization_update(context, data_dict=None):
    user = toolkit.g.userobj
    # Sysadmin can do anything
    if authz.is_sysadmin(user.name):
        return {'success': True}

    if not authz.auth_is_anon_user(context):

        if data_dict is not None and 'id' in data_dict:
            organization_id = data_dict['id']
        elif 'group' in context:
            organization_id = context['group'].id
        else:
            log.debug('Scenario not accounted for in ckanext-workflow > plugin.py')

        if organization_id:
            role = helpers.role_in_org(organization_id, user.name)
            if role == 'admin':
                return {'success': True}

    return {'success': False, 'msg': 'Only user level admin or above can update an organisation.'}
