import ckan.plugins.toolkit as toolkit

from ckan.lib.base import _
from ckan.logic.auth import get_package_object
from ckan.lib.plugins import get_permission_labels
from ckanext.workflow import helpers


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
