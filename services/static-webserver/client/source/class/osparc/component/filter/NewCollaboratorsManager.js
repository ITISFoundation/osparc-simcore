/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.component.filter.NewCollaboratorsManager", {
  extend: osparc.ui.window.SingletonWindow,
  construct: function(resourceData) {
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
    this.__selectedCollaborators = new qx.data.Array();
    this.__renderLayout();
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
    __saveButton: null,
    __selectedCollaborators: null,
    __visibleCollaborators: null,

    __renderLayout: function() {
      const filter = new osparc.component.filter.TextFilter("name", "collaboratorsManager").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
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
      const saveButton = this.__saveButton = new osparc.ui.form.FetchButton(this.tr("Share")).set({
        appearance: "strong-button"
      });
      saveButton.addListener("execute", () => this.__saveClicked(), this);
      buttons.add(saveButton);
      this.add(buttons);
    },

    __reloadCollaborators: function() {
      osparc.store.Store.getInstance().getPotentialCollaborators()
        .then(potentialCollaborators => {
          this.__visibleCollaborators = potentialCollaborators;
          this.__addCollaborators();
        });
    },

    __collaboratorButton: function(collaborator) {
      const collaboratorButton = new osparc.component.filter.CollaboratorToggleButton(collaborator);
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
      if (this.__resourceData["accessRights"]) {
        // study/template
        existingCollabs = Object.keys(this.__resourceData["accessRights"]);
      } else if (this.__resourceData["access_rights"]) {
        // service
        existingCollabs = Object.keys(this.__resourceData["access_rights"]);
      }
      visibleCollaborators.forEach(visibleCollaborator => {
        // do not list the visibleCollaborators that are already collaborators
        if (existingCollabs.includes(visibleCollaborator["gid"])) {
          return;
        }
        this.__collabButtonsContainer.add(this.__collaboratorButton(visibleCollaborator));
      });
    },

    __saveClicked: function() {
      this.__collabButtonsContainer.setEnabled(false);
      this.__saveButton.setFetching(true);

      const addCollabs = [];
      for (let i=0; i<this.__selectedCollaborators.length; i++) {
        const collabId = this.__selectedCollaborators.getItem(i);
        addCollabs.push(collabId);
      }
      if (addCollabs.length) {
        this.fireDataEvent("addCollaborators", addCollabs);
      }

      this.__collabButtonsContainer.setEnabled(true);
      this.__saveButton.setFetching(false);
    }
  }
});
