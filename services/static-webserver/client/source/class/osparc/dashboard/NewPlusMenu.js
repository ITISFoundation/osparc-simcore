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

/**
  Supports:
  "categories": [{
    "id": "string", // required
    "title": "string", // required
    "description": "string" // optional
  }],
  "resources": [{
    "resourceType": "study", // it will start an empty study
    "title": "string", // required
    "icon": "fontAwesome inner link | url", // optional
    "newStudyLabel": "string", // optional
    "idToWidget": "string" // optional
  }, {
    "resourceType": "template", // it will create a study from the template
    "expectedTemplateLabel": "string", // required
    "title": "string", // required
    "icon": "fontAwesome inner link | url", // optional
    "newStudyLabel": "string", // optional
    "category": "categories.id", // optional
    "idToWidget": "string" // optional
  }, {
    "resourceType": "service", // it will create a study from the service
    "expectedKey": "service.key", // required
    "title": "string", // required
    "icon": "fontAwesome inner link | url", // optional
    "newStudyLabel": "string", // optional
    "category": "categories.id", // optional
    "idToWidget": "string" // optional
  }, {
    "resourceType": "service", // it will create a study from the service
    "myMostUsed": 2, // required
    "category": "categories.id", // optional
  }, {
    "showDisabled": true, // it will show a disabled button on the defined item
    "title": "string", // required
    "icon": "fontAwesome inner link | url", // optional
    "reason": "string", // optional
    "newStudyLabel": "string", // optional
    "category": "categories.id", // optional
    "idToWidget": "string" // optional
  }]
 */
