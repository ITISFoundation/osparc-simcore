/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.WorkspaceEditor", {
  extend: qx.ui.core.Widget,

  construct: function(workspace) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    if (!workspace) {
      this.getChildControl("intro-text");
    }

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    const title = this.getChildControl("title");
    title.setRequired(true);
    manager.add(title);
    this.getChildControl("description");
    this.getChildControl("thumbnail");
    workspace ? this.getChildControl("save") : this.getChildControl("create");
    if (workspace) {
      this.__workspaceId = workspace.getWorkspaceId();
      this.set({
        label: workspace.getName(),
        description: workspace.getDescription(),
        thumbnail: workspace.getThumbnail(),
      });
    }

    this.addListener("appear", this.__onAppear, this);
  },

  properties: {
    label: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeLabel"
    },

    description: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeDescription"
    },

    thumbnail: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeThumbnail"
    },
  },

  events: {
    "workspaceCreated": "qx.event.type.Data",
    "workspaceUpdated": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __workspaceId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-text": {
          const studies = osparc.product.Utils.getStudyAlias({ plural: true });
          const text = this.tr(`A Shared Workspace is the context where all the ${studies} and folders are shared among its members.`);
          control = new qx.ui.basic.Label(text).set({
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        }
        case "title": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Title"),
            minHeight: 27
          });
          this.bind("label", control, "value");
          control.bind("value", this, "label");
          this._add(control);
          break;
        }
        case "description": {
          control = new qx.ui.form.TextArea().set({
            font: "text-14",
            placeholder: this.tr("Description"),
            autoSize: true,
            minHeight: 70,
          });
          this.bind("description", control, "value");
          control.bind("value", this, "description");
          this._add(control);
          break;
        }
        case "thumbnail": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("Thumbnail"),
          });
          this.bind("thumbnail", control, "value");
          control.bind("value", this, "thumbnail");
          this._add(control);
          break;
        }
        case "create": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Create")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            if (this.__validator.validate()) {
              this.__createWorkspaceClicked(control);
            }
          }, this);
          buttons.addAt(control, 1);
          break;
        }
        case "save": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            if (this.__validator.validate()) {
              this.__editWorkspace(control);
            }
          }, this);
          buttons.addAt(control, 1);
          break;
        }
        case "buttonsLayout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
            alignX: "right"
          }));
          const cancelButton = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text"
          });
          cancelButton.addListener("execute", () => this.fireEvent("cancel"), this);
          control.addAt(cancelButton, 0);
          this._add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __createWorkspaceClicked: function(createButton) {
      createButton.setFetching(true);
      this.__createWorkspace()
        .then(newWorkspace => this.fireDataEvent("workspaceCreated", newWorkspace))
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(err.message, "ERROR");
        })
        .finally(() => createButton.setFetching(false));
    },

    __createWorkspace: function() {
      const newWorkspaceData = {
        name: this.getLabel(),
        description: this.getDescription(),
        thumbnail: this.getThumbnail(),
      };
      return osparc.store.Workspaces.getInstance().postWorkspace(newWorkspaceData)
    },

    __editWorkspace: function(editButton) {
      editButton.setFetching(true);
      const updateData = {
        name: this.getLabel(),
        description: this.getDescription(),
        thumbnail: this.getThumbnail(),
      };
      osparc.store.Workspaces.getInstance().putWorkspace(this.__workspaceId, updateData)
        .then(() => this.fireEvent("workspaceUpdated"))
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(err.message, "ERROR");
        })
        .finally(() => editButton.setFetching(false));
    },

    __onAppear: function() {
      const title = this.getChildControl("title");
      title.focus();
      title.activate();
    }
  }
});
