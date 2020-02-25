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
 * Filter for organizations.
 */
qx.Class.define("osparc.component.filter.Organizations", {
  extend: osparc.component.filter.TagsFilter,

  /**
   * Constructor for Organizations creates the filter and builds its menu.
   *
   * @extends osparc.component.filter.TagsFilter
   */
  construct: function(groupId) {
    this.base(arguments, this.tr("My Organizations"), "organizations", groupId);
    this._setLayout(new qx.ui.layout.HBox());

    this.__buildMenu();
  },

  members: {
    /**
     * Function that uses the information in {osparc.store.Store.getMyOrganizations} to build the menu for the filter.
     */
    __buildMenu: function() {
      const store = osparc.store.Store.getInstance();
      const myOrganizations = store.getMyOrganizations();
      myOrganizations.sort(this.__sortByLabel);
      myOrganizations.forEach(organization => {
        const bnt = this._addOption(osparc.utils.Utils.capitalize(organization.label));
        bnt.orgId = organization.orgId;
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

    getSelectedOrganizationIDs: function() {
      const selectedOrganizationIDs = [];
      const activeMenuButtons = this._getActiveMenuButtons();
      activeMenuButtons.forEach(activeMenuButton => {
        selectedOrganizationIDs.push(activeMenuButton.orgId);
      });
      return selectedOrganizationIDs;
    }
  }
});
