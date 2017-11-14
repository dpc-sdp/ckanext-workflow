import ckan.authz as authz
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging
import ckan.logic as logic

from inspect import getmembers
from pprint import pprint
from ckan.common import config

# Try importing the helpers from ckanext-hierarchy
#from ckanext.hierarchy import helpers

# Not needed - using toolkit.c
#from ckan.common import c
import ckan.model as model

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
        log1.debug('*** IPackageController -- read -- ID: %s | Name: %s ***', entity.id, entity.name)
        return entity

    def create(self, entity):
        #log1.debug('*** IPackageController: `create` ***')
        entity.extras['workflow_status'] = 'draft';
        return entity

    def edit(context, entity):
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
        log1.debug('*** IPackageController -- before_search ***')


        return search_params

        # Check the config for `internal_protected_site_read`
        private_site = config.get('ckan.victheme.internal_protected_site_read', True)

        if (private_site != True):
            return search_params

        # Assuming this is a private site -- all rules apply

        # Check that the user is logged in..
        if (authz.auth_is_loggedin_user() != True):
            log1.debug('*** NOT a logged in User ***')
            search_params['fq'] = '+workflow_status:(impossible) ' + search_params['fq']
        else:
            log1.debug('*** User IS logged in ***')

            user = toolkit.c.userobj

            # group types are: organization & group
            user_organizations = user.get_groups('organization')

            for organization in user_organizations:
                # group = model.Group.get(organization.id)


                for parent in organization.get_parent_groups('organization'):
                    str_parents += "\n" + parent.id + " | " + parent.name

            # if authz.is_sysadmin(user.name) and (search_params.get('include_drafts', None) is None):
            if authz.is_sysadmin(user.name):
                search_params['include_drafts'] = True
            #else:
                #search_params['fq'] = '+extract:(published OR needs_review workflow_drxft) ' + search_params['fq']
                # search_params['fq'] = '+workflow_status:(published OR draft) ' + search_params['fq']
                #search_params['fq'] = '+(owner_org:(d0346b02-dadf-421c-95fc-980397224575)) ' + search_params['fq']
             #   search_params['fq'] = ' OR (owner_org:"d0346b02-dadf-421c-95fc-980397224575") ' + search_params['fq']

            # orgs = logic.get_action('organization_list_for_user')(
            #     {'user': user.name}, {'permission': 'read'})

            # #role = authz.users_role_for_group_or_org(pkg_dict['owner_org'], user.name)

            # search_params['fq'] = '+extract:(published OR workflow_drxft) ' + search_params['fq']

        log1.debug('*** search_params: ***')
        pprint(search_params)

        return search_params

    def after_search(self, search_results, search_params):
        return search_results

    def before_index(self, pkg_dict):
        return pkg_dict

    def before_view(self, pkg_dict):
        log1.debug('*** IPackageController -- before_view -- ID: %s | Name: %s ***', pkg_dict['id'], pkg_dict['name'])
        return pkg_dict