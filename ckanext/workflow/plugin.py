import ckan
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

        if entity.extras['workflow_status'] == 'published':
            # Super Admins can publish datasets
            # The only other user that can publish datasets are admins of the organization
            if authz.is_sysadmin(user.name) or role == "admin":
                entity.private = False

        # DATAVIC-55    Dataset approval reminders
        to_revision = entity.latest_related_revision
        # TODO: make sure there is a previous revision
        from_revision = entity.all_related_revisions[1][0]

        diff = entity.diff(to_revision, from_revision)

        if 'PackageExtra-workflow_status-value' in diff:
            change = diff['PackageExtra-workflow_status-value'].split('\n')

            # If workflow_status changes from draft to ready_for_approval..
            if 'draft' in change[0] and 'ready_for_approval' in change[1]:
                helpers.notify_admin_users(
                    entity.owner_org,
                    user.name,
                    entity.name
                )
            # Else, if workflow_status changes from ready_for_approval back to draft..
            elif 'ready_for_approval' in change[0] and 'draft' in change[1]:
                helpers.notify_creator(
                    entity.name,
                    entity.creator_user_id,
                    entity.extras.get('workflow_status_notes', None)
                )

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