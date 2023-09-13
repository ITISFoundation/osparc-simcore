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
qx.Class.define("osparc.filter.Organizations", {
  extend: osparc.filter.TagsFilter,

  /**
   * Constructor for Organizations creates the filter and builds its menu.
   *
   * @extends osparc.filter.TagsFilter
   */
  construct: function() {
    this.base(arguments, this.tr("Select Organization"), "organizations", "organizations");

    this.__buildMenu();
  },

  members: {
    __buildMenu: function() {
      osparc.data.Resources.get("organizations")
        .then(resp => {
          const orgs = resp["organizations"];
          orgs.sort((a, b) => (a["label"] > b["label"]) ? 1 : -1);
          orgs.forEach(org => {
            const bnt = this._addOption(osparc.utils.Utils.capitalize(org["label"]));
            bnt.gid = org["gid"];
          });
        });
    },

    getSelectedOrgIDs: function() {
      const selectedOrganizationIDs = [];
      const activeMenuButtons = this._getActiveMenuButtons();
      activeMenuButtons.forEach(activeMenuButton => {
        selectedOrganizationIDs.push(activeMenuButton.gid);
      });
      return selectedOrganizationIDs;
    }
  }
});
