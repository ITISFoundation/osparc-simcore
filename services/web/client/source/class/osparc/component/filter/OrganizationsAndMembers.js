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
qx.Class.define("osparc.component.filter.OrganizationsAndMembers", {
  extend: osparc.component.filter.TagsFilter,

  /**
   * Constructor for Organizations creates the filter and builds its menu.
   *
   * @extends osparc.component.filter.TagsFilter
   */
  construct: function(filterGroupId) {
    this.base(arguments, this.tr("Members"), "organizationsAndMembers", filterGroupId);
  },

  members: {
    addOption: function(group) {
      let name = "";
      if ("first_name" in group) {
        name = group["first_name"] + " " + group["last_name"];
      } else {
        name = group["name"];
      }
      const btn = this._addOption(name);
      btn.gid = group["gid"];
      return btn;
    },

    addOptions: function(groups) {
      this._removeAllOptions();
      groups.forEach(group => {
        this.addOption(group);
      });
    },

    getSelectedGIDs: function() {
      const selectedGIDs = [];
      const activeMenuButtons = this._getActiveMenuButtons();
      activeMenuButtons.forEach(activeMenuButton => {
        selectedGIDs.push(activeMenuButton.gid);
      });
      return selectedGIDs;
    }
  }
});
