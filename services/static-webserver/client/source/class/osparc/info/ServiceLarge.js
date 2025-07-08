/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.info.ServiceLarge", {
  extend: osparc.info.CardLarge,

  /**
    * @param metadata {Object} Serialized Service Object
    * @param instance {Object} instance related data
    * @param openOptions {Boolean} open edit options in new window or fire event
    */
  construct: function(metadata, instance = null, openOptions = true) {
    this.base(arguments);

    this.setService(metadata);

    if (instance) {
      if ("nodeId" in instance) {
        this.setNodeId(instance["nodeId"]);
      }
      if ("label" in instance) {
        this.setInstanceLabel(instance["label"]);
      }
      if ("studyId" in instance) {
        this.setStudyId(instance["studyId"]);
      }
    }

    if (openOptions !== undefined) {
      this.setOpenOptions(openOptions);
    }

    this._attachHandlers();
  },

  events: {
    "updateService": "qx.event.type.Data"
  },

  properties: {
    service: {
      check: "Object",
      init: null,
      nullable: false,
      apply: "_rebuildLayout"
    },

    nodeId: {
      check: "String",
      init: null,
      nullable: true
    },

    instanceLabel: {
      check: "String",
      init: null,
      nullable: true
    },

    studyId: {
      check: "String",
      init: null,
      nullable: true
    }
  },

  statics: {
    popUpInWindow: function(serviceLarge) {
      const metadata = serviceLarge.getService();
      const versionDisplay = osparc.service.Utils.extractVersionDisplay(metadata);
      const title = `${metadata["name"]} ${versionDisplay}`;
      const width = osparc.info.CardLarge.WIDTH;
      const height = osparc.info.CardLarge.HEIGHT;
      osparc.ui.window.Window.popUpInWindow(serviceLarge, title, width, height).set({
        maxHeight: height
      });
    },
  },

  members: {
    _rebuildLayout: function() {
      this._removeAll();

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const deprecated = this.__createDeprecated();
      if (deprecated) {
        vBox.add(deprecated);
      }

      const copyMetadataButton = new qx.ui.form.Button(this.tr("Copy Raw metadata"), "@FontAwesome5Solid/copy/12").set({
        allowGrowX: false
      });
      copyMetadataButton.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(osparc.utils.Utils.prettifyJson(this.getService())), this);

      if (
        this.getService()["descriptionUi"] &&
        !osparc.service.Utils.canIWrite(this.getService()["accessRights"])
      ) {
        // In case of service instance, show also the copy Id buttons too
        const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
        if (this.getNodeId()) {
          const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
          const copyStudyIdButton = new qx.ui.form.Button(this.tr(`Copy ${studyAlias} Id`), "@FontAwesome5Solid/copy/12").set({
            toolTipText: qx.locale.Manager.tr("Copy to clipboard"),
          });
          copyStudyIdButton.addListener("execute", this.__copyStudyIdToClipboard, this);
          buttonsLayout.add(copyStudyIdButton);
          vBox.add(buttonsLayout);

          const copyNodeIdButton = new qx.ui.form.Button(this.tr("Copy Service Id"), "@FontAwesome5Solid/copy/12").set({
            toolTipText: qx.locale.Manager.tr("Copy to clipboard"),
          });
          copyNodeIdButton.addListener("execute", this.__copyNodeIdToClipboard, this);
          buttonsLayout.add(copyNodeIdButton);
          vBox.add(buttonsLayout);
        }

        // Show description only
        const description = this.__createDescription();
        vBox.add(description);
      } else {
        // Icon and title
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
        const icon = this.__createIcon();
        const iconLayout = this.__createViewWithEdit(icon, this.__openIconEditor);
        hBox.add(iconLayout);
        const title = this.__createName();
        const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
        hBox.add(titleLayout);
        vBox.add(hBox);

        // Rest of information
        const infoElements = this.__infoElements();
        const isStudy = false;
        const infoLayout = osparc.info.Utils.infoElementsToLayout(infoElements, isStudy);
        vBox.add(infoLayout);

        // Resources info if not billable
        if (!osparc.desktop.credits.Utils.areWalletsEnabled()) {
          const resources = this.__createResources();
          if (resources) {
            vBox.add(resources);
          }
        }
      }

      // Copy metadata button
      vBox.add(copyMetadataButton);

      // All in a scroll container
      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(vBox);

      this._add(scrollContainer, {
        flex: 1
      });
    },

    __createViewWithEdit: function(view, cb) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      layout.add(view);
      if (osparc.service.Utils.canIWrite(this.getService()["accessRights"])) {
        const editBtn = osparc.utils.Utils.getEditButton();
        editBtn.addListener("execute", () => cb.call(this), this);
        layout.add(editBtn);
      }

      return layout;
    },

    __createDeprecated: function() {
      const isDeprecated = osparc.service.Utils.isDeprecated(this.getService());
      const isRetired = osparc.service.Utils.isRetired(this.getService());
      if (isDeprecated) {
        return osparc.service.StatusUI.createServiceDeprecatedChip();
      } else if (isRetired) {
        return osparc.service.StatusUI.createServiceRetiredChip();
      }
      return null;
    },

    __createIcon: function() {
      const serviceIcon = this.getService()["icon"] || "osparc/no_photography_black_24dp.svg";
      const icon = osparc.dashboard.CardBase.createCardIcon().set({
        source: serviceIcon,
      });
      osparc.utils.Utils.setAltToImage(icon.getChildControl("image"), "card-icon");
      return icon;
    },

    __createName: function() {
      const serviceName = this.getService()["name"];
      let text = "";
      if (this.getInstanceLabel()) {
        text = `${this.getInstanceLabel()} [${serviceName}]`;
      } else {
        text = serviceName;
      }
      const title = osparc.info.ServiceUtils.createTitle(text).set({
        font: "text-14"
      });
      return title;
    },

    __infoElements: function() {
      const canIWrite = osparc.service.Utils.canIWrite(this.getService()["accessRights"]);

      const infoLayout = {
        "THUMBNAIL": {
          view: this.__createThumbnail(),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openThumbnailEditor : null,
            ctx: this,
          },
        },
        "KEY": {
          label: this.tr("Key"),
          view: this.__createKey(),
          action: {
            button: osparc.utils.Utils.getCopyButton(),
            callback: this.__copyKeyToClipboard,
            ctx: this,
          },
        },
        "VERSION": {
          label: this.tr("Version"),
          view: this.__createDisplayVersion(),
          action: {
            button: canIWrite ? osparc.utils.Utils.getEditButton() : null,
            callback: this.__openVersionDisplayEditor,
            ctx: this,
          },
        },
        "DATE": {
          label: this.tr("Released Date"),
          view: this.__createReleasedDate(),
          action: null,
        },
        "CONTACT": {
          label: this.tr("Contact"),
          view: this.__createContact(),
          action: null,
        },
        "AUTHORS": {
          label: this.tr("Authors"),
          view: this.__createAuthors(),
          action: null,
        },
        "ACCESS_RIGHTS": {
          label: this.tr("Access"),
          view: this.__createAccessRights(),
          action: {
            button: canIWrite ? osparc.utils.Utils.getEditButton() : null,
            callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
            ctx: this,
          },
        },
        "DESCRIPTION": {
          view: this.__createDescription(),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openDescriptionEditor : null,
            ctx: this,
          },
        },
      };

      if (this.getNodeId()) {
        infoLayout["SERVICE_ID"] = {
          label: this.tr("Service ID"),
          view: this.__createNodeId(),
          action: {
            button: osparc.utils.Utils.getCopyButton(),
            callback: this.__copyNodeIdToClipboard,
            ctx: this
          },
        };
      }

      if (osparc.data.Permissions.getInstance().isTester() || canIWrite) {
        infoLayout["INTEGRATION_VERSION"] = {
          label: this.tr("Integration Version"),
          view: this.__createIntegrationVersion(),
          action: null,
        };
      }

      if (canIWrite) {
        infoLayout["DESCRIPTION_ONLY"] = {
          label: this.tr("Description only"),
          view: this.__createDescriptionUi(),
          action: null,
        };
      }

      return infoLayout;
    },

    __createNodeId: function() {
      return osparc.info.ServiceUtils.createNodeId(this.getNodeId());
    },

    __createKey: function() {
      return osparc.info.ServiceUtils.createKey(this.getService()["key"]);
    },

    __createIntegrationVersion: function() {
      return osparc.info.ServiceUtils.createVersion(this.getService()["version"]);
    },

    __createDisplayVersion: function() {
      return osparc.info.ServiceUtils.createVersionDisplay(this.getService()["key"], this.getService()["version"]);
    },

    __createReleasedDate: function() {
      return osparc.info.ServiceUtils.createReleasedDate(this.getService()["key"], this.getService()["version"]);
    },

    __createContact: function() {
      return osparc.info.ServiceUtils.createContact(this.getService());
    },

    __createAuthors: function() {
      return osparc.info.ServiceUtils.createAuthors(this.getService());
    },

    __createAccessRights: function() {
      return osparc.info.ServiceUtils.createAccessRights(this.getService());
    },

    __createThumbnail: function() {
      let maxWidth = 190;
      let maxHeight = 220;
      // make sure maxs are not larger than the mins
      const minWidth = Math.max(120, maxWidth);
      const minHeight = Math.max(139, maxHeight);
      maxWidth = Math.max(minWidth, maxWidth);
      maxHeight = Math.max(minHeight, maxHeight);

      const serviceData = this.getService();
      const thumbnail = osparc.info.Utils.createThumbnail(maxWidth, maxHeight);
      if (serviceData["thumbnail"]) {
        thumbnail.set({
          source: serviceData["thumbnail"]
        });
      } else {
        const noThumbnail = "osparc/no_photography_black_24dp.svg";
        thumbnail.set({
          source: noThumbnail
        });
        thumbnail.getChildControl("image").set({
          minWidth,
          minHeight,
        });
      }
      return thumbnail;
    },

    __createDescriptionUi: function() {
      const cbAutoPorts = new qx.ui.form.CheckBox().set({
        toolTipText: this.tr("From all the metadata shown in this view,\nonly the Description will be shown to Users."),
      });
      cbAutoPorts.setValue(Boolean(this.getService()["descriptionUi"]));
      cbAutoPorts.addListener("changeValue", e => {
        this.__patchService("descriptionUi", e.getData());
      });
      return cbAutoPorts;
    },

    __createDescription: function() {
      return osparc.info.ServiceUtils.createDescription(this.getService());
    },

    __createResources: function() {
      const resourcesLayout = osparc.info.ServiceUtils.createResourcesInfoCompact();
      resourcesLayout.exclude();
      let promise = null;
      if (this.getNodeId()) {
        promise = osparc.store.Study.getNodeResources(this.getStudyId(), this.getNodeId());
      } else {
        promise = osparc.store.Services.getResources(this.getService()["key"], this.getService()["version"])
      }
      promise
        .then(serviceResources => {
          resourcesLayout.show();
          osparc.info.ServiceUtils.resourcesToResourcesInfoCompact(resourcesLayout, serviceResources);
        })
        .catch(err => console.error(err));
      return resourcesLayout;
    },

    __openIconEditor: function() {
      const iconEditor = new osparc.widget.Renamer(this.getService()["icon"], null, this.tr("Edit Icon"));
      iconEditor.addListener("labelChanged", e => {
        iconEditor.close();
        const newIcon = e.getData()["newLabel"];
        this.__patchService("icon", newIcon);
      }, this);
      iconEditor.center();
      iconEditor.open();
    },

    __openTitleEditor: function() {
      const titleEditor = new osparc.widget.Renamer(this.getService()["name"], null, this.tr("Edit Name"));
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__patchService("name", newLabel);
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __copyStudyIdToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getStudyId());
    },

    __copyNodeIdToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getNodeId());
    },

    __copyKeyToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getService()["key"]);
    },

    __openVersionDisplayEditor: function() {
      const title = this.tr("Edit Version Display");
      const oldVersionDisplay = osparc.service.Utils.extractVersionDisplay(this.getService());
      const versionDisplayEditor = new osparc.widget.Renamer(oldVersionDisplay, null, title);
      versionDisplayEditor.addListener("labelChanged", e => {
        versionDisplayEditor.close();
        const newVersionDisplay = e.getData()["newLabel"];
        this.__patchService("versionDisplay", newVersionDisplay);
      }, this);
      versionDisplayEditor.center();
      versionDisplayEditor.open();
    },

    __openAccessRights: function() {
      const collaboratorsView = osparc.info.ServiceUtils.openAccessRights(this.getService());
      collaboratorsView.addListener("updateAccessRights", e => {
        const updatedServiceData = e.getData();
        this.setService(updatedServiceData);
        this.fireDataEvent("updateService", updatedServiceData);
      }, this);
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const thumbnailEditor = new osparc.editor.ThumbnailEditor(this.getService()["thumbnail"]);
      const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, 300, 115);
      thumbnailEditor.addListener("updateThumbnail", e => {
        win.close();
        const validUrl = e.getData();
        this.__patchService("thumbnail", validUrl);
      }, this);
      thumbnailEditor.addListener("cancel", () => win.close());
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.editor.MarkdownEditor(this.getService()["description"]);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__patchService("description", newDescription);
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __patchService: function(key, value) {
      this.setEnabled(false);
      const serviceDataCopy = osparc.utils.Utils.deepCloneObject(this.getService());
      osparc.store.Services.patchServiceData(serviceDataCopy, key, value)
        .then(() => {
          this.setService(serviceDataCopy);
          this.fireDataEvent("updateService", this.getService());
        })
        .catch(err => {
          const msg = this.tr("An issue occurred while updating the information.");
          osparc.FlashMessenger.logError(err, msg);
        })
        .finally(() => this.setEnabled(true));
    }
  }
});
