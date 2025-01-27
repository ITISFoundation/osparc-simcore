/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.NewPlusMenu", {
  extend: qx.ui.menu.Menu,

  construct: function() {
    this.base(arguments);

    osparc.utils.Utils.prettifyMenu(this);

    this.set({
      position: "bottom-left",
      padding: 10,
      allowGrowX: true,
    });

    this.__addItems();
  },

  events: {
    "createFolder": "qx.event.type.Data",
    "newStudyFromTemplateClicked": "qx.event.type.Data",
    "changeTab": "qx.event.type.Data",
  },

  statics: {
    createMenuButton: function(label, icon) {
      const menuButton = new qx.ui.menu.Button().set({
        label,
        icon: icon || null,
        font: "text-16",
        padding: 4,
      });
      menuButton.getChildControl("label").set({
        rich: true,
      });
      menuButton.getChildControl("icon").set({
        scale: true,
        maxHeight: 20,
        maxWidth: 20,
        allowShrinkX: true,
        allowShrinkY: true,
      });
      return menuButton;
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "new-folder":
          control = this.self().createMenuButton(
            this.tr("New Folder"),
            osparc.dashboard.CardBase.NEW_ICON + "16"
          );
          osparc.utils.Utils.setIdToWidget(control, "newFolderButton");
          control.addListener("tap", () => this.__createNewFolder());
          this.add(control);
          break;
        case "templates-entry":
          control = this.self().createMenuButton(
            osparc.product.Utils.getTemplateAlias({
              firstUpperCase: true,
              plural: true
            }),
            "@FontAwesome5Solid/copy/16"
          );
          control.addListener("tap", () => this.fireDataEvent("changeTab", "templatesTab"));
          this.add(control);
          break;
        case "services-entry":
          control = this.self().createMenuButton(
            this.tr("Services"),
            "@FontAwesome5Solid/cogs/16"
          );
          control.addListener("tap", () => this.fireDataEvent("changeTab", "servicesTab"));
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __addItems: async function() {
      this.getChildControl("new-folder");
      this.addSeparator();
      await this.__addNewStudyItems();
      const permissions = osparc.data.Permissions.getInstance();
      if (permissions.canDo("dashboard.templates.read") || permissions.canDo("dashboard.services.read")) {
        this.addSeparator();
        if (permissions.canDo("dashboard.templates.read")) {
          const templatesButton = this.getChildControl("templates-entry");
          this.add(templatesButton);
        }
        if (permissions.canDo("dashboard.services.read")) {
          const servicesButton = this.getChildControl("services-entry");
          this.add(servicesButton);
        }
      }
    },

    __addNewStudyItems: async function() {
      await Promise.all([
        osparc.store.Products.getInstance().getNewStudyConfig(),
        osparc.data.Resources.get("templates")
      ]).then(values => {
        const newStudiesData = values[0];
        const templates = values[1];
        if (newStudiesData["categories"]) {
          // this.__addCategories(newStudiesData["categories"]);
        }
        if (newStudiesData["linkedResource"] === "templates") {
          newStudiesData["resources"].forEach(templateData => {
            this.__addFromTemplateButton(templateData, templates);
          });
        }
      });
    },

    __addCategories: function(categories) {
      categories.forEach(category => {
        const categoryHeader = new qx.ui.basic.Label().set({
          value: category["label"],
          font: "text-16",
          rich: true,
          wrap: true,
        });
        categoryHeader.id = category["id"];
        this.add(categoryHeader);
      });
    },

    __addFromTemplateButton: function(templateData, templates) {
      const icon = "icon" in templateData ? templateData["icon"] : null;
      const menuButton = this.self().createMenuButton(templateData.title, icon);
      osparc.utils.Utils.setIdToWidget(menuButton, templateData.idToWidget);

      if (templateData.showDisabled) {
        if (templateData.showDisabled) {
          menuButton.set({
            enabled: false,
            toolTipText: templateData.description,
          });
        }
        this.add(menuButton);
        return;
      }

      const templateFound = templates.find(t => t.name === templateData.expectedTemplateLabel);
      if (templateFound) {
        if (menuButton.getIcon() === null && templateFound["thumbnail"]) {
          menuButton.setIcon(templateFound["thumbnail"]);
        }
        menuButton.addListener("tap", () => {
          this.fireDataEvent("newStudyFromTemplateClicked", {
            templateData: templateFound,
            newStudyLabel: templateData.newStudyLabel,
          });
        });
        this.add(menuButton);
      }
    },

    __createNewFolder: function() {
      const newFolder = true;
      const folderEditor = new osparc.editor.FolderEditor(newFolder);
      const title = this.tr("New Folder");
      const win = osparc.ui.window.Window.popUpInWindow(folderEditor, title, 300, 120);
      folderEditor.addListener("createFolder", () => {
        const name = folderEditor.getLabel();
        this.fireDataEvent("createFolder", {
          name,
        });
        win.close();
      });
      folderEditor.addListener("cancel", () => win.close());
    },
  },
});
