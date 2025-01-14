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
      layout: new qx.ui.layout.VBox(5),
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
    this.__potentialCollaborators = {};
    this.__reloadPotentialCollaborators();

    this.center();
    this.open();
  },

  events: {
    "addCollaborators": "qx.event.type.Data"
  },

  members: {
    __resourceData: null,
    __showOrganizations: null,
    __textFilter: null,
    __collabButtonsContainer: null,
    __searchingCollaborators: null,
    __searchDelayer: null,
    __shareButton: null,
    __selectedCollaborators: null,
    __potentialCollaborators: null,

    getActionButton: function() {
      return this.__shareButton;
    },

    __renderLayout: function() {
      let text = this.__showOrganizations ?
        this.tr("Select users or organizations from the list below.") :
        this.tr("Select users from the list below.");
      text += this.tr("<br>Search them if they aren't listed.");
      const introLabel = new qx.ui.basic.Label().set({
        value: text,
        rich: true,
        wrap: true,
        paddingBottom: 5
      });
      this.add(introLabel);

      const toolbar = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle",
      }));
      const filter = this.__textFilter = new osparc.filter.TextFilter("name", "collaboratorsManager");
      filter.setCompact(true);
      const filterTextField = filter.getChildControl("textfield");
      filterTextField.setPlaceholder(this.tr("Search"));
      this.addListener("appear", () => filterTextField.focus());
      toolbar.add(filter, {
        flex: 1
      });
      filterTextField.addListener("input", e => {
        const filterValue = e.getData();
        if (this.__searchDelayer) {
          clearTimeout(this.__searchDelayer);
        }
        if (filterValue.length > 3) {
          this.__searchingCollaborators.show();
          this.__searchDelayer = setTimeout(() => {
            this.__searchingCollaborators.show();
            this.__searchUsers();
          }, 1000);
        }
      });
      this.add(toolbar);

      const collabButtonsContainer = this.__collabButtonsContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(collabButtonsContainer);
      this.add(scrollContainer, {
        flex: 1
      });

      const searchingCollaborators = this.__searchingCollaborators = new osparc.filter.SearchingCollaborators();
      searchingCollaborators.exclude();
      this.__collabButtonsContainer.add(searchingCollaborators);

      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));
      const shareButton = this.__shareButton = new osparc.ui.form.FetchButton(this.tr("Share")).set({
        appearance: "form-button",
        enabled: false,
      });
      shareButton.addListener("execute", () => this.__shareClicked(), this);
      buttons.add(shareButton);
      this.add(buttons);
    },

    __searchUsers: function() {
      const text = this.__textFilter.getChildControl("textfield").getValue();
      osparc.store.Users.getInstance().searchUsers(text)
        .then(users => {
          users.forEach(user => user["collabType"] = 2);
          this.__addPotentialCollaborators(users);
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
        })
        .finally(() => {
          this.__searchingCollaborators.exclude();
        });
    },

    __showProductEveryone: function() {
      let showProductEveryone = false;
      if (this.__showOrganizations === false) {
        showProductEveryone = false;
      } else if (this.__resourceData && this.__resourceData["resourceType"] === "study") {
        // studies can't be shared with ProductEveryone
        showProductEveryone = false;
      } else if (this.__resourceData && this.__resourceData["resourceType"] === "template") {
        // only users with permissions can share templates with ProductEveryone
        showProductEveryone = osparc.data.Permissions.getInstance().canDo("study.everyone.share");
      } else if (this.__resourceData && this.__resourceData["resourceType"] === "service") {
        // all users can share services with ProductEveryone
        showProductEveryone = true;
      }
      return showProductEveryone;
    },

    __reloadPotentialCollaborators: function() {
      const includeProductEveryone = this.__showProductEveryone();
      this.__potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators(false, includeProductEveryone);
      const potentialCollaborators = Object.values(this.__potentialCollaborators);
      this.__addPotentialCollaborators(potentialCollaborators);
    },

    __collaboratorButton: function(collaborator) {
      const collaboratorButton = new osparc.filter.CollaboratorToggleButton(collaborator);
      collaboratorButton.groupId = collaborator.getGroupId();
      collaboratorButton.addListener("changeValue", e => {
        const selected = e.getData();
        if (selected) {
          this.__selectedCollaborators.push(collaborator.getGroupId());
        } else {
          const idx = this.__selectedCollaborators.indexOf(collaborator.getGroupId());
          if (idx > -1) {
            this.__selectedCollaborators.splice(idx, 1);
          }
        }
        this.__shareButton.setEnabled(Boolean(this.__selectedCollaborators.length));
      }, this);
      collaboratorButton.subscribeToFilterGroup("collaboratorsManager");
      return collaboratorButton;
    },

    __addPotentialCollaborators: function(potentialCollaborators) {
      // sort them first
      potentialCollaborators.sort((a, b) => {
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
      if (this.__resourceData) {
        if (this.__resourceData["groupMembers"] && this.__resourceData["resourceType"] === "organization") {
          // organization
          existingCollabs = Object.keys(this.__resourceData["groupMembers"]);
        } else if (this.__resourceData["accessRights"] && this.__resourceData["resourceType"] === "wallet") {
          // wallet
          // array of objects
          existingCollabs = this.__resourceData["accessRights"].map(collab => collab["gid"]);
        } else if (this.__resourceData["accessRights"]) {
          // study/template/service/
          // object
          existingCollabs = Object.keys(this.__resourceData["accessRights"]);
        }
      }

      const existingCollaborators = existingCollabs.map(c => parseInt(c));
      potentialCollaborators.forEach(potentialCollaborator => {
        // do not list the potentialCollaborators that are already collaborators
        if (existingCollaborators.includes(potentialCollaborator.getGroupId())) {
          return;
        }
        // do not list those that were already listed
        if (this.__collabButtonsContainer.getChildren().find(c => "groupId" in c && c["groupId"] === potentialCollaborator.getGroupId())) {
          return;
        }
        if (this.__showOrganizations === false && potentialCollaborator["collabType"] !== 2) {
          return;
        }
        this.__collabButtonsContainer.add(this.__collaboratorButton(potentialCollaborator));
      });

      // move it to last position
      this.__collabButtonsContainer.remove(this.__searchingCollaborators);
      this.__collabButtonsContainer.add(this.__searchingCollaborators);
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
