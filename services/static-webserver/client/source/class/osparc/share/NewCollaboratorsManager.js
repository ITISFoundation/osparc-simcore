/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.share.NewCollaboratorsManager", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function(resourceData, showOrganizations = true) {
    this.base(arguments, "collaboratorsManager", this.tr("Share with"));
    this.set({
      layout: new qx.ui.layout.VBox(),
      allowMinimize: false,
      allowMaximize: false,
      showMinimize: false,
      showMaximize: false,
      autoDestroy: true,
      modal: true,
      width: 262,
      maxHeight: 500,
      clickAwayClose: true
    });

    this.__resourceData = resourceData;
    this.__showOrganizations = showOrganizations;

    this.__renderLayout();

    this.__selectedCollaborators = new qx.data.Array();
    this.__visibleCollaborators = {};
    this.__reloadCollaborators();

    this.center();
    this.open();
  },

  events: {
    "addCollaborators": "qx.event.type.Data"
  },

  members: {
    __resourceData: null,
    __showOrganizations: null,
    __collabButtonsContainer: null,
    __shareButton: null,
    __selectedCollaborators: null,
    __visibleCollaborators: null,

    getActionButton: function() {
      return this.__shareButton;
    },

    __renderLayout: function() {
      const filter = new osparc.filter.TextFilter("name", "collaboratorsManager").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      this.addListener("appear", () => filter.getChildControl("textfield").focus());
      this.add(filter);

      const collabButtonsContainer = this.__collabButtonsContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(collabButtonsContainer);
      this.add(scrollContainer, {
        flex: 1
      });

      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));
      const shareButton = this.__shareButton = new osparc.ui.form.FetchButton(this.tr("Share")).set({
        appearance: "strong-button"
      });
      shareButton.addListener("execute", () => this.__shareClicked(), this);
      buttons.add(shareButton);
      this.add(buttons);
    },

    __reloadCollaborators: function() {
      let includeEveryone = false;
      if (this.__showOrganizations === false) {
        includeEveryone = false;
      } else if (this.__resourceData && this.__resourceData["resourceType"] === "service") {
        includeEveryone = true;
      } else {
        includeEveryone = osparc.data.Permissions.getInstance().canDo("study.everyone.share");
      }
      osparc.store.Store.getInstance().getPotentialCollaborators(false, includeEveryone)
        .then(potentialCollaborators => {
          this.__visibleCollaborators = potentialCollaborators;
          this.__addCollaborators();
        });
    },

    __collaboratorButton: function(collaborator) {
      const collaboratorButton = new osparc.filter.CollaboratorToggleButton(collaborator);
      collaboratorButton.addListener("changeValue", e => {
        const selected = e.getData();
        if (selected) {
          this.__selectedCollaborators.push(collaborator.gid);
        } else {
          this.__selectedCollaborators.remove(collaborator.gid);
        }
      }, this);
      collaboratorButton.subscribeToFilterGroup("collaboratorsManager");
      return collaboratorButton;
    },

    __addCollaborators: function() {
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

      let existingCollabs = [];
      if (this.__resourceData) {
        if (this.__resourceData["accessRights"]) {
          // study/template/wallet
          if (this.__resourceData["resourceType"] === "wallet") {
            existingCollabs = this.__resourceData["accessRights"].map(collab => collab["gid"]);
          } else {
            existingCollabs = Object.keys(this.__resourceData["accessRights"]);
          }
        } else if (this.__resourceData["access_rights"]) {
          // service
          existingCollabs = Object.keys(this.__resourceData["access_rights"]);
        }
      }

      const existingCollaborators = existingCollabs.map(c => parseInt(c));
      visibleCollaborators.forEach(visibleCollaborator => {
        // do not list the visibleCollaborators that are already collaborators
        if (existingCollaborators.includes(visibleCollaborator["gid"])) {
          return;
        }
        if (this.__showOrganizations === false && visibleCollaborator["collabType"] !== 2) {
          return;
        }
        this.__collabButtonsContainer.add(this.__collaboratorButton(visibleCollaborator));
      });
    },

    __shareClicked: function() {
      this.__collabButtonsContainer.setEnabled(false);
      this.__shareButton.setFetching(true);

      const addCollabs = [];
      for (let i=0; i<this.__selectedCollaborators.length; i++) {
        const collabId = this.__selectedCollaborators.getItem(i);
        addCollabs.push(collabId);
      }
      if (addCollabs.length) {
        this.fireDataEvent("addCollaborators", addCollabs);
      }
      // The parent class will close the window
    }
  }
});
