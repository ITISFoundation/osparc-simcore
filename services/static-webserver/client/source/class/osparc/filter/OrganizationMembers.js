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
qx.Class.define("osparc.filter.OrganizationMembers", {
  extend: osparc.filter.TagsFilter,

  /**
   * Constructor for Organizations creates the filter and builds its menu.
   *
   * @extends osparc.filter.TagsFilter
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
            const name = osparc.utils.Utils.firstsUp(member["first_name"], member["last_name"]);
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
