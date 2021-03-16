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
    */
  construct: function(serviceData) {
    this.base(arguments);

    console.log("serviceData", serviceData);

    this.set({
      minHeight: 350,
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    this.setService(serviceData);

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
    this.addListener("resize", () => {
      this.__rebuildLayout();
    }, this);
  },

  events: {
    "updateService": "qx.event.type.Data",
    "startService": "qx.event.type.Data"
  },

  properties: {
    service: {
      check: "Object",
      init: null,
      nullable: false
    }
  },

  statics: {
    PADDING: 5,
    EXTRA_INFO_WIDTH: 250,
    THUMBNAIL_MIN_WIDTH: 150,
    THUMBNAIL_MAX_WIDTH: 230
  },

  members: {
    __isOwner: function() {
      return this.getService()["owner"] === osparc.auth.Data.getInstance().getEmail();
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
      let widgetWidth = bounds ? bounds.width - offset : 500 - offset;
      let thumbnailWidth = widgetWidth - 2*this.self().PADDING;
      const maxThumbnailHeight = extraInfo.length*20;
      const slim = widgetWidth < this.self().EXTRA_INFO_WIDTH + this.self().THUMBNAIL_MIN_WIDTH + 2*this.self().PADDING - 20;
      if (slim) {
        this._add(extraInfoLayout);
        thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
        const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);
        this._add(thumbnailLayout);
      } else {
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center"
        }));
        hBox.add(extraInfoLayout);
        thumbnailWidth -= this.self().EXTRA_INFO_WIDTH;
        thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
        const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);
        hBox.add(thumbnailLayout, {
          flex: 1
        });
        this._add(hBox);
      }

      if (this.getService()["description"] || this.__isOwner()) {
        const description = this.__createDescription();
        const descriptionLayout = this.__createViewWithEdit(description, this.__openDescriptionEditor);
        this._add(descriptionLayout);
      }

      if (this.getService()["tags"].length || this.__isOwner()) {
        const tags = this.__createTags();
        const tagsLayout = this.__createViewWithEdit(tags, this.__openTagsEditor);
        if (this.__isOwner()) {
          osparc.utils.Utils.setIdToWidget(tagsLayout.getChildren()[1], "editStudyEditTagsBtn");
        }
        this._add(tagsLayout);
      }
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
        label: this.tr("Key"),
        view: this.__createKey(),
        action: null
      }, {
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
          callback: this.__openAccessRights,
          ctx: this
        }
      }];

      if (this.getService()["classifiers"]) {
        extraInfo.push({
          label: this.tr("Classifiers"),
          view: this.__createClassifiers(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.__openClassifiers,
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
            callback: this.__openQuality,
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

    __createTags: function() {
      return osparc.servicecard.Utils.createTags(this.getService());
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

    __openAccessRights: function() {
      const permissionsView = osparc.servicecard.Utils.openAccessRights(this.getService().serialize());
      permissionsView.addListener("updateService", e => {
        const updatedData = e.getData();
        this.getService().setAccessRights(updatedData["accessRights"]);
        this.fireDataEvent("updateService", updatedData);
      }, this);
    },

    __openClassifiers: function() {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (this.__isOwner()) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(this.getService().serialize());
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedData = e.getData();
          this.getService().setClassifiers(updatedData["classifiers"]);
          this.fireDataEvent("updateService", updatedData);
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(this.getService().serialize());
        osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
      }
    },

    __openQuality: function() {
      const qualityEditor = osparc.servicecard.Utils.openQuality(this.getService().serialize());
      qualityEditor.addListener("updateQuality", e => {
        const updatedData = e.getData();
        this.getService().setQuality(updatedData["quality"]);
        this.fireDataEvent("updateService", updatedData);
      });
    },

    __openTagsEditor: function() {
      const tagManager = new osparc.component.form.tag.TagManager(this.getService().serialize(), null, "study", this.getService().getUuid()).set({
        liveUpdate: false
      });
      tagManager.addListener("updateTags", e => {
        tagManager.close();
        const updatedData = e.getData();
        this.getService().setTags(updatedData["tags"]);
        this.fireDataEvent("updateService", updatedData);
      }, this);
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const thubmnailEditor = new osparc.component.widget.Renamer(this.getService().getThumbnail(), null, title);
      thubmnailEditor.addListener("labelChanged", e => {
        thubmnailEditor.close();
        const dirty = e.getData()["newLabel"];
        const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(dirty);
        if (dirty && dirty !== clean) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was some curation in the text of thumbnail "), "WARNING");
        }
        this.__updateService({
          "thumbnail": clean
        });
      }, this);
      thubmnailEditor.center();
      thubmnailEditor.open();
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const subtitle = this.tr("Supports Markdown");
      const textEditor = new osparc.component.widget.TextEditor(this.getService()["description"], subtitle, title);
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

    __updateService: function(params) {
      this.getService().updateService(params)
        .then(studyData => {
          this.fireDataEvent("updateService", studyData);
          qx.event.message.Bus.getInstance().dispatchByName("updateService", studyData);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    }
  }
});
