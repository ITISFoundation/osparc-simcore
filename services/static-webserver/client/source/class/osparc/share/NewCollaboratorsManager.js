/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.share.NewCollaboratorsManager", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function(resourceData, showOrganizations = true, showAccessRights = true, preselectCollaboratorGids = []) {
    this.base(arguments, "newCollaboratorsManager", this.tr("New collaborators"));

    this.set({
      layout: new qx.ui.layout.VBox(5),
      allowMinimize: false,
      allowMaximize: false,
      showMinimize: false,
      showMaximize: false,
      autoDestroy: true,
      modal: true,
      width: 330,
      maxHeight: 500,
      clickAwayClose: true
    });

    this.__resourceData = resourceData;
    this.__showOrganizations = showOrganizations;
    this.__showAccessRights = showAccessRights;

    this.__renderLayout();

    this.__selectedCollaborators = {};
    this.__potentialCollaborators = {};
    this.__reloadPotentialCollaborators();

    this.__shareWithEmailEnabled = this.__resourceData["resourceType"] === "study";

    if (preselectCollaboratorGids && preselectCollaboratorGids.length) {
      preselectCollaboratorGids.forEach(preselectCollaboratorGid => {
        const potentialCollaboratorList = this.getChildControl("potential-collaborators-list");
        const found = potentialCollaboratorList.getChildren().find(c => "groupId" in c && c["groupId"] === preselectCollaboratorGid)
        if (found) {
          found.setValue(true);
        }
      });
    }

    this.center();
    this.open();
  },

  events: {
    "addCollaborators": "qx.event.type.Data",
    "shareWithEmails": "qx.event.type.Data",
  },

  properties: {
    acceptOnlyOne: {
      check: "Boolean",
      init: false,
      event: "changeAcceptOnlyOne"
    }
  },

  members: {
    __resourceData: null,
    __showOrganizations: null,
    __showAccessRights: null,
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
        case "filter-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this.add(control);
          break;
        case "text-filter": {
          control = new osparc.filter.TextFilter("name", "collaboratorsManager");
          control.setCompact(true);
          const filterTextField = control.getChildControl("textfield");
          filterTextField.setPlaceholder(this.tr("Search"));
          filterTextField.setBackgroundColor("transparent");
          this.addListener("appear", () => filterTextField.focus());
          this.getChildControl("filter-layout").add(control, {
            flex: 1
          });
          break;
        }
        case "send-email-button": {
          control = new qx.ui.form.Button(this.tr("Send email"));
          control.exclude();
          control.addListener("execute", () => {
            const textField = this.getChildControl("text-filter").getChildControl("textfield");
            const email = textField.getValue();
            if (osparc.auth.core.Utils.checkEmail(email)) {
              const invitedButton = this.__invitedButton(email);
              this.getChildControl("potential-collaborators-list").addAt(invitedButton, 0);
              invitedButton.setValue(true);
            }
          });
          this.getChildControl("filter-layout").add(control);
          break;
        }
        case "potential-collaborators-list": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
            minHeight: 160,
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
          const title = new qx.ui.basic.Label(this.tr("Set the following Role:"));
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
        const inputValue = e.getData();
        if (this.__searchDelayer) {
          clearTimeout(this.__searchDelayer);
        }
        const sendEmailButton = this.getChildControl("send-email-button");
        sendEmailButton.exclude();
        if (inputValue.length > 3) {
          if (this.__shareWithEmailEnabled) {
            if (osparc.auth.core.Utils.checkEmail(inputValue)) {
              sendEmailButton.show();
            }
          }
          const waitBeforeSearching = 1000;
          this.__searchDelayer = setTimeout(() => {
            this.__searchUsers();
          }, waitBeforeSearching);
        }
      });

      this.getChildControl("potential-collaborators-list");
      this.getChildControl("searching-collaborators");

      if (this.__resourceData["resourceType"] === "study" && this.__showAccessRights) {
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
      } else if (this.__resourceData) {
        switch (this.__resourceData["resourceType"]) {
          case "study":
            // studies can't be shared with ProductEveryone
            showProductEveryone = false;
            break;
          case "template":
          case "tutorial":
            // only users with permissions can share templates with ProductEveryone
            showProductEveryone = osparc.data.Permissions.getInstance().canDo("study.everyone.share");
            break;
          case "service":
            // all users can share services with ProductEveryone
            showProductEveryone = true;
            break;
          case "hypertool":
            // all users can share hypertool with ProductEveryone
            showProductEveryone = true;
            break;
        }
      }
      return showProductEveryone;
    },

    __reloadPotentialCollaborators: function() {
      const includeProductEveryone = this.__showProductEveryone();
      this.__potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators(false, includeProductEveryone);
      this.__addPotentialCollaborators();
    },

    __collaboratorButton: function(collaborator) {
      const collaboratorButton = new osparc.filter.CollaboratorToggleButton(collaborator);
      collaborator.button = collaboratorButton;
      collaboratorButton.groupId = collaborator.getGroupId();
      collaboratorButton.subscribeToFilterGroup("collaboratorsManager");

      collaboratorButton.addListener("changeValue", e => {
        const selected = e.getData();
        this.__collaboratorSelected(selected, collaborator.getGroupId(), collaborator, collaboratorButton);
      }, this);
      return collaboratorButton;
    },

    __invitedButton: function(email) {
      if (email in this.__selectedCollaborators) {
        return this.__selectedCollaborators[email];
      }

      const collaboratorData = {
        label: email,
        email: email,
        description: null,
      };
      const collaborator = qx.data.marshal.Json.createModel(collaboratorData);
      const collaboratorButton = new osparc.filter.CollaboratorToggleButton(collaborator);
      collaborator.button = collaboratorButton;
      collaboratorButton.setIconSrc("@FontAwesome5Solid/envelope/14");

      collaboratorButton.addListener("changeValue", e => {
        const selected = e.getData();
        this.__collaboratorSelected(selected, collaborator.getEmail(), collaborator, collaboratorButton);
      }, this);
      return collaboratorButton;
    },

    __collaboratorSelected: function(selected, collaboratorGidOrEmail, collaborator, collaboratorButton) {
      if (selected) {
        if (this.isAcceptOnlyOne() && Object.keys(this.__selectedCollaborators).length) {
          // unselect the previous collaborator
          const id = Object.keys(this.__selectedCollaborators)[0];
          this.__selectedCollaborators[id].button.setValue(false);
        }
        this.__selectedCollaborators[collaboratorGidOrEmail] = collaborator;
        collaboratorButton.unsubscribeToFilterGroup("collaboratorsManager");
      } else if (collaborator.getGroupId() in this.__selectedCollaborators) {
        delete this.__selectedCollaborators[collaboratorGidOrEmail];
        collaboratorButton.subscribeToFilterGroup("collaboratorsManager");
      }
      this.getChildControl("share-button").setEnabled(Boolean(Object.keys(this.__selectedCollaborators).length));
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
          return;
        }
        // do not list the potentialCollaborators that were selected
        if (potentialCollaborator.getGroupId() in this.__selectedCollaborators) {
          return;
        }
        // do not list the potentialCollaborators that were already listed
        if (potentialCollaboratorList.getChildren().find(c => "groupId" in c && c["groupId"] === potentialCollaborator.getGroupId())) {
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

      let newAccessRights = null;
      if (this.__resourceData["resourceType"] === "study") {
        const selected = this.getChildControl("access-rights-selector").getSelection()[0];
        if (selected) {
          newAccessRights = osparc.data.Roles.STUDY[selected.getModel()].accessRights;
        }
      }
      if (Object.keys(this.__selectedCollaborators).length) {
        const selectedGIds = Object.keys(this.__selectedCollaborators).filter(key => /^\d+$/.test(key)); // all digits
        const selectedEmails = Object.keys(this.__selectedCollaborators).filter(key => osparc.auth.core.Utils.checkEmail(key));

        const addCollaborators = () => {
          if (selectedGIds.length) {
            this.fireDataEvent("addCollaborators", {
              selectedGids: selectedGIds,
              newAccessRights,
            });
          }
        };

        const sendEmails = message => {
          if (selectedEmails.length) {
            this.fireDataEvent("shareWithEmails", {
              selectedEmails,
              newAccessRights,
              message,
            });
          }
        };

        if (selectedEmails.length) {
          const dialog = new osparc.ui.window.Confirmation();
          dialog.setCaption(this.tr("Add Message"));
          dialog.setMessage(this.tr("Add a message to include in the email (optional)"));
          dialog.getConfirmButton().setLabel(this.tr("Send"));
          const messageEditor = new qx.ui.form.TextArea().set({
            autoSize: true,
            minHeight: 70,
            maxHeight: 140,
          });
          dialog.addWidget(messageEditor);
          dialog.open();
          dialog.addListener("close", () => {
            addCollaborators();
            sendEmails(messageEditor.getValue());
          }, this);
        } else {
          addCollaborators();
        }
      }
    }
  }
});
