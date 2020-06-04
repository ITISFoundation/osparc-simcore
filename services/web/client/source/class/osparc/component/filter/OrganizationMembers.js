/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Filter for members for the given organization.
 */
qx.Class.define("osparc.component.filter.OrganizationMembers", {
  extend: osparc.component.filter.TagsFilter,

  /**
   * Constructor for Organizations creates the filter and builds its menu.
   *
   * @extends osparc.component.filter.TagsFilter
   */
  construct: function(filterGroupId) {
    this.base(arguments, this.tr("Members"), "organizationMembers", filterGroupId);
  },

  properties: {
    organizationId: {
      check: "Number",
      nullable: true,
      apply: "_applyOrganizationId",
      event: "changeOrganizationId"
    }
  },

  members: {
    _applyOrganizationId: function(orgId) {
      this._removeAllOptions();
      const params = {
        url: {
          gid: orgId
        }
      };
      osparc.data.Resources.get("organizationMembers", params)
        .then(members => {
          members.sort((a, b) => (a["first_name"] > b["first_name"]) ? 1 : -1);
          members.forEach(member => {
            const name = osparc.utils.Utils.capitalize(member["first_name"]) + osparc.utils.Utils.capitalize(member["last_name"]);
            const bnt = this._addOption(name);
            bnt.uid = member["id"];
          });
        });
    },

    getSelectedOrgMemberIDs: function() {
      const selectedOrganizationMemberIDs = [];
      const activeMenuButtons = this._getActiveMenuButtons();
      activeMenuButtons.forEach(activeMenuButton => {
        selectedOrganizationMemberIDs.push(activeMenuButton.uid);
      });
      return selectedOrganizationMemberIDs;
    }
  }
});
