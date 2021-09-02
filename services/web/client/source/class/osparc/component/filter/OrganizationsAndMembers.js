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
    this.base(arguments, this.tr("Organizations and Members"), "organizationsAndMembers", filterGroupId);

    this.__visibleCollaborators = {};
  },

  members: {
    __visibleCollaborators: null,
    __collaboratorsToBeRemoved: null,

    addOption: function(group) {
      let name = "";
      if ("first_name" in group) {
        name = group["first_name"] + " " + group["last_name"];
      } else {
        name = group["label"];
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
    },

    reloadVisibleCollaborators: function(collaboratorsToBeRemoved = null) {
      if (collaboratorsToBeRemoved) {
        this.__collaboratorsToBeRemoved = collaboratorsToBeRemoved.map(collaboratorToBeRemoved => parseInt(collaboratorToBeRemoved));
      }

      const store = osparc.store.Store.getInstance();
      const promises = [];
      promises.push(store.getGroupsOrganizations());
      promises.push(store.getVisibleMembers());
      Promise.all(promises)
        .then(values => {
          const orgs = values[0]; // array
          const orgMembers = values[1]; // object
          orgs.forEach(org => {
            org["collabType"] = 1;
            this.__visibleCollaborators[org["gid"]] = org;
          });
          for (const gid of Object.keys(orgMembers)) {
            const orgMember = orgMembers[gid];
            orgMember["collabType"] = 2;
            this.__visibleCollaborators[gid] = orgMember;
          }
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
        if (a["label"] > b["label"]) {
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
