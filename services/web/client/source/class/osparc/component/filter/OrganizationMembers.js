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
  construct: function() {
    this.base(arguments, this.tr("Organization members"), "organizations", "organizationMembers");

    this.__buildMenu();
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
    /**
     * Function that uses the information in {osparc.store.Store.getGroupsOrganizations} to build the menu for the filter.
     */
    _applyOrganizationId: function(orgId) {
      const store = osparc.store.Store.getInstance();
      store.getOrganizationMembers(orgId)
        .then(members => {
          members.sort(this.__sortByLabel);
          members.forEach(member => {
            const bnt = this._addOption(osparc.utils.Utils.capitalize(member["label"]));
            bnt.uid = member["uid"];
          });
        });
    },

    __sortByLabel: function(org1, org2) {
      if (org1.label > org2.label) {
        return 1;
      }
      if (org1.label < org2.label) {
        return -1;
      }
      return 0;
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
