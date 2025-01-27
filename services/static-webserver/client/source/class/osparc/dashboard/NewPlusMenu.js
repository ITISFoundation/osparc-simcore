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
      padding: 8,
    });

    this.__categoryHeaders = [];

    this.__addItems();
  },

  events: {
    "createFolder": "qx.event.type.Data",
    "newStudyFromTemplateClicked": "qx.event.type.Data",
    "newStudyFromServiceClicked": "qx.event.type.Data",
    "changeTab": "qx.event.type.Data",
  },

  statics: {
    createMenuButton: function(label, icon, description) {
      const menuButton = new qx.ui.menu.Button().set({
        label,
        icon: icon || null,
        font: "text-16",
        allowGrowX: true,
      });
      menuButton.getChildControl("label").set({
        rich: true,
        allowGrowX: true,
        wrap: false,
      });
      if (description) {
        const infoHint = new osparc.ui.hint.InfoHint(description).set({
          source: osparc.ui.hint.InfoHint.INFO_ICON + "/16",
          alignY: "middle",
        });
        // where the shortcut is supposed to go
        // eslint-disable-next-line no-underscore-dangle
        menuButton._add(infoHint, {
          column: 2
        });
      }
      return menuButton;
    },

    createHeader: function(label, icon, description) {
      const headerLabel = `--- ${label} ---`;
      return this.createMenuButton(headerLabel, icon, description).set({
        anonymous: true,
        cursor: "default",
        font: "text-16",
      });
    },
  },

  members: {
    __categoryHeaders: null,

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
          this.__addCategories(newStudiesData["categories"]);
        }
        newStudiesData["resources"].forEach(resourceData => {
          if (resourceData["resourceType"] === "template") {
            this.__addFromTemplateButton(resourceData, templates);
          } else if (resourceData["resourceType"] === "service") {
            this.__addFromServiceButton(resourceData);
          }
        });
      });
    },

    __getLastIdxFromCategory: function(categoryId) {
      for (let i=this.getChildren().length-1; i>=0; i--) {
        const child = this.getChildren()[i];
        if (child && child["categoryId"] && child["categoryId"] === categoryId) {
          return i;
        }
      }
      return null;
    },

    __addCategories: function(categories) {
      categories.forEach(category => {
        const categoryHeader = this.self().createHeader(category["title"], null, category["description"]);
        categoryHeader["categoryId"] = category["id"];
        this.__categoryHeaders.push(categoryHeader);
        this.add(categoryHeader);
      });
    },

    __createFromResourceButton: function(resourceData) {
      const icon = "icon" in resourceData ? resourceData["icon"] : null;
      const menuButton = this.self().createMenuButton(resourceData.title, icon);
      osparc.utils.Utils.setIdToWidget(menuButton, resourceData.idToWidget);
      return menuButton;
    },

    __addFromResourceButton: function(menuButton, resourceData) {
      if (menuButton.getIcon()) {
        menuButton.getChildControl("icon").set({
          scale: true,
          maxWidth: 22,
          maxHeight: 22,
        })
      }

      let idx = null;
      if (resourceData.category) {
        idx = this.__getLastIdxFromCategory(resourceData.category);
      }
      if (idx) {
        menuButton["categoryId"] = resourceData.category;
        this.addAt(menuButton, idx+1);
      } else {
        this.add(menuButton);
      }
    },

    __addFromTemplateButton: function(templateData, templates) {
      const menuButton = this.__createFromResourceButton(templateData);

      if (templateData.showDisabled) {
        menuButton.set({
          enabled: false,
          toolTipText: templateData.description,
        });
      } else {
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
        }
      }

      this.__addFromResourceButton(menuButton, templateData);
    },

    __addFromServiceButton: function(serviceData) {
      const menuButton = this.__createFromResourceButton(serviceData);
      // disable it until found in services store
      menuButton.setEnabled(false);

      const key = serviceData.expectedKey;
      // Include deprecated versions, they should all be updatable to a non deprecated version
      const versions = osparc.service.Utils.getVersions(key, false);
      if (versions.length && serviceData) {
        // scale to latest compatible
        const latestVersion = versions[0];
        const latestCompatible = osparc.service.Utils.getLatestCompatible(key, latestVersion);
        osparc.store.Services.getService(latestCompatible["key"], latestCompatible["version"])
          .then(latestMetadata => {
            // make sure this one is not deprecated
            if (osparc.service.Utils.isDeprecated(latestMetadata)) {
              return;
            }
            menuButton.setEnabled(true);
            if (menuButton.getIcon() === null && latestMetadata["thumbnail"]) {
              menuButton.setIcon(latestMetadata["thumbnail"]);
            }
            menuButton.addListener("tap", () => {
              this.fireDataEvent("newStudyFromServiceClicked", {
                serviceMetadata: latestMetadata,
                newStudyLabel: serviceData.newStudyLabel,
              });
            });
          })
      }

      this.__addFromResourceButton(menuButton, serviceData);
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
