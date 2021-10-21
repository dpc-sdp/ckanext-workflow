import ckan.authz as authz
import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging

from ckanext.workflow import helpers
from ckan.lib.plugins import DefaultOrganizationForm

log = logging.getLogger(__name__)


class DataVicHierarchyForm(plugins.SingletonPlugin, DefaultOrganizationForm):

    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IGroupForm, inherit=True)

    ## IConfigurer interface ##

    def update_config(self, config):
        ''' Setup the (fanstatic) resource library, public and template directory '''
        toolkit.add_template_directory(config, 'templates_hierarchy_form')
        toolkit.add_resource('webassets', 'ckanext-hierarchy-form')

    ## ITemplateHelpers interface ##

    def get_helpers(self):
        return {
            'is_sysadmin': helpers.is_sysadmin,
            'is_top_level_organization': helpers.is_top_level_organization,
            'is_workflow_enabled': helpers.is_workflow_enabled,
            'show_top_level_option': helpers.show_top_level_option,
        }

    def group_types(self):
        return ('organization',)

    def group_controller(self):
        return 'organization'

    def setup_template_variables(self, context, data_dict):
        #from pylons import tmpl_context as c

        #  DataVic - we filter these in context of logged in user
        user = toolkit.g.userobj

        if authz.is_sysadmin(user.name):
            toolkit.g.allowable_parent_groups = model.Group.all(
                group_type='organization')
        else:
            group_id = data_dict.get('id')
            if group_id:
                group = model.Group.get(group_id)
                toolkit.g.allowable_parent_groups = \
                    group.groups_allowed_to_be_its_parent(type='organization')
            else:
                context = {'user': toolkit.g.user}
                data_dict = {'permission': None}
                toolkit.g.allowable_parent_groups = toolkit.get_action('organization_list_for_user')(context, data_dict)
