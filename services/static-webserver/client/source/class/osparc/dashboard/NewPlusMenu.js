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
    this.__itemIdx = 0;

    this.__addItems();
  },

  events: {
    "createFolder": "qx.event.type.Data",
    "changeTab": "qx.event.type.Data",
    "newEmptyStudyClicked": "qx.event.type.Data",
    "newStudyFromTemplateClicked": "qx.event.type.Data",
    "newStudyFromServiceClicked": "qx.event.type.Data",
  },

  statics: {
    MORE_ICON: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/refs/heads/main/app/icons/arrows.png",
    FOLDER_ICON: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/refs/heads/main/app/icons/folder.png",

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

    setIcon: function(menuButton, icon, resourceMetadata) {
      const source = icon ? icon : osparc.utils.Utils.getIconFromResource(resourceMetadata);
      if (source) {
        osparc.utils.Utils.replaceIconWithThumbnail(menuButton, source, 24);
      }
    },
  },

  members: {
    __categoryHeaders: null,
    __itemIdx: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "new-folder":
          this.addSeparator();
          control = this.self().createMenuButton(null, this.tr("New Folder"));
          this.self().setIcon(control, this.self().FOLDER_ICON);
          osparc.utils.Utils.setIdToWidget(control, "newFolderButton");
          control.addListener("tap", () => this.__createNewFolder());
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __addItems: function() {
      this.__addUIConfigItems();
      if (osparc.product.Utils.isS4LProduct()) {
        this.__addHypertools();
      }
      this.__addMoreMenu();
      this.getChildControl("new-folder");
    },

    __addUIConfigItems: function() {
      const plusButtonConfig = osparc.store.Products.getInstance().getPlusButtonUiConfig();
      if (plusButtonConfig) {
        if (plusButtonConfig["categories"]) {
          this.__addCategories(plusButtonConfig["categories"]);
        }
        plusButtonConfig["resources"].forEach(buttonConfig => {
          if (buttonConfig["showDisabled"]) {
            this.__addDisabledButton(buttonConfig);
          } else if (buttonConfig["resourceType"] === "study") {
            this.__addEmptyStudyButton(buttonConfig);
          } else if (buttonConfig["resourceType"] === "template") {
            this.__addFromTemplateButton(buttonConfig);
          } else if (buttonConfig["resourceType"] === "service") {
            this.__addFromServiceButton(buttonConfig);
          }
        });
      }
    },

    __addHypertools: function() {
      osparc.store.Templates.getHypertools()
        .then(hypertools => {
          if (hypertools.length) {
            const hypertoolsMenuButton = this.self().createMenuButton(null, this.tr("Hypertools"));
            this.addAt(hypertoolsMenuButton, this.__itemIdx);
            this.__itemIdx++;

            const hypertoolsMenu = new qx.ui.menu.Menu().set({
              appearance: "menu-wider",
            });
            hypertoolsMenuButton.setMenu(hypertoolsMenu);
            this.self().setIcon(hypertoolsMenuButton, osparc.data.model.StudyUI.HYPERTOOL_ICON);

            hypertools.forEach(templateData => {
              const hypertoolButton = this.self().createMenuButton(null, templateData["name"]);
              hypertoolButton.addListener("tap", () => {
                this.fireDataEvent("newStudyFromTemplateClicked", {
                  templateData,
                  newStudyLabel: templateData["name"],
                });
              });
              hypertoolsMenu.add(hypertoolButton);
              osparc.study.Utils.guessIcon(templateData)
                .then(iconSource => {
                  if (iconSource) {
                    const iconSize = 22;
                    hypertoolButton.getChildControl("icon").set({ minWidth: iconSize+2 });
                    osparc.utils.Utils.replaceIconWithThumbnail(hypertoolButton, iconSource, iconSize);
                  }
                });
            });
          }
        });
    },

    __addMoreMenu: function() {
      const moreMenuButton = this.self().createMenuButton(null, this.tr("More"));
      this.addAt(moreMenuButton, this.__itemIdx);
      this.__itemIdx++;

      const moreMenu = new qx.ui.menu.Menu().set({
        appearance: "menu-wider",
      });
      moreMenuButton.setMenu(moreMenu);
      this.self().setIcon(moreMenuButton, this.self().MORE_ICON);

      const permissions = osparc.data.Permissions.getInstance();
      if (permissions.canDo("dashboard.templates.read")) {
        const tutorialsButton = this.self().createMenuButton("@FontAwesome5Solid/copy/16", this.tr("Tutorials..."));
        tutorialsButton.addListener("execute", () => this.fireDataEvent("changeTab", "tutorialsTab"), this);
        moreMenu.add(tutorialsButton);
      }

      if (permissions.canDo("dashboard.services.read")) {
        const servicesButton = this.self().createMenuButton("@FontAwesome5Solid/cog/16", this.tr("Apps..."));
        servicesButton.addListener("execute", () => this.fireDataEvent("changeTab", "appsTab"), this);
        moreMenu.add(servicesButton);
      }
      moreMenuButton.setVisibility(moreMenu.getChildren().length ? "visible" : "excluded");
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

    __addFromResourceButton: function(menuButton, category, idx = null) {
      if (category) {
        idx = this.__getLastIdxFromCategory(category);
      }
      if (category && idx) {
        menuButton["categoryId"] = category;
        this.addAt(menuButton, idx+1);
      } else if (idx) {
        this.addAt(menuButton, idx);
      } else {
        this.addAt(menuButton, this.__itemIdx);
        this.__itemIdx++;
      }
    },

    __addDisabledButton: function(buttonConfig) {
      const menuButton = this.self().createMenuButton(null, buttonConfig["title"], buttonConfig["reason"]);
      osparc.utils.Utils.setIdToWidget(menuButton, buttonConfig["idToWidget"]);
      menuButton.setEnabled(false);

      this.self().setIcon(menuButton, buttonConfig["icon"]);
      this.__addFromResourceButton(menuButton, buttonConfig["category"]);
    },

    __addEmptyStudyButton: function(buttonConfig = {}) {
      if (this.__emptyPipelineButton) {
        return;
      }

      const menuButton = this.__emptyPipelineButton = this.self().createMenuButton(null, buttonConfig["title"] || "Empty Pipeline");
      osparc.utils.Utils.setIdToWidget(menuButton, buttonConfig["idToWidget"] || "emptyStudyBtn");

      menuButton.addListener("tap", () => {
        this.fireDataEvent("newEmptyStudyClicked", {
          newStudyLabel: buttonConfig["newStudyLabel"] || "Empty Pipeline",
        });
      });

      this.self().setIcon(menuButton, buttonConfig["icon"] || osparc.data.model.StudyUI.PIPELINE_ICON);
      this.__addFromResourceButton(menuButton, buttonConfig["category"]);
    },

    __addFromTemplateButton: function(buttonConfig) {
      osparc.store.Templates.getHypertools()
        .then(hypertools => {
          const menuButton = this.self().createMenuButton(null, buttonConfig["title"]);
          osparc.utils.Utils.setIdToWidget(menuButton, buttonConfig["idToWidget"]);
          // disable it until found in templates store
          menuButton.setEnabled(false);

          let templateMetadata = hypertools.find(t => t.name === buttonConfig["expectedTemplateLabel"]);
          if (templateMetadata) {
            menuButton.setEnabled(true);
            menuButton.addListener("tap", () => {
              this.fireDataEvent("newStudyFromTemplateClicked", {
                templateData: templateMetadata,
                newStudyLabel: buttonConfig["newStudyLabel"],
              });
            });
            this.self().setIcon(menuButton, buttonConfig["icon"], templateMetadata);
            this.__addFromResourceButton(menuButton, buttonConfig["category"]);
          }
        });
    },

    __addFromServiceButton: function(buttonConfig) {
      const addListenerToButton = (menuButton, latestMetadata) => {
        menuButton.addListener("tap", () => {
          this.fireDataEvent("newStudyFromServiceClicked", {
            serviceMetadata: latestMetadata,
            newStudyLabel: buttonConfig["newStudyLabel"],
          });
        });

        const cb = e => {
          this.hide();
          // so that is not consumed by the menu button itself
          e.stopPropagation();
          latestMetadata["resourceType"] = "service";
          const resourceDetails = new osparc.dashboard.ResourceDetails(latestMetadata);
          const win = osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
          resourceDetails.addListener("openService", ev => {
            win.close();
            const openServiceData = ev.getData();
            this.fireDataEvent("newStudyFromServiceClicked", {
              serviceMetadata: openServiceData,
              newStudyLabel: buttonConfig["newStudyLabel"],
            });
          });
        }
        const infoButton = new osparc.ui.basic.IconButton(osparc.ui.hint.InfoHint.INFO_ICON + "/16", cb);
        // where the shortcut is supposed to go
        // eslint-disable-next-line no-underscore-dangle
        menuButton._add(infoButton, {column: 2});
      };

      if ("expectedKey" in buttonConfig) {
        const menuButton = this.self().createMenuButton(null, buttonConfig["title"]);
        osparc.utils.Utils.setIdToWidget(menuButton, buttonConfig["idToWidget"]);
        // disable it until found in services store
        menuButton.setEnabled(false);

        const key = buttonConfig["expectedKey"];
        const latestMetadata = osparc.store.Services.getLatest(key);
        if (!latestMetadata) {
          return;
        }
        menuButton.setEnabled(true);
        this.self().setIcon(menuButton, buttonConfig["icon"], latestMetadata);
        this.__addFromResourceButton(menuButton, buttonConfig["category"]);
        addListenerToButton(menuButton, latestMetadata);
      } else if ("myMostUsed" in buttonConfig) {
        const excludeFrontend = true;
        const excludeDeprecated = true;
        const old = this.__itemIdx;
        this.__itemIdx += buttonConfig["myMostUsed"];
        osparc.store.Services.getServicesLatestList(excludeFrontend, excludeDeprecated)
          .then(srvList => {
            const servicesList = srvList.filter(srv => srv !== null);
            osparc.service.Utils.sortObjectsBasedOn(servicesList, {
              "sort": "hits",
              "order": "down"
            });
            for (let i=0; i<buttonConfig["myMostUsed"]; i++) {
              const latestMetadata = servicesList[i];
              if (latestMetadata && latestMetadata["hits"] > 0) {
                const menuButton = new qx.ui.menu.Button().set({
                  label: latestMetadata["name"],
                  font: "text-16",
                  allowGrowX: true,
                });
                this.self().setIcon(menuButton, null, latestMetadata);
                this.__addFromResourceButton(menuButton, buttonConfig["category"], old+i);
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
