import pytest
import ckan.plugins.toolkit as tk
from ckanext.workflow import helpers


@pytest.mark.usefixtures("clean_db", "with_plugins")
class TestGetAdminUsersForOrg:
    def test_returns_active_admins_only(self, organization, user_factory):
        """Only admins with state 'active' are returned."""
        active_user = user_factory(state="active")
        pending_user = user_factory(state="pending")

        for u in (active_user, pending_user):
            tk.get_action("member_create")(
                {"ignore_auth": True},
                {
                    "id": organization["id"],
                    "object": u["id"],
                    "object_type": "user",
                    "capacity": "admin",
                },
            )

        result = helpers.get_admin_users_for_org(organization["id"])

        assert len(result) == 1
        assert result[0]["email"] == active_user["email"]
