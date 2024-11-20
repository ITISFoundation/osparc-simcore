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

qx.Class.define("osparc.editor.FolderEditor", {
  extend: qx.ui.core.Widget,

  construct: function(newFolder = true) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    const title = this.getChildControl("title");
    title.setRequired(true);
    manager.add(title);
    this.__doButton = newFolder ? this.getChildControl("create") : this.getChildControl("save");

    this.addListener("appear", this.__onAppear, this);
  },

  properties: {
    label: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeLabel"
    }
  },

  events: {
    "createFolder": "qx.event.type.Event",
    "updateFolder": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __doButton: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Title"),
            height: 27
          });
          osparc.utils.Utils.setIdToWidget(control, "folderEditorTitle");
          this.bind("label", control, "value");
          control.bind("value", this, "label");
          this._add(control);
          break;
        }
        case "create": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Create")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            const title = this.getChildControl("title");
            title.blur();
            if (this.__validator.validate()) {
              control.setFetching(true);
              this.fireEvent("createFolder");
            }
          }, this);
          osparc.utils.Utils.setIdToWidget(control, "folderEditorCreate");
          buttons.addAt(control, 1);
          break;
        }
        case "save": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            const title = this.getChildControl("title");
            title.blur();
            if (this.__validator.validate()) {
              control.setFetching(true);
              this.fireEvent("updateFolder");
            }
          }, this);
          osparc.utils.Utils.setIdToWidget(control, "folderEditorSave");
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

    __onAppear: function() {
      const title = this.getChildControl("title");
      title.focus();
      title.activate();

      const command = new qx.ui.command.Command("Enter");
      this.__doButton.setCommand(command);
    }
  }
});
