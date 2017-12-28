import ckan.authz as authz
import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging
import ckan.logic as logic

from ckan.common import config
from ckanext.workflow import helpers
from ckanext.workflow.logic import actions

log1 = logging.getLogger(__name__)

class WorkflowPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IPackageController)
    plugins.implements(plugins.IActions)

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
            elif role == 'admin':
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