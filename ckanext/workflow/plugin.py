import ckan.authz as authz
import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging
import ckan.logic as logic

from ckan.common import config
from ckanext.workflow import helpers
from ckanext.workflow.logic import actions
from ckan.lib.plugins import DefaultOrganizationForm

#from ckanext.hierarchy import helpers as heirarchy_helpers

log1 = logging.getLogger(__name__)

def organization_create(context, data_dict=None):
    user = toolkit.c.userobj
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


class WorkflowPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IPackageController)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)

    # IAuthFunctions
    def get_auth_functions(self):
        return {
            'organization_create': organization_create,
        }

    # IActions
    def get_actions(self):
        return {
            # Override CKAN's core `package_search` method
            'package_search': actions.datavic_package_search
        }

    # IPackageController
    def read(self, entity):
        # log1.debug('*** IPackageController -- read -- ID: %s | Name: %s ***', entity.id, entity.name)
        return entity

    def create(self, entity):
        # DATAVIC-56: "Each dataset is initially created in a 'Draft' status"
        entity.extras['workflow_status'] = 'draft'
        return entity

    def edit(context, entity):
        user = toolkit.c.userobj
        role = helpers.role_in_org(entity.owner_org, user.name)

        # Dataset is Private until workflow_status becomes "published"
        entity.private = True

        # Sysadmin can do whatever they like..
        if not authz.is_sysadmin(user.name):
            # Get the existing dataset to compare workflow_status
            dataset = model.Package.get(entity.id)
            current_workflow_status = dataset.extras['workflow_status']

            # Validate the workflow_status in context of the user's role
            workflow_status = entity.extras['workflow_status']

            # TODO: Refactor these workflows into the .json settings file if possible.
            if role == 'editor':
                # editor can do the following:
                # draft > needs_review
                # needs_review > draft
                # published > draft
                # published > archived
                # archived > draft
                if current_workflow_status == 'published' and workflow_status != 'archived':
                    workflow_status = 'draft'
                elif current_workflow_status == 'draft' and workflow_status != 'draft':
                    workflow_status = 'needs_review'
                elif current_workflow_status == 'needs_review' and workflow_status != 'needs_review':
                    workflow_status = 'draft'
                elif current_workflow_status == 'archived' and workflow_status != 'draft':
                    workflow_status = 'draft'
            elif role == 'admin':
                # admin can do the following:
                # draft > needs_review
                # needs_review > published
                # needs_review > draft
                # published > draft
                # published > archived
                # archived > draft
                if not current_workflow_status == workflow_status:
                    if current_workflow_status == 'draft' and workflow_status != 'draft':
                        workflow_status = 'needs_review'
                    elif current_workflow_status == 'needs_review' and workflow_status != 'published':
                        workflow_status = 'draft'
                    elif current_workflow_status == 'published' and workflow_status != 'archived':
                        workflow_status = 'draft'
                    elif current_workflow_status == 'archived' and workflow_status != 'draft':
                        workflow_status = 'draft'

            # Assign the adjusted workflow_status back to the entity
            entity.extras['workflow_status'] = workflow_status

        if entity.extras['workflow_status'] == 'published':
            # Super Admins can publish datasets
            # The only other user that can publish datasets are admins of the organization
            if authz.is_sysadmin(user.name) or role == "admin":
                entity.private = False

        return entity

    def delete(self, entity):
        return entity

    def after_create(self, context, pkg_dict):
        return pkg_dict

    def after_update(self, context, pkg_dict):
        return pkg_dict

    def after_show(self, context, pkg_dict):
        return pkg_dict

    def before_search(self, search_params):
        log1.debug("*** IPackageController -- before_search ***\n*** controller: %s | action: %s ***", \
                   toolkit.c.controller, toolkit.c.action)

        if helpers.is_private_site_and_user_not_logged_in():
            search_params['abort_search'] = True
        else:
            search_params['include_private'] = True

        return search_params

    def after_search(self, search_results, search_params):
        return search_results

    def before_index(self, pkg_dict):
        return pkg_dict

    def before_view(self, pkg_dict):
        log1.debug('*** IPackageController -- before_view -- ID: %s | Name: %s *** | owner_org: %s', pkg_dict['id'], pkg_dict['name'], pkg_dict['owner_org'])
        if helpers.is_private_site_and_user_not_logged_in():
            toolkit.redirect_to('user_login')
        return pkg_dict


class DataVicHierarchyForm(plugins.SingletonPlugin, DefaultOrganizationForm):

    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IGroupForm, inherit=True)

    def is_sysadmin(self):
        user = toolkit.c.userobj
        if authz.is_sysadmin(user.name):
            return True

        return False

    def is_top_level_organization(self, id):
        group = model.Group.get(id)
        if group:
            parent = group.get_parent_group_hierarchy('organization')
            # This reads a bit funny - but we're checking if the organization has a parent or not
            if not parent:
                return True
        return False

    ## IConfigurer interface ##

    def update_config(self, config):
        ''' Setup the (fanstatic) resource library, public and template directory '''
        plugins.toolkit.add_template_directory(config, 'templates')
        plugins.toolkit.add_resource('fantastic', 'ckanext-workflow')

    ## ITemplateHelpers interface ##

    def get_helpers(self):
        return {
            'is_sysadmin': self.is_sysadmin,
            'is_top_level_organization': self.is_top_level_organization,
        }

    def group_types(self):
        return ('organization',)

    def group_controller(self):
        return 'organization'

    def setup_template_variables(self, context, data_dict):
        from pylons import tmpl_context as c

        #  DataVic - we filter these in context of logged in user
        user = toolkit.c.userobj

        c.allowable_parent_groups = user.get_groups('organization', 'admin')
