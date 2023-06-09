/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.editor.AnnotationNoteEditor", {
  extend: qx.ui.core.Widget,

  construct: function(newNote = true) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("instructions");
    this.getChildControl("destinatary");
    this.getChildControl("note");
    newNote ? this.getChildControl("add") : this.getChildControl("save");
  },

  properties: {
    destinatary: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeDestinatary"
    },

    note: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeNote"
    }
  },

  events: {
    "addNote": "qx.event.type.Event",
    "saveNote": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  statics: {
    popUpInWindow: function(noteEditor, newNote = true) {
      const title = newNote ? qx.locale.Manager.tr("Add Note") : qx.locale.Manager.tr("Edit Note");
      const win = osparc.ui.window.Window.popUpInWindow(noteEditor, title, 300, 210);
      win.center();
      win.open();
      return win;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "instructions":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Add a destinary and a notification will be sent"),
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        case "destinatary": {
          control = new qx.ui.form.Button(this.tr("Select destinatary")).set({
            allowGrowX: false
          });
          control.addListener("execute", () => {
            const collaboratorsManager = new osparc.component.share.NewCollaboratorsManager();
            collaboratorsManager.addListener("addCollaborators", e => {
              const collabs = e.getData();
              if (collabs) {
                console.log("addCollaborators", collabs);
                this.bind("destinatary", control, "value");
                control.bind("value", this, "destinatary");
              }
            }, this);
          }, this);
          this._add(control);
          break;
        }
        case "note": {
          control = new qx.ui.form.TextArea().set({
            font: "text-14",
            placeholder: this.tr("Note"),
            autoSize: true,
            minHeight: 70,
            maxHeight: 140
          });
          this.bind("note", control, "value");
          control.bind("value", this, "note");
          this._add(control);
          break;
        }
        case "buttonsLayout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
            alignX: "right"
          }));
          const cancelButton = new qx.ui.form.Button(this.tr("Cancel"));
          cancelButton.addListener("execute", () => this.fireEvent("cancel"), this);
          control.add(cancelButton);
          this._add(control);
          break;
        }
        case "add": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new qx.ui.form.Button(this.tr("Add"));
          control.addListener("execute", () => this.fireEvent("addNote"), this);
          buttons.addAt(control, 0);
          break;
        }
        case "save": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new qx.ui.form.Button(this.tr("Save"));
          control.addListener("execute", () => this.fireEvent("saveNote"), this);
          buttons.addAt(control, 0);
          break;
        }
      }

      return control || this.base(arguments, id);
    }
  }
});
