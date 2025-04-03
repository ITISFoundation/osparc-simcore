/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.share.NewCollaboratorsManager", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function(resourceData, showOrganizations = true) {
    this.base(arguments, "newCollaboratorsManager", this.tr("New collaborators"));

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

    this.__selectedCollaborators = {};
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
    __searchDelayer: null,
    __selectedCollaborators: null,
    __potentialCollaborators: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-text": {
          let text = this.__showOrganizations ?
            this.tr("Select users or organizations from the list below.") :
            this.tr("Select users from the list below.");
          text += this.tr("<br>Search them if they aren't listed.");
          control = new qx.ui.basic.Label().set({
            value: text,
            rich: true,
            wrap: true,
            paddingBottom: 5
          });
          this.add(control);
          break;
        }
        case "text-filter": {
          control = new osparc.filter.TextFilter("name", "collaboratorsManager");
          control.setCompact(true);
          const filterTextField = control.getChildControl("textfield");
          filterTextField.setPlaceholder(this.tr("Search"));
          filterTextField.setBackgroundColor("transparent");
          this.addListener("appear", () => filterTextField.focus());
          this.add(control);
          break;
        }
        case "potential-collaborators-list": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
            minHeight: 100,
          });
          const scrollContainer = new qx.ui.container.Scroll();
          scrollContainer.add(control);
          this.add(scrollContainer, {
            flex: 1
          });
          break;
        }
        case "searching-collaborators":
          control = new osparc.filter.SearchingCollaborators();
          control.exclude();
          this.getChildControl("potential-collaborators-list").add(control);
          break;
        case "access-rights-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(2)).set({
            paddingLeft: 8,
          });
          const title = new qx.ui.basic.Label(this.tr("Set following Role:"));
          control.add(title);
          this.add(control);
          break;
        }
        case "access-rights-selector":
          control = new qx.ui.form.SelectBox().set({
            allowGrowX: false,
            backgroundColor: "transparent",
          });
          this.getChildControl("access-rights-layout").add(control);
          break;
        case "access-rights-helper": {
          control = new qx.ui.basic.Label().set({
            paddingLeft: 5,
            font: "text-12",
            rich: true,
          });
          this.getChildControl("access-rights-layout").add(control);
          break;
        }
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignX: "right"
          }));
          this.add(control);
          break;
        case "share-button":
          control = new osparc.ui.form.FetchButton(this.tr("Share")).set({
            appearance: "form-button",
            enabled: false,
          });
          this.getChildControl("buttons-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    getActionButton: function() {
      return this.getChildControl("share-button");
    },

    __renderLayout: function() {
      this.getChildControl("intro-text");

      const textFilter = this.getChildControl("text-filter");
      const filterTextField = textFilter.getChildControl("textfield");
      filterTextField.addListener("input", e => {
        const filterValue = e.getData();
        if (this.__searchDelayer) {
          clearTimeout(this.__searchDelayer);
        }
        if (filterValue.length > 3) {
          const waitBeforeSearching = 1000;
          this.__searchDelayer = setTimeout(() => {
            this.__searchUsers();
          }, waitBeforeSearching);
        }
      });

      this.getChildControl("potential-collaborators-list");
      this.getChildControl("searching-collaborators");

      if (this.__resourceData["resourceType"] === "study") {
        const selectBox = this.getChildControl("access-rights-selector");
        const helper = this.getChildControl("access-rights-helper");

        Object.entries(osparc.data.Roles.STUDY).forEach(([id, role]) => {
          const option = new qx.ui.form.ListItem(role.label, null, id);
          selectBox.add(option);
        });
        selectBox.addListener("changeSelection", e => {
          const selected = e.getData()[0];
          if (selected) {
            const selectedRole = osparc.data.Roles.STUDY[selected.getModel()];
            const helperText = selectedRole.canDo.join("<br>");
            helper.setValue(helperText);
          }
        }, this);
        selectBox.getSelectables().forEach(selectable => {
          if (selectable.getModel() === "write") { // in case of the study, default it to "write"
            selectBox.setSelection([selectable]);
          }
        });
      }

      const shareButton = this.getChildControl("share-button");
      shareButton.addListener("execute", () => this.__shareClicked(), this);
    },

    __searchUsers: function() {
      this.getChildControl("searching-collaborators").show();
      const text = this.getChildControl("text-filter").getChildControl("textfield").getValue();
      osparc.store.Users.getInstance().searchUsers(text)
        .then(users => {
          users.forEach(user => user["collabType"] = 2);
          this.__addPotentialCollaborators(users);
        })
        .catch(err => osparc.FlashMessenger.logError(err))
        .finally(() => this.getChildControl("searching-collaborators").exclude());
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
      this.__addPotentialCollaborators();
    },

    __collaboratorButton: function(collaborator, preSelected = false) {
      const collaboratorButton = new osparc.filter.CollaboratorToggleButton(collaborator);
      collaboratorButton.groupId = collaborator.getGroupId();
      collaboratorButton.setValue(preSelected);
      if (!preSelected) {
        collaboratorButton.subscribeToFilterGroup("collaboratorsManager");
      }

      collaboratorButton.addListener("changeValue", e => {
        const selected = e.getData();
        if (selected) {
          this.__selectedCollaborators[collaborator.getGroupId()] = collaborator;
          collaboratorButton.unsubscribeToFilterGroup("collaboratorsManager");
        } else if (collaborator.getGroupId() in this.__selectedCollaborators) {
          delete this.__selectedCollaborators[collaborator.getGroupId()];
          collaboratorButton.subscribeToFilterGroup("collaboratorsManager");
        }
        this.getChildControl("share-button").setEnabled(Boolean(Object.keys(this.__selectedCollaborators).length));
      }, this);
      return collaboratorButton;
    },

    __addPotentialCollaborators: function(foundCollaborators = []) {
      const potentialCollaborators = Object.values(this.__potentialCollaborators).concat(foundCollaborators);
      const potentialCollaboratorList = this.getChildControl("potential-collaborators-list");

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
          console.log("already collaborator", potentialCollaborator.getLabel());
          return;
        }
        // do not list the potentialCollaborators that were selected
        console.log("selected?", potentialCollaborator.getGroupId(), this.__selectedCollaborators);
        if (potentialCollaborator.getGroupId() in this.__selectedCollaborators) {
          console.log("already selected", potentialCollaborator.getLabel());
          return;
        }
        // do not list the potentialCollaborators that were already listed
        if (potentialCollaboratorList.getChildren().find(c => "groupId" in c && c["groupId"] === potentialCollaborator.getGroupId())) {
          console.log("already listed", potentialCollaborator.getLabel());
          return;
        }
        // maybe, do not list the organizations
        if (this.__showOrganizations === false && potentialCollaborator["collabType"] !== 2) {
          return;
        }
        potentialCollaboratorList.add(this.__collaboratorButton(potentialCollaborator));
      });

      // move it to last position
      const searching = this.getChildControl("searching-collaborators");
      potentialCollaboratorList.remove(searching);
      potentialCollaboratorList.add(searching);
    },

    __shareClicked: function() {
      this.getChildControl("potential-collaborators-list").setEnabled(false);
      this.getChildControl("share-button").setFetching(true);

      if (Object.keys(this.__selectedCollaborators).length) {
        this.fireDataEvent("addCollaborators", Object.keys(this.__selectedCollaborators));
      }
    }
  }
});
