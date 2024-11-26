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
      width: 350,
      maxHeight: 500,
      clickAwayClose: true
    });

    this.__resourceData = resourceData;
    this.__showOrganizations = showOrganizations;

    this.__renderLayout();

    this.__selectedCollaborators = [];
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
    __introLabel: null,
    __textFilter: null,
    __collabButtonsContainer: null,
    __orgsButton: null,
    __shareButton: null,
    __selectedCollaborators: null,
    __visibleCollaborators: null,

    getActionButton: function() {
      return this.__shareButton;
    },

    __renderLayout: function() {
      const introText = this.tr("In order to start Sharing with other members, you first need to belong to an Organization.");
      const introLabel = this.__introLabel = new qx.ui.basic.Label(introText).set({
        rich: true,
        wrap: true,
        visibility: "excluded",
        padding: 8
      });
      this.add(introLabel);

      const filter = this.__textFilter = new osparc.filter.TextFilter("name", "collaboratorsManager").set({
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
      // Quick access for users that still don't belong to any organization
      const orgsButton = this.__orgsButton = new qx.ui.form.Button(this.tr("My Organizations...")).set({
        appearance: "form-button",
        visibility: "excluded",
      });
      orgsButton.addListener("execute", () => osparc.desktop.organizations.OrganizationsWindow.openWindow(), this);
      buttons.add(orgsButton);
      const shareButton = this.__shareButton = new osparc.ui.form.FetchButton(this.tr("Share")).set({
        appearance: "form-button",
        enabled: false,
      });
      shareButton.addListener("execute", () => this.__shareClicked(), this);
      buttons.add(shareButton);
      this.add(buttons);
    },

    __reloadCollaborators: function() {
      let includeProductEveryone = false;
      if (this.__showOrganizations === false) {
        includeProductEveryone = false;
      } else if (this.__resourceData && this.__resourceData["resourceType"] === "study") {
        // studies can't be shared with ProductEveryone
        includeProductEveryone = false;
      } else if (this.__resourceData && this.__resourceData["resourceType"] === "template") {
        // only users with permissions can share templates with ProductEveryone
        includeProductEveryone = osparc.data.Permissions.getInstance().canDo("study.everyone.share");
      } else if (this.__resourceData && this.__resourceData["resourceType"] === "service") {
        // all users can share services with ProductEveryone
        includeProductEveryone = true;
      }
      const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators(false, includeProductEveryone)
      this.__visibleCollaborators = potentialCollaborators;
      const anyCollaborator = Object.keys(potentialCollaborators).length;
      // tell the user that belonging to an organization is required to start sharing
      this.__introLabel.setVisibility(anyCollaborator ? "excluded" : "visible");
      this.__orgsButton.setVisibility(anyCollaborator ? "excluded" : "visible");

      // or start sharing
      this.__textFilter.setVisibility(anyCollaborator ? "visible" : "excluded");
      this.__collabButtonsContainer.setVisibility(anyCollaborator ? "visible" : "excluded");
      this.__shareButton.setVisibility(anyCollaborator ? "visible" : "excluded");
      this.__addEditors();
    },

    __collaboratorButton: function(collaborator) {
      const collaboratorButton = new osparc.filter.CollaboratorToggleButton(collaborator);
      collaboratorButton.addListener("changeValue", e => {
        const selected = e.getData();
        if (selected) {
          this.__selectedCollaborators.push(collaborator.getGroupId());
        } else {
          this.__selectedCollaborators.remove(collaborator.getGroupId());
        }
        this.__shareButton.setEnabled(Boolean(this.__selectedCollaborators.length));
      }, this);
      collaboratorButton.subscribeToFilterGroup("collaboratorsManager");
      return collaboratorButton;
    },

    __addEditors: function() {
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

      let existingCollabs = [];
      if (this.__resourceData && this.__resourceData["accessRights"]) {
        // study/template/service/wallet
        if (this.__resourceData["resourceType"] === "wallet") {
          // array of objects
          existingCollabs = this.__resourceData["accessRights"].map(collab => collab["gid"]);
        } else {
          // object
          existingCollabs = Object.keys(this.__resourceData["accessRights"]);
        }
      }

      const existingCollaborators = existingCollabs.map(c => parseInt(c));
      visibleCollaborators.forEach(visibleCollaborator => {
        // do not list the visibleCollaborators that are already collaborators
        if (existingCollaborators.includes(visibleCollaborator.getGroupId())) {
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

      if (this.__selectedCollaborators.length) {
        this.fireDataEvent("addCollaborators", this.__selectedCollaborators);
      }
      // The parent class will close the window
    }
  }
});
