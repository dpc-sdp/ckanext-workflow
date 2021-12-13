import ckan.authz as authz
import ckan.model as model
import logging
from ckan.common import config
from ckanext.workflow import helpers
from pprint import pprint

log1 = logging.getLogger(__name__)


def organization_read_filter_query(organization_id, username):
    log1.debug('*** PACKAGE_SEARCH | organization_read_filter_query | organization_id: %s ***' % organization_id)

    organization = model.Group.get(organization_id)

    rules = []

    # Return early if private site and non-logged in user..
    if helpers.is_private_site_and_user_not_logged_in():
        return ' ( {0} ) '.format(' OR '.join(rule for rule in rules))

    role = helpers.role_in_org(organization_id, username)

    if not role is None:
        log1.debug('*** User belongs to organization `%s` | role: %s - no further querying required ***', organization.name, role)
        user = model.User.get(username)
        # Of course the user can see any datasets they have created
        rules.append('(owner_org:"{0}" AND creator_user_id:{1})'.format(organization_id, user.id))
        # Admin can see unpublished datasets in organisations they are members of
        if role in ['admin', 'editor']:
            rules.append('(owner_org:"{0}")'.format(organization_id))
        else:
            # The user can see any published datasets in their own organisation
            rules.append('(capacity:public AND owner_org:"{0}")'.format(organization_id))
    else:
        user_organizations = helpers.get_user_organizations(username)
        relationships = helpers.get_organization_relationships_for_user(organization, user_organizations)
        if relationships:
            for relationship in relationships:
                rules.append('(owner_org:"{0}" AND organization_visibility:"{1}" AND workflow_status:"published")'.format(organization_id, relationship))

    rules = ' ( {0} ) '.format(' OR '.join(rule for rule in rules))
    # DEBUG:
    if config.get('debug', False):
        print(">>>>>>>>>>>>>>>>>>>>>>>>> organization_read_filter_query RULES: <<<<<<<<<<<<<<<<<<<<<<<<<<")
        pprint(rules)

    return rules


def package_search_filter_query(username):
    # Return early if private site and non-logged in user..
    if helpers.is_private_site_and_user_not_logged_in():
        return

    user = model.User.get(username)
    user_organizations = user.get_groups('organization')

    # All logged in users can see:
    # - any Published datasets with organization_visibility set to All
    # - "any unpublished records they have created themselves" (from client 18/10/2017)
    rules = [
        '(capacity:public AND organization_visibility:"all")',
        '(creator_user_id:{0} AND +state:(draft OR active))'.format(user.id)
    ]

    for organization in user_organizations:
        role = helpers.role_in_org(organization.id, username)

        # Any user within the organisation that owns the dataset can see it
        # Unsure about this rule -- need to check with client..
        if role == 'admin':
            rules.append('(owner_org:"{0}")'.format(organization.id))
        else:
            rules.append('(owner_org:"{0}" AND workflow_status:"published")'.format(organization.id))

        '''
        PLEASE NOTE: These rules MAY appear to be labelled incorrectly
        BUT - they need to operate inversely as the search is dataset centric
        but we are approaching from a User centric standpoint..
        '''
        # From client ~18/102017:
        # "...within the owning Organisation, discoverability/searchability of *unpublished*
        # data records is limited to the Org ADMIN account holders and the EDITOR account
        # holder who created the data record itself
        if role in ['admin', 'editor', 'member']:
            # ALL
            # All users who have a role in an organisation should be able to see any dataset that has:
            # workflow_status = 'published'
            # organization_visibility = 'all
            rules.append('(organization_visibility:"all" AND workflow_status:"published")')

            if role == 'admin':
                query = '(owner_org:"{0}" AND organization_visibility:"{1}")'
            else:
                # For 'editor' and 'member' users
                query = '(owner_org:"{0}" AND organization_visibility:"{1}" AND workflow_status:"published")'

            # PARENT
            # Dataset Organisation Visibility = Parent -- Get this Organization's Child orgs...
            for child in organization.get_children_groups('organization'):
                rules.append(query.format(child.id, 'parent'))
            # CHILD
            # Dataset Organisation Visibility = Child -- Get this Organization's Parent orgs...
            for parent in organization.get_parent_groups('organization'):
                rules.append(query.format(parent.id, 'child'))
            # FAMILY
            # Dataset Organisation Visibility = Family -- Get this Organization's Ancestor & Descendent orgs...
            for ancestor in organization.get_parent_group_hierarchy('organization'):
                rules.append(query.format(ancestor.id, 'family'))
                descendants = ancestor.get_children_group_hierarchy('organization')
                for descendant in descendants:
                    rules.append(query.format(descendant.id, 'family'))

            for descendant in organization.get_children_group_hierarchy('organization'):
                rules.append(query.format(descendant.id, 'family'))

    rules = ' ( {0} ) '.format(' OR '.join(rule for rule in rules))

    # DEBUG:
    if config.get('debug', False):
        print(">>>>>>>>>>>>>>>>>>>>>>>>> package_search_filter_query RULES: <<<<<<<<<<<<<<<<<<<<<<<<<<")
        pprint(rules)

    return rules
