from __future__ import annotations

import logging

import ckan.model as model
import ckan.plugins.toolkit as toolkit
import ckan.lib.plugins as lib_plugins

from ckanext.workflow import helpers

log1 = logging.getLogger(__name__)
config = toolkit.config


def organization_read_filter_query(organization_id, username):
    log1.debug(
        "*** PACKAGE_SEARCH | organization_read_filter_query | organization_id: %s ***"
        % organization_id
    )

    organization = model.Group.get(organization_id)
    user = model.User.get(username)

    rules = []

    if not user:
        return ""

    role = helpers.role_in_org(organization_id, username)

    if role or user.sysadmin:
        log1.debug(
            "*** User belongs to organization `%s` | role: %s - no further querying required ***",
            organization.name,
            role,
        )
        # Of course the user can see any datasets they have created
        rules.append(f'(owner_org:"{organization_id}" AND creator_user_id:"{user.id}")')
        # Admin can see unpublished datasets in organisations they are members of
        if role in ["admin", "editor"] or user.sysadmin:
            rules.append(f'(owner_org:"{organization_id}")')
        else:
            # The user can see any published datasets in their own organisation
            rules.append(f'(capacity:public AND owner_org:"{organization_id}")')
    else:
        user_organizations = helpers.get_user_organizations(username)
        relationships = helpers.get_organization_relationships_for_user(
            organization, user_organizations
        )
        if relationships:
            for relationship in relationships:
                rules.append(
                    f'(owner_org:"{organization_id}" AND organization_visibility:"{relationship}" AND workflow_status:"published")'
                )

    if toolkit.config["ckan.auth.allow_dataset_collaborators"]:
        add_collaborators_filter(rules, user)

    rules = " ( {0} ) ".format(" OR ".join(rule for rule in rules))

    return rules


def package_search_filter_query(user: model.User | model.AnonymousUser):
    # Return early if private site and non-logged in user..

    if user.is_anonymous:
        return ""

    user_organizations = user.get_groups("organization")

    # All logged in users can see:
    # - any datasets with organization_visibility set to All and workflow_status set to published
    # - "any unpublished records they have created themselves" (from client 18/10/2017)
    rules = [
        '(organization_visibility:"all" AND workflow_status:"published")',
        f"(creator_user_id:{user.id} AND +state:(draft OR active))",
    ]

    if toolkit.config["ckan.auth.allow_dataset_collaborators"]:
        add_collaborators_filter(rules, user)

    for organization in user_organizations:
        role = helpers.role_in_org(organization.id, user.name)

        # Any user within the organisation that owns the dataset can see it
        # Unsure about this rule -- need to check with client..
        if role == "admin":
            rules.append(f'(owner_org:"{organization.id}")')
        else:
            rules.append(
                f'(owner_org:"{organization.id}" AND workflow_status:"published")'
            )

        """
        PLEASE NOTE: These rules MAY appear to be labelled incorrectly
        BUT - they need to operate inversely as the search is dataset centric
        but we are approaching from a User centric standpoint..
        """
        # From client ~18/102017:
        # "...within the owning Organisation, discoverability/searchability of *unpublished*
        # data records is limited to the Org ADMIN account holders and the EDITOR account
        # holder who created the data record itself
        if role in ["admin", "editor", "member"]:
            if role == "admin" or user.sysadmin:
                query = '(owner_org:"{0}" AND organization_visibility:"{1}")'
            else:
                # For 'editor' and 'member' users
                query = '(owner_org:"{0}" AND organization_visibility:"{1}" AND workflow_status:"published")'

            # PARENT
            # Dataset Organisation Visibility = Parent -- Get this Organization's Child orgs...
            for child in organization.get_children_groups("organization"):
                rules.append(query.format(child.id, "parent"))
            # CHILD
            # Dataset Organisation Visibility = Child -- Get this Organization's Parent orgs...
            for parent in organization.get_parent_groups("organization"):
                rules.append(query.format(parent.id, "child"))
            # FAMILY
            # Dataset Organisation Visibility = Family -- Get this Organization's Ancestor & Descendent orgs...
            for ancestor in organization.get_parent_group_hierarchy("organization"):
                rules.append(query.format(ancestor.id, "family"))
                descendants = ancestor.get_children_group_hierarchy("organization")
                for descendant in descendants:
                    rules.append(query.format(descendant.id, "family"))

            for descendant in organization.get_children_group_hierarchy("organization"):
                rules.append(query.format(descendant.id, "family"))

    rules = " ( {0} ) ".format(" OR ".join(rule for rule in rules))

    return rules


def add_collaborators_filter(rules: list, user: model.User) -> list:
    """Add rules to filter datasets by collaborators"""

    user_labels = lib_plugins.get_permission_labels().get_user_dataset_labels(user)

    for permission_label in user_labels:
        if not permission_label.startswith("collaborator"):
            continue

        rules.append(f'(permission_labels:"{permission_label}")')
