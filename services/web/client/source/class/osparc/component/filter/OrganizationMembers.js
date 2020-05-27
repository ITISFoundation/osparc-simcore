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
      const store = osparc.store.Store.getInstance();
      store.getOrganizationMembers(orgId)
        .then(members => {
          members.sort((a, b) => (a["name"] > b["name"]) ? 1 : -1);
          members.forEach(member => {
            const bnt = this._addOption(osparc.utils.Utils.capitalize(member["name"]));
            bnt.uid = member["uid"];
          });
        });
    },

    getSelectedOrganizationMemberIDs: function() {
      const selectedOrganizationMemberIDs = [];
      const activeMenuButtons = this._getActiveMenuButtons();
      activeMenuButtons.forEach(activeMenuButton => {
        selectedOrganizationMemberIDs.push(activeMenuButton.uid);
      });
      return selectedOrganizationMemberIDs;
    }
  }
});
