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

    reloadVisibleCollaborators: function(collaboratorsToBeRemoved = null) {
      if (collaboratorsToBeRemoved) {
        this.__collaboratorsToBeRemoved = collaboratorsToBeRemoved.map(collaboratorToBeRemoved => parseInt(collaboratorToBeRemoved));
      }

      osparc.store.Groups.getInstance().getPotentialCollaborators()
        .then(potentialCollaborators => {
          this.__visibleCollaborators = potentialCollaborators;
          this.__addOrgsAndMembers();
        });
    },

    __addOrgsAndMembers: function() {
      this.reset();

      const visibleCollaborators = Object.values(this.__visibleCollaborators);

      // sort them first
      visibleCollaborators.sort((a, b) => {
        if (a["collabType"] > b["collabType"]) {
          return 1;
        }
        if (a["collabType"] < b["collabType"]) {
          return -1;
        }
        if (a.getLabel() > b.getLabel()) {
          return 1;
        }
        return -1;
      });

      visibleCollaborators.forEach(visibleCollaborator => {
        if (this.__collaboratorsToBeRemoved && this.__collaboratorsToBeRemoved.includes(visibleCollaborator["gid"])) {
          return;
        }
        const btn = this.addOption(visibleCollaborator);
        let iconPath = null;
        switch (visibleCollaborator["collabType"]) {
          case 0:
            iconPath = "@FontAwesome5Solid/globe/14";
            break;
          case 1:
            iconPath = "@FontAwesome5Solid/users/14";
            break;
          case 2:
            iconPath = "@FontAwesome5Solid/user/14";
            break;
        }
        btn.setIcon(iconPath);
      });
    }
  }
});
