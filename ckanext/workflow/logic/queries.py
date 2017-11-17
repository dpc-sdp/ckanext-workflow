import ckan.model as model
import logging
from ckanext.workflow import helpers

log1 = logging.getLogger(__name__)


def organization_read_filter_query(organization_id, username):
    log1.debug('*** PACKAGE_SEARCH | organization_read_filter_query ***')

    fq = 'owner_org:"{0}"'.format(organization_id)

    user_organizations = helpers.get_user_organizations(username)
    organization = model.Group.get(organization_id)

    # If the user is in the organization being viewed - we don't need to check if they can see any of
    # the organizations packages (datasets) by way of organization_visibilty
    if helpers.find_match_in_list([organization], user_organizations):
        log1.debug('*** User belongs to organization `%s` - no further querying required ***', organization.name)
        return ' OR ( {0} )'.format(fq)

    relationships = helpers.get_organization_relationships_for_user(organization, user_organizations)

    if relationships:
        fq = ' OR ( {0}'.format(fq)
        fq += ' AND ( organization_visibility:"{0}" ) '.format('" OR organization_visibility:"'.join(relationship for relationship in relationships))
        fq += ' ) '
    else:
        fq = '+{0}'.format(fq)

    return fq


def package_search_filter_query(username):
    # All logged in users can see any Published datasets with org vis set to All
    user = model.User.get(username)
    user_organizations = user.get_groups('organization')
    rules = ['(capacity:public AND organization_visibility:"all")']
    for organization in user_organizations:
        # Any user within the organisaion that owns the dataset can see it
        rules.append('(owner_org:"{0}")'.format(organization.id))
        '''
        PLEASE NOTE: These rules MAY appear to be labelled incorrectly
        BUT - they need to operate inversely as the search is dataset centric
        but we are approaching from a User centric standpoint..
        '''
        # PARENT
        # Dataset Organisation Visibility = Parent -- Get this Organization's Child orgs...
        for child in organization.get_children_groups('organization'):
            rules.append('(owner_org:"{0}" AND organization_visibility:"{1}")'.format(child.id, 'parent'))
        # CHILD
        # Dataset Organisation Visibility = Child -- Get this Organization's Parent orgs...
        for parent in organization.get_parent_groups('organization'):
            rules.append('(owner_org:"{0}" AND organization_visibility:"{1}")'.format(parent.id, 'child'))
        # FAMILY
        # Dataset Organisation Visibility = Family -- Get this Organization's Ancestor & Descendent orgs...
        for ancestor in organization.get_parent_group_hierarchy('organization'):
            rules.append('(owner_org:"{0}" AND organization_visibility:"{1}")'.format(ancestor.id, 'family'))
        for descendent in organization.get_children_group_hierarchy('organization'):
            rules.append('(owner_org:"{0}" AND organization_visibility:"{1}")'.format(descendent.id, 'family'))
    # DEBUG:
    # print(">>>>>>>>>>>>>>>>>>>>>>>>> RULES: <<<<<<<<<<<<<<<<<<<<<<<<<<")
    # pprint(' OR '.join(rule for rule in rules))
    return ' ( {0} ) '.format(' OR '.join(rule for rule in rules))
