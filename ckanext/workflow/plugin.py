import ckan.authz as authz
import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging

from ckan.common import config
from ckanext.workflow.logic import actions
from ckanext.workflow.logic import auth
from ckanext.workflow import helpers
from ckan.lib.plugins import DefaultOrganizationForm

log1 = logging.getLogger(__name__)



class WorkflowPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)

    # IAuthFunctions
    def get_auth_functions(self):
        return {
            'organization_create': actions.organization_create,
            # 'organization_update': actions.organization_update,
            'package_show': auth.iar_package_show,
        }

    # IActions
    def get_actions(self):
        return {
            # Override CKAN's core `package_search` method
            'package_search': actions.datavic_package_search
        }

    # IPackageController

    def create(self, entity):
        # DATAVIC-56: "Each dataset is initially created in a 'Draft' status"
        if toolkit.g.controller in ['package', 'dataset']:
            entity.extras['workflow_status'] = 'draft'
        # Harvester created datasets
        else:
            self.set_harvested_dataset_workflow_properties(entity)

        return entity

    def edit(self, entity):

        # Datasets updated through the UI need to be handled differently that those updated via the Harvester
        if toolkit.g.controller in ['package', 'dataset']:
            user = toolkit.g.userobj
            role = helpers.role_in_org(entity.owner_org, user.name)

            workflow_status = entity.extras.get('workflow_status', None)
            organization_visibility = entity.extras.get('organization_visibility', None)

            # DATAVIC-108: A dataset can only be set for Public Release (`private` = False)
            # if workflow status and
            # organization visibility are published and all, respectively
            if workflow_status == 'published' and organization_visibility == 'all':
                # Super Admins can publish datasets
                # The only other user that can publish datasets are admins of the organization
                if not authz.is_sysadmin(user.name) and not role == "admin":
                    entity.private = True
            else:
                # Dataset is Private until workflow_status becomes "published"
                entity.private = True

            # BEGIN: DATAVIC-251 CKAN 2.9 upgrade
            # BEGIN: DATAVIC-251 CKAN 2.9 upgrade
            from pprint import pprint

            activity_diffs = helpers.get_activity_diffs(entity.id)
            # Check if there are recoreded activities 
            if activity_diffs:
                # pprint(activity_diffs.get('activities')[0])
                previous_workflow_status = activity_diffs.get('data').get('package').get('workflow_status')

                if workflow_status != previous_workflow_status:
                    # If workflow_status changes from draft to ready_for_approval..
                    if previous_workflow_status == 'draft' and workflow_status == 'ready_for_approval':
                        helpers.notify_admin_users(
                            entity.owner_org,
                            user.name,
                            entity.name
                        )
                    # Else, if workflow_status changes from ready_for_approval back to draft..
                    elif previous_workflow_status == 'ready_for_approval' and workflow_status == 'draft':
                        if entity.workflow_status_notes:
                            workflow_status_notes = entity.workflow_status_notes
                        else:
                            workflow_status_notes = entity.extras.get('workflow_status_notes', None)

                        helpers.notify_creator(
                            entity.name,
                            entity.creator_user_id,
                            workflow_status_notes
                    )
        # Handle datasets updated through the Harvester differently
        else:
            self.set_harvested_dataset_workflow_properties(entity)

        return entity

    def before_search(self, search_params):
        if helpers.is_private_site_and_user_not_logged_in():
            search_params['abort_search'] = True
        else:
            search_params['include_private'] = True

        return search_params

    def before_view(self, pkg_dict):
        if helpers.is_private_site_and_user_not_logged_in():
            toolkit.redirect_to('user_login')
        return pkg_dict

    def set_harvested_dataset_workflow_properties(self, entity):
        workflow_status = entity.extras.get('workflow_status', None)
        organization_visibility = entity.extras.get('organization_visibility', None)

        if not workflow_status:
            if toolkit.asbool(entity.private) is True:
                entity.extras['workflow_status'] = 'draft'
            else:
                entity.extras['workflow_status'] = 'published'

        if not organization_visibility:
            if toolkit.asbool(entity.private) is True:
                entity.extras['organization_visibility'] = 'current'
            else:
                entity.extras['organization_visibility'] = 'all'


class DataVicHierarchyForm(plugins.SingletonPlugin, DefaultOrganizationForm):

    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IGroupForm, inherit=True)

    ## IConfigurer interface ##

    def update_config(self, config):
        ''' Setup the (fanstatic) resource library, public and template directory '''
        plugins.toolkit.add_template_directory(config, 'templates')
        plugins.toolkit.add_resource('webassets', 'workflow')

    ## ITemplateHelpers interface ##

    def get_helpers(self):
        return {
            'is_sysadmin': helpers.is_sysadmin,
            'is_top_level_organization': helpers.is_top_level_organization,
            'is_workflow_enabled': helpers.is_workflow_enabled,
        }

    def group_types(self):
        return ('organization',)

    def group_controller(self):
        return 'organization'

    def setup_template_variables(self, context, data_dict):
        #from pylons import tmpl_context as c

        #  DataVic - we filter these in context of logged in user
        user = toolkit.c.userobj

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