qx.Class.define("osparc.dashboard.NewPlusMenu", {
  extend: qx.ui.menu.Menu,

  construct: function() {
    this.base(arguments);

    this.set({
      appearance: "menu-wider",
      position: "bottom-left",
      spacingX: 20,
    });

    osparc.utils.Utils.setIdToWidget(this, "newPlusMenu");

    this.getContentElement().setStyles({
      "border-color": qx.theme.manager.Color.getInstance().resolve("strong-main"),
    });

    this.__categoryHeaders = [];

    this.__addItems();
  },

  events: {
    "createFolder": "qx.event.type.Data",
    "newEmptyStudyClicked": "qx.event.type.Data",
    "newStudyFromTemplateClicked": "qx.event.type.Data",
    "newStudyFromServiceClicked": "qx.event.type.Data",
  },

  statics: {
    createMenuButton: function(icon, title, infoText) {
      title = osparc.utils.Utils.replaceTokens(
        title,
        "replace_me_product_name",
        osparc.store.StaticInfo.getInstance().getDisplayName()
      );
      title = title.replace(/<br>/g, " ");
      const menuButton = new qx.ui.menu.Button().set({
        icon: icon || null,
        label: title,
        font: "text-16",
        allowGrowX: true,
      });
      menuButton.getChildControl("icon").set({
        alignX: "center",
      });
      menuButton.getChildControl("label").set({
        rich: true,
        marginRight: 20,
      });
      if (infoText) {
        infoText = osparc.utils.Utils.replaceTokens(
          infoText,
          "replace_me_product_name",
          osparc.store.StaticInfo.getInstance().getDisplayName()
        );
        const infoHint = new osparc.ui.hint.InfoHint(infoText).set({
          source: osparc.ui.hint.InfoHint.INFO_ICON + "/16",
        });
        // where the shortcut is supposed to go
        // eslint-disable-next-line no-underscore-dangle
        menuButton._add(infoHint, {column: 2});
      }
      return menuButton;
    },

    createHeader: function(icon, label, infoText) {
      return this.createMenuButton(icon, label, infoText).set({
        anonymous: true,
        cursor: "default",
        font: "text-14",
        textColor: "text-darker",
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
            osparc.dashboard.CardBase.NEW_ICON + "16",
            this.tr("New Folder"),
          );
          osparc.utils.Utils.setIdToWidget(control, "newFolderButton");
          control.addListener("tap", () => this.__createNewFolder());
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __addItems: async function() {
      this.getChildControl("new-folder");
      this.addSeparator();
      await this.__addNewStudyItems();
    },

    __addNewStudyItems: async function() {
      const plusButtonConfig = osparc.store.Products.getInstance().getPlusButtonUiConfig();
      if (plusButtonConfig) {
        await osparc.data.Resources.get("templates")
          .then(templates => {
            if (plusButtonConfig["categories"]) {
              this.__addCategories(plusButtonConfig["categories"]);
            }
            plusButtonConfig["resources"].forEach(newStudyData => {
              if (newStudyData["showDisabled"]) {
                this.__addDisabledButton(newStudyData);
              } else if (newStudyData["resourceType"] === "study") {
                this.__addEmptyStudyButton(newStudyData);
              } else if (newStudyData["resourceType"] === "template") {
                this.__addFromTemplateButton(newStudyData, templates);
              } else if (newStudyData["resourceType"] === "service") {
                this.__addFromServiceButton(newStudyData);
              }
            });
          });
      }
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
        const categoryHeader = this.self().createHeader(null, category["title"], category["description"]);
        categoryHeader["categoryId"] = category["id"];
        if (this.__categoryHeaders.length) {
          // add spacing between categories
          categoryHeader.setMarginTop(10);
        }
        this.__categoryHeaders.push(categoryHeader);
        this.add(categoryHeader);
      });
    },

    __addIcon: function(menuButton, resourceInfo, resourceMetadata) {
      let source = null;
      if (resourceInfo && resourceInfo["icon"]) {
        source = resourceInfo["icon"];
      } else {
        source = osparc.utils.Utils.getIconFromResource(resourceMetadata);
      }

      if (source) {
        const thumbnail = new osparc.ui.basic.Thumbnail(source, 24, 24).set({
          minHeight: 24,
          minWidth: 24,
        });
        thumbnail.getChildControl("image").set({
          anonymous: true,
          decorator: "rounded",
        });
        // eslint-disable-next-line no-underscore-dangle
        menuButton._add(thumbnail, {column: 0});
      }
    },

    __addFromResourceButton: function(menuButton, category) {
      let idx = null;
      if (category) {
        idx = this.__getLastIdxFromCategory(category);
      }
      if (idx) {
        menuButton["categoryId"] = category;
        this.addAt(menuButton, idx+1);
      } else {
        this.add(menuButton);
      }
    },

    __addDisabledButton: function(newStudyData) {
      const menuButton = this.self().createMenuButton(null, newStudyData["title"], newStudyData["reason"]);
      osparc.utils.Utils.setIdToWidget(menuButton, newStudyData["idToWidget"]);
      menuButton.setEnabled(false);

      this.__addIcon(menuButton, newStudyData);
      this.__addFromResourceButton(menuButton, newStudyData["category"]);
    },

    __addEmptyStudyButton: function(newStudyData) {
      const menuButton = this.self().createMenuButton(null, newStudyData["title"]);
      osparc.utils.Utils.setIdToWidget(menuButton, newStudyData["idToWidget"]);

      menuButton.addListener("tap", () => {
        this.fireDataEvent("newEmptyStudyClicked", {
          newStudyLabel: newStudyData["newStudyLabel"],
        });
      });

      this.__addIcon(menuButton, newStudyData);
      this.__addFromResourceButton(menuButton, newStudyData["category"]);
    },

    __addFromTemplateButton: function(newStudyData, templates) {
      const menuButton = this.self().createMenuButton(null, newStudyData["title"]);
      osparc.utils.Utils.setIdToWidget(menuButton, newStudyData["idToWidget"]);
      // disable it until found in templates store
      menuButton.setEnabled(false);

      let templateMetadata = templates.find(t => t.name === newStudyData["expectedTemplateLabel"]);
      if (templateMetadata) {
        menuButton.setEnabled(true);
        menuButton.addListener("tap", () => {
          this.fireDataEvent("newStudyFromTemplateClicked", {
            templateData: templateMetadata,
            newStudyLabel: newStudyData["newStudyLabel"],
          });
        });
        this.__addIcon(menuButton, newStudyData, templateMetadata);
        this.__addFromResourceButton(menuButton, newStudyData["category"]);
      }
    },

    __addFromServiceButton: function(newStudyData) {
      const addListenerToButton = (menuButton, latestMetadata) => {
        menuButton.addListener("tap", () => {
          this.fireDataEvent("newStudyFromServiceClicked", {
            serviceMetadata: latestMetadata,
            newStudyLabel: newStudyData["newStudyLabel"],
          });
        });

        const cb = e => {
          this.hide();
          // so that is not consumed by the menu button itself
          e.stopPropagation();
          latestMetadata["resourceType"] = "service";
          const resourceDetails = new osparc.dashboard.ResourceDetails(latestMetadata);
          osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
        }
        const infoButton = new osparc.ui.basic.IconButton(osparc.ui.hint.InfoHint.INFO_ICON + "/16", cb);
        // where the shortcut is supposed to go
        // eslint-disable-next-line no-underscore-dangle
        menuButton._add(infoButton, {column: 2});
      };

      if ("expectedKey" in newStudyData) {
        const menuButton = this.self().createMenuButton(null, newStudyData["title"]);
        osparc.utils.Utils.setIdToWidget(menuButton, newStudyData["idToWidget"]);
        // disable it until found in services store
        menuButton.setEnabled(false);

        const key = newStudyData["expectedKey"];
        const latestMetadata = osparc.store.Services.getLatest(key);
        if (!latestMetadata) {
          return;
        }
        menuButton.setEnabled(true);
        this.__addIcon(menuButton, newStudyData, latestMetadata);
        this.__addFromResourceButton(menuButton, newStudyData["category"]);
        addListenerToButton(menuButton, latestMetadata);
      } else if ("myMostUsed" in newStudyData) {
        const excludeFrontend = true;
        const excludeDeprecated = true
        osparc.store.Services.getServicesLatestList(excludeFrontend, excludeDeprecated)
          .then(servicesList => {
            osparc.service.Utils.sortObjectsBasedOn(servicesList, {
              "sort": "hits",
              "order": "down"
            });
            for (let i=0; i<newStudyData["myMostUsed"]; i++) {
              const latestMetadata = servicesList[i];
              if (latestMetadata && latestMetadata["hits"] > 0) {
                const menuButton = new qx.ui.menu.Button().set({
                  label: latestMetadata["name"],
                  font: "text-16",
                  allowGrowX: true,
                });
                this.__addIcon(menuButton, null, latestMetadata);
                this.__addFromResourceButton(menuButton, newStudyData["category"]);
                addListenerToButton(menuButton, latestMetadata);
              }
            }
          });
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
