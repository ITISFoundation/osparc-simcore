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
  extend: osparc.ui.window.Window,

  construct: function(organization) {
    const caption = organization ? this.tr("Edit Organization") : this.tr("New Organization");
    this.base(arguments, caption);

    this.set({
      layout: new qx.ui.layout.VBox(10),
      autoDestroy: true,
      modal: true,
      showMaximize: false,
      showMinimize: false,
      width: 400,
      clickAwayClose: true,
    });

    const form = this.__form = new qx.ui.form.Form();
    const formRenderer = new qx.ui.form.renderer.Single(form).set({
      font: "text-14",
    });
    this.add(formRenderer, {
      flex: 1
    });

    const label = this.getChildControl("label");
    this.getChildControl("description");
    this.getChildControl("thumbnail");
    organization ? this.getChildControl("save-button") : this.getChildControl("create-button");

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
      label.setValue(defaultName);
    }

    this.addListener("appear", () => {
      label.focus();
      label.activate();
    });

    this.center();
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
  },

  members: {
    __form: null,
    __validator: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "label":
          control = new qx.ui.form.TextField().set({
            appearance: "form-input",
            required: true,
            allowGrowX: true,
          });
          this.bind("label", control, "value");
          control.bind("value", this, "label");
          this.__form.add(control, this.tr("Title"), null, "title");
          break;
        case "description":
          control = new qx.ui.form.TextField().set({
            appearance: "form-input",
            required: true,
            allowGrowX: true,
          });
          this.bind("description", control, "value");
          control.bind("value", this, "description");
          this.__form.add(control, this.tr("Description"), null, "description");
          break;
        case "thumbnail":
          control = new qx.ui.form.TextField().set({
            appearance: "form-input",
            allowGrowX: true,
          });
          this.bind("thumbnail", control, "value");
          control.bind("value", this, "thumbnail");
          this.__form.add(control, this.tr("Thumbnail"), null, "thumbnail");
          break;
        case "create-button": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Create")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            if (this.__form.validate()) {
              control.setFetching(true);
              this.fireEvent("createOrg");
            }
          }, this);
          buttons.addAt(control, 1);
          break;
        }
        case "save-button": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            if (this.__form.validate()) {
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
          cancelButton.addListener("execute", () => this.close());
          control.addAt(cancelButton, 0);
          this.add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    }
  }
});
