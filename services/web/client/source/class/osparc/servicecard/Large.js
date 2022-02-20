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


qx.Class.define("osparc.servicecard.Large", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Serialized Service Object
    * @param openOptions {Boolean} open edit options in new window or fire event
    */
  construct: function(serviceData, openOptions = true) {
    this.base(arguments);

    this.set({
      minHeight: 350,
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this.setService(serviceData);

    if (openOptions !== undefined) {
      this.setOpenOptions(openOptions);
    }

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
    this.addListener("resize", () => {
      this.__rebuildLayout();
    }, this);
  },

  events: {
    "openAccessRights": "qx.event.type.Event",
    "openClassifiers": "qx.event.type.Event",
    "openQuality": "qx.event.type.Event",
    "updateService": "qx.event.type.Data"
  },

  properties: {
    service: {
      check: "Object",
      init: null,
      nullable: false,
      apply: "__rebuildLayout"
    },

    openOptions: {
      check: "Boolean",
      init: true,
      nullable: false
    }
  },

  statics: {
    PADDING: 5,
    EXTRA_INFO_WIDTH: 300,
    THUMBNAIL_MIN_WIDTH: 140,
    THUMBNAIL_MAX_WIDTH: 280
  },

  members: {
    __isOwner: function() {
      return osparc.utils.Services.isOwner(this.getService());
    },

    __rebuildLayout: function() {
      this._removeAll();

      const title = this.__createTitle();
      const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
      this._add(titleLayout);

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);

      const bounds = this.getBounds();
      const offset = 30;
      const maxThumbnailHeight = extraInfo.length*20;
      let widgetWidth = bounds ? bounds.width - offset : 500 - offset;
      let thumbnailWidth = widgetWidth - 2*this.self().PADDING - this.self().EXTRA_INFO_WIDTH;
      thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
      const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
      const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
        alignX: "center"
      }));
      hBox.add(extraInfoLayout);
      hBox.add(thumbnailLayout, {
        flex: 1
      });
      this._add(hBox);

      const description = this.__createDescription();
      const descriptionLayout = this.__createViewWithEdit(description, this.__openDescriptionEditor);
      this._add(descriptionLayout);

      const rawMetadata = this.__createRawMetadata();
      const more = new osparc.desktop.PanelView(this.tr("raw metadata"), rawMetadata).set({
        caretSize: 14
      });
      more.setCollapsed(true);
      more.getChildControl("title").setFont("title-12");
      this._add(more, {
        flex: 1
      });
    },

    __createViewWithEdit: function(view, cb) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      layout.add(view, {
        flex: 1
      });
      if (this.__isOwner()) {
        const editBtn = osparc.utils.Utils.getEditButton();
        editBtn.addListener("execute", () => {
          cb.call(this);
        }, this);
        layout.add(editBtn);
      }

      return layout;
    },

    __createTitle: function() {
      const title = osparc.servicecard.Utils.createTitle(this.getService()).set({
        font: "title-16"
      });
      return title;
    },

    __extraInfo: function() {
      const extraInfo = [{
        label: this.tr("Version"),
        view: this.__createVersion(),
        action: null
      }, {
        label: this.tr("Contact"),
        view: this.__createContact(),
        action: null
      }, {
        label: this.tr("Authors"),
        view: this.__createAuthors(),
        action: null
      }, {
        label: this.tr("Access Rights"),
        view: this.__createAccessRights(),
        action: {
          button: osparc.utils.Utils.getViewButton(),
          callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
          ctx: this
        }
      }];

      if (this.getService()["classifiers"]) {
        extraInfo.push({
          label: this.tr("Classifiers"),
          view: this.__createClassifiers(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.isOpenOptions() ? this.__openClassifiers : "openClassifiers",
            ctx: this
          }
        });
      }

      if (this.getService()["quality"] && osparc.component.metadata.Quality.isEnabled(this.getService()["quality"])) {
        extraInfo.push({
          label: this.tr("Quality"),
          view: this.__createQuality(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.isOpenOptions() ? this.__openQuality : "openQuality",
            ctx: this
          }
        });
      }

      if (osparc.data.Permissions.getInstance().isTester()) {
        extraInfo.unshift({
          label: this.tr("Key"),
          view: this.__createKey(),
          action: {
            button: osparc.utils.Utils.getCopyButton(),
            callback: this.__copyKeyToClipboard,
            ctx: this
          }
        });
      }

      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.servicecard.Utils.createExtraInfo(extraInfo).set({
        width: this.self().EXTRA_INFO_WIDTH
      });

      return moreInfo;
    },

    __createKey: function() {
      return osparc.servicecard.Utils.createKey(this.getService());
    },

    __createVersion: function() {
      return osparc.servicecard.Utils.createVersion(this.getService());
    },

    __createContact: function() {
      return osparc.servicecard.Utils.createContact(this.getService());
    },

    __createAuthors: function() {
      return osparc.servicecard.Utils.createAuthors(this.getService());
    },

    __createAccessRights: function() {
      return osparc.servicecard.Utils.createAccessRights(this.getService());
    },

    __createClassifiers: function() {
      return osparc.servicecard.Utils.createClassifiers(this.getService());
    },

    __createQuality: function() {
      return osparc.servicecard.Utils.createQuality(this.getService());
    },

    __createThumbnail: function(maxWidth, maxHeight = 160) {
      return osparc.servicecard.Utils.createThumbnail(this.getService(), maxWidth, maxHeight);
    },

    __createDescription: function() {
      const maxHeight = 400;
      return osparc.servicecard.Utils.createDescription(this.getService(), maxHeight);
    },

    __createRawMetadata: function() {
      const container = new qx.ui.container.Scroll();
      container.add(new osparc.ui.basic.JsonTreeWidget(this.getService(), "serviceDescriptionSettings"));
      return container;
    },

    __openTitleEditor: function() {
      const title = this.tr("Edit Title");
      const titleEditor = new osparc.component.widget.Renamer(this.getService()["name"], null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__updateService({
          "name": newLabel
        });
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __copyKeyToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getService()["key"]);
    },

    __openAccessRights: function() {
      const permissionsView = osparc.servicecard.Utils.openAccessRights(this.getService());
      permissionsView.addListener("updateService", e => {
        const updatedServiceData = e.getData();
        this.setService(updatedServiceData);
        this.fireDataEvent("updateService", updatedServiceData);
      }, this);
    },

    __openClassifiers: function() {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (this.__isOwner()) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(this.getService());
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedServiceData = e.getData();
          this.setService(updatedServiceData);
          this.fireDataEvent("updateService", updatedServiceData);
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(this.getService());
        osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
      }
    },

    __openQuality: function() {
      const qualityEditor = osparc.servicecard.Utils.openQuality(this.getService());
      qualityEditor.addListener("updateQuality", e => {
        const updatedServiceData = e.getData();
        this.setService(updatedServiceData);
        this.fireDataEvent("updateService", updatedServiceData);
      });
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const thubmnailEditor = new osparc.component.widget.Renamer(this.getService()["thumbnail"], null, title);
      thubmnailEditor.addListener("labelChanged", e => {
        thubmnailEditor.close();
        const dirty = e.getData()["newLabel"];
        const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(dirty);
        if ((dirty && dirty !== clean) || (clean !== "" && !osparc.utils.Utils.isValidHttpUrl(clean))) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Error checking thumbnail link"), "WARNING");
        } else {
          this.__updateService({
            "thumbnail": clean
          });
        }
      }, this);
      thubmnailEditor.center();
      thubmnailEditor.open();
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const subtitle = this.tr("Supports Markdown");
      const textEditor = new osparc.component.editor.TextEditor(this.getService()["description"], subtitle, title);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__updateService({
          "description": newDescription
        });
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __updateService: function(data) {
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this.getService()["key"],
          this.getService()["version"]
        ),
        data: data
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.setService(serviceData);
          this.fireDataEvent("updateService", serviceData);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    }
  }
});
