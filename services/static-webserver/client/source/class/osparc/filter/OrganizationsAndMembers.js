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
qx.Class.define("osparc.filter.OrganizationsAndMembers", {
  extend: osparc.filter.TagsFilter,

  /**
   * Constructor for Organizations creates the filter and builds its menu.
   *
   * @extends osparc.filter.TagsFilter
   */
  construct: function(filterGroupId) {
    this.base(arguments, this.tr("Organizations and Members"), "organizationsAndMembers", filterGroupId);

    this.__visibleCollaborators = {};
  },

  members: {
    __visibleCollaborators: null,
    __collaboratorsToBeRemoved: null,

    addOption: function(group) {
      const name = group.getLabel();
      const btn = this._addOption(name);
      btn.gid = group.getGroupId();
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
    },

    __addOrgsAndMembers: function() {
      this.reset();

      const visibleCollaborators = Object.values(this.__visibleCollaborators);

      const collabTypeOrder = osparc.store.Groups.COLLAB_TYPE_ORDER;
      // sort them first
      visibleCollaborators.sort((a, b) => {
        const typeDiff = collabTypeOrder.indexOf(a["collabType"]) - collabTypeOrder.indexOf(b["collabType"]);
          if (typeDiff !== 0) {
            return typeDiff;
          }
          // fallback: sort alphabetically by label
          return a.getLabel().localeCompare(b.getLabel());
      });

      visibleCollaborators.forEach(visibleCollaborator => {
        if (this.__collaboratorsToBeRemoved && this.__collaboratorsToBeRemoved.includes(visibleCollaborator["gid"])) {
          return;
        }
        const btn = this.addOption(visibleCollaborator);
        let iconPath = null;
        switch (visibleCollaborator["collabType"]) {
          case osparc.store.Groups.COLLAB_TYPE.EVERYONE:
            iconPath = osparc.dashboard.CardBase.SHARED_ALL;
            break;
          case osparc.store.Groups.COLLAB_TYPE.ORGANIZATION:
            iconPath = osparc.dashboard.CardBase.SHARED_ORGS;
            break;
          case osparc.store.Groups.COLLAB_TYPE.USER:
            iconPath = osparc.dashboard.CardBase.SHARED_USER;
            break;
        }
        btn.setIcon(iconPath);
      });
    }
  }
});
