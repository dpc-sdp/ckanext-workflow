from __future__ import annotations

import ckan.authz as authz
import ckan.plugins.toolkit as tk
import logging

import ckan.types as types
from ckan.logic.auth import get_package_object

# from ckan.lib.plugins import get_permission_labels
from ckanext.workflow import helpers


log = logging.getLogger(__name__)


@tk.chained_auth_function
@tk.auth_allow_anonymous_access
def package_show(
    next_auth: types.AuthFunction,
    context: types.Context,
    data_dict: types.DataDict,
) -> types.AuthResult:
    user = context.get("user")
    package = get_package_object(context, data_dict)

    # DATAVIC: Apply organisation visibility rules if the dataset is marked private
    if (
        tk.asbool(package.private)
        and package.extras
        and helpers.user_can_view_private_dataset(package, user)
    ):
        return {"success": True}

    return next_auth(context, data_dict)


def organization_create(context, data_dict=None):
    """Custom code: if user is an admin in any org, allow him to create orgs"""
    user_name = tk.current_user.name if tk.current_user else None
    if authz.is_sysadmin(user_name):
        return {"success": True}

    if not authz.auth_is_anon_user(context):
        orgs = helpers.get_user_organizations(user_name)
        for org in orgs:
            role = helpers.role_in_org(org.id, user_name)
            if role == "admin":
                return {"success": True}

    return {
        "success": False,
        "msg": "Only user level admin or above can create an organisation.",
    }


def organization_update(context, data_dict=None):
    user_name = tk.current_user.name if tk.current_user else None
    if authz.is_sysadmin(user_name):
        return {"success": True}

    if authz.auth_is_anon_user(context):
        return {
            "success": False,
            "msg": "Only user level admin or above can update an organisation.",
        }

    if data_dict is not None and "id" in data_dict:
        organization_id = data_dict["id"]
    elif "group" in context:
        organization_id = context["group"].id
    else:
        log.debug("Scenario not accounted for in ckanext-workflow > plugin.py")
        return {"success": False, "msg": "Missing organization ID."}

    if organization_id:
        role = helpers.role_in_org(organization_id, user_name)
        if role == "admin":
            return {"success": True}

    return {
        "success": False,
        "msg": "Only user level admin or above can update an organisation.",
    }
