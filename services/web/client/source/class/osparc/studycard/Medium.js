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


qx.Class.define("osparc.studycard.Medium", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
    */
  construct: function(study) {
    this.base(arguments);

    this.set({
      padding: this.self().PADDING,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(6));

    if (study instanceof osparc.data.model.Study) {
      this.setStudy(study);
    }

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      init: null,
      nullable: false
    }
  },

  statics: {
    PADDING: 0,
    EXTRA_INFO_WIDTH: 220,
    THUMBNAIL_MIN_WIDTH: 110,
    THUMBNAIL_MAX_WIDTH: 180
  },

  members: {
    /**
      * @param studyData {Object} Serialized Study Object
      */
    setStudyData: function(studyData) {
      const study = new osparc.data.model.Study(studyData, false);
      this.setStudy(study);
    },

    checkResize: function(bounds) {
      this.__rebuildLayout(bounds.width);
    },

    __applyStudy: function() {
      this.__rebuildLayout();
    },

    __rebuildLayout: function(width) {
      this._removeAll();

      const nameAndMenuButton = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      }));
      nameAndMenuButton.add(this.__createTitle(), {
        flex: 1
      });
      nameAndMenuButton.add(this.__createMenuButton());
      this._add(nameAndMenuButton);

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);

      const bounds = this.getBounds();
      let widgetWidth = null;
      const offset = 10;
      if (width) {
        widgetWidth = width - offset;
      } else if (bounds) {
        widgetWidth = bounds.width - offset;
      } else {
        widgetWidth = 350 - offset;
      }
      let thumbnailWidth = widgetWidth - 2*this.self().PADDING;
      const maxThumbnailHeight = extraInfo.length*20;
      const slim = widgetWidth < this.self().EXTRA_INFO_WIDTH + this.self().THUMBNAIL_MIN_WIDTH + 2*this.self().PADDING;
      if (slim) {
        this._add(extraInfoLayout);
        thumbnailWidth = Math.min(thumbnailWidth, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
        if (thumbnail) {
          this._add(thumbnail);
        }
      } else {
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center"
        }));
        hBox.add(extraInfoLayout);
        thumbnailWidth -= this.self().EXTRA_INFO_WIDTH;
        thumbnailWidth = Math.min(thumbnailWidth, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
        if (thumbnail) {
          hBox.add(thumbnail, {
            flex: 1
          });
        }
        this._add(hBox);
      }

      const description = this.__createDescription();
      if (description) {
        this._add(description);
      }
    },

    __createMenuButton: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const menuButton = new qx.ui.form.MenuButton().set({
        menu,
        width: 25,
        height: 25,
        icon: "@FontAwesome5Solid/ellipsis-v/14",
        focusable: false
      });

      const moreInfoButton = this.__getMoreInfoMenuButton();
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      return menuButton;
    },

    __getMoreInfoMenuButton: function() {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        this.__openStudyDetails();
      }, this);
      return moreInfoButton;
    },

    __extraInfo: function() {
      const extraInfo = [{
        label: this.tr("Author"),
        view: this.__createOwner(),
        action: null
      }, {
        label: this.tr("Creation Date"),
        view: this.__createCreationDate(),
        action: null
      }, {
        label: this.tr("Last Modified"),
        view: this.__createLastChangeDate(),
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

      if (osparc.component.metadata.Quality.isEnabled(this.getStudy().getQuality())) {
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
      const moreInfo = osparc.studycard.Utils.createExtraInfo(extraInfo).set({
        width: this.self().EXTRA_INFO_WIDTH
      });

      return moreInfo;
    },

    __createTitle: function() {
      return osparc.studycard.Utils.createTitle(this.getStudy());
    },

    __createOwner: function() {
      return osparc.studycard.Utils.createOwner(this.getStudy());
    },

    __createCreationDate: function() {
      return osparc.studycard.Utils.createCreationDate(this.getStudy());
    },

    __createLastChangeDate: function() {
      return osparc.studycard.Utils.createLastChangeDate(this.getStudy());
    },

    __createAccessRights: function() {
      return osparc.studycard.Utils.createAccessRights(this.getStudy());
    },

    __createQuality: function() {
      return osparc.studycard.Utils.createQuality(this.getStudy());
    },

    __createThumbnail: function(maxWidth, maxHeight = 150) {
      if (this.getStudy().getThumbnail()) {
        return osparc.studycard.Utils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
      }
      return null;
    },

    __createDescription: function() {
      if (this.getStudy().getDescription()) {
        const maxHeight = 300;
        return osparc.studycard.Utils.createDescription(this.getStudy(), maxHeight);
      }
      return null;
    },

    __openAccessRights: function() {
      const permissionsView = osparc.studycard.Utils.openAccessRights(this.getStudy().serialize());
      permissionsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        this.getStudy().setAccessRights(updatedData["accessRights"]);
      });
    },

    __openQuality: function() {
      const qualityEditor = osparc.studycard.Utils.openQuality(this.getStudy().serialize());
      qualityEditor.addListener("updateQuality", e => {
        const updatedData = e.getData();
        this.getStudy().setQuality(updatedData["quality"]);
      });
    },

    __openStudyDetails: function() {
      const studyDetails = new osparc.studycard.Large(this.getStudy());
      const title = this.tr("Study Details");
      const width = 500;
      const height = 500;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
    }
  }
});
