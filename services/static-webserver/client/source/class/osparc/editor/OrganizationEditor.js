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

qx.Class.define("osparc.editor.OrganizationEditor", {
  extend: qx.ui.core.Widget,

  construct: function(organization) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    const title = this.getChildControl("title");
    title.setRequired(true);
    manager.add(title);
    this.getChildControl("description");
    this.getChildControl("thumbnail");
    organization ? this.getChildControl("save") : this.getChildControl("create");

    if (organization) {
      organization.bind("groupId", this, "gid");
      organization.bind("label", this, "label");
      organization.bind("description", this, "description");
      organization.bind("thumbnail", this, "thumbnail", {
        converter: val => val ? val : ""
      });
    } else {
      const groupsStore = osparc.store.Groups.getInstance();
      const orgs = groupsStore.getOrganizations();
      const existingNames = Object.values(orgs).map(org => org.getLabel());
      const defaultName = osparc.utils.Utils.getUniqueName("New Organization", existingNames)
      title.setValue(defaultName);
    }

    this.addListener("appear", () => {
      title.focus();
      title.activate();
    });
  },

  properties: {
    gid: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeGid"
    },

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
    }
  },

  events: {
    "createOrg": "qx.event.type.Event",
    "updateOrg": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("Title"),
            height: 30,
          });
          this.bind("label", control, "value");
          control.bind("value", this, "label");
          this._add(control);
          break;
        }
        case "description": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("Description"),
            height: 30,
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
            height: 30,
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
              control.setFetching(true);
              this.fireEvent("createOrg");
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
              control.setFetching(true);
              this.fireEvent("updateOrg");
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
    }
  }
});
